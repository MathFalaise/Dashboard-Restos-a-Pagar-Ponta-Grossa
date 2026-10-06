"""Bar chart as SVG generated on the server (docs/stages/05-analysis/ANALYTICAL_CONTRACT.md section 7).

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
from .formato import esc

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
