"""Overview screen (/): key numbers, pies and columns for a quick reading (stage 06, docs/stages/06-bi/SCOPE.md).

Every number comes ready from Painel.visao_geral (values, partitions already checked against their totals, shares
in tenths of a point). Here we only choose colors, labels and the reading sentence. Big values are abbreviated
(R$ 78,7 mi); the exact value is in the <data value> of each figure, in its hint and in the collapsed table of each
block. The technical screens stay one click away ("ver detalhes").
"""
from .. import formato as fm, grafico, portal as P
from ..formato import esc
from .estrutura import _avisos, _entidades_do_catalogo, erro, _formulario, _quando, _retrato, _selecao, SemDados

PALETA = ("c1", "c2", "c3", "c4", "c5", "c6", "c7", "c9")          # 8 colors: a top of 8 never repeats one
CLASSE_DEMAIS = "c8"
CORES_FIXAS = {"pago": "c3", "cancelado": "c8", "em_aberto": "c2", "a_liquidar": "c4", "liquidado_a_pagar": "c1"}
SERIE_EVOLUCAO = [("Saldo em aberto", "c2"), ("Pago desde 01/01", "c3")]
SERIE_EXERCICIOS = [("Inscrito na abertura", "c1"), ("Saldo no fim do exercício", "c2")]
NUMEROS = [("inscricao_total", "Inscrito na abertura", "Restos a Pagar herdados de anos anteriores em 01/01"),
           ("pagamentos", "Pago até o corte", None),
           ("cancelamentos", "Cancelado até o corte", None),
           ("saldo_total", "Em aberto no corte", "ainda a pagar")]
COMPOSICOES_DA_VISAO = [
    ("categoria", "Que tipo de dívida está em aberto?",
     "Processado: despesa já liquidada no ano de origem. Não processado: ainda não liquidada."),
    ("fonte_recurso", "Com que recurso será pago?", None),
    ("funcao", "Em que área de governo?", None),
    ("tipo_credor", "Para quem se deve?", None),
]


def visao(p, q):
    try:
        sel = _selecao(p, q)
    except SemDados as e:
        return erro("Sem dados processados", str(e))
    v = p.visao_geral(sel["exercicio"], sel["data_final"], sel["entidade"], sel["em"])
    escopo = _nome_do_escopo(p, sel["entidade"])
    titulo = f"Restos a Pagar {sel['exercicio']} — {escopo}"
    partes = [f"<h1>{esc(titulo)}</h1>",
              f'<p class="subtitulo">Posição em {esc(fm.data_br(sel["data_final"]))} · {esc(_quando(sel))}</p>',
              _avisos(sel["avisos"]), _formulario("/", sel, _entidades_do_catalogo(p)), _retrato(v["retrato"])]
    if not v["disponivel"]:
        partes.append('<section class="indisponivel" id="indisponivel"><h2>Dados indisponíveis para este recorte</h2>'
                      f'<p>{esc(v["motivo_indisponivel"])}.</p><p>Nenhum valor é mostrado: ausência de dado não é '
                      "zero. A evolução e a série abaixo mostram os cortes que têm valor.</p></section>")
    else:
        partes.append(_numeros(v["numeros"]))
    blocos = []
    if v["disponivel"]:
        n = v["numeros"]
        blocos.append(_bloco_pizza(
            "destino", "O que aconteceu com o valor inscrito?", v["destino"], sel,
            _leitura_destino(v["destino"]), ("inscrito", n["inscricao_total"]), "/resumo"))
        blocos.append(_bloco_pizza(
            "saldo", "O que falta para pagar o saldo?", v["situacao_do_saldo"], sel,
            "A liquidar: entrega ainda não atestada. Liquidado: entrega atestada, falta só o pagamento.",
            ("em aberto", n["saldo_total"]), "/resumo"))
    blocos.append(_bloco_evolucao(v["evolucao"], sel))
    blocos.append(_bloco_exercicios(v["entre_exercicios"], sel))
    if v["disponivel"]:
        if v["por_entidade"]:
            blocos.append(_bloco_pizza("entidade", "De quem é o saldo em aberto?", v["por_entidade"], sel,
                                       _leitura_maiores(v["por_entidade"], 2), ("em aberto", n["saldo_total"]),
                                       "/entidades"))
        for dimensao, pergunta, explicacao in COMPOSICOES_DA_VISAO:
            bloco = v["composicao"].get(dimensao)
            if bloco is None:
                continue
            nota = f"Nomes das funções: {v['fonte_das_funcoes']}." if dimensao == "funcao" else None
            blocos.append(_bloco_pizza(dimensao, pergunta, bloco, sel, explicacao or _leitura_maiores(bloco, 1),
                                       ("em aberto", n["saldo_total"]), "/composicao", nota, dimensao=dimensao))
    partes.append(f'<div class="painel-bi">{"".join(blocos)}</div>')
    if v["disponivel"]:
        ret = v["retrato"]
        partes.append(P.secao_onde_conferir(v["entidades"], sel["exercicio"], sel["data_final"],
                                            fm.data_br(ret["coletado_de"], True) if ret else ""))
    partes.append('<p class="dica">' + fm.link("/resumo", "Ver todos os indicadores deste corte, com fonte, regra e "
                                                          "conferência com o RREO", exercicio=sel["exercicio"],
                                               data_final=sel["data_final"], entidade=sel["entidade"], em=sel["em"])
                  + "</p>")
    return titulo, "".join(partes)


