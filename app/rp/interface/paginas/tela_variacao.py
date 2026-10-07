"""Variation between two cut-offs (/variacao)."""
from ...painel.consulta import METRICAS_DA_VARIACAO
from .. import formato as fm, portal as P
from ..formato import esc
from .estrutura import (_avisos, _entidades_do_catalogo, erro, _quando, _registro_tecnico, _selecao, SemDados,
                        _situacao_curta, TAMANHO_PAGINA)


def variacao(p, q):
    """Investigation of the variation between two cut-offs of the same fiscal year (sub-stage 05.5). Variation,
    contributions, groups, classes, closings and pagination come ready from the panel layer."""
    try:
        sel = _selecao(p, q)
    except SemDados as e:
        return erro("Sem dados processados", str(e))
    metrica = q.escolha("metrica", tuple(METRICAS_DA_VARIACAO)) or "s1"
    pagina = q.inteiro("pagina", 1, 10 ** 6) or 1
    cortes = [c["data_final"] for c in sel["cortes_do_exercicio"]]
    escopo = f"entidade {sel['entidade']}" if sel["entidade"] is not None else "Município"
    if len(cortes) < 2:
        titulo = f"Variação entre cortes — {escopo}, exercício {sel['exercicio']} ({_quando(sel)})"
        return titulo, (f"<h1>{esc(titulo)}</h1>{_avisos(sel['avisos'])}"
                        + _formulario_variacao(sel, cortes, None, metrica, _entidades_do_catalogo(p))
                        + '<section class="indisponivel" id="indisponivel"><p>O exercício tem um único corte processado: '
                          "não há variação dentro do exercício. A passagem de um exercício para o seguinte está na "
                          + fm.link("/historico", "Série entre exercícios", entidade=sel["entidade"], em=sel["em"])
                          + " (fechamento × abertura).</p></section>")
    posterior, anterior = sel["data_final"], q.data("anterior")
    if posterior == cortes[0] and q.data("data_final") is None:   # default: the first cut-off has no previous one
        posterior = cortes[1]
    if anterior is None:   # default: the processed cut-off right before the later one
        anteriores = [c for c in cortes if c < posterior]
        anterior = anteriores[-1] if anteriores else None
    if anterior is None or anterior >= posterior:   # an impossible requested pair: it is never swapped for another
        motivo = (f"não há corte processado anterior a {fm.data_br(posterior)} neste exercício" if anterior is None else
                  f"o corte anterior ({fm.data_br(anterior)}) precisa ser anterior ao posterior ({fm.data_br(posterior)})")
        titulo = f"Variação entre cortes — {escopo}, exercício {sel['exercicio']} ({_quando(sel)})"
        return titulo, (f"<h1>{esc(titulo)}</h1>{_avisos(sel['avisos'])}"
                        + _formulario_variacao(sel, cortes, (anterior, posterior), metrica, _entidades_do_catalogo(p))
                        + '<section class="indisponivel" id="indisponivel"><h2>Investigação indisponível para este par'
                          f"</h2><p>{esc(motivo)}. Escolha os dois cortes no formulário.</p><p>Nenhuma contribuição é "
                          "mostrada: ausência de dado não é zero.</p></section>")
    r = p.variacao(sel["exercicio"], anterior, posterior, sel["entidade"], metrica, sel["em"], TAMANHO_PAGINA,
                   (pagina - 1) * TAMANHO_PAGINA)
    titulo = (f"Variação entre cortes — {escopo}, exercício {sel['exercicio']}: {fm.data_br(anterior)} → "
              f"{fm.data_br(posterior)} ({_quando(sel)})")
    corpo = [f"<h1>{esc(titulo)}</h1>", _avisos(sel["avisos"]),
             _formulario_variacao(sel, cortes, (anterior, posterior), metrica, _entidades_do_catalogo(p)),
             _dois_cortes(r)]
    if not r["disponivel"]:
        corpo.append('<section class="indisponivel" id="indisponivel"><h2>Investigação indisponível para este par</h2>'
                     f'<p>{esc(r["motivo_indisponivel"])}.</p><p>Nenhuma contribuição é mostrada: ausência de dado não é '
                     "zero.</p>" + _chaves_repetidas(r["chaves_repetidas"]) + "</section>")
        return titulo, "".join(corpo)
    if any(r["pares_espelhados"].values()):
        corpo.append(f'<p class="aviso" id="aviso-pares">Este escopo envolve as entidades 1 e 15, com registros '
                     f'espelhados (cópias 24xxxxx): {fm.inteiro(r["pares_espelhados"]["anterior"])} no corte anterior e '
                     f'{fm.inteiro(r["pares_espelhados"]["posterior"])} no posterior. Os dois lados continuam nos valores, '
                     "como a API os devolve; cópia incluída depois aparece como “presente só no corte posterior”.</p>")
    base = dict(exercicio=sel["exercicio"], anterior=anterior, data_final=posterior, entidade=sel["entidade"],
                em=sel["em"], metrica=metrica)
    corpo += [f'<p class="nota">{esc(r["nota"])}</p>', _total_da_variacao(r), _resumo_da_variacao(r, sel),
              _classes_da_variacao(r), _lista_da_variacao(r, sel, pagina, base)]
    return titulo, "".join(corpo)


