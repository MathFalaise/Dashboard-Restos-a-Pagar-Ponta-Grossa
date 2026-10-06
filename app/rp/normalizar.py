"""Layer 1 - normalization: faithful typing of the raw data, WITHOUT interpretation.

Guarantees (stage 04.2 gate):
  * each item of content[] becomes exactly one row, at its source position (response, index);
  * nothing is discarded, merged or invented; a missing key is recorded in `chaves_ausentes`;
  * money becomes cents; a value with more than 2 decimal places is an ERROR (never rounded);
  * a response that is not a valid page (failed snapshot) produces no rows and is counted;
  * a catalog (entities/fiscal years) with an unexpected structure produces no rows and goes to `problemas`;
  * each RREO PDF leaves a row in rreo_extracao (extractor, PyMuPDF/MuPDF version, SHA-256, file id, extraction
    date, how many values came out or the error): the values depend on the method, so the method stays with them;
  * the run keeps the highest collection it read (ultima_coleta_id): a snapshot with 0 records also counts as
    processed, without depending on having produced rows;
  * layer 0 is only read.
"""
import json
import logging
import re
from datetime import date
from decimal import Decimal

from . import agora, banco

log = logging.getLogger("rp.normalizar")

VERSAO = "rp-normalizador/1"
EXTRATOR_RREO = "rp-rreo-coordenadas/1"

BASE = ["entidade", "empenho", "anoempenho", "empenhoExercicio", "cnpjNome", "dataEmissao", "programatica",
        "fonteRecurso", "descricaoFonte", "fornecedor", "nome", "cnpj", "proc", "aproc", "canceladoProc",
        "pagoProc", "pagoProcEstornado", "canceladoAProc", "pagoAProc", "pagoAProcEstornado", "retencao",
        "liquidado", "desdobraDesp", "subDesdobramento"]
OPCIONAIS = ["orgao", "unidade", "funcao", "subFuncao", "programa", "projeto", "elemento"]
CONHECIDAS = set(BASE) | set(OPCIONAIS)
ESPERADAS = BASE + OPCIONAIS
DINHEIRO = ["proc", "aproc", "canceladoProc", "pagoProc", "pagoProcEstornado", "canceladoAProc",
            "pagoAProc", "pagoAProcEstornado", "liquidado", "retencao"]

SQL_RP = "INSERT INTO rp_registro VALUES (" + ",".join("?" * 37) + ")"
SQL_MOV = "INSERT INTO movimentacao_lancamento VALUES (" + ",".join("?" * 18) + ")"
# No OR IGNORE (critical review, item 11): a repeated cell with the SAME value no longer gets here (_rreo writes a
# single row) and a different value becomes LayoutDesconhecido; any other key conflict is an error, never ignored.
SQL_RREO = "INSERT INTO rreo_valor VALUES (?,?,?,?,?,?,?,?,?,?)"
PAGINAS_RREO = 1          # known Annex VII layout (Elotech): 1 page; the 36 PDFs in the store have 1
# DATA or PDF errors that leave an RREO without transcription, recorded in rreo_extracao. A program error
# (TypeError, AttributeError, NameError...) does not go here: it stops the processing (critical review, item 7).
ERROS_DE_LAYOUT = (LookupError, ValueError, RuntimeError)   # LayoutDesconhecido is a ValueError; PyMuPDF: RuntimeError
SQL_EXTRACAO = ("INSERT INTO rreo_extracao (normalizacao_id, resposta_id, coleta_id, extrator_versao, biblioteca, "
                "biblioteca_versao, sha256_pdf, id_arquivo, rotulo, extraida_em, valores, erro) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)")

_CENTAVO = Decimal("0.01")
_INT_SEGURO = 10 ** 20   # in this range an integer fits Decimal's precision (28 digits) with 2 decimal places


class ValorNaoRepresentavel(ValueError):
    pass


