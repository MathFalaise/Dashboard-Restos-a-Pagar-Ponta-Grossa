"""Coletor: transforma consultas ao portal em snapshots imutaveis.

Ordem de gravacao de um snapshot (e por que):
  1. objetos no armazem (bytes, conferidos pelo hash);
  2. manifesto no armazem (imutavel) - a partir daqui o snapshot EXISTE;
  3. registro no banco (camada 0). Se falhar, `banco.sincronizar` completa depois.

Regras de negocio que o coletor garante (Etapa 02 secoes 8 e 11; Etapa 03 secao 4.2):
  * listagem de RP sempre SEM `tipoPesquisa` e com `dataInicial` = 01/01 do exercicio;
  * `dataFinal` tem de estar no mesmo ano do exercicio (nunca mistura anos);
  * paginacao ate `last`, conferindo que `totalElements` nao muda entre paginas e que a soma
    das paginas nunca passa dele (servidor que ignore `page` nao prende o coletor em laco);
  * snapshot incompleto ou falho tambem e gravado - com status que impede seu uso.
"""
import json
import logging
import re
from datetime import date

from . import VERSAO, agora, hash_do_codigo
from .http import ErroDeRede
from .snapshots import gravar_snapshot

log = logging.getLogger("rp.coletor")

EP_RP = "/empenhos/restos-a-pagar"
EP_MOV = "/empenhos/detalhe/movimentacao"
EP_PUB = "/api/publicacoes/1"
EP_ARQ = "/api/files/arquivo"
EP_ENT = "/api/entidades/lista"
EP_EXE = "/api/exercicios/entidade"
TAMANHO_PAGINA = 2000
MAX_PAGINAS = 10_000     # teto de seguranca: 20 milhoes de registros por corte, muito acima do real


class ParametroInvalido(ValueError):
    pass


def _inteiro_positivo(v):
    """True para int (nao bool) maior que zero."""
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


