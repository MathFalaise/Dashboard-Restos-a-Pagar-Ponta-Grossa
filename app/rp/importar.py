"""Importacao dos dados brutos baixados nas Etapas 01 e 02 como snapshots historicos.

* Nenhum byte e alterado: cada arquivo vira um objeto do armazem com o mesmo SHA-256.
* O horario de cada snapshot vem da melhor fonte disponivel, identificada em
  `origem_carimbo`: o manifesto da Etapa 02 (preciso), o cabecalho Date do
  servidor (preciso) ou a data de modificacao do arquivo (APROXIMADO).
* O `snapshot_uid` e derivado do arquivo de origem (uuid5): importar de novo
  nao duplica nada, e duas importacoes independentes geram os mesmos snapshots.

Etapa 04.2: usado so em armazens TEMPORARIOS (testes e reconciliacao).
A importacao para o armazem real e da subetapa 04.3.
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


def _uid(chave):
    return uuid.uuid5(ESPACO, chave).hex


def _iso(s):
    return datetime.fromisoformat(s).replace(tzinfo=BRT).isoformat(timespec="seconds")


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
    uid = _uid(chave)
    if con.execute("SELECT 1 FROM coleta WHERE snapshot_uid=?", (uid,)).fetchone():
        return 0
    gravar_snapshot(con, armazem, snapshot_uid=uid, **kw)
    return 1


def importar_etapas_anteriores(con, armazem, raiz_projeto):
    raiz = Path(raiz_projeto)
    e2 = raiz / "etapa02" / "dados_brutos"
    novos = {}

    # 1) listagens da Etapa 02 (MANIFESTO.jsonl agrupado por consulta)
    col = _coletor("etapa02-investigacao/coletar.py", raiz / "etapa02/investigacao/coletar.py", "investigação da Etapa 02")
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
                     origem_carimbo="manifesto", status=status_de_paginas([r["corpo"] for r in resp]),
                     coletor=col, respostas=resp)
    novos["rp_listagem"] = n

    # 2) recoleta do mesmo corte (Etapa 02 secao 3.6): outro snapshot, horario aproximado
    col = _coletor("etapa02-recoleta-inline", None, "recoleta por script inline na Etapa 02")
    arqs = sorted((e2 / "api" / "recoleta").glob("*_p*_recoleta.json"))
    p = {"entidade": 1, "exercicio": 2026, "dataInicial": "2026-01-01", "dataFinal": "2026-08-31", "size": 2000}
    resp = [{"url": f"{API}/empenhos/restos-a-pagar?{urlencode({**p, 'page': int(re.search(r'_p(\d+)_', a.name).group(1))})}",
             "recebida_em": _mtime(a), "corpo": a.read_bytes()} for a in arqs]
    novos["rp_listagem (recoleta)"] = _gravar(
        con, armazem, "etapa02/api/recoleta", tipo="rp_listagem", endpoint="/empenhos/restos-a-pagar", parametros=p,
        coletada_em=_mtime(arqs[0]), origem_carimbo="mtime_arquivo", status=status_de_paginas([r["corpo"] for r in resp]),
        coletor=col, respostas=resp, observacao="recoleta do mesmo corte ~13 min depois; horário aproximado (mtime)")

    # 3) movimentacoes
    col = _coletor("etapa02-investigacao/casos.py", raiz / "etapa02/investigacao/casos.py")
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

    # 4) publicacoes e PDFs do RREO
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

    # 5) catalogos da Etapa 01
    col = _coletor("etapa01-curl-manual", None, "downloads com curl durante a Etapa 01")
    e1 = raiz / "etapa01" / "amostras_brutas"
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
