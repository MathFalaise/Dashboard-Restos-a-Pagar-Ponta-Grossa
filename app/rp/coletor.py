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
  * contrato da pagina conferido (auditoria COL-02/03): `totalElements` inteiro, `number` = pagina pedida,
    `numberOfElements` = tamanho de `content`, `content` nao maior que o `size` ecoado, `totalPages` coerente;
    `first` e `empty` coerentes (revisao, item 2; presentes e coerentes nas 322 paginas reais gravadas);
  * soma = total NAO prova que os registros sao distintos (auditoria COL-01). Por isso, alem dela:
      - nenhum registro identico pode reaparecer numa pagina seguinte;
      - na listagem de RP, a chave (anoempenho, empenho) nao pode diminuir e precisa CRESCER na troca de pagina
        (ordem real da API em 100% dos snapshots gravados; nao e contrato documentado - se a API mudar a ordem,
        a coleta falha visivelmente em vez de aceitar paginas deslocadas);
      - com mais de uma pagina, todas sao lidas de novo e precisam vir iguais (a base nao mudou no meio). A
        segunda leitura vai para o manifesto ("segunda_leitura"), fora das respostas normalizadas;
  * a listagem de RP PEDE a ordem (anoempenho, empenho) em `sort` e confere o eco em cada pagina (revisao, item 3):
    a ordem deixa de ser so a observada. Sondagem de 05/10/2026: com essa ordem a API devolve o mesmo content da
    ordem implicita (auditoria/sondagem_ordenacao.json);
  * a chave de negocio (entidade, anoempenho, empenho) nao pode repetir no retrato inteiro, dentro ou entre
    paginas (revisao, itens 1 e 2). Repetida, o snapshot fica `incompleta`: e preservado, mas nunca vira o retrato
    vigente do corte. A observacao diz quantas chaves repetiram e se as copias sao identicas (exatas) ou diferem
    (conflitantes);
  * catalogo so e 'completa' se cumprir o contrato minimo (contrato.py): JSON valido nao basta (revisao, item 6);
  * o manifesto registra quando a coleta terminou (`coleta_finalizada_em`) e a forma da resposta (`contrato_api`):
    uma coleta de varias paginas e um retrato montado por consultas sucessivas, nao uma fotografia atomica da base
    (revisao, itens 17 e 18);
  * snapshot incompleto ou falho tambem e gravado - com status que impede seu uso.
