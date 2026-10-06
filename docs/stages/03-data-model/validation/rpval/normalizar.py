"""Layer 1: normalization (faithful typing of the raw data, without interpretation).

MODEL VALIDATION - stage 03. Not production code.

Principles:
  * every content[] item becomes exactly one row (nothing is discarded or merged);
  * money becomes cents; a value with more than 2 decimal places is an ERROR, not rounding;
  * a missing key is recorded (chaves_ausentes), not invented.
"""
import json
import re
from datetime import date, datetime
from decimal import Decimal

import fitz  # pymupdf - only to transcribe the RREO PDF

from .bruto import agora

VERSAO = "normalizador-1"

BASE = ["entidade", "empenho", "anoempenho", "empenhoExercicio", "cnpjNome", "dataEmissao", "programatica",
        "fonteRecurso", "descricaoFonte", "fornecedor", "nome", "cnpj", "proc", "aproc", "canceladoProc",
        "pagoProc", "pagoProcEstornado", "canceladoAProc", "pagoAProc", "pagoAProcEstornado", "retencao",
        "liquidado", "desdobraDesp", "subDesdobramento"]
OPCIONAIS = ["orgao", "unidade", "funcao", "subFuncao", "programa", "projeto", "elemento"]
DINHEIRO = ["proc", "aproc", "canceladoProc", "pagoProc", "pagoProcEstornado", "canceladoAProc",
            "pagoAProc", "pagoAProcEstornado", "liquidado", "retencao"]


class ValorNaoRepresentavel(ValueError):
    pass


def centavos(v):
    if v is None:
        return None
    d = Decimal(str(v))
    q = d.quantize(Decimal("0.01"))
    if q != d:
        raise ValorNaoRepresentavel(f"{v!r} tem mais de 2 casas decimais")
    return int(q * 100)


def _json(corpo):
    return json.loads(corpo, parse_float=Decimal)


def normalizar(con):
    """Creates a normalization run over ALL the raw data. Returns the id."""
    with con:
        nid = con.execute("INSERT INTO normalizacao_execucao (normalizador_versao, executada_em) VALUES (?,?)",
                          (VERSAO, agora())).lastrowid
        rs = con.execute("SELECT r.id, r.coleta_id, c.tipo, r.corpo FROM resposta_bruta r "
                         "JOIN coleta c ON c.id = r.coleta_id ORDER BY r.id").fetchall()
        for rid, cid, tipo, corpo in rs:
            if tipo == "rp_listagem":
                _rp(con, nid, rid, cid, corpo)
            elif tipo == "movimentacao":
                _mov(con, nid, rid, cid, corpo)
            elif tipo == "rreo_pdf":
                _rreo(con, nid, cid, corpo)
            elif tipo == "entidades":
                for e in _json(corpo):
                    con.execute("INSERT INTO entidade_ref VALUES (?,?,?,?,?,?)",
                                (nid, cid, e["id"], e.get("nome"), e.get("cnpj"), e.get("tipo")))
            elif tipo == "exercicios":
                for x in _json(corpo):
                    ent = x["id"]["entidade"]["id"]
                    con.execute("INSERT INTO exercicio_ref VALUES (?,?,?,?,?,?)",
                                (nid, cid, ent, x["id"]["exercicio"], int(bool(x.get("aberto"))), int(bool(x.get("fechado")))))
    return nid


def _rp(con, nid, rid, cid, corpo):
    for i, r in enumerate(_json(corpo)["content"]):
        conhecidas = set(BASE) | set(OPCIONAIS)
        ausentes = [k for k in BASE + OPCIONAIS if k not in r]
        extras = sorted(k for k in r if k not in conhecidas)
        con.execute(
            "INSERT INTO rp_registro VALUES (" + ",".join("?" * 37) + ")",
            (nid, rid, i, cid, r.get("entidade"), r.get("anoempenho"), r.get("empenho"), r.get("empenhoExercicio"),
             r.get("dataEmissao"), r.get("programatica"), r.get("fonteRecurso"), r.get("descricaoFonte"),
             r.get("fornecedor"), r.get("nome"), r.get("cnpj"), r.get("cnpjNome"),
             *[centavos(r.get(c, 0)) for c in DINHEIRO],
             r.get("orgao"), r.get("unidade"), r.get("funcao"), r.get("subFuncao"), r.get("programa"),
             r.get("projeto"), r.get("elemento"), r.get("desdobraDesp"), r.get("subDesdobramento"),
             json.dumps(ausentes), json.dumps(extras)))


