"""Collector: turns portal queries into immutable snapshots.

Write order of a snapshot (and why):
  1. objects in the store (bytes, checked against their hash);
  2. manifest in the store (immutable) - from here on the snapshot EXISTS;
  3. row in the database (layer 0). If it fails, `banco.sincronizar` completes it later.

Business rules the collector guarantees (stage 02 sections 8 and 11; stage 03 section 4.2):
  * the RP listing is always WITHOUT `tipoPesquisa` and with `dataInicial` = 01/01 of the fiscal year;
  * `dataFinal` must be in the same year as the fiscal year (years are never mixed);
  * pagination until `last`, checking that `totalElements` does not change between pages and that the sum of the
    pages never exceeds it (a server that ignores `page` cannot trap the collector in a loop);
  * strict contract (contrato.py v2, 09/10/2026): every page brings all the Spring Page metadata with its type, and
    every record of the RP listing / movement list brings exactly the known keys with their types. A missing or
    extra key, a null money field or another type makes the snapshot 'incompleta' with the reason: a change of
    structure is never absorbed, and a missing money field never becomes zero further down;
  * page contract checked (audit COL-02/03): integer `totalElements`, `number` = requested page,
    `numberOfElements` = size of `content`, `content` not larger than the echoed `size`, consistent `totalPages`;
    consistent `first` and `empty` (review, item 2; present and consistent in the 322 real pages recorded);
  * sum = total does NOT prove the records are distinct (audit COL-01). So, besides it:
      - no identical record may reappear on a later page;
      - in the RP listing, the key (anoempenho, empenho) cannot decrease and must GROW at the page boundary
        (the API's real order in 100% of the recorded snapshots; it is not a documented contract - if the API
        changes the order, collection fails visibly instead of accepting shifted pages);
      - with more than one page, all pages are read again and must come back equal (the base did not change
        midway). The second read goes to the manifest ("segunda_leitura"), outside the normalized responses;
  * the RP listing ASKS for the order (anoempenho, empenho) in `sort` and checks the echo on every page (review,
    item 3): the order is no longer only observed. Probe of 05/10/2026: with this order the API returns the same
    content as the implicit order (docs/audits/sondagem_ordenacao.json);
  * the business key (entidade, anoempenho, empenho) cannot repeat in the whole snapshot, within or across pages
    (review, items 1 and 2). If repeated, the snapshot is `incompleta`: it is kept, but it never becomes the
    current snapshot of the cut-off. The note says how many keys repeated and whether the copies are identical
    (exact) or differ (conflicting);
  * a catalog is only 'completa' if it meets the minimum contract (contrato.py): valid JSON is not enough (review,
    item 6);
  * the manifest records when the collection finished (`coleta_finalizada_em`) and the shape of the response
    (`contrato_api`): a multi-page collection is a snapshot built from successive queries, not an atomic picture of
    the base (review, items 17 and 18);
  * an incomplete or failed snapshot is recorded too - with a status that prevents its use.
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
MAX_PAGINAS = 10_000     # safety ceiling: 20 million records per cut-off, far above reality


class ParametroInvalido(ValueError):
    pass


def _inteiro_positivo(v):
    """True for an int (not bool) greater than zero."""
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


def _inteiro(v):
    return isinstance(v, int) and not isinstance(v, bool)


def chave_rp(registro):
    """Order of the RP listing in the API: (anoempenho, empenho)."""
    return (registro["anoempenho"], registro["empenho"])


def conferir_pagina(d, pagina, size, total, paginas, conteudo, sort=None):
    """A problem in the page contract (text) or None. A missing field is not required here (the real API always sends
    them; totalElements, the only indispensable one, is required in _paginado). `sort`: requested order; if the page
    echoes `sort`, the echo must be exactly it - a server that ignores the requested order yields no 'completa'
    snapshot."""
    if d.get("number") is not None and d.get("number") != pagina:
        return f"página {pagina}: a API devolveu a página number={d.get('number')}"
    if d.get("numberOfElements") is not None and d.get("numberOfElements") != len(conteudo):
        return f"página {pagina}: numberOfElements={d.get('numberOfElements')} mas content tem {len(conteudo)}"
    if d.get("first") is not None and d.get("first") is not (pagina == 0):     # review, item 2
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
    """Note text for repeated business keys: how many, how many exact/conflicting, examples."""
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

    # ----------------------------------------------------------------- core
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

    def _paginado(self, endpoint, params, chave=None, registro=None):
        """All pages of an endpoint in the Spring Page format. Returns (respostas, status, observacoes, segunda_leitura).
        `chave`: function of the record whose sequence cannot decrease and must grow at the page boundary (RP
        listing); with it, the BUSINESS key (contrato.chave_negocio) cannot repeat in the snapshot either - neither
        across pages (shifted pagination) nor within a page (the API itself repeated it).
        `registro`: contract of each record (contrato.contrato_registro_*), checked before anything else uses it."""
        respostas, obs, total, paginas, soma, pagina = [], [], None, None, 0, 0
        vistos, ultima = set(), None
        primeira = {}        # business key -> canonical form of the first occurrence
        repetidas = {}       # business key -> "exata" | "conflitante"

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
            problema = contrato.contrato_pagina(d)
            if problema is None and registro is not None:
                problema = next((f"registro {i}: {p}" for i, p in ((i, registro(x)) for i, x in enumerate(conteudo))
                                 if p), None)
            if problema:
                return fim("incompleta", f"página {pagina}: contrato da API ({contrato.VERSAO}) não atendido: {problema}")
            if pagina == 0:
                total, paginas = d.get("totalElements"), d.get("totalPages")
                if not _inteiro(total) or total < 0:      # without a total, the ceiling by sum does not apply (audit COL-03)
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
            if repetidas:           # the whole page was checked: the note classifies all of its repetitions
                return fim("incompleta", _descrever_repetidas(repetidas))
            vistos |= novos
            soma += len(conteudo)
            if soma > total:
                return fim("incompleta", f"soma das paginas {soma} passou de totalElements {total}")
            if d.get("last") or not conteudo:
                break
            pagina += 1
            if paginas is not None and pagina >= paginas:     # pages start at 0 (audit COL-04)
                return fim("incompleta", f"a página {pagina - 1} não é a última (last=false), mas totalPages={paginas}")
            if pagina >= MAX_PAGINAS:
                return fim("incompleta", f"paginacao passou do teto de {MAX_PAGINAS} paginas")
        if soma != total:
            return fim("incompleta", f"soma das páginas {soma} ≠ totalElements {total}")
        if len(respostas) == 1:      # one response is an atomic picture of the base: nothing to check
            return respostas, "completa", obs, None
        return self._segunda_leitura(endpoint, params, respostas, obs)

    def _segunda_leitura(self, endpoint, params, respostas, obs):
        """Reads every page again; the snapshot is only 'completa' if all of them come back with the same content and
        the same total. Detects the compensated shift (deletion before the point + insertion after) that sum, total
        and order cannot see."""
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

    # ----------------------------------------------------------------- types
    def listagem(self, entidade, exercicio, data_final):
        """Snapshot of an entity's RP listing at a cut-off (01/01 -> data_final)."""
        df = date.fromisoformat(data_final)
        if df.year != exercicio:
            raise ParametroInvalido(f"dataFinal {data_final} fora do exercício {exercicio}: combinação proibida (Etapa 02 §8)")
        params = {"entidade": int(entidade), "exercicio": int(exercicio), "dataInicial": f"{exercicio}-01-01",
                  "dataFinal": data_final, "size": TAMANHO_PAGINA, "sort": list(contrato.ORDEM_RP)}
        inicio = agora()
        respostas, status, obs, segunda = self._paginado(EP_RP, params, chave_rp, contrato.contrato_registro_rp)
        obs = self._fora_do_catalogo(int(entidade), int(exercicio)) + obs
        return self._snapshot("rp_listagem", EP_RP, params, respostas, status, inicio, obs, segunda)

    def _fora_do_catalogo(self, entidade, exercicio):
        """Note when the entity (or its fiscal year) is not in the current catalog already collected: the API returns
        200 with 0 records for a non-existent entity or year, which would read as 'no RP' (audit COL-05). It only
        informs; collection is not refused (an extinct entity may be missing from the current catalog)."""
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
        """New collection of an ALREADY collected cut-off, with EXACTLY the parameters of snapshot `ref` (uid or id).
        The previous snapshot is not touched: the re-collection is another snapshot, which records where it came from."""
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
        respostas, status, obs, segunda = self._paginado(EP_RP, params, chave_rp, contrato.contrato_registro_rp)
        return self._snapshot("rp_listagem", EP_RP, params, respostas, status, inicio, [f"recoleta de {uid}"] + obs,
                              segunda)

    def movimentacao(self, entidade, anoempenho, empenho):
        params = {"entidade": int(entidade), "exercicio": int(anoempenho), "empenho": int(empenho), "size": 500}
        inicio = agora()
        respostas, status, obs, segunda = self._paginado(EP_MOV, params, registro=contrato.contrato_registro_mov)
        meta = {"entidade": int(entidade), "anoempenho": int(anoempenho), "empenho": int(empenho), "size": 500}
        return self._snapshot("movimentacao", EP_MOV, meta, respostas, status, inicio, obs, segunda)

    def _simples(self, tipo, endpoint, params, meta, validar):
        """One request. `validar(resposta)` returns the content problem (text) or None: only HTTP 200 with content within
        the contract is 'completa'."""
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
        """Catalog of entities and, per entity, of fiscal years. Valid JSON is not enough: each one must meet the minimum
        contract (contrato.py), otherwise the snapshot is 'falhou' with the reason (review, item 6)."""
        feitos = []
        s, _ = self._simples("entidades", EP_ENT, None, {}, lambda r: contrato.contrato_entidades(_json(r.corpo)))
        feitos.append(s)
        for e in entidades:
            s, _ = self._simples("exercicios", f"{EP_EXE}/{int(e)}", None, {"entidade": int(e)},
                                 lambda r, e=int(e): contrato.contrato_exercicios(_json(r.corpo), e))
            feitos.append(s)
        return feitos

    def rreo(self, exercicio, entidade=None, ids=None, baixar_pdfs=True, bimestres=None):
        """List of LRF publications (group 1) and RREO Annex VII PDFs not yet collected.
        `bimestres` (e.g. {6}): only the PDFs of those two-month periods (labels such as "6o Bimestre", "6o BIMESTRE"
        and "6o Bimestre - Consolidado"; on the portal the "o" is the ordinal indicator).
        A file whose idArquivo is not a positive integer is ignored and logged: no text coming from the response
        goes into the URL."""
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
                continue  # the label varies across years: "6o Bimestre", "6o BIMESTRE", "4 o Bimestre"
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
    """Files of the 'Anexo VII - Demonstrativo dos Restos a Pagar...' subgroup in the publications list."""
    for grupo in publicacoes if isinstance(publicacoes, list) else []:
        if not isinstance(grupo, dict):
            continue
        for sub in grupo.get("list") or []:
            if not isinstance(sub, dict):
                continue
            nome = (sub.get("subGrupoRelatorio") or {}).get("valor", "")
            if "Restos a Pagar" in str(nome) and "Anexo VII" in str(nome):
                yield from sub.get("list") or []
