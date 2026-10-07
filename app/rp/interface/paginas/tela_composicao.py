"""Balance composition (/composicao)."""
from ...painel.consulta import COMPOSICOES, ROTULO_COMPOSICAO, TEXTO_FAIXA
from .. import formato as fm
from ..formato import esc
from .estrutura import (_avisos, _entidades_do_catalogo, erro, _formulario, _origem_conjunto, _quando, _retrato,
                        _selecao, SemDados)

TOTAL_NA_LISTA = {"inscricao_processada": "Processado (inscrito)", "inscricao_nao_processada": "Não processado (inscrito)"}


def composicao(p, q):
    """Composition of the cut-off's inscription and balance (sub-stage 05.4). Groups, totals and closings come ready
    from the panel layer; a dimension that does not add up to the cut-off total is not shown."""
    try:
        sel = _selecao(p, q)
    except SemDados as e:
        return erro("Sem dados processados", str(e))
    dim = q.escolha("dimensao", COMPOSICOES) or "categoria"
    r = p.composicao(sel["exercicio"], sel["data_final"], sel["entidade"], sel["em"])
    escopo = f"entidade {sel['entidade']}" if sel["entidade"] is not None else "Município"
    titulo = (f"Composição do saldo — {escopo}, exercício {sel['exercicio']}, corte {fm.data_br(sel['data_final'])} "
              f"({_quando(sel)})")
    extra = (f'<label>Dimensão <select name="dimensao">'
             f'{fm.opcoes([(d, ROTULO_COMPOSICAO[d]) for d in COMPOSICOES], dim)}</select></label>')
    corpo = [f"<h1>{esc(titulo)}</h1>", _avisos(sel["avisos"]),
             _formulario("/composicao", sel, _entidades_do_catalogo(p), extra), _retrato(r["retrato"])]
    if not r["disponivel"]:
        corpo.append('<section class="indisponivel" id="indisponivel"><h2>Composição indisponível para este recorte</h2>'
                     f'<p>{esc(r["situacao"]["texto"])}.</p><p>Motivo: {esc(r["motivo_indisponivel"])}.</p><p>Nenhum grupo é '
                     "mostrado: ausência de dado não é zero.</p></section>")
        return titulo, "".join(corpo)
    if r["pares_espelhados_no_corte"]:
        corpo.append(f'<p class="aviso" id="aviso-pares">Este escopo envolve as entidades 1 e 15, com '
                     f'{fm.inteiro(r["pares_espelhados_no_corte"])} registros espelhados (cópias 24xxxxx) neste corte. '
                     "Os dois lados continuam em todos os grupos, como a API os devolve; a natureza das cópias não está "
                     f"determinada. {fm.link('/pares', 'Ver os pares', exercicio=sel['exercicio'], data_final=sel['data_final'])}</p>")
    navegacao = " · ".join(
        f"<strong>{esc(ROTULO_COMPOSICAO[d])}</strong>" if d == dim else
        fm.link("/composicao", ROTULO_COMPOSICAO[d], exercicio=sel["exercicio"], data_final=sel["data_final"],
                entidade=sel["entidade"], em=sel["em"], dimensao=d)
        for d in COMPOSICOES)
    t = r["total"]
    corpo += [f'<p class="dimensoes" id="dimensoes">Dimensões: {navegacao}</p>',
              '<section class="grupo"><h2>Total do corte</h2>'
              + fm.selo("elotech", "derivado", [{"codigo": "S1", "versao": 1, "situacao": "operacional"}],
                        "indicadores homologados do corte")
              + '<div class="cartoes compactos">'
              + "".join(f'<div class="indicador"><p class="rotulo">{esc(rot)}</p><p class="numero">{html}</p></div>'
                        for rot, html in (("Empenhos (registros)", fm.contagem(t["registros"], "comp-total-reg")),
                                          ("Inscrição (abertura)", fm.valor(t["inscricao_total_c"], "comp-total-insc")),
                                          ("Saldo no corte (S1)", fm.valor(t["saldo_total_c"], "comp-total-s1"))))
              + "</div></section>",
              _secao_dimensao(r["dimensoes"][dim], r["total"], sel),
              _tabela_fechamentos(r, sel),
              _origem_conjunto(r["proveniencia"])]
    return titulo, "".join(corpo)


def _lista_do_grupo(g, sel):
    if g["registros"] == 0:
        return "nenhum registro"
    if not g["filtro"]:
        return f'<span class="sem-valor">{esc(g.get("motivo_sem_lista") or "sem lista exata")}</span>'
    return fm.link("/empenhos", f"ver {fm.inteiro(g['registros'])} empenhos", exercicio=sel["exercicio"],
                   data_final=sel["data_final"], entidade=sel["entidade"], em=sel["em"], **g["filtro"])


