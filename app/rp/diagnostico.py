"""Diagnosis of the Elotech API contract (critical review, item 49): queries the portal and records NOTHING.

To be used before a collection, or when a collection ends 'incompleta' for no clear reason: it says whether the API
still answers the way the collector expects. No snapshot is created: the database is opened read-only (it only
serves as a reference) and the store is not even opened.

It checks, with the same code as the collector (contrato.py and coletor.conferir_pagina):
  * the entity catalog and the entity's fiscal year catalog: minimum contract;
  * the first, small page of a cut-off's RP listing: HTTP 200, Spring page, integer totalElements, page contract,
    echo of the requested order (here the echo is REQUIRED: without it the order cannot be checked), records of
    the requested entity, an order (anoempenho, empenho) that does not decrease and a business key without
    repetition;
  * the STRUCTURE of each response against the most recent complete snapshot of the same type
    (contrato.comparar_amostra): a new field, a new type, or a field that was in every recorded record and is missing.

Result: 'ok' (nothing changed), 'mudou' (different contract or structure: review before collecting) or
'indisponivel' (network, HTTP 429 or 5xx: that point was not checked). With 'mudou' and 'indisponivel' together,
'mudou' wins. The portal version (/actuator/info; stage 01: Oxy Transparencia 3.128.0) goes in the report for
information only.
"""
from datetime import date

from . import agora, banco, contrato
from .coletor import EP_ENT, EP_EXE, EP_RP, TAMANHO_PAGINA, ParametroInvalido, _json, chave_rp, conferir_pagina
from .http import ErroDeRede

TAMANHO_AMOSTRA = 20
EP_INFO = "/actuator/info"
CODIGO_DE_SAIDA = {"ok": 0, "mudou": 1, "indisponivel": 2}


