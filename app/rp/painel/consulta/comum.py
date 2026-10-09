"""Constants, exceptions and helper functions shared by the Painel modules."""
from ... import DataInvalida, instante as _instante, vigencia
from .. import explicacoes, fontes

VERSAO = "rp-painel/1"
ESQUEMA_MINIMO = 7          # v7: coleta_tempo (a snapshot is only available from its conclusion on)
NIVEIS = ("publico", "interno")
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
LIMITE_LISTA = 500
CATEGORIAS = ("processado", "nao_processado", "ambos", "sem_saldo_abertura")
ORDEM_COLUNAS = "abcdefghijkL"          # order of the columns in the RREO Annex VII
# Data situation of an entity at a cut-off. Only 'com_dados' and 'sem_rp' have a value; 'sem_rp' is the only true
# zero (the entity existed and the API returned zero records). The others never become R$ 0,00.
SITUACOES_DO_DADO = {
    "com_dados": "dado existente",
    "sem_rp": "entidade existente, sem RP neste corte (zero registros na API)",
    "inexistente": "entidade inexistente no exercício (fora do catálogo oficial; não é RP zero)",
    "sem_coleta": "corte não coletado",
    "nao_processado": "corte coletado, mas ainda não processado",
    "incompleto": "dado indisponível: só há coleta incompleta ou com falha deste corte",
    "ambiguo": "dado indisponível: o retrato do corte tem a mesma chave de empenho mais de uma vez (CHAVE-DUP); "
               "nenhuma ocorrência é escolhida",
    "valor_recusado": "dado indisponível: o retrato do corte tem campo monetário ausente, nulo ou inválido "
                      "(VALOR-RECUSADO); o registro nunca é somado como zero",
    "divergente": "dado com diferença em relação ao RREO (a diferença é mostrada; o valor da API não muda)",
}
# Situation of a series POINT (docs/stages/05-analysis/ANALYTICAL_CONTRACT.md section 2): extends the taxonomy
# above, without a parallel one. 'municipio_indisponivel' comes in 05.2; 'exercicio_sem_cobertura' comes in 05.3.
SITUACOES_DO_PONTO = {
    **{k: v for k, v in SITUACOES_DO_DADO.items() if k != "divergente"},
    "municipio_indisponivel": "Município indisponível: alguma entidade do catálogo do exercício sem snapshot processado "
                              "neste corte",
    "exercicio_sem_cobertura": "exercício sem cobertura: nenhuma coleta deste exercício no banco",
}
TEM_VALOR = ("com_dados", "sem_rp")
# Indicators of the series within the fiscal year (contract M-01 and M-02)
INDICADORES_DA_SERIE = ("inscricao_total", "pagamentos", "liquidacoes", "cancelamentos", "saldo_total")
ROTULO_POSTERIOR_A_COLETA = "corte posterior à coleta: valores até a data da coleta"
ROTULO_EXERCICIO_EM_ABERTO = "exercício em aberto: último corte com o Município disponível"
INDICADORES_ENTRE_EXERCICIOS = ("inscricao_total", "pagamentos", "cancelamentos", "saldo_total")
CONTINUIDADE = "continuidade fechamento→abertura"          # description recorded by the derivation (ANOM-CONT v1)
# Cut-off composition (sub-stage 05.4; contract M-05 to M-08): each dimension adds up ON ITS OWN to the cut-off total.
ROTULO_CATEGORIA = {"processado": "processado", "nao_processado": "não processado",
                    "ambos": "processado e não processado", "sem_saldo_abertura": "sem saldo de abertura"}
FAIXAS = ("a", "b", "f", "g")
DIMENSOES_ORCAMENTARIAS = ("fonte_recurso", "orgao", "funcao", "programa", "elemento")
COMPOSICOES = ("categoria", "faixa", "tipo_credor") + DIMENSOES_ORCAMENTARIAS
ROTULO_COMPOSICAO = {"categoria": "Categoria (CAT v1)", "faixa": "Faixa (FAIXA v1)", "tipo_credor": "Tipo de credor",
                     "fonte_recurso": "Fonte de recurso", "orgao": "Órgão", "funcao": "Função", "programa": "Programa",
                     "elemento": "Elemento de despesa"}
