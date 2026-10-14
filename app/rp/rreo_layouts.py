"""Versioned layout rules for the RREO Annex VII PDFs the production extractor (rp-rreo-coordenadas/2) refuses -
corrective audit of 13/10/2026, item 6.5.

Two layouts, each with its own version name recorded in rreo_valor.extrator_versao:

  rp-rreo-2016/1     the portal's 2016 layout: the period is printed ("JANEIRO A FEVEREIRO 2.016"), but the columns
                     have no "(a)".."(j)" labels - only the header words, in a FIXED order: Em, Em, Pagos, Cancelados,
                     Saldo, Em, Em, Liquidados, Pagos, Cancelados, Saldo, Saldo (a, b, c, d, e, f, g, h, i, j, k, L).
                     The Executive row is printed "EXECUTIVO". Scope as the publication says (entity, unless the
                     label says Consolidado).
  rp-rreo-siconfi/1  print of the SICONFI declaration ("Tabela 7.2 - Demonstrativo dos Restos a Pagar por Poder e
                     Órgão - Municípios"), used by the portal in 2018-2020: period "JANEIRO À FEVEREIRO 2018", column
                     labels split into tokens "( a )", "e = (...)"; a zero is printed "-". It is the declaration of the
                     whole ente: scope 'consolidado'.

Same guarantees as the production extractor: one page; every recognized row read whole (one value per column, each
strictly between the neighbouring column labels); "-" is zero ONLY in the SICONFI print and ONLY in a column position;
the document's own identities must close (e = a + b - c - d, k = f + g - i - j, L = e + k, TOTAL = (I) + (II)).
Anything else raises LayoutDesconhecido: the document stays refused, never partially transcribed.
"""
import re
from datetime import date

from .normalizar import (LINHAS, MESES, NUM, PAGINAS_RREO, LayoutDesconhecido, _abrir_pdf, _celulas_da_linha,
                         _centavos_pt, _conferir_aritmetica)

VERSAO_2016 = "rp-rreo-2016/1"
VERSAO_SICONFI = "rp-rreo-siconfi/1"
ORDEM_2016 = ["Em", "Em", "Pagos", "Cancelados", "Saldo", "Em", "Em", "Liquidados", "Pagos", "Cancelados", "Saldo", "Saldo"]
COLUNAS = list("abcdefghijk") + ["L"]
LETRAS_SICONFI = {"a", "b", "c", "d", "f", "g", "h", "i", "j"}      # labels "( x )"; e, k and L are "x = (...)"
APELIDOS_DE_LINHA = {"EXECUTIVO": "PODER EXECUTIVO"}


def _fim_do_mes(ano, mes):
    return date.fromordinal(date(ano + (mes == 12), mes % 12 + 1, 1).toordinal() - 1).isoformat()


def _linhas_de_numeros(palavras, aceitar_traco):
    """{y: [(x center, text)]} of the number words (and of '-' when accepted), grouped by line (2.5 pt)."""
    linhas = {}
    for x0, y0, x1, y1, w, *_ in palavras:
        if NUM.match(w) or (aceitar_traco and w == "-" and x0 > 200):
            y = next((k for k in linhas if abs(k - y0) < 2.5), y0)
            linhas.setdefault(y, []).append(((x0 + x1) / 2, w))
    return linhas


def _rotulos(palavras, linhas):
    rotulo = {}
    for x0, y0, x1, y1, w, *_ in palavras:
        if x0 < 200 and not NUM.match(w) and w != "-":
            y = next((k for k in linhas if abs(k - y0) < 2.5), None)
            if y is not None:
                rotulo.setdefault(y, []).append(w)
    return rotulo


def _colunas_2016(palavras):
    """Header words of the 2016 layout, left to right, must be exactly ORDEM_2016 (between y 170 and 200)."""
    cab = sorted(((x0 + x1) / 2, w) for x0, y0, x1, y1, w, *_ in palavras
                 if 170 <= y0 <= 200 and w in {"Em", "Pagos", "Cancelados", "Saldo", "Liquidados"})
    # "Em" appears twice per inscription column ("Em Exercícios", "Em 31 de dezembro"): one per column, kept in order
    vistos, seq = [], []
    for x, w in cab:
        if w == "Em" and any(abs(x - v) < 15 for v in vistos):
            continue
        if w == "Em":
            vistos.append(x)
        seq.append((x, w))
    if [w for _, w in seq] != ORDEM_2016:
        raise LayoutDesconhecido(f"cabeçalho do layout 2016 diferente do esperado: {[w for _, w in seq]}")
    return {c: x for c, (x, _) in zip(COLUNAS, seq)}