def centavos(v):
    if v is None:
        return None
    if type(v) is int and -_INT_SEGURO < v < _INT_SEGURO:
        return v * 100                                   # same result as the Decimal path, without conversion
    d = v if type(v) is Decimal else Decimal(str(v))     # Decimal(str(d)) == d for every Decimal
    q = d.quantize(_CENTAVO)
    if q != d:
        raise ValorNaoRepresentavel(f"{v!r} tem mais de 2 casas decimais")
    return int(q * 100)


def _pagina(corpo):
    try:
        d = json.loads(corpo, parse_float=Decimal)
        return d["content"] if isinstance(d, dict) and isinstance(d.get("content"), list) else None
    except (ValueError, RecursionError):
        return None


def _lista_json(corpo):
    """List of JSON objects, or None if the body is not that."""
    try:
        d = json.loads(corpo)
    except (ValueError, RecursionError):
        return None
    return d if isinstance(d, list) and all(isinstance(x, dict) for x in d) else None


def normalizar(con):
    """New normalization run over all the raw data. Returns (id, summary)."""
    resumo = {"respostas": 0, "ignoradas_sem_pagina": 0, "rp_registro": 0, "movimentacao_lancamento": 0,
              "rreo_valor": 0, "problemas": []}
    with con:
        ultima = con.execute("SELECT IFNULL(MAX(id), 0) FROM coleta").fetchone()[0]
        nid = con.execute("INSERT INTO normalizacao_execucao (normalizador_versao, executada_em, ultima_coleta_id) "
                          "VALUES (?,?,?)", (VERSAO, agora(), ultima)).lastrowid
        itens = con.execute("SELECT r.id, r.coleta_id, c.tipo, r.sha256, c.parametros_json, c.entidade, c.anoempenho, "
                            "c.empenho FROM resposta_bruta r JOIN coleta c ON c.id = r.coleta_id WHERE c.id <= ? "
                            "ORDER BY c.coletada_em, c.snapshot_uid, r.ordem", (ultima,)).fetchall()
        for rid, cid, tipo, sha, params, ent, ano, emp in itens:
            resumo["respostas"] += 1
            corpo = banco.corpo(con, sha)
            if tipo == "rp_listagem":
                conteudo = _pagina(corpo)
                if conteudo is None:
                    resumo["ignoradas_sem_pagina"] += 1
                    continue
                con.executemany(SQL_RP, (_linha_rp(nid, rid, i, cid, r) for i, r in enumerate(conteudo)))
                resumo["rp_registro"] += len(conteudo)
            elif tipo == "movimentacao":
                conteudo = _pagina(corpo)
                if conteudo is None:
                    resumo["ignoradas_sem_pagina"] += 1
                    continue
                con.executemany(SQL_MOV, (_linha_mov(nid, rid, i, cid, ent, ano, emp, m) for i, m in enumerate(conteudo)))
                resumo["movimentacao_lancamento"] += len(conteudo)
            elif tipo == "rreo_pdf":
                if corpo[:4] != b"%PDF":
                    resumo["ignoradas_sem_pagina"] += 1
                    continue
                meta = json.loads(params)
                try:
                    n, erro = _rreo(con, nid, cid, meta, corpo), None
                    resumo["rreo_valor"] += n
                except ERROS_DE_LAYOUT as e:  # a new layout does not stop the processing; it gets recorded
                    n, erro = 0, f"{type(e).__name__}: {e}"
                    resumo["problemas"].append({"coleta_id": cid, "extrator": EXTRATOR_RREO, "erro": erro})
                    log.warning("RREO da coleta %d não transcrito: %s", cid, e)
                con.execute(SQL_EXTRACAO, (nid, rid, cid, EXTRATOR_RREO, "PyMuPDF/MuPDF", _versao_biblioteca_pdf(), sha,
                                           meta.get("id_arquivo"), meta.get("rotulo"), agora(), n, erro))
            elif tipo in ("entidades", "exercicios"):
                lista = _lista_json(corpo)
                if lista is None:
                    resumo["ignoradas_sem_pagina"] += 1
                    continue
                try:
                    if tipo == "entidades":
                        linhas = [(nid, cid, e["id"], e.get("nome"), e.get("cnpj"), e.get("tipo")) for e in lista]
                        sql = "INSERT INTO entidade_ref VALUES (?,?,?,?,?,?)"
                    else:
                        linhas = [(nid, cid, x["id"]["entidade"]["id"], x["id"]["exercicio"],
                                   int(bool(x.get("aberto"))), int(bool(x.get("fechado")))) for x in lista]
                        sql = "INSERT INTO exercicio_ref VALUES (?,?,?,?,?,?)"
                except (KeyError, TypeError) as e:  # unexpected structure: no row, problem recorded
                    resumo["problemas"].append({"coleta_id": cid, "catalogo": tipo, "erro": f"{type(e).__name__}: {e}"})
                    log.warning("catalogo %s da coleta %d nao normalizado: %r", tipo, cid, e)
                    continue
                con.executemany(sql, linhas)
        if resumo["problemas"]:
            con.execute("UPDATE normalizacao_execucao SET observacao=? WHERE id=?",
                        (json.dumps({"problemas": resumo["problemas"]}, ensure_ascii=False), nid))
    log.info("normalização %d: %s", nid, resumo)
    return nid, resumo


