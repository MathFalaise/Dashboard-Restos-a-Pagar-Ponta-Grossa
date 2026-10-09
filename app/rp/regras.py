"""Catalog of rules and anomaly types (production).

Same codes and versions as stage 03 (docs/stages/03-data-model/REPORT.md section 6.1). Every rule carries its evidence
status and source. `uso='experimental'` means: computed and identified, NEVER promoted to default automatically.

Business parameters (the pair's entities, the copies' base 2,400,000, the entity of the per-entity RREO) live in
PARAMETROS, tied to the rule VERSION, and go to the immutable regra_parametro table. The code reads the rule's
parameters instead of repeating numbers; changing a parameter requires a new rule version.
The usage situation of each version (operational, experimental, not recommended...) lives in governanca.py.
"""
import json

from . import governanca

E2 = "etapa02/RELATORIO_ETAPA02.md"
E3 = "etapa03/RELATORIO_ETAPA03.md"

# codigo, versao, tipo, uso, status_evidencia, definicao, fonte
REGRAS = [
    ("CAT", 1, "classificacao", "estavel", "CONFIRMADO",
     "categoria: 'ambos' se proc>0 e aproc>0; 'processado' se proc>0; 'nao_processado' se aproc>0; "
     "senão 'sem_saldo_abertura'. Semântica RREO só com dataInicial = 01/01.", f"{E2} §2.2, §7"),
    ("FAIXA", 1, "classificacao", "estavel", "CONFIRMADO",
     "anoempenho = exercicio−1 → (b)/(g); anoempenho < exercicio−1 → (a)/(f).", f"{E2} §3.2"),
    ("S1", 1, "formula", "estavel", "CONFIRMADO",
     "saldo_total = proc + aproc − pagoProc − pagoAProc − canceladoAProc", f"{E2} §9"),
    ("S2", 1, "formula", "estavel", "CONFIRMADO", "a_liquidar = aproc − liquidado − canceladoAProc", f"{E2} §9"),
    ("S3", 1, "formula", "estavel", "CONFIRMADO", "liquidado_a_pagar = proc − pagoProc + liquidado − pagoAProc", f"{E2} §9"),
    ("CANC", 1, "classificacao", "estavel", "FORTE EVIDÊNCIA",
     "cancel_processado = canceladoAProc se proc>0 e aproc=0; cancel_nao_processado = canceladoAProc se aproc>0.", f"{E2} §6"),
    ("RREO-COL", 1, "agregacao", "estavel", "FORTE EVIDÊNCIA",
     "a/b = Σproc[proc>0] por faixa; c = ΣpagoProc[proc>0]; d = Σcancel_processado; f/g = Σaproc[aproc>0] por faixa; "
     "h = Σliquidado[aproc>0]; i = ΣpagoAProc[aproc>0]; j = ΣcanceladoAProc[aproc>0]; e=a+b−c−d; k=f+g−i−j; L=e+k. "
     "Pagamento segue o CAMPO da API. Só consulta sem tipo com dataInicial = 01/01.", f"{E2} §3.2"),
    ("RREO-COL", 2, "agregacao", "experimental", "FORTE EVIDÊNCIA",
     "Como v1, mas o pagamento segue a CATEGORIA do registro: c += ΣpagoAProc[só-P]; i += ΣpagoProc[só-N]. "
     "Consequência: L = ΣS1.", f"{E3} §8"),
    ("MOV-REF", 1, "interpretacao", "estavel", "FORTE EVIDÊNCIA",
     "Lançamentos 40/41: a liquidação paga é (exercicioPagamento, noPagamento) — rótulos trocados; "
     "30/31/50/51: (exercicioLiquidacao, noLiquidacao).", f"{E2} §2.2"),
    ("PAR-24", 1, "pareamento", "estavel", "FORTE EVIDÊNCIA",
     "A (entidade 1, empenho ≥ 2.400.000) ↔ B (entidade 15, mesmo anoempenho, empenho − 2.400.000), mesmo corte, "
     "mesmo CNPJ/CPF e mesma data de emissão.", f"{E2} §3.5 + ADENDO"),
    ("CONS-PAR", 1, "consolidacao", "experimental", "HIPÓTESE",
     "Visão analítica: inscrições iguais e execução em no máximo um lado → a inscrição de B sai; fluxos dos dois lados ficam.",
     f"{E2} ADENDO"),
    ("CONS-PAR", 2, "consolidacao", "experimental", "HIPÓTESE",
     "Visão analítica: inscrição de A = inscrição de B ou = S1 final de B → A é remanescente; a inscrição de A sai; "
     "fluxos dos dois lados ficam. Execução nos dois lados: não consolida.", f"{E3} §7.2"),
    ("CONC-RREO", 1, "conciliacao", "estavel", "CONFIRMADO",
     "Diferença API − RREO por coluna, para cada regra de agregação. Registro, nunca correção.", f"{E2} §3.3"),
    ("ANOM-REG", 1, "anomalia", "estavel", "CONFIRMADO", "Anomalias por registro (ver anomalia_tipo).", f"{E2} §11.4"),
    ("VALOR-OBRIG", 1, "anomalia", "estavel", "CONFIRMADO",
     "Campo monetário da listagem de RP ausente, nulo ou inválido: o registro não vira valor (nunca zero) e o "
     "retrato do corte nunca é o vigente.", "pedido de correção de 09/10/2026, item 2 (contrato da API v2)"),
    ("ANOM-CONT", 1, "anomalia", "estavel", "CONFIRMADO",
     "Continuidade: proc(A+1)=S3 final de A e aproc(A+1)=S2 final de A; saldo final ≠ 0 exige presença em A+1.",
     f"{E2} §1.3"),
]

