"""Explicacoes conhecidas das diferencas (transcricao versionada dos achados das Etapas 02-04.4).

Nada aqui e analise nova: cada entrada aponta o relatorio que a sustenta. Uma explicacao NUNCA altera o valor da
API; ela so qualifica a diferenca mostrada na area de reconciliacao. Diferenca sem entrada aparece com a situacao
"nao determinada".

EXPLICACOES: diferencas API x RREO (tabela conciliacao_rreo). Campos: exercicios, datas_finais (None = todas do
exercicio), escopo (None = entidade e consolidado), colunas (None = todas), regra ("RREO-COL v1"/"RREO-COL v2" ou
None = qualquer), classe, situacao, status_evidencia, texto, fonte.
COERENCIA: diferencas entre duas publicacoes (L do RREO de dezembro de A x (a)+(f) dos RREOs de A+1).

Classes (docs/stages/04-pipeline/REPORT_04_4.md secao 9): T = lancamento com data retroativa feito depois da emissao do RREO;
C = copias 24xxxxx ausentes do RREO; R = reclassificacao; P = regra de pagamento (RREO-COL);
E = caso isolado de entidade; H = hipotese de divisao de cancelamento; ND = nao determinada.
Situacao: explicada (valor atribuido a registros ou documentos identificados, com CONFIRMADO ou FORTE EVIDENCIA);
parcialmente explicada (so parte do valor atribuida); hipotese (causa provavel, sem atribuicao do valor a registros);
nao determinada. `status_evidencia` repete o grau de evidencia registrado no relatorio de origem.
"""

SITUACOES = ("explicada", "parcialmente explicada", "hipótese", "não determinada")

L44 = "docs/stages/04-pipeline/REPORT_04_4.md"
COR = "docs/stages/04-pipeline/CORRECTIONS_STAGES_01_TO_04_4.md"

