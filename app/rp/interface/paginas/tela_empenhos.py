"""Commitment list (/empenhos)."""
from ...painel import fontes as F, publico
from ...painel.consulta import CATEGORIAS, DIMENSOES_ORCAMENTARIAS, FAIXAS, ROTULO_COMPOSICAO
from .. import formato as fm
from ..formato import esc
from .estrutura import (_avisos, _entidades_do_catalogo, erro, _formulario, NOME_CATEGORIA, NOME_FAIXA,
                        _origem_conjunto, _quando, _retrato, _selecao, SemDados, TAMANHO_PAGINA)


def _filtros_empenho(q):
    return {"categoria": q.escolha("categoria", CATEGORIAS), "fonte_recurso": q.inteiro("fonte_recurso", 0, 10 ** 9),
            "programatica": q.texto("programatica", 28), "tipo_credor": q.escolha("tipo_credor", publico.TIPOS_CREDOR),
            "cnpj": q.texto("cnpj", 18), "anoempenho": q.inteiro("anoempenho", 1900, 2999),
            "empenho": q.inteiro("empenho", 0, 10 ** 9), "faixa": q.escolha("faixa", FAIXAS),
            "orgao": q.texto("orgao", 20), "funcao": q.texto("funcao", 20), "programa": q.texto("programa", 20),
            "elemento": q.texto("elemento", 20),
            "sem_classificacao": q.escolha("sem_classificacao", DIMENSOES_ORCAMENTARIAS)}


def _mais_filtros(filtros):
    """Composition filters (05.4): band and budget classification, in a collapsible block (open when in use)."""
    usados = any(filtros[k] is not None for k in ("faixa", "orgao", "funcao", "programa", "elemento", "sem_classificacao"))
    campos = [f'<label>Faixa (FAIXA v1) <select name="faixa"><option value="">todas</option>'
              f'{fm.opcoes([(f, NOME_FAIXA[f]) for f in FAIXAS], filtros["faixa"] or "")}</select></label>']
    for nome, rotulo, exemplo in (("orgao", "Órgão", "09"), ("funcao", "Função", "12"), ("programa", "Programa", "0076"),
                                  ("elemento", "Elemento de despesa", "3390390000")):
        campos.append(f'<label>{esc(rotulo)} (código) <input name="{nome}" inputmode="numeric" maxlength="20" '
                      f'value="{esc(filtros[nome] or "")}" placeholder="ex.: {exemplo}"></label>')
    campos.append('<label>Sem classificação em <select name="sem_classificacao"><option value="">—</option>'
                  + fm.opcoes([(d, ROTULO_COMPOSICAO[d].lower()) for d in DIMENSOES_ORCAMENTARIAS],
                              filtros["sem_classificacao"] or "") + "</select></label>")
    return (f'<details class="mais-filtros"{" open" if usados else ""}><summary>Mais filtros: faixa e classificação '
            f'orçamentária</summary><div class="filtros-extra">{"".join(campos)}</div></details>')