def _mov(con, nid, rid, cid, corpo):
    ent, ano, emp = con.execute("SELECT entidade, anoempenho, empenho FROM coleta WHERE id=?", (cid,)).fetchone()
    for i, m in enumerate(_json(corpo)["content"]):
        con.execute(
            "INSERT INTO movimentacao_lancamento VALUES (" + ",".join("?" * 18) + ")",
            (nid, rid, i, cid, ent, ano, emp, m["data"], m["tipoLancamento"], (m.get("descricaoTipoLancamento") or "").strip(),
             centavos(m["valor"]), centavos(m.get("valorALiquidar")), centavos(m.get("valorAPagar")),
             m.get("exercicioLiquidacao"), m.get("noLiquidacao"), m.get("exercicioPagamento"), m.get("noPagamento"),
             m.get("nroDocumento")))


# --- transcription of the RREO Annex VII PDF (1 page, Elotech layout) ---------
EXTRATOR = "rreo-coordenadas-1"
NUM = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d{2}$")
ROTULOS = {"(a)": "a", "(b)": "b", "(c)": "c", "(d)": "d", "e=(a+b)": "e", "(f)": "f", "(g)": "g",
           "(h)": "h", "(i)": "i", "(j)": "j", "k=(f+g)": "k", "L=(e+k)": "L"}
MESES = {"JANEIRO": 1, "FEVEREIRO": 2, "MARÇO": 3, "ABRIL": 4, "MAIO": 5, "JUNHO": 6, "JULHO": 7,
         "AGOSTO": 8, "SETEMBRO": 9, "OUTUBRO": 10, "NOVEMBRO": 11, "DEZEMBRO": 12}
LINHAS = ("RESTOS A PAGAR (EXCETO", "PODER EXECUTIVO", "RESTOS A PAGAR (INTRA", "TOTAL (III)")


def _rreo(con, nid, cid, corpo):
    pg = fitz.open(stream=corpo, filetype="pdf")[0]
    texto = pg.get_text()
    m = re.search(r"JANEIRO A ([A-ZÇ]+) (\d)\.(\d{3})", texto)
    mes, ano = MESES[m.group(1)], int(m.group(2) + m.group(3))
    prox = date(ano + (mes == 12), mes % 12 + 1, 1)
    data_final = date.fromordinal(prox.toordinal() - 1).isoformat()
    em = re.search(r"emitido em (\d+/\w+/\d{4}) as (\d+)h e (\d+)m", texto)
    emitido = f"{em.group(1)} {em.group(2)}:{em.group(3)}" if em else None
    # scope by the publication label ("6º Bimestre - Consolidado"), kept in the collection parameters
    rotulo_pub = json.loads(con.execute("SELECT parametros_json FROM coleta WHERE id=?", (cid,)).fetchone()[0])["rotulo"]
    escopo = "consolidado" if "Consolidado" in rotulo_pub else "entidade"
    palavras = pg.get_text("words")
    cols = {}
    for x0, y0, x1, y1, w, *_ in palavras:
        for r, c in ROTULOS.items():
            if w.startswith(r) and c not in cols:
                cols[c] = (x0 + x1) / 2
    faltam = set(ROTULOS.values()) - set(cols)
    assert not faltam, f"colunas não encontradas no PDF: {faltam}"
    linhas = {}
    for x0, y0, x1, y1, w, *_ in palavras:
        if NUM.match(w):
            y = next((k for k in linhas if abs(k - y0) < 2.5), y0)
            linhas.setdefault(y, []).append(((x0 + x1) / 2, w))
    rotulo = {}
    for x0, y0, x1, y1, w, *_ in palavras:
        if x0 < 200 and not NUM.match(w):
            y = next((k for k in linhas if abs(k - y0) < 2.5), None)
            if y is not None:
                rotulo.setdefault(y, []).append(w)
    for y, vals in linhas.items():
        nome = " ".join(rotulo.get(y, []))
        chave = next((l for l in LINHAS if nome.startswith(l)), None)
        if not chave:
            continue
        nome_linha = "TOTAL (III)" if chave == "TOTAL (III)" else chave
        vistos = {}
        for xc, w in vals:
            c = min(cols, key=lambda k: abs(cols[k] - xc))
            vistos.setdefault(c, w)
        for c, w in vistos.items():
            con.execute("INSERT OR IGNORE INTO rreo_valor VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (nid, cid, EXTRATOR, escopo, ano, data_final, emitido, nome_linha, c,
                         int(Decimal(w.replace(".", "").replace(",", ".")) * 100)))
