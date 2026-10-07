"""Methodology and sources (/metodologia)."""
from ...painel import fontes as F, publico
from .. import formato as fm
from ..formato import esc


def metodologia(p, q):
    m = p.metodologia()
    f = p.fontes()
    regras = [[esc(r["codigo"]), esc(r["versao"]),
               fm.situacao_regra(f"{r['codigo']} v{r['versao']}", r["situacao"], r.get("ressalva")),
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
