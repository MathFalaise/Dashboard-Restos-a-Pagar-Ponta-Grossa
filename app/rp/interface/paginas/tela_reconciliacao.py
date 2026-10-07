"""Reconciliation with the RREO (/reconciliacao)."""
from ...painel import fontes as F
from .. import formato as fm, portal as P
from ..formato import esc
from .estrutura import _explicacoes, _pdf, _registro_tecnico


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
        ident = f"rec-{x['regra_agregacao']['regra'].split()[-1]}-{x['coluna']}"      # e.g. rec-v2-h
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
    ultimo = {(x["escopo"], x["de"]): x for x in coe["comparacoes"] if x["mais_recente"]}   # mark from the panel layer
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
    no_portal = " e ".join(P.link(P.url_pdf(i), f"PDF de {ex}") for i, ex in zip(x.get("pdfs_arquivo") or [],
                                                                                 (x["de"], x["para"])) if i)
    return (f'<details class="origem"><summary>onde conferir</summary><p>No portal: {no_portal or "—"} (coluna L do '
            "primeiro; colunas (a) e (f) do segundo).</p>"
            + _registro_tecnico(f"PDFs do RREO (snapshots): {pdfs}. Snapshots da API: "
                                + (" ".join(f"<code>{esc(u)}</code>" for u in api) or "—") + ".")
            + "</details>")