EXPLICACOES = [
    dict(exercicios=[2024], datas_finais=["2024-12-31"], escopo="entidade", colunas=["c", "d", "e", "i", "j", "k", "L"],
         regra=None, classe="T", situacao="parcialmente explicada", status_evidencia="FORTE EVIDÊNCIA",
         texto=("As duas publicações oficiais divergem entre si: o RREO de 2024 (emitido em 30/01/2025) fecha a entidade 1 "
                "em 17.848.930,28 e a abertura de exercícios anteriores do RREO de 2025 é 18.523.356,29 (diferença de "
                "674.426,01); a API reproduz a publicação posterior (diferença temporal, FORTE EVIDÊNCIA no agregado). "
                "Localizado: o cancelamento de 2023/9459 (511.782,00), datado de 31/12/2024 e ausente do RREO emitido "
                "depois. Os demais registros responsáveis (pagamentos, estornos) não foram determinados."),
         fonte=f"docs/stages/04-pipeline/batches/LOTE_A.md seções 1, 3 e 4; docs/stages/04-pipeline/batches/LOTE_M.md; {L44} seções 7 e 9"),
    dict(exercicios=[2024], datas_finais=["2024-12-31"], escopo="consolidado", colunas=["c", "d", "e", "i", "j", "k", "L"],
         regra=None, classe="T", situacao="parcialmente explicada", status_evidencia="FORTE EVIDÊNCIA",
         texto=("No consolidado, o RREO de 2024 fecha em 18.296.817,34 e a abertura de exercícios anteriores do RREO de "
                "2025 é 18.966.578,99 (diferença de 669.761,65); a API reproduz a publicação posterior. Localizado: o "
                "cancelamento de 2023/9459 (entidade 1, 511.782,00), datado de 31/12/2024. O restante não foi atribuído "
                "a registros."),
         fonte=f"docs/stages/04-pipeline/batches/LOTE_R.md; docs/stages/04-pipeline/batches/consistencia_rreo.md; {L44} seções 8 e 9"),
    dict(exercicios=[2024], datas_finais=["2024-12-31"], escopo=None, colunas=["g", "k", "L"], regra=None, classe="C",
         situacao="explicada", status_evidencia="CONFIRMADO",
         texto=("8.410,00 = inscrição da cópia 2401751/2023 (entidade 1), par de 1751/2023 (entidade 15): está na API "
                "e não está no RREO de 2024 (confere pelo valor)."),
         fonte=f"docs/stages/04-pipeline/batches/LOTE_A.md seção 2; {L44} seções 7, 9 e 13"),
    dict(exercicios=[2025], datas_finais=None, escopo=None, colunas=["f", "g", "k", "L"], regra=None, classe="C",
         situacao="explicada", status_evidencia="CONFIRMADO",
         texto=("As 20 cópias 24xxxxx (inscrição de 925.702,62: 917.292,62 de 2024 em (g) e 8.410,00 de 2023 em (f)) "
                "estão na API e não estão em nenhum RREO de 2025; aparecem nos RREOs de 2026. O valor confere ao "
                "centavo; a causa (inserção depois das publicações) é hipótese forte."),
         fonte=f"docs/stages/04-pipeline/batches/LOTE_R.md; {L44} seções 8, 9 e 13"),
    dict(exercicios=[2024], datas_finais=["2024-12-31"], escopo=None, colunas=["a", "f"], regra=None, classe="R",
         situacao="não determinada", status_evidencia="NÃO DETERMINADO",
         texto="Reclassificação de soma zero de 1.829,50 entre processado e não processado; nenhum registro tem esse valor.",
         fonte=f"docs/stages/04-pipeline/batches/LOTE_A.md seção 5; {L44} seção 9"),
    dict(exercicios=[2024], datas_finais=["2024-12-31"], escopo="entidade", colunas=["d", "j"], regra=None, classe="R",
         situacao="não determinada", status_evidencia="NÃO DETERMINADO",
         texto="Reclassificação de 3.972,66 entre cancelamento de processado (d) e de não processado (j); registros não determinados.",
         fonte=f"docs/stages/04-pipeline/batches/LOTE_A.md seção 3; {L44} seção 9"),
    dict(exercicios=[2025], datas_finais=None, escopo=None, colunas=["a", "f", "d", "j"], regra=None, classe="R",
         situacao="não determinada", status_evidencia="NÃO DETERMINADO",
         texto="Reclassificação de soma zero de 1.829,50 entre (a)/(f) e (d)/(j); nenhum registro tem esse valor.",
         fonte=f"docs/stages/02-accounting-validation/REPORT.md seção 7; {L44} seção 9"),
    dict(exercicios=[2026], datas_finais=["2026-02-28"], escopo=None, colunas=["a", "f", "d", "j"], regra=None, classe="R",
         situacao="não determinada", status_evidencia="NÃO DETERMINADO",
         texto="A mesma reclassificação de 1.829,50 aparece no 1º bimestre de 2026.", fonte=f"{L44} seção 9"),
    dict(exercicios=[2024], datas_finais=["2024-12-31"], escopo=None, colunas=["f"], regra=None, classe="R",
         situacao="explicada", status_evidencia="FORTE EVIDÊNCIA",
         texto=("2.951,48 = 2011/21040 (entidade 1): estorno de liquidação em 11/01/2024; os RREOs emitidos depois dessa data o tratam "
                "como não processado, e a API o mantém processado na abertura."),
         fonte=f"docs/stages/04-pipeline/batches/LOTE_C.md; docs/stages/04-pipeline/batches/LOTE_M.md; {L44} seção 9"),
    dict(exercicios=[2024], datas_finais=["2024-12-31"], escopo="entidade", colunas=["h"], regra=None, classe="R",
         situacao="hipótese", status_evidencia="HIPÓTESE",
         texto=("(h) +2.951,48: o RREO parece somar em (h) a liquidação negativa de 2011/21040, que a regra RREO-COL não "
                "soma por o registro ser só processado na API (candidato, não confirmado)."),
         fonte="docs/stages/04-pipeline/batches/LOTE_A.md seção 5"),
    dict(exercicios=[2023], datas_finais=["2023-12-31"], escopo=None, colunas=["f"], regra=None, classe="R",
         situacao="explicada", status_evidencia="FORTE EVIDÊNCIA",
         texto=("2.951,48 = 2011/21040: estorno de liquidação em 11/01/2024; o RREO de 2023, emitido em 29/01/2024, "
                "já o trata como não processado; a API o mantém processado na abertura."),
         fonte=f"docs/stages/04-pipeline/batches/LOTE_C.md; docs/stages/04-pipeline/batches/LOTE_M.md; {L44} seção 9"),
    dict(exercicios=[2025], datas_finais=["2025-06-30"], escopo=None, colunas=["d", "e", "j", "k", "L"], regra=None,
         classe="T", situacao="explicada", status_evidencia="FORTE EVIDÊNCIA",
         texto=("O RREO do 3º bimestre de 2025 (emitido em 29/07/2025) não tem cancelamentos com data no semestre que o "
                "4º bimestre (emitido em 26/09/2025) já inclui: foram lançados entre as duas emissões."),
         fonte=f"docs/stages/04-pipeline/batches/LOTE_R.md; {L44} seção 9"),
    dict(exercicios=[2026], datas_finais=["2026-02-28"], escopo=None, colunas=None, regra=None, classe="T",
         situacao="explicada", status_evidencia="FORTE EVIDÊNCIA",
         texto=("O RREO do 1º bimestre de 2026 (emitido em 27/03/2026) difere da API; o do 2º bimestre (emitido em "
                "29/05/2026) já a reproduz, salvo (h) +644,16."),
         fonte=f"docs/stages/04-pipeline/batches/LOTE_R.md; {L44} seção 9"),
    dict(exercicios=[2026], datas_finais=["2026-04-30"], escopo=None, colunas=["h"], regra=None, classe="ND",
         situacao="não determinada", status_evidencia="NÃO DETERMINADO", texto="(h) +644,16 no 2º bimestre de 2026.",
         fonte="docs/stages/03-data-model/REPORT.md; docs/stages/02-accounting-validation/REPORT.md"),
    dict(exercicios=[2026], datas_finais=["2026-06-30", "2026-08-31"], escopo=None, colunas=["h", "i", "k", "L"],
         regra=None, classe="ND", situacao="não determinada", status_evidencia="NÃO DETERMINADO",
         texto=("A API mostra menos liquidado e pago que o RREO no 3º e no 4º bimestre de 2026 (entidade 1); a causa "
                "não foi determinada."),
         fonte=f"docs/stages/02-accounting-validation/REPORT.md; docs/stages/04-pipeline/REPORT_04_3.md; {L44} seção 9"),
    dict(exercicios=[2026], datas_finais=["2026-06-30", "2026-08-31"], escopo="consolidado", colunas=["c", "e", "i"],
         regra=None, classe="E", situacao="hipótese", status_evidencia="HIPÓTESE",
         texto=("Entidade 5, empenho 1485/2025: pagoProc 9.773,02 acima do inscrito processado 6.080,77 (excesso "
                "3.692,25); hipótese de que o RREO limita o pago processado ao inscrito (1 caso)."),
         fonte=f"docs/stages/04-pipeline/REPORT_04_3.md; {L44} seção 9"),
    dict(exercicios=[2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025], datas_finais=None, escopo=None,
         colunas=["c", "e", "i", "k", "L"], regra="RREO-COL v1", classe="P", situacao="parcialmente explicada",
         status_evidencia="FORTE EVIDÊNCIA",
         texto=("Com a RREO-COL v1 o pagamento segue o campo da API; com a v2 (experimental), que segue a categoria do "
                "registro, a diferença em (c)/(i) desaparece ou diminui. Compare com a linha da v2."),
         fonte=f"docs/stages/03-data-model/REPORT.md seção 8; {L44} seções 9 e 14"),
    dict(exercicios=[2022], datas_finais=["2022-12-31"], escopo=None, colunas=["d", "e", "L"], regra=None, classe="ND",
         situacao="não determinada", status_evidencia="NÃO DETERMINADO", texto="(d) −159.904,72 em 2022.",
         fonte="docs/stages/04-pipeline/batches/LOTE_C.md; docs/stages/04-pipeline/batches/hipotese_canc_2020_2026.md"),
    dict(exercicios=[2020], datas_finais=["2020-12-31"], escopo=None, colunas=["d", "e", "j", "k"], regra=None, classe="H",
         situacao="hipótese", status_evidencia="HIPÓTESE",
         texto=("Troca (d)/(j) de 249.027,59 (14 registros 'ambos'): a hipótese do excedente de cancelamento sobre o "
                "aproc a fecha ao centavo; CANC v2 é candidata, não criada."),
         fonte="docs/stages/04-pipeline/batches/LOTE_D.md; docs/stages/04-pipeline/batches/hipotese_canc_2020_2026.md"),
    dict(exercicios=[2021], datas_finais=["2021-12-31"], escopo="consolidado", colunas=["d", "e", "j", "k"], regra=None,
         classe="H", situacao="hipótese", status_evidencia="HIPÓTESE",
         texto="Troca (d)/(j) de 757,56: excedente de cancelamento de 2019/1684 (entidade 6) sobre o aproc.",
         fonte="docs/stages/04-pipeline/batches/LOTE_D.md; docs/stages/04-pipeline/batches/hipotese_canc_2020_2026.md"),
    dict(exercicios=[2020], datas_finais=["2020-12-31"], escopo="consolidado", colunas=["f", "k", "L"], regra=None,
         classe="ND", situacao="não determinada", status_evidencia="NÃO DETERMINADO",
         texto="(f) −180.334,82 de outra entidade que não a 1; o PDF consolidado não detalha por órgão.",
         fonte=f"docs/stages/04-pipeline/batches/LOTE_D.md; {L44} seções 9 e 15"),
    dict(exercicios=[2017], datas_finais=["2017-12-31"], escopo=None, colunas=["h"], regra=None, classe="ND",
         situacao="não determinada", status_evidencia="NÃO DETERMINADO", texto="(h) +1.065.159,06 em 2017.",
         fonte=f"docs/stages/04-pipeline/batches/LOTE_F.md; {L44} seção 9"),
    dict(exercicios=[2017], datas_finais=["2017-12-31"], escopo=None, colunas=["d", "e", "j", "k"], regra=None,
         classe="H", situacao="hipótese", status_evidencia="HIPÓTESE",
         texto=("Com a hipótese do excedente (7 registros 'ambos'), (j) fecha ao centavo em 2017 e (d) fica em "
                "−95.522,00 (script da 04.4 reexecutado sobre a base completa na revisão de 30/09/2026)."),
         fonte=f"docs/stages/04-pipeline/batches/hipotese_canc.py; {COR}"),
]