def _colunas_siconfi(palavras):
    """Label row of the SICONFI print: '(' x ')' tokens for a-d, f-j; 'e', 'k', 'L' followed by '='. The leftmost
    occurrence wins (the formulas of e and k repeat letters further right)."""
    ws = sorted(((x0, y0, x1, w) for x0, y0, x1, y1, w, *_ in palavras), key=lambda t: (round(t[1]), t[0]))
    cols = {}
    for i, (x0, y0, x1, w) in enumerate(ws):
        ant = ws[i - 1] if i else None
        prox = ws[i + 1] if i + 1 < len(ws) else None
        mesma = lambda o: o is not None and abs(o[1] - y0) < 2.5
        centro = (x0 + x1) / 2
        if w in LETRAS_SICONFI and mesma(ant) and ant[3] == "(" and mesma(prox) and prox[3] == ")":
            cols.setdefault(w, centro)
        elif w in ("e", "k", "L") and mesma(prox) and prox[3] == "=":
            cols.setdefault(w, centro)
    if set(cols) != set(COLUNAS):
        raise LayoutDesconhecido(f"colunas não encontradas na impressão do Siconfi: {sorted(set(COLUNAS) - set(cols))}")
    return cols


def extrair(corpo, params):
    """(versao, escopo, ano, data_final, emitido_em, {(linha, coluna): text}) of a PDF in one of the two layouts."""
    with _abrir_pdf(corpo) as doc:
        if doc.page_count != PAGINAS_RREO:
            raise LayoutDesconhecido(f"PDF com {doc.page_count} página(s)")
        pg = doc[0]
        palavras = pg.get_text("words")
    texto = " ".join(w[4] for w in palavras)
    siconfi = "Tabela 7.2" in texto
    if siconfi:
        m = re.search(r"JANEIRO \S ([A-ZÇ]+) (\d{4}) / BIMESTRE", texto)
        if not m or m.group(1) not in MESES:
            raise LayoutDesconhecido("período não encontrado na impressão do Siconfi")
        ano, versao, escopo = int(m.group(2)), VERSAO_SICONFI, "consolidado"
        cols = _colunas_siconfi(palavras)
    else:
        m = re.search(r"JANEIRO A ([A-ZÇ]+) (\d)\.(\d{3})", texto)
        if not m or m.group(1) not in MESES:
            raise LayoutDesconhecido("período não encontrado no layout 2016")
        ano, versao = int(m.group(2) + m.group(3)), VERSAO_2016
        escopo = "consolidado" if "Consolidado" in params.get("rotulo", "") else "entidade"
        cols = _colunas_2016(palavras)
    data_final = _fim_do_mes(ano, MESES[m.group(1)])
    em = re.search(r"emitido em (\d+/\w+/\d{4}) as (\d+)h e (\d+)m", texto)
    emitido = f"{em.group(1)} {em.group(2)}:{em.group(3)}" if em else None
    linhas = _linhas_de_numeros(palavras, aceitar_traco=siconfi)
    rotulo = _rotulos(palavras, linhas)
    celulas = {}
    for y in sorted(linhas):
        nome = " ".join(rotulo.get(y, []))
        nome = APELIDOS_DE_LINHA.get(nome, nome)
        linha = next((l for l in LINHAS if nome.startswith(l)), None)
        if not linha:
            continue
        for c, w in _celulas_da_linha(linhas[y], cols, linha).items():
            w = "0,00" if w == "-" else w
            ja = celulas.get((linha, c))
            if ja is not None and ja != w:
                raise LayoutDesconhecido(f"linha {linha!r} repetida com outro valor na coluna ({c}): {ja} e {w}")
            celulas[(linha, c)] = w
    _conferir_aritmetica(celulas)
    return versao, escopo, ano, data_final, emitido, {k: _centavos_pt(v) for k, v in celulas.items()}
