"""HTML formatting for the interface.

* Every text coming from the database goes through `esc` (HTML escaping, quotes included): a creditor name, a
  funding source description or a PDF label never becomes markup.
* Money arrives in cents (integer) and is formatted with integer arithmetic: no float, no rounding. The exact value
  in cents goes along, machine-readable, in the <data value="..."> element.
* A missing value NEVER becomes "R$ 0,00": it shows up as explicit text (no value, with the reason).
"""
import html
from urllib.parse import urlencode

FONTE_CURTA = {"elotech": "API Elotech", "rreo": "RREO Anexo VII"}
NATUREZA = {
    "da_fonte": "dado da fonte",
    "publicado": "valor publicado",
    "derivado": "valor derivado",
    "analitico": "valor analítico (não oficial)",
    "diferenca": "diferença",
}
SITUACAO_REGRA = {"operacional": "operacional", "experimental": "experimental", "nao_recomendada": "não recomendada",
                  "supersedida": "supersedida", "aposentada": "aposentada", None: "sem decisão registrada"}


def esc(v):
    return html.escape("" if v is None else str(v), quote=True)


def moeda(c):
    """Cents (int) -> 'R$ 1.234.567,89' / '-R$ 12,30'. None -> None (the caller decides the absence text)."""
    if c is None:
        return None
    if isinstance(c, bool) or not isinstance(c, int):
        raise TypeError(f"valor monetario precisa ser inteiro em centavos: {c!r}")
    reais, centavos = divmod(abs(c), 100)
    return ("-" if c < 0 else "") + "R$ " + f"{reais:,}".replace(",", ".") + f",{centavos:02d}"


def inteiro(n):
    return None if n is None else f"{n:,}".replace(",", ".")


def valor(c, ident=None, ausencia="sem valor"):
    """<data> with the exact value in cents, or the absence text (never zero)."""
    if c is None:
        return f'<span class="sem-valor">{esc(ausencia)}</span>'
    atributo_id = f' id="{esc(ident)}"' if ident else ""
    classe = "valor negativo" if c < 0 else "valor"
    return f'<data class="{classe}"{atributo_id} value="{c}">{esc(moeda(c))}</data>'


UNIDADES_ABREVIADAS = ((10 ** 11, "bi"), (10 ** 8, "mi"), (10 ** 5, "mil"))     # in cents


def abreviado(c):
    """Cents (int) -> 'R$ 78,7 mi' / 'R$ 1,2 bi' / 'R$ 950,3 mil': one decimal, rounded half up with integer
    arithmetic, in the largest unit where the value shows as at least 1,0. Below that, the exact value."""
    if c is None:
        return None
    if isinstance(c, bool) or not isinstance(c, int):
        raise TypeError(f"valor monetario precisa ser inteiro em centavos: {c!r}")
    for unidade, nome in UNIDADES_ABREVIADAS:
        decimos = (abs(c) * 20 + unidade) // (2 * unidade)
        if decimos >= 10:
            return ("-" if c < 0 else "") + f"R$ {decimos // 10:,}".replace(",", ".") + f",{decimos % 10} {nome}"
    return moeda(c)


def valor_abreviado(c, ident=None, ausencia="sem valor"):
    """<data> with the exact value in cents (machine-readable and in the hint) and the abbreviated text."""
    if c is None:
        return f'<span class="sem-valor">{esc(ausencia)}</span>'
    atributo_id = f' id="{esc(ident)}"' if ident else ""
    classe = "valor negativo" if c < 0 else "valor"
    return f'<data class="{classe}"{atributo_id} value="{c}" title="{esc(moeda(c))}">{esc(abreviado(c))}</data>'


def percentual(decimos):
    """Tenths of a percentage point (int) -> '38,3%'. None -> None."""
    if decimos is None:
        return None
    return ("-" if decimos < 0 else "") + f"{abs(decimos) // 10},{abs(decimos) % 10}%"


