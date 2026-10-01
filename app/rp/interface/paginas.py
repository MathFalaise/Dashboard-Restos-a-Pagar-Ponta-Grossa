"""Paginas da interface publica.

Cada funcao recebe o Painel (conexao somente leitura) e os parametros ja validados e devolve (titulo, corpo HTML).
Nenhuma funcao calcula regra contabil: os valores chegam prontos da camada painel, com natureza, fonte, regra e
proveniencia; aqui so se escolhe o que mostrar e como rotular. Todo texto do banco passa por `esc`.

Regras de apresentacao:
  * valor principal = API Elotech; o RREO aparece so na conferencia e na reconciliacao, sempre rotulado;
  * todo valor mostra fonte, natureza e regra, e tem a origem acessivel (<details>, sem JavaScript);
  * todo corte mostra exercicio, corte e data da coleta (nunca so "Restos a Pagar de AAAA");
  * ausencia de valor e texto explicito, nunca R$ 0,00; entidade fora do catalogo oficial nao vira zero;
  * nivel publico sempre: listas sem nome nem documento do credor; pessoa fisica sem nome no detalhe;
  * visoes analiticas (CONS-PAR) e regras experimentais nao aparecem como indicador.
"""
from ..painel import fontes as F
from ..painel import publico
from ..painel.consulta import (CATEGORIAS, COMPOSICOES, DIMENSOES_ORCAMENTARIAS, FAIXAS, METRICAS_DA_VARIACAO,
                               ROTULO_CATEGORIA, ROTULO_COMPOSICAO, TEXTO_FAIXA)
from . import formato as fm
from . import grafico
from .formato import esc

TAMANHO_PAGINA = 50
MENU = [("/", "Resumo"), ("/evolucao", "Evolução no exercício"), ("/historico", "Série entre exercícios"),
        ("/composicao", "Composição do saldo"), ("/variacao", "Variação entre cortes"), ("/entidades", "Entidades"),
        ("/empenhos", "Empenhos"), ("/retratos", "Retratos"), ("/reconciliacao", "Reconciliação com o RREO"),
        ("/metodologia", "Metodologia e fontes"), ("/pares", "Técnico: pares espelhados")]
NOME_CATEGORIA = ROTULO_CATEGORIA
NOME_FAIXA = {"a": "a — processado, ano do empenho < exercício − 1", "b": "b — processado, ano do empenho = exercício − 1",
              "f": "f — não processado, ano do empenho < exercício − 1",
              "g": "g — não processado, ano do empenho = exercício − 1"}
GRUPOS = [
    ("Restos a Pagar inscritos na abertura do exercício", ["inscricao_total", "inscricao_processada",
                                                           "inscricao_nao_processada"]),
    ("Saldo no corte", ["saldo_total", "saldo_a_liquidar", "saldo_liquidado_a_pagar"]),
    ("Movimento de 01/01 até o corte", ["pagamentos", "pago_processado", "pago_nao_processado", "liquidacoes",
                                        "cancelamentos", "retencoes"]),
    ("Empenhos", ["registros"]),
]
DESTAQUES = {"inscricao_total", "saldo_total", "pagamentos", "registros"}


class SemDados(Exception):
    pass


# ---------------------------------------------------------------------------------------------- estrutura
def documento(titulo, corpo, ctx, ativo):
    """Pagina completa: cabecalho, menu, fonte dos dados, conteudo e rodape com a execucao em uso."""
    itens = []
    for caminho, texto in MENU:
        atual = ' class="ativo" aria-current="page"' if caminho == ativo else ""
        itens.append(f'<a href="{esc(caminho)}"{atual}>{esc(texto)}</a>')
    d, n = ctx["derivacao"], ctx["normalizacao"]
    rodape = (f"Derivação {d['id']} (hash {d['hash_resultado'][:16]}…), normalização {n['id']}, camada de consulta "
              f"{ctx['painel']}.")
    return ("<!doctype html>\n"
            '<html lang="pt-BR"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{esc(titulo)} — Restos a Pagar de Ponta Grossa</title>"
            '<link rel="stylesheet" href="/estilo.css"></head><body>'
            '<header class="topo"><p class="marca">Restos a Pagar — Ponta Grossa/PR</p>'
            f'<nav aria-label="Seções">{"".join(itens)}</nav></header>'
            f'<main id="conteudo"><p class="fonte-dados"><strong>Fonte dos dados:</strong> {esc(F.ELOTECH["rotulo"])}.</p>'
            f"{corpo}</main>"
            '<footer class="rodape"><p>Interface somente leitura: mostra o que o projeto coletou e processou, '
            "sem consultar o portal. O RREO aparece só como publicação oficial independente, para conferência.</p>"
            f"<p>{esc(rodape)}</p></footer></body></html>")


def erro(titulo, mensagem):
    return titulo, f'<h1>{esc(titulo)}</h1><section class="aviso"><p>{esc(mensagem)}</p></section>'


def _avisos(lista):
    return "".join(f'<p class="aviso">{esc(a)}</p>' for a in lista)


def _entidades_do_catalogo(p):
    return [(e["entidade"], e["nome"] or f"entidade {e['entidade']}") for e in p.entidades()["entidades"]]


def _selecao(p, q, com_entidade=True):
    """Exercicio, corte e entidade escolhidos (ou os padroes), so entre os cortes que existem no banco."""
    em = q.data("em")
    cortes = p.cortes(em)["cortes"]
    if not cortes:
        raise SemDados("Nenhum corte processado" + (f" até {fm.data_br(em)}" if em else "") + ".")
    exercicios = sorted({c["exercicio"] for c in cortes}, reverse=True)
    avisos = []
    ex = q.inteiro("exercicio", 1900, 2999)
    if ex not in exercicios:
        if ex is not None:
            avisos.append(f"Exercício {ex} sem corte processado: mostrado o exercício mais recente.")
        ex = exercicios[0]
    entidade = q.inteiro("entidade", 1, 10 ** 6) if com_entidade else None
    do_exercicio = [c for c in cortes if c["exercicio"] == ex]
    df = q.data("data_final")
    if df not in [c["data_final"] for c in do_exercicio]:
        if df is not None:
            avisos.append(f"Corte {fm.data_br(df)} não disponível no exercício {ex}: mostrado outro corte.")
        candidatos = [c for c in do_exercicio if (c["municipio_disponivel"] if entidade is None
                                                   else entidade in c["entidades_com_snapshot"])]
        df = (candidatos or do_exercicio)[-1]["data_final"]
    return {"em": em, "exercicio": ex, "data_final": df, "entidade": entidade, "exercicios": exercicios,
            "cortes_do_exercicio": do_exercicio, "avisos": avisos}


def _quando(sel):
    """Complemento obrigatorio do titulo: o retrato e o estado atual da base ou 'como estava em' uma data."""
    return f"como a base estava em {fm.data_br(sel['em'])}" if sel["em"] else "estado atual da base"


def _formulario(acao, sel, entidades=None, extra="", com_corte=True):
    cortes = [(c["data_final"], fm.data_br(c["data_final"]) + ("" if c["municipio_disponivel"] else
                                                               " (Município incompleto)"))
              for c in sel["cortes_do_exercicio"]]
    campos = [f'<label>Exercício <select name="exercicio">{fm.opcoes([(x, x) for x in sel["exercicios"]], sel["exercicio"])}'
              "</select></label>"]
    if com_corte:
        campos.append(f'<label>Corte (data final) <select name="data_final">{fm.opcoes(cortes, sel["data_final"])}'
                      "</select></label>")
    if entidades is not None:
        lista = fm.opcoes([(e, f"{e} — {n}") for e, n in entidades], sel["entidade"] if sel["entidade"] else "")
        campos.append('<label>Entidade <select name="entidade"><option value="">Município (entidades do catálogo '
                      f"oficial)</option>{lista}</select></label>")
    campos.append(f'<label>Como estava em (opcional) <input type="date" name="em" value="{esc(sel["em"] or "")}"></label>')
    dica = ('<p class="dica">Mudou o exercício? Consulte uma vez para atualizar a lista de cortes.</p>'
            if com_corte else "")
    return (f'<form class="filtros" method="get" action="{esc(acao)}">{"".join(campos)}{extra}'
            f'<button type="submit">Consultar</button></form>{dica}')