def _linha_rp(nid, rid, i, cid, r):
    ausentes = [k for k in ESPERADAS if k not in r]
    extras = sorted(k for k in r if k not in CONHECIDAS)
    return (nid, rid, i, cid, r.get("entidade"), r.get("anoempenho"), r.get("empenho"), r.get("empenhoExercicio"),
            r.get("dataEmissao"), r.get("programatica"), r.get("fonteRecurso"), r.get("descricaoFonte"),
            r.get("fornecedor"), r.get("nome"), r.get("cnpj"), r.get("cnpjNome"),
            *[centavos(r.get(c, 0)) for c in DINHEIRO],
            r.get("orgao"), r.get("unidade"), r.get("funcao"), r.get("subFuncao"), r.get("programa"),
            r.get("projeto"), r.get("elemento"), r.get("desdobraDesp"), r.get("subDesdobramento"),
            json.dumps(ausentes), json.dumps(extras))


def _linha_mov(nid, rid, i, cid, ent, ano, emp, m):
    return (nid, rid, i, cid, ent, ano, emp, m["data"], m["tipoLancamento"], (m.get("descricaoTipoLancamento") or "").strip(),
            centavos(m["valor"]), centavos(m.get("valorALiquidar")), centavos(m.get("valorAPagar")),
            m.get("exercicioLiquidacao"), m.get("noLiquidacao"), m.get("exercicioPagamento"), m.get("noPagamento"),
            m.get("nroDocumento"))


# --- transcription of the RREO Annex VII (1-page PDF, Elotech layout) ------
NUM = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d{2}$")
ROTULOS = {"(a)": "a", "(b)": "b", "(c)": "c", "(d)": "d", "e=(a+b)": "e", "(f)": "f", "(g)": "g",
           "(h)": "h", "(i)": "i", "(j)": "j", "k=(f+g)": "k", "L=(e+k)": "L"}
MESES = {"JANEIRO": 1, "FEVEREIRO": 2, "MARÇO": 3, "ABRIL": 4, "MAIO": 5, "JUNHO": 6, "JULHO": 7,
         "AGOSTO": 8, "SETEMBRO": 9, "OUTUBRO": 10, "NOVEMBRO": 11, "DEZEMBRO": 12}
LINHAS = ("RESTOS A PAGAR (EXCETO", "PODER EXECUTIVO", "RESTOS A PAGAR (INTRA", "TOTAL (III)")


class LayoutDesconhecido(ValueError):
    pass


