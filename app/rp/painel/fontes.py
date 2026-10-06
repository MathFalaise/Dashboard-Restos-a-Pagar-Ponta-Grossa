"""Data sources, value natures, field dictionary and methodology of the query layer.

Declarations only (no database access). The texts only say what the project's documentation demonstrates: the
attribution of the API to the Oxy Transparencia platform (Elotech) comes from the actuator/info queried in stage 01
and from the OpenAPI specification kept in the raw data; nothing here asserts something the project did not prove.
"""

ELOTECH = {
    "id": "elotech",
    "papel": "fonte operacional primária",
    "rotulo": "Portal da Transparência de Ponta Grossa — API do sistema Elotech/Oxy Transparência",
    "descricao": ("Registros granulares de Restos a Pagar por empenho, coletados da API do Portal da Transparência "
                  "de Ponta Grossa (servicos.pontagrossa.pr.gov.br/portaltransparencia-api) e guardados em snapshots "
                  "imutáveis antes de qualquer tratamento."),
    "endpoints": {"rp_listagem": "/empenhos/restos-a-pagar", "movimentacao": "/empenhos/detalhe/movimentacao",
                  "entidades": "/api/entidades/lista", "exercicios": "/api/exercicios/entidade/{id}"},
    "evidencia_da_atribuicao": [
        "Etapa 01: GET /portaltransparencia-api/actuator/info identificou a plataforma como Oxy Transparência, da Elotech "
        "Gestão Pública, versão 3.128.0 (registrado em docs/stages/01-source-discovery/REPORT.md; a resposta não foi guardada no bruto).",
        "data/stage01-samples/openapi_v3_api-docs.json: especificação OpenAPI da API, com contato 'Elotech Gestão Pública'.",
        "O endpoint de RP usado pelo projeto (/empenhos/restos-a-pagar) não consta dessa especificação; foi identificado "
        "na Etapa 01 pelo funcionamento do próprio portal.",
    ],
}

RREO = {
    "id": "rreo",
    "papel": "publicação oficial independente / fonte de reconciliação",
    "rotulo": "RREO Anexo VII — Demonstrativo dos Restos a Pagar por Poder e Órgão (PDF publicado pelo Município)",
    "descricao": ("Documento publicado pelo Município numa data de emissão própria, coletado como snapshot (PDF), "
                  "transcrito por um extrator versionado e usado para conferência, reconciliação e auditoria. "
                  "Não substitui os registros da API."),
    "observacao": ("Os PDFs de 2020 a 2026 trazem no rodapé 'FONTE: Sistema Elotech Gestão Pública'; os de 2018 e 2019, "
                   "'Sistema de Contabilidade Pública'; os de 2016 e 2017 não têm essa linha. O RREO é um retrato do "
                   "momento da emissão; a API mostra o estado da base no momento da coleta."),
}

EXTERNA = {
    "id": "externa",
    "papel": "fonte externa",
    "rotulo": "Documentos externos registrados (e-SIC, normas, notas técnicas, documentos oficiais)",
    "descricao": "Arquivos guardados no armazém com SHA-256 e registrados na tabela evidencia_externa.",
}

FONTES = {f["id"]: f for f in (ELOTECH, RREO, EXTERNA)}

NATUREZAS = {
    "da_fonte": "Dado da fonte — valor retornado pela API Elotech para um registro",
    "publicado": "Dado publicado — valor presente no RREO (PDF oficial)",
    "derivado": "Valor derivado — soma ou fórmula documentada pelo projeto sobre dados da API, com regra operacional",
    "analitico": "Valor analítico — resultado de hipótese ou regra experimental; não é dado oficial",
    "diferenca": "Diferença — divergência entre duas fontes ou dois retratos",
}