class Coletor:
    def __init__(self, cfg, con, armazem, cliente):
        self.cfg, self.con, self.armazem, self.cliente = cfg, con, armazem, cliente
        h = hash_do_codigo()
        self.identidade = {"nome": "rp-coletor", "versao": f"{VERSAO}+{h[:12]}", "sha256_codigo": h,
                           "descricao": "coletor de produção (app/rp)"}

    # ----------------------------------------------------------------- nucleo
    def _snapshot(self, tipo, endpoint, parametros, respostas, status, coletada_em, observacoes):
        s = gravar_snapshot(
            self.con, self.armazem, tipo=tipo, endpoint=endpoint, parametros=parametros, coletada_em=coletada_em,
            origem_carimbo="relogio_coletor", status=status, coletor=self.identidade,
            observacao="; ".join(observacoes) or None,
            respostas=[{"url": r.url, "http_status": r.status, "cabecalhos": r.cabecalhos, "recebida_em": r.recebida_em,
                        "tentativas": r.tentativas, "corpo": r.corpo} for r in respostas])
        log.info("snapshot %s %s %s: %s, %d resposta(s), coleta %d", tipo, json.dumps(parametros, ensure_ascii=False),
                 s["snapshot_uid"][:8], status, s["respostas"], s["coleta_id"])
        return s

    def _paginado(self, endpoint, params):
        """Todas as paginas de um endpoint no formato Page do Spring. Devolve (respostas, status, observacoes)."""
        respostas, obs, total, soma, paginas, pagina = [], [], None, 0, None, 0
        while True:
            try:
                r = self.cliente.get(endpoint, {**params, "page": pagina})
            except ErroDeRede as e:
                return respostas, "falhou", obs + [str(e)]
            respostas.append(r)
            if r.status != 200:
                return respostas, "falhou", obs + [f"página {pagina}: HTTP {r.status}"]
            try:
                d = json.loads(r.corpo)
                conteudo = d["content"]
                if not isinstance(conteudo, list):
                    raise TypeError("content nao e lista")
            except (ValueError, KeyError, TypeError, RecursionError) as e:
                return respostas, "falhou", obs + [f"página {pagina}: resposta não é uma página JSON ({e})"]
            if total is None:
                total, paginas = d.get("totalElements"), d.get("totalPages")
            elif d.get("totalElements") != total:
                return respostas, "incompleta", obs + [f"totalElements mudou de {total} para {d.get('totalElements')} "
                                                       f"na página {pagina}: a base mudou durante a coleta"]
            soma += len(conteudo)
            if isinstance(total, int) and soma > total:
                return respostas, "incompleta", obs + [f"soma das paginas {soma} passou de totalElements {total}"]
            if d.get("last") or not conteudo:
                break
            pagina += 1
            if paginas is not None and pagina > paginas:
                return respostas, "incompleta", obs + [f"paginação passou de totalPages={paginas}"]
            if pagina >= MAX_PAGINAS:
                return respostas, "incompleta", obs + [f"paginacao passou do teto de {MAX_PAGINAS} paginas"]
        if soma != total:
            return respostas, "incompleta", obs + [f"soma das páginas {soma} ≠ totalElements {total}"]
        return respostas, "completa", obs

    # ----------------------------------------------------------------- tipos
    def listagem(self, entidade, exercicio, data_final):
        """Snapshot da listagem de RP de uma entidade num corte (01/01 -> data_final)."""
        df = date.fromisoformat(data_final)
        if df.year != exercicio:
            raise ParametroInvalido(f"dataFinal {data_final} fora do exercício {exercicio}: combinação proibida (Etapa 02 §8)")
        params = {"entidade": int(entidade), "exercicio": int(exercicio), "dataInicial": f"{exercicio}-01-01",
                  "dataFinal": data_final, "size": TAMANHO_PAGINA}
        inicio = agora()
        respostas, status, obs = self._paginado(EP_RP, params)
        return self._snapshot("rp_listagem", EP_RP, params, respostas, status, inicio, obs)

    def recoletar(self, ref):
        """Nova coleta de um corte JA coletado, com EXATAMENTE os parametros do snapshot `ref` (uid ou id).
        O snapshot anterior nao e tocado: a recoleta e outro snapshot, que registra de qual veio."""
        col = "snapshot_uid" if isinstance(ref, str) and not str(ref).isdigit() else "id"
        row = self.con.execute(f"SELECT snapshot_uid, tipo, parametros_json FROM coleta WHERE {col}=?", (ref,)).fetchone()
        if not row:
            raise ParametroInvalido(f"snapshot {ref} não existe")
        uid, tipo, pj = row
        params = json.loads(pj)
        if tipo != "rp_listagem":
            raise ParametroInvalido(f"recoleta só de listagem de RP (snapshot {uid} é {tipo})")
        if "tipoPesquisa" in params or params.get("dataInicial") != f"{params['exercicio']}-01-01":
            raise ParametroInvalido(f"snapshot {uid} usa parâmetros fora da regra de produção (tipo/dataInicial): "
                                    "não é recoletado para não criar corte proibido")
        inicio = agora()
        respostas, status, obs = self._paginado(EP_RP, params)
        return self._snapshot("rp_listagem", EP_RP, params, respostas, status, inicio, [f"recoleta de {uid}"] + obs)

    def movimentacao(self, entidade, anoempenho, empenho):
        params = {"entidade": int(entidade), "exercicio": int(anoempenho), "empenho": int(empenho), "size": 500}
        inicio = agora()
        respostas, status, obs = self._paginado(EP_MOV, params)
        meta = {"entidade": int(entidade), "anoempenho": int(anoempenho), "empenho": int(empenho), "size": 500}
        return self._snapshot("movimentacao", EP_MOV, meta, respostas, status, inicio, obs)

    def _simples(self, tipo, endpoint, params, meta, validar):
        inicio = agora()
        obs = []
        try:
            r = self.cliente.get(endpoint, params)
            respostas = [r]
            status = "completa" if r.status == 200 and validar(r) else "falhou"
            if status == "falhou":
                obs.append(f"HTTP {r.status} ou conteúdo inesperado")
        except ErroDeRede as e:
            respostas, status = [], "falhou"
            obs.append(str(e))
        return self._snapshot(tipo, endpoint, meta, respostas, status, inicio, obs), (respostas[0] if respostas else None)

    def catalogos(self, entidades):
        feitos = []
        json_ok = lambda r: _json(r.corpo) is not None
        s, _ = self._simples("entidades", EP_ENT, None, {}, json_ok)
        feitos.append(s)
        for e in entidades:
            s, _ = self._simples("exercicios", f"{EP_EXE}/{int(e)}", None, {"entidade": int(e)}, json_ok)
            feitos.append(s)
        return feitos

    def rreo(self, exercicio, entidade=1, ids=None, baixar_pdfs=True, bimestres=None):
        """Listagem de publicacoes da LRF (grupo 1) e PDFs do RREO Anexo VII ainda nao coletados.
        `bimestres` (ex. {6}): so os PDFs desses bimestres (rotulos como "6o Bimestre", "6o BIMESTRE" e
        "6o Bimestre - Consolidado"; no portal o "o" e o indicador ordinal).
        Arquivo cujo idArquivo nao e inteiro positivo e ignorado e vai para o log: nenhum texto vindo da
        resposta entra na URL."""
        params = {"entidade": int(entidade), "exercicio": int(exercicio)}
        s, r = self._simples("publicacoes", EP_PUB, params, dict(params), lambda r: isinstance(_json(r.corpo), list))
        feitos = [s]
        if s["status"] != "completa" or not baixar_pdfs:
            return feitos
        for arq in anexo_vii(_json(r.corpo)):
            if not isinstance(arq, dict) or not _inteiro_positivo(arq.get("idArquivo")):
                log.warning("publicacao ignorada: idArquivo invalido em %r", arq)
                continue
            if ids and arq["idArquivo"] not in ids:
                continue
            if bimestres and not any(re.match(rf"\s*{b}\s*º\s*bimestre", str(arq.get("valor", "")), re.I) for b in bimestres):
                continue  # o rotulo varia entre anos: "6o Bimestre", "6o BIMESTRE", "4 o Bimestre"
            ja = self.con.execute("SELECT 1 FROM coleta WHERE tipo='rreo_pdf' AND id_arquivo=? AND status='completa'",
                                  (arq["idArquivo"],)).fetchone()
            if ja:
                continue
            meta = {"id_arquivo": arq["idArquivo"], "exercicio": int(exercicio), "entidade": int(entidade),
                    "rotulo": arq["valor"], "nomeArquivo": arq.get("nomeArquivo"), "dataArquivo": arq.get("dataArquivo")}
            s, _ = self._simples("rreo_pdf", f"{EP_ARQ}/{arq['idArquivo']}", None, meta, lambda r: r.corpo[:4] == b"%PDF")
            feitos.append(s)
        return feitos


def _json(b):
    try:
        return json.loads(b)
    except (ValueError, RecursionError):
        return None


def anexo_vii(publicacoes):
    """Arquivos do subgrupo 'Anexo VII - Demonstrativo dos Restos a Pagar...' na listagem de publicacoes."""
    for grupo in publicacoes if isinstance(publicacoes, list) else []:
        if not isinstance(grupo, dict):
            continue
        for sub in grupo.get("list") or []:
            if not isinstance(sub, dict):
                continue
            nome = (sub.get("subGrupoRelatorio") or {}).get("valor", "")
            if "Restos a Pagar" in str(nome) and "Anexo VII" in str(nome):
                yield from sub.get("list") or []
