"""Page structure and the components shared by the screens: document, menu, selection form,
snapshot notice, indicator cards and the 'where to check' blocks."""
from ...painel import fontes as F
from ...painel.consulta import ROTULO_CATEGORIA
from .. import formato as fm, portal as P
from ..formato import esc

TAMANHO_PAGINA = 50
MENU = [("/", "Visão geral"), ("/resumo", "Resumo do corte"), ("/evolucao", "Evolução no exercício"),
        ("/historico", "Série entre exercícios"), ("/composicao", "Composição do saldo"),
        ("/variacao", "Variação entre cortes"), ("/entidades", "Entidades"),
        ("/empenhos", "Empenhos"), ("/retratos", "Retratos"), ("/reconciliacao", "Reconciliação com o RREO"),
        ("/qualidade", "Qualidade dos dados"), ("/metodologia", "Metodologia e fontes"),
        ("/pares", "Técnico: pares espelhados")]
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


def documento(titulo, corpo, ctx, ativo):
    """Full page: header, menu, data source, content and footer with the run in use."""
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
    """Chosen fiscal year, cut-off and entity. The default (nothing requested) comes from the cut-offs in the database;
    what was requested is never swapped for something else: a year without a processed cut-off becomes SemDados, and
    an unprocessed cut-off goes on to the panel layer, which returns the data situation of each entity
    (corte_processado = False)."""
    em = q.data("em")
    cortes = p.cortes(em)["cortes"]
    ate = f" até {fm.data_br(em)}" if em else ""
    if not cortes:
        raise SemDados(f"Nenhum corte processado{ate}.")
    exercicios = sorted({c["exercicio"] for c in cortes}, reverse=True)
    avisos = []
    ex = q.inteiro("exercicio", 1900, 2999)
    if ex is None:
        ex = exercicios[0]
    elif ex not in exercicios:
        raise SemDados(f"Exercício {ex} sem corte processado{ate}: nenhum valor é mostrado. Exercícios com corte "
                       f"processado: {', '.join(str(x) for x in exercicios)}.")
    entidade = q.inteiro("entidade", 1, 10 ** 6) if com_entidade else None
    do_exercicio = [c for c in cortes if c["exercicio"] == ex]
    processados = [c["data_final"] for c in do_exercicio]
    df = q.data("data_final")
    if df is None:
        candidatos = [c for c in do_exercicio if (c["municipio_disponivel"] if entidade is None
                                                   else entidade in c["entidades_com_snapshot"])]
        df = (candidatos or do_exercicio)[-1]["data_final"]
    elif df not in processados:
        avisos.append(f"Corte {fm.data_br(df)} não processado no exercício {ex}{ate}: nenhum outro corte é mostrado "
                      "no lugar dele. Cortes processados deste exercício: "
                      f"{', '.join(fm.data_br(x) for x in processados)}.")
    return {"em": em, "exercicio": ex, "data_final": df, "entidade": entidade, "exercicios": exercicios,
            "cortes_do_exercicio": do_exercicio, "corte_processado": df in processados, "avisos": avisos}


def _quando(sel):
    """Mandatory complement of the title: the snapshot is the current state of the base or 'as it was on' a date."""
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
    """Mandatory block: fiscal year, cut-off and collection, with the snapshot text. Hierarchy (POST_05_CONSOLIDATION
    section 7): at the top only the snapshot sentence (fiscal year, cut-off and collection date) and the warning of a
    cut-off after the collection; the audit detail (type, definitions, snapshots used and the long note) goes into
    "Origem do retrato", collapsed."""
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
    return (f'<section class="retrato"><p class="retrato-texto" id="retrato">{esc(ret["texto"])}</p>{nota}'
            '<details class="origem-retrato"><summary>Origem do retrato: tipo, corte, coleta e snapshots usados'
            f"</summary>{fm.lista_definicoes(definicoes)}"
            f'<p class="nota">{esc(ret["nota"])}</p></details></section>')


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


