"""Formatacao HTML da interface.

* Todo texto vindo do banco passa por `esc` (escape de HTML, inclusive aspas): nome de credor, descricao de
  fonte de recurso ou rotulo de PDF nunca viram marcacao.
* Dinheiro chega em centavos (inteiro) e e formatado com aritmetica inteira: nada de float, nada de
  arredondamento. O valor exato em centavos vai junto, legivel por maquina, no elemento <data value="...">.
* Ausencia de valor NUNCA vira "R$ 0,00": aparece como texto explicito (sem valor, com o motivo).
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
    """Centavos (int) -> 'R$ 1.234.567,89' / '-R$ 12,30'. None -> None (quem chama decide o texto de ausencia)."""
    if c is None:
        return None
    if isinstance(c, bool) or not isinstance(c, int):
        raise TypeError(f"valor monetario precisa ser inteiro em centavos: {c!r}")
    reais, centavos = divmod(abs(c), 100)
    return ("-" if c < 0 else "") + "R$ " + f"{reais:,}".replace(",", ".") + f",{centavos:02d}"


def inteiro(n):
    return None if n is None else f"{n:,}".replace(",", ".")


def valor(c, ident=None, ausencia="sem valor"):
    """<data> com o valor exato em centavos, ou o texto de ausencia (nunca zero)."""
    if c is None:
        return f'<span class="sem-valor">{esc(ausencia)}</span>'
    atributo_id = f' id="{esc(ident)}"' if ident else ""
    classe = "valor negativo" if c < 0 else "valor"
    return f'<data class="{classe}"{atributo_id} value="{c}">{esc(moeda(c))}</data>'


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
    """'RREO-COL v2' + situacao -> texto com o rotulo explicito: regra experimental = ANALISE EXPERIMENTAL; nao
    recomendada = analise nao recomendada. So regra operacional sai sem destaque; promovida sem conferencia
    independente (decisao D7) sai como "operacional com ressalva", com o motivo."""
    if situacao == "experimental":
        return f'{esc(codigo_versao)} <span class="selo-analise">ANÁLISE EXPERIMENTAL</span>'
    if situacao == "nao_recomendada":
        return f'{esc(codigo_versao)} <span class="selo-analise">ANÁLISE — REGRA NÃO RECOMENDADA</span>'
    if situacao == "operacional" and ressalva:
        return f"{esc(codigo_versao)} (operacional com ressalva: {esc(ressalva)})"
    return f"{esc(codigo_versao)} ({esc(SITUACAO_REGRA.get(situacao, situacao))})"


def selo(fonte, nat, lista_regras=None, calculo=None):
    """Linha 'Fonte - Natureza - Regra' que acompanha todo valor. Sem regra, mostra o calculo (ex.: soma de proc)."""
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
    """cabecalho: lista de (texto, dica ou None); linhas: listas de celulas em HTML JA escapado. Celula que ja
    comeca com '<td' (ex.: colspan) entra como esta."""
    th = "".join(_th(t, d) for t, d in cabecalho)
    corpo = "".join("<tr>" + "".join(c if c.startswith("<td") else f"<td>{c}</td>" for c in l) + "</tr>" for l in linhas)
    return f'<div class="rolagem"><table class="{esc(classe)}"><thead><tr>{th}</tr></thead><tbody>{corpo}</tbody></table></div>'


def lista_definicoes(pares):
    """[(termo, HTML ja escapado)] -> <dl>."""
    return "<dl>" + "".join(f"<dt>{esc(t)}</dt><dd>{d}</dd>" for t, d in pares) + "</dl>"


def opcoes(lista, selecionado):
    """[(valor, rotulo)] -> <option>s, marcando o selecionado."""
    return "".join(f'<option value="{esc(v)}"{" selected" if str(v) == str(selecionado) else ""}>{esc(r)}</option>'
                   for v, r in lista)
