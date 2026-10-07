"""Data quality (/qualidade)."""
import json

from .. import formato as fm
from ..formato import esc
from .estrutura import TAMANHO_PAGINA

SITUACAO_CURTA = {"sem diferença": "sem", "explicada": "exp", "parcialmente explicada": "parc", "hipótese": "hip",
                  "não determinada": "nd"}


def qualidade(p, q):
    """Anomalies, checks and the situation of the differences with the RREO (sub-stage 05.6), read from the derivation
    by the panel layer; no reinterpretation here."""
    tipo, exercicio = q.texto("tipo", 40), q.inteiro("exercicio", 1900, 2999)
    entidade, data_final = q.inteiro("entidade", 1, 10 ** 6), q.data("data_final")
    pagina = q.inteiro("pagina", 1, 10 ** 6) or 1
    r = p.qualidade()
    d = r["derivacao"]
    titulo = f"Qualidade dos dados — derivação {d['id']}"
    corpo = [f"<h1>{esc(titulo)}</h1>",
             f'<p class="nota">{esc(r["nota"])} Derivação {esc(d["id"])} (hash <code>{esc(d["hash_resultado"][:16])}…</code>), '
             f'normalização {esc(r["normalizacao"]["id"])}.</p>',
             _tabela_anomalias(r["anomalias"])]
    if tipo:
        corpo.append(_ocorrencias(p.anomalias(tipo, TAMANHO_PAGINA, (pagina - 1) * TAMANHO_PAGINA, exercicio, entidade,
                                              data_final), r["anomalias"], pagina))
    corpo += [_tabela_verificacoes(r["verificacoes"]), _tabela_diferencas_rreo(r["diferencas_rreo"])]
    return titulo, "".join(corpo)


def _tabela_anomalias(a):
    linhas = [[f"<code>{esc(x['tipo'])}</code>", esc(x["descricao"]), esc(x["status_evidencia"]),
               fm.situacao_regra(x["regra"], x["situacao_da_regra"]), fm.contagem(x["ocorrencias"], f"anom-{x['tipo']}"),
               fm.contagem(x["em_snapshots_vigentes"], f"anom-{x['tipo']}-vig"), fm.contagem(x["snapshots"]),
               esc(", ".join(map(str, x["exercicios"]))), fm.link("/qualidade", "ver ocorrências", tipo=x["tipo"])]
              for x in a["por_tipo"]]
    sem = "".join(f"<li><code>{esc(x['tipo'])}</code> — {esc(x['descricao'])}</li>" for x in a["tipos_sem_ocorrencia"])
    return ('<section class="grupo" id="anomalias"><h2>Anomalias registradas pela derivação</h2>'
            + fm.selo("elotech", "derivado", None, "fatos registrados por regra; nenhum valor é alterado")
            + '<p class="nota">Anomalia não é erro: é um fato registrado por uma regra, descrito pelo tipo (ex.: LIQ-NEG = '
              "estorno de liquidação). A contagem é a da derivação: uma linha por ocorrência em cada snapshot "
              "processado. O mesmo empenho conta uma vez por retrato e por corte em que a condição vale; por isso a coluna "
              "ao lado mostra quantas estão nos snapshots vigentes.</p>"
            + fm.tabela([("Tipo", None), ("Descrição", None), ("Evidência", "status de evidência do tipo"),
                         ("Regra", None), ("Ocorrências", "linhas da derivação"),
                         ("Em snapshots vigentes", "o retrato usado pelo painel em cada corte"),
                         ("Snapshots", "snapshots com ocorrência"), ("Exercícios", None), ("Lista", None)], linhas,
                        "tabela anomalias")
            + (f"<h3>Tipos sem ocorrência na derivação atual</h3><ul>{sem}</ul>" if sem else "")
            + "</section>")


def _detalhe_da_anomalia(det):
    if not det:
        return "—"
    return "; ".join(f"{esc(k)}: " + (fm.valor(v) if k.endswith("_c") and isinstance(v, int) and not isinstance(v, bool)
                                       else esc(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)))
                     for k, v in sorted(det.items()))