MEDIDAS_DA_COMPOSICAO = ("registros", "inscricao_total_c", "saldo_total_c")
TEXTO_FAIXA = "composição dos registros da API segundo a regra FAIXA v1"
SEM_CLASSIFICACAO = "sem classificação (campo ausente no registro da API)"
# Investigation of variations (sub-stage 05.5; contract M-09 to M-12); the metrics live in METRICAS_DA_VARIACAO.
CLASSES_DA_CHAVE = {"nos_dois": "nos dois cortes", "so_posterior": "presente só no corte posterior",
                    "so_anterior": "ausente no corte posterior"}
TOP_DA_VARIACAO = 10
CAMPOS_DO_HISTORICO = ("proc_c", "aproc_c", "pago_proc_c", "pago_aproc_c", "liquidado_c", "cancelado_aproc_c",
                       "s1_saldo_total_c")
# Data quality (sub-stage 05.6; contract section 6): structures recorded by the derivation, only read ("derivacao"
# regime). The meaning of "falhas" depends on the check (R5): catalog by literal description and rule; a description
# outside the catalog comes out with the raw numbers and "significado nao catalogado", never by analogy.
SITUACOES_DAS_DIFERENCAS = ("sem diferença",) + explicacoes.SITUACOES
NAO_CATALOGADA = "significado não catalogado"
INTERPRETACOES_DE_VERIFICACAO = {
    CONTINUIDADE: {
        "regra": ("ANOM-CONT", 1), "natureza": "conformidade", "anomalias": ("SALDO-SEM-CONTINUIDADE", "DESCONTINUIDADE"),
        "verificados": "registros do fechamento de A (corte 31/12)",
        "falhas": "registros com saldo que somem da abertura de A+1, ou cuja abertura (proc, aproc) difere de (S3, S2) do "
                  "fechamento"},
    "pareamento de cópias 24xxxxx": {
        "regra": ("PAR-24", 1), "natureza": "conformidade", "anomalias": ("COPIA-SEM-PAR",),
        "verificados": "cópias 24xxxxx da entidade 1 no corte",
        "falhas": "cópias sem registro correspondente na entidade 15, ou com campos de conferência diferentes"},
    "conciliação RREO × API (colunas com diferença)": {
        "regra": ("CONC-RREO", 1), "natureza": "colunas_com_diferenca", "anomalias": (),
        "verificados": "colunas do RREO comparadas, por snapshot do PDF e regra de agregação",
        "falhas": "colunas com diferença entre a API projetada e o valor publicado (informativo, não é erro)"},
    "RREO sem valores extraídos (ver problemas da normalização)": {
        "regra": ("CONC-RREO", 1), "natureza": "pdfs_nao_lidos", "anomalias": (),
        "verificados": "PDFs do RREO", "falhas": "PDFs que o extrator de produção não leu"},
    vigencia.VERIF_RETRATO_AMBIGUO: {
        "regra": ("ANOM-REG", 1), "natureza": "conformidade", "anomalias": ("CHAVE-DUP",),
        "verificados": "retrato mais recente de um corte com chave de empenho repetida",
        "falhas": "retratos recusados como vigentes (vale o retrato válido anterior do corte, ou nenhum)"},
    vigencia.VERIF_RETRATO_VALOR_RECUSADO: {
        "regra": ("VALOR-OBRIG", 1), "natureza": "conformidade", "anomalias": ("VALOR-RECUSADO",),
        "verificados": "retrato mais recente de um corte com campo monetário ausente, nulo ou inválido",
        "falhas": "retratos recusados como vigentes (vale o retrato válido anterior do corte, ou nenhum)"},
}


def diferenca(anterior, posterior):
    """The single difference rule of stage 05 (contract section 1.5): later - earlier, in integer cents. Absence on
    either side returns None: a difference is never computed against an implicit zero."""
    if anterior is None or posterior is None:
        return None
    return posterior - anterior

