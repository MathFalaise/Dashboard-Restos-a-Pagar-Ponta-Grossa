"""Onde conferir, no Portal da Transparencia de Ponta Grossa (Oxy/Elotech), o valor que a interface mostra.

Tres caminhos no portal, com condicoes diferentes (conferido no portal em 06/10/2026, versao 3.128.0):
  * integra: a API do proprio portal (/portaltransparencia-api/empenhos/restos-a-pagar), o mesmo endereco que o coletor
    consulta, com o corte (dataFinal) e, para um empenho, os filtros empenho/anoempenho. E o dado exato do corte (JSON),
    mas como esta HOJE na fonte: lancamento com data anterior ao corte, feito depois da coleta, muda o resultado.
  * tela "Consulta em Restos a Pagar" (/{entidade}/restos-a-pagar): o exercicio e escolhido no topo do portal e a busca
    no formulario (nada disso vai no endereco). Mostra sempre o exercicio inteiro como esta hoje (equivale ao corte
    31/12), separado em Processados e Nao Processados, sem totais, sem retencao e sem estorno.
  * detalhe do empenho (/{entidade}/empenhos/detalhe): o empenho exato, com a aba Movimentacao (lancamentos com data),
    que explica o valor em qualquer corte.
Montante (soma de registros) nao existe no portal: e a soma do campo em todas as paginas da integra de cada entidade.
RREO: o PDF tem endereco direto; a pagina do Anexo VII (grupo 1, subgrupo 15) usa o exercicio escolhido no topo.
So ha link para o dominio oficial, marcado rel="external": a interface continua sem nenhum recurso externo carregado.
"""
from urllib.parse import urlencode

from .formato import esc

DOMINIO = "https://servicos.pontagrossa.pr.gov.br"
SITE = f"{DOMINIO}/portaltransparencia"
API = f"{DOMINIO}/portaltransparencia-api"
TAMANHO_PAGINA = 2000                       # maior pagina que a API devolve (contrato observado)
ORDEM = ("anoempenho,asc", "empenho,asc")   # a mesma ordem que o coletor pede
GRUPO_LRF, SUBGRUPO_ANEXO_VII = 1, 15

# campo da API -> (aba, coluna) na tela "Consulta em Restos a Pagar" (conferido empenho a empenho na prova real)
TELA = {
    "proc": ("Processados", "Valor Inscrito"),
    "canceladoProc": ("Processados", "Valor Cancelado"),
    "pagoProc": ("Processados", "Valor Pago"),
    "aproc": ("Não Processados", "Valor Inscrito"),
    "liquidado": ("Não Processados", "Valor Liquidado"),
    "canceladoAProc": ("Não Processados", "Valor Cancelado"),
    "pagoAProc": ("Não Processados", "Valor Pago"),
}


def link(url, texto):
    return f'<a href="{esc(url)}" rel="external noopener noreferrer">{esc(texto)}</a>'


def url_integra(entidade, exercicio, data_final, pagina=0, empenho=None, anoempenho=None):
    """Listagem de RP da entidade de 01/01 ate o corte, como o coletor pede (ou so um empenho, com os filtros)."""
    params = [("entidade", entidade), ("exercicio", exercicio), ("dataInicial", f"{exercicio}-01-01"),
              ("dataFinal", data_final)]
    if empenho is not None:
        params += [("empenho", empenho), ("anoempenho", anoempenho)]
    params += [("size", TAMANHO_PAGINA)] + [("sort", o) for o in ORDEM] + [("page", pagina)]
    return f"{API}/empenhos/restos-a-pagar?{urlencode(params)}"


def url_consulta(entidade):
    return f"{SITE}/{int(entidade)}/restos-a-pagar"


def url_empenho(entidade, anoempenho, empenho):
    """Detalhe do empenho no portal: `exercicio` aqui e o ano do EMPENHO (anoempenho), como o proprio portal monta."""
    e = int(entidade)
    return (f"{SITE}/{e}/empenhos/detalhe?search=id.entidade=={e}&entidade={e}&exercicio={int(anoempenho)}"
            f"&empenho={int(empenho)}")


def url_pdf(id_arquivo):
    return f"{API}/api/files/arquivo/{int(id_arquivo)}"


def url_publicacoes_rreo(entidade=1):
    return f"{SITE}/{int(entidade)}/publicacoes/{GRUPO_LRF}/{SUBGRUPO_ANEXO_VII}"