def _formulario_variacao(sel, cortes, par, metrica, entidades):
    anterior, posterior = par or (None, None)
    opcoes = [(df, fm.data_br(df)) for df in cortes]
    lista = fm.opcoes([(e, f"{e} — {n}") for e, n in entidades], sel["entidade"] if sel["entidade"] else "")
    return ('<form class="filtros" method="get" action="/variacao">'
            f'<label>Exercício <select name="exercicio">{fm.opcoes([(x, x) for x in sel["exercicios"]], sel["exercicio"])}'
            "</select></label>"
            f'<label>Corte anterior <select name="anterior">{fm.opcoes(opcoes, anterior or "")}</select></label>'
            f'<label>Corte posterior <select name="data_final">{fm.opcoes(opcoes, posterior or "")}</select></label>'
            '<label>Entidade <select name="entidade"><option value="">Município (entidades do catálogo oficial)</option>'
            f"{lista}</select></label>"
            f'<label>Métrica <select name="metrica">'
            f'{fm.opcoes([(k, v["rotulo"]) for k, v in METRICAS_DA_VARIACAO.items()], metrica)}</select></label>'
            f'<label>Como estava em (opcional) <input type="date" name="em" value="{esc(sel["em"] or "")}"></label>'
            '<button type="submit">Consultar</button></form>'
            '<p class="dica">Mudou o exercício? Consulte uma vez para atualizar a lista de cortes. Os dois cortes são '
            "escolhidos por você; não precisam ser vizinhos.</p>")


def _dois_cortes(r):
    linhas = []
    for nome, rotulo in (("anterior", "Corte anterior"), ("posterior", "Corte posterior")):
        x = r[nome]
        if x is None:
            continue
        ret = x["retrato"]
        coleta = "—" if not ret else esc(fm.data_br(ret["coletado_de"], True) + (
            "" if fm.data_br(ret["coletado_de"], True) == fm.data_br(ret["coletado_ate"], True)
            else " a " + fm.data_br(ret["coletado_ate"], True)))
        snaps = (f'<details class="origem"><summary>{fm.inteiro(len(x["snapshots"]))} snapshot(s)</summary>'
                 + " ".join(f"<code>{esc(u)}</code>" for u in x["snapshots"]) + "</details>") if x["snapshots"] else "—"
        linhas.append([esc(rotulo), esc(fm.data_br(x["data_final"])),
                       f'<span title="{esc(x["situacao"]["texto"])}">{esc(_situacao_curta(x["situacao"]["texto"]))}</span>',
                       coleta, snaps, fm.valor(x["total_c"], f"var-{nome}")])
    return ('<section class="grupo" id="dois-cortes"><h2>Os dois cortes</h2>'
            + fm.selo("elotech", r["metrica"]["natureza_do_operando"], r["metrica"]["regras"], r["metrica"]["formula"])
            + fm.tabela([("", None), ("Corte", None), ("Situação", None), ("Coletado em", "data da consulta à API"),
                         ("Snapshots", None), (r["metrica"]["rotulo"], "soma do indicador homologado do corte")], linhas,
                        "tabela dois-cortes")
            + "</section>")


def _chaves_repetidas(lista):
    if not lista:
        return ""
    linhas = [[esc(f"{x['chave']['entidade']} / {x['chave']['empenho']}/{x['chave']['anoempenho']}"),
               fm.contagem(x["anterior"]), fm.contagem(x["posterior"])] for x in lista[:200]]
    return ("<h3>Chaves repetidas</h3>"
            + fm.tabela([("Entidade / empenho/ano", None), ("Ocorrências no anterior", None),
                         ("Ocorrências no posterior", None)], linhas))