def contagem(n, ident=None, ausencia="sem valor"):
    if n is None:
        return f'<span class="sem-valor">{esc(ausencia)}</span>'
    atributo_id = f' id="{esc(ident)}"' if ident else ""
    return f'<data class="contagem"{atributo_id} value="{n}">{esc(inteiro(n))}</data>'


def data_br(iso, com_hora=False):
    if not iso:
        return ""
    d = f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"
    return f"{d} {iso[11:16]}" if com_hora and len(iso) > 10 else d


def natureza(n):
    return f'<span class="natureza natureza-{esc(n)}">{esc(NATUREZA.get(n, n))}</span>'


def regras(lista):
    """[{'codigo','versao','situacao'}] -> 'S1 v1 (operacional)'."""
    return ", ".join(f"{esc(r['codigo'])} v{esc(r['versao'])} ({esc(SITUACAO_REGRA.get(r.get('situacao'), r.get('situacao')))})"
                     for r in lista) or "—"


def situacao_regra(codigo_versao, situacao, ressalva=None):
    """'RREO-COL v2' + situation -> text with the explicit label: experimental rule = ANALISE EXPERIMENTAL; not
    recommended = analise nao recomendada. Only an operational rule shows without a badge; one promoted without an
    independent check (decision D7) shows as "operacional com ressalva", with the reason."""
    if situacao == "experimental":
        return f'{esc(codigo_versao)} <span class="selo-analise">ANÁLISE EXPERIMENTAL</span>'
    if situacao == "nao_recomendada":
        return f'{esc(codigo_versao)} <span class="selo-analise">ANÁLISE — REGRA NÃO RECOMENDADA</span>'
    if situacao == "operacional" and ressalva:
        return f"{esc(codigo_versao)} (operacional com ressalva: {esc(ressalva)})"
    return f"{esc(codigo_versao)} ({esc(SITUACAO_REGRA.get(situacao, situacao))})"


def selo(fonte, nat, lista_regras=None, calculo=None):
    """'Fonte - Natureza - Regra' line that goes with every value. Without a rule, it shows the calculation (e.g. sum of proc)."""
    partes = [f'<span class="selo-fonte">Fonte: {esc(FONTE_CURTA.get(fonte, fonte))}</span>', f"Natureza: {natureza(nat)}"]
    if lista_regras:
        partes.append(f"Regra: {regras(lista_regras)}")
    elif calculo:
        partes.append(f"Cálculo: {esc(calculo)}")
    return '<p class="selo">' + " · ".join(partes) + "</p>"


def link(caminho, texto, **params):
    q = urlencode({k: v for k, v in params.items() if v is not None and v != ""})
    return f'<a href="{esc(caminho + ("?" + q if q else ""))}">{esc(texto)}</a>'


def url(caminho, **params):
    q = urlencode({k: v for k, v in params.items() if v is not None and v != ""})
    return caminho + ("?" + q if q else "")


def _th(texto, dica):
    atributo = f' title="{esc(dica)}"' if dica else ""
    return f'<th scope="col"{atributo}>{esc(texto)}</th>'


def tabela(cabecalho, linhas, classe="tabela"):
    """header: list of (text, hint or None); rows: lists of cells in ALREADY escaped HTML. A cell that already
    starts with '<td' (e.g. colspan) goes in as is."""
    th = "".join(_th(t, d) for t, d in cabecalho)
    corpo = "".join("<tr>" + "".join(c if c.startswith("<td") else f"<td>{c}</td>" for c in l) + "</tr>" for l in linhas)
    return f'<div class="rolagem"><table class="{esc(classe)}"><thead><tr>{th}</tr></thead><tbody>{corpo}</tbody></table></div>'


def lista_definicoes(pares):
    """[(term, already escaped HTML)] -> <dl>."""
    return "<dl>" + "".join(f"<dt>{esc(t)}</dt><dd>{d}</dd>" for t, d in pares) + "</dl>"


def opcoes(lista, selecionado):
    """[(value, label)] -> <option>s, marking the selected one."""
    return "".join(f'<option value="{esc(v)}"{" selected" if str(v) == str(selecionado) else ""}>{esc(r)}</option>'
                   for v, r in lista)