# RREO Annex VII columns (labels transcribed in stage 02, docs/stages/02-accounting-validation/REPORT.md section 5)
COLUNAS_RREO = {
    "a": "Processados — inscritos em exercícios anteriores",
    "b": "Processados — inscritos em 31/dez do exercício anterior",
    "c": "Processados — pagos",
    "d": "Processados — cancelados",
    "e": "Processados — saldo = (a+b) − (c+d)",
    "f": "Não processados — inscritos em exercícios anteriores",
    "g": "Não processados — inscritos em 31/dez do exercício anterior",
    "h": "Não processados — liquidados",
    "i": "Não processados — pagos",
    "j": "Não processados — cancelados",
    "k": "Não processados — saldo = (f+g) − (i+j)",
    "L": "Saldo total = e + k",
}
# normalized column -> (API field, displayed label, meaning confirmed in stage 02, evidence status)
CAMPOS = {
    "proc_c": ("proc", "Inscrição processada",
               "Saldo liquidado e não pago antes de dataInicial; com dataInicial = 01/01, RP Processados inscritos.",
               "CONFIRMADO com dataInicial = 01/01"),
    "aproc_c": ("aproc", "Inscrição não processada",
                "Saldo empenhado e não liquidado antes de dataInicial; com dataInicial = 01/01, RP Não Processados inscritos.",
                "CONFIRMADO com dataInicial = 01/01"),
    "cancelado_proc_c": ("canceladoProc", "Cancelado processado (campo da API)",
                         "Sempre 0 em todos os dados observados; significado não determinado.", "NÃO DETERMINADO"),
    "pago_proc_c": ("pagoProc", "Pago processado",
                    "Pagamentos menos estornos no período, de liquidações de exercício anterior; já líquido de estornos.",
                    "CONFIRMADO para o total"),
    "pago_proc_estornado_c": ("pagoProcEstornado", "Estornos de pagamento (processado)",
                              "Soma bruta dos estornos no período; informativo, já descontado de pagoProc.",
                              "FORTE EVIDÊNCIA"),
    "cancelado_aproc_c": ("canceladoAProc", "Cancelamentos",
                          "Cancelamentos do empenho no período, de qualquer parcela, líquidos de estorno de cancelamento.",
                          "FORTE EVIDÊNCIA"),
    "pago_aproc_c": ("pagoAProc", "Pago não processado",
                     "Pagamentos menos estornos no período, de liquidações do próprio exercício, mais retenções.",
                     "FORTE EVIDÊNCIA"),
    "pago_aproc_estornado_c": ("pagoAProcEstornado", "Estornos de pagamento (não processado)",
                               "Informativo; já descontado de pagoAProc e não aditivo entre períodos.", "FORTE EVIDÊNCIA"),
    "liquidado_c": ("liquidado", "Liquidações",
                    "Liquidações menos estornos de liquidação no período; negativo quando há estorno de parcela já liquidada.",
                    "FORTE EVIDÊNCIA"),
    "retencao_c": ("retencao", "Retenções",
                   "Retenções menos estornos no período; já contidas em pagoAProc quando a liquidação é do exercício.",
                   "FORTE EVIDÊNCIA"),
    "entidade": ("entidade", "Entidade", "Identificador da entidade no portal.", "CONFIRMADO"),
    "anoempenho": ("anoempenho", "Ano do empenho", "Exercício de emissão do empenho; sempre anterior ao exercício consultado.",
                   "CONFIRMADO"),
    "empenho": ("empenho", "Empenho", "Número dentro da entidade e do ano; a chave é (entidade, anoempenho, empenho).",
                "CONFIRMADO"),
    "empenho_exercicio": ("empenhoExercicio", "Empenho/ano", "Como a API devolve.", "campo da API"),
    "data_emissao": ("dataEmissao", "Data de emissão", "Como a API devolve.", "campo da API"),
    "programatica": ("programatica", "Programação orçamentária", "Classificação programática como a API devolve.",
                     "campo da API"),
    "fonte_recurso": ("fonteRecurso", "Fonte de recurso", "Código da fonte como a API devolve.", "campo da API"),
    "descricao_fonte": ("descricaoFonte", "Descrição da fonte", "Como a API devolve.", "campo da API"),
    "orgao": ("orgao", "Órgão", "Nem todo registro traz (ver chaves_ausentes).", "campo da API"),
    "unidade": ("unidade", "Unidade", "Nem todo registro traz.", "campo da API"),
    "funcao": ("funcao", "Função", "Nem todo registro traz.", "campo da API"),
    "sub_funcao": ("subFuncao", "Subfunção", "Nem todo registro traz.", "campo da API"),
    "programa": ("programa", "Programa", "Nem todo registro traz.", "campo da API"),
    "projeto": ("projeto", "Projeto/atividade", "Nem todo registro traz.", "campo da API"),
    "elemento": ("elemento", "Elemento de despesa", "Nem todo registro traz.", "campo da API"),
    "desdobra_desp": ("desdobraDesp", "Desdobramento da despesa", "Como a API devolve.", "campo da API"),
    "sub_desdobramento": ("subDesdobramento", "Subdesdobramento", "Como a API devolve.", "campo da API"),
    "fornecedor": ("fornecedor", "Código do credor", "Identificador interno do credor no sistema (restrito).", "campo da API"),
    "nome": ("nome", "Credor", "Nome do credor como a API devolve (restrito; o nome de MEI pode conter o CPF do titular).",
             "campo da API"),
    "cnpj": ("cnpj", "CNPJ/CPF do credor", "CNPJ completo; CPF chega mascarado pela própria API (restrito).", "campo da API"),
    "cnpj_nome": ("cnpjNome", "Documento e nome do credor", "Como a API devolve (restrito).", "campo da API"),
}

