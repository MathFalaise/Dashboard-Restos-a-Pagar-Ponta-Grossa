"""Series across fiscal years (/historico)."""
from .. import formato as fm, grafico
from ..formato import esc
from .estrutura import _entidades_do_catalogo, erro, _quando, _situacao_curta

HISTORICO_COLUNAS = [("inscricao_total", "Inscrição (abertura)", "proc + aproc"),
                     ("pagamentos", "Pagamentos (até o corte)", "pagoProc + pagoAProc"),
                     ("cancelamentos", "Cancelamentos (até o corte)", "canceladoAProc + canceladoProc"),
                     ("saldo_total", "Saldo no corte (S1)", "S1 v1")]


def historico(p, q):
    """Series by fiscal year (sub-stage 05.3). Values, differences and checks come ready from the panel layer."""
    em = q.data("em")
    entidade = q.inteiro("entidade", 1, 10 ** 6)
    r = p.serie_entre_exercicios(entidade, em)
    pontos = r["exercicios"]
    if not pontos:
        return erro("Sem dados processados", "Nenhum exercício com coleta.")
    escopo = f"entidade {entidade}" if entidade is not None else "Município"
    sel = {"em": em, "entidade": entidade}
    titulo = (f"Série entre exercícios {pontos[0]['exercicio']}–{pontos[-1]['exercicio']} — {escopo} "
              f"({_quando(sel)})")
    lista = fm.opcoes([(e, f"{e} — {n}") for e, n in _entidades_do_catalogo(p)], entidade if entidade else "")
    formulario = ('<form class="filtros" method="get" action="/historico">'
                  '<label>Entidade <select name="entidade"><option value="">Município (entidades do catálogo '
                  f'oficial)</option>{lista}</select></label>'
                  f'<label>Como estava em (opcional) <input type="date" name="em" value="{esc(em or "")}"></label>'
                  '<button type="submit">Consultar</button></form>')
    corpo = [f"<h1>{esc(titulo)}</h1>", formulario,
             f'<p class="aviso" id="aviso-historico">{esc(r["nota"])}</p>',
             '<p class="nota">Cada exercício aparece num único corte, o mesmo para todos os escopos: 31/12 quando o '
             "Município está completo nele; senão, o último corte com o Município completo (exercício em aberto). "
             "Exercício ou escopo sem valor aparece como lacuna, com o motivo, nunca como zero.</p>"]
    pares = {ex: n for ex, n in r["pares_espelhados_por_exercicio"].items() if n}
    if pares:
        texto = ", ".join(f"{fm.inteiro(n)} em {ex}" for ex, n in sorted(pares.items()))
        corpo.append(f'<p class="aviso" id="aviso-pares">Este escopo envolve as entidades 1 e 15, com registros '
                     f"espelhados (cópias 24xxxxx): {esc(texto)}. Os dois lados continuam nos valores, como a API os "
                     "devolve; a natureza das cópias não está determinada.</p>")
    if any(x["tem_valor"] for x in pontos):
        barras = [{"rotulo": str(x["exercicio"]),
                   "valor_c": x["valores"]["saldo_total"]["valor_c"] if x["tem_valor"] else None,
                   "titulo": (f"{x['exercicio']}: " + (fm.moeda(x["valores"]["saldo_total"]["valor_c"]) +
                                                      f" (corte {fm.data_br(x['data_final'])})" if x["tem_valor"] else
                                                      f"sem dado — {x['situacao']['texto']}")),
                   "href": fm.url("/resumo", exercicio=x["exercicio"], data_final=x["data_final"], entidade=entidade, em=em)
                   if x["data_final"] else fm.url("/historico", entidade=entidade, em=em)} for x in pontos]
        corpo.append('<section class="grupo"><h2>Saldo de RP no corte representativo (S1)</h2>'
                     + grafico.barras("graf-hist", f"Saldo de RP (S1) por exercício — {escopo}",
                                      "Uma barra por exercício, no corte representativo; exercício sem valor aparece "
                                      "como lacuna tracejada.", barras)
                     + "</section>")
    corpo.append(_tabela_historico(pontos, sel))
    corpo.append(_tabela_fechamento_abertura(r["fechamento_abertura"]))
    return titulo, "".join(corpo)


