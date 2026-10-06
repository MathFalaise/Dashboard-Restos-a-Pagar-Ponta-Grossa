"""Catalog of rules and anomaly types (version 1).

MODEL VALIDATION - stage 03. Not production code.

Each rule points to the section of the stage 02 report that supports it and carries the
same evidence status. A rule is never edited: a change = a new version.
"""

R2 = "etapa02/RELATORIO_ETAPA02.md"

REGRAS = [
    # codigo, versao, tipo, uso, status, definicao, fonte
    ("CAT", 1, "classificacao", "estavel", "CONFIRMADO",
     "categoria = 'ambos' se proc>0 e aproc>0; 'processado' se proc>0; 'nao_processado' se aproc>0; "
     "senão 'sem_saldo_abertura'. Válida só com dataInicial = 01/01.", f"{R2} §2.2, §7"),
    ("FAIXA", 1, "classificacao", "estavel", "CONFIRMADO",
     "anoempenho = exercicio-1 → (b)/(g); anoempenho < exercicio-1 → (a)/(f).", f"{R2} §3.2"),
    ("S1", 1, "formula", "estavel", "CONFIRMADO",
     "saldo_total = proc + aproc − pagoProc − pagoAProc − canceladoAProc", f"{R2} §9"),
    ("S2", 1, "formula", "estavel", "CONFIRMADO",
     "a_liquidar = aproc − liquidado − canceladoAProc", f"{R2} §9"),
    ("S3", 1, "formula", "estavel", "CONFIRMADO",
     "liquidado_a_pagar = proc − pagoProc + liquidado − pagoAProc", f"{R2} §9"),
    ("CANC", 1, "classificacao", "estavel", "FORTE EVIDÊNCIA",
     "cancel_processado = canceladoAProc se proc>0 e aproc=0; cancel_nao_processado = canceladoAProc se aproc>0.",
     f"{R2} §6"),
    ("RREO-COL", 1, "agregacao", "estavel", "FORTE EVIDÊNCIA",
     "a=Σproc[proc>0,faixa a]; b=Σproc[proc>0,faixa b]; c=ΣpagoProc[proc>0]; d=Σcancel_processado; "
     "f=Σaproc[aproc>0,faixa f]; g=Σaproc[aproc>0,faixa g]; h=Σliquidado[aproc>0]; i=ΣpagoAProc[aproc>0]; "
     "j=ΣcanceladoAProc[aproc>0]; e=a+b−c−d; k=f+g−i−j; L=e+k. Só consulta sem tipo e dataInicial=01/01.",
     f"{R2} §3.2 (a,b,c,f,g,j CONFIRMADO; d,h,i FORTE)"),
    ("RREO-COL", 2, "agregacao", "experimental", "FORTE EVIDÊNCIA",
     "Como v1, mas o pagamento segue a CATEGORIA do registro, não o campo: c = ΣpagoProc[proc>0] + "
     "ΣpagoAProc[só-P]; i = ΣpagoAProc[aproc>0] + ΣpagoProc[só-N]. Consequência algébrica: L = ΣS1.",
     "etapa03/RELATORIO_ETAPA03.md §8 (2025 c −462,00 = 15863/2023; 2025 consolidado i −2.554,25 = 8 reg. "
     "da entidade 15; 2026 49,50 = 2410946/2025)"),
    ("MOV-REF", 1, "interpretacao", "estavel", "FORTE EVIDÊNCIA",
     "Nos lançamentos 40/41 a liquidação paga é (exercicioPagamento, noPagamento) — rótulos trocados; "
     "nos 30/31/50/51 é (exercicioLiquidacao, noLiquidacao).", f"{R2} §2.2, §10.10"),
    ("PAR-24", 1, "pareamento", "estavel", "FORTE EVIDÊNCIA",
     "Par espelhado: registro A (entidade 1, empenho ≥ 2.400.000) ↔ registro B (entidade 15, mesmo anoempenho, "
     "empenho = A − 2.400.000), no mesmo corte, com mesmo CNPJ/CPF e mesma data de emissão.",
     f"{R2} §3.5 + ADENDO"),
    ("CONS-PAR", 1, "consolidacao", "experimental", "HIPÓTESE",
     "Visão analítica: par com a mesma inscrição conta a inscrição UMA vez e soma os fluxos dos dois lados. "
     "Par com inscrição divergente ou com execução nos dois lados NÃO é consolidado (os dois lados contam) "
     "e vira anomalia.", f"{R2} ADENDO item 3; PROMPT_ETAPA03 decisões 1 e 5"),
    ("CONS-PAR", 2, "consolidacao", "experimental", "HIPÓTESE",
     "Visão analítica: se a inscrição de A (cópia) = saldo final S1 de B (original) no mesmo corte, A é o saldo "
     "remanescente de B: exclui-se a inscrição de A e somam-se os fluxos dos dois lados. Cobre também o caso "
     "de inscrições iguais sem execução em B. Execução nos dois lados: não consolida. Só verificável num corte "
     "que feche o exercício (31/12) ou em que B não tenha execução.",
     "etapa03/RELATORIO_ETAPA03.md §7 (9/9 pares de 2025: inscrição A = inscrição B − execução B)"),
    ("CONC-RREO", 1, "conciliacao", "estavel", "CONFIRMADO",
     "Diferença API − RREO por coluna. Escopo 'entidade' contra a visão da entidade; 'consolidado' contra a "
     "visão publicada. Registro de diferença, nunca correção.", f"{R2} §3.3"),
    ("ANOM-REG", 1, "anomalia", "estavel", "CONFIRMADO",
     "Regras de anomalia por registro (ver anomalia_tipo).", f"{R2} §11.4"),
    ("ANOM-CONT", 1, "anomalia", "estavel", "CONFIRMADO",
     "Continuidade: para chave presente em A e A+1, proc(A+1)=S3 final de A e aproc(A+1)=S2 final de A; "
     "chave com S1 final de A ≠ 0 tem de estar em A+1.", f"{R2} §1.3 (continuidade 1.247/1.247)"),
]