def paginas(registros):
    return max(1, -(-int(registros or 0) // TAMANHO_PAGINA))


def _lista_paginas(urls):
    if len(urls) == 1:
        return link(urls[0], "íntegra no corte")
    return "íntegra no corte, páginas " + " · ".join(link(u, str(i + 1)) for i, u in enumerate(urls))


def campos_na_tela(campos):
    """Onde cada campo da API usado no valor aparece no portal."""
    itens = []
    for c in campos:
        aba_col = TELA.get(c["campo_api"])
        tela = (f"na tela de consulta: aba {aba_col[0]}, coluna “{aba_col[1]}”" if aba_col
                else "não aparece na tela de consulta: só na íntegra")
        itens.append(f"<li>{esc(c['rotulo'])}: campo <code>{esc(c['campo_api'])}</code> da íntegra; {esc(tela)}</li>")
    return f"<ul>{''.join(itens)}</ul>" if itens else ""


def como_conferir_montante(v):
    """Bloco "Onde conferir no Portal" de um cartao de indicador (montante): campos, formula e o caminho."""
    if v["id"] == "registros":
        corpo = ("<p>Número de registros: campo <code>totalElements</code> da íntegra de cada entidade, somado. "
                 "Na tela de consulta, os itens das abas Processados e Não Processados.</p>")
    else:
        corpo = (f"<p>O portal não mostra este total. Cálculo: {esc(v['formula'])}, sobre todos os empenhos do "
                 "corte das entidades que entram no total.</p>" + campos_na_tela(v["campos"]))
    return (corpo + '<p>Os links da íntegra de cada entidade e as condições estão em '
            '<a href="#onde-conferir">Onde conferir no Portal</a>.</p>')


def secao_onde_conferir(entidades, exercicio, data_final, coleta):
    """Secao da pagina com a integra de cada entidade que entra no total do corte e as condicoes de cada caminho."""
    itens = []
    for e in entidades:
        if not e.get("entra_no_total") or not e.get("snapshot"):
            continue
        n = e["snapshot"].get("registros")
        urls = [url_integra(e["entidade"], exercicio, data_final, p) for p in range(paginas(n))]
        qtd = "sem RP (0 registros)" if not n else f"{n} registros"
        itens.append(f"<li>Entidade {esc(e['entidade'])} — {esc(e.get('nome') or '')} ({esc(qtd)}): "
                     f"{_lista_paginas(urls)} · {link(url_consulta(e['entidade']), 'tela de consulta')}</li>")
    if not itens:
        return ""
    return ('<section class="grupo" id="onde-conferir"><h2>Onde conferir no Portal</h2>'
            f"<ul>{''.join(itens)}</ul>" + condicoes(data_final, coleta, montante=True) + "</section>")


def condicoes(data_final, coleta, montante=False):
    """As condicoes de cada caminho, que nao sao as mesmas."""
    partes = []
    if montante:
        partes.append("<li><strong>Montante:</strong> o portal não soma. Some o campo em todas as páginas da íntegra "
                      "de todas as entidades listadas; o total do Município é a soma delas.</li>")
    partes += [
        f"<li><strong>Íntegra:</strong> é o dado do corte ({esc(_br(data_final))}) consultado hoje na API do portal. "
        f"Um lançamento com data até o corte feito depois da coleta ({esc(coleta)}) muda o resultado; o que foi "
        "coletado fica no registro técnico.</li>",
        "<li><strong>Tela de consulta:</strong> escolha o exercício no topo do portal; ela mostra o exercício inteiro "
        "como está hoje (equivale ao corte 31/12), separado em Processados e Não Processados, sem totais e sem "
        "retenção nem estorno.</li>",
    ]
    return f'<ul class="nota">{"".join(partes)}</ul>'


def como_conferir_registro(s, chave, pv=None):
    """Um empenho: a integra filtrada no corte, a pagina da integra da coleta, o detalhe e a tela de consulta."""
    ex, df = s["exercicio"], s["data_final"]
    e, ano, emp = chave["entidade"], chave["anoempenho"], chave["empenho"]
    itens = [f"<li>{link(url_integra(e, ex, df, 0, emp, ano), 'Este empenho no corte')} (íntegra filtrada)</li>"]
    if pv and pv.get("resposta_url", "").startswith(API):
        itens.append(f"<li>{link(pv['resposta_url'], 'Página da íntegra onde ele estava na coleta')} (página "
                     f"{esc(int(pv['resposta_ordem']) + 1)}, posição {esc(int(pv['indice_no_content']) + 1)})</li>")
    itens += [f"<li>{link(url_empenho(e, ano, emp), 'Detalhe do empenho no portal')}: valores do empenho e aba "
              "Movimentação, com a data de cada lançamento</li>",
              f"<li>{link(url_consulta(e), 'Tela de consulta')}: exercício {esc(ex)} no topo, Empenho {esc(emp)}, "
              f"Ano {esc(ano)}, Pesquisar; aba Processados ou Não Processados</li>"]
    return f"<ul>{''.join(itens)}</ul>"


def como_conferir_pdf(pdf, entidade=1):
    return (f"{link(url_pdf(pdf['id_arquivo']), 'PDF no portal')} · "
            f"{link(url_publicacoes_rreo(entidade), 'Publicações do Anexo VII')} (escolha o exercício no topo; "
            "há a versão da entidade e a “Consolidado”)")


def _br(d):
    a, m, dia = str(d)[:10].split("-")
    return f"{dia}/{m}/{a}"
