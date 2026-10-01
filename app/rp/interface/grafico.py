"""Grafico de barras em SVG gerado no servidor (etapa05/CONTRATO_ANALITICO.md secao 7).

* Sem JavaScript e sem recurso externo: o <svg> faz parte do HTML. Nada de atributo `style` nem <style> (a CSP
  `style-src 'self'` os bloquearia): so atributos de geometria (x, y, width, height) e classes, com as cores em
  estilo.css.
* Apresentacao, nao calculo: os valores chegam prontos da camada painel. Aqui so se converte valor em pixels
  (escala), sem nenhuma soma ou diferenca de valores monetarios.
* Ponto sem valor e LACUNA (retangulo tracejado e o texto "sem dado"), nunca uma barra de altura zero. Zero
  verdadeiro e uma linha na base com o rotulo "0".
* Cada barra e um link (href interno, comecando por "/") para a tela do corte, onde esta a proveniencia; a tabela
  de valores exatos acompanha sempre o grafico e e a fonte da verdade.
"""
from .formato import esc

LARGURA, ALTURA = 720, 340
MARGEM_X, TOPO, BASE = 20, 20, 64          # BASE: espaco para os rotulos dos cortes


def barras(ident, titulo, descricao, pontos):
    """pontos: [{"rotulo": "31/01", "valor_c": int ou None, "titulo": texto do ponto, "href": "/..."}].
    Devolve o <figure> com o SVG; texto do titulo e da descricao vao em <title>/<desc> (leitor de tela)."""
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
        if v is None:
            forma = (f'<rect class="lacuna" x="{x:.1f}" y="{TOPO}" width="{largura_barra:.1f}" '
                     f'height="{altura_util}"/>'
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