def empenhos(p, q):
    try:
        sel = _selecao(p, q)
    except SemDados as e:
        return erro("Sem dados processados", str(e))
    filtros = _filtros_empenho(q)
    ordem = q.escolha("ordem", ("saldo", "empenho")) or "saldo"
    pagina = q.inteiro("pagina", 1, 10 ** 6) or 1
    r = p.empenhos(sel["exercicio"], sel["data_final"], sel["entidade"], sel["em"], TAMANHO_PAGINA,
                   (pagina - 1) * TAMANHO_PAGINA, ordem, **filtros)
    escopo = f"entidade {sel['entidade']}" if sel["entidade"] is not None else "Município"
    titulo = (f"Empenhos — {escopo}, exercício {sel['exercicio']}, corte {fm.data_br(sel['data_final'])} "
              f"({_quando(sel)})")
    fontes_rec = []
    if r["disponivel"]:
        fontes_rec = [(l["fonte_recurso"], l["descricao_fonte"] or l["fonte_recurso"])
                      for l in p.por_dimensao("fonte_recurso", sel["exercicio"], sel["data_final"], sel["entidade"],
                                              sel["em"])["linhas"]]
        fontes_rec.sort(key=lambda x: (x[0] is None, x[0]))
    extra = (f'<label>Ano do empenho <input name="anoempenho" inputmode="numeric" maxlength="4" '
             f'value="{esc(filtros["anoempenho"] or "")}" placeholder="ex.: 2025"></label>'
             f'<label>Número do empenho <input name="empenho" inputmode="numeric" maxlength="10" '
             f'value="{esc(filtros["empenho"] if filtros["empenho"] is not None else "")}" placeholder="ex.: 5659"></label>'
             f'<label>Categoria <select name="categoria"><option value="">todas</option>'
             f'{fm.opcoes([(c, NOME_CATEGORIA[c]) for c in CATEGORIAS], filtros["categoria"] or "")}</select></label>'
             f'<label>Fonte de recurso <select name="fonte_recurso"><option value="">todas</option>'
             f'{fm.opcoes(fontes_rec, filtros["fonte_recurso"] if filtros["fonte_recurso"] is not None else "")}</select></label>'
             f'<label>Programação (começa com) <input name="programatica" inputmode="numeric" maxlength="28" '
             f'value="{esc(filtros["programatica"] or "")}" placeholder="ex.: 09002"></label>'
             f'<label>Tipo de credor <select name="tipo_credor"><option value="">todos</option>'
             f'{fm.opcoes([(t, t) for t in publico.TIPOS_CREDOR], filtros["tipo_credor"] or "")}</select></label>'
             f'<label>CNPJ do credor (só pessoa jurídica) <input name="cnpj" maxlength="18" '
             f'value="{esc(filtros["cnpj"] or "")}" placeholder="00.000.000/0000-00"></label>'
             f'<label>Ordem <select name="ordem">{fm.opcoes([("saldo", "maior saldo"), ("empenho", "entidade, ano e número")], ordem)}'
             "</select></label>" + _mais_filtros(filtros))
    corpo = [f"<h1>{esc(titulo)}</h1>", _avisos(sel["avisos"]), _formulario("/empenhos", sel, _entidades_do_catalogo(p), extra)]
    if not r["disponivel"]:
        corpo.append(f'<section class="indisponivel" id="indisponivel"><p>{esc(r["motivo_indisponivel"])}.</p>'
                     "<p>Nenhum valor é mostrado: ausência de dado não é zero.</p></section>")
        return titulo, "".join(corpo)
    corpo.append(_retrato(r["retrato"]))
    filtros_txt = ", ".join(f"{k} = {v}" for k, v in r["filtros"].items()) or "nenhum"
    if r["sem_resultado"]:
        corpo.append('<section class="grupo sem-resultado" id="sem-resultado"><h2>Nenhum resultado encontrado</h2>'
                     f'<p>{esc(r["mensagem_sem_resultado"])}.</p><p>Filtros aplicados: {esc(filtros_txt)}.</p>'
                     f'<p>Empenhos encontrados: {fm.contagem(r["total"], "tot-registros")}.</p>'
                     "<p>Nenhum valor é mostrado: conjunto vazio não é valor zero.</p>"
                     + _origem_conjunto(r["proveniencia"], "Snapshots consultados") + "</section>")
        return titulo, "".join(corpo)
    t = r["totais"]["valores"]
    corpo.append('<section class="grupo"><h2>Conjunto selecionado</h2>'
                 f'<p>Filtros aplicados: {esc(filtros_txt)}. Filtro só escolhe registros; não altera nenhum valor.</p>'
                 + fm.selo("elotech", "derivado", r["totais"]["regras"], "somas dos campos da API nos registros filtrados")
                 + '<div class="cartoes compactos">'
                 + "".join(f'<div class="indicador"><p class="rotulo">{esc(rot)}</p><p class="numero">{html}</p></div>'
                           for rot, html in (("Empenhos", fm.contagem(r["total"], "tot-registros")),
                                             ("Processado (inscrito)", fm.valor(t["inscricao_processada"], "tot-proc")),
                                             ("Não processado (inscrito)", fm.valor(t["inscricao_nao_processada"], "tot-aproc")),
                                             ("Pagamentos", fm.valor(t["pagamentos"], "tot-pagamentos")),
                                             ("Liquidações", fm.valor(t["liquidacoes"], "tot-liquidacoes")),
                                             ("Cancelamentos", fm.valor(t["cancelamentos"], "tot-cancelamentos")),
                                             ("Saldo (S1)", fm.valor(t["saldo_total"], "tot-s1"))))
                 + "</div>" + _origem_conjunto(r["proveniencia"])
                 + '<p class="nota">A origem de cada registro (resposta HTTP, página, posição e hash do objeto bruto) '
                   "está no detalhe do empenho.</p></section>")
    linhas = []
    for reg in r["registros"]:
        detalhe = fm.url("/empenho", entidade=reg["entidade"], anoempenho=reg["anoempenho"], empenho=reg["empenho"],
                         exercicio=sel["exercicio"], data_final=sel["data_final"], em=sel["em"])
        linhas.append([esc(reg["entidade"]), esc(reg["anoempenho"]), f'<a href="{esc(detalhe)}">{esc(reg["empenho"])}</a>',
                       esc(reg["tipo_credor"]), esc(fm.data_br(reg["data_emissao"])), f'<code>{esc(reg["programatica"] or "")}</code>',
                       esc(reg["fonte_recurso"]), fm.valor(reg["proc_c"]), fm.valor(reg["aproc_c"]),
                       fm.valor(reg["pago_proc_c"]), fm.valor(reg["pago_aproc_c"]), fm.valor(reg["liquidado_c"]),
                       fm.valor(reg["cancelamentos_c"]), fm.valor(reg["s1_saldo_total_c"]),
                       esc(NOME_CATEGORIA.get(reg["categoria"], reg["categoria"]))])
    cab = [("Entidade", "entidade"), ("Ano", "anoempenho"), ("Empenho", "empenho — abre o detalhe"),
           ("Credor", "só o tipo; nome e documento não aparecem na lista"), ("Emissão", "dataEmissao"),
           ("Programação", "programatica"), ("Fonte", "fonteRecurso"), ("Processado", "proc"),
           ("Não processado", "aproc"), ("Pago proc.", "pagoProc"), ("Pago não proc.", "pagoAProc"),
           ("Liquidado", "liquidado"), ("Cancelado", "canceladoAProc + canceladoProc"),
           ("Saldo (S1)", "proc + aproc − pagoProc − pagoAProc − canceladoAProc (S1 v1)"), ("Categoria", "CAT v1")]
    paginas = max(1, -(-r["total"] // TAMANHO_PAGINA))
    params = {k: v for k, v in filtros.items() if v not in (None, "")}
    base = dict(exercicio=sel["exercicio"], data_final=sel["data_final"], entidade=sel["entidade"], em=sel["em"],
                ordem=ordem, **params)
    nav = [f"Página {pagina} de {paginas} ({fm.inteiro(r['total'])} empenhos)"]
    if pagina > 1:
        nav.insert(0, fm.link("/empenhos", "« anterior", pagina=pagina - 1, **base))
    if pagina < paginas:
        nav.append(fm.link("/empenhos", "próxima »", pagina=pagina + 1, **base))
    corpo += ['<section class="grupo"><h2>Registros</h2>',
              fm.selo("elotech", "da_fonte", None, None),
              '<p class="nota">Valores das colunas vêm como a API devolveu (dado da fonte); saldo e categoria são '
              "derivados pelas regras S1 v1 e CAT v1 (operacionais).</p>",
              fm.tabela(cab, linhas, "tabela empenhos"), f'<p class="paginacao">{" · ".join(nav)}</p>',
              _dicionario_resumido(), "</section>"]
    return titulo, "".join(corpo)


def _dicionario_resumido():
    itens = "".join(f"<li><strong>{esc(rot)}</strong> = <code>{esc(api)}</code>: {esc(sig)}</li>"
                    for col, (api, rot, sig, _) in F.CAMPOS.items() if col not in publico.CAMPOS_RESTRITOS)
    return f'<details class="dicionario"><summary>Nomes técnicos dos campos (API Elotech)</summary><ul>{itens}</ul></details>'
