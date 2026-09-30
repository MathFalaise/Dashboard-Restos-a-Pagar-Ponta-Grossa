"""Camada 0: criação do banco e registro de coletas brutas.

VALIDAÇÃO DO MODELO — Etapa 03. Não é código de produção.

`registrar_coleta` é o único caminho de escrita da camada bruta: grava a coleta
e todas as respostas numa só transação (a camada é imutável; não existe
"completar depois"). `carregar_etapas_anteriores` importa, sem alterar um
byte, o que as Etapas 01 e 02 baixaram.
"""
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

from . import regras

BRT = timezone(timedelta(hours=-3))
API = "https://servicos.pontagrossa.pr.gov.br/portaltransparencia-api"
ESQUEMA = Path(__file__).resolve().parents[2] / "modelo" / "schema.sql"


def criar_banco(caminho):
    con = sqlite3.connect(caminho)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(ESQUEMA.read_text(encoding="utf-8"))
    regras.semear(con)
    con.commit()
    return con


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def agora():
    return datetime.now(BRT).isoformat(timespec="seconds")


def coletor(con, nome, versao, arquivo_codigo=None, descricao=None):
    h = sha256(Path(arquivo_codigo).read_bytes()) if arquivo_codigo and Path(arquivo_codigo).exists() else None
    con.execute("INSERT OR IGNORE INTO coletor_versao (nome, versao, sha256_codigo, descricao, registrado_em) "
                "VALUES (?,?,?,?,?)", (nome, versao, h, descricao, agora()))
    return con.execute("SELECT id FROM coletor_versao WHERE nome=? AND versao=?", (nome, versao)).fetchone()[0]


def registrar_coleta(con, *, tipo, endpoint, parametros, coletada_em, origem_carimbo, status,
                     coletor_id, respostas, observacao=None):
    """respostas: lista de dicts {url, corpo(bytes), http_status, cabecalhos, recebida_em}, na ordem."""
    p = parametros
    with con:  # uma transação: coleta e respostas entram juntas ou não entram
        cur = con.execute(
            "INSERT INTO coleta (tipo, endpoint, parametros_json, entidade, exercicio, data_inicial, data_final, "
            "tipo_pesquisa, anoempenho, empenho, id_arquivo, coletada_em, origem_carimbo, status, "
            "coletor_versao_id, observacao) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tipo, endpoint, json.dumps(p, sort_keys=True, ensure_ascii=False),
             p.get("entidade"), p.get("exercicio"), p.get("dataInicial"), p.get("dataFinal"),
             p.get("tipoPesquisa"), p.get("anoempenho"), p.get("empenho"), p.get("id_arquivo"),
             coletada_em, origem_carimbo, status, coletor_id, observacao))
        cid = cur.lastrowid
        for ordem, r in enumerate(respostas):
            con.execute(
                "INSERT INTO resposta_bruta (coleta_id, ordem, url, http_status, cabecalhos_json, recebida_em, "
                "corpo, sha256, tamanho) VALUES (?,?,?,?,?,?,?,?,?)",
                (cid, ordem, r["url"], r.get("http_status"),
                 json.dumps(r["cabecalhos"], ensure_ascii=False) if r.get("cabecalhos") else None,
                 r.get("recebida_em"), r["corpo"], sha256(r["corpo"]), len(r["corpo"])))
    return cid


def _iso(s):
    """'2026-09-29T20:12:30' (sem fuso, horário local da coleta) -> ISO com -03:00."""
    return datetime.fromisoformat(s).replace(tzinfo=BRT).isoformat(timespec="seconds")


def _mtime(p):
    return datetime.fromtimestamp(Path(p).stat().st_mtime, BRT).isoformat(timespec="seconds")


def _status_listagem(corpos):
    """Completa se a última página diz last=true e a soma bate com totalElements."""
    ds = [json.loads(c) for c in corpos]
    ok = ds[-1].get("last") and sum(d["numberOfElements"] for d in ds) == ds[-1]["totalElements"]
    return "completa" if ok else "incompleta"


