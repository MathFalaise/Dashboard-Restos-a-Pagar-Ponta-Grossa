"""Import of the raw data downloaded in stages 01 and 02 as historical snapshots.

* No byte is changed: each file becomes a store object with the same SHA-256.
* The time of each snapshot comes from the best available source, identified in `origem_carimbo`: the stage 02
  manifest (precise), the server's Date header (precise) or the file's modification date (APPROXIMATE).
* `snapshot_uid` is derived from the source file (uuid5): importing again duplicates nothing, and two independent
  imports produce the same snapshots.
* The same `snapshot_uid` with other content (bytes or parameters) is a CONFLICT, never "it already exists, so skip
  it": the source file changed after the first import (critical review, item 20).
* A timestamp with an offset is CONVERTED to Brasilia; only a timestamp without an offset gets the Brasilia offset
  (item 21). The 66 timestamps of the stage 02 MANIFESTO.jsonl have no offset: no imported snapshot changes.

Stage 04.2: used only in TEMPORARY stores (tests and reconciliation).
The import into the real store is from sub-stage 04.3.
"""
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

from . import BRT, sha256
from .snapshots import gravar_snapshot, status_de_paginas

API = "https://servicos.pontagrossa.pr.gov.br/portaltransparencia-api"
ESPACO = uuid.UUID("7b1f0d3e-5a52-4c7e-9e0a-2c1f2b6d9a01")


class ConflitoDeImportacao(ValueError):
    """The snapshot derived from this file already exists with other content: the source file changed."""


def _uid(chave):
    return uuid.uuid5(ESPACO, chave).hex


def _iso(s):
    """ISO timestamp -> ISO in Brasilia. Without an offset: it is Brasilia time (the offset is added). With an offset:
    the SAME instant is converted - swapping the offset without converting would change the instant (10:00 UTC is
    not 10:00 BRT)."""
    d = datetime.fromisoformat(s)
    d = d.replace(tzinfo=BRT) if d.tzinfo is None else d.astimezone(BRT)
    return d.isoformat(timespec="seconds")


def _mtime(p):
    return datetime.fromtimestamp(Path(p).stat().st_mtime, BRT).isoformat(timespec="seconds")


def _coletor(nome, arquivo=None, descricao=None):
    h = sha256(Path(arquivo).read_bytes()) if arquivo and Path(arquivo).exists() else None
    return {"nome": nome, "versao": "1", "sha256_codigo": h, "descricao": descricao}


def _params_rp(url):
    q = dict(parse_qsl(urlsplit(url).query))
    p = {"entidade": int(q["entidade"]), "exercicio": int(q["exercicio"]), "dataInicial": q["dataInicial"],
         "dataFinal": q["dataFinal"], "size": int(q.get("size", 20))}
    if "tipoPesquisa" in q:
        p["tipoPesquisa"] = q["tipoPesquisa"]
    return p


def _gravar(con, armazem, chave, **kw):
    """Writes the snapshot derived from `chave` (source path), or nothing if it already exists WITH THE SAME CONTENT.
    Same uid with other bytes or other parameters -> ConflitoDeImportacao: nothing is written nor silently ignored."""
    uid = _uid(chave)
    ja = con.execute("SELECT id, parametros_json FROM coleta WHERE snapshot_uid=?", (uid,)).fetchone()
    if ja:
        gravadas = [tuple(r) for r in con.execute("SELECT ordem, sha256 FROM resposta_bruta WHERE coleta_id=? "
                                                  "ORDER BY ordem", (ja[0],))]
        novas = [(ordem, sha256(r["corpo"])) for ordem, r in enumerate(kw["respostas"])]
        parametros = json.dumps(kw["parametros"], sort_keys=True, ensure_ascii=False)
        if gravadas != novas or ja[1] != parametros:
            raise ConflitoDeImportacao(
                f"{chave}: o snapshot {uid[:8]} já existe com outro conteúdo "
                f"({'bytes' if gravadas != novas else 'parâmetros'} diferentes). O arquivo de origem mudou depois da "
                "primeira importação; nada foi gravado")
        return 0
    gravar_snapshot(con, armazem, snapshot_uid=uid, **kw)
    return 1


