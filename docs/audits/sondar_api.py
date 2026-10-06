# CONTROLLED probe of the API (audit): few requests, 2 s pause, GET only, no redirects.
# Records only metadata (status, headers, page fields, keys, content hash) - no creditor name.
import hashlib
import json
import sys
import time

import requests

BASE = "https://servicos.pontagrossa.pr.gov.br/portaltransparencia-api"
UA = "RestosAPagarPG-coletor (pesquisa sobre dados publicos de Restos a Pagar)"
S = requests.Session()
S.headers["User-Agent"] = UA
SAIDA = []
ULTIMA = [0.0]


def chave(r):
    return (r.get("entidade"), r.get("anoempenho"), r.get("empenho"))


def get(rotulo, caminho, params=None, guardar=None):
    falta = 2.0 - (time.monotonic() - ULTIMA[0])
    if falta > 0:
        time.sleep(falta)
    t = time.monotonic()
    try:
        r = S.get(BASE + caminho, params=params, timeout=60, allow_redirects=False)
    except requests.RequestException as e:
        ULTIMA[0] = time.monotonic()
        SAIDA.append({"rotulo": rotulo, "params": params, "erro": f"{type(e).__name__}: {e}"})
        return None
    ULTIMA[0] = time.monotonic()
    item = {"rotulo": rotulo, "caminho": caminho, "params": params, "status": r.status_code,
            "segundos": round(time.monotonic() - t, 2), "bytes": len(r.content),
            "cabecalhos": {k: v for k, v in r.headers.items() if k.lower() in (
                "content-type", "content-length", "content-encoding", "transfer-encoding", "etag", "last-modified",
                "cache-control", "date", "server", "location", "retry-after", "x-ratelimit-limit", "x-ratelimit-remaining")}}
    try:
        d = r.json()
    except ValueError:
        item["corpo_inicio"] = r.content[:200].decode("utf-8", "replace")
        SAIDA.append(item)
        return None
    if isinstance(d, dict) and "content" in d:
        item["pagina"] = {k: v for k, v in d.items() if k != "content"}
        item["len_content"] = len(d["content"])
        item["chaves_registro"] = sorted({k for x in d["content"] for k in x}) if d["content"] else []
        item["sha_content"] = hashlib.sha256(json.dumps(d["content"], sort_keys=True).encode()).hexdigest()[:16]
        item["primeiras_chaves"] = [chave(x) for x in d["content"][:3]]
        item["ultimas_chaves"] = [chave(x) for x in d["content"][-3:]]
    elif isinstance(d, dict):
        item["json_objeto"] = {k: (v if not isinstance(v, (list, dict)) else type(v).__name__) for k, v in d.items()}
    elif isinstance(d, list):
        item["json_lista"] = len(d)
        item["chaves_item"] = sorted({k for x in d if isinstance(x, dict) for k in x})[:30]
    SAIDA.append(item)
    if guardar is not None:
        guardar.append(d)
    return d


RP = "/empenhos/restos-a-pagar"
c5 = {"entidade": 5, "exercicio": 2026, "dataInicial": "2026-01-01", "dataFinal": "2026-08-31"}
# 1) full cut-off of entity 5 at once and again (stability between consecutive queries)
inteiro = []
get("ent5 size=2000 p0 (1a)", RP, {**c5, "size": 2000, "page": 0}, inteiro)
get("ent5 size=2000 p0 (2a)", RP, {**c5, "size": 2000, "page": 0}, inteiro)
# 2) same cut-off in pages of 100 (order and stability across pages)
paginas = []
for p in range(5):
    get(f"ent5 size=100 p{p}", RP, {**c5, "size": 100, "page": p}, paginas)
get("ent5 size=100 p0 repetida", RP, {**c5, "size": 100, "page": 0}, paginas)
# 3) pagination out of range and limit parameters
get("ent5 size=100 p99 (fora)", RP, {**c5, "size": 100, "page": 99})
get("ent5 size=100 page=-1", RP, {**c5, "size": 100, "page": -1})
get("ent5 size=0", RP, {**c5, "size": 0, "page": 0})
get("ent5 sem size/page", RP, c5)
# 4) size above 2000: does the server honor, cap or ignore it?
grande = []
get("ent1 size=5000 p0", RP, {"entidade": 1, "exercicio": 2026, "dataInicial": "2026-01-01", "dataFinal": "2026-08-31",
                              "size": 5000, "page": 0}, grande)
