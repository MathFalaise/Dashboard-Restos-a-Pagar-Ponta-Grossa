"""NON-destructive governance of the rules.

The `regra` table is immutable (trigger): a rule version is never edited or deleted. The usage situation of each
version is a HISTORY of decisions in `regra_situacao` (also immutable: append-only):

  operacional      may produce values of the published indicator (if compoe_indicador_publicado = 1)
  experimental     computed side by side, never enters the published indicator
  nao_recomendada  later evidence weakened the rule; still computed for history and comparison, but it should not
                   be the only basis of new calculations
  supersedida      replaced by another version (supersedida_por)
  aposentada       no longer computed

The current situation of a rule is the most recent decision (decidido_em, then id). The old decision stays there.
The events below are the versioned transcription of those decisions; `semear` copies them into the database
(INSERT OR IGNORE). A new decision = a new event at the end of the list (or `registrar_decisao`), never an edit of
an old event.

Promotion to operational (critical review decision D7, valid since POLITICA_PROMOCAO_DESDE), on two tracks:
  * a rule that does NOT make up a published indicator (quality, anomalies, pairing): documented evidence (`fonte`)
    + a regression test (`teste_regressao` = "tests/<file>.py::<test>", which must exist);
  * a rule that makes up a published indicator: the same + a recorded independent check (`evidencia_externa_id`:
    RREO, e-SIC...). If there is none, or the e-SIC does not answer in time (PRAZO_CONFERENCIA_DIAS), the documented
    way out is to promote it with a `ressalva` (the reason), shown in the methodology: "operacional com ressalva".
A new promotion only through `registrar_decisao` (or `python -m rp decidir-regra`), never through a new event in
EVENTOS; the v5 database refuses, by trigger, a promotion outside the criteria.
"""
from pathlib import Path

from . import agora
from .banco import POLITICA_PROMOCAO_DESDE

PRAZO_CONFERENCIA_DIAS = 30            # e-SIC: 20 days + 10 of extension (Law 12.527/2011, art. 11)
TESTES = Path(__file__).resolve().parents[1] / "tests"

SITUACOES = ("operacional", "experimental", "nao_recomendada", "supersedida", "aposentada")
STATUS = ("CONFIRMADO", "FORTE EVIDÊNCIA", "HIPÓTESE", "NÃO DETERMINADO")

E3 = "etapa03/RELATORIO_ETAPA03.md secao 6.1"
E44 = "etapa04/RELATORIO_04_4.md"
REV = "etapa04/REVISAO_CODIGO_20260930.md"
COR = "etapa04/CORRECOES_ETAPAS_01_A_04_4.md"
CATALOGO = "catalogo das Etapas 03/04.2: uso e status de evidencia originais"
CORRETIVA = "especificacao da revisao corretiva 01-04.4 (usuario, 30/09/2026)"