"""
import json
import logging
import re
from datetime import date

from . import VERSAO, agora, contrato, hash_do_codigo
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


def _inteiro(v):
    return isinstance(v, int) and not isinstance(v, bool)


def chave_rp(registro):
    """Ordem da listagem de RP na API: (anoempenho, empenho)."""
    return (registro["anoempenho"], registro["empenho"])


def conferir_pagina(d, pagina, size, total, paginas, conteudo, sort=None):
    """Problema no contrato da pagina (texto) ou None. Campo ausente nao e cobrado aqui (a API real sempre os manda;
    totalElements, o unico indispensavel, e cobrado em _paginado). `sort`: ordem pedida; se a pagina ecoar `sort`,
    o eco tem de ser exatamente ela - servidor que ignora a ordem pedida nao produz retrato 'completa'."""
    if d.get("number") is not None and d.get("number") != pagina:
        return f"página {pagina}: a API devolveu a página number={d.get('number')}"
    if d.get("numberOfElements") is not None and d.get("numberOfElements") != len(conteudo):
        return f"página {pagina}: numberOfElements={d.get('numberOfElements')} mas content tem {len(conteudo)}"
    if d.get("first") is not None and d.get("first") is not (pagina == 0):     # revisao, item 2
        return f"página {pagina}: first={d.get('first')!r} incoerente com a página pedida"
    if d.get("empty") is not None and d.get("empty") is not (not conteudo):
        return f"página {pagina}: empty={d.get('empty')!r} mas content tem {len(conteudo)}"
    eco = d.get("size")
    if eco is not None and (not _inteiro_positivo(eco) or (size is not None and eco > size) or len(conteudo) > eco):
        return f"página {pagina}: size ecoado {eco!r} incoerente com o pedido ({size}) e com content ({len(conteudo)})"
    if paginas is not None and _inteiro(total) and _inteiro_positivo(eco) and paginas != -(-total // eco):
        return f"página {pagina}: totalPages={paginas} incoerente com totalElements={total} e size={eco}"
    if sort and "sort" in d and not contrato.sort_ecoado_confere(d["sort"], sort):
        return (f"página {pagina}: a API não aplicou a ordenação pedida {list(sort)} "
                f"(sort ecoado {json.dumps(d['sort'], ensure_ascii=False)[:200]})")
    return None


def _descrever_repetidas(repetidas):
    """Texto da observacao de chaves de negocio repetidas: quantas, quantas exatas/conflitantes, exemplos."""
    exatas = sorted(k for k, n in repetidas.items() if n == "exata")
    conflitantes = sorted(k for k, n in repetidas.items() if n == "conflitante")
    exemplos = ", ".join(f"{k[1]}/{k[2]}" for k in (conflitantes or exatas)[:3])
    return (f"chave de negócio (entidade, anoempenho, empenho) repetida no retrato: {len(repetidas)} chave(s), "
            f"{len(exatas)} exata(s) (cópias idênticas) e {len(conflitantes)} conflitante(s) (conteúdo diferente); "
            f"ex.: {exemplos}. Snapshot preservado, mas não vira o retrato vigente do corte: recolete")


class Coletor:
    def __init__(self, cfg, con, armazem, cliente):
        self.cfg, self.con, self.armazem, self.cliente = cfg, con, armazem, cliente
        h = hash_do_codigo()
        self.identidade = {"nome": "rp-coletor", "versao": f"{VERSAO}+{h[:12]}", "sha256_codigo": h,
                           "descricao": "coletor de produção (app/rp)"}

    # ----------------------------------------------------------------- nucleo
    def _snapshot(self, tipo, endpoint, parametros, respostas, status, coletada_em, observacoes, segunda_leitura=None):
        s = gravar_snapshot(
            self.con, self.armazem, tipo=tipo, endpoint=endpoint, parametros=parametros, coletada_em=coletada_em,
            origem_carimbo="relogio_coletor", status=status, coletor=self.identidade,
            observacao="; ".join(observacoes) or None, segunda_leitura=segunda_leitura,
            respostas=[{"url": r.url, "http_status": r.status, "cabecalhos": r.cabecalhos, "recebida_em": r.recebida_em,
                        "tentativas": r.tentativas, "corpo": r.corpo} for r in respostas],
            finalizada_em=agora(), contrato_api=contrato.descricao_forma([r.corpo for r in respostas]))
        log.info("snapshot %s %s %s: %s, %d resposta(s), coleta %d", tipo, json.dumps(parametros, ensure_ascii=False),
                 s["snapshot_uid"][:8], status, s["respostas"], s["coleta_id"])
        return s

    def _paginado(self, endpoint, params, chave=None):
        """Todas as paginas de um endpoint no formato Page do Spring. Devolve (respostas, status, observacoes,
        segunda_leitura). `chave`: funcao do registro cuja sequencia nao pode diminuir e precisa crescer na troca
        de pagina (listagem de RP); com ela, a chave de NEGOCIO (contrato.chave_negocio) tambem nao pode repetir no
        retrato - nem entre paginas (paginacao deslocada) nem dentro de uma pagina (a propria API repetiu)."""
        respostas, obs, total, paginas, soma, pagina = [], [], None, None, 0, 0
        vistos, ultima = set(), None
        primeira = {}        # chave de negocio -> forma canonica da primeira ocorrencia
        repetidas = {}       # chave de negocio -> "exata" | "conflitante"

        def fim(status, mensagem):
            return respostas, status, obs + [mensagem], None
        while True:
            try:
                r = self.cliente.get(endpoint, {**params, "page": pagina})
            except ErroDeRede as e:
                return fim("falhou", str(e))
            respostas.append(r)
            if r.status != 200:
                return fim("falhou", f"página {pagina}: HTTP {r.status}")
            try:
                d = json.loads(r.corpo)
                conteudo = d["content"]
                if not isinstance(conteudo, list):
                    raise TypeError("content nao e lista")
            except (ValueError, KeyError, TypeError, RecursionError) as e:
                return fim("falhou", f"página {pagina}: resposta não é uma página JSON ({e})")
            if pagina == 0:
                total, paginas = d.get("totalElements"), d.get("totalPages")
                if not _inteiro(total) or total < 0:      # sem total o teto pela soma nao vale (auditoria COL-03)
                    return fim("incompleta", f"totalElements ausente ou não inteiro: {total!r}")
                if paginas is not None and (not _inteiro(paginas) or paginas < 0):
                    return fim("incompleta", f"totalPages não inteiro: {paginas!r}")
            elif d.get("totalElements") != total:
                return fim("incompleta", f"totalElements mudou de {total} para {d.get('totalElements')} "
                                         f"na página {pagina}: a base mudou durante a coleta")
            problema = conferir_pagina(d, pagina, params.get("size"), total, paginas, conteudo, params.get("sort"))
            if problema:
                return fim("incompleta", problema)
            novos = set()
            for i, x in enumerate(conteudo):
                canon = json.dumps(x, sort_keys=True, ensure_ascii=False)
                if canon in vistos:
                    return fim("incompleta", f"página {pagina}: registro idêntico a um de página anterior "
                                             "(paginação deslocada ou página repetida)")
                novos.add(canon)
                if chave is not None:
                    try:
                        k = chave(x)
                        recuou = ultima is not None and (k < ultima or (i == 0 and k == ultima))
                    except (KeyError, TypeError):
                        return fim("incompleta", f"página {pagina}: registro sem chave de ordem comparável")
                    if recuou:
                        return fim("incompleta", f"página {pagina}: ordem (anoempenho, empenho) não cresce em {k} "
                                                 f"depois de {ultima} (página deslocada, repetida ou ordem da API mudou)")
                    ultima = k
                    if params.get("entidade") is not None and x.get("entidade") != params["entidade"]:
                        return fim("incompleta", f"página {pagina}: registro da entidade {x.get('entidade')!r} numa "
                                                 f"listagem da entidade {params['entidade']} (resposta de outra consulta)")
                    negocio = contrato.chave_negocio(x)
                    if negocio in primeira:
                        anterior = repetidas.get(negocio, "exata")
                        repetidas[negocio] = "conflitante" if anterior == "conflitante" or primeira[negocio] != canon \
                            else "exata"
                    else:
                        primeira[negocio] = canon
            if repetidas:           # a pagina inteira foi conferida: a observacao classifica todas as repeticoes dela
                return fim("incompleta", _descrever_repetidas(repetidas))
            vistos |= novos
            soma += len(conteudo)
            if soma > total:
                return fim("incompleta", f"soma das paginas {soma} passou de totalElements {total}")
            if d.get("last") or not conteudo:
                break
            pagina += 1
            if paginas is not None and pagina >= paginas:     # paginas comecam em 0 (auditoria COL-04)
                return fim("incompleta", f"a página {pagina - 1} não é a última (last=false), mas totalPages={paginas}")
            if pagina >= MAX_PAGINAS:
                return fim("incompleta", f"paginacao passou do teto de {MAX_PAGINAS} paginas")
        if soma != total:
            return fim("incompleta", f"soma das páginas {soma} ≠ totalElements {total}")
        if len(respostas) == 1:      # uma resposta e um retrato atomico da base: nada a conferir
            return respostas, "completa", obs, None
        return self._segunda_leitura(endpoint, params, respostas, obs)

    def _segunda_leitura(self, endpoint, params, respostas, obs):
        """Le de novo cada pagina; o snapshot so e 'completa' se todas vierem com o mesmo content e o mesmo total.
        Detecta o deslocamento compensado (exclusao antes do ponto + inclusao depois) que soma, total e ordem nao veem."""
        segunda = []
        for pagina, r1 in enumerate(respostas):
            try:
                r2 = self.cliente.get(endpoint, {**params, "page": pagina})
            except ErroDeRede as e:
                return respostas, "incompleta", obs + [f"segunda leitura da página {pagina} falhou: {e}"], segunda
            try:
                a, b = json.loads(r1.corpo), json.loads(r2.corpo)
                igual = r2.status == 200 and a["content"] == b["content"] and a["totalElements"] == b["totalElements"]
            except (ValueError, KeyError, TypeError, RecursionError):
                igual = False
            segunda.append({"ordem": pagina, "url": r2.url, "http_status": r2.status, "cabecalhos": r2.cabecalhos,
                            "recebida_em": r2.recebida_em, "tentativas": r2.tentativas, "corpo": r2.corpo,
                            "igual": igual})
            if not igual:
                return respostas, "incompleta", obs + [f"segunda leitura da página {pagina} diferente da primeira: "
                                                       "a base mudou durante a coleta"], segunda
        return respostas, "completa", obs + [f"segunda leitura das {len(segunda)} páginas idêntica"], segunda

    # ----------------------------------------------------------------- tipos
    def listagem(self, entidade, exercicio, data_final):
        """Snapshot da listagem de RP de uma entidade num corte (01/01 -> data_final)."""
        df = date.fromisoformat(data_final)
        if df.year != exercicio:
            raise ParametroInvalido(f"dataFinal {data_final} fora do exercício {exercicio}: combinação proibida (Etapa 02 §8)")
        params = {"entidade": int(entidade), "exercicio": int(exercicio), "dataInicial": f"{exercicio}-01-01",
                  "dataFinal": data_final, "size": TAMANHO_PAGINA, "sort": list(contrato.ORDEM_RP)}
        inicio = agora()
        respostas, status, obs, segunda = self._paginado(EP_RP, params, chave_rp)
        obs = self._fora_do_catalogo(int(entidade), int(exercicio)) + obs
        return self._snapshot("rp_listagem", EP_RP, params, respostas, status, inicio, obs, segunda)

    def _fora_do_catalogo(self, entidade, exercicio):
        """Observacao quando a entidade (ou o exercicio dela) nao esta no catalogo vigente ja coletado: a API devolve
        200 com 0 registros para entidade ou exercicio inexistente, o que seria lido como 'sem RP' (auditoria COL-05).
        So informa; a coleta nao e recusada (entidade extinta pode faltar do catalogo atual)."""
        from . import banco
        obs = []
        consultas = (
            ("entidades", "", (), lambda d: any(isinstance(x, dict) and x.get("id") == entidade for x in d),
             f"entidade {entidade}"),
            ("exercicios", " AND c.entidade=?", (entidade,),
             lambda d: any(isinstance(x, dict) and isinstance(x.get("id"), dict) and x["id"].get("exercicio") == exercicio
                           for x in d), f"exercício {exercicio} da entidade {entidade}"))
        for tipo, filtro, p, achou, alvo in consultas:
            row = self.con.execute(
                "SELECT c.snapshot_uid, r.sha256 FROM coleta c JOIN resposta_bruta r ON r.coleta_id = c.id "
                f"WHERE c.tipo=? AND c.status='completa'{filtro} ORDER BY c.coletada_em DESC, c.snapshot_uid DESC LIMIT 1",
                (tipo, *p)).fetchone()
            if not row:
                continue
            d = _json(banco.corpo(self.con, row[1]))
            if isinstance(d, list) and not achou(d):
                obs.append(f"{alvo} fora do catálogo vigente ({tipo}, snapshot {row[0][:8]}): resposta vazia da API "
                           "não distingue 'sem RP' de entidade ou exercício inexistente")
        return obs

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
        respostas, status, obs, segunda = self._paginado(EP_RP, params, chave_rp)
        return self._snapshot("rp_listagem", EP_RP, params, respostas, status, inicio, [f"recoleta de {uid}"] + obs,
                              segunda)

    def movimentacao(self, entidade, anoempenho, empenho):
        params = {"entidade": int(entidade), "exercicio": int(anoempenho), "empenho": int(empenho), "size": 500}
        inicio = agora()
        respostas, status, obs, segunda = self._paginado(EP_MOV, params)
        meta = {"entidade": int(entidade), "anoempenho": int(anoempenho), "empenho": int(empenho), "size": 500}
        return self._snapshot("movimentacao", EP_MOV, meta, respostas, status, inicio, obs, segunda)

    def _simples(self, tipo, endpoint, params, meta, validar):
        """Uma requisicao. `validar(resposta)` devolve o problema do conteudo (texto) ou None: so HTTP 200 com
        conteudo dentro do contrato e 'completa'."""
        inicio = agora()
        obs = []
        try:
            r = self.cliente.get(endpoint, params)
            respostas = [r]
            problema = f"HTTP {r.status}" if r.status != 200 else validar(r)
            status = "falhou" if problema else "completa"
            if problema:
                obs.append(problema)
        except ErroDeRede as e:
            respostas, status = [], "falhou"
            obs.append(str(e))
        return self._snapshot(tipo, endpoint, meta, respostas, status, inicio, obs), (respostas[0] if respostas else None)

    def catalogos(self, entidades):
        """Catalogo de entidades e, por entidade, o de exercicios. JSON valido nao basta: cada um precisa cumprir o
        contrato minimo (contrato.py), senao o snapshot fica 'falhou' com o motivo (revisao, item 6)."""
        feitos = []
        s, _ = self._simples("entidades", EP_ENT, None, {}, lambda r: contrato.contrato_entidades(_json(r.corpo)))
        feitos.append(s)
        for e in entidades:
            s, _ = self._simples("exercicios", f"{EP_EXE}/{int(e)}", None, {"entidade": int(e)},
                                 lambda r, e=int(e): contrato.contrato_exercicios(_json(r.corpo), e))
            feitos.append(s)
        return feitos

    def rreo(self, exercicio, entidade=None, ids=None, baixar_pdfs=True, bimestres=None):
        """Listagem de publicacoes da LRF (grupo 1) e PDFs do RREO Anexo VII ainda nao coletados.
        `bimestres` (ex. {6}): so os PDFs desses bimestres (rotulos como "6o Bimestre", "6o BIMESTRE" e
        "6o Bimestre - Consolidado"; no portal o "o" e o indicador ordinal).
        Arquivo cujo idArquivo nao e inteiro positivo e ignorado e vai para o log: nenhum texto vindo da
        resposta entra na URL."""
        entidade = self.cfg.entidade_rreo if entidade is None else entidade   # config.toml [rreo]
        params = {"entidade": int(entidade), "exercicio": int(exercicio)}
        s, r = self._simples("publicacoes", EP_PUB, params, dict(params),
                             lambda r: contrato.contrato_publicacoes(_json(r.corpo)))
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
            s, _ = self._simples("rreo_pdf", f"{EP_ARQ}/{arq['idArquivo']}", None, meta,
                                 lambda r: None if r.corpo[:4] == b"%PDF" else "o corpo não começa com %PDF")
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