# 5) ordering: does Spring accept sort? (discovery; does not go into the collector without proof)
srt = []
get("ent5 size=100 p0 sort=empenho,asc", RP, {**c5, "size": 100, "page": 0, "sort": "empenho,asc"}, srt)
# 6) invalid parameters
get("exercicio invalido 1900", RP, {"entidade": 5, "exercicio": 1900, "dataInicial": "1900-01-01", "dataFinal": "1900-12-31", "size": 10, "page": 0})
get("entidade inexistente 99999", RP, {**c5, "entidade": 99999, "size": 10, "page": 0})
get("data invalida 2026-13-45", RP, {**c5, "dataFinal": "2026-13-45", "size": 10, "page": 0})
get("sem dataFinal", RP, {"entidade": 5, "exercicio": 2026, "dataInicial": "2026-01-01", "size": 10, "page": 0})
get("parametro desconhecido foo=bar", RP, {**c5, "size": 10, "page": 0, "foo": "bar"})
get("dataFinal em outro ano", RP, {**c5, "dataFinal": "2027-02-28", "size": 10, "page": 0})
# 7) other endpoints used by the project
get("entidades/lista", "/api/entidades/lista")
get("exercicios/entidade/5", "/api/exercicios/entidade/5")
get("publicacoes/1 ent1 2026", "/api/publicacoes/1", {"entidade": 1, "exercicio": 2026})
get("movimentacao ent1 2025 emp5659", "/empenhos/detalhe/movimentacao", {"entidade": 1, "exercicio": 2025, "empenho": 5659, "size": 500})
get("caminho inexistente", "/empenhos/nao-existe")

# local analyses (no network)
an = {}
if len(inteiro) == 2:
    a, b = inteiro
    an["consultas_consecutivas_identicas_bytes_content"] = a["content"] == b["content"]
    an["consultas_consecutivas_mesma_ordem_de_chaves"] = [chave(x) for x in a["content"]] == [chave(x) for x in b["content"]]
if len(paginas) >= 5 and inteiro:
    juntas = [x for d in paginas[:5] for x in d["content"]]
    ks = [chave(x) for x in juntas]
    an["paginas100_total_registros"] = len(juntas)
    an["paginas100_chaves_distintas"] = len(set(ks))
    an["paginas100_mesmo_conjunto_que_size2000"] = sorted(map(str, ks)) == sorted(str(chave(x)) for x in inteiro[0]["content"])
    an["paginas100_mesma_ordem_que_size2000"] = ks == [chave(x) for x in inteiro[0]["content"]]
    an["paginas100_registros_identicos_ao_size2000"] = (sorted(json.dumps(x, sort_keys=True) for x in juntas)
                                                        == sorted(json.dumps(x, sort_keys=True) for x in inteiro[0]["content"]))
    an["pagina0_repetida_identica"] = paginas[0]["content"] == paginas[5]["content"] if len(paginas) > 5 else None
    ordem = [x["empenho"] for x in inteiro[0]["content"]]
    an["ordem_crescente_por_empenho"] = ordem == sorted(ordem)
    an["ordem_por_anoempenho_empenho"] = [chave(x)[1:] for x in inteiro[0]["content"]] == sorted(chave(x)[1:] for x in inteiro[0]["content"])
    an["chave_entidade_ano_empenho_unica_no_corte"] = len({chave(x) for x in inteiro[0]["content"]}) == len(inteiro[0]["content"])
if grande:
    g = grande[0]
    an["size5000_len_content"] = len(g["content"])
    an["size5000_size_ecoado"] = g.get("size")
    an["size5000_totalPages"] = g.get("totalPages")
if srt:
    ordem = [x["empenho"] for x in srt[0]["content"]]
    an["sort_param_ordena_por_empenho"] = ordem == sorted(ordem)
    an["sort_ecoado"] = srt[0].get("sort")
json.dump({"requisicoes": SAIDA, "analises": an}, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(an, ensure_ascii=False, indent=1))
for s in SAIDA:
    print(s["rotulo"], "|", s.get("status"), s.get("erro", ""), "|", s.get("len_content", s.get("json_lista", "")),
          "|", {k: s.get("pagina", {}).get(k) for k in ("totalElements", "totalPages", "number", "size", "numberOfElements", "last", "first", "empty")} if "pagina" in s else s.get("json_objeto", s.get("corpo_inicio", ""))[:200] if not isinstance(s.get("json_objeto"), dict) else s.get("json_objeto"))
