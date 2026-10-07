"""Charts as SVG generated on the server: bars (docs/stages/05-analysis/ANALYTICAL_CONTRACT.md section 7), and the
pie (donut) and vertical columns of the overview (docs/stages/06-bi/SCOPE.md).

* No JavaScript and no external resource: the <svg> is part of the HTML. No `style` attribute nor <style> (the CSP
  `style-src 'self'` would block them): only geometry attributes (x, y, width, height) and classes, with the colors
  in estilo.css.
* Presentation, not calculation: values arrive ready from the panel layer. Here they are only turned into pixels
  (scale), with no sum or difference of monetary values.
* A point without a value is a GAP (dashed rectangle and the text "sem dado"), never a zero-height bar. A true zero
  is a line at the base with the label "0".
* Each bar is a link (internal href, starting with "/") to the cut-off screen, where the provenance is; the table of
  exact values always goes with the chart and is the source of truth.
"""
import math

from .formato import abreviado, esc, moeda, percentual

LARGURA, ALTURA = 720, 340
MARGEM_X, TOPO, BASE = 20, 20, 64          # BASE: room for the cut-off labels


def barras(ident, titulo, descricao, pontos):
    """pontos: [{"rotulo": "31/01", "valor_c": int or None, "titulo": point text, "href": "/..."}].
    Returns the <figure> with the SVG; the title and description text go in <title>/<desc> (screen readers)."""
    valores = [p["valor_c"] for p in pontos if p["valor_c"] is not None]
    maior = max([0] + valores)
    menor = min([0] + valores)
    amplitude = (maior - menor) or 1
    altura_util = ALTURA - TOPO - BASE
    faixa = (LARGURA - 2 * MARGEM_X) / max(1, len(pontos))
    largura_barra = faixa * 0.6

    def y(v):
        return TOPO + (maior - v) * altura_util / amplitude

    base = y(0)
    partes = [f'<line class="eixo" x1="{MARGEM_X}" y1="{base:.1f}" x2="{LARGURA - MARGEM_X}" y2="{base:.1f}"/>']
    for i, p in enumerate(pontos):
        x = MARGEM_X + i * faixa + (faixa - largura_barra) / 2
        centro = MARGEM_X + i * faixa + faixa / 2
        v = p["valor_c"]
        if v is None:       # the gap fills almost the whole band of the point, so the label fits even with many points
            largura_lacuna = faixa * 0.9
            forma = (f'<rect class="lacuna" x="{centro - largura_lacuna / 2:.1f}" y="{TOPO}" '
                     f'width="{largura_lacuna:.1f}" height="{altura_util}"/>'
                     f'<text class="rotulo-lacuna" x="{centro:.1f}" y="{TOPO + altura_util / 2 - 12:.1f}" '
                     f'text-anchor="middle"><tspan x="{centro:.1f}">sem</tspan>'
                     f'<tspan x="{centro:.1f}" dy="26">dado</tspan></text>')
        elif v == 0:
            forma = (f'<line class="zero" x1="{x:.1f}" y1="{base:.1f}" x2="{x + largura_barra:.1f}" y2="{base:.1f}"/>'
                     f'<text class="rotulo-zero" x="{centro:.1f}" y="{base - 6:.1f}" text-anchor="middle">0</text>')
        else:
            topo, fundo = sorted((y(v), base))
            forma = (f'<rect class="barra{" negativa" if v < 0 else ""}" x="{x:.1f}" y="{topo:.1f}" '
                     f'width="{largura_barra:.1f}" height="{max(fundo - topo, 1):.1f}"/>')
        partes.append(f'<a href="{esc(p["href"])}" class="ponto"><title>{esc(p["titulo"])}</title>{forma}'
                      f'<text class="rotulo-corte" x="{centro:.1f}" y="{ALTURA - BASE + 30}" text-anchor="middle">'
                      f'{esc(p["rotulo"])}</text></a>')
    return (f'<figure class="grafico"><svg viewBox="0 0 {LARGURA} {ALTURA}" role="img" '
            f'aria-labelledby="{esc(ident)}-t {esc(ident)}-d">'
            f'<title id="{esc(ident)}-t">{esc(titulo)}</title><desc id="{esc(ident)}-d">{esc(descricao)}</desc>'
            + "".join(partes) + "</svg>"
            f'<figcaption>{esc(titulo)}. Os valores exatos estão na tabela abaixo; barra tracejada com "sem dado" '
            "é lacuna (corte sem valor), nunca zero.</figcaption></figure>")


# ------------------------------------------------------------------ overview: pie (donut) and vertical columns
PIZZA_LADO, PIZZA_RAIO, PIZZA_FURO = 240, 112, 70