def _nome_do_escopo(p, entidade):
    if entidade is None:
        return "Município de Ponta Grossa"
    nomes = dict(_entidades_do_catalogo(p))
    return nomes.get(entidade, f"entidade {entidade}")


def _numeros(n):
    cartoes = []
    for chave, rotulo, nota in NUMEROS:
        if chave == "pagamentos" and n["pago_do_inscrito_decimos"] is not None:
            nota = f"{fm.percentual(n['pago_do_inscrito_decimos'])} do inscrito"
        cartoes.append(f'<div class="numero-chave numero-{esc(chave)}"><p class="rotulo">{esc(rotulo)}</p>'
                       f'<p class="grande">{fm.valor_abreviado(n[chave], f"vg-{chave}")}</p>'
                       f'<p class="exato">{esc(fm.moeda(n[chave]))}</p>'
                       + (f'<p class="nota-numero">{esc(nota)}</p>' if nota else "") + "</div>")
    return f'<section class="numeros-chave" aria-label="Números-chave">{"".join(cartoes)}</section>'


def _classes(itens):
    """Colors: fixed for the known parts, the palette in order for the others, grey for 'demais'."""
    classes, livres = [], iter(PALETA)
    for i in itens:
        if i["chave"] in CORES_FIXAS:
            classes.append(CORES_FIXAS[i["chave"]])
        elif i.get("agrupa"):
            classes.append(CLASSE_DEMAIS)
        else:
            classes.append(next(livres, CLASSE_DEMAIS))
    return classes


def _href(nome, item, sel):
    if item.get("agrupa"):                    # "demais" joins several groups: no single list to open
        return None
    if nome == "entidade":
        return fm.url("/resumo", exercicio=sel["exercicio"], data_final=sel["data_final"], entidade=item["entidade"],
                      em=sel["em"])
    if item.get("filtro"):
        return fm.url("/empenhos", exercicio=sel["exercicio"], data_final=sel["data_final"], entidade=sel["entidade"],
                      em=sel["em"], **item["filtro"])
    return None


def _bloco_pizza(nome, pergunta, bloco, sel, leitura, centro, detalhe, nota=None, **params_detalhe):
    ident = f"vg-{nome}"
    rotulo_centro, total = centro
    tabela = _tabela_exata(nome, bloco)
    ver = fm.link(detalhe, "ver detalhes", exercicio=sel["exercicio"], data_final=sel["data_final"],
                  entidade=sel["entidade"], em=sel["em"], **params_detalhe)
    if not bloco["pizza"]:
        corpo = f'<p class="aviso">{esc(bloco["motivo"])}.</p>'
    else:
        fatias = [{"rotulo": i["rotulo"], "valor_c": i["valor_c"], "decimos": i["decimos"], "classe": c,
                   "href": _href(nome, i, sel)} for i, c in zip(bloco["itens"], _classes(bloco["itens"]))]
        corpo = grafico.pizza(ident, pergunta, f"{leitura} Total: {fm.moeda(total)}.", bloco["total_c"], fatias,
                              (fm.abreviado(total), rotulo_centro))
    nota = f'<p class="fonte-texto">{esc(nota)}</p>' if nota else ""
    return (f'<section class="bloco" id="{esc(ident)}"><h2>{esc(pergunta)}</h2><p class="leitura">{esc(leitura)}</p>'
            f'{corpo}{nota}<details class="exatos"><summary>Valores exatos</summary>{tabela}</details>'
            f'<p class="ver-detalhes">{ver}</p></section>')


def _tabela_exata(nome, bloco):
    linhas = [[esc(i["rotulo"]), fm.valor(i["valor_c"], f"vg-{nome}-{i['chave']}"),
               esc(fm.percentual(i.get("decimos")) or "—")] for i in bloco["itens"]]
    linhas.append(["<strong>Total</strong>", fm.valor(bloco["total_c"], f"vg-{nome}-total"), "100,0%"
                   if bloco["pizza"] else "—"])
    return fm.tabela([("Parte", None), ("Valor exato", None), ("Participação", None)], linhas)


def _leitura_destino(bloco):
    if not bloco["pizza"]:
        return "Divisão do valor inscrito entre pago, cancelado e em aberto."
    d = {i["chave"]: i["decimos"] for i in bloco["itens"]}
    return (f"{fm.percentual(d['pago'])} já foi pago, {fm.percentual(d['cancelado'])} foi cancelado e "
            f"{fm.percentual(d['em_aberto'])} segue em aberto.")