COERENCIA = [
    dict(escopos=("entidade", "consolidado"), de=2025, classe="C", situacao="explicada", status_evidencia="CONFIRMADO",
         texto=("925.702,62 = inscrição das 20 cópias 24xxxxx: ausentes de todos os RREOs de 2025 e presentes nos de "
                "2026 (confere pelo valor)."),
         fonte=f"{L44} seções 9 e 12; docs/stages/04-pipeline/batches/consistencia_rreo.md"),
    dict(escopos=("entidade",), de=2024, classe="T", situacao="parcialmente explicada", status_evidencia="FORTE EVIDÊNCIA",
         texto=("Diferença temporal entre as publicações (FORTE EVIDÊNCIA no agregado): a API reproduz a abertura "
                "publicada em 2025. Localizado o cancelamento de 2023/9459 (511.782,00), datado de 31/12/2024 e ausente "
                "do RREO de 2024; os demais registros responsáveis não foram determinados."),
         fonte=f"docs/stages/04-pipeline/batches/LOTE_A.md; {L44} seções 7, 9 e 12"),
    dict(escopos=("consolidado",), de=2024, classe="T", situacao="hipótese", status_evidencia="FORTE EVIDÊNCIA",
         texto=("Salto entre publicações: lançamentos com data retroativa feitos depois da emissão (FORTE EVIDÊNCIA no "
                "agregado; registros localizados só em parte)."),
         fonte=f"{L44} seção 9; docs/stages/04-pipeline/batches/consistencia_rreo.md"),
    dict(escopos=("entidade", "consolidado"), de=2022, classe="T", situacao="hipótese", status_evidencia="FORTE EVIDÊNCIA",
         texto=("Salto entre publicações: lançamentos com data retroativa feitos depois da emissão (FORTE EVIDÊNCIA no "
                "agregado; registros não localizados)."),
         fonte=f"{L44} seção 9; docs/stages/04-pipeline/batches/consistencia_rreo.md"),
    dict(escopos=("entidade", "consolidado"), de=2023, classe="T", situacao="hipótese", status_evidencia="FORTE EVIDÊNCIA",
         texto=("Salto entre publicações: lançamentos com data retroativa feitos depois da emissão (FORTE EVIDÊNCIA no "
                "agregado; registros não localizados)."),
         fonte=f"{L44} seção 9; docs/stages/04-pipeline/batches/consistencia_rreo.md"),
    dict(escopos=("consolidado",), de=2020, classe="ND", situacao="não determinada", status_evidencia="NÃO DETERMINADO",
         texto="−180.334,82 de outra entidade que não a 1; o PDF consolidado não detalha por órgão.",
         fonte=f"{L44} seções 9, 12 e 15"),
]