def _retrato(ret):
    """Bloco obrigatorio: exercicio, corte e coleta, com o texto do retrato."""
    if not ret:
        return ""
    ex, df = ret["exercicio"], ret["data_final"]
    coleta, ate = fm.data_br(ret["coletado_de"], True), fm.data_br(ret["coletado_ate"], True)
    if ate != coleta:
        coleta += " a " + ate
    if ret["tipo"] == "historico":
        tipo = (f"histórico — como a base estava em {fm.data_br(ret['como_estava_em'], True)}: só snapshots coletados "
                "até essa data; os posteriores não entram")
    else:
        tipo = "atual — o snapshot mais recente de cada entidade para este corte"
    snaps = ret.get("snapshots") or []
    definicoes = [
        ("Retrato", esc(tipo)),
        ("Exercício", esc(f"{ex} — ano de execução dos Restos a Pagar: inscritos em 01/01/{ex}, de empenhos de anos "
                          "anteriores")),
        ("Corte", esc(f"{fm.data_br(df)} — data final do retrato: movimentos de 01/01/{ex} até essa data")),
        ("Coleta", esc(f"{coleta} — quando a API foi consultada")),
    ]
    if snaps:
        definicoes.append(("Snapshots usados", " ".join(f"<code>{esc(u)}</code>" for u in snaps)))
    nota = ""
    if ret.get("corte_posterior_a_coleta"):
        nota = ('<p class="nota">O corte é posterior à data da coleta: os valores vão só até o dia em que a API foi '
                "consultada.</p>")
    return (f'<section class="retrato"><p class="retrato-texto" id="retrato">{esc(ret["texto"])}</p>'
            f"{fm.lista_definicoes(definicoes)}{nota}"
            f'<p class="nota">{esc(ret["nota"])}</p></section>')


def _origem_indicador(v):
    pv = v["proveniencia"]
    campos = ", ".join(f"{c['rotulo']} ({c['campo_api']})" for c in v["campos"]) or "—"
    snaps = "<br>".join(f"<code>{esc(u)}</code>" for u in pv["snapshots"]) or "—"
    return fm.lista_definicoes([
        ("Fonte", esc(v["fonte"])),
        ("Cálculo", esc(v["formula"])),
        ("Campos da API", esc(campos)),
        ("Snapshots", snaps),
        ("Derivação", f"{esc(pv['derivacao_id'])} (hash <code>{esc(pv['derivacao_hash'])}</code>)"),
        ("Normalização", esc(pv["normalizacao_id"])),
    ])


def _origem_conjunto(prov, resumo="Origem do dado (snapshots usados)"):
    """<details> com a fonte, a derivacao e cada snapshot (uid, recorte, coleta, endpoint) de um conjunto de valores."""
    itens = "".join(f"<li><code>{esc(s['snapshot_uid'])}</code> — entidade {esc(s['entidade'])}, "
                    f"{esc(fm.data_br(s['data_inicial']))} a {esc(fm.data_br(s['data_final']))}, coletado em "
                    f"{esc(fm.data_br(s['coletada_em'], True))}, endpoint <code>{esc(s['endpoint'])}</code></li>"
                    for s in prov["snapshots"])
    d = prov["derivacao"]
    usada = prov.get("derivacao_usada", d["id"])
    hash_ = f" (hash <code>{esc(d['hash_resultado'])}</code>)" if usada == d["id"] else ""
    return (f'<details class="origem"><summary>{esc(resumo)}</summary><p>Fonte: {esc(F.ELOTECH["rotulo"])}. '
            f'Derivação {esc(usada)}{hash_}, normalização {esc(prov["normalizacao"]["id"])}.</p><ul>{itens}</ul></details>')


def _cartao(v):
    ident = f"ind-{v['id']}"
    if v["id"] == "registros":
        numero = fm.contagem(v["valor_c"], ident, "indisponível")
    else:
        numero = fm.valor(v["valor_c"], ident, "indisponível")
    classe = "indicador destaque" if v["id"] in DESTAQUES else "indicador"
    return (f'<div class="{classe}"><p class="rotulo">{esc(v["rotulo"])}</p><p class="numero">{numero}</p>'
            f'{fm.selo("elotech", v["natureza"], v["regras"], v["formula"])}'
            f'<details class="origem"><summary>Origem do dado</summary>{_origem_indicador(v)}</details></div>')


def _pdf(pdf, extracao=None):
    partes = [("Documento", esc(f"{pdf['rotulo']} — arquivo {pdf['id_arquivo']} de {fm.data_br(pdf['data_arquivo'])}")),
              ("Emitido em (rodapé)", esc(pdf["emitido_em"] or "não lido")),
              ("Snapshot do PDF", f"<code>{esc(pdf['snapshot_uid'])}</code> (coletado em {esc(fm.data_br(pdf['coletada_em'], True))})"),
              ("SHA-256 do PDF", f"<code>{esc(pdf['objeto_bruto_sha256'])}</code>")]
    if pdf.get("mesmo_pdf_coletado_tambem_em"):
        partes.append(("Mesmo PDF também em", " ".join(f"<code>{esc(u)}</code>" for u in pdf["mesmo_pdf_coletado_tambem_em"])))
    if extracao and extracao.get("registrada"):
        partes.append(("Extração", esc(f"{extracao['extrator_versao']} — {extracao['biblioteca_versao']}, em "
                                       f"{fm.data_br(extracao['extraida_em'], True)}, {extracao['valores']} valores")))
    return fm.lista_definicoes(partes)


def _explicacoes(situacao, lista):
    if situacao == "sem diferença":
        return '<span class="situacao situacao-ok">sem diferença</span>'
    itens = "".join(f"<li><strong>{esc(e['classe'])}</strong> ({esc(e['situacao'])}; {esc(e['status_evidencia'])}): "
                    f"{esc(e['texto'])} <span class=\"fonte-texto\">Fonte: {esc(e['fonte'])}</span></li>" for e in lista)
    classe = "situacao-nd" if situacao == "não determinada" else "situacao-exp"
    return (f'<span class="situacao {classe}">{esc(situacao)}</span>'
            + (f'<details class="explicacao"><summary>Explicação documentada</summary><ul>{itens}</ul></details>'
               if itens else ""))


# ---------------------------------------------------------------------------------------------- resumo
def resumo(p, q):
    try:
        sel = _selecao(p, q)
    except SemDados as e:
        return erro("Sem dados processados", str(e))
    ind = p.indicadores(sel["exercicio"], sel["data_final"], sel["entidade"], sel["em"])
    escopo = f"entidade {sel['entidade']}" if sel["entidade"] is not None else "Município"
    titulo = (f"Restos a Pagar — {escopo}, exercício {sel['exercicio']}, corte {fm.data_br(sel['data_final'])} "
              f"({_quando(sel)})")
    partes = [f"<h1>{esc(titulo)}</h1>", _avisos(sel["avisos"]),
              _formulario("/", sel, _entidades_do_catalogo(p)),
              '<p class="dica">' + fm.link("/evolucao", f"Ver a evolução de todos os cortes do exercício "
                                                        f"{sel['exercicio']}", exercicio=sel["exercicio"],
                                           entidade=sel["entidade"], em=sel["em"]) + " · "
              + fm.link("/composicao", "Ver a composição do saldo deste corte", exercicio=sel["exercicio"],
                        data_final=sel["data_final"], entidade=sel["entidade"], em=sel["em"]) + "</p>",
              _retrato(ind["retrato"])]
    unicas = [e for e in ind["entidades"] if e["entra_no_total"]]
    if ind["disponivel"] and unicas and all(e["situacao_do_dado"]["codigo"] == "sem_rp" for e in unicas):
        partes.append('<p class="aviso" id="sem-rp">Zero de verdade: a API devolveu zero registros de RP para '
                      "este escopo e corte (entidade existente, sem RP).</p>")
    if not ind["disponivel"]:
        partes.append('<section class="indisponivel" id="indisponivel"><h2>Dados indisponíveis para este recorte</h2>'
                      f'<p>{esc(ind["motivo_indisponivel"])}.</p><p>Nenhum valor é mostrado: ausência de dado não é '
                      "zero.</p></section>")
    else:
        v = ind["valores"]
        for nome, ids in GRUPOS:
            partes.append(f'<section class="grupo"><h2>{esc(nome)}</h2><div class="cartoes">'
                          + "".join(_cartao(v[i]) for i in ids) + "</div></section>")
    partes.append(_entidades_abrangidas(ind))
    partes.append(_aviso_retratos(ind, sel))
    if ind["disponivel"]:
        partes.append(_conferencia(ind, sel))
    partes.append(_avisos([a for a in ind["avisos"][1:]]))
    return titulo, "".join(partes)