# per-record derived values (layer 2): column -> (label, formula, rule)
DERIVADOS = {
    "categoria": ("Categoria", "ambos / processado / não processado / sem saldo de abertura, por proc e aproc", ("CAT", 1)),
    "faixa_processado": ("Faixa do processado", "(b) se anoempenho = exercício − 1; senão (a)", ("FAIXA", 1)),
    "faixa_nao_processado": ("Faixa do não processado", "(g) se anoempenho = exercício − 1; senão (f)", ("FAIXA", 1)),
    "s1_saldo_total_c": ("Saldo total (S1)", "proc + aproc − pagoProc − pagoAProc − canceladoAProc", ("S1", 1)),
    "s2_a_liquidar_c": ("Saldo a liquidar (S2)", "aproc − liquidado − canceladoAProc", ("S2", 1)),
    "s3_liquidado_a_pagar_c": ("Saldo liquidado a pagar (S3)", "proc − pagoProc + liquidado − pagoAProc", ("S3", 1)),
    "cancel_processado_c": ("Cancelamento de processado (divisão CANC v1)",
                            "canceladoAProc se proc > 0 e aproc = 0", ("CANC", 1)),
    "cancel_nao_processado_c": ("Cancelamento de não processado (divisão CANC v1)", "canceladoAProc se aproc > 0",
                                ("CANC", 1)),
}

METODOLOGIA = {
    "dados_operacionais": ("Portal da Transparência de Ponta Grossa — dados da API do sistema Elotech/Oxy Transparência. "
                           "São os registros granulares de Restos a Pagar por empenho, coletados pelo coletor do projeto."),
    "publicacoes_de_referencia": ("RREO Anexo VII e demais documentos oficiais publicados pelo Município, usados para "
                                  "conferência, reconciliação e auditoria."),
    "tratamento": ("Os dados Elotech são preservados em snapshots imutáveis, normalizados sem alteração dos valores "
                   "originais (em centavos) e depois derivados segundo regras versionadas. Uma divergência com o RREO é "
                   "mostrada como diferença; o valor da API nunca é ajustado para coincidir com o RREO."),
    "importante": ("Um exercício histórico representa o estado da base observado na data da coleta, e não "
                   "necessariamente o estado que estava disponível ao público naquele ano. A Etapa 04.4 registrou "
                   "alterações retroativas na base (lançamentos com data no passado feitos depois e registros inseridos "
                   "depois que aparecem em cortes antigos)."),
    "arquitetura": "docs/stages/04-pipeline/SOURCE_ARCHITECTURE.md",
    "snapshots": ("Cada consulta à API vira um snapshot: as respostas HTTP são guardadas byte a byte, com SHA-256, "
                  "num armazém onde nada é sobrescrito nem apagado. Coletar de novo o mesmo corte cria outro snapshot "
                  "(outro retrato); o anterior continua disponível."),
    "processamento": ("A normalização lê os snapshots e grava um registro por item devolvido pela API, sem mudar "
                      "valores. A derivação aplica regras versionadas (saldos S1–S3, categoria, faixas, pares) e grava "
                      "um hash do resultado. Snapshot coletado depois da última normalização aparece como 'coletado, "
                      "mas ainda não processado', nunca como zero."),
    "retrato_atual_e_historico": ("Retrato atual: o snapshot mais recente de cada entidade para o corte. Para um "
                                  "exercício passado, isso é o estado atual da base para aquele corte, visto na data "
                                  "da coleta, e não o que se publicava na época. 'Como estava em' limita a escolha aos "
                                  "snapshots coletados até a data informada."),
    "limitacoes": [
        "A base do Município muda depois do fim do exercício: lançamentos com data no passado e registros incluídos "
        "depois aparecem em cortes antigos (Etapa 04.4).",
        "Os empenhos 24xxxxx da Prefeitura espelham registros da Fundação Municipal de Saúde; a natureza dessas "
        "cópias não está determinada e os dois lados continuam nos totais, como a API devolve.",
        "Parte das diferenças entre a API e o RREO está sem explicação documentada ('não determinada'); a origem foi "
        "perguntada no pedido e-SIC em rascunho.",
        "A reconciliação 'como estava em' só existe para as datas que têm derivação 'como estava em' própria "
        "(listadas nesta página).",
        "Os RREOs de 2016 (entidade), 2018 e 2019 não são lidos pelo extrator de produção.",
        "O catálogo de entidades é o que a API devolve hoje; entidade extinta que não conste dele não é conhecida.",
        "A consulta de RP usada (/empenhos/restos-a-pagar) não consta da documentação oficial da API nem do menu do "
        "portal.",
    ],
}