def _total_da_variacao(r):
    return ('<section class="grupo"><h2>Variação total</h2>'
            + fm.selo("elotech", "diferenca", r["metrica"]["regras"], "valor do corte posterior − valor do corte anterior")
            + '<div class="cartoes compactos">'
            + "".join(f'<div class="indicador"><p class="rotulo">{esc(rot)}</p><p class="numero">{html}</p></div>'
                      for rot, html in (("Corte anterior", fm.valor(r["anterior"]["total_c"])),
                                        ("Corte posterior", fm.valor(r["posterior"]["total_c"])),
                                        ("Variação (posterior − anterior)", fm.valor(r["variacao_c"], "var-total"))))
            + "</div></section>")


def _chave(x, sel):
    c = x["chave"]
    return fm.link("/empenho/cortes", f"{c['empenho']}/{c['anoempenho']}", entidade=c["entidade"],
                   anoempenho=c["anoempenho"], empenho=c["empenho"], exercicio=sel["exercicio"], em=sel["em"])


def _lado(x, nome):
    lado = x[nome]
    if lado is None:
        return f'<span class="sem-valor">ausente do corte {"anterior" if nome == "anterior" else "posterior"}</span>'
    return fm.valor(lado["valor_c"])


def _linha_de_contribuicao(x, sel, ident):
    return [esc(x["chave"]["entidade"]), _chave(x, sel), esc(x["classe_texto"]), _lado(x, "anterior"),
            _lado(x, "posterior"), fm.valor(x["contribuicao_c"], ident)]


CABECALHO_CONTRIBUICAO = [("Entidade", None), ("Empenho/ano", "abre o empenho em todos os cortes"), ("Classe", None),
                          ("Valor no corte anterior", None), ("Valor no corte posterior", None),
                          ("Contribuição", "posterior − anterior")]


def _resumo_da_variacao(r, sel):
    grupos = {g["id"]: g for g in r["resumo"]["grupos"]}
    linhas = [[esc(g["rotulo"]), fm.contagem(g["quantidade"], f"grp-{g['id']}-n"), fm.valor(g["soma_c"], f"grp-{g['id']}")]
              for g in r["resumo"]["grupos"]]
    f = r["fechamentos"]["grupos"]
    linhas += [["<strong>Soma dos grupos</strong>", "—", fm.valor(f["soma_dos_grupos"], "grp-soma")],
               ["Variação total", "—", fm.valor(f["total"], "grp-total")],
               ["Soma dos grupos − variação total", "—", fm.valor(f["diferenca"], "fech-grupos")]]
    partes = ['<section class="grupo" id="resumo-variacao"><h2>Resumo: maiores aumentos e reduções</h2>',
              fm.selo("elotech", "diferenca", None, "contribuição de cada empenho = posterior − anterior; sem valor absoluto"),
              fm.tabela([("Grupo", None), ("Empenhos", None), ("Soma das contribuições", None)], linhas)]
    for gid, titulo, prefixo in (("top_aumentos", "Maiores aumentos", "top-aum"), ("top_reducoes", "Maiores reduções", "top-red")):
        itens = grupos[gid]["itens"]
        if itens:
            partes.append(f"<h3>{esc(titulo)}</h3>" + fm.tabela(
                CABECALHO_CONTRIBUICAO, [_linha_de_contribuicao(x, sel, f"{prefixo}-{i}") for i, x in enumerate(itens, 1)]))
    partes.append('<p class="nota">“Sem variação” reúne os empenhos com contribuição zero; aparecem só na contagem. '
                  "Aumentos e reduções nunca se compensam em silêncio: cada grupo mostra a sua soma, com o sinal.</p>"
                  "</section>")
    return "".join(partes)


def _classes_da_variacao(r):
    linhas = [[esc(c["rotulo"]), fm.contagem(c["quantidade"], f"cls-{c['id']}-n"), fm.valor(c["soma_c"], f"cls-{c['id']}")]
              for c in r["classes"]]
    f = r["fechamentos"]["classes"]
    linhas += [["<strong>Soma das classes</strong>", "—", fm.valor(f["soma_dos_grupos"], "cls-soma")],
               ["Soma das classes − variação total", "—", fm.valor(f["diferenca"], "fech-classes")]]
    return ('<section class="grupo" id="classes-variacao"><h2>Por situação da chave</h2>'
            + fm.selo("elotech", "diferenca", None, "chave = entidade, ano e número do empenho")
            + '<p class="nota">Nos dois cortes: valor posterior − anterior. Presente só no corte posterior: o valor do '
              "posterior (ex.: registro incluído depois). Ausente no corte posterior: 0 − valor do anterior. Registro "
              "de um lado só nunca é tratado como zero do outro lado sem esse rótulo.</p>"
            + fm.tabela([("Situação da chave", None), ("Empenhos", None), ("Soma das contribuições", None)], linhas)
            + "</section>")