# Single expression for a record's cancellation: used in the indicator, the grouping and the list column (the
# interface does not sum fields on its own).
EXPR_CANCELAMENTOS = "r.cancelado_aproc_c + r.cancelado_proc_c"
# Single expression for a record's payments (indicator, grouping and the 05.5 variation; contract M-09 and M-11).
EXPR_PAGAMENTOS = "r.pago_proc_c + r.pago_aproc_c"
# Metrics of the variation investigation (05.5; contract M-10 and M-11): only these two.
METRICAS_DA_VARIACAO = {
    "s1": {"rotulo": "Saldo de RP (S1)", "sql": "d.s1_saldo_total_c", "indicador": "saldo_total",
           "formula": "S1 v1 = proc + aproc − pagoProc − pagoAProc − canceladoAProc", "natureza_do_operando": "derivado",
           "regras": {("S1", 1)}},
    "pagamentos": {"rotulo": "Pagamentos (acumulados de 01/01 até o corte)", "sql": f"({EXPR_PAGAMENTOS})",
                   "indicador": "pagamentos", "formula": "pagoProc + pagoAProc", "natureza_do_operando": "da_fonte",
                   "regras": set()},
}

# Cut-off indicators: all computed over the API records (rp_registro) and the per-record derived values
# (rp_derivado). `rreo` = RREO columns the indicator is compared with in the reconciliation (never replaced).
SOMAS = [
    dict(id="registros", rotulo="Registros de RP no corte", sql="COUNT(*)", colunas=[], regras=[],
         formula="número de registros devolvidos pela API"),
    dict(id="inscricao_processada", rotulo="RP processados inscritos (abertura do exercício)", sql="SUM(r.proc_c)",
         colunas=["proc_c"], regras=[], formula="soma de proc", rreo=["a", "b"]),
    dict(id="inscricao_nao_processada", rotulo="RP não processados inscritos (abertura do exercício)",
         sql="SUM(r.aproc_c)", colunas=["aproc_c"], regras=[], formula="soma de aproc", rreo=["f", "g"]),
    dict(id="inscricao_total", rotulo="RP inscritos (abertura do exercício)", sql="SUM(r.proc_c + r.aproc_c)",
         colunas=["proc_c", "aproc_c"], regras=[], formula="soma de proc + aproc"),
    dict(id="pago_processado", rotulo="Pago processado", sql="SUM(r.pago_proc_c)", colunas=["pago_proc_c"], regras=[],
         formula="soma de pagoProc", rreo=["c"]),
    dict(id="pago_nao_processado", rotulo="Pago não processado (inclui retenções)", sql="SUM(r.pago_aproc_c)",
         colunas=["pago_aproc_c"], regras=[], formula="soma de pagoAProc", rreo=["i"]),
    dict(id="pagamentos", rotulo="Pagamentos no período", sql=f"SUM({EXPR_PAGAMENTOS})",
         colunas=["pago_proc_c", "pago_aproc_c"], regras=[], formula="soma de pagoProc + pagoAProc"),
    dict(id="estornos_de_pagamento", rotulo="Estornos de pagamento (informativo; já descontados dos pagamentos)",
         sql="SUM(r.pago_proc_estornado_c + r.pago_aproc_estornado_c)",
         colunas=["pago_proc_estornado_c", "pago_aproc_estornado_c"], regras=[],
         formula="soma dos estornos brutos; já descontados de pagoProc e pagoAProc"),
    dict(id="liquidacoes", rotulo="Liquidações no período (líquidas de estornos)", sql="SUM(r.liquidado_c)",
         colunas=["liquidado_c"], regras=[], formula="soma de liquidado", rreo=["h"]),
    dict(id="cancelamentos", rotulo="Cancelamentos no período", sql=f"SUM({EXPR_CANCELAMENTOS})",
         colunas=["cancelado_aproc_c", "cancelado_proc_c"], regras=[],
         formula="soma de canceladoAProc + canceladoProc (este sempre 0 nos dados observados)", rreo=["d", "j"]),
    dict(id="retencoes", rotulo="Retenções no período (já contidas em pagoAProc)", sql="SUM(r.retencao_c)",
         colunas=["retencao_c"], regras=[], formula="soma de retencao; não somar aos pagamentos"),
    dict(id="saldo_total", rotulo="Saldo de RP no corte (S1)", sql="SUM(d.s1_saldo_total_c)",
         colunas=["proc_c", "aproc_c", "pago_proc_c", "pago_aproc_c", "cancelado_aproc_c"], regras=[("S1", 1)],
         formula="soma de S1 = proc + aproc − pagoProc − pagoAProc − canceladoAProc", rreo=["L"]),
    dict(id="saldo_a_liquidar", rotulo="Saldo a liquidar (S2)", sql="SUM(d.s2_a_liquidar_c)",
         colunas=["aproc_c", "liquidado_c", "cancelado_aproc_c"], regras=[("S2", 1)],
         formula="soma de S2 = aproc − liquidado − canceladoAProc"),
    dict(id="saldo_liquidado_a_pagar", rotulo="Saldo liquidado a pagar (S3)", sql="SUM(d.s3_liquidado_a_pagar_c)",
         colunas=["proc_c", "pago_proc_c", "liquidado_c", "pago_aproc_c"], regras=[("S3", 1)],
         formula="soma de S3 = proc − pagoProc + liquidado − pagoAProc"),
]
# rules the indicators and groupings depend on (S1-S3 in the balances, CAT in the grouping by category)
REGRAS_DO_INDICADOR = {("S1", 1), ("S2", 1), ("S3", 1), ("CAT", 1)}