def _setor(cx, cy, raio, furo, inicio, fim):
    """Path of a donut sector between two angles (radians, clockwise from the top)."""
    def ponto(r, a):
        return cx + r * math.sin(a), cy - r * math.cos(a)
    grande = 1 if fim - inicio > math.pi else 0
    (x1, y1), (x2, y2) = ponto(raio, inicio), ponto(raio, fim)
    (x3, y3), (x4, y4) = ponto(furo, fim), ponto(furo, inicio)
    return (f"M{x1:.2f} {y1:.2f}A{raio} {raio} 0 {grande} 1 {x2:.2f} {y2:.2f}"
            f"L{x3:.2f} {y3:.2f}A{furo} {furo} 0 {grande} 0 {x4:.2f} {y4:.2f}Z")


def _anel(cx, cy, raio, furo):
    """A whole donut (one part = 100%): two circles drawn with fill-rule evenodd."""
    def circulo(r):
        return f"M{cx - r} {cy}A{r} {r} 0 1 0 {cx + r} {cy}A{r} {r} 0 1 0 {cx - r} {cy}Z"
    return circulo(raio) + circulo(furo)


def pizza(ident, titulo, descricao, total_c, fatias, centro):
    """Donut chart with its legend. total_c: the total the parts close against (from the panel layer, never summed
    here); fatias: [{"rotulo", "valor_c" (>= 0), "decimos" (share in tenths of a point, from the panel layer),
    "classe": "c1".."c8", "href": "/..." or None}]; centro: (big text, small text) for the hole.
    Each part becomes an angle proportional to valor_c / total_c; a zero part has no sector but stays in the legend."""
    c = PIZZA_LADO / 2
    partes, inicio = [], 0.0
    for f in fatias:
        if f["valor_c"] <= 0:
            continue
        fim = inicio + 2 * math.pi * f["valor_c"] / total_c
        if f["valor_c"] == total_c:
            forma = (f'<path class="fatia {esc(f["classe"])}" fill-rule="evenodd" '
                     f'd="{_anel(c, c, PIZZA_RAIO, PIZZA_FURO)}"/>')
        else:
            forma = f'<path class="fatia {esc(f["classe"])}" d="{_setor(c, c, PIZZA_RAIO, PIZZA_FURO, inicio, fim)}"/>'
        dica = f'<title>{esc(f["rotulo"])}: {esc(moeda(f["valor_c"]))} ({esc(percentual(f["decimos"]))})</title>'
        partes.append(f'<a href="{esc(f["href"])}" class="setor">{dica}{forma}</a>' if f.get("href")
                      else f'<g class="setor">{dica}{forma}</g>')
        inicio = fim
    grande, pequeno = centro
    partes.append(f'<text class="centro-valor" x="{c}" y="{c + 2}" text-anchor="middle">{esc(grande)}</text>'
                  f'<text class="centro-rotulo" x="{c}" y="{c + 24}" text-anchor="middle">{esc(pequeno)}</text>')
    itens = []
    for f in fatias:
        texto = f'<a href="{esc(f["href"])}">{esc(f["rotulo"])}</a>' if f.get("href") else esc(f["rotulo"])
        itens.append(f'<li><span class="amostra {esc(f["classe"])}" aria-hidden="true"></span>'
                     f'<span class="legenda-rotulo">{texto}</span>'
                     f'<span class="legenda-valor"><data value="{f["valor_c"]}" title="{esc(moeda(f["valor_c"]))}">'
                     f'{esc(abreviado(f["valor_c"]))}</data> <strong>{esc(percentual(f["decimos"]))}</strong></span></li>')
    return (f'<figure class="pizza"><svg viewBox="0 0 {PIZZA_LADO} {PIZZA_LADO}" role="img" '
            f'aria-labelledby="{esc(ident)}-t {esc(ident)}-d">'
            f'<title id="{esc(ident)}-t">{esc(titulo)}</title><desc id="{esc(ident)}-d">{esc(descricao)}</desc>'
            + "".join(partes) + f'</svg><ul class="legenda">{"".join(itens)}</ul></figure>')


COL_LARGURA, COL_ALTURA = 720, 330
COL_ESQUERDA, COL_DIREITA, COL_TOPO, COL_BASE = 96, 12, 16, 46


def _passo(maior):
    """A round step in cents (1, 2, 2,5 or 5 x 10^k) giving at most 5 grid intervals up to `maior`."""
    if maior <= 0:
        return 1
    base = 10 ** (len(str(maior)) - 1)          # maior < 10 * base, so 2 * base always gives at most 5 intervals
    for multiplo in (10, 20, 25, 50, 100, 200):
        passo = base * multiplo // 100 or 1
        if maior <= 5 * passo:
            return passo