def _entidades_abrangidas(ind):
    linhas = []
    for e in ind["entidades"]:
        s = e["snapshot"]
        fora = e["situacao_no_exercicio"] == "fora do catálogo oficial"
        situacao = e["situacao_do_dado"]["texto"]
        if e["retrato_mais_novo_nao_processado"]:
            situacao += "; há retrato mais novo coletado, ainda não processado"
        linhas.append([esc(e["entidade"]), esc(e["nome"] or ""), esc(e["situacao_no_exercicio"]),
                       f'<span id="situacao-{esc(e["entidade"])}">{esc(situacao)}</span>',
                       "sim" if e["entra_no_total"] else "não",
                       esc(fm.data_br(s["coletada_em"], True)) if s else "—",
                       fm.contagem(s["registros"]) if s and not fora else "—",
                       f"<code>{esc(s['snapshot_uid'])}</code>" if s else "—"])
    return ('<section class="grupo"><h2>Entidades abrangidas</h2>'
            + fm.tabela([("Entidade", None), ("Nome", None), ("Situação no catálogo do exercício", None),
                         ("Situação do dado", None), ("Entra no total", None), ("Coletado em", None),
                         ("Registros", None), ("Snapshot", "retrato usado (origem dos valores)")], linhas)
            + f'<p>{fm.link("/entidades", "Ver valores por entidade")}</p></section>')


def _aviso_retratos(ind, sel):
    varios = [e for e in ind["entidades"] if e.get("retratos_do_corte", 0) > 1]
    if not varios:
        return ""
    itens = "".join("<li>" + fm.link("/retratos", f"entidade {e['entidade']}: {e['retratos_do_corte']} retratos deste corte",
                                     entidade=e["entidade"], exercicio=sel["exercicio"], data_final=sel["data_final"])
                    + "</li>" for e in varios)
    return ('<section class="grupo"><h2>Mais de um retrato disponível</h2><p>O mesmo corte foi coletado mais de uma '
            "vez. Cada coleta é um retrato independente; os valores acima usam o mais recente (vigente).</p>"
            f"<ul>{itens}</ul></section>")


def _conferencia(ind, sel):
    c = ind.get("conferencia_rreo")
    cab = ('<section class="grupo conferencia" id="conferencia-rreo"><h2>Conferência com o RREO (publicação oficial '
           'independente)</h2><p class="fontes"><strong>Fonte primária:</strong> API Elotech · <strong>Fonte de '
           "reconciliação:</strong> RREO Anexo VII</p>")
    if not c:
        motivo = ind.get("reconciliacao") or "sem RREO transcrito para este corte e escopo"
        return cab + f"<p>{esc(motivo)}.</p></section>"
    linhas = [
        [esc(c["api"]["rotulo"]), fm.valor(c["api"]["valor_c"], "conf-api"), "API Elotech", fm.natureza("derivado")],
        [esc(c["rreo"]["rotulo"]), fm.valor(c["rreo"]["valor_c"], "conf-rreo"),
         esc(f"RREO Anexo VII — {c['rreo']['pdf']['rotulo']}, emitido em {c['rreo']['pdf']['emitido_em']}"),
         fm.natureza("publicado")],
        ["Diferença (API − RREO)", fm.valor(c["diferenca_c"], "conf-dif"), "—", fm.natureza("diferenca")],
    ]
    detalhe = fm.link("/reconciliacao", "Ver a reconciliação coluna a coluna deste documento",
                      exercicio=sel["exercicio"], data_final=sel["data_final"], escopo=c["escopo"])
    return (cab + fm.tabela([("", None), ("Valor", None), ("Fonte", None), ("Natureza", None)], linhas)
            + f'<p>Situação do dado: {esc(c["situacao_do_dado"]["texto"])}.</p>'
            + f'<p>Situação da diferença: {_explicacoes(c["situacao_da_diferenca"], c["explicacoes"])}</p>'
            + f'<p class="nota">{esc(c["nota"])}</p><p>{detalhe}</p></section>')


# ---------------------------------------------------------------------------------------------- evolucao
SERIE_COLUNAS = [("inscricao_total", "Inscrição (abertura)", "proc + aproc"),
                 ("pagamentos", "Pagamentos (acumulado)", "pagoProc + pagoAProc, de 01/01 até o corte"),
                 ("liquidacoes", "Liquidações (acumulado)", "liquidado, de 01/01 até o corte"),
                 ("cancelamentos", "Cancelamentos (acumulado)", "canceladoAProc + canceladoProc, de 01/01 até o corte"),
                 ("saldo_total", "Saldo no corte (S1)", "S1 v1")]


def evolucao(p, q):
    """Serie de todos os cortes do exercicio (Subetapa 05.2). Valores e diferencas vem prontos da camada painel."""
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
                   "href": fm.url("/", exercicio=sel["exercicio"], data_final=x["data_final"], entidade=sel["entidade"],
                                  em=sel["em"])} for x in serie]
        corpo.append('<section class="grupo"><h2>Saldo de RP no corte (S1)</h2>'
                     + grafico.barras("graf-s1", f"Saldo de RP (S1) por corte — exercício {sel['exercicio']}, {escopo}",
                                      "Barras por corte; corte sem valor aparece como lacuna tracejada.", pontos)
                     + "</section>")
    corpo.append(_tabela_serie(serie, sel))
    corpo.append(_tabela_diferencas(serie, sel))
    return titulo, "".join(corpo)


def _situacao_curta(texto):
    """Forma curta da situacao para tabelas: o texto antes de ':' e de ' (' (o completo vai como dica)."""
    return texto.split(":")[0].split(" (")[0]


def _celula_situacao(x):
    """Forma curta da situacao (antes de ':'), com o texto completo como dica; o motivo detalhado esta na celula ao
    lado. Os rotulos (ex.: corte posterior a coleta) aparecem sempre por inteiro."""
    texto = _situacao_curta(x["situacao"]["texto"]) + "".join(f"; {rot}" for rot in x["rotulos"])
    return f'<span id="sit-{esc(x["data_final"])}" title="{esc(x["situacao"]["texto"])}">{esc(texto)}</span>'