ANOMALIAS = [
    # codigo, descricao, status, fonte
    ("LIQ-NEG", "liquidado < 0 no período (estorno de liquidação)", "CONFIRMADO", f"{R2} §5"),
    ("PAGOPROC-SEM-PROC", "pagoProc ≠ 0 em registro com proc = 0", "CONFIRMADO", f"{R2} §4 caso I2"),
    ("CANCPROC-NZ", "canceladoProc ≠ 0 (campo sempre 0 até hoje)", "CONFIRMADO", f"{R2} §2.1"),
    ("COPIA-24", "entidade 1 com empenho ≥ 2.400.000 (cópia espelhada)", "CONFIRMADO", f"{R2} §3.5"),
    ("ANOEMP-FUTURO", "anoempenho ≥ exercicio consultado", "CONFIRMADO", f"{R2} §8"),
    ("SEM-SALDO-ABERTURA", "registro no universo com proc = aproc = 0", "CONFIRMADO", f"{R2} §8"),
    ("CHAVE-DUP", "mesma chave (entidade, anoempenho, empenho) duas vezes na mesma coleta", "CONFIRMADO", f"{R2} §2.1"),
    ("COPIA-SEM-PAR", "cópia 24xxxxx sem par na entidade 15 no mesmo corte", "HIPÓTESE", f"{R2} ADENDO"),
    ("PAR-INSCRICAO-DIVERGENTE", "par espelhado com proc/aproc diferentes nos dois lados", "CONFIRMADO", f"{R2} ADENDO"),
    ("PAR-EXECUCAO-DOIS-LADOS", "par espelhado com fluxo nos dois lados no mesmo corte", "HIPÓTESE", f"{R2} ADENDO"),
    ("DESCONTINUIDADE", "abertura de A+1 ≠ fechamento de A para o mesmo empenho", "CONFIRMADO", f"{R2} §11.4"),
    ("SALDO-SEM-CONTINUIDADE", "empenho com saldo final ≠ 0 em A ausente em A+1", "CONFIRMADO", f"{R2} §11.4"),
]


def semear(con):
    """Writes the catalog. Idempotent: does not reinsert what already exists."""
    for r in REGRAS:
        con.execute("INSERT OR IGNORE INTO regra (codigo, versao, tipo, uso, status_evidencia, definicao, fonte) "
                    "VALUES (?,?,?,?,?,?,?)", r)
    for a in ANOMALIAS:
        con.execute("INSERT OR IGNORE INTO anomalia_tipo (codigo, descricao, status_evidencia, fonte) VALUES (?,?,?,?)", a)


def regra_id(con, codigo, versao=1):
    return con.execute("SELECT id FROM regra WHERE codigo=? AND versao=?", (codigo, versao)).fetchone()[0]