def importar_etapas_anteriores(con, armazem, raiz_projeto):
    raiz = Path(raiz_projeto)
    e2 = raiz / "data" / "stage02-raw"
    novos = {}

    # 1) stage 02 listings (MANIFESTO.jsonl grouped by query)
    col = _coletor("etapa02-investigacao/coletar.py", raiz / "docs/stages/02-accounting-validation/investigation/coletar.py", "investigação da Etapa 02")
    grupos = {}
    for linha in (e2 / "api" / "MANIFESTO.jsonl").read_text(encoding="utf-8").splitlines():
        m = json.loads(linha)
        grupos.setdefault(re.sub(r"_p\d+\.json$", "", m["arquivo"]), []).append(m)
    n = 0
    for base, ms in sorted(grupos.items()):
        ms.sort(key=lambda m: int(re.search(r"_p(\d+)\.json$", m["arquivo"]).group(1)))
        resp = []
        for m in ms:
            corpo = (e2 / "api" / m["arquivo"]).read_bytes()
            if sha256(corpo) != m["sha256"]:
                raise ValueError(f"hash não confere com o MANIFESTO da Etapa 02: {m['arquivo']}")
            resp.append({"url": m["url"], "http_status": m["status"], "recebida_em": _iso(m["coletado_em"]), "corpo": corpo})
        n += _gravar(con, armazem, f"etapa02/api/{base}", tipo="rp_listagem", endpoint="/empenhos/restos-a-pagar",
                     parametros=_params_rp(ms[0]["url"]), coletada_em=_iso(ms[0]["coletado_em"]),
                     origem_carimbo="manifesto",
                     status=status_de_paginas([r["corpo"] for r in resp], chave_unica=True),
                     coletor=col, respostas=resp)
    novos["rp_listagem"] = n

    # 2) re-collection of the same cut-off (stage 02 section 3.6): another snapshot, approximate time
    col = _coletor("etapa02-recoleta-inline", None, "recoleta por script inline na Etapa 02")
    arqs = sorted((e2 / "api" / "recoleta").glob("*_p*_recoleta.json"))
    p = {"entidade": 1, "exercicio": 2026, "dataInicial": "2026-01-01", "dataFinal": "2026-08-31", "size": 2000}
    pagina = lambda a: int(re.search(r"_p(\d+)_", a.name).group(1))   # outside the f-string: backslash inside {}
    resp = [{"url": f"{API}/empenhos/restos-a-pagar?{urlencode({**p, 'page': pagina(a)})}",   # only valid from Python 3.12
             "recebida_em": _mtime(a), "corpo": a.read_bytes()} for a in arqs]
    novos["rp_listagem (recoleta)"] = _gravar(
        con, armazem, "etapa02/api/recoleta", tipo="rp_listagem", endpoint="/empenhos/restos-a-pagar", parametros=p,
        coletada_em=_mtime(arqs[0]), origem_carimbo="mtime_arquivo",
        status=status_de_paginas([r["corpo"] for r in resp], chave_unica=True),
        coletor=col, respostas=resp, observacao="recoleta do mesmo corte ~13 min depois; horário aproximado (mtime)")

    # 3) movements
    col = _coletor("etapa02-investigacao/casos.py", raiz / "docs/stages/02-accounting-validation/investigation/casos.py")
    n = 0
    for a in sorted((e2 / "movimentacao").glob("mov_ent*_ex*_emp*.json")):
        e, ano, emp = map(int, re.match(r"mov_ent(\d+)_ex(\d+)_emp(\d+)\.json", a.name).groups())
        corpo = a.read_bytes()
        q = {"entidade": e, "exercicio": ano, "empenho": emp, "size": 500}
        n += _gravar(con, armazem, f"etapa02/movimentacao/{a.name}", tipo="movimentacao",
                     endpoint="/empenhos/detalhe/movimentacao",
                     parametros={"entidade": e, "anoempenho": ano, "empenho": emp, "size": 500},
                     coletada_em=_mtime(a), origem_carimbo="mtime_arquivo", status=status_de_paginas([corpo]),
                     coletor=col, respostas=[{"url": f"{API}/empenhos/detalhe/movimentacao?{urlencode(q)}",
                                              "recebida_em": _mtime(a), "corpo": corpo}])
    novos["movimentacao"] = n

    # 4) RREO publications and PDFs
    col = _coletor("etapa02-curl-manual", None, "downloads com curl durante a Etapa 02")
    pubs, n = {}, 0
    for a in sorted((e2 / "rreo").glob("api_publicacoes_1_ent1_ex*.json")):
        ano = int(re.search(r"_ex(\d+)", a.name).group(1))
        corpo = a.read_bytes()
        q = {"entidade": 1, "exercicio": ano}
        n += _gravar(con, armazem, f"etapa02/rreo/{a.name}", tipo="publicacoes", endpoint="/api/publicacoes/1",
                     parametros=q, coletada_em=_mtime(a), origem_carimbo="mtime_arquivo", status="completa",
                     coletor=col, respostas=[{"url": f"{API}/api/publicacoes/1?{urlencode(q)}", "recebida_em": _mtime(a),
                                              "corpo": corpo}])
        for g in json.loads(corpo):
            for sg in g.get("list", []):
                if "Restos" in (sg.get("subGrupoRelatorio") or {}).get("valor", ""):
                    for arq in sg.get("list", []):
                        pubs[arq["nomeArquivo"]] = dict(arq, exercicio=ano)
    novos["publicacoes"] = n
    n = 0
    for pdf in sorted((e2 / "rreo").glob("*.pdf")):
        hdr = pdf.with_suffix(".hdr").read_text(encoding="latin-1")
        nome = re.search(r'filename="([^"]+)"', hdr).group(1)
        quando = (datetime.strptime(re.search(r"^Date: (.+)$", hdr, re.M).group(1).strip(), "%a, %d %b %Y %H:%M:%S GMT")
                  .replace(tzinfo=timezone.utc).astimezone(BRT).isoformat(timespec="seconds"))
        arq = pubs[nome]
        meta = {"id_arquivo": arq["idArquivo"], "exercicio": arq["exercicio"], "entidade": 1, "rotulo": arq["valor"],
                "nomeArquivo": nome, "dataArquivo": arq.get("dataArquivo")}
        n += _gravar(con, armazem, f"etapa02/rreo/{pdf.name}", tipo="rreo_pdf", endpoint=f"/api/files/arquivo/{arq['idArquivo']}",
                     parametros=meta, coletada_em=quando, origem_carimbo="cabecalho_http", status="completa", coletor=col,
                     respostas=[{"url": f"{API}/api/files/arquivo/{arq['idArquivo']}", "http_status": 200,
                                 "cabecalhos": dict(re.findall(r"^([A-Za-z-]+): (.*?)\r?$", hdr, re.M)),
                                 "recebida_em": quando, "corpo": pdf.read_bytes()}])
    novos["rreo_pdf"] = n

    # 5) stage 01 catalogs
    col = _coletor("etapa01-curl-manual", None, "downloads com curl durante a Etapa 01")
    e1 = raiz / "data" / "stage01-samples"
    n = 0
    for tipo, arq, endpoint, q in (("entidades", "api_entidades_lista.json", "/api/entidades/lista", {}),
                                   ("exercicios", "api_exercicios_entidade_1.json", "/api/exercicios/entidade/1", {"entidade": 1})):
        a = e1 / arq
        n += _gravar(con, armazem, f"etapa01/{arq}", tipo=tipo, endpoint=endpoint, parametros=q, coletada_em=_mtime(a),
                     origem_carimbo="mtime_arquivo", status="completa", coletor=col,
                     respostas=[{"url": API + endpoint, "recebida_em": _mtime(a), "corpo": a.read_bytes()}],
                     observacao="horário aproximado: mtime da cópia do arquivo")
    novos["catalogos"] = n
    return novos
