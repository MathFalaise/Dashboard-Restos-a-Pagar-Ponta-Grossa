"""INVESTIGAÇÃO — Etapa 02. NÃO é código de produção.

Extrai os valores do RREO Anexo VII (PDF de 1 página, gerado pelo sistema
Elotech) atribuindo cada número à coluna cujo rótulo "(a)".."(j)", "e=", "k=",
"L=" está mais próximo na horizontal. As linhas são agrupadas pela posição
vertical. Imprime a grade para conferência visual: não interpreta nada.
"""
import re
import sys

import fitz  # pymupdf

NUM = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d{2}$")
ROTULOS = ["(a)", "(b)", "(c)", "(d)", "e=(a+b)", "(f)", "(g)", "(h)", "(i)", "(j)", "k=(f+g)", "L=(e+k)"]


def colunas(words):
    """x-centro de cada rótulo de coluna encontrado no cabeçalho."""
    xs = {}
    for x0, y0, x1, y1, w, *_ in words:
        for r in ROTULOS:
            if w.startswith(r) and r not in xs:
                xs[r] = ((x0 + x1) / 2, y0)
    return xs


def extrair(caminho):
    pg = fitz.open(caminho)[0]
    words = pg.get_text("words")
    cols = colunas(words)
    nums = [(round(y0, 1), (x0 + x1) / 2, w) for x0, y0, x1, y1, w, *_ in words if NUM.match(w)]
    linhas = {}
    for y, xc, w in nums:
        chave = next((k for k in linhas if abs(k - y) < 2.5), y)
        linhas.setdefault(chave, []).append((xc, w))
    rotulo_linha = {}
    for x0, y0, x1, y1, w, *_ in words:
        if x0 < 200 and not NUM.match(w):
            chave = next((k for k in linhas if abs(k - y0) < 2.5), None)
            if chave is not None:
                rotulo_linha.setdefault(chave, []).append(w)
    print(f"== {caminho}")
    print("colunas (x):", {k: round(v[0]) for k, v in sorted(cols.items(), key=lambda kv: kv[1][0])})
    for y in sorted(linhas):
        cel = {}
        for xc, w in sorted(linhas[y]):
            col = min(cols, key=lambda r: abs(cols[r][0] - xc))
            cel.setdefault(col, []).append(w)
        print(f"y={y:6.1f} {' '.join(rotulo_linha.get(y, []))[:45]:45s} | " +
              " | ".join(f"{c}={'/'.join(v)}" for c, v in sorted(cel.items(), key=lambda kv: cols[kv[0]][0])))


if __name__ == "__main__":
    for c in sys.argv[1:]:
        extrair(c)