def _ocorrencias(o, a, pagina):
    anos = next((x["exercicios"] for x in a["por_tipo"] if x["tipo"] == o["tipo"]), [])
    f = o["filtros"]
    ocultos = "".join(f'<input type="hidden" name="{k}" value="{esc(f[k])}">' for k in ("entidade", "data_final") if k in f)
    filtro = ('<form class="filtros" method="get" action="/qualidade">'
              f'<input type="hidden" name="tipo" value="{esc(o["tipo"])}">{ocultos}'
              f'<label>Exercício <select name="exercicio"><option value="">todos</option>'
              f'{fm.opcoes([(x, x) for x in anos], f.get("exercicio", ""))}</select></label>'
              '<button type="submit">Filtrar</button></form>')
    escopo = ", ".join(f"{k} = {fm.data_br(v) if k == 'data_final' else v}" for k, v in f.items()) or "todos"
    linhas = []
    for x in o["itens"]:
        c, lig = x["chave"], x["ligacao"]
        if lig and lig["destino"] == "empenho":
            ligacao = fm.link("/empenho", "registro", entidade=c["entidade"], anoempenho=c["anoempenho"],
                              empenho=c["empenho"], exercicio=lig["exercicio"], data_final=lig["data_final"])
        elif lig:
            ligacao = fm.link("/retratos", "retratos do corte", entidade=c["entidade"], exercicio=lig["exercicio"],
                              data_final=lig["data_final"])
        else:
            ligacao = "não é corte do painel"
        linhas.append([f"<code>{esc((x['snapshot'] or '—')[:12])}</code>", esc(x["exercicio"] or "—"),
                       esc(fm.data_br(x["data_final"]) or "—"), esc(x["retrato"]), esc(c["entidade"]),
                       esc(f"{c['empenho']}/{c['anoempenho']}"), _detalhe_da_anomalia(x["detalhe"]), ligacao])
    paginas = max(1, -(-o["total"] // TAMANHO_PAGINA))
    base = dict(tipo=o["tipo"], **f)
    nav = [f"Página {pagina} de {paginas} ({fm.inteiro(o['total'])} ocorrências)"]
    if pagina > 1:
        nav.insert(0, fm.link("/qualidade", "« anterior", pagina=pagina - 1, **base))
    if pagina < paginas:
        nav.append(fm.link("/qualidade", "próxima »", pagina=pagina + 1, **base))
    return (f'<section class="grupo" id="ocorrencias"><h2>Ocorrências: {esc(o["tipo"])}</h2>'
            f'<p>{esc(o["descricao"])} ({esc(o["status_evidencia"])}; fonte: {esc(o["fonte"])}). Escopo: '
            f"{esc(escopo)}.</p>"
            f'<p class="nota">{esc(o["nota"])} A ligação leva ao registro só quando a ocorrência está no snapshot vigente '
            "do corte (o detalhe do empenho mostra o retrato vigente); ocorrência num retrato anterior leva aos retratos "
            "do corte; coleta que não é corte do painel não tem ligação.</p>"
            + (f'<p class="aviso" id="sem-chave">{fm.contagem(o["sem_chave"], "ocorr-sem-chave")} ocorrência(s) deste '
               "escopo sem entidade, ano e número do empenho: ficam só na contagem por tipo, sem lista nem ligação.</p>"
               if o["sem_chave"] else "")
            + filtro
            + (fm.tabela([("Snapshot", None), ("Exercício", None), ("Corte", None), ("Retrato", None), ("Entidade", None),
                          ("Empenho/ano", None), ("Detalhe registrado", "detalhe_json da anomalia"), ("Ligação", None)],
                         linhas, "tabela ocorrencias") if linhas else
               '<p id="sem-ocorrencia">Nenhuma ocorrência com chave de empenho deste tipo na derivação atual'
               + (" neste escopo" if f else "") + ".</p>")
            + f'<p class="paginacao">{" · ".join(nav)}</p></section>')


def _tabela_verificacoes(vs):
    linhas, detalhes = [], []
    for i, v in enumerate(vs, 1):
        if v["anomalias_ligadas"]:
            ligacao = ", ".join(fm.link("/qualidade", f"{a['tipo']} ({fm.inteiro(a['ocorrencias'])})", tipo=a["tipo"])
                                for a in v["anomalias_ligadas"])
        elif v["natureza"] in ("colunas_com_diferenca", "pdfs_nao_lidos"):
            ligacao = fm.link("/reconciliacao", "reconciliação com o RREO")
        else:
            ligacao = "—"
        linhas.append([esc(v["regra"]), esc(v["descricao"]), fm.contagem(len(v["itens"])),
                       fm.contagem(v["verificados"], f"verif-{i}-v"), fm.contagem(v["falhas"], f"verif-{i}-f"),
                       esc(v["significado_de_falhas"]), f'<strong id="verif-{i}-sit">{esc(v["situacao"])}</strong>', ligacao])
        itens = [[esc("; ".join(f"{k}: {val}" for k, val in sorted(it["escopo"].items()) if k != "snapshots")),
                  fm.contagem(it["verificados"]), fm.contagem(it["falhas"]), esc(it["situacao"]),
                  " ".join(f"<code>{esc(u[:12])}</code>" for u in it["snapshots"]) or "—",
                  ", ".join(fm.link("/qualidade", a["tipo"], **a) for a in it["anomalias_do_escopo"]) or "—"]
                 for it in v["itens"]]
        detalhes.append(f'<details class="origem"><summary>{esc(v["descricao"])}: {fm.inteiro(len(v["itens"]))} itens</summary>'
                        + fm.tabela([("Escopo", None), ("Verificados", None), ("“Falhas”", None), ("Situação", None),
                                     ("Snapshots", None), ("Anomalias do escopo", "registradas pela mesma regra")], itens,
                                    "tabela itens-verificacao")
                        + "</details>")
    return ('<section class="grupo" id="verificacoes"><h2>Verificações da derivação</h2>'
            + fm.selo("elotech", "derivado", None, "verificações de conjunto gravadas pela derivação")
            + '<p class="nota">Cada verificação é de conjunto e nunca é apresentada como lista de empenhos. O significado '
              "de “falhas” muda conforme a verificação; ele vem de um catálogo por descrição. Descrição fora do catálogo "
              "aparece com os números brutos e “significado não catalogado”. Quando a mesma regra registra anomalias por "
              "empenho, a ligação leva à lista dessas anomalias.</p>"
            + fm.tabela([("Regra", None), ("Descrição (como a derivação grava)", None), ("Itens", None),
                         ("Verificados", None), ("“Falhas” (número bruto)", None), ("Significado de “falhas”", None),
                         ("Situação", None), ("Ligação", None)], linhas, "tabela verificacoes")
            + "".join(detalhes) + "</section>")


def _tabela_diferencas_rreo(dr):
    colunas = [(f"RREO × API — {r}", dr["por_regra"][r], dr["total_por_regra"][r], r.split()[-1]) for r in dr["por_regra"]]
    colunas += [("Coerência entre publicações (a exibida na reconciliação)", dr["coerencia"]["exibida"],
                 dr["total_coerencia"]["exibida"], "coe"),
                ("Coerência: todas as publicações de A+1", dr["coerencia"]["todas"], dr["total_coerencia"]["todas"],
                 "coe-todas")]
    linhas = [[f"<strong>{esc(s)}</strong>"] + [fm.contagem(c[s], f"sit-{ident}-{SITUACAO_CURTA[s]}") for _, c, _, ident in colunas]
              for s in dr["situacoes"]]
    linhas.append(["Total"] + [fm.contagem(t, f"sit-{ident}-total") for _, _, t, ident in colunas])
    c = dr["conferencia_com_a_verificacao"]
    rep = c["pdfs_repetidos"]
    conferencia = (f"A verificação CONC-RREO conta {fm.inteiro(c['verificacao']['colunas'])} colunas, "
                   f"{fm.inteiro(c['verificacao']['com_diferenca'])} com diferença, porque conta por snapshot do PDF. A "
                   f"reconciliação conta por documento: {fm.inteiro(c['reconciliacao']['colunas'])} colunas, "
                   f"{fm.inteiro(c['reconciliacao']['com_diferenca'])} com diferença. A diferença entre as duas contagens é o "
                   f"mesmo PDF coletado mais de uma vez ({fm.inteiro(len(rep['snapshots']))} snapshot(s) repetido(s): "
                   f"{fm.inteiro(rep['colunas'])} colunas, {fm.inteiro(rep['com_diferenca'])} com diferença). "
                   + ("As contagens conferem." if c["confere"] else "AS CONTAGENS NÃO CONFEREM."))
    return ('<section class="grupo" id="diferencas-rreo"><h2>Diferenças com o RREO por situação</h2>'
            + fm.selo("rreo", "diferenca", None, "API − RREO por coluna; situação da explicação documentada")
            + f'<p class="nota">{esc(dr["nota"])} {esc(fm.inteiro(dr["documentos"]))} documentos, '
              f'{esc(fm.inteiro(dr["linhas"]))} comparações coluna a coluna.</p>'
            + fm.tabela([("Situação", None)] + [(rot, None) for rot, _, _, _ in colunas], linhas, "tabela situacoes")
            + f'<p class="nota" id="conferencia-conc-rreo">{esc(conferencia)}</p>'
            + f'<p>{fm.link("/reconciliacao", "Ver a reconciliação documento a documento")}</p></section>')