def _tabela_historico(pontos, sel):
    linhas = []
    for x in pontos:
        ex = x["exercicio"]
        corte = (fm.link("/resumo", fm.data_br(x["data_final"]), exercicio=ex, data_final=x["data_final"],
                         entidade=sel["entidade"], em=sel["em"]) if x["data_final"] else "—")
        situacao = _situacao_curta(x["situacao"]["texto"]) + "".join(f"; {rot}" for rot in x["rotulos"])
        sit = f'<span title="{esc(x["situacao"]["texto"])}">{esc(situacao)}</span>'
        if x["tem_valor"]:
            pv = x["valores"]["saldo_total"]["proveniencia"]
            snaps = " ".join(f"<code>{esc(u)}</code>" for u in pv["snapshots"]) or "—"
            origem = (f'<details class="origem"><summary>origem</summary>Snapshots: {snaps}. Derivação '
                      f'{esc(pv["derivacao_id"])} (hash <code>{esc(pv["derivacao_hash"][:16])}…</code>).</details>')
            linhas.append([esc(ex), corte, f'<span id="ret-{esc(ex)}">{esc(x["retrato"]["texto"])}</span>', sit]
                          + [fm.valor(x["valores"][k]["valor_c"], f"hist-{ex}-{k}") for k, _, _ in HISTORICO_COLUNAS]
                          + [origem])
        else:
            linhas.append([esc(ex), corte, "—", sit,
                           f'<td colspan="{len(HISTORICO_COLUNAS)}" class="sem-valor" id="hist-lacuna-{esc(ex)}">'
                           f'sem valor — {esc(x["motivo_indisponivel"] or x["situacao"]["texto"])}</td>', "—"])
    return ('<section class="grupo"><h2>Valores por exercício</h2>'
            + fm.selo("elotech", "derivado", [{"codigo": "S1", "versao": 1, "situacao": "operacional"}],
                      "indicadores homologados no corte representativo de cada exercício")
            + fm.tabela([("Exercício", None), ("Corte", "corte representativo; abre o resumo"),
                         ("Retrato", "estado atual da base para o corte, na data da coleta"), ("Situação", None)]
                        + [(rot, dica) for _, rot, dica in HISTORICO_COLUNAS] + [("Origem", None)], linhas,
                        "tabela historico")
            + "</section>")


def _tabela_fechamento_abertura(itens):
    linhas = []
    for f in itens:
        de = f["de"]
        rotulo = esc(f"{de} → {f['para']}")
        mudancas = "; ".join(t for t in (
            f"entram: {', '.join(map(str, f['entidades_que_entram']))}" if f["entidades_que_entram"] else "",
            f"saem: {', '.join(map(str, f['entidades_que_saem']))}" if f["entidades_que_saem"] else "") if t) or "—"
        c = f["continuidade"]
        cont = (f'<span id="cont-{esc(de)}">{fm.inteiro(c["verificados"])} verificados, {fm.inteiro(c["falhas"])} '
                f"falhas</span>" if c["linhas"] else "—")
        if f["motivo_indisponivel"]:
            linhas.append([rotulo, f'<td colspan="3" class="sem-valor" id="fa-lacuna-{esc(de)}">'
                                   f'{esc(f["motivo_indisponivel"])}</td>', esc(mudancas), cont])
        else:
            linhas.append([rotulo, fm.valor(f["s1_de_c"], f"fa-{de}-s1"), fm.valor(f["a_mais_f_para_c"], f"fa-{de}-af"),
                           fm.valor(f["diferenca_c"], f"fa-{de}-dif"), esc(mudancas), cont])
    if not linhas:
        return ""
    return ('<section class="grupo"><h2>Fechamento de um exercício × abertura do seguinte</h2>'
            + fm.selo("elotech", "diferenca", [{"codigo": "S1", "versao": 1, "situacao": "operacional"},
                                              {"codigo": "FAIXA", "versao": 1, "situacao": "operacional"}],
                      "abertura de A+1 (faixas 'a' e 'f') − saldo S1 de A")
            + '<p class="nota">O saldo que fecha A (S1) deveria reaparecer, em A+1, como RP inscritos em exercícios '
              "anteriores a A: a composição dos registros da API segundo a regra FAIXA v1, faixas 'a' (processados) e "
              "'f' (não processados). A inscrição total de A+1 não serve para essa comparação, porque inclui os "
              "empenhos do próprio ano A. Diferença diferente de zero é mostrada como diferença, não como erro. No "
              "Município, a comparação só é feita se as entidades que entram ou saem do catálogo não tiverem "
              "registros. A continuidade é a verificação ANOM-CONT v1 gravada pela derivação, registro a registro.</p>"
            + fm.tabela([("Exercícios", None), ("Saldo S1 no fechamento de A", None),
                         ("Abertura de A+1: faixas 'a' + 'f'", "inscritos em exercícios anteriores a A (FAIXA v1)"),
                         ("Diferença", "abertura de A+1 − S1 de A"), ("Entidades que entram ou saem", None),
                         ("Continuidade (derivação)", "ANOM-CONT v1")], linhas)
            + "</section>")