def _secao_dimensao(x, total, sel):
    d = x["dimensao"]
    cab = (f'<section class="grupo" id="composicao-{esc(d)}"><h2>{esc(x["rotulo"])}</h2>'
           + fm.selo("elotech", "derivado", x["regras"], x["consulta"]))
    if not x["exibida"]:
        return (cab + f'<div class="indisponivel" id="comp-nao-exibida"><p>Dimensão não exibida: '
                f'{esc(x["motivo_nao_exibida"])}.</p></div></section>')
    f = x["fechamento"]
    if d == "faixa":
        linhas = [[esc(g["rotulo"]), fm.contagem(g["registros"], f"comp-faixa-{g['ident']}-reg"),
                   fm.valor(g["inscricao_total_c"], f"comp-faixa-{g['ident']}-insc"), _lista_do_grupo(g, sel)]
                  for g in x["grupos"]]
        linhas += [["<strong>Inscrição total do corte</strong>", "—", fm.valor(total["inscricao_total_c"], "comp-faixa-total-insc"), "—"],
                   ["Soma das faixas − inscrição total", "—",
                    fm.valor(f["inscricao_total_c"]["diferenca"], "comp-faixa-fech-insc"), "—"]]
        return (cab + f'<p class="nota">{esc(TEXTO_FAIXA[0].upper() + TEXTO_FAIXA[1:])}. Cada registro tem uma parte '
                "processada (proc) e uma não processada (aproc); cada parte positiva entra na faixa pela regra: faixas a e "
                "f para empenhos de anos anteriores a exercício − 1, faixas b e g para empenhos de exercício − 1. A soma "
                "dos valores das quatro faixas é a inscrição total do corte. A contagem de registros é por parte e não é "
                "somada: um registro com as duas partes aparece em duas faixas. Na lista de empenhos de uma faixa, o valor "
                f"da faixa é o total “{TOTAL_NA_LISTA['inscricao_processada']}” (faixas a e b) ou "
                f"“{TOTAL_NA_LISTA['inscricao_nao_processada']}” (faixas f e g).</p>"
                + fm.tabela([("Faixa", None), ("Registros com esta parte", "não somados"),
                             ("Valor inscrito da parte", "proc ou aproc"), ("Empenhos", "lista filtrada pela faixa")],
                            linhas, "tabela composicao")
                + "</section>")
    linhas = [[esc(g["rotulo"]), fm.contagem(g["registros"], f"comp-{d}-{g['ident']}-reg"),
               fm.valor(g["inscricao_total_c"], f"comp-{d}-{g['ident']}-insc"),
               fm.valor(g["saldo_total_c"], f"comp-{d}-{g['ident']}-s1"), _lista_do_grupo(g, sel)] for g in x["grupos"]]
    linhas += [["<strong>Total do corte</strong>", fm.contagem(total["registros"], f"comp-{d}-total-reg"),
                fm.valor(total["inscricao_total_c"], f"comp-{d}-total-insc"),
                fm.valor(total["saldo_total_c"], f"comp-{d}-total-s1"), "—"],
               ["Soma dos grupos − total do corte", fm.contagem(f["registros"]["diferenca"], f"comp-{d}-fech-reg"),
                fm.valor(f["inscricao_total_c"]["diferenca"], f"comp-{d}-fech-insc"),
                fm.valor(f["saldo_total_c"]["diferenca"], f"comp-{d}-fech-s1"), "—"]]
    nota = ("Grupo sem registros aparece com zero (zero do grupo, não ausência de dado)." if d in ("categoria", "tipo_credor")
            else "“Sem classificação” reúne os registros em que a API não devolveu o campo; aparece sempre, mesmo com "
                 "zero registros.")
    if d == "tipo_credor":
        nota += " Só o tipo do credor: nome e documento não aparecem em nenhum agrupamento."
    return (cab + f'<p class="nota">A soma dos grupos é igual ao total do corte em registros, inscrição e saldo. {esc(nota)}'
            "</p>"
            + fm.tabela([("Grupo", None), ("Registros", None), ("Inscrição (abertura)", "proc + aproc"),
                         ("Saldo no corte (S1)", "S1 v1"), ("Empenhos", "lista filtrada pelo grupo")], linhas,
                        "tabela composicao")
            + "</section>")


def _tabela_fechamentos(r, sel):
    linhas = []
    for d, x in r["dimensoes"].items():
        f = x["fechamento"]
        nome = fm.link("/composicao", x["rotulo"], exercicio=sel["exercicio"], data_final=sel["data_final"],
                       entidade=sel["entidade"], em=sel["em"], dimensao=d)
        linhas.append([nome, "sim" if x["exibida"] else '<strong>não</strong> (não fecha)',
                       fm.contagem(f["registros"]["diferenca"], f"fech-{d}-reg") if "registros" in f else "não se aplica",
                       fm.valor(f["inscricao_total_c"]["diferenca"], f"fech-{d}-insc"),
                       fm.valor(f["saldo_total_c"]["diferenca"], f"fech-{d}-s1") if "saldo_total_c" in f else "não se aplica"])
    return ('<section class="grupo" id="fechamentos"><h2>Fechamento de cada dimensão com o total do corte</h2>'
            + fm.selo("elotech", "diferenca", None, "soma dos grupos − total do corte; exibida só com 0 em todas as medidas")
            + '<p class="nota">Cada dimensão fecha sozinha. Uma dimensão que não fecha não é exibida até a causa ser '
              "explicada, mesmo que as outras fechem. Na faixa só o valor fecha: a contagem por faixa não é somada.</p>"
            + fm.tabela([("Dimensão", None), ("Exibida", None), ("Registros", "soma − total"),
                         ("Inscrição", "soma − total"), ("Saldo (S1)", "soma − total")], linhas)
            + "</section>")