def _inteiro(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _referencia(con, tipo, entidade=None):
    """(snapshot_uid, bodies) of the most recent complete snapshot of the type - the entity's, if any -, or (None, [])."""
    if con is None:
        return None, []
    extra = " AND tipo_pesquisa IS NULL" if tipo == "rp_listagem" else ""
    for filtro, p in ([(" AND entidade=?", (entidade,))] if entidade is not None else []) + [("", ())]:
        row = con.execute(f"SELECT id, snapshot_uid FROM coleta WHERE tipo=? AND status='completa'{extra}{filtro} "
                          "ORDER BY coletada_em DESC, snapshot_uid DESC LIMIT 1", (tipo, *p)).fetchone()
        if row:
            shas = [s for (s,) in con.execute("SELECT sha256 FROM resposta_bruta WHERE coleta_id=? ORDER BY ordem",
                                              (row[0],))]
            return row[1], [banco.corpo(con, s) for s in shas]
    return None, []


def _verificar(con, cliente, alvo, tipo, caminho, params, entidade_ref, conferir):
    """One query: situation, contract problems (`conferir(dados)` -> (problems, warnings)) and structure against the
    reference snapshot. Network, HTTP 429 or 5xx: 'indisponivel'. Any other HTTP other than 200: 'mudou'."""
    saida = {"alvo": alvo, "url": cliente.url(caminho, params), "http_status": None, "situacao": "ok",
             "problemas": [], "avisos": [], "estrutura": None}
    try:
        r = cliente.get(caminho, params)
    except ErroDeRede as e:
        return {**saida, "situacao": "indisponivel", "problemas": [str(e)]}
    saida["http_status"] = r.status
    if r.status == 429 or r.status >= 500:
        return {**saida, "situacao": "indisponivel", "problemas": [f"HTTP {r.status}"]}
    if r.status != 200:
        return {**saida, "situacao": "mudou", "problemas": [f"HTTP {r.status}: a consulta do coletor não é aceita"]}
    problemas, avisos = conferir(_json(r.corpo))
    uid, corpos = _referencia(con, tipo, entidade_ref)
    if uid is None:
        avisos.append(f"nenhum snapshot completo do tipo {tipo} no banco: estrutura não comparada")
    else:
        saida["estrutura"] = {"referencia": uid, **contrato.comparar_amostra(corpos, [r.corpo])}
        if not saida["estrutura"]["igual"]:
            problemas.append(f"estrutura da resposta diferente da do snapshot {uid[:8]} (ver 'estrutura')")
    return {**saida, "situacao": "mudou" if problemas else "ok", "problemas": problemas, "avisos": avisos}


def _versao_do_portal(cliente):
    """Portal version and build at /actuator/info, or None. Informative only: it is not a collector endpoint and may be
    switched off without affecting collection."""
    try:
        r = cliente.get(EP_INFO)
    except ErroDeRede as e:
        return {"url": cliente.url(EP_INFO), "http_status": None, "versao": None, "build": None, "erro": str(e)}
    d = _json(r.corpo) if r.status == 200 else None
    build = d.get("build") if isinstance(d, dict) and isinstance(d.get("build"), dict) else {}
    return {"url": r.url, "http_status": r.status, "versao": build.get("version"), "build": build.get("time")}


def _conferir_entidades(entidade):
    def conferir(d):
        problema = contrato.contrato_entidades(d)
        if problema:
            return [problema], []
        return [], ([] if any(x.get("id") == entidade for x in d) else
                    [f"entidade {entidade} fora do catálogo de entidades"])
    return conferir


def _conferir_exercicios(entidade, exercicio):
    def conferir(d):
        problema = contrato.contrato_exercicios(d, entidade)
        if problema:
            return [problema], []
        return [], ([] if any(x["id"]["exercicio"] == exercicio for x in d) else
                    [f"exercício {exercicio} fora do catálogo de exercícios da entidade {entidade}"])
    return conferir


def _conferir_listagem(entidade, tamanho):
    def conferir(d):
        if not isinstance(d, dict) or not isinstance(d.get("content"), list):
            return ["a resposta não é uma página JSON com 'content' em lista"], []
        conteudo, total, paginas = d["content"], d.get("totalElements"), d.get("totalPages")
        problemas = []
        if not _inteiro(total) or total < 0:
            problemas.append(f"totalElements ausente ou não inteiro: {total!r}")
        if paginas is not None and (not _inteiro(paginas) or paginas < 0):
            problemas.append(f"totalPages não inteiro: {paginas!r}")
        problema = conferir_pagina(d, 0, tamanho, total, paginas, conteudo, contrato.ORDEM_RP)
        if problema:
            problemas.append(problema)
        # only page 0 is read: what the collector checks at the end (sum = total) is checked here by the page itself
        if d.get("last") is True and _inteiro(total) and total != len(conteudo):
            problemas.append(f"a página 0 é a última (last=true), mas totalElements={total} e content tem "
                             f"{len(conteudo)}")
        if d.get("last") is False and len(conteudo) != d.get("size", tamanho):
            problemas.append(f"a página 0 não é a última (last=false), mas veio com {len(conteudo)} de "
                             f"{d.get('size', tamanho)} registros")
        if "sort" not in d:
            problemas.append("a página não ecoa 'sort': a ordem pedida não pode ser conferida")
        if not all(isinstance(x, dict) for x in conteudo):
            return problemas + ["content tem item que não é objeto"], []
        outras = sorted({repr(x.get("entidade")) for x in conteudo if x.get("entidade") != entidade})
        if outras:
            problemas.append(f"registro(s) da entidade {', '.join(outras)} na listagem da entidade {entidade}")
        try:
            chaves = [chave_rp(x) for x in conteudo]
            if chaves != sorted(chaves):
                problemas.append("a ordem (anoempenho, empenho) não cresce dentro da página")
        except (KeyError, TypeError):
            problemas.append("registro sem anoempenho/empenho comparáveis")
        negocio = [contrato.chave_negocio(x) for x in conteudo]
        if len(negocio) != len(set(negocio)):
            problemas.append("chave de negócio (entidade, anoempenho, empenho) repetida na amostra")
        return problemas, ([] if conteudo else ["amostra sem registros: só o topo da página foi comparado"])
    return conferir


def diagnosticar(con, cliente, entidade, exercicio, data_final, tamanho=TAMANHO_AMOSTRA):
    """Diagnosis report. `con`: database opened READ-ONLY (structure reference) or None.
    Nothing is recorded: no snapshot, no database row, no file in the store."""
    try:
        ano = date.fromisoformat(data_final).year
    except (TypeError, ValueError) as e:
        raise ParametroInvalido(f"data final inválida: {data_final!r} (use AAAA-MM-DD)") from e
    if ano != exercicio:
        raise ParametroInvalido(f"dataFinal {data_final} fora do exercício {exercicio}: combinação proibida "
                                "(Etapa 02 §8)")
    if not _inteiro(tamanho) or not 1 <= tamanho <= TAMANHO_PAGINA:
        raise ParametroInvalido(f"tamanho da amostra precisa ser inteiro entre 1 e {TAMANHO_PAGINA}")
    entidade, exercicio = int(entidade), int(exercicio)
    params = {"entidade": entidade, "exercicio": exercicio, "dataInicial": f"{exercicio}-01-01",
              "dataFinal": data_final, "size": tamanho, "sort": list(contrato.ORDEM_RP), "page": 0}
    verificacoes = [
        _verificar(con, cliente, "entidades", "entidades", EP_ENT, None, None, _conferir_entidades(entidade)),
        _verificar(con, cliente, f"exercicios/{entidade}", "exercicios", f"{EP_EXE}/{entidade}", None, entidade,
                   _conferir_exercicios(entidade, exercicio)),
        _verificar(con, cliente, "rp_listagem", "rp_listagem", EP_RP, params, entidade,
                   _conferir_listagem(entidade, tamanho)),
    ]
    portal = _versao_do_portal(cliente)
    situacoes = {v["situacao"] for v in verificacoes}
    resultado = "mudou" if "mudou" in situacoes else "indisponivel" if "indisponivel" in situacoes else "ok"
    return {"resultado": resultado, "contrato": contrato.VERSAO, "consultado_em": agora(),
            "corte": {"entidade": entidade, "exercicio": exercicio, "data_final": data_final,
                      "tamanho_amostra": tamanho},
            "portal": portal, "verificacoes": verificacoes, "requisicoes": cliente.requisicoes,
            "nota": ("Nada foi gravado: nenhum snapshot, nenhuma linha no banco, nenhum arquivo no armazém. 'mudou' "
                     "pede revisão antes de coletar; a estrutura é comparada com o snapshot completo mais recente "
                     "do mesmo tipo.")}
