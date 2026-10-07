"""A commitment across cut-offs (/empenho/cortes) and the commitment
detail (/empenho)."""
from ...painel import fontes as F
from .. import formato as fm, portal as P
from ..formato import esc
from .estrutura import erro, NOME_CATEGORIA, _quando, _retrato, _situacao_curta


def empenho_cortes(p, q):
    """One commitment across all cut-offs of the fiscal year (sub-stage 05.5; contract M-12). Values come ready from the
    panel layer."""
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
    """Snapshot sentence for a commitment's timeline (current state or 'as it was on')."""
    if em:
        return f"Como a base estava em {fm.data_br(em)}: só snapshots coletados até essa data."
    return "Cada corte é o estado atual da base para aquele corte, na data da coleta, não o que se sabia na época."


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
        corpo.append(_detalhe_ocorrencia(o, d["chave"]))
    if d.get("nota"):
        corpo.append(f'<p class="nota">{esc(d["nota"])}</p>')
    corpo.append(_movimentacao(d["movimentacao"], d["chave"]))
    return titulo, "".join(corpo)


def _detalhe_ocorrencia(o, chave):
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
    partes.append(_origem_registro(o["proveniencia"], chave))
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


def _origem_registro(pv, chave):
    """Where to check this commitment on the portal (visible) and the collection's technical record (collapsed)."""
    s = pv["snapshot"]
    parametros = ", ".join(f"{k}={v}" for k, v in sorted(s["parametros"].items()))
    return ('<section class="grupo origem-dado" id="origem"><h2>Origem do dado: onde conferir no Portal</h2>'
            + P.como_conferir_registro(s, chave, pv)
            + P.condicoes(s["data_final"], fm.data_br(s["coletada_em"], True))
            + "<details><summary>Registro técnico (auditoria): fonte, endpoint, snapshot, hash</summary>"
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


def _movimentacao(m, chave):
    no_portal = (f'<p>{P.link(P.url_empenho(chave["entidade"], chave["anoempenho"], chave["empenho"]), "Movimentação no portal")}'
                 " (detalhe do empenho, aba Movimentação: todos os lançamentos até hoje, com a data de cada um).</p>")
    if not m.get("coletada"):
        return (f'<section class="grupo"><h2>Movimentações</h2><p>{esc(m.get("nota") or "não coletada")}.</p>'
                f"{no_portal}</section>")
    linhas = [[esc(fm.data_br(l["data"])), esc(l["tipo_lancamento"]), esc(l["descricao"]), fm.valor(l["valor_c"]),
               esc(l["efeito"] or "—"), esc(l["liquidacao_referida"] or "—")] for l in m["lancamentos"]]
    s = m["snapshot"]
    return ('<section class="grupo"><h2>Movimentações</h2>'
            + fm.selo("elotech", "da_fonte") + no_portal
            + f'<p class="nota">Snapshot <code>{esc(s["snapshot_uid"])}</code>, coletado em '
            + f'{esc(fm.data_br(s["coletada_em"], True))}, endpoint <code>{esc(s["endpoint"])}</code>. Efeito e '
            + "liquidação referida são interpretação (MOV-REF v1, operacional).</p>"
            + fm.tabela([("Data", None), ("Tipo", None), ("Descrição", None), ("Valor", None), ("Efeito", None),
                         ("Liquidação referida", None)], linhas) + "</section>")