ANOMALIAS = [
    ("LIQ-NEG", "liquidado < 0 no período (estorno de liquidação)", "CONFIRMADO", f"{E2} §5"),
    ("PAGOPROC-SEM-PROC", "pagoProc ≠ 0 em registro com proc = 0", "CONFIRMADO", f"{E2} §4"),
    ("CANCPROC-NZ", "canceladoProc ≠ 0 (campo sempre 0 até hoje)", "CONFIRMADO", f"{E2} §2.1"),
    ("COPIA-24", "entidade 1 com empenho ≥ 2.400.000 (cópia espelhada)", "CONFIRMADO", f"{E2} §3.5"),
    ("ANOEMP-FUTURO", "anoempenho ≥ exercicio consultado", "CONFIRMADO", f"{E2} §8"),
    ("SEM-SALDO-ABERTURA", "registro no universo com proc = aproc = 0", "CONFIRMADO", f"{E2} §8"),
    ("CHAVE-DUP", "mesma chave (entidade, anoempenho, empenho) duas vezes no mesmo snapshot", "CONFIRMADO", f"{E2} §2.1"),
    ("VALOR-RECUSADO", "campo monetário ausente, nulo ou inválido no registro (recusado na normalização)",
     "CONFIRMADO", "pedido de correção de 09/10/2026, item 2"),
    ("COPIA-SEM-PAR", "cópia 24xxxxx sem par na entidade 15 no mesmo corte", "HIPÓTESE", f"{E2} ADENDO"),
    ("PAR-INSCRICAO-DIVERGENTE", "par espelhado com proc/aproc diferentes nos dois lados", "CONFIRMADO", f"{E2} ADENDO"),
    ("PAR-EXECUCAO-DOIS-LADOS", "par espelhado com fluxo nos dois lados no mesmo corte", "HIPÓTESE", f"{E2} ADENDO"),
    ("DESCONTINUIDADE", "abertura de A+1 ≠ fechamento de A para o mesmo empenho", "CONFIRMADO", f"{E2} §11.4"),
    ("SALDO-SEM-CONTINUIDADE", "empenho com saldo final ≠ 0 em A ausente em A+1", "CONFIRMADO", f"{E2} §11.4"),
]


# (codigo, versao) -> structured parameters. Transcription of the rule's definition: same meaning, without numbers
# scattered through the code. A new value = a new rule version (the regra_parametro table accepts no edits).
PARAMETROS = {
    ("PAR-24", 1): {"entidade_copia": 1, "entidade_original": 15, "base_empenho_copia": 2400000,
                    "campos_de_conferencia": ["cnpj", "data_emissao"]},
    ("CONC-RREO", 1): {"entidade_do_rreo_por_entidade": 1},
}


class CatalogoDivergente(Exception):
    """The catalog recorded in the database is not the code's for a version that already exists."""