CAMPOS_SAIDA = ("classe", "situacao", "status_evidencia", "texto", "fonte")


def resumo(achadas):
    """Situacao de uma diferenca a partir das entradas aplicaveis. Cada entrada costuma cobrir PARTE do valor,
    entao a diferenca so e 'explicada' quando todas as entradas sao explicadas; havendo parte explicada e parte
    nao, e 'parcialmente explicada'."""
    s = {e["situacao"] for e in achadas}
    if not s:
        return "não determinada"
    if s == {"explicada"}:
        return "explicada"
    if s & {"explicada", "parcialmente explicada"}:
        return "parcialmente explicada"
    return "hipótese" if "hipótese" in s else "não determinada"


def explicar(exercicio, data_final, escopo, coluna, regra):
    """Entradas aplicaveis a uma diferenca API x RREO e a situacao resumida (ver `resumo`)."""
    achadas = [e for e in EXPLICACOES
               if exercicio in e["exercicios"]
               and (e["datas_finais"] is None or data_final in e["datas_finais"])
               and (e["escopo"] is None or e["escopo"] == escopo)
               and (e["colunas"] is None or coluna in e["colunas"])
               and (e["regra"] is None or e["regra"] == regra)]
    return achadas, resumo(achadas)


def explicar_coerencia(escopo, de):
    """Entradas aplicaveis a uma diferenca entre publicacoes (A = `de`) e a situacao resumida."""
    achadas = [e for e in COERENCIA if escopo in e["escopos"] and e["de"] == de]
    return achadas, resumo(achadas)