def _registro_tecnico(conteudo, resumo="Registro técnico (auditoria)"):
    """What was collected (snapshot, hash, derivation): proof of where the number came from, even if the portal changes
    later."""
    return f'<details class="registro-tecnico"><summary>{esc(resumo)}</summary>{conteudo}</details>'


def _origem_conjunto(prov, resumo="Origem do dado: onde conferir no Portal"):
    """<details> with the full portal listing of each snapshot in the set (the exact pages the collector queried), the
    query screen and the conditions; the technical record (uid, slice, collection, endpoint, derivation) stays collapsed."""
    portal, coleta = [], ""
    for s in prov["snapshots"]:
        urls = [r["url"] for r in s.get("respostas") or [] if str(r.get("url", "")).startswith(P.API)]
        if s.get("endpoint") != F.ELOTECH["endpoints"]["rp_listagem"] or not urls:
            continue
        coleta = fm.data_br(s["coletada_em"], True)
        paginas = (P.link(urls[0], "íntegra no corte") if len(urls) == 1 else
                   "íntegra no corte, páginas " + " · ".join(P.link(u, str(i + 1)) for i, u in enumerate(urls)))
        portal.append(f"<li>Entidade {esc(s['entidade'])}, {esc(fm.data_br(s['data_inicial']))} a "
                      f"{esc(fm.data_br(s['data_final']))}: {paginas} · {P.link(P.url_consulta(s['entidade']), 'tela de consulta')}</li>")
    itens = "".join(f"<li><code>{esc(s['snapshot_uid'])}</code> — entidade {esc(s['entidade'])}, "
                    f"{esc(fm.data_br(s['data_inicial']))} a {esc(fm.data_br(s['data_final']))}, coletado em "
                    f"{esc(fm.data_br(s['coletada_em'], True))}, endpoint <code>{esc(s['endpoint'])}</code></li>"
                    for s in prov["snapshots"])
    d = prov["derivacao"]
    usada = prov.get("derivacao_usada", d["id"])
    hash_ = f" (hash <code>{esc(d['hash_resultado'])}</code>)" if usada == d["id"] else ""
    tecnico = _registro_tecnico(f'<p>Fonte: {esc(F.ELOTECH["rotulo"])}. Derivação {esc(usada)}{hash_}, normalização '
                                f'{esc(prov["normalizacao"]["id"])}.</p><ul>{itens}</ul>',
                                "Origem do dado (snapshots usados): registro técnico")
    onde = (f"<ul>{''.join(portal)}</ul>" + P.condicoes(prov["snapshots"][0]["data_final"], coleta, montante=True)
            if portal else "<p>Sem íntegra da listagem de RP neste conjunto.</p>")
    return f'<details class="origem"><summary>{esc(resumo)}</summary>{onde}{tecnico}</details>'


def _cartao(v):
    ident = f"ind-{v['id']}"
    if v["id"] == "registros":
        numero = fm.contagem(v["valor_c"], ident, "indisponível")
    else:
        numero = fm.valor(v["valor_c"], ident, "indisponível")
    classe = "indicador destaque" if v["id"] in DESTAQUES else "indicador"
    return (f'<div class="{classe}"><p class="rotulo">{esc(v["rotulo"])}</p><p class="numero">{numero}</p>'
            f'{fm.selo("elotech", v["natureza"], v["regras"], v["formula"])}'
            f'<details class="origem"><summary>Origem do dado: onde conferir no Portal</summary>{P.como_conferir_montante(v)}'
            f"{_registro_tecnico(_origem_indicador(v))}</details></div>")


def _pdf(pdf, extracao=None):
    partes = [("Documento", esc(f"{pdf['rotulo']} — arquivo {pdf['id_arquivo']} de {fm.data_br(pdf['data_arquivo'])}")),
              ("No portal", P.como_conferir_pdf(pdf)),
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


def _situacao_curta(texto):
    """Short form of the situation for tables: the text before ':' and ' (' (the full one goes as a hint)."""
    return texto.split(":")[0].split(" (")[0]