def _versao_biblioteca_pdf():
    """Version of PyMuPDF and MuPDF that made the transcription (the values depend on them)."""
    try:
        import pymupdf
    except ImportError:  # old versions only expose `fitz`
        import fitz as pymupdf
    return f"PyMuPDF {getattr(pymupdf, 'VersionBind', '?')} / MuPDF {getattr(pymupdf, 'VersionFitz', '?')}"


def _abrir_pdf(corpo):
    """PDF document (use with `with`, to release the document after reading)."""
    try:
        import pymupdf
    except ImportError:  # old versions only expose `fitz`
        import fitz as pymupdf
    return pymupdf.open(stream=corpo, filetype="pdf")


def _rreo(con, nid, cid, params, corpo):
    with _abrir_pdf(corpo) as doc:
        # only page 1 is read: with another page count the PDF is not the known layout, and transcribing only the
        # first one would give a partial RREO without warning (critical review, item 12)
        if doc.page_count != PAGINAS_RREO:
            raise LayoutDesconhecido(f"PDF com {doc.page_count} página(s); o layout conhecido do Anexo VII tem "
                                     f"{PAGINAS_RREO}")
        pg = doc[0]
        texto = pg.get_text()
        palavras = pg.get_text("words")
    m = re.search(r"JANEIRO A ([A-ZÇ]+) (\d)\.(\d{3})", texto)
    if not m:
        raise LayoutDesconhecido(f"período não encontrado no RREO (coleta {cid})")
    mes, ano = MESES[m.group(1)], int(m.group(2) + m.group(3))
    data_final = date.fromordinal(date(ano + (mes == 12), mes % 12 + 1, 1).toordinal() - 1).isoformat()
    em = re.search(r"emitido em (\d+/\w+/\d{4}) as (\d+)h e (\d+)m", texto)
    emitido = f"{em.group(1)} {em.group(2)}:{em.group(3)}" if em else None
    escopo = "consolidado" if "Consolidado" in params.get("rotulo", "") else "entidade"
    cols = {}
    for x0, y0, x1, y1, w, *_ in palavras:
        for r, c in ROTULOS.items():
            if w.startswith(r) and c not in cols:
                cols[c] = (x0 + x1) / 2
    if set(cols) != set(ROTULOS.values()):
        raise LayoutDesconhecido(f"colunas não encontradas no RREO: {sorted(set(ROTULOS.values()) - set(cols))}")
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
    # A cell (row, column) can only have ONE value. Two different numbers falling in the same cell (same row, nearest
    # column; or the same row printed twice) used to be silently dropped (the second one); now the whole PDF is left
    # untranscribed and the reason recorded (audit NORM-02). Repeating the same value is accepted.
    valores, celulas = [], {}
    for y, vals in linhas.items():
        nome = " ".join(rotulo.get(y, []))
        linha = next((l for l in LINHAS if nome.startswith(l)), None)
        if not linha:
            continue
        vistos = {}
        for xc, w in vals:
            c = min(cols, key=lambda k: abs(cols[k] - xc))
            if vistos.setdefault(c, w) != w:
                raise LayoutDesconhecido(f"dois números na coluna ({c}) da linha {linha!r}: {vistos[c]} e {w}")
        for c, w in vistos.items():
            ja = celulas.get((linha, c))
            if ja is not None and ja != w:
                raise LayoutDesconhecido(f"linha {linha!r} repetida com outro valor na coluna ({c}): {ja} e {w}")
            if ja is not None:          # the same row printed again with the same value: a single row (formerly, OR IGNORE)
                continue
            celulas[(linha, c)] = w
            valores.append((nid, cid, EXTRATOR_RREO, escopo, ano, data_final, emitido, linha, c,
                            int(Decimal(w.replace(".", "").replace(",", ".")) * 100)))
    return con.executemany(SQL_RREO, valores).rowcount if valores else 0