def _leitura_maiores(bloco, quantos):
    if not bloco["pizza"]:
        return "Divisão do saldo em aberto."
    maiores = [i for i in bloco["itens"] if not i.get("agrupa")]
    maiores = sorted(maiores, key=lambda i: -i["decimos"])[:quantos]
    return "; ".join(f"{i['rotulo']}: {fm.percentual(i['decimos'])} do saldo" for i in maiores) + "."


def _bloco_evolucao(serie, sel):
    ident = "vg-evolucao"
    grupos, linhas = [], []
    for x in serie:
        df = x["data_final"]
        situacao = x["situacao"]["texto"]
        valores = [x["saldo_total"], x["pagamentos"]]
        titulos = [f"{nome} em {fm.data_br(df)}: " + (fm.moeda(val) if val is not None else f"sem dado ({situacao})")
                   for (nome, _), val in zip(SERIE_EVOLUCAO, valores)]
        grupos.append({"rotulo": fm.data_br(df)[:5], "valores": valores, "titulos": titulos,
                       "href": fm.url("/resumo", exercicio=sel["exercicio"], data_final=df, entidade=sel["entidade"],
                                      em=sel["em"])})
        linhas.append([esc(fm.data_br(df)), fm.valor(x["saldo_total"], f"vg-ev-{df}-saldo", "sem dado"),
                       fm.valor(x["pagamentos"], f"vg-ev-{df}-pago", "sem dado"),
                       esc("; ".join([situacao] + x["rotulos"]))])
    com_valor = [x for x in serie if x["tem_valor"]]
    if len(com_valor) >= 2:
        a, b = com_valor[0], com_valor[-1]
        leitura = (f"O saldo em aberto foi de {fm.abreviado(a['saldo_total'])} em {fm.data_br(a['data_final'])} "
                   f"para {fm.abreviado(b['saldo_total'])} em {fm.data_br(b['data_final'])}.")
    else:
        leitura = "Saldo em aberto e total pago em cada corte do exercício."
    leitura += " Coluna tracejada = corte sem dado (nunca zero)."
    tabela = fm.tabela([("Corte", None), ("Saldo em aberto", None), ("Pago desde 01/01", None),
                        ("Situação do dado", None)], linhas)
    ver = fm.link("/evolucao", "ver detalhes", exercicio=sel["exercicio"], entidade=sel["entidade"], em=sel["em"])
    titulo = f"Como o saldo caiu ao longo de {sel['exercicio']}?"
    return (f'<section class="bloco largo" id="{ident}"><h2>{esc(titulo)}</h2><p class="leitura">{esc(leitura)}</p>'
            + grafico.colunas(ident, titulo, leitura, grupos, SERIE_EVOLUCAO)
            + f'<details class="exatos"><summary>Valores exatos</summary>{tabela}</details>'
            f'<p class="ver-detalhes">{ver}</p></section>')


def _bloco_exercicios(serie, sel):
    ident = "vg-exercicios"
    grupos, linhas = [], []
    for x in serie:
        ex, df = x["exercicio"], x["data_final"]
        situacao = x["situacao"]["texto"]
        valores = [x["inscricao_total"], x["saldo_total"]]
        fim = f"corte {fm.data_br(df)}" + (" (exercício em aberto)" if x["aberto"] else "")
        titulos = [f"{nome} — {ex}, {fim}: " + (fm.moeda(val) if val is not None else f"sem dado ({situacao})")
                   for (nome, _), val in zip(SERIE_EXERCICIOS, valores)]
        grupos.append({"rotulo": str(ex) + ("*" if x["aberto"] else ""), "valores": valores, "titulos": titulos,
                       "href": fm.url("/", exercicio=ex, data_final=df, entidade=sel["entidade"], em=sel["em"])})
        linhas.append([esc(ex), esc(fm.data_br(df)), fm.valor(x["inscricao_total"], f"vg-ex-{ex}-inscrito", "sem dado"),
                       fm.valor(x["saldo_total"], f"vg-ex-{ex}-saldo", "sem dado"),
                       esc("; ".join([situacao] + x["rotulos"]))])
    leitura = ("Quanto foi inscrito em 01/01 de cada ano e quanto restou em aberto no fim dele. "
               "* exercício em aberto: último corte disponível.")
    tabela = fm.tabela([("Exercício", None), ("Corte", None), ("Inscrito na abertura", None),
                        ("Saldo no corte", None), ("Situação do dado", None)], linhas)
    ver = fm.link("/historico", "ver detalhes", entidade=sel["entidade"], em=sel["em"])
    titulo = "Como os Restos a Pagar evoluíram de um ano para o outro?"
    return (f'<section class="bloco largo" id="{ident}"><h2>{esc(titulo)}</h2><p class="leitura">{esc(leitura)}</p>'
            + grafico.colunas(ident, titulo, leitura, grupos, SERIE_EXERCICIOS)
            + f'<details class="exatos"><summary>Valores exatos</summary>{tabela}</details>'
            f'<p class="ver-detalhes">{ver}</p></section>')