# (codigo, versao, situacao, status_evidencia, compoe_indicador_publicado, supersedida_por, motivo, fonte, decidido_em, origem)
EVENTOS = [
    # ---- 29/09/2026: classification inherited from the catalog (use 'estavel' -> operacional; 'experimental' -> experimental)
    ("CAT", 1, "operacional", "CONFIRMADO", 1, None, "classificacao do registro por proc/aproc na abertura", E3, "2026-09-29", CATALOGO),
    ("FAIXA", 1, "operacional", "CONFIRMADO", 1, None, "faixa por anoempenho (exercicio anterior x anteriores)", E3, "2026-09-29", CATALOGO),
    ("S1", 1, "operacional", "CONFIRMADO", 1, None, "saldo total do registro", E3, "2026-09-29", CATALOGO),
    ("S2", 1, "operacional", "CONFIRMADO", 1, None, "saldo a liquidar do registro", E3, "2026-09-29", CATALOGO),
    ("S3", 1, "operacional", "CONFIRMADO", 1, None, "saldo liquidado a pagar do registro", E3, "2026-09-29", CATALOGO),
    ("CANC", 1, "operacional", "FORTE EVIDÊNCIA", 1, None, "divisao de canceladoAProc entre processado e nao processado", E3, "2026-09-29", CATALOGO),
    ("RREO-COL", 1, "operacional", "FORTE EVIDÊNCIA", 1, None, "agregacao dos registros nas colunas do RREO; pagamento segue o campo", E3, "2026-09-29", CATALOGO),
    ("RREO-COL", 2, "experimental", "FORTE EVIDÊNCIA", 0, None, "pagamento segue a categoria do registro", E3, "2026-09-29", CATALOGO),
    ("MOV-REF", 1, "operacional", "FORTE EVIDÊNCIA", 1, None, "interpretacao dos rotulos dos lancamentos 40/41", E3, "2026-09-29", CATALOGO),
    ("PAR-24", 1, "operacional", "FORTE EVIDÊNCIA", 0, None, "identifica pares copia 24xxxxx <-> original; nao altera valor", E3, "2026-09-29", CATALOGO),
    ("CONS-PAR", 1, "experimental", "HIPÓTESE", 0, None, "visao analitica: retira a inscricao de B em par igual", E3, "2026-09-29", CATALOGO),
    ("CONS-PAR", 2, "experimental", "HIPÓTESE", 0, None, "visao analitica: retira a inscricao de A", E3, "2026-09-29", CATALOGO),
    ("CONC-RREO", 1, "operacional", "CONFIRMADO", 0, None, "registro da diferenca API - RREO; nunca corrige", E3, "2026-09-29", CATALOGO),
    ("ANOM-REG", 1, "operacional", "CONFIRMADO", 0, None, "anomalias por registro", E3, "2026-09-29", CATALOGO),
    ("ANOM-CONT", 1, "operacional", "CONFIRMADO", 0, None, "continuidade fechamento -> abertura", E3, "2026-09-29", CATALOGO),
    # ---- 30/09/2026: corrective review (evidence from 04.4 and from the code review)
    ("RREO-COL", 1, "nao_recomendada", "HIPÓTESE", 0, None,
     "A evidencia de 2017-2026 (04.4) enfraqueceu a v1: nunca concilia mais colunas que a v2 e concilia menos em "
     "documentos de 2020, 2021, 2022 e 2025; seu L = e + k nao e o saldo (difere da soma de S1). Preservada para "
     "historico e calculada lado a lado na reconciliacao; nao usar como regra unica de agregacao.",
     f"{E44} secoes 8 e 14; {REV} item 17; {COR}", "2026-09-30", CORRETIVA),
    ("RREO-COL", 2, "experimental", "FORTE EVIDÊNCIA", 0, None,
     "Mais consistente que a v1 em 2017-2025, mas sem criterio de promocao aprovado: continua experimental e fora "
     "do indicador publicado.", f"{E44} secao 14; {COR}", "2026-09-30", CORRETIVA),
    ("CANC", 1, "nao_recomendada", "HIPÓTESE", 0, None,
     "Diverge da divisao (d)/(j) dos RREOs consolidados de 2017 a 2021; a hipotese do excedente fecha (j) nesses "
     "anos mas piora 2022 e 2023. Continua calculada (derivacao inalterada); o total de cancelamentos "
     "(canceladoAProc) nao depende dela.", f"{E44} secao 9; {REV} item 18; {COR}", "2026-09-30", CORRETIVA),
    ("CONS-PAR", 1, "experimental", "HIPÓTESE", 0, None,
     "04.4: nao fecha 2025 em nenhum corte e, em 2026, quebra a conciliacao (o RREO conta os dois lados). "
     "So visao analitica; o lado original do par nunca e apagado.", f"{E44} secao 14; {COR}", "2026-09-30", CORRETIVA),
    ("CONS-PAR", 2, "experimental", "HIPÓTESE", 0, None,
     "04.4: so reproduz 2025 em 31/12; 'saldo final de B' avaliado no corte muda a relacao ao longo do ano, e a "
     "hipotese temporal (copias inseridas depois das publicacoes) explica o mesmo. So visao analitica.",
     f"{E44} secao 14; {COR}", "2026-09-30", CORRETIVA),
    ("PAR-24", 1, "operacional", "FORTE EVIDÊNCIA", 0, None,
     "Parametros estruturados em regra_parametro (entidades 1/15, base 2.400.000, conferencia por CNPJ/CPF e data): "
     "transcricao da definicao, sem mudanca de significado. A natureza das copias continua NAO DETERMINADA.",
     COR, "2026-09-30", CORRETIVA),
    ("CONC-RREO", 1, "operacional", "CONFIRMADO", 0, None,
     "Parametro estruturado: o RREO 'por entidade' e comparado com a entidade 1 (Prefeitura). Uma divergencia "
     "nunca altera o valor da API.", COR, "2026-09-30", CORRETIVA),
]


class DecisaoInvalida(ValueError):
    pass


def semear(con, R):
    """Copies EVENTOS into regra_situacao (idempotent). `R` = {(codigo, versao): id}."""
    for codigo, versao, situacao, status, compoe, sup, motivo, fonte, quando, origem in EVENTOS:
        con.execute("INSERT OR IGNORE INTO regra_situacao (regra_id, situacao, status_evidencia, compoe_indicador_publicado, "
                    "supersedida_por, motivo, fonte, evidencia_externa_id, decidido_em, origem_decisao) "
                    "VALUES (?,?,?,?,?,?,?,NULL,?,?)",
                    (R[(codigo, versao)], situacao, status, compoe, R[sup] if sup else None, motivo, fonte, quando, origem))


def teste_existe(referencia):
    """Does 'tests/<file>.py::<test>' exist (file and function) in app/tests?"""
    arq, _, nome = str(referencia or "").partition("::")
    if not (arq.startswith("tests/") and arq.endswith(".py") and nome.isidentifier() and nome.startswith("test")):
        return False
    caminho = TESTES.parent / arq
    try:
        return (caminho.resolve().is_relative_to(TESTES.resolve())
                and f"def {nome}(" in caminho.read_text(encoding="utf-8"))
    except OSError:
        return False