def conferir_catalogo(con):
    """Differences between the code's catalog and the database's (empty list = equal). Since semear uses INSERT OR
    IGNORE, editing in the code the definition, status, a parameter or a decision of an ALREADY recorded version would
    not reach the database and nobody would know (audit DB-03). A decision recorded only in the database
    (registrar_decisao) is not a divergence."""
    problemas = []
    for codigo, versao, *resto in REGRAS:
        row = con.execute("SELECT tipo, uso, status_evidencia, definicao, fonte FROM regra WHERE codigo=? AND versao=?",
                          (codigo, versao)).fetchone()
        if row is not None and tuple(row) != tuple(resto):
            problemas.append(f"regra {codigo} v{versao}: banco {tuple(row)!r} × código {tuple(resto)!r}")
    for codigo, *resto in ANOMALIAS:
        row = con.execute("SELECT descricao, status_evidencia, fonte FROM anomalia_tipo WHERE codigo=?", (codigo,)).fetchone()
        if row is not None and tuple(row) != tuple(resto):
            problemas.append(f"tipo de anomalia {codigo}: banco {tuple(row)!r} × código {tuple(resto)!r}")
    R = ids(con)
    for (codigo, versao), valores in PARAMETROS.items():
        if (codigo, versao) not in R:
            continue
        banco = {n: json.loads(v) for n, v in con.execute("SELECT nome, valor_json FROM regra_parametro WHERE regra_id=?",
                                                          (R[(codigo, versao)],))}
        if banco and banco != json.loads(json.dumps(valores)):
            problemas.append(f"parâmetros de {codigo} v{versao}: banco {banco!r} × código {valores!r}")
    for codigo, versao, situacao, status, compoe, sup, motivo, fonte, quando, origem in governanca.EVENTOS:
        if (codigo, versao) not in R:
            continue
        row = con.execute("SELECT situacao, status_evidencia, compoe_indicador_publicado, supersedida_por, motivo, fonte, "
                          "origem_decisao FROM regra_situacao WHERE regra_id=? AND decidido_em=? AND evidencia_externa_id "
                          "IS NULL ORDER BY id LIMIT 1", (R[(codigo, versao)], quando)).fetchone()
        esperado = (situacao, status, compoe, R.get(sup) if sup else None, motivo, fonte, origem)
        if row is not None and tuple(row) != esperado:
            problemas.append(f"decisão de {codigo} v{versao} em {quando}: banco {tuple(row)!r} × código {esperado!r}")
    return problemas


def semear(con):
    """Catalog of rules, anomaly types, rule parameters and governance decisions (all idempotent).
    Then checks that the database has exactly the code's catalog; a divergence -> CatalogoDivergente (a rule change
    requires a new version, never an edit)."""
    _inserir(con)
    problemas = conferir_catalogo(con)
    if problemas:
        raise CatalogoDivergente(f"{len(problemas)} divergência(s) entre o catálogo do código e o do banco "
                                 f"(crie versão nova em vez de editar): {'; '.join(problemas[:3])}")


def _inserir(con):
    for r in REGRAS:
        con.execute("INSERT OR IGNORE INTO regra (codigo, versao, tipo, uso, status_evidencia, definicao, fonte) "
                    "VALUES (?,?,?,?,?,?,?)", r)
    for a in ANOMALIAS:
        con.execute("INSERT OR IGNORE INTO anomalia_tipo (codigo, descricao, status_evidencia, fonte) VALUES (?,?,?,?)", a)
    R = ids(con)
    for (codigo, versao), valores in PARAMETROS.items():
        for nome, valor in valores.items():
            con.execute("INSERT OR IGNORE INTO regra_parametro VALUES (?,?,?)",
                        (R[(codigo, versao)], nome, json.dumps(valor, sort_keys=True)))
    governanca.semear(con, R)


class ParametroAusente(KeyError):
    pass


def parametros(con, codigo, versao):
    """Recorded parameters of a rule version (read from the database; never from a constant in the code)."""
    linhas = con.execute("SELECT p.nome, p.valor_json FROM regra_parametro p JOIN regra r ON r.id = p.regra_id "
                         "WHERE r.codigo=? AND r.versao=?", (codigo, versao)).fetchall()
    if not linhas:
        raise ParametroAusente(f"regra {codigo} v{versao} sem parametros registrados")
    return {nome: json.loads(valor) for nome, valor in linhas}


def ids(con):
    """{(codigo, versao): id} of every rule in the catalog."""
    return {(c, v): i for i, c, v in con.execute("SELECT id, codigo, versao FROM regra")}