def colunas(ident, titulo, descricao, grupos, series):
    """Vertical columns, one or more series per group. grupos: [{"rotulo", "valores": [int or None per series],
    "titulos": [hint per series], "href": "/..." or None}]; series: [(name, "c1".."c8")]. A value None is a GAP
    (dashed outline and "sem dado"), never a zero-height column; a true zero is a line at the base."""
    valores = [v for g in grupos for v in g["valores"] if v is not None]
    maior, menor = max([0] + valores), min([0] + valores)
    passo = _passo(max(maior, -menor))
    topo_escala = -(-maior // passo) * passo
    fundo_escala = (menor // passo) * passo
    amplitude = (topo_escala - fundo_escala) or 1
    util = COL_ALTURA - COL_TOPO - COL_BASE
    faixa = (COL_LARGURA - COL_ESQUERDA - COL_DIREITA) / max(1, len(grupos))

    def y(v):
        return COL_TOPO + (topo_escala - v) * util / amplitude

    partes = []
    for linha in range(fundo_escala, topo_escala + 1, passo):
        partes.append(f'<line class="{"eixo" if linha == 0 else "grade"}" x1="{COL_ESQUERDA}" y1="{y(linha):.1f}" '
                      f'x2="{COL_LARGURA - COL_DIREITA}" y2="{y(linha):.1f}"/>'
                      f'<text class="escala" x="{COL_ESQUERDA - 8}" y="{y(linha) + 7:.1f}" text-anchor="end">'
                      f'{esc(abreviado(linha).replace("R$ ", "") if linha else "0")}</text>')
    largura_col = faixa * 0.72 / max(1, len(series))
    for i, g in enumerate(grupos):
        x0 = COL_ESQUERDA + i * faixa + faixa * 0.14
        centro = COL_ESQUERDA + i * faixa + faixa / 2
        formas = []
        sem_dado = all(v is None for v in g["valores"])
        if sem_dado:                                     # the whole cut-off without data: one gap for the group
            dica = f"<title>{esc('; '.join(g['titulos']))}</title>"
            formas.append(f'<g>{dica}<rect class="lacuna" x="{x0 + 1:.1f}" y="{COL_TOPO}" '
                          f'width="{largura_col * len(series) - 2:.1f}" height="{util}"/></g>'
                          f'<text class="rotulo-lacuna" x="{centro:.1f}" y="{COL_TOPO + util / 2:.1f}" '
                          'text-anchor="middle">sem dado</text>')
        for j, (v, (_, classe)) in enumerate(zip(g["valores"], series)):
            x = x0 + j * largura_col
            dica = f"<title>{esc(g['titulos'][j])}</title>"
            if sem_dado:
                break
            if v is None:
                formas.append(f'<g>{dica}<rect class="lacuna" x="{x + 1:.1f}" y="{COL_TOPO}" '
                              f'width="{largura_col - 2:.1f}" height="{util}"/></g>')
            elif v == 0:
                formas.append(f'<g>{dica}<line class="zero" x1="{x:.1f}" y1="{y(0):.1f}" x2="{x + largura_col:.1f}" '
                              f'y2="{y(0):.1f}"/></g>')
            else:
                a, b = sorted((y(v), y(0)))
                formas.append(f'<g>{dica}<rect class="coluna {esc(classe)}" x="{x + 1:.1f}" y="{a:.1f}" '
                              f'width="{largura_col - 2:.1f}" height="{max(b - a, 1):.1f}"/></g>')
        formas.append(f'<text class="rotulo-corte" x="{centro:.1f}" y="{COL_ALTURA - COL_BASE + 30}" '
                      f'text-anchor="middle">{esc(g["rotulo"])}</text>')
        partes.append(f'<a href="{esc(g["href"])}" class="grupo-colunas">{"".join(formas)}</a>' if g.get("href")
                      else f'<g class="grupo-colunas">{"".join(formas)}</g>')
    legenda = "".join(f'<li><span class="amostra {esc(classe)}" aria-hidden="true"></span>{esc(nome)}</li>'
                      for nome, classe in series)
    return (f'<figure class="colunas"><ul class="legenda legenda-series">{legenda}</ul>'
            f'<svg viewBox="0 0 {COL_LARGURA} {COL_ALTURA}" role="img" aria-labelledby="{esc(ident)}-t {esc(ident)}-d">'
            f'<title id="{esc(ident)}-t">{esc(titulo)}</title><desc id="{esc(ident)}-d">{esc(descricao)}</desc>'
            + "".join(partes) + "</svg></figure>")