def _conferir_promocao(situacao, compoe, fonte, teste_regressao, evidencia_externa_id, ressalva):
    """Decision D7 criteria for a promotion to operational (see the module docstring)."""
    if situacao != "operacional":
        return
    if not str(fonte or "").strip():
        raise DecisaoInvalida("promocao a operacional exige evidencia documentada (fonte)")
    if not teste_existe(teste_regressao):
        raise DecisaoInvalida("promocao a operacional exige teste de regressao existente "
                              f"('tests/<arquivo>.py::<teste>'): {teste_regressao!r}")
    if compoe and evidencia_externa_id is None and not str(ressalva or "").strip():
        raise DecisaoInvalida("regra que compoe indicador publicado exige conferencia independente (evidencia externa "
                              f"registrada) ou, sem ela no prazo de {PRAZO_CONFERENCIA_DIAS} dias, ressalva documentada")


def registrar_decisao(con, codigo, versao, situacao, status_evidencia, compoe_indicador_publicado, motivo, fonte, origem,
                      supersedida_por=None, evidencia_externa_id=None, decidido_em=None, teste_regressao=None,
                      ressalva=None):
    """Appends a decision to the history (never edits). Returns the event id. A promotion to operational follows the
    decision D7 criteria (module docstring)."""
    if situacao not in SITUACOES or status_evidencia not in STATUS:
        raise DecisaoInvalida(f"situacao/status invalido: {situacao!r}, {status_evidencia!r}")
    if compoe_indicador_publicado and situacao != "operacional":
        raise DecisaoInvalida("so regra operacional pode compor o indicador publicado")
    if ressalva is not None and situacao != "operacional":
        raise DecisaoInvalida("ressalva so existe na promocao a operacional")
    _conferir_promocao(situacao, compoe_indicador_publicado, fonte, teste_regressao, evidencia_externa_id, ressalva)
    ids = {(c, v): i for i, c, v in con.execute("SELECT id, codigo, versao FROM regra")}
    if (codigo, versao) not in ids or (supersedida_por and tuple(supersedida_por) not in ids):
        raise DecisaoInvalida(f"regra inexistente: {codigo} v{versao} / {supersedida_por}")
    if evidencia_externa_id is not None and not con.execute("SELECT 1 FROM evidencia_externa WHERE id=?",
                                                            (evidencia_externa_id,)).fetchone():
        raise DecisaoInvalida(f"evidencia externa {evidencia_externa_id} nao registrada")
    with con:
        return con.execute("INSERT INTO regra_situacao (regra_id, situacao, status_evidencia, compoe_indicador_publicado, "
                           "supersedida_por, motivo, fonte, evidencia_externa_id, decidido_em, origem_decisao, "
                           "teste_regressao, ressalva) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                           (ids[(codigo, versao)], situacao, status_evidencia, int(bool(compoe_indicador_publicado)),
                            ids[tuple(supersedida_por)] if supersedida_por else None, motivo, fonte, evidencia_externa_id,
                            decidido_em or agora(), origem, teste_regressao,
                            str(ressalva).strip() if ressalva is not None else None)).lastrowid


def situacao_atual(con):
    """{(codigo, versao): most recent decision} with the full history of each rule."""
    atual = {}
    for (codigo, versao, uso, status0, rid, sid, situacao, status, compoe, sup, motivo, fonte, evid, quando,
         origem, teste, ressalva) in con.execute(
            "SELECT r.codigo, r.versao, r.uso, r.status_evidencia, r.id, s.id, s.situacao, s.status_evidencia, "
            "s.compoe_indicador_publicado, s.supersedida_por, s.motivo, s.fonte, s.evidencia_externa_id, s.decidido_em, "
            "s.origem_decisao, s.teste_regressao, s.ressalva FROM regra r LEFT JOIN regra_situacao s "
            "ON s.regra_id = r.id "
            "ORDER BY r.codigo, r.versao, s.decidido_em, s.id"):
        item = atual.setdefault((codigo, versao), {"codigo": codigo, "versao": versao, "uso_original": uso,
                                                   "status_evidencia_original": status0, "historico": []})
        if sid is not None:
            decisao = {"situacao": situacao, "status_evidencia": status, "compoe_indicador_publicado": bool(compoe),
                       "supersedida_por": sup, "motivo": motivo, "fonte": fonte, "evidencia_externa_id": evid,
                       "decidido_em": quando, "origem_decisao": origem, "teste_regressao": teste, "ressalva": ressalva}
            item["historico"].append(decisao)
            item.update({k: decisao[k] for k in ("situacao", "status_evidencia", "compoe_indicador_publicado",
                                                 "ressalva")})
    for item in atual.values():   # a rule with no recorded decision cannot make up the published indicator
        item.setdefault("situacao", None)
        item.setdefault("status_evidencia", item["status_evidencia_original"])
        item.setdefault("compoe_indicador_publicado", False)
        item.setdefault("ressalva", None)
    return atual