DIMENSOES = {
    "entidade": ["r.entidade"], "anoempenho": ["r.anoempenho"], "categoria": ["d.categoria"],
    "fonte_recurso": ["r.fonte_recurso", "r.descricao_fonte"], "programatica": ["r.programatica"],
    "orgao": ["r.orgao"], "unidade": ["r.unidade"], "funcao": ["r.funcao"], "sub_funcao": ["r.sub_funcao"],
    "programa": ["r.programa"], "projeto": ["r.projeto"], "elemento": ["r.elemento"],
}
CAMPOS_REGISTRO = ["entidade", "anoempenho", "empenho", "empenho_exercicio", "data_emissao", "programatica",
                   "fonte_recurso", "descricao_fonte", "orgao", "unidade", "funcao", "sub_funcao", "programa", "projeto",
                   "elemento", "desdobra_desp", "sub_desdobramento"]
DINHEIRO = ["proc_c", "aproc_c", "cancelado_proc_c", "pago_proc_c", "pago_proc_estornado_c", "cancelado_aproc_c",
            "pago_aproc_c", "pago_aproc_estornado_c", "liquidado_c", "retencao_c"]
DERIVADOS = list(fontes.DERIVADOS)
CADEIA = ["dashboard", "camada de consulta", "derivação", "normalização", "snapshot", "resposta HTTP", "objeto bruto",
          "endpoint da API Elotech"]


class ErroDoPainel(ValueError):
    pass


class NivelInvalido(ErroDoPainel):
    pass


class RegraNaoOperacional(ErroDoPainel):
    pass


class SemProcessamento(ErroDoPainel):
    pass


class EsquemaAntigo(ErroDoPainel):
    pass


def fechamento(total, componentes):
    """Contract section 4.2: difference = sum of the components - total; it closes only with a 0 difference. No
    tolerance and no adjustment component; a value that is not an integer (bool and float included) is an error,
    never converted."""
    for v in (total, *componentes):
        if isinstance(v, bool) or not isinstance(v, int):
            raise ErroDoPainel(f"fechamento exige inteiros: {v!r}")
    soma = sum(componentes)
    return {"fecha": soma == total, "total": total, "soma_dos_grupos": soma, "diferenca": soma - total,
            "grupos": len(componentes)}


def _data_br(iso):
    """'2026-09-30T01:31:08-03:00' or '2026-09-30' -> '30/09/2026'."""
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else None


def _instante_br(iso):
    """Date (end of day) or date and time, in the Brazilian format."""
    if not iso:
        return None
    return _data_br(iso) if len(iso) == 10 or iso[11:19] == "23:59:59" else f"{_data_br(iso)} {iso[11:16]}"


def instante(em):
    """rp.instante (the same as the derivation's and the CLI's), with the panel layer's error."""
    try:
        return _instante(em)
    except DataInvalida as e:
        raise ErroDoPainel(str(e)) from e


def _in(n):
    return ",".join("?" * n)