def _params_rp(url):
    q = dict(parse_qsl(urlsplit(url).query))
    p = {"entidade": int(q["entidade"]), "exercicio": int(q["exercicio"]),
         "dataInicial": q["dataInicial"], "dataFinal": q["dataFinal"], "size": int(q.get("size", 20))}
    if "tipoPesquisa" in q:
        p["tipoPesquisa"] = q["tipoPesquisa"]
    return p


def carregar_etapas_anteriores(con, raiz):
    """Importa os dados brutos das Etapas 01 e 02. Devolve um resumo."""
    raiz = Path(raiz)
    e2 = raiz / "etapa02" / "dados_brutos"
    resumo = {}

    # 1) listagens de RP da Etapa 02, agrupadas por consulta (MANIFESTO)
    col_rp = coletor(con, "etapa02-investigacao/coletar.py", "1", raiz / "etapa02/investigacao/coletar.py",
                     "script de investigação da Etapa 02")
    grupos = {}
    for linha in (e2 / "api" / "MANIFESTO.jsonl").read_text(encoding="utf-8").splitlines():
        m = json.loads(linha)
        base = re.sub(r"_p\d+\.json$", "", m["arquivo"])
        grupos.setdefault(base, []).append(m)
    n = 0
    for base, ms in sorted(grupos.items()):
        ms.sort(key=lambda m: int(re.search(r"_p(\d+)\.json$", m["arquivo"]).group(1)))
        resp = []
        for m in ms:
            corpo = (e2 / "api" / m["arquivo"]).read_bytes()
            assert sha256(corpo) == m["sha256"], f"hash não confere: {m['arquivo']}"
            resp.append({"url": m["url"], "corpo": corpo, "http_status": m["status"], "recebida_em": _iso(m["coletado_em"])})
        p = _params_rp(ms[0]["url"])
        registrar_coleta(con, tipo="rp_listagem", endpoint="/empenhos/restos-a-pagar", parametros=p,
                         coletada_em=_iso(ms[0]["coletado_em"]), origem_carimbo="manifesto",
                         status=_status_listagem([r["corpo"] for r in resp]), coletor_id=col_rp, respostas=resp)
        n += 1
    resumo["rp_listagem (manifesto)"] = n

    # 2) recoleta do mesmo corte, 13 min depois (Etapa 02 §3.6): OUTRO snapshot
    col_re = coletor(con, "etapa02-recoleta-inline", "1", None, "recoleta feita por script inline na Etapa 02")
    arqs = sorted((e2 / "api" / "recoleta").glob("*_p*_recoleta.json"))
    resp = []
    for a in arqs:
        pg = int(re.search(r"_p(\d+)_recoleta", a.name).group(1))
        q = {"entidade": 1, "exercicio": 2026, "dataInicial": "2026-01-01", "dataFinal": "2026-08-31", "size": 2000, "page": pg}
        resp.append({"url": f"{API}/empenhos/restos-a-pagar?{urlencode(q)}", "corpo": a.read_bytes(), "recebida_em": _mtime(a)})
    registrar_coleta(con, tipo="rp_listagem", endpoint="/empenhos/restos-a-pagar",
                     parametros={"entidade": 1, "exercicio": 2026, "dataInicial": "2026-01-01",
                                 "dataFinal": "2026-08-31", "size": 2000},
                     coletada_em=_mtime(arqs[0]), origem_carimbo="mtime_arquivo",
                     status=_status_listagem([r["corpo"] for r in resp]), coletor_id=col_re, respostas=resp,
                     observacao="recoleta do mesmo corte ~13 min depois; horário aproximado (mtime)")
    resumo["rp_listagem (recoleta)"] = 1

    # 3) movimentações por empenho
    col_mv = coletor(con, "etapa02-investigacao/casos.py", "1", raiz / "etapa02/investigacao/casos.py")
    n = 0
    for a in sorted((e2 / "movimentacao").glob("mov_ent*_ex*_emp*.json")):
        e, ano, emp = map(int, re.match(r"mov_ent(\d+)_ex(\d+)_emp(\d+)\.json", a.name).groups())
        q = {"entidade": e, "exercicio": ano, "empenho": emp, "size": 500}
        corpo = a.read_bytes()
        d = json.loads(corpo)
        registrar_coleta(con, tipo="movimentacao", endpoint="/empenhos/detalhe/movimentacao",
                         parametros={"entidade": e, "anoempenho": ano, "empenho": emp, "size": 500},
                         coletada_em=_mtime(a), origem_carimbo="mtime_arquivo",
                         status="completa" if d.get("last") else "incompleta", coletor_id=col_mv,
                         respostas=[{"url": f"{API}/empenhos/detalhe/movimentacao?{urlencode(q)}", "corpo": corpo,
                                     "recebida_em": _mtime(a)}])
        n += 1
    resumo["movimentacao"] = n

    # 4) listagens de publicações e PDFs do RREO (id do arquivo pelo nome no Content-Disposition)
    col_man = coletor(con, "etapa02-curl-manual", "1", None, "downloads com curl durante a Etapa 02")
    pubs = {}
    for a in sorted((e2 / "rreo").glob("api_publicacoes_1_ent1_ex*.json")):
        ano = int(re.search(r"_ex(\d+)", a.name).group(1))
        corpo = a.read_bytes()
        q = {"entidade": 1, "exercicio": ano}
        registrar_coleta(con, tipo="publicacoes", endpoint="/api/publicacoes/1", parametros=q,
                         coletada_em=_mtime(a), origem_carimbo="mtime_arquivo", status="completa", coletor_id=col_man,
                         respostas=[{"url": f"{API}/api/publicacoes/1?{urlencode(q)}", "corpo": corpo, "recebida_em": _mtime(a)}])
        for g in json.loads(corpo):
            for sg in g.get("list", []):
                if "Restos" in (sg.get("subGrupoRelatorio") or {}).get("valor", ""):
                    for arq in sg.get("list", []):
                        pubs[arq["nomeArquivo"]] = {"id_arquivo": arq["idArquivo"], "rotulo": arq["valor"], "exercicio": ano}
    n = 0
    for pdf in sorted((e2 / "rreo").glob("*.pdf")):
        hdr = pdf.with_suffix(".hdr").read_text(encoding="latin-1")
        nome = re.search(r'filename="([^"]+)"', hdr).group(1)
        data_http = re.search(r"^Date: (.+)$", hdr, re.M).group(1).strip()
        quando = datetime.strptime(data_http, "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=timezone.utc).astimezone(BRT)
        meta = pubs[nome]
        cab = dict(re.findall(r"^([A-Za-z-]+): (.*?)\r?$", hdr, re.M))
        registrar_coleta(con, tipo="rreo_pdf", endpoint="/api/files/arquivo",
                         parametros={"id_arquivo": meta["id_arquivo"], "exercicio": meta["exercicio"],
                                     "rotulo": meta["rotulo"], "nomeArquivo": nome},
                         coletada_em=quando.isoformat(timespec="seconds"), origem_carimbo="cabecalho_http",
                         status="completa", coletor_id=col_man,
                         respostas=[{"url": f"{API}/api/files/arquivo/{meta['id_arquivo']}", "corpo": pdf.read_bytes(),
                                     "http_status": 200, "cabecalhos": cab, "recebida_em": quando.isoformat(timespec="seconds")}])
        n += 1
    resumo["rreo_pdf"] = n

    # 5) catálogos baixados na Etapa 01
    col_e1 = coletor(con, "etapa01-curl-manual", "1", None, "downloads com curl durante a Etapa 01")
    e1 = raiz / "etapa01" / "amostras_brutas"
    for tipo, arq, endpoint, q in (("entidades", "api_entidades_lista.json", "/api/entidades/lista", {}),
                                   ("exercicios", "api_exercicios_entidade_1.json", "/api/exercicios/entidade/1", {"entidade": 1})):
        a = e1 / arq
        registrar_coleta(con, tipo=tipo, endpoint=endpoint, parametros=q, coletada_em=_mtime(a),
                         origem_carimbo="mtime_arquivo", status="completa", coletor_id=col_e1,
                         respostas=[{"url": API + endpoint, "corpo": a.read_bytes(), "recebida_em": _mtime(a)}],
                         observacao="horário aproximado: mtime da cópia do arquivo")
    resumo["catalogos"] = 2
    return resumo