def _tabela_serie(serie, sel):
    linhas = []
    for x in serie:
        df = x["data_final"]
        corte = fm.link("/", fm.data_br(df), exercicio=sel["exercicio"], data_final=df, entidade=sel["entidade"],
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


# ---------------------------------------------------------------------------------------------- serie entre exercicios
HISTORICO_COLUNAS = [("inscricao_total", "Inscrição (abertura)", "proc + aproc"),
                     ("pagamentos", "Pagamentos (até o corte)", "pagoProc + pagoAProc"),
                     ("cancelamentos", "Cancelamentos (até o corte)", "canceladoAProc + canceladoProc"),
                     ("saldo_total", "Saldo no corte (S1)", "S1 v1")]


def historico(p, q):
    """Serie por exercicio (Subetapa 05.3). Valores, diferencas e verificacoes vem prontos da camada painel."""
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
                   "href": fm.url("/", exercicio=x["exercicio"], data_final=x["data_final"], entidade=entidade, em=em)
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
        corte = (fm.link("/", fm.data_br(x["data_final"]), exercicio=ex, data_final=x["data_final"],
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


# ---------------------------------------------------------------------------------------------- composicao
TOTAL_NA_LISTA = {"inscricao_processada": "Processado (inscrito)", "inscricao_nao_processada": "Não processado (inscrito)"}


def composicao(p, q):
    """Composicao da inscricao e do saldo do corte (Subetapa 05.4). Grupos, totais e fechamentos vem prontos da camada
    painel; a dimensao que nao fecha com o total do corte nao e exibida."""
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


# ---------------------------------------------------------------------------------------------- variacao entre cortes
def variacao(p, q):
    """Investigacao da variacao entre dois cortes do mesmo exercicio (Subetapa 05.5). Variacao, contribuicoes, grupos,
    classes, fechamentos e paginacao vem prontos da camada painel."""
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
    if posterior == cortes[0]:
        sel["avisos"].append("Não há corte anterior ao primeiro do exercício: mostrado o par dos dois primeiros cortes.")
        posterior = cortes[1]
    if anterior is None or anterior not in cortes or anterior >= posterior:
        if anterior is not None:
            sel["avisos"].append("O corte anterior precisa ser um corte do exercício anterior ao posterior: mostrado o "
                                 "corte imediatamente anterior.")
        anterior = cortes[cortes.index(posterior) - 1]
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
    partes = []
    for nome, df in (("anterior", sel["anterior"]), ("posterior", sel["posterior"])):
        lado = x[nome]
        if lado is None:
            partes.append(f"<li>{esc(nome.capitalize())}: ausente do corte.</li>")
            continue
        pv, c = lado["proveniencia"], x["chave"]
        detalhe = fm.link("/empenho", "detalhe", entidade=c["entidade"], anoempenho=c["anoempenho"], empenho=c["empenho"],
                          exercicio=sel["exercicio"], data_final=df, em=sel["em"])
        partes.append(f"<li>{esc(nome.capitalize())}: snapshot <code>{esc(pv['snapshot_uid'])}</code>, página "
                      f"{esc(pv['resposta_ordem'])}, posição {esc(pv['indice_no_content'])}, objeto bruto "
                      f"<code>{esc(pv['objeto_bruto_sha256'][:16])}…</code> ({detalhe})</li>")
    return f'<details class="origem"><summary>origem</summary><ul>{"".join(partes)}</ul></details>'


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


# ---------------------------------------------------------------------------------------------- empenho nos cortes
def empenho_cortes(p, q):
    """Um empenho em todos os cortes do exercicio (Subetapa 05.5; contrato M-12). Valores vem prontos da camada painel."""
    entidade, ano, numero = q.inteiro("entidade", 1, 10 ** 6), q.inteiro("anoempenho", 1900, 2999), q.inteiro("empenho", 0, 10 ** 9)
    exercicio = q.inteiro("exercicio", 1900, 2999)
    if None in (entidade, ano, numero, exercicio):
        return erro("Empenho nos cortes", "Informe entidade, ano do empenho, número do empenho e exercício.")
    em = q.data("em")
    h = p.historico_empenho(entidade, ano, numero, exercicio, em)
    titulo = (f"Empenho {numero}/{ano} — entidade {entidade}, exercício {exercicio}: todos os cortes "
              f"({_quando({'em': em})})")
    campos = h["campos"]
    linhas = []
    for x in h["cortes"]:
        df = x["data_final"]
        corte = fm.link("/empenho", fm.data_br(df), entidade=entidade, anoempenho=ano, empenho=numero, exercicio=exercicio,
                        data_final=df, em=em) if x["presente"] else esc(fm.data_br(df))
        situacao = _situacao_curta(x["situacao"]["texto"]) + "".join(f"; {rot}" for rot in x["rotulos"])
        coleta = esc(fm.data_br(x["retrato"]["coletado_de"], True)) if x["retrato"] else "—"
        if not x["tem_valor"]:
            linhas.append([corte, f'<span title="{esc(x["situacao"]["texto"])}">{esc(situacao)}</span>', "—",
                           f'<td colspan="{len(campos) + 2}" class="sem-valor" id="emp-lacuna-{esc(df)}">sem valor — '
                           f'{esc(x["motivo_indisponivel"] or x["situacao"]["texto"])}</td>'])
            continue
        if not x["presente"]:
            linhas.append([corte, esc(situacao), coleta,
                           f'<td colspan="{len(campos) + 2}" class="sem-valor" id="emp-ausente-{esc(df)}">'
                           f'{esc(x["motivo_ausencia"])}</td>'])
            continue
        for i, o in enumerate(x["ocorrencias"], 1):
            rotulo = situacao + (f"; ocorrência {i} de {len(x['ocorrencias'])}" if len(x["ocorrencias"]) > 1 else "")
            pv = o["proveniencia"]
            origem = (f'<details class="origem"><summary>origem</summary>Snapshot <code>{esc(pv["snapshot_uid"])}</code>, '
                      f'página {esc(pv["resposta_ordem"])}, posição {esc(pv["indice_no_content"])}, objeto bruto '
                      f'<code>{esc(pv["objeto_bruto_sha256"])}</code>.</details>')
            linhas.append([corte, esc(rotulo), coleta]
                          + [fm.valor(o["valores"][c["coluna"]], f"emp-{df}-{i}-{c['coluna']}") for c in campos]
                          + [esc(NOME_CATEGORIA.get(o["categoria"], o["categoria"])), origem])
    cab = ([("Corte", "abre o detalhe do empenho no corte"), ("Situação", None), ("Coletado em", None)]
           + [(c["rotulo"], (c["campo_api"] or "derivado") + f" — {fm.NATUREZA.get(c['natureza'], c['natureza'])}")
              for c in campos]
           + [("Categoria", "CAT v1"), ("Origem", None)])
    d = h["derivacao"]
    corpo = [f"<h1>{esc(titulo)}</h1>",
             f'<p class="nota">{esc(_nota_do_retrato(em))} Corte sem valor para a entidade aparece com o motivo; corte em que o '
             "empenho não aparece, como “empenho ausente deste corte”. Nada é calculado aqui: são os valores do registro "
             "em cada corte.</p>",
             fm.selo("elotech", "da_fonte", None, "campos da API; S1 derivado pela regra S1 v1"),
             fm.tabela(cab, linhas, "tabela empenho-cortes"),
             f'<p class="nota">Derivação {esc(d["id"])} (hash <code>{esc(d["hash_resultado"][:16])}…</code>), '
             f'normalização {esc(h["normalizacao_id"])}.</p>']
    if h["nota"]:
        corpo.append(f'<p class="aviso">{esc(h["nota"])}</p>')
    return titulo, "".join(corpo)


def _nota_do_retrato(em):
    """Frase do retrato para a linha do tempo de um empenho (estado atual ou 'como estava em')."""
    if em:
        return f"Como a base estava em {fm.data_br(em)}: só snapshots coletados até essa data."
    return "Cada corte é o estado atual da base para aquele corte, na data da coleta, não o que se sabia na época."


# ---------------------------------------------------------------------------------------------- entidades
def entidades(p, q):
    try:
        sel = _selecao(p, q, com_entidade=False)
    except SemDados as e:
        return erro("Sem dados processados", str(e))
    r = p.entidades_do_corte(sel["exercicio"], sel["data_final"], sel["em"])
    titulo = (f"Entidades — exercício {sel['exercicio']}, corte {fm.data_br(sel['data_final'])} "
              f"({_quando(sel)})")
    linhas = []
    for l in r["linhas"]:
        situacao = l["situacao_do_dado"]["texto"]
        if l["retrato_mais_novo_nao_processado"]:
            situacao += "; há retrato mais novo coletado, ainda não processado"
        base = [esc(l["entidade"]), esc(l["nome"] or ""), esc(sel["exercicio"]), esc(l["situacao_no_exercicio"]),
                f'<span id="situacao-{esc(l["entidade"])}">{esc(situacao)}</span>']
        v = l["valores"]
        if v is None:
            base.append(f'<td colspan="5" class="sem-valor" id="sem-valor-{esc(l["entidade"])}">'
                        f'{esc(l["situacao_do_valor"])} — sem valor</td>')
        else:
            ent = l["entidade"]
            base += [fm.valor(v["inscricao_processada"], f"ent-{ent}-proc"),
                     fm.valor(v["inscricao_nao_processada"], f"ent-{ent}-aproc"),
                     fm.valor(v["inscricao_total"], f"ent-{ent}-total"),
                     fm.valor(v["saldo_total"], f"ent-{ent}-s1"),
                     fm.contagem(v["registros"], f"ent-{ent}-registros")]
        retratos = l["retratos_do_corte"]
        base.append(fm.link("/retratos", str(retratos), entidade=l["entidade"], exercicio=sel["exercicio"],
                            data_final=sel["data_final"]) if retratos else "0")
        if v is not None:
            pv = l["proveniencia"]
            base.append(f'<details class="origem"><summary>origem</summary><code>{esc(l["snapshot"]["snapshot_uid"])}</code> '
                        f'— coletado em {esc(fm.data_br(l["snapshot"]["coletada_em"], True))}; derivação '
                        f'{esc(pv["derivacao_id"])}, normalização {esc(pv["normalizacao_id"])}</details>')
        else:
            base.append("—")
        linhas.append(base)
    tabela = fm.tabela([("Entidade", None), ("Nome", None), ("Exercício", None), ("Situação no catálogo", None),
                        ("Situação do dado", None), ("Processado (inscrito)", "proc na abertura"), ("Não processado (inscrito)", "aproc na abertura"),
                        ("Total inscrito", "proc + aproc"), ("Saldo no corte (S1)", "S1 v1"),
                        ("Empenhos", "registros no snapshot"), ("Retratos", "coletas deste corte"),
                        ("Origem", "snapshot e derivação dos valores da linha")], linhas)
    corpo = [f"<h1>{esc(titulo)}</h1>", _avisos(sel["avisos"]), _formulario("/entidades", sel), _retrato(r["retrato"]),
             fm.selo("elotech", "derivado", [{"codigo": "S1", "versao": 1, "situacao": "operacional"}],
                     "somas dos campos da API por entidade"),
             tabela, f'<p class="nota">{esc(r["nota"])}</p>']
    if not r["municipio_disponivel"]:
        corpo.append(f'<p class="aviso">Total do Município indisponível neste corte: {esc(r["motivo_indisponivel"])}.</p>')
    return titulo, "".join(corpo)


# ---------------------------------------------------------------------------------------------- empenhos
def _filtros_empenho(q):
    return {"categoria": q.escolha("categoria", CATEGORIAS), "fonte_recurso": q.inteiro("fonte_recurso", 0, 10 ** 9),
            "programatica": q.texto("programatica", 28), "tipo_credor": q.escolha("tipo_credor", publico.TIPOS_CREDOR),
            "cnpj": q.texto("cnpj", 18), "anoempenho": q.inteiro("anoempenho", 1900, 2999),
            "empenho": q.inteiro("empenho", 0, 10 ** 9), "faixa": q.escolha("faixa", FAIXAS),
            "orgao": q.texto("orgao", 20), "funcao": q.texto("funcao", 20), "programa": q.texto("programa", 20),
            "elemento": q.texto("elemento", 20),
            "sem_classificacao": q.escolha("sem_classificacao", DIMENSOES_ORCAMENTARIAS)}


def _mais_filtros(filtros):
    """Filtros da composicao (05.4): faixa e classificacao orcamentaria, num bloco recolhivel (aberto quando em uso)."""
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


# ---------------------------------------------------------------------------------------------- detalhe de empenho
def empenho(p, q):
    entidade, ano, numero = q.inteiro("entidade", 1, 10 ** 6), q.inteiro("anoempenho", 1900, 2999), q.inteiro("empenho", 0, 10 ** 9)
    exercicio = q.inteiro("exercicio", 1900, 2999)
    if None in (entidade, ano, numero, exercicio):
        return erro("Empenho", "Informe entidade, ano do empenho, número do empenho e exercício.")
    em = q.data("em")
    d = p.detalhe_empenho(entidade, ano, numero, exercicio, q.data("data_final"), em)
    titulo = f"Empenho {numero}/{ano} — entidade {entidade}, exercício {exercicio}"
    if d.get("data_final"):
        titulo += f", corte {fm.data_br(d['data_final'])} ({_quando({'em': em})})"
    nos_cortes = ('<p class="dica">' + fm.link("/empenho/cortes", "Ver este empenho em todos os cortes do exercício",
                                               entidade=entidade, anoempenho=ano, empenho=numero, exercicio=exercicio, em=em)
                  + "</p>")
    if not d["encontrado"]:
        return titulo, (f"<h1>{esc(titulo)}</h1>" + nos_cortes + _retrato(d.get("retrato")) +
                        f'<section class="indisponivel" id="indisponivel"><p>{esc(d["motivo_indisponivel"])}.</p></section>')
    corpo = [f"<h1>{esc(titulo)}</h1>", nos_cortes, _retrato(d["retrato"])]
    for i, o in enumerate(d["ocorrencias"], 1):
        if len(d["ocorrencias"]) > 1:
            corpo.append(f"<h2>Ocorrência {i} de {len(d['ocorrencias'])} no snapshot</h2>")
        corpo.append(_detalhe_ocorrencia(o))
    if d.get("nota"):
        corpo.append(f'<p class="nota">{esc(d["nota"])}</p>')
    corpo.append(_movimentacao(d["movimentacao"]))
    return titulo, "".join(corpo)


def _detalhe_ocorrencia(o):
    c, dv, cred = o["campos"], o["derivados"], o["credor"]
    ident = fm.lista_definicoes([
        ("Entidade", esc(c["entidade"]["valor"])),
        ("Ano do empenho", esc(c["anoempenho"]["valor"])),
        ("Número do empenho", esc(c["empenho"]["valor"])),
        ("Empenho/ano (como a API devolve)", esc(c["empenho_exercicio"]["valor"])),
        ("Data de emissão", esc(fm.data_br(c["data_emissao"]["valor"]))),
        ("Credor", esc(f"{cred['nome_publico'] or '—'} ({cred['tipo']})")),
        ("Programação orçamentária", f'<code>{esc(c["programatica"]["valor"] or "")}</code>'),
        ("Fonte de recurso", esc(f"{c['fonte_recurso']['valor']} — {c['descricao_fonte']['valor'] or ''}")),
    ])
    valores = []
    for col in ("proc_c", "aproc_c", "pago_proc_c", "pago_proc_estornado_c", "pago_aproc_c", "pago_aproc_estornado_c",
                "liquidado_c", "cancelado_aproc_c", "cancelado_proc_c", "retencao_c"):
        x = c[col]
        valores.append([esc(x["rotulo"]), f"<code>{esc(x['campo_api'])}</code>", fm.valor(x["valor"], f"campo-{col}"),
                        fm.natureza(x["natureza"]), esc(x["significado"]), esc(x["status_semantica"])])
    classificacao, analise = [], []
    for col, x in dv.items():
        if col.endswith("_c"):
            v = fm.valor(x["valor"], f"derivado-{col}")
        elif col == "categoria":
            v = esc(NOME_CATEGORIA.get(x["valor"], x["valor"]))
        else:
            v = esc(x["valor"] if x["valor"] is not None else "—")
        (classificacao if x["natureza"] == "derivado" else analise).append(
            [esc(x["rotulo"]), v, esc(x["formula"]),
             esc(f"{x['regra']} ({fm.SITUACAO_REGRA.get(x['situacao_da_regra'], x['situacao_da_regra'])})"),
             fm.natureza(x["natureza"])])
    outros = fm.lista_definicoes([(c[k]["rotulo"] + f" ({c[k]['campo_api']})", esc(c[k]["valor"] if c[k]["valor"] is not None else "não veio na API"))
                                  for k in ("orgao", "unidade", "funcao", "sub_funcao", "programa", "projeto", "elemento",
                                            "desdobra_desp", "sub_desdobramento")])
    partes = ['<section class="grupo"><h2>Identificação</h2>', ident, "</section>",
              '<section class="grupo"><h2>Valores (API Elotech)</h2>', fm.selo("elotech", "da_fonte"),
              fm.tabela([("Campo", None), ("Nome na API", None), ("Valor", None), ("Natureza", None),
                         ("Significado (Etapa 02)", None), ("Status", None)], valores), "</section>",
              '<section class="grupo"><h2>Classificação e saldos (valores derivados, regra operacional)</h2>',
              fm.tabela([("Item", None), ("Valor", None), ("Fórmula", None), ("Regra (situação)", None),
                         ("Natureza", None)], classificacao), "</section>"]
    if analise:
        partes += ['<section class="grupo analise" id="analise-experimental"><h2>ANÁLISE EXPERIMENTAL (não oficial)</h2>',
                   '<p class="nota">Calculado por regra experimental ou não recomendada. Não é dado da fonte, não é '
                   "valor publicado e não entra em nenhum indicador.</p>",
                   fm.tabela([("Item", None), ("Valor", None), ("Fórmula", None), ("Regra (situação)", None),
                              ("Natureza", None)], analise), "</section>"]
    partes.append(f'<section class="grupo"><h2>Classificação orçamentária</h2>{outros}</section>')
    if o["par_espelhado"]:
        partes.append(_par(o["par_espelhado"]))
    partes.append(_origem_registro(o["proveniencia"]))
    return "".join(partes)


def _par(par):
    a, b = par["a"], par["b"]
    return ('<section class="grupo"><h2>Par espelhado (identificação PAR-24 v1)</h2>'
            + fm.lista_definicoes([
                ("Este registro é o lado", esc(par["este_registro_e_o_lado"])),
                ("Lado A (cópia)", esc(f"entidade {a['entidade']}, empenho {a['empenho']}/{a['anoempenho']}") + ", inscrito "
                 + fm.valor(a["inscrito_c"])),
                ("Lado B (original)", esc(f"entidade {b['entidade']}, empenho {b['empenho']}/{b['anoempenho']}") + ", inscrito "
                 + fm.valor(b["inscrito_c"])),
                ("Relação da inscrição", esc(par["relacao_inscricao"])),
                ("Lado com execução", esc(par["lado_com_execucao"])),
            ]) + f'<p class="nota">{esc(par["nota"])}</p></section>')


def _origem_registro(pv):
    s = pv["snapshot"]
    parametros = ", ".join(f"{k}={v}" for k, v in sorted(s["parametros"].items()))
    return ('<section class="grupo origem-dado" id="origem"><details><summary>Origem do dado (fonte, endpoint, '
            "snapshot, hash)</summary>"
            + fm.lista_definicoes([
                ("Fonte", esc(F.ELOTECH["rotulo"])),
                ("Endpoint", f"<code>{esc(s['endpoint'])}</code>"),
                ("Parâmetros", f"<code>{esc(parametros)}</code>"),
                ("Exercício", esc(s["exercicio"])),
                ("Entidade", esc(s["entidade"])),
                ("Data inicial e final", esc(f"{fm.data_br(s['data_inicial'])} a {fm.data_br(s['data_final'])}")),
                ("Coletado em", esc(f"{fm.data_br(s['coletada_em'], True)} (carimbo: {s['origem_carimbo']})")),
                ("Snapshot", f"<code>{esc(s['snapshot_uid'])}</code>"),
                ("Manifesto", f"<code>{esc(s['manifesto'])}</code>"),
                ("Resposta HTTP", f"<code>{esc(pv['resposta_url'])}</code> (página {esc(pv['resposta_ordem'])}, posição "
                                  f"{esc(pv['indice_no_content'])} no content)"),
                ("Objeto bruto (SHA-256)", f"<code>{esc(pv['objeto_bruto_sha256'])}</code>"),
                ("Normalização / derivação", esc(f"{pv['normalizacao_id']} / {pv['derivacao_id']}")),
            ]) + "</details></section>")


def _movimentacao(m):
    if not m.get("coletada"):
        return f'<section class="grupo"><h2>Movimentações</h2><p>{esc(m.get("nota") or "não coletada")}.</p></section>'
    linhas = [[esc(fm.data_br(l["data"])), esc(l["tipo_lancamento"]), esc(l["descricao"]), fm.valor(l["valor_c"]),
               esc(l["efeito"] or "—"), esc(l["liquidacao_referida"] or "—")] for l in m["lancamentos"]]
    s = m["snapshot"]
    return ('<section class="grupo"><h2>Movimentações</h2>'
            + fm.selo("elotech", "da_fonte")
            + f'<p class="nota">Snapshot <code>{esc(s["snapshot_uid"])}</code>, coletado em '
            + f'{esc(fm.data_br(s["coletada_em"], True))}, endpoint <code>{esc(s["endpoint"])}</code>. Efeito e '
            + "liquidação referida são interpretação (MOV-REF v1, operacional).</p>"
            + fm.tabela([("Data", None), ("Tipo", None), ("Descrição", None), ("Valor", None), ("Efeito", None),
                         ("Liquidação referida", None)], linhas) + "</section>")


# ---------------------------------------------------------------------------------------------- retratos
def retratos(p, q):
    entidade, exercicio, df = q.inteiro("entidade", 1, 10 ** 6), q.inteiro("exercicio", 1900, 2999), q.data("data_final")
    if None in (entidade, exercicio, df):
        itens = "".join("<li>" + fm.link("/retratos", f"entidade {x['entidade']} — exercício {x['exercicio']}, corte "
                                                      f"{fm.data_br(x['data_final'])}: {x['retratos']} retratos",
                                          entidade=x["entidade"], exercicio=x["exercicio"], data_final=x["data_final"])
                        + "</li>" for x in p.retratos_multiplos())
        return "Retratos", ("<h1>Retratos</h1><p>Cada coleta de um corte é um retrato independente e nenhum é apagado. "
                            "Cortes com mais de um retrato:</p>" + (f"<ul>{itens}</ul>" if itens else "<p>nenhum.</p>"))
    r = p.retratos(entidade, exercicio, df)
    titulo = f"Retratos — entidade {entidade}, exercício {exercicio}, corte {fm.data_br(df)}"
    linhas = []
    for x in r["retratos"]:
        v, dif = x["valores"], x["diferenca_para_o_anterior"]
        comparar = "—"
        if dif:
            comparar = fm.link("/comparar", "comparar com o anterior", a=dif["anterior"], b=x["snapshot_uid"])
        linhas.append([f"<code>{esc(x['snapshot_uid'])}</code>", esc(fm.data_br(x["coletada_em"], True)),
                       esc(x["origem_carimbo"]), esc(x["status"]), "sim" if x["processado"] else "não",
                       fm.contagem(x["registros"], ausencia="—"),
                       fm.valor(v["inscricao_total_c"]) if v else "—", fm.valor(v["saldo_total_c"]) if v else "—",
                       (fm.valor(dif["saldo_total_c"]) + f" ({esc(dif['registros'])} registros)") if dif else "—",
                       ("sim" if dif["bytes_identicos"] else "não") if dif else "—",
                       "vigente" if x["vigente"] else "", comparar])
    tabela = fm.tabela([("Snapshot", None), ("Coletado em", None), ("Carimbo", "origem do horário"), ("Status", None),
                        ("Processado", None), ("Registros", None), ("Total inscrito", "proc + aproc"),
                        ("Saldo (S1)", "S1 v1"), ("Diferença de saldo para o anterior", None),
                        ("Bytes idênticos ao anterior", None), ("", None), ("", None)], linhas)
    return titulo, (f"<h1>{esc(titulo)}</h1><p>{esc(r['nota'])}</p>"
                    + fm.selo("elotech", "derivado", [{"codigo": "S1", "versao": 1, "situacao": "operacional"}],
                              "somas por retrato; diferença = retrato − anterior")
                    + tabela)


def comparar(p, q):
    a, b = q.snapshot("a"), q.snapshot("b")
    if not a or not b:
        return erro("Comparar retratos", "Informe os dois snapshots (a e b).")
    r = p.comparar_retratos(a, b)
    titulo = "Comparação de dois retratos do mesmo corte"
    c = r["contagens"]
    grupos = [[esc(g), fm.valor(v["antes"]), fm.valor(v["depois"]), fm.valor(v["diferenca"])]
              for g, v in r["impacto_financeiro_por_grupo"].items()]
    alterados = [[esc("/".join(str(x) for x in alt["chave"])),
                  esc("; ".join(f"{x['campo']}: {x['antes']} → {x['depois']}" for x in alt["campos"]))]
                 for alt in r["alterados"][:50]]
    corpo = (f"<h1>{esc(titulo)}</h1>" + fm.selo("elotech", "diferenca")
             + fm.lista_definicoes([
                 ("Corte", esc(f"entidade {r['corte']['entidade']}, exercício {r['corte']['exercicio']}, "
                               f"{fm.data_br(r['corte']['data_inicial'])} a {fm.data_br(r['corte']['data_final'])}")),
                 ("Anterior", f"<code>{esc(r['anterior']['snapshot_uid'])}</code> — {esc(fm.data_br(r['anterior']['coletada_em'], True))}, "
                              f"{esc(r['anterior']['registros'])} registros"),
                 ("Posterior", f"<code>{esc(r['posterior']['snapshot_uid'])}</code> — {esc(fm.data_br(r['posterior']['coletada_em'], True))}, "
                               f"{esc(r['posterior']['registros'])} registros"),
                 ("Bytes idênticos", "sim" if r["bytes_identicos"] else "não"),
                 ("Registros", esc(f"{c['novos']} novos, {c['removidos']} removidos, {c['alterados']} alterados, "
                                   f"{c['comuns']} em comum")),
                 ("Saldo S1", f"{fm.valor(r['saldo_s1']['antes'])} → {fm.valor(r['saldo_s1']['depois'])} "
                              f"(diferença {fm.valor(r['saldo_s1']['diferenca'])})")])
             + "<h2>Impacto por grupo</h2>"
             + fm.tabela([("Grupo", None), ("Antes", None), ("Depois", None), ("Diferença", None)], grupos)
             + ("<h2>Registros alterados (até 50)</h2>" + fm.tabela([("Chave", None), ("Campos", None)], alterados)
                if alterados else "<p>Nenhum registro alterado.</p>")
             + '<p class="nota">A comparação relata fatos, não causas. Campos do credor aparecem como [restrito].</p>')
    return titulo, corpo


# ---------------------------------------------------------------------------------------------- reconciliacao
def reconciliacao(p, q):
    em = q.data("em")
    exercicio, df, escopo = q.inteiro("exercicio", 1900, 2999), q.data("data_final"), q.escolha("escopo", ("entidade", "consolidado"))
    cab = ('<p class="fontes"><strong>Fonte primária:</strong> API Elotech (Portal da Transparência de Ponta Grossa) · '
           "<strong>Fonte de reconciliação:</strong> RREO Anexo VII (PDF publicado pelo Município)</p>"
           '<p class="nota">A diferença é registro: o valor da API nunca é trocado pelo do RREO. O lado API é a projeção '
           "dos registros nas colunas do RREO pela regra indicada (RREO-COL v1 não recomendada, v2 experimental), por "
           "isso sai como valor analítico; o indicador principal não depende dela.</p>")
    if exercicio is not None and df is not None and escopo is not None:
        return _reconciliacao_documento(p, q, exercicio, df, escopo, em, cab)
    docs = p.documentos_rreo(em)
    linhas = []
    for d in docs["documentos"]:
        dif = ", ".join(f"{k}: {v} de {d['colunas_comparadas'][k]}" for k, v in sorted(d["colunas_com_diferenca"].items()))
        linhas.append([fm.link("/reconciliacao", d["periodo"], exercicio=d["exercicio"], data_final=d["data_final"],
                               escopo=d["escopo"], em=em),
                       esc(d["escopo"] + (f" (entidade {d['entidade']})" if d["entidade"] else "")),
                       esc(d["pdf"]["rotulo"]), esc(d["pdf"]["emitido_em"] or "—"), esc(dif)])
    sem = "".join(f"<li>{esc(s['exercicio'])} — {esc(s['rotulo'])}: {esc((s['extracao'] or {}).get('erro') or 'sem valores')}"
                  "</li>" for s in docs["pdfs_sem_valores_transcritos"])
    corpo = ["<h1>Reconciliação com o RREO</h1>", cab,
             "<h2>Documentos conciliados</h2>",
             fm.tabela([("Período", None), ("Escopo", None), ("Documento", None), ("Emitido em", None),
                        ("Colunas com diferença", None)], linhas),
             ("<h2>PDFs sem valores transcritos pelo extrator</h2><ul>" + sem + "</ul>") if sem else "",
             _coerencia(p)]
    return "Reconciliação com o RREO", "".join(corpo)


def _reconciliacao_documento(p, q, exercicio, df, escopo, em, cab):
    somente = q.marcado("somente_diferencas")
    versao = q.escolha("regra", ("RREO-COL v1", "RREO-COL v2"))
    r = p.reconciliacao(exercicio, df, escopo, somente, em)
    linhas_r = [x for x in r["linhas"] if versao is None or x["regra_agregacao"]["regra"] == versao]
    titulo = f"Reconciliação — {escopo}, exercício {exercicio}, corte {fm.data_br(df)}"
    if not linhas_r:
        return titulo, (f"<h1>{esc(titulo)}</h1>{cab}<p>Sem RREO transcrito para este corte e escopo"
                        + (" (ou sem diferença)" if somente else "") + ".</p>")
    primeiro = linhas_r[0]
    linhas = []
    for x in linhas_r:
        ident = f"rec-{x['regra_agregacao']['regra'].split()[-1]}-{x['coluna']}"      # ex.: rec-v2-h
        linhas.append([f'<strong>{esc(x["coluna"])}</strong> <small>{esc(F.COLUNAS_RREO.get(x["coluna"], ""))}</small>',
                       fm.situacao_regra(x["regra_agregacao"]["regra"], x["regra_agregacao"]["situacao"]),
                       fm.valor(x["api_c"], ident + "-api") + " " + fm.natureza(x["api_natureza"]),
                       fm.valor(x["rreo_c"], ident + "-rreo") + " " + fm.natureza(x["rreo_natureza"]),
                       fm.valor(x["diferenca_c"], ident + "-dif"),
                       _explicacoes(x["situacao_da_diferenca"], x["explicacoes"])])
    filtro = (f'<form class="filtros" method="get" action="/reconciliacao">'
              f'<input type="hidden" name="exercicio" value="{esc(exercicio)}">'
              f'<input type="hidden" name="data_final" value="{esc(df)}">'
              f'<input type="hidden" name="escopo" value="{esc(escopo)}">'
              + (f'<input type="hidden" name="em" value="{esc(em)}">' if em else "")
              + f'<label>Regra <select name="regra"><option value="">as duas</option>'
                f'{fm.opcoes([("RREO-COL v1", "RREO-COL v1"), ("RREO-COL v2", "RREO-COL v2")], versao or "")}</select></label>'
              + f'<label><input type="checkbox" name="somente_diferencas" value="1"{" checked" if somente else ""}> só '
                "diferenças</label><button type=\"submit\">Filtrar</button></form>")
    corpo = (f"<h1>{esc(titulo)}</h1>{cab}"
             + fm.lista_definicoes([("Período", esc(primeiro["periodo"])),
                                    ("Escopo", esc(escopo + (f" — entidade {primeiro['entidade']}" if primeiro["entidade"] else
                                                             " — Município"))),
                                    ("Snapshots da API", " ".join(f"<code>{esc(u)}</code>" for u in primeiro["snapshots_api"]))])
             + _pdf(primeiro["pdf"], primeiro["extracao"]) + filtro
             + fm.tabela([("Coluna do RREO", None), ("Regra de agregação", None),
                          ("API Elotech projetada na coluna (análise)", "registros da API agregados pela regra ao lado"),
                          ("RREO (valor publicado)", None), ("Diferença (API − RREO)", None),
                          ("Situação e explicação", None)], linhas, "tabela reconciliacao")
             + f'<p>{fm.link("/reconciliacao", "« todos os documentos", em=em)}</p>')
    return titulo, corpo


def _coerencia(p):
    coe = p.coerencia_entre_publicacoes()
    ultimo = {}
    for x in coe["comparacoes"]:   # uma linha por (escopo, A): a publicacao mais recente de A+1
        k = (x["escopo"], x["de"])
        if k not in ultimo or x["data_final_para"] > ultimo[k]["data_final_para"]:
            ultimo[k] = x
    linhas = []
    for (escopo, de), x in sorted(ultimo.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        linhas.append([esc(escopo), esc(f"{de} → {x['para']}"),
                       fm.valor(x["rreo_L_de_c"]) + f" <small>({esc(x['emitido_de'])})</small>",
                       fm.valor(x["rreo_a_mais_f_para_c"]) + f" <small>({esc(x['emitido_para'])})</small>",
                       fm.valor(x["diferenca_c"], f"coe-{escopo}-{de}"),
                       fm.valor(x["api_s1_de_c"], ausencia="—"), fm.valor(x["api_a_mais_f_para_c"], ausencia="—"),
                       _explicacoes(x["situacao_da_diferenca"], x["explicacoes"]), _origem_coerencia(x)])
    return ('<section class="grupo" id="coerencia"><h2>Coerência entre publicações</h2>'
            "<p>O saldo que fecha um exercício no RREO de dezembro (coluna L) deveria ser o RP de exercícios anteriores "
            "que abre o seguinte ((a)+(f) do RREO de A+1). Ao lado, os mesmos agregados calculados hoje com a API.</p>"
            + fm.tabela([("Escopo", None), ("Exercícios", None), ("RREO: L de A", None), ("RREO: (a)+(f) de A+1", None),
                         ("Diferença entre publicações", None), ("API hoje: saldo S1 de A", None),
                         ("API hoje: (a)+(f) de A+1", None), ("Situação", None), ("Origem", None)], linhas)
            + f'<p class="nota">{esc(coe["limitacao"])}</p></section>')


def _origem_coerencia(x):
    pdfs = " e ".join(f"<code>{esc(u)}</code>" for u in x["pdfs"])
    api = [u for lado in ("de", "para") for u in (x["api_snapshots"][lado] or [])]
    return (f'<details class="origem"><summary>origem</summary>PDFs do RREO (snapshots): {pdfs}. Snapshots da API: '
            + (" ".join(f"<code>{esc(u)}</code>" for u in api) or "—") + ".</details>")


# ---------------------------------------------------------------------------------------------- pares (tecnico)
def pares(p, q):
    try:
        sel = _selecao(p, q, com_entidade=False)
    except SemDados as e:
        return erro("Sem dados processados", str(e))
    r = p.pares(sel["exercicio"], sel["data_final"], sel["em"])
    titulo = f"Técnico: pares espelhados — exercício {sel['exercicio']}, corte {fm.data_br(sel['data_final'])}"
    res = r.get("resumo", {})
    resumo_html = fm.lista_definicoes([
        ("Pares", fm.contagem(res.get("pares", 0), "pares-total")),
        ("Relação da inscrição", esc(", ".join(f"{k}: {v}" for k, v in sorted(res.get("relacao", {}).items())) or "—")),
        ("Lado com execução", esc(", ".join(f"{k}: {v}" for k, v in sorted(res.get("lado_com_execucao", {}).items())) or "—")),
        ("Ano do empenho (cópia)", esc(", ".join(f"{k}: {v}" for k, v in sorted(res.get("anoempenho", {}).items())) or "—")),
    ])
    linhas = [[esc(f"{x['a']['entidade']} / {x['a']['empenho']}/{x['a']['anoempenho']}"), fm.valor(x["a"]["inscrito_c"]),
               esc(f"{x['b']['entidade']} / {x['b']['empenho']}/{x['b']['anoempenho']}"), fm.valor(x["b"]["inscrito_c"]),
               "sim" if x["mesma_inscricao"] else "não", esc(x["relacao_inscricao"]), esc(x["lado_com_execucao"])]
              for x in r.get("pares", [])[:500]]
    corpo = (f"<h1>{esc(titulo)}</h1>" + _formulario("/pares", sel)
             + '<p class="aviso">Área técnica. Identificação de pares pela regra PAR-24 v1 (operacional): não é '
               "consolidação. Os dois lados continuam nos indicadores, como a API os devolve. A natureza das cópias "
               "(duplicidade ou transferência) não está determinada. As visões analíticas CONS-PAR (experimentais) "
               "não são exibidas nesta interface.</p>"
             + fm.selo("elotech", "derivado", [{"codigo": "PAR-24", "versao": 1, "situacao": "operacional"}],
                       "identificação por regra; nenhum valor é alterado")
             + resumo_html + (_origem_conjunto(r["proveniencia"]) if r.get("proveniencia") else "")
             + fm.tabela([("Lado A (entidade / empenho)", None), ("Inscrito A", None), ("Lado B (entidade / empenho)", None),
                          ("Inscrito B", None), ("Mesma inscrição", None), ("Relação", None), ("Execução", None)], linhas))
    return titulo, corpo


# ---------------------------------------------------------------------------------------------- metodologia
def metodologia(p, q):
    m = p.metodologia()
    f = p.fontes()
    regras = [[esc(r["codigo"]), esc(r["versao"]), fm.situacao_regra(f"{r['codigo']} v{r['versao']}", r["situacao"]),
               "sim" if r["compoe_indicador_publicado"] else "não", esc(r["status_evidencia"]), esc(r["definicao"])]
              for r in p.regras()]
    campos = [[esc(rot), f"<code>{esc(api)}</code>", esc(sig), esc(st),
               "não (restrito)" if col in publico.CAMPOS_RESTRITOS else "sim"]
              for col, (api, rot, sig, st) in F.CAMPOS.items()]
    naturezas = fm.lista_definicoes([(k, esc(v)) for k, v in f["naturezas"].items()])
    situacoes = fm.lista_definicoes([(k, esc(v)) for k, v in m["situacoes_do_dado"].items()])
    datas = ", ".join(fm.data_br(d, True) for d in m["datas_como_estava_em_com_derivacao"]) or "nenhuma"
    corpo = ("<h1>Metodologia e fontes</h1>"
             "<h2>Fonte principal</h2>"
             f"<p>{esc(m['dados_operacionais'])}</p>"
             "<h2>Fonte de reconciliação</h2>"
             f"<p>{esc(m['publicacoes_de_referencia'])} O RREO nunca substitui um valor da API: a diferença entre os "
             "dois aparece como diferença, com a situação da explicação (sem diferença, explicada, parcialmente "
             "explicada ou não determinada).</p>"
             "<h2>Hierarquia das fontes</h2><ul>" + "".join(f"<li>{esc(h)}</li>" for h in f["hierarquia"]) + "</ul>"
             "<h2>Snapshots</h2>"
             f"<p>{esc(m['snapshots'])}</p>"
             "<h2>Processamento e derivação</h2>"
             f"<p>{esc(m['processamento'])}</p><p>{esc(m['tratamento'])}</p>"
             "<h2>Retrato atual e retrato histórico</h2>"
             f"<p>{esc(m['retrato_atual_e_historico'])}</p>"
             "<ul><li><strong>Exercício</strong>: ano de execução dos Restos a Pagar (inscritos em 01/01, de empenhos de "
             "anos anteriores).</li><li><strong>Corte</strong>: data final do retrato (movimentos de 01/01 até ela)."
             "</li><li><strong>Coleta</strong>: data em que a API foi consultada.</li></ul>"
             f"<p>{esc(m['importante'])}</p>"
             f"<p>Datas 'como estava em' com derivação própria (reconciliação histórica): {esc(datas)}.</p>"
             "<h2>Situação dos dados</h2><p>Só 'dado existente' e 'entidade existente, sem RP' têm valor; nas demais "
             "situações a interface mostra o motivo, nunca R$ 0,00.</p>" + situacoes
             + "<h2>Natureza de cada valor</h2>" + naturezas
             + "<h2>Regras e situação</h2><p>Só regra operacional que compõe indicador entra nos indicadores. "
               "Regras experimentais ou não recomendadas aparecem apenas aqui e, rotuladas como análise, na "
               "reconciliação e no detalhe do empenho.</p>"
             + fm.tabela([("Regra", None), ("Versão", None), ("Situação", None), ("Compõe indicador", None),
                          ("Evidência", None), ("Definição", None)], regras)
             + "<h2>Limitações</h2><ul>" + "".join(f"<li>{esc(x)}</li>" for x in m["limitacoes"]) + "</ul>"
             + "<h2>Dados pessoais</h2><p>Listas e totais não mostram nome, código nem documento do credor. O detalhe "
               "de um empenho mostra o nome de pessoa jurídica sem documento; o nome de pessoa física não é exibido. "
               "Não há dado bancário nos dados coletados. A interface não tem modo interno.</p>"
             + "<h2>Dicionário de campos</h2>"
             + fm.tabela([("Nome", None), ("Campo da API", None), ("Significado", None), ("Status", None),
                          ("Aparece nas listas", None)], campos)
             + f'<p>Arquitetura detalhada: <code>{esc(m["arquitetura"])}</code>.</p>')
    return "Metodologia e fontes", corpo