def _origem_contribuicao(x, sel):
    """Each side of the variation: the commitment at that cut-off in the portal's full listing and the commitment
    detail; the technical record (snapshot, page, position, raw object) stays collapsed."""
    c = x["chave"]
    portal, tecnico = [], []
    for nome, df in (("anterior", sel["anterior"]), ("posterior", sel["posterior"])):
        lado = x[nome]
        if lado is None:
            portal.append(f"<li>{esc(nome.capitalize())} ({esc(fm.data_br(df))}): ausente do corte.</li>")
            continue
        pv = lado["proveniencia"]
        detalhe = fm.link("/empenho", "detalhe", entidade=c["entidade"], anoempenho=c["anoempenho"], empenho=c["empenho"],
                          exercicio=sel["exercicio"], data_final=df, em=sel["em"])
        portal.append(f"<li>{esc(nome.capitalize())} ({esc(fm.data_br(df))}): "
                      + P.link(P.url_integra(c["entidade"], sel["exercicio"], df, 0, c["empenho"], c["anoempenho"]),
                               "este empenho no corte") + "</li>")
        tecnico.append(f"<li>{esc(nome.capitalize())}: snapshot <code>{esc(pv['snapshot_uid'])}</code>, página "
                       f"{esc(pv['resposta_ordem'])}, posição {esc(pv['indice_no_content'])}, objeto bruto "
                       f"<code>{esc(pv['objeto_bruto_sha256'][:16])}…</code> ({detalhe})</li>")
    portal.append(f"<li>{P.link(P.url_empenho(c['entidade'], c['anoempenho'], c['empenho']), 'Detalhe do empenho no portal')}"
                  " (aba Movimentação: lançamentos com data)</li>")
    return (f'<details class="origem"><summary>onde conferir</summary><ul>{"".join(portal)}</ul>'
            f'{_registro_tecnico("<ul>" + "".join(tecnico) + "</ul>") if tecnico else ""}</details>')


def _lista_da_variacao(r, sel, pagina, base):
    lst = r["lista"]
    contexto = {**sel, "anterior": r["consulta"]["anterior"], "posterior": r["consulta"]["posterior"]}
    linhas = [[esc(x["posicao"])] + _linha_de_contribuicao(x, sel, f"lst-{x['posicao']}") + [_origem_contribuicao(x, contexto)]
              for x in lst["itens"]]
    paginas = max(1, -(-lst["total_de_chaves"] // TAMANHO_PAGINA))
    nav = [f"Página {pagina} de {paginas} ({fm.inteiro(lst['total_de_chaves'])} empenhos com variação)"]
    if pagina > 1:
        nav.insert(0, fm.link("/variacao", "« anterior", pagina=pagina - 1, **base))
    if pagina < paginas:
        nav.append(fm.link("/variacao", "próxima »", pagina=pagina + 1, **base))
    totais = fm.lista_definicoes([("Subtotal desta página", fm.valor(lst["subtotal_c"], "lst-subtotal")),
                                  ("Acumulado até esta página", fm.valor(lst["acumulado_c"], "lst-acumulado")),
                                  ("Variação total", fm.valor(r["variacao_c"])),
                                  ("Soma da lista completa − variação total",
                                   fm.valor(r["fechamentos"]["lista"]["diferenca"], "fech-lista"))])
    return ('<section class="grupo" id="lista-variacao"><h2>Lista completa das contribuições</h2>'
            + '<p class="nota">Todos os empenhos com contribuição diferente de zero, do maior aumento à maior redução '
              "(empate: entidade, ano e número). A última página fecha com a variação total.</p>"
            + (fm.tabela([("#", "posição na lista completa")] + CABECALHO_CONTRIBUICAO + [("Origem", "registro de cada lado")],
                         linhas, "tabela variacao") if linhas else "<p>Nenhum empenho com variação.</p>")
            + totais + f'<p class="paginacao">{" · ".join(nav)}</p></section>')
