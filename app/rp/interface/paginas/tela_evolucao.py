"""Evolution within the fiscal year (/evolucao)."""
from .. import formato as fm, grafico
from ..formato import esc
from .estrutura import _avisos, _entidades_do_catalogo, erro, _formulario, _quando, _selecao, SemDados, _situacao_curta

SERIE_COLUNAS = [("inscricao_total", "Inscrição (abertura)", "proc + aproc"),
                 ("pagamentos", "Pagamentos (acumulado)", "pagoProc + pagoAProc, de 01/01 até o corte"),
                 ("liquidacoes", "Liquidações (acumulado)", "liquidado, de 01/01 até o corte"),
                 ("cancelamentos", "Cancelamentos (acumulado)", "canceladoAProc + canceladoProc, de 01/01 até o corte"),
                 ("saldo_total", "Saldo no corte (S1)", "S1 v1")]


def evolucao(p, q):
    """Series of all cut-offs of the fiscal year (sub-stage 05.2). Values and differences come ready from the panel layer."""
    try:
        sel = _selecao(p, q)
    except SemDados as e:
        return erro("Sem dados processados", str(e))
    r = p.evolucao(sel["exercicio"], sel["entidade"], sel["em"])
    escopo = f"entidade {sel['entidade']}" if sel["entidade"] is not None else "Município"
    titulo = f"Evolução no exercício {sel['exercicio']} — {escopo} ({_quando(sel)})"
    corpo = [f"<h1>{esc(titulo)}</h1>", _avisos(sel["avisos"]),
             _formulario("/evolucao", sel, _entidades_do_catalogo(p), com_corte=False),
             f'<p class="nota">{esc(r["nota"])} Todos os cortes processados do exercício aparecem; corte sem valor '
             "para este escopo aparece como lacuna, com o motivo, e nunca como zero. A diferença só é calculada entre "
             "cortes vizinhos que tenham valor.</p>"]
    if r["pares_espelhados_no_exercicio"]:
        corpo.append(f'<p class="aviso" id="aviso-pares">Este escopo envolve as entidades 1 e 15, que têm '
                     f'{fm.inteiro(r["pares_espelhados_no_exercicio"])} registros espelhados (cópias 24xxxxx) neste '
                     "exercício. Os dois lados continuam nos valores, como a API os devolve; a natureza das cópias não "
                     f"está determinada. {fm.link('/pares', 'Ver os pares', exercicio=sel['exercicio'])}</p>")
    serie = r["serie"]
    if any(x["tem_valor"] for x in serie):
        pontos = [{"rotulo": fm.data_br(x["data_final"])[:5],
                   "valor_c": x["valores"]["saldo_total"]["valor_c"] if x["tem_valor"] else None,
                   "titulo": (f"{fm.data_br(x['data_final'])}: " + (fm.moeda(x["valores"]["saldo_total"]["valor_c"])
                                                                     if x["tem_valor"] else
                                                                     f"sem dado — {x['situacao']['texto']}")),
                   "href": fm.url("/resumo", exercicio=sel["exercicio"], data_final=x["data_final"], entidade=sel["entidade"],
                                  em=sel["em"])} for x in serie]
        corpo.append('<section class="grupo"><h2>Saldo de RP no corte (S1)</h2>'
                     + grafico.barras("graf-s1", f"Saldo de RP (S1) por corte — exercício {sel['exercicio']}, {escopo}",
                                      "Barras por corte; corte sem valor aparece como lacuna tracejada.", pontos)
                     + "</section>")
    corpo.append(_tabela_serie(serie, sel))
    corpo.append(_tabela_diferencas(serie, sel))
    return titulo, "".join(corpo)


def _celula_situacao(x):
    """Short form of the situation (before ':'), with the full text as a hint; the detailed reason is in the cell next
    to it. Labels (e.g. cut-off after the collection) always appear in full."""
    texto = _situacao_curta(x["situacao"]["texto"]) + "".join(f"; {rot}" for rot in x["rotulos"])
    return f'<span id="sit-{esc(x["data_final"])}" title="{esc(x["situacao"]["texto"])}">{esc(texto)}</span>'


def _tabela_serie(serie, sel):
    linhas = []
    for x in serie:
        df = x["data_final"]
        corte = fm.link("/resumo", fm.data_br(df), exercicio=sel["exercicio"], data_final=df, entidade=sel["entidade"],
                        em=sel["em"])
        if x["tem_valor"]:
            pv = x["valores"]["saldo_total"]["proveniencia"]
            snaps = " ".join(f"<code>{esc(u)}</code>" for u in pv["snapshots"]) or "—"
            origem = (f'<details class="origem"><summary>origem</summary>Snapshots: {snaps}. Derivação '
                      f'{esc(pv["derivacao_id"])} (hash <code>{esc(pv["derivacao_hash"][:16])}…</code>), normalização '
                      f'{esc(pv["normalizacao_id"])}.</details>')
            linhas.append([corte, _celula_situacao(x)]
                          + [fm.valor(x["valores"][k]["valor_c"], f"ser-{df}-{k}") for k, _, _ in SERIE_COLUNAS]
                          + [origem])
        else:
            linhas.append([corte, _celula_situacao(x),
                           f'<td colspan="{len(SERIE_COLUNAS)}" class="sem-valor" id="lacuna-{esc(df)}">sem valor — '
                           f'{esc(x["motivo_indisponivel"] or x["situacao"]["texto"])}</td>', "—"])
    return ('<section class="grupo"><h2>Valores por corte</h2>'
            + fm.selo("elotech", "derivado", [{"codigo": "S1", "versao": 1, "situacao": "operacional"}],
                      "indicadores homologados de cada corte")
            + fm.tabela([("Corte", "abre o resumo do corte"), ("Situação", None)]
                        + [(rot, dica) for _, rot, dica in SERIE_COLUNAS] + [("Origem", None)], linhas,
                        "tabela serie")
            + "</section>")


def _tabela_diferencas(serie, sel):
    linhas = []
    for x in serie[1:]:
        d = x["diferenca_para_o_anterior"]
        df = x["data_final"]
        texto = f"{fm.data_br(d['anterior'])} → {fm.data_br(df)}"
        if d["motivo_indisponivel"]:
            linhas.append([esc(texto), f'<td colspan="{len(SERIE_COLUNAS)}" class="sem-valor" id="dif-lacuna-{esc(df)}">'
                                       f'{esc(d["motivo_indisponivel"])}</td>'])
        else:
            rotulo = fm.link("/variacao", texto, exercicio=sel["exercicio"], anterior=d["anterior"], data_final=df,
                             entidade=sel["entidade"], em=sel["em"])
            linhas.append([rotulo] + [fm.valor(d["valores"][k], f"dif-{df}-{k}") for k, _, _ in SERIE_COLUNAS])
    if not linhas:
        return ""
    return ('<section class="grupo"><h2>Diferença para o corte anterior</h2>'
            + fm.selo("elotech", "diferenca", None, "posterior − anterior, só entre cortes vizinhos com valor")
            + '<p class="nota">Inscrição igual em todos os cortes dá diferença 0. Pagamentos, liquidações e '
              "cancelamentos são acumulados: a diferença é o movimento do intervalo. Cada intervalo leva à "
              "investigação da variação, empenho por empenho.</p>"
            + fm.tabela([("Cortes", "anterior → posterior")] + [(rot, None) for _, rot, _ in SERIE_COLUNAS], linhas)
            + "</section>")
