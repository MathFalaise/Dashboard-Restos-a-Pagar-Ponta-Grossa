"""Camada de consulta do dashboard: SOMENTE LEITURA sobre o banco do projeto.

Fluxo:  API Elotech -> coleta -> snapshot imutavel -> normalizacao -> derivacao -> ESTA CAMADA -> dashboard.
  * Nao chama a API: le o banco aberto em modo read-only (URI mode=ro + PRAGMA query_only). A coleta continua
    sendo do coletor; nenhuma tela depende do portal estar no ar.
  * Indicador principal = registros da API Elotech (somas de campos e formulas S1-S3). O RREO so aparece na
    reconciliacao, lado a lado; uma divergencia nunca altera o valor da API.
  * Todo valor sai com: natureza (da_fonte, publicado, derivado, analitico, diferenca), regras usadas com a
    situacao de governanca, fonte declarada, rotulo de retrato e proveniencia (derivacao -> normalizacao ->
    snapshot -> resposta HTTP -> objeto bruto -> endpoint).
  * Regra que nao esteja 'operacional' com compoe_indicador_publicado = 1 nunca entra num indicador publicado
    (RegraNaoOperacional). Valor calculado por regra nao operacional sai como 'analitico'.
  * Um exercicio historico e o estado da base na data da coleta, nao o que era conhecido naquele ano.
  * Entidade fora do catalogo oficial do exercicio NAO e entidade com RP zero: aparece como nao aplicavel e nao
    entra no total do Municipio.
  * So entram snapshots que a normalizacao em uso processou: snapshot novo, ainda nao processado, vira aviso
    (nunca um corte com valor zero).
  * Nivel 'publico' (padrao) nunca devolve identificacao de credor em listas nem agregados (ver publico.py).
"""
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from .. import BRT, banco, governanca, regras
from ..comparador import comparar as _comparar
from . import explicacoes, fontes, publico

VERSAO = "rp-painel/1"
ESQUEMA_MINIMO = 4          # regra_situacao, regra_parametro e rreo_extracao existem a partir da v4
NIVEIS = ("publico", "interno")
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
LIMITE_LISTA = 500
CATEGORIAS = ("processado", "nao_processado", "ambos", "sem_saldo_abertura")
ORDEM_COLUNAS = "abcdefghijkL"          # ordem das colunas no Anexo VII do RREO
# Situacao do dado de uma entidade num corte. So 'com_dados' e 'sem_rp' tem valor; 'sem_rp' e o unico zero de
# verdade (a entidade existia e a API devolveu zero registros). Os demais nunca viram R$ 0,00.
SITUACOES_DO_DADO = {
    "com_dados": "dado existente",
    "sem_rp": "entidade existente, sem RP neste corte (zero registros na API)",
    "inexistente": "entidade inexistente no exercício (fora do catálogo oficial; não é RP zero)",
    "sem_coleta": "corte não coletado",
    "nao_processado": "corte coletado, mas ainda não processado",
    "incompleto": "dado indisponível: só há coleta incompleta ou com falha deste corte",
    "divergente": "dado com diferença em relação ao RREO (a diferença é mostrada; o valor da API não muda)",
}
# Situacao de um PONTO de serie (etapa05/CONTRATO_ANALITICO.md secao 2): estende a taxonomia acima, sem outra
# paralela. 'municipio_indisponivel' entra na 05.2; 'exercicio_sem_cobertura' entra na 05.3.
SITUACOES_DO_PONTO = {
    **{k: v for k, v in SITUACOES_DO_DADO.items() if k != "divergente"},
    "municipio_indisponivel": "Município indisponível: alguma entidade do catálogo do exercício sem snapshot processado "
                              "neste corte",
    "exercicio_sem_cobertura": "exercício sem cobertura: nenhuma coleta deste exercício no banco",
}
TEM_VALOR = ("com_dados", "sem_rp")
# Indicadores da serie no exercicio (contrato M-01 e M-02)
INDICADORES_DA_SERIE = ("inscricao_total", "pagamentos", "liquidacoes", "cancelamentos", "saldo_total")
ROTULO_POSTERIOR_A_COLETA = "corte posterior à coleta: valores até a data da coleta"
ROTULO_EXERCICIO_EM_ABERTO = "exercício em aberto: último corte com o Município disponível"
INDICADORES_ENTRE_EXERCICIOS = ("inscricao_total", "pagamentos", "cancelamentos", "saldo_total")
CONTINUIDADE = "continuidade fechamento→abertura"          # descricao gravada pela derivacao (ANOM-CONT v1)
# Composicao do corte (Subetapa 05.4; contrato M-05 a M-08): cada dimensao fecha SOZINHA com o total do corte.
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
# Investigacao de variacoes (Subetapa 05.5; contrato M-09 a M-12); as metricas ficam em METRICAS_DA_VARIACAO.
CLASSES_DA_CHAVE = {"nos_dois": "nos dois cortes", "so_posterior": "presente só no corte posterior",
                    "so_anterior": "ausente no corte posterior"}
TOP_DA_VARIACAO = 10
CAMPOS_DO_HISTORICO = ("proc_c", "aproc_c", "pago_proc_c", "pago_aproc_c", "liquidado_c", "cancelado_aproc_c",
                       "s1_saldo_total_c")
# Qualidade dos dados (Subetapa 05.6; contrato secao 6): estruturas gravadas pela derivacao, so lidas (regime
# "derivacao"). O significado de "falhas" depende da verificacao (R5): catalogo por descricao literal e regra;
# descricao fora do catalogo sai com os numeros brutos e "significado nao catalogado", nunca por analogia.
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
}


def diferenca(anterior, posterior):
    """Unica regra de diferenca da Etapa 05 (contrato secao 1.5): posterior - anterior, em centavos inteiros. Ausencia
    em qualquer lado devolve None: diferenca nunca e calculada contra zero implicito."""
    if anterior is None or posterior is None:
        return None
    return posterior - anterior

# Expressao unica do cancelamento de um registro: usada no indicador, no agrupamento e na coluna da lista (a
# interface nao soma campos por conta propria).
EXPR_CANCELAMENTOS = "r.cancelado_aproc_c + r.cancelado_proc_c"
# Expressao unica dos pagamentos de um registro (indicador, agrupamento e variacao da 05.5; contrato M-09 e M-11).
EXPR_PAGAMENTOS = "r.pago_proc_c + r.pago_aproc_c"
# Metricas da investigacao de variacoes (05.5; contrato M-10 e M-11): so estas duas.
METRICAS_DA_VARIACAO = {
    "s1": {"rotulo": "Saldo de RP (S1)", "sql": "d.s1_saldo_total_c", "indicador": "saldo_total",
           "formula": "S1 v1 = proc + aproc − pagoProc − pagoAProc − canceladoAProc", "natureza_do_operando": "derivado",
           "regras": {("S1", 1)}},
    "pagamentos": {"rotulo": "Pagamentos (acumulados de 01/01 até o corte)", "sql": f"({EXPR_PAGAMENTOS})",
                   "indicador": "pagamentos", "formula": "pagoProc + pagoAProc", "natureza_do_operando": "da_fonte",
                   "regras": set()},
}

# Indicadores do corte: todos calculados sobre os registros da API (rp_registro) e os derivados por registro
# (rp_derivado). `rreo` = colunas do RREO com que o indicador e comparado na reconciliacao (nunca substituido).
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
# regras de que os indicadores e os agrupamentos dependem (S1-S3 nos saldos, CAT no agrupamento por categoria)
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
    """Contrato secao 4.2: diferenca = soma dos componentes - total; fecha so com diferenca 0. Sem tolerancia e sem
    componente de ajuste; valor que nao seja inteiro (inclusive bool e float) e erro, nunca convertido."""
    for v in (total, *componentes):
        if isinstance(v, bool) or not isinstance(v, int):
            raise ErroDoPainel(f"fechamento exige inteiros: {v!r}")
    soma = sum(componentes)
    return {"fecha": soma == total, "total": total, "soma_dos_grupos": soma, "diferenca": soma - total,
            "grupos": len(componentes)}


def _data_br(iso):
    """'2026-09-30T01:31:08-03:00' ou '2026-09-30' -> '30/09/2026'."""
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else None


def _instante_br(iso):
    """Data (fim do dia) ou data e hora, no formato brasileiro."""
    if not iso:
        return None
    return _data_br(iso) if len(iso) == 10 or iso[11:19] == "23:59:59" else f"{_data_br(iso)} {iso[11:16]}"


def instante(em):
    """'AAAA-MM-DD' (fim do dia) ou data/hora ISO -> ISO com fuso de Brasilia, no formato de coleta.coletada_em.
    A comparacao com coletada_em e textual, por isso todo instante e convertido para -03:00."""
    if em is None:
        return None
    try:
        d = datetime.fromisoformat(str(em))
    except ValueError as e:
        raise ErroDoPainel(f"data invalida para 'como estava em': {em!r} (use AAAA-MM-DD ou ISO com fuso)") from e
    if len(str(em)) == 10:
        d = d.replace(hour=23, minute=59, second=59, tzinfo=BRT)
    d = d.replace(tzinfo=BRT) if d.tzinfo is None else d.astimezone(BRT)
    return d.isoformat(timespec="seconds")


def _in(n):
    return ",".join("?" * n)


class Painel:
    """Consultas de leitura para o dashboard. Use Painel.abrir(caminho_do_banco) (conexao so de leitura)."""

    def __init__(self, con, nivel="publico"):
        if nivel not in NIVEIS:
            raise NivelInvalido(f"nivel precisa ser um de {NIVEIS}: {nivel!r}")
        self.con, self.nivel = con, nivel
        # tipo de credor calculado no SQL pela mesma funcao da camada publica (registrar funcao nao escreve no banco)
        con.create_function("tipo_credor", 1, publico.tipo_credor, deterministic=True)

    @classmethod
    def abrir(cls, caminho, nivel="publico"):
        """Conexao SOMENTE LEITURA ao banco (o painel nunca escreve). Exige esquema v4 ou mais novo."""
        p = Path(caminho).expanduser()
        if not p.is_file():
            raise FileNotFoundError(f"banco nao encontrado: {p}")
        con = sqlite3.connect(f"{p.resolve().as_uri()}?mode=ro", uri=True)
        try:
            con.execute("PRAGMA query_only = ON")
            try:
                versao = banco.versao_esquema(con)
            except sqlite3.DatabaseError as e:
                raise ErroDoPainel(f"{p} nao e um banco do projeto ({e})") from e
            if versao is None or versao < ESQUEMA_MINIMO:
                raise EsquemaAntigo(f"banco na v{versao}; o painel exige v{ESQUEMA_MINIMO}. Rode qualquer comando "
                                    "de 'python -m rp' uma vez: a migracao faz backup antes e so acrescenta tabelas.")
            return cls(con, nivel)
        except Exception:
            con.close()
            raise

    def fechar(self):
        self.con.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.fechar()

    # ------------------------------------------------------------------ contexto
    def contexto(self):
        """Derivacao atual mais recente, a normalizacao sobre a qual ela foi feita e o maior id de coleta que essa
        normalizacao leu (normalizacao_execucao.ultima_coleta_id). Os ids de coleta so crescem (a camada 0 nao
        apaga), entao toda coleta com id ate esse limite ja estava no banco quando a normalizacao rodou.
        Normalizacao anterior ao esquema v4 (sem o registro): limite = maior coleta com linha na camada 1, o que
        e conservador (snapshot vazio mais novo que ela fica como nao processado, nunca como zero)."""
        d = self.con.execute("SELECT id, normalizacao_id, derivador_versao, executada_em, hash_resultado FROM "
                             "derivacao_execucao WHERE vigencia_em IS NULL ORDER BY id DESC LIMIT 1").fetchone()
        if not d:
            raise SemProcessamento("nenhuma derivacao atual: rode 'python -m rp processar'")
        n = self.con.execute("SELECT id, normalizador_versao, executada_em, ultima_coleta_id FROM normalizacao_execucao "
                             "WHERE id=?", (d[1],)).fetchone()
        limite = n[3]
        if limite is None:
            limite = max(self.con.execute(f"SELECT IFNULL(MAX(coleta_id), 0) FROM {t} WHERE normalizacao_id=?",
                                          (n[0],)).fetchone()[0]
                         for t in ("rp_registro", "movimentacao_lancamento", "rreo_valor", "rreo_extracao",
                                   "entidade_ref", "exercicio_ref"))
        return {"derivacao": {"id": d[0], "versao": d[2], "executada_em": d[3], "hash_resultado": d[4], "vigencia_em": None},
                "normalizacao": {"id": n[0], "versao": n[1], "executada_em": n[2]}, "limite_coleta": limite,
                "painel": VERSAO}

    def _vigentes(self, ctx, em):
        """Snapshot vigente de cada corte de listagem: mesma regra de derivar.coletas_vigentes (o mais recente ate
        `em`, desempate por snapshot_uid), restrita aos snapshots que a normalizacao do contexto processou."""
        sql = ("SELECT id, entidade, exercicio, data_inicial, data_final FROM coleta WHERE tipo='rp_listagem' "
               "AND status='completa' AND tipo_pesquisa IS NULL AND id <= ?" + (" AND coletada_em <= ?" if em else "")
               + " ORDER BY coletada_em, snapshot_uid")
        vig = {}
        for cid, e, ex, di, df in self.con.execute(sql, (ctx["limite_coleta"], em) if em else (ctx["limite_coleta"],)):
            vig[(e, ex, di, df)] = cid
        return vig

    def _pendentes(self, ctx):
        return self.con.execute("SELECT COUNT(*) FROM coleta WHERE tipo='rp_listagem' AND id > ?",
                                (ctx["limite_coleta"],)).fetchone()[0]

    # ------------------------------------------------------------------ catalogo historico de entidades
    def _catalogo(self, ctx, em):
        """Catalogo de entidades e, por entidade, o catalogo de exercicios: os snapshots mais recentes ate `em`
        (mesma escolha de derivar._entidades_do_catalogo), entre os processados."""
        nid, lim = ctx["normalizacao"]["id"], ctx["limite_coleta"]
        filtro, p = (" AND coletada_em <= ?", (em,)) if em else ("", ())
        ents, snap_ent = {}, None
        c = self.con.execute("SELECT id, snapshot_uid, coletada_em FROM coleta WHERE tipo='entidades' AND "
                             "status='completa' AND id <= ?" + filtro + " ORDER BY coletada_em DESC, snapshot_uid DESC "
                             "LIMIT 1", (lim, *p)).fetchone()
        if c:
            snap_ent = {"snapshot_uid": c[1], "coletada_em": c[2]}
            for e, nome, cnpj, tipo in self.con.execute("SELECT entidade, nome, cnpj, tipo FROM entidade_ref "
                                                        "WHERE normalizacao_id=? AND coleta_id=?", (nid, c[0])):
                ents[e] = {"nome": nome, "cnpj": cnpj, "tipo": tipo}
        exerc = {}
        for e, cid, uid, quando in self.con.execute(
                "SELECT entidade, id, snapshot_uid, coletada_em FROM coleta WHERE tipo='exercicios' AND "
                "status='completa' AND id <= ?" + filtro + " ORDER BY coletada_em, snapshot_uid", (lim, *p)):
            exerc[e] = {"coleta_id": cid, "snapshot_uid": uid, "coletada_em": quando}   # fica o mais recente
        for info in exerc.values():
            info["exercicios"] = sorted(x for (x,) in self.con.execute(
                "SELECT exercicio FROM exercicio_ref WHERE normalizacao_id=? AND coleta_id=?", (nid, info["coleta_id"])))
        return {"entidades": ents, "snapshot_entidades": snap_ent, "exercicios": exerc}

    @staticmethod
    def _status_no_exercicio(cat, entidade, exercicio):
        info = cat["exercicios"].get(entidade)
        if info is None or not info["exercicios"]:
            return "sem catálogo de exercícios"
        return "no catálogo oficial" if exercicio in info["exercicios"] else "fora do catálogo oficial"

    def entidades(self, exercicio=None, em=None):
        """Catalogo historico: para cada entidade, periodo oficial, periodo observado e situacao no exercicio."""
        ctx, em = self.contexto(), instante(em)
        cat = self._catalogo(ctx, em)
        observados = {}
        for (e, ex, di, df) in self._vigentes(ctx, em):
            observados.setdefault(e, set()).add(ex)
        saida = []
        for e in sorted(set(cat["entidades"]) | set(cat["exercicios"]) | set(observados)):
            info, ofic, obs = cat["entidades"].get(e, {}), cat["exercicios"].get(e), sorted(observados.get(e, ()))
            item = {"entidade": e, "nome": info.get("nome"), "cnpj": info.get("cnpj"), "tipo": info.get("tipo"),
                    "no_catalogo_de_entidades": e in cat["entidades"],
                    "primeiro_exercicio_oficial": ofic["exercicios"][0] if ofic and ofic["exercicios"] else None,
                    "ultimo_exercicio_oficial": ofic["exercicios"][-1] if ofic and ofic["exercicios"] else None,
                    "exercicios_oficiais": ofic["exercicios"] if ofic else None,
                    "exercicios_com_snapshot": obs,
                    "origem_catalogo": {"entidades": cat["snapshot_entidades"],
                                        "exercicios": {k: ofic[k] for k in ("snapshot_uid", "coletada_em")} if ofic else None}}
            if exercicio is not None:
                item["situacao_no_exercicio"] = self._status_no_exercicio(cat, e, exercicio)
            saida.append(item)
        return {"exercicio": exercicio, "como_estava_em": em, "entidades": saida,
                "nota": ("O catálogo de entidades é o que a API devolve hoje; entidade extinta que não conste dele não "
                         "é conhecida. 'Fora do catálogo oficial' significa que a entidade não existia no exercício, "
                         "o que é diferente de ter RP zero: ela não entra no total do Município.")}

    # ------------------------------------------------------------------ corte
    def _estado_sem_snapshot(self, ctx, e, exercicio, di, data_final, em):
        """Por que uma entidade nao tem snapshot processado no corte: nunca coletado, coletado e ainda nao
        processado, ou so coletas incompletas/com falha. Olha todas as coletas do corte ate `em` (inclusive as
        posteriores a normalizacao em uso)."""
        filtro_em, p_em = (" AND coletada_em <= ?", (em,)) if em else ("", ())
        linhas = self.con.execute(
            "SELECT id, status FROM coleta WHERE tipo='rp_listagem' AND tipo_pesquisa IS NULL AND entidade=? AND "
            "exercicio=? AND data_inicial=? AND data_final=?" + filtro_em, (e, exercicio, di, data_final, *p_em)).fetchall()
        if any(st == "completa" and cid > ctx["limite_coleta"] for cid, st in linhas):
            return "nao_processado"
        if any(st != "completa" for _, st in linhas):
            return "incompleto"
        return "sem_coleta"

    def _corte(self, ctx, exercicio, data_final, entidade, em, vig=None, cat=None):
        di = f"{exercicio}-01-01"
        vig = self._vigentes(ctx, em) if vig is None else vig
        cat = self._catalogo(ctx, em) if cat is None else cat
        com_snapshot = {e for (e, ex, d0, df) in vig if ex == exercicio and d0 == di and df == data_final}
        universo = [entidade] if entidade is not None else sorted(set(cat["entidades"]) | com_snapshot)
        itens, somar, faltam, fora, avisos = [], [], [], [], []
        filtro_em, p_em = (" AND coletada_em <= ?", (em,)) if em else ("", ())
        for e in universo:
            status = self._status_no_exercicio(cat, e, exercicio)
            cid = vig.get((e, exercicio, di, data_final))
            item = {"entidade": e, "nome": cat["entidades"].get(e, {}).get("nome"), "situacao_no_exercicio": status,
                    "snapshot": None, "entra_no_total": False,
                    "retratos_do_corte": self.con.execute(
                        "SELECT COUNT(*) FROM coleta WHERE tipo='rp_listagem' AND tipo_pesquisa IS NULL AND entidade=? AND "
                        "exercicio=? AND data_inicial=? AND data_final=? AND id <= ?" + filtro_em,
                        (e, exercicio, di, data_final, ctx["limite_coleta"], *p_em)).fetchone()[0],
                    "retrato_mais_novo_nao_processado": bool(self.con.execute(
                        "SELECT 1 FROM coleta WHERE tipo='rp_listagem' AND tipo_pesquisa IS NULL AND status='completa' "
                        "AND entidade=? AND exercicio=? AND data_inicial=? AND data_final=? AND id > ?" + filtro_em,
                        (e, exercicio, di, data_final, ctx["limite_coleta"], *p_em)).fetchone())}
            if cid is not None:
                uid, quando = self.con.execute("SELECT snapshot_uid, coletada_em FROM coleta WHERE id=?", (cid,)).fetchone()
                n = self.con.execute("SELECT COUNT(*) FROM rp_registro WHERE normalizacao_id=? AND coleta_id=?",
                                     (ctx["normalizacao"]["id"], cid)).fetchone()[0]
                item["snapshot"] = {"snapshot_uid": uid, "coletada_em": quando, "registros": n}
            if status == "fora do catálogo oficial":
                fora.append(e)
                estado = "inexistente"
                if item["snapshot"] and item["snapshot"]["registros"]:
                    avisos.append(f"entidade {e} fora do catálogo oficial de {exercicio} com registros no snapshot: "
                                  "não somados ao Município")
            elif cid is None:
                faltam.append(e)
                estado = self._estado_sem_snapshot(ctx, e, exercicio, di, data_final, em)
            else:
                somar.append(cid)
                item["entra_no_total"] = True
                estado = "sem_rp" if item["snapshot"]["registros"] == 0 else "com_dados"
            item["situacao_do_dado"] = {"codigo": estado, "texto": SITUACOES_DO_DADO[estado]}
            itens.append(item)
        if entidade is not None and fora:
            motivo = "entidade fora do catálogo oficial do exercício: não existia; não é RP zero"
        elif faltam:
            por_estado = {}
            for i in itens:
                if i["entidade"] in faltam:
                    por_estado.setdefault(i["situacao_do_dado"]["codigo"], []).append(i["entidade"])
            motivo = "; ".join(f"{SITUACOES_DO_DADO[k]} para a(s) entidade(s) {v}" for k, v in por_estado.items())
        elif not somar:
            motivo = "nenhuma entidade do catálogo oficial com snapshot neste corte"
        else:
            motivo = None
        coletadas = [i["snapshot"]["coletada_em"] for i in itens if i["entra_no_total"]]
        uids = [i["snapshot"]["snapshot_uid"] for i in itens if i["entra_no_total"]]
        return {"exercicio": exercicio, "data_inicial": di, "data_final": data_final, "entidade": entidade, "em": em,
                "entidades": itens, "fora_do_catalogo": fora, "faltam": faltam, "somar": somar, "avisos": avisos,
                "disponivel": motivo is None, "motivo": motivo,
                "retrato": self._retrato(exercicio, data_final, coletadas, em, uids)}

    @staticmethod
    def _retrato(exercicio, data_final, coletadas, em, snapshots=None):
        """Rotulo obrigatorio de todo valor: retrato atual ou 'como a base estava em', com os snapshots usados."""
        if not coletadas:
            return None
        ini, fim = min(coletadas), max(coletadas)
        d0, d1 = _data_br(ini), _data_br(fim)
        quando = f"coletado em {d0}" if d0 == d1 else f"coletado entre {d0} e {d1}"
        base = f"exercício de {exercicio}, corte {_data_br(data_final)}, {quando}"
        texto = f"Como a base estava em {_instante_br(em)}: {base}" if em else f"Estado atual da base para o {base}"
        return {"tipo": "historico" if em else "atual", "texto": texto, "exercicio": exercicio, "data_final": data_final,
                "coletado_de": ini, "coletado_ate": fim, "como_estava_em": em, "snapshots": snapshots or [],
                "corte_posterior_a_coleta": data_final > ini[:10],   # ex.: corte 31/12 coletado em setembro
                "nota": fontes.METODOLOGIA["importante"]}

    def cortes(self, em=None):
        """Cortes com snapshot processado: entidades cobertas e se o total do Municipio esta disponivel."""
        ctx, em = self.contexto(), instante(em)
        vig, cat = self._vigentes(ctx, em), self._catalogo(ctx, em)
        por_corte = {}
        for (e, ex, di, df) in vig:
            if di == f"{ex}-01-01":
                por_corte.setdefault((ex, df), set()).add(e)
        saida = []
        for (ex, df), ents in sorted(por_corte.items()):
            c = self._corte(ctx, ex, df, None, em, vig, cat)
            saida.append({"exercicio": ex, "data_final": df, "entidades_com_snapshot": sorted(ents),
                          "municipio_disponivel": c["disponivel"], "motivo": c["motivo"],
                          "fora_do_catalogo": c["fora_do_catalogo"]})
        return {"como_estava_em": em, "cortes": saida, "snapshots_nao_processados": self._pendentes(ctx)}

    # ------------------------------------------------------------------ governanca e proveniencia
    def _regras_publicaveis(self, usadas):
        atual = governanca.situacao_atual(self.con)
        saida = []
        for codigo, versao in sorted(usadas):
            g = atual.get((codigo, versao))
            if not g or g["situacao"] != "operacional" or not g["compoe_indicador_publicado"]:
                raise RegraNaoOperacional(f"{codigo} v{versao} nao pode compor indicador publicado "
                                          f"(situacao atual: {g and g['situacao']})")
            saida.append({"codigo": codigo, "versao": versao, "situacao": g["situacao"],
                          "status_evidencia": g["status_evidencia"]})
        return saida

    def _snapshot(self, cid):
        c = self.con.execute("SELECT snapshot_uid, tipo, entidade, exercicio, data_inicial, data_final, coletada_em, "
                             "origem_carimbo, status, manifesto, endpoint, parametros_json FROM coleta WHERE id=?",
                             (cid,)).fetchone()
        respostas = [{"ordem": o, "url": u, "http_status": st, "recebida_em": q, "objeto_bruto_sha256": h, "tamanho": t}
                     for o, u, st, q, h, t in self.con.execute(
                         "SELECT ordem, url, http_status, recebida_em, sha256, tamanho FROM resposta_bruta "
                         "WHERE coleta_id=? ORDER BY ordem", (cid,))]
        return {"snapshot_uid": c[0], "tipo": c[1], "entidade": c[2], "exercicio": c[3], "data_inicial": c[4],
                "data_final": c[5], "coletada_em": c[6], "origem_carimbo": c[7], "status": c[8], "manifesto": c[9],
                "endpoint": c[10], "parametros": json.loads(c[11]), "respostas": respostas}

    def _proveniencia(self, ctx, coletas, consulta):
        return {"cadeia": CADEIA, "fonte": fontes.ELOTECH["id"], "consulta": consulta, "derivacao": ctx["derivacao"],
                "normalizacao": ctx["normalizacao"], "snapshots": [self._snapshot(c) for c in coletas]}

    @staticmethod
    def _prov_curta(ctx, uids, consulta, regras_usadas):
        return {"snapshots": uids, "derivacao_id": ctx["derivacao"]["id"],
                "derivacao_hash": ctx["derivacao"]["hash_resultado"], "normalizacao_id": ctx["normalizacao"]["id"],
                "consulta": consulta, "regras": regras_usadas, "detalhe": "ver 'proveniencia' no topo da resposta"}

    def _uids(self, coletas):
        return [self.con.execute("SELECT snapshot_uid FROM coleta WHERE id=?", (c,)).fetchone()[0] for c in coletas]

    # ------------------------------------------------------------------ indicadores
    def _de_coletas(self, coletas):
        """Filtro dos registros de um conjunto de coletas pela chave primaria (resposta_id IN ...)."""
        ph = _in(len(coletas))
        return (f"r.resposta_id IN (SELECT id FROM resposta_bruta WHERE coleta_id IN ({ph})) AND r.coleta_id IN ({ph})",
                (*coletas, *coletas))

    def _somas(self, ctx, coletas, filtro_extra="", params_extra=()):
        """Somas de SOMAS sobre os registros das coletas (com filtro opcional). Sem filtro, confere que a derivacao
        cobre todo registro do corte: se nao cobrir, nao ha total (erro, nunca um total menor)."""
        filtro, p = self._de_coletas(coletas)
        linha = self.con.execute(
            f"SELECT {', '.join(s['sql'] for s in SOMAS)} FROM rp_registro r JOIN rp_derivado d ON d.derivacao_id=? "
            f"AND d.resposta_id=r.resposta_id AND d.indice=r.indice WHERE r.normalizacao_id=? AND {filtro}{filtro_extra}",
            (ctx["derivacao"]["id"], ctx["normalizacao"]["id"], *p, *params_extra)).fetchone()
        valores = {s["id"]: (v or 0) for s, v in zip(SOMAS, linha)}
        if filtro_extra:
            return valores
        n = self.con.execute(f"SELECT COUNT(*) FROM rp_registro r WHERE r.normalizacao_id=? AND {filtro}",
                             (ctx["normalizacao"]["id"], *p)).fetchone()[0]
        if n != valores["registros"]:   # a derivacao cobre todo registro processado; se nao cobrir, nao ha total
            raise ErroDoPainel(f"derivacao {ctx['derivacao']['id']} sem os valores derivados de {n - valores['registros']} "
                               "registro(s) do corte: reprocesse ('python -m rp processar')")
        return valores

    @staticmethod
    def _campos(colunas):
        return [{"coluna": c, "campo_api": fontes.CAMPOS[c][0], "rotulo": fontes.CAMPOS[c][1]} for c in colunas]

    def indicadores(self, exercicio, data_final, entidade=None, em=None):
        """Indicadores do corte (uma entidade ou o Municipio) a partir dos registros da API Elotech."""
        ctx, em = self.contexto(), instante(em)
        corte = self._corte(ctx, exercicio, data_final, entidade, em)
        regras_usadas = self._regras_publicaveis(REGRAS_DO_INDICADOR)
        uids = self._uids(corte["somar"])
        somas = self._somas(ctx, corte["somar"]) if corte["disponivel"] else {}
        rec = self._reconciliacao_do_corte(ctx, exercicio, data_final, entidade, em) if corte["disponivel"] else {}
        valores = {}
        for s in SOMAS:
            regs = [r for r in regras_usadas if (r["codigo"], r["versao"]) in set(s["regras"])]
            consulta = f"{s['formula']} sobre os registros dos snapshots do corte"
            valores[s["id"]] = {
                "id": s["id"], "rotulo": s["rotulo"], "valor_c": somas.get(s["id"]), "unidade": "centavos",
                "natureza": "derivado", "campos": self._campos(s["colunas"]), "formula": s["formula"], "regras": regs,
                "fonte": fontes.ELOTECH["rotulo"], "retrato": corte["retrato"],
                "motivo_indisponivel": None if corte["disponivel"] else corte["motivo"],
                "proveniencia": self._prov_curta(ctx, uids, consulta, regs),
                "reconciliacao_rreo": [x for x in rec.get("linhas", []) if x["coluna"] in s.get("rreo", [])],
            }
        categorias = []
        if corte["disponivel"]:
            regs_cat = [r for r in regras_usadas if r["codigo"] in ("CAT", "S1")]
            for g in sorted(self._por_grupo(ctx, corte["somar"], ["d.categoria"]), key=lambda g: str(g["chave"][0])):
                categorias.append({"categoria": g["chave"][0], "registros": g["registros"],
                                   "inscricao_total_c": g["inscricao_total_c"], "saldo_total_c": g["saldo_total_c"],
                                   "natureza": "derivado", "regras": regs_cat,
                                   "proveniencia": self._prov_curta(ctx, uids, "agrupamento por categoria (CAT v1)",
                                                                    regs_cat)})
        avisos = [fontes.METODOLOGIA["importante"]] + corte["avisos"]
        if self._pendentes(ctx):
            avisos.append("Há snapshots de listagem ainda não processados; rode 'python -m rp processar'.")
        return {"consulta": {"exercicio": exercicio, "data_final": data_final, "entidade": entidade, "como_estava_em": em},
                "escopo": f"entidade {entidade}" if entidade is not None else "Município (entidades do catálogo oficial do exercício)",
                "disponivel": corte["disponivel"], "motivo_indisponivel": corte["motivo"], "retrato": corte["retrato"],
                "fonte": fontes.ELOTECH["rotulo"], "entidades": corte["entidades"], "valores": valores,
                "categorias": categorias, "reconciliacao": rec.get("resumo"),
                "conferencia_rreo": self._conferencia_saldo(somas, rec, exercicio, data_final) if corte["disponivel"] else None,
                "avisos": avisos,
                "proveniencia": self._proveniencia(ctx, corte["somar"], "somas sobre rp_registro + rp_derivado")}

    @staticmethod
    def _conferencia_saldo(somas, rec, exercicio, data_final):
        """Saldo S1 da API (indicador, regra operacional) ao lado da coluna L do RREO do mesmo corte: comparacao,
        nunca substituicao. Nao usa RREO-COL: o saldo e o da formula S1 e o L e o impresso no PDF."""
        linhas = [x for x in rec.get("linhas", []) if x["coluna"] == "L"]
        if not linhas:
            return None
        x = linhas[0]              # o L do RREO e o mesmo nas linhas de RREO-COL v1 e v2 (mesmo PDF)
        dif = somas["saldo_total"] - x["rreo_c"]
        achadas, situacao = explicacoes.explicar(exercicio, data_final, x["escopo"], "L", None) if dif else ([], "sem diferença")
        return {"escopo": x["escopo"], "periodo": x["periodo"],
                "api": {"rotulo": "Saldo de RP no corte (S1)", "valor_c": somas["saldo_total"], "natureza": "derivado",
                        "fonte": fontes.ELOTECH["rotulo"], "regra": "S1 v1"},
                "rreo": {"rotulo": "Coluna L do RREO Anexo VII (saldo de RP)", "valor_c": x["rreo_c"],
                         "natureza": "publicado", "fonte": fontes.RREO["rotulo"], "pdf": x["pdf"], "extracao": x["extracao"]},
                "diferenca_c": dif, "diferenca_natureza": "diferenca", "situacao_da_diferenca": situacao,
                "situacao_do_dado": ({"codigo": "divergente", "texto": SITUACOES_DO_DADO["divergente"]} if dif else
                                     {"codigo": "com_dados", "texto": "dado existente, igual ao RREO"}),
                "explicacoes": [{k: e[k] for k in explicacoes.CAMPOS_SAIDA} for e in achadas],
                "nota": ("Fonte primária: API Elotech. Fonte de reconciliação: RREO Anexo VII. A diferença é mostrada; "
                         "o saldo da API nunca é trocado pelo valor do RREO.")}

    @staticmethod
    def _situacao_do_ponto(r, entidade):
        """Situacao de um ponto (contrato secao 2.2) a partir do resultado de `indicadores`."""
        if entidade is not None:
            return r["entidades"][0]["situacao_do_dado"]["codigo"]
        if not r["disponivel"]:
            return "municipio_indisponivel"
        somadas = [e for e in r["entidades"] if e["entra_no_total"]]
        return "sem_rp" if all(e["situacao_do_dado"]["codigo"] == "sem_rp" for e in somadas) else "com_dados"

    def evolucao(self, exercicio, entidade=None, em=None):
        """Serie dos cortes do exercicio (Subetapa 05.2; contrato M-01 e M-02).
        * Universo: TODOS os cortes processados do exercicio, de qualquer entidade, para qualquer escopo. Corte sem
          dado para o escopo aparece com a situacao (R1), nunca omitido e nunca com valor zero.
        * Cada ponto: situacao, valores dos indicadores (None sem valor), retrato, rotulos (R4) e proveniencia.
        * Diferenca para o ponto adjacente anterior: posterior - anterior, so quando os dois tem valor (nunca pula
          lacuna); natureza 'diferenca', com a proveniencia dos dois lados."""
        ctx, em = self.contexto(), instante(em)
        di = f"{exercicio}-01-01"
        universo = sorted({df for (e, ex, d0, df) in self._vigentes(ctx, em) if ex == exercicio and d0 == di})
        serie, anterior = [], None
        for df in universo:
            r = self.indicadores(exercicio, df, entidade, em)
            codigo = self._situacao_do_ponto(r, entidade)
            tem_valor = codigo in TEM_VALOR
            posterior_a_coleta = tem_valor and bool(r["retrato"] and r["retrato"]["corte_posterior_a_coleta"])
            ponto = {"data_final": df, "disponivel": r["disponivel"], "motivo_indisponivel": r["motivo_indisponivel"],
                     "situacao": {"codigo": codigo, "texto": SITUACOES_DO_PONTO[codigo]}, "tem_valor": tem_valor,
                     "retrato": r["retrato"], "rotulos": [ROTULO_POSTERIOR_A_COLETA] if posterior_a_coleta else [],
                     "entidades": [{"entidade": e["entidade"], "situacao": e["situacao_do_dado"]["codigo"],
                                    "entra_no_total": e["entra_no_total"]} for e in r["entidades"]],
                     "valores": {k: {x: v[x] for x in ("rotulo", "valor_c", "natureza", "proveniencia")}
                                 for k, v in r["valores"].items()}}
            ponto["diferenca_para_o_anterior"] = None if anterior is None else self._diferenca_de_pontos(anterior, ponto)
            serie.append(ponto)
            anterior = ponto
        par = regras.parametros(self.con, "PAR-24", 1)
        envolve_pares = entidade is None or entidade in (par["entidade_copia"], par["entidade_original"])
        pares = self.con.execute(          # copias 24xxxxx distintas com par em algum corte do exercicio
            "SELECT COUNT(DISTINCT anoempenho_a || '/' || empenho_a) FROM espelhamento_par WHERE derivacao_id=? AND "
            "exercicio=?", (ctx["derivacao"]["id"], exercicio)).fetchone()[0] if envolve_pares else 0
        return {"exercicio": exercicio, "entidade": entidade, "como_estava_em": em, "fonte": fontes.ELOTECH["rotulo"],
                "indicadores_da_serie": list(INDICADORES_DA_SERIE), "serie": serie,
                "pares_espelhados_no_exercicio": pares,
                "nota": ("Cada corte é o estado atual da base para aquele corte, na data da coleta. Pagamentos, "
                         "liquidações e cancelamentos são acumulados de 01/01 até o corte; a diferença entre cortes "
                         "vizinhos é o movimento do intervalo, se os dois cortes refletem a mesma base.")}

    @staticmethod
    def _diferenca_de_pontos(anterior, ponto):
        """Diferenca entre pontos adjacentes (contrato secao 2.6): valores None quando algum lado nao tem valor."""
        motivo = None
        if not (anterior["tem_valor"] and ponto["tem_valor"]):
            lacuna = anterior if not anterior["tem_valor"] else ponto
            motivo = (f"sem diferença: o corte {_data_br(lacuna['data_final'])} não tem valor "
                      f"({lacuna['situacao']['texto']})")
        return {"anterior": anterior["data_final"], "natureza": "diferenca", "sinal": "posterior − anterior",
                "motivo_indisponivel": motivo,
                "valores": {k: diferenca(anterior["valores"][k]["valor_c"], ponto["valores"][k]["valor_c"])
                            for k in ponto["valores"]},
                "proveniencia": {"anterior": anterior["valores"]["saldo_total"]["proveniencia"],
                                 "posterior": ponto["valores"]["saldo_total"]["proveniencia"]}}

    def _sem_cobertura(self, exercicio, em):
        """Contrato secao 2.1: nenhuma coleta de listagem do exercicio (de qualquer entidade e situacao) ate `em`."""
        filtro, p = (" AND coletada_em <= ?", (em,)) if em else ("", ())
        return not self.con.execute("SELECT 1 FROM coleta WHERE tipo='rp_listagem' AND tipo_pesquisa IS NULL AND "
                                    "exercicio=? AND data_inicial=?" + filtro + " LIMIT 1",
                                    (exercicio, f"{exercicio}-01-01", *p)).fetchone()

    def _corte_representativo(self, ctx, vig, cat, exercicio, em):
        di, fim = f"{exercicio}-01-01", f"{exercicio}-12-31"
        cortes = sorted({df for (e, ex, d0, df) in vig if ex == exercicio and d0 == di})
        base = {"exercicio": exercicio, "data_final": None, "aberto": None, "motivo": None}
        if not cortes:
            return {**base, "motivo": ("exercício sem cobertura" if self._sem_cobertura(exercicio, em)
                                       else "nenhum corte processado do exercício")}
        disponiveis = [df for df in cortes if self._corte(ctx, exercicio, df, None, em, vig, cat)["disponivel"]]
        if fim in disponiveis:
            return {**base, "data_final": fim, "aberto": False}
        if disponiveis:
            return {**base, "data_final": disponiveis[-1], "aberto": True}
        return {**base, "motivo": "Município indisponível em todos os cortes do exercício"}

    def corte_representativo(self, exercicio, em=None):
        """Corte que representa o exercicio na serie entre exercicios (contrato secao 2.5; R8): 31/12 se o Municipio
        estiver disponivel nele; senao o ultimo corte com o Municipio disponivel ('exercicio em aberto'); senao nenhum
        (lacuna para todos os escopos). O mesmo corte vale para todo escopo."""
        ctx, em = self.contexto(), instante(em)
        return self._corte_representativo(ctx, self._vigentes(ctx, em), self._catalogo(ctx, em), exercicio, em)

    def serie_entre_exercicios(self, entidade=None, em=None):
        """Serie por exercicio (Subetapa 05.3; contrato M-03 e M-04).
        * Universo: todos os exercicios entre o primeiro e o ultimo com coleta de listagem; exercicio sem nenhuma
          coleta aparece como 'exercicio_sem_cobertura'.
        * Cada exercicio no corte representativo (R8), o mesmo para todos os escopos; valores None sem dado.
        * Todo ponto com valor carrega o retrato 'Estado atual da base para o exercicio de A, corte ..., coletado em
          ...': o passado e o estado atual da base, nao o que se sabia na epoca.
        * Fechamento de A x abertura de A+1: (a)+(f)(A+1) - S1(A) pela FAIXA v1 (R2); no Municipio, so com as entidades
          exclusivas de um lado sem registros (R7); com a verificacao de continuidade da derivacao (ANOM-CONT v1)."""
        ctx, em = self.contexto(), instante(em)
        vig, cat = self._vigentes(ctx, em), self._catalogo(ctx, em)
        filtro, p = (" AND coletada_em <= ?", (em,)) if em else ("", ())
        anos = [ex for (ex,) in self.con.execute(
            "SELECT DISTINCT exercicio FROM coleta WHERE tipo='rp_listagem' AND tipo_pesquisa IS NULL AND "
            "data_inicial = exercicio || '-01-01'" + filtro, p)]
        pontos = []
        for ex in (range(min(anos), max(anos) + 1) if anos else []):
            pontos.append(self._ponto_do_exercicio(ctx, vig, cat, ex, entidade, em))
        fechamentos = [self._fechamento_abertura(ctx, vig, cat, a, b, entidade, em) for a, b in zip(pontos, pontos[1:])]
        par = regras.parametros(self.con, "PAR-24", 1)
        pares = {}
        if entidade is None or entidade in (par["entidade_copia"], par["entidade_original"]):
            pares = dict(self.con.execute(
                "SELECT exercicio, COUNT(DISTINCT anoempenho_a || '/' || empenho_a) FROM espelhamento_par "
                "WHERE derivacao_id=? GROUP BY exercicio", (ctx["derivacao"]["id"],)).fetchall())
        return {"entidade": entidade, "como_estava_em": em, "fonte": fontes.ELOTECH["rotulo"],
                "indicadores": list(INDICADORES_ENTRE_EXERCICIOS), "exercicios": pontos,
                "fechamento_abertura": fechamentos, "pares_espelhados_por_exercicio": pares,
                "nota": fontes.METODOLOGIA["importante"]}

    def _ponto_do_exercicio(self, ctx, vig, cat, ex, entidade, em):
        rep = self._corte_representativo(ctx, vig, cat, ex, em)
        # mesmo formato da serie no exercicio (05.2): todo indicador presente, com valor_c None quando nao ha valor
        ponto = {"exercicio": ex, "data_final": rep["data_final"], "aberto": rep["aberto"], "retrato": None,
                 "rotulos": [], "entidades": [], "tem_valor": False,
                 "valores": {i["id"]: {"rotulo": i["rotulo"], "valor_c": None, "natureza": "derivado",
                                       "proveniencia": None} for i in SOMAS}}
        if self._sem_cobertura(ex, em):
            codigo, motivo = "exercicio_sem_cobertura", SITUACOES_DO_PONTO["exercicio_sem_cobertura"]
        elif rep["data_final"] is None:
            codigo, motivo = "municipio_indisponivel", rep["motivo"]
        else:
            r = self.indicadores(ex, rep["data_final"], entidade, em)
            codigo, motivo = self._situacao_do_ponto(r, entidade), r["motivo_indisponivel"]
            ponto.update(retrato=r["retrato"],
                         entidades=[{"entidade": e["entidade"], "situacao": e["situacao_do_dado"]["codigo"],
                                     "entra_no_total": e["entra_no_total"]} for e in r["entidades"]],
                         valores={k: {x: v[x] for x in ("rotulo", "valor_c", "natureza", "proveniencia")}
                                  for k, v in r["valores"].items()})
        ponto.update(situacao={"codigo": codigo, "texto": SITUACOES_DO_PONTO[codigo]}, tem_valor=codigo in TEM_VALOR,
                     motivo_indisponivel=None if codigo in TEM_VALOR else motivo)
        if ponto["tem_valor"]:
            ponto["rotulos"] = ([ROTULO_EXERCICIO_EM_ABERTO] if rep["aberto"] else []) + (
                [ROTULO_POSTERIOR_A_COLETA] if ponto["retrato"]["corte_posterior_a_coleta"] else [])
        return ponto

    def _fechamento_abertura(self, ctx, vig, cat, a, b, entidade, em):
        """Contrato M-04: (a)+(f)(A+1) - S1(A), cada um no corte representativo; R7 no Municipio."""
        item = {"de": a["exercicio"], "para": b["exercicio"], "natureza": "diferenca",
                "sinal": "(a)+(f) da abertura de A+1 − S1 do fechamento de A", "regras": ["S1 v1", "FAIXA v1"],
                "s1_de_c": None, "a_mais_f_para_c": None, "diferenca_c": None, "motivo_indisponivel": None,
                "entidades_que_entram": [], "entidades_que_saem": [], "proveniencia": None,
                "continuidade": self._continuidade(ctx, a["exercicio"], entidade,
                                                   {e["entidade"] for e in a["entidades"] + b["entidades"]})}
        if not (a["tem_valor"] and b["tem_valor"]):
            falta = a if not a["tem_valor"] else b
            item["motivo_indisponivel"] = f"exercício {falta['exercicio']} sem valor ({falta['situacao']['texto']})"
            return item
        if entidade is None:
            ea = {e["entidade"]: e["situacao"] for e in a["entidades"] if e["entra_no_total"]}
            eb = {e["entidade"]: e["situacao"] for e in b["entidades"] if e["entra_no_total"]}
            item["entidades_que_saem"], item["entidades_que_entram"] = sorted(set(ea) - set(eb)), sorted(set(eb) - set(ea))
            com_registros = ([e for e in item["entidades_que_saem"] if ea[e] != "sem_rp"]
                             + [e for e in item["entidades_que_entram"] if eb[e] != "sem_rp"])
            if com_registros:
                item["motivo_indisponivel"] = ("conjunto de entidades diferente nos dois exercícios, com registros na(s) "
                                               f"entidade(s) {sorted(com_registros)} (R7)")
                return item
        coletas_b = self._corte(ctx, b["exercicio"], b["data_final"], entidade, em, vig, cat)["somar"]
        _, af = self._s1_e_a_mais_f(ctx, coletas_b)
        s1 = a["valores"]["saldo_total"]["valor_c"]
        item.update(s1_de_c=s1, a_mais_f_para_c=af, diferenca_c=diferenca(s1, af),
                    proveniencia={"de": a["valores"]["saldo_total"]["proveniencia"],
                                  "para": {**b["valores"]["saldo_total"]["proveniencia"],
                                           "consulta": "Σ proc com faixa 'a' + Σ aproc com faixa 'f' (FAIXA v1)"}})
        return item

    def _continuidade(self, ctx, de, entidade, entidades):
        """Verificacao ANOM-CONT v1 gravada pela derivacao (regime 'derivacao'): uma linha por entidade e par de
        exercicios; aqui so se le e se soma no Municipio."""
        linhas = []
        for escopo_json, verificados, falhas in self.con.execute(
                "SELECT escopo_json, verificados, falhas FROM verificacao WHERE derivacao_id=? AND descricao=?",
                (ctx["derivacao"]["id"], CONTINUIDADE)):
            esc = json.loads(escopo_json)
            if esc["de"] == de and (esc["entidade"] == entidade if entidade is not None else esc["entidade"] in entidades):
                linhas.append({"entidade": esc["entidade"], "verificados": verificados, "falhas": falhas,
                               "snapshots": esc.get("snapshots")})
        linhas.sort(key=lambda x: x["entidade"])
        return {"regra": "ANOM-CONT v1", "descricao": CONTINUIDADE, "linhas": linhas,
                "verificados": sum(x["verificados"] for x in linhas), "falhas": sum(x["falhas"] for x in linhas),
                "nota": "a abertura usada pela derivação é o snapshot de A+1 de maior data final"}

    def por_dimensao(self, dimensao, exercicio, data_final, entidade=None, em=None):
        """Totais por fonte de recurso, programacao orcamentaria, orgao, categoria etc. (lista fechada de dimensoes)."""
        if dimensao not in DIMENSOES:
            raise ErroDoPainel(f"dimensao precisa ser uma de {sorted(DIMENSOES)}")
        ctx, em = self.contexto(), instante(em)
        corte = self._corte(ctx, exercicio, data_final, entidade, em)
        regras_usadas = self._regras_publicaveis(REGRAS_DO_INDICADOR)
        if not corte["disponivel"]:
            return {"dimensao": dimensao, "disponivel": False, "motivo_indisponivel": corte["motivo"], "linhas": []}
        uids = self._uids(corte["somar"])
        regs = [r for r in regras_usadas if r["codigo"] in ("S1",) + (("CAT",) if dimensao == "categoria" else ())]
        nomes = [c.split(".")[1] for c in DIMENSOES[dimensao]]
        linhas = [{**dict(zip(nomes, g.pop("chave"))), **g, "natureza": "derivado",
                   "proveniencia": self._prov_curta(ctx, uids, f"somas agrupadas por {dimensao}", regs)}
                  for g in self._por_grupo(ctx, corte["somar"], DIMENSOES[dimensao])]
        return {"dimensao": dimensao, "disponivel": True, "retrato": corte["retrato"], "fonte": fontes.ELOTECH["rotulo"],
                "linhas": linhas, "proveniencia": self._proveniencia(ctx, corte["somar"], f"somas agrupadas por {dimensao}")}

    def _por_grupo(self, ctx, coletas, colunas):
        """Consulta unica de agrupamento (por_dimensao, categorias do indicador e composicao): registros e somas por
        valor de `colunas` (expressoes SQL fixas deste modulo), INCLUSIVE o grupo nulo, em ordem de S1 decrescente."""
        grupo = ", ".join(colunas)
        filtro, p = self._de_coletas(coletas)
        k = len(colunas)
        return [{"chave": row[:k], "registros": row[k], "inscricao_total_c": row[k + 1] or 0,
                 "pagamentos_c": row[k + 2] or 0, "liquidacoes_c": row[k + 3] or 0, "cancelamentos_c": row[k + 4] or 0,
                 "saldo_total_c": row[k + 5] or 0}
                for row in self.con.execute(
                    f"SELECT {grupo}, COUNT(*), SUM(r.proc_c + r.aproc_c), SUM({EXPR_PAGAMENTOS}), "
                    f"SUM(r.liquidado_c), SUM({EXPR_CANCELAMENTOS}), SUM(d.s1_saldo_total_c) "
                    f"FROM rp_registro r JOIN rp_derivado d ON d.derivacao_id=? AND d.resposta_id=r.resposta_id "
                    f"AND d.indice=r.indice WHERE r.normalizacao_id=? AND {filtro} GROUP BY {grupo} "
                    f"ORDER BY SUM(d.s1_saldo_total_c) DESC, {grupo}",
                    (ctx["derivacao"]["id"], ctx["normalizacao"]["id"], *p))]

    def _por_faixa(self, ctx, coletas):
        """Valor inscrito por faixa (FAIXA v1; R3): proc por faixa do processado e aproc por faixa do nao processado. Um
        registro com as duas partes entra em dois grupos, por isso so os VALORES fecham; a contagem e por parte."""
        filtro, p = self._de_coletas(coletas)
        saida = {}
        for coluna, valor in (("d.faixa_processado", "r.proc_c"), ("d.faixa_nao_processado", "r.aproc_c")):
            for faixa, n, v in self.con.execute(
                    f"SELECT {coluna}, COUNT(*), SUM({valor}) FROM rp_registro r JOIN rp_derivado d ON d.derivacao_id=? "
                    f"AND d.resposta_id=r.resposta_id AND d.indice=r.indice WHERE r.normalizacao_id=? AND {filtro} "
                    f"AND {coluna} IS NOT NULL GROUP BY {coluna}",
                    (ctx["derivacao"]["id"], ctx["normalizacao"]["id"], *p)):
                saida[faixa] = {"registros": n, "inscricao_total_c": v or 0}
        return saida

    def composicao(self, exercicio, data_final, entidade=None, em=None):
        """Composicao da inscricao e do saldo de um corte (Subetapa 05.4; contrato M-05 a M-08), por categoria, faixa,
        tipo de credor e dimensao orcamentaria.
        * Cada dimensao fecha SOZINHA com o total do corte, por medida (secao 4.2: soma dos grupos - total = 0, sem
          tolerancia nem ajuste). Dimensao que nao fecha nao e exibida: sai sem grupos, com o motivo e o fechamento.
        * Grupos fixos (categoria, faixa, tipo de credor) aparecem todos, com 0 quando nao tem registros (zero do
          grupo); nas dimensoes orcamentarias o grupo 'sem classificacao' (campo ausente na API) aparece sempre.
        * Faixa (R3): so o valor inscrito fecha; a contagem de registros por faixa e por parte e nao e somada.
        * Cada grupo traz o filtro da lista de empenhos cujo total e o proprio grupo.
        * Corte sem valor para o escopo: indisponivel, com a situacao (nunca grupos com zero)."""
        ctx, em = self.contexto(), instante(em)
        corte = self._corte(ctx, exercicio, data_final, entidade, em)
        codigo = self._situacao_do_ponto(corte, entidade)
        saida = {"consulta": {"exercicio": exercicio, "data_final": data_final, "entidade": entidade, "como_estava_em": em},
                 "escopo": f"entidade {entidade}" if entidade is not None else "Município (entidades do catálogo oficial do exercício)",
                 "situacao": {"codigo": codigo, "texto": SITUACOES_DO_PONTO[codigo]}, "disponivel": codigo in TEM_VALOR,
                 "motivo_indisponivel": None if codigo in TEM_VALOR else corte["motivo"], "retrato": corte["retrato"],
                 "fonte": fontes.ELOTECH["rotulo"], "total": None, "dimensoes": {},
                 "pares_espelhados_no_corte": 0, "proveniencia": None, "nota": fontes.METODOLOGIA["importante"]}
        if codigo not in TEM_VALOR:
            return saida
        regras_usadas = self._regras_publicaveis(REGRAS_DO_INDICADOR | {("FAIXA", 1)})
        uids = self._uids(corte["somar"])
        s = self._somas(ctx, corte["somar"])
        total = {"registros": s["registros"], "inscricao_total_c": s["inscricao_total"], "saldo_total_c": s["saldo_total"]}
        saida.update(total=total, proveniencia=self._proveniencia(ctx, corte["somar"], "composição por dimensão sobre "
                                                                                      "rp_registro + rp_derivado"))
        for d in COMPOSICOES:
            saida["dimensoes"][d] = self._dimensao(ctx, corte["somar"], uids, regras_usadas, d, total, exercicio)
        saida["pares_espelhados_no_corte"] = self._pares_no_corte(ctx, exercicio, data_final, entidade)
        return saida

    def _pares_no_corte(self, ctx, exercicio, data_final, entidade):
        """Copias 24xxxxx distintas com par no corte (PAR-24 v1), quando o escopo envolve as entidades do par; senao 0."""
        par = regras.parametros(self.con, "PAR-24", 1)
        if entidade is not None and entidade not in (par["entidade_copia"], par["entidade_original"]):
            return 0
        return self.con.execute(
            "SELECT COUNT(DISTINCT anoempenho_a || '/' || empenho_a) FROM espelhamento_par WHERE derivacao_id=? AND "
            "exercicio=? AND data_inicial=? AND data_final=?",
            (ctx["derivacao"]["id"], exercicio, f"{exercicio}-01-01", data_final)).fetchone()[0]

    def _dimensao(self, ctx, coletas, uids, regras_usadas, d, total, exercicio):
        """Grupos e fechamento de UMA dimensao da composicao (ver `composicao`)."""
        codigos = {"categoria": ("S1", "CAT"), "faixa": ("FAIXA",)}.get(d, ("S1",))
        regs = [r for r in regras_usadas if r["codigo"] in codigos]
        medidas = ("inscricao_total_c",) if d == "faixa" else MEDIDAS_DA_COMPOSICAO
        por = {"categoria": "categoria (CAT v1)", "tipo_credor": "tipo de credor",
               "fonte_recurso": "fonte de recurso (código e descrição)", "orgao": "órgão", "funcao": "função",
               "programa": "programa", "elemento": "elemento de despesa"}
        consulta = (f"{TEXTO_FAIXA}: soma de proc por faixa do processado e de aproc por faixa do não processado"
                    if d == "faixa" else f"registros, soma de proc + aproc e soma de S1 por {por.get(d)}")
        grupos = []
        if d == "faixa":
            achadas = self._por_faixa(ctx, coletas)
            anterior = exercicio - 1
            textos = {"a": ("processada", f"empenhos de anos anteriores a {anterior}", "inscricao_processada"),
                      "b": ("processada", f"empenhos de {anterior}", "inscricao_processada"),
                      "f": ("não processada", f"empenhos de anos anteriores a {anterior}", "inscricao_nao_processada"),
                      "g": ("não processada", f"empenhos de {anterior}", "inscricao_nao_processada")}
            for f in list(FAIXAS) + sorted(set(achadas) - set(FAIXAS)):
                parte, origem, na_lista = textos.get(f, ("?", "valor de faixa não previsto pela regra", None))
                v = achadas.get(f, {"registros": 0, "inscricao_total_c": 0})
                grupos.append({"ident": f, "chave": f, "rotulo": f"faixa {f} — parte {parte} de {origem}", "parte": parte,
                               "registros": v["registros"], "inscricao_total_c": v["inscricao_total_c"],
                               "filtro": {"faixa": f} if f in FAIXAS else None, "total_na_lista": na_lista})
        else:
            colunas = {"categoria": ["d.categoria"], "tipo_credor": ["tipo_credor(r.cnpj)"]}.get(d, DIMENSOES.get(d))
            achados = {g["chave"]: g for g in self._por_grupo(ctx, coletas, colunas)}
            fixos = {"categoria": CATEGORIAS, "tipo_credor": publico.TIPOS_CREDOR}.get(d)
            if fixos:
                chaves = [(k,) for k in fixos] + [k for k in achados if k[0] not in fixos]
            else:
                nulo = (None,) * len(colunas)
                chaves = [k for k in achados if k != nulo] + [nulo]
            descricoes = {}
            for k in chaves:
                if d == "fonte_recurso" and k[0] is not None:
                    descricoes.setdefault(k[0], set()).add(k[1])
            for i, k in enumerate(chaves):
                g = achados.get(k, {"registros": 0, "inscricao_total_c": 0, "saldo_total_c": 0})
                grupos.append({**self._rotulo_do_grupo(d, k, i, descricoes), "registros": g["registros"],
                               "inscricao_total_c": g["inscricao_total_c"], "saldo_total_c": g["saldo_total_c"]})
        for g in grupos:
            g.update(natureza="derivado", proveniencia=self._prov_curta(ctx, uids, consulta, regs))
        fech = {m: fechamento(total[m], [g[m] for g in grupos]) for m in medidas}
        abertas = [m for m in medidas if not fech[m]["fecha"]]
        motivo = None
        if abertas:
            motivo = ("a soma dos grupos não fecha com o total do corte ("
                      + "; ".join(f"{m}: diferença {fech[m]['diferenca']}" for m in abertas)
                      + "): a dimensão não é exibida até a causa ser explicada")
        return {"dimensao": d, "rotulo": ROTULO_COMPOSICAO[d], "medidas": list(medidas), "regras": regs,
                "consulta": consulta, "fechamento": fech, "fecha": not abertas, "exibida": not abertas,
                "motivo_nao_exibida": motivo, "grupos": [] if abertas else grupos,
                "contagem_aditiva": d != "faixa"}

    @staticmethod
    def _rotulo_do_grupo(d, k, i, descricoes):
        """Identificador, rotulo e filtro da lista de empenhos de um grupo (ver `composicao`). Grupo sem filtro exato
        (valor nao previsto, codigo com mais de uma descricao) sai com filtro None e o motivo, nunca com lista errada."""
        v = k[0]
        if d in DIMENSOES_ORCAMENTARIAS and all(x is None for x in k):
            return {"ident": "sem", "chave": None, "rotulo": SEM_CLASSIFICACAO, "filtro": {"sem_classificacao": d}}
        if d == "categoria":
            return {"ident": str(v), "chave": v, "rotulo": ROTULO_CATEGORIA.get(v, f"valor não previsto: {v}"),
                    "filtro": {"categoria": v} if v in CATEGORIAS else None}
        if d == "tipo_credor":
            ident = {"pessoa jurídica": "pj", "pessoa física": "pf", "não identificado": "ni"}.get(v, f"tipo{i}")
            return {"ident": ident, "chave": v, "rotulo": v,
                    "filtro": {"tipo_credor": v} if v in publico.TIPOS_CREDOR else None}
        if d == "fonte_recurso":
            item = {"ident": str(v), "chave": {"fonte_recurso": v, "descricao_fonte": k[1]},
                    "rotulo": k[1] or f"fonte {v}", "filtro": {"fonte_recurso": v}}
            if v is None:
                item.update(ident="sem-codigo", filtro=None, motivo_sem_lista="registro sem o código da fonte")
            elif len(descricoes.get(v, ())) > 1:
                item.update(filtro=None, motivo_sem_lista=f"o código {v} aparece com mais de uma descrição neste "
                                                          "corte; a lista por código juntaria esses grupos")
            return item
        nome = {"orgao": "órgão", "funcao": "função", "programa": "programa", "elemento": "elemento"}[d]
        return {"ident": str(v), "chave": v, "rotulo": f"{nome} {v}", "filtro": {d: v}}

    # ------------------------------------------------------------------ investigacao de variacoes (05.5)
    def _universo_do_exercicio(self, vig, exercicio):
        """Cortes processados do exercicio, de qualquer entidade (contrato secao 2.4)."""
        di = f"{exercicio}-01-01"
        return sorted({df for (e, ex, d0, df) in vig if ex == exercicio and d0 == di})

    def _valores_por_chave(self, ctx, coletas, expr):
        """{(entidade, anoempenho, empenho): [ocorrencias]} com o valor de `expr` (expressao fixa deste modulo) e a
        origem de cada registro (snapshot, resposta HTTP, posicao no content[] e SHA-256 do objeto bruto)."""
        filtro, p = self._de_coletas(coletas)
        mapa = {}
        for e, ano, emp, v, uid, ordem, sha, indice, rid in self.con.execute(
                f"SELECT r.entidade, r.anoempenho, r.empenho, {expr}, c.snapshot_uid, rb.ordem, rb.sha256, r.indice, "
                f"r.resposta_id FROM rp_registro r JOIN rp_derivado d ON d.derivacao_id=? AND d.resposta_id=r.resposta_id "
                f"AND d.indice=r.indice JOIN coleta c ON c.id=r.coleta_id JOIN resposta_bruta rb ON rb.id=r.resposta_id "
                f"WHERE r.normalizacao_id=? AND {filtro}", (ctx["derivacao"]["id"], ctx["normalizacao"]["id"], *p)):
            mapa.setdefault((e, ano, emp), []).append(
                {"valor_c": v, "proveniencia": {"snapshot_uid": uid, "resposta_ordem": ordem, "indice_no_content": indice,
                                                "objeto_bruto_sha256": sha, "resposta_id": rid}})
        return mapa

    def variacao(self, exercicio, anterior, posterior, entidade=None, metrica="s1", em=None, limite=50, deslocamento=0,
                 top=TOP_DA_VARIACAO):
        """Variacao de uma metrica entre dois cortes do MESMO exercicio, explicada pelas contribuicoes de cada empenho
        (Subetapa 05.5; contrato M-09 a M-11).
        * Par escolhido explicitamente (anterior < posterior), adjacente ou nao. Fica indisponivel, com o motivo, se
          um lado nao tem valor no escopo; no Municipio, se o conjunto de entidades somadas difere (R6); se a mesma
          chave (entidade, anoempenho, empenho) aparece mais de uma vez num lado (lista das chaves; nada e escolhido).
        * Variacao total = indicador homologado do posterior - do anterior. Contribuicao por chave, sempre posterior -
          anterior: nos dois cortes = post - ant; so no posterior = post; so no anterior = 0 - ant.
        * Fechamento ao centavo (secao 4.2) da lista, dos grupos do resumo e das classes; se falhar, o par e
          bloqueado (criterio de parada da 05.5), nunca exibido com resto.
        * Lista completa (chaves com contribuicao != 0) em ordem de contribuicao decrescente, desempate pela chave;
          paginada, com subtotal da pagina e acumulado ate ela."""
        if metrica not in METRICAS_DA_VARIACAO:
            raise ErroDoPainel(f"metrica precisa ser uma de {sorted(METRICAS_DA_VARIACAO)}")
        if isinstance(top, bool) or not isinstance(top, int) or top < 1:
            raise ErroDoPainel("top precisa ser um inteiro positivo")
        if not (isinstance(anterior, str) and isinstance(posterior, str) and anterior < posterior):
            raise ErroDoPainel("o corte anterior precisa ser anterior ao corte posterior")
        limite, deslocamento = max(1, min(int(limite), LIMITE_LISTA)), max(0, int(deslocamento))
        m = METRICAS_DA_VARIACAO[metrica]
        ctx, em = self.contexto(), instante(em)
        vig, cat = self._vigentes(ctx, em), self._catalogo(ctx, em)
        regs = self._regras_publicaveis(m["regras"])
        saida = {"consulta": {"exercicio": exercicio, "anterior": anterior, "posterior": posterior, "entidade": entidade,
                              "metrica": metrica, "como_estava_em": em},
                 "escopo": f"entidade {entidade}" if entidade is not None else "Município (entidades do catálogo oficial do exercício)",
                 "metrica": {"id": metrica, "rotulo": m["rotulo"], "formula": m["formula"],
                             "natureza_do_operando": m["natureza_do_operando"], "regras": regs},
                 "fonte": fontes.ELOTECH["rotulo"], "natureza": "diferenca", "sinal": "posterior − anterior",
                 "disponivel": False, "motivo_indisponivel": None, "chaves_repetidas": [], "anterior": None,
                 "posterior": None, "variacao_c": None, "resumo": None, "classes": None, "fechamentos": None,
                 "lista": None, "chaves": None, "pares_espelhados": None, "proveniencia": None, "nota": None}
        universo = self._universo_do_exercicio(vig, exercicio)
        faltam = [df for df in (anterior, posterior) if df not in universo]
        if faltam:
            saida["motivo_indisponivel"] = (f"corte sem processamento no exercício {exercicio}: "
                                            + ", ".join(_data_br(df) for df in faltam))
            return saida
        lados = {}
        for nome, df in (("anterior", anterior), ("posterior", posterior)):
            corte = self._corte(ctx, exercicio, df, entidade, em, vig, cat)
            codigo = self._situacao_do_ponto(corte, entidade)
            lados[nome] = {"data_final": df, "situacao": {"codigo": codigo, "texto": SITUACOES_DO_PONTO[codigo]},
                           "tem_valor": codigo in TEM_VALOR, "motivo_indisponivel": None if codigo in TEM_VALOR else corte["motivo"],
                           "retrato": corte["retrato"],
                           "snapshots": self._uids(corte["somar"]) if codigo in TEM_VALOR else [],
                           "entidades_no_total": sorted(e["entidade"] for e in corte["entidades"] if e["entra_no_total"]),
                           "total_c": None, "coletas": corte["somar"]}
            if lados[nome]["tem_valor"]:   # total do corte: o indicador homologado (exibido mesmo com o par indisponivel)
                lados[nome]["total_c"] = self._somas(ctx, corte["somar"])[m["indicador"]]
        publico_ = {nome: {k: v for k, v in l.items() if k != "coletas"} for nome, l in lados.items()}
        saida.update(anterior=publico_["anterior"], posterior=publico_["posterior"])
        sem_valor = [l for l in lados.values() if not l["tem_valor"]]
        if sem_valor:
            saida["motivo_indisponivel"] = "; ".join(
                f"o corte {_data_br(l['data_final'])} não tem valor para o escopo ({l['situacao']['texto']}"
                + (f": {l['motivo_indisponivel']}" if l["motivo_indisponivel"] else "") + ")" for l in sem_valor)
            return saida
        a, b = lados["anterior"]["entidades_no_total"], lados["posterior"]["entidades_no_total"]
        if entidade is None and a != b:
            saida["motivo_indisponivel"] = (f"conjunto de entidades diferente nos dois cortes (R6): só no anterior "
                                            f"{sorted(set(a) - set(b))}, só no posterior {sorted(set(b) - set(a))}")
            return saida
        mapas = {nome: self._valores_por_chave(ctx, l["coletas"], m["sql"]) for nome, l in lados.items()}
        repetidas = sorted({k for mp in mapas.values() for k, occ in mp.items() if len(occ) > 1})
        if repetidas:
            saida["chaves_repetidas"] = [{"chave": dict(zip(("entidade", "anoempenho", "empenho"), k)),
                                          "anterior": len(mapas["anterior"].get(k, ())),
                                          "posterior": len(mapas["posterior"].get(k, ()))} for k in repetidas]
            saida["motivo_indisponivel"] = (f"a mesma chave (entidade, ano, empenho) aparece mais de uma vez num dos "
                                            f"snapshots ({len(repetidas)} chave(s)); nenhuma ocorrência é escolhida")
            return saida
        variacao = diferenca(lados["anterior"]["total_c"], lados["posterior"]["total_c"])
        itens = []
        for k in set(mapas["anterior"]) | set(mapas["posterior"]):
            ant, post = mapas["anterior"].get(k, [None])[0], mapas["posterior"].get(k, [None])[0]
            if ant and post:
                classe, contrib = "nos_dois", diferenca(ant["valor_c"], post["valor_c"])
            elif post:
                classe, contrib = "so_posterior", post["valor_c"]
            else:
                classe, contrib = "so_anterior", 0 - ant["valor_c"]
            itens.append({"chave": {"entidade": k[0], "anoempenho": k[1], "empenho": k[2]}, "classe": classe,
                          "classe_texto": CLASSES_DA_CHAVE[classe], "anterior": ant, "posterior": post,
                          "contribuicao_c": contrib, "natureza": "diferenca", "_k": k})
        itens.sort(key=lambda x: (-x["contribuicao_c"], x["_k"]))
        aumentos = [x for x in itens if x["contribuicao_c"] > 0]
        reducoes = sorted((x for x in itens if x["contribuicao_c"] < 0), key=lambda x: (x["contribuicao_c"], x["_k"]))
        zeros = [x for x in itens if x["contribuicao_c"] == 0]
        lista = aumentos + [x for x in itens if x["contribuicao_c"] < 0]      # ordem do contrato: decrescente
        for i, x in enumerate(lista, 1):
            x["posicao"] = i
        for x in itens:
            del x["_k"]

        def soma(xs):
            return sum(x["contribuicao_c"] for x in xs)

        grupos = [{"id": "top_aumentos", "rotulo": f"maiores aumentos (até {top})", "quantidade": len(aumentos[:top]),
                   "soma_c": soma(aumentos[:top]), "itens": aumentos[:top]},
                  {"id": "outros_aumentos", "rotulo": "outros aumentos", "quantidade": len(aumentos[top:]),
                   "soma_c": soma(aumentos[top:])},
                  {"id": "top_reducoes", "rotulo": f"maiores reduções (até {top})", "quantidade": len(reducoes[:top]),
                   "soma_c": soma(reducoes[:top]), "itens": reducoes[:top]},
                  {"id": "outras_reducoes", "rotulo": "outras reduções", "quantidade": len(reducoes[top:]),
                   "soma_c": soma(reducoes[top:])},
                  {"id": "sem_variacao", "rotulo": "sem variação", "quantidade": len(zeros), "soma_c": 0}]
        classes = [{"id": c, "rotulo": CLASSES_DA_CHAVE[c], "quantidade": sum(1 for x in itens if x["classe"] == c),
                    "soma_c": soma(x for x in itens if x["classe"] == c)} for c in CLASSES_DA_CHAVE]
        fech = {"grupos": fechamento(variacao, [g["soma_c"] for g in grupos]),
                "classes": fechamento(variacao, [c["soma_c"] for c in classes]),
                "lista": fechamento(variacao, [x["contribuicao_c"] for x in lista])}
        saida["fechamentos"] = fech
        if not all(f["fecha"] for f in fech.values()):
            saida["motivo_indisponivel"] = ("as contribuições não fecham com a variação total: o par não é exibido até a "
                                            "causa ser investigada (critério de parada da 05.5)")
            return saida
        pagina = lista[deslocamento:deslocamento + limite]
        saida.update(
            disponivel=True, variacao_c=variacao,
            resumo={"top": top, "grupos": grupos}, classes=classes,
            lista={"itens": pagina, "total_de_chaves": len(lista), "limite": limite, "deslocamento": deslocamento,
                   "subtotal_c": soma(pagina), "acumulado_c": soma(lista[:deslocamento + limite]),
                   "ultima_pagina": deslocamento + limite >= len(lista)},
            chaves={"total": len(itens), "com_variacao": len(lista), "sem_variacao": len(zeros)},
            pares_espelhados={nome: self._pares_no_corte(ctx, exercicio, l["data_final"], entidade)
                              for nome, l in lados.items()},
            proveniencia={nome: self._proveniencia(ctx, l["coletas"], f"{m['formula']} por registro do corte "
                                                                     f"{_data_br(l['data_final'])}")
                          for nome, l in lados.items()},
            nota=("Variação = valor do corte posterior − valor do corte anterior, pela mesma soma do indicador homologado. "
                  "Cada corte é o estado atual da base para aquele corte, na data da coleta: se as duas coletas "
                  "refletem bases diferentes, a variação mistura o movimento do intervalo com mudança retroativa."))
        return saida

    def historico_empenho(self, entidade, anoempenho, empenho, exercicio, em=None):
        """Um empenho em cada corte do exercicio (Subetapa 05.5; contrato M-12): os valores do registro em cada corte
        do universo (secao 2.4), sem formula nova. Corte sem valor para a entidade aparece com a situacao; corte com
        valor em que a chave nao aparece, como 'empenho ausente deste corte'; chave repetida mostra todas as
        ocorrencias, sem escolher."""
        ctx, em = self.contexto(), instante(em)
        vig, cat = self._vigentes(ctx, em), self._catalogo(ctx, em)
        governo = self._naturezas_derivados()
        cortes = []
        for df in self._universo_do_exercicio(vig, exercicio):
            corte = self._corte(ctx, exercicio, df, entidade, em, vig, cat)
            codigo = self._situacao_do_ponto(corte, entidade)
            ponto = {"data_final": df, "situacao": {"codigo": codigo, "texto": SITUACOES_DO_PONTO[codigo]},
                     "tem_valor": codigo in TEM_VALOR, "motivo_indisponivel": None if codigo in TEM_VALOR else corte["motivo"],
                     "retrato": corte["retrato"], "rotulos": [], "presente": False, "motivo_ausencia": None,
                     "ocorrencias": []}
            if ponto["tem_valor"]:
                if corte["retrato"] and corte["retrato"]["corte_posterior_a_coleta"]:
                    ponto["rotulos"].append(ROTULO_POSTERIOR_A_COLETA)
                for reg, prov, _, _ in self._registros(ctx, corte["somar"], " AND r.anoempenho=? AND r.empenho=?",
                                                        (anoempenho, empenho), ordem="empenho"):
                    ponto["ocorrencias"].append({"valores": {c: reg[c] for c in CAMPOS_DO_HISTORICO},
                                                 "categoria": reg["categoria"], "proveniencia": prov})
                ponto["presente"] = bool(ponto["ocorrencias"])
                ponto["motivo_ausencia"] = None if ponto["presente"] else "empenho ausente deste corte"
            cortes.append(ponto)
        campos = [{"coluna": c, "rotulo": fontes.CAMPOS[c][1] if c in fontes.CAMPOS else fontes.DERIVADOS[c][0],
                   "campo_api": fontes.CAMPOS[c][0] if c in fontes.CAMPOS else None,
                   "natureza": "da_fonte" if c in fontes.CAMPOS else governo[c]} for c in CAMPOS_DO_HISTORICO]
        repetida = any(len(x["ocorrencias"]) > 1 for x in cortes)
        return {"chave": {"entidade": entidade, "anoempenho": anoempenho, "empenho": empenho}, "exercicio": exercicio,
                "como_estava_em": em, "fonte": fontes.ELOTECH["rotulo"], "campos": campos, "cortes": cortes,
                "derivacao": {"id": ctx["derivacao"]["id"], "hash_resultado": ctx["derivacao"]["hash_resultado"]},
                "normalizacao_id": ctx["normalizacao"]["id"],
                "nota": ("Mais de uma ocorrência num corte = a mesma chave apareceu mais de uma vez no snapshot; nenhuma é "
                         "descartada.") if repetida else None}

    # ------------------------------------------------------------------ qualidade dos dados (05.6)
    def qualidade(self):
        """Anomalias, verificacoes e situacao das diferencas com o RREO (Subetapa 05.6; contrato secao 6), cada uma
        segundo a sua natureza e lidas da derivacao atual, sem nenhuma regra nova.
        * Anomalias: uma linha por ocorrencia, em TODO snapshot processado (inclusive retratos anteriores e coletas
          por tipo de pesquisa); por tipo, a contagem da derivacao e quantas estao em snapshots vigentes.
        * Verificacoes: de conjunto; a situacao e interpretada pela descricao (R5); nunca viram lista de empenhos.
        * Diferencas com o RREO: as cinco situacoes separadas, contadas por coluna x documento x regra de agregacao
          (as mesmas linhas da reconciliacao); 'sem diferenca' nunca e contada como explicada."""
        ctx = self.contexto()
        did = ctx["derivacao"]["id"]
        governo = governanca.situacao_atual(self.con)
        vig = sorted(set(self._vigentes(ctx, None).values()))
        tipos = {c: {"descricao": d, "status_evidencia": s, "fonte": f} for c, d, s, f in self.con.execute(
            "SELECT codigo, descricao, status_evidencia, fonte FROM anomalia_tipo ORDER BY codigo")}
        por_tipo = []
        for tipo, cod, ver, n, coletas, com_chave, vigentes, anos in self.con.execute(
                "SELECT a.tipo, g.codigo, g.versao, COUNT(*), COUNT(DISTINCT a.coleta_id), SUM(a.entidade IS NOT NULL AND "
                f"a.anoempenho IS NOT NULL AND a.empenho IS NOT NULL), SUM(a.coleta_id IN ({_in(len(vig))})), "
                "GROUP_CONCAT(DISTINCT c.exercicio) FROM anomalia a JOIN regra g ON g.id = a.regra_id LEFT JOIN coleta c "
                "ON c.id = a.coleta_id WHERE a.derivacao_id=? GROUP BY a.tipo, g.codigo, g.versao "
                "ORDER BY a.tipo, g.codigo, g.versao", (*vig, did)):
            t = tipos.get(tipo, {"descricao": None, "status_evidencia": None, "fonte": None})
            por_tipo.append({"tipo": tipo, **t, "regra": f"{cod} v{ver}",
                             "situacao_da_regra": governo.get((cod, ver), {}).get("situacao"), "ocorrencias": n,
                             "em_snapshots_vigentes": vigentes or 0, "com_chave_de_empenho": com_chave or 0,
                             "snapshots": coletas, "exercicios": sorted(int(x) for x in (anos or "").split(",") if x)})
        presentes = {x["tipo"] for x in por_tipo}
        sem_ocorrencia = [{"tipo": c, **t} for c, t in tipos.items() if c not in presentes]
        return {"derivacao": ctx["derivacao"], "normalizacao": ctx["normalizacao"], "fonte": fontes.ELOTECH["rotulo"],
                "anomalias": {"por_tipo": por_tipo, "tipos_sem_ocorrencia": sem_ocorrencia,
                              "total": sum(x["ocorrencias"] for x in por_tipo)},
                "verificacoes": self._verificacoes(did, governo, por_tipo),
                "diferencas_rreo": self._situacao_das_diferencas(did),
                "nota": ("Anomalias e verificações são gravadas pela derivação (regras versionadas) e aqui só são lidas. "
                         "Anomalia não é erro: é um fato registrado, descrito pelo tipo. Verificação é de conjunto: o "
                         "significado de 'falhas' depende da verificação.")}

    def _verificacoes(self, did, governo, por_tipo):
        contagem = {x["tipo"]: x["ocorrencias"] for x in por_tipo}
        grupos = {}
        for cod, ver, descricao, escopo_json, verificados, falhas in self.con.execute(
                "SELECT g.codigo, g.versao, v.descricao, v.escopo_json, v.verificados, v.falhas FROM verificacao v JOIN "
                "regra g ON g.id = v.regra_id WHERE v.derivacao_id=? ORDER BY v.descricao, g.codigo, g.versao, v.rowid",
                (did,)):
            g = grupos.setdefault((descricao, cod, ver), {"descricao": descricao, "regra": f"{cod} v{ver}",
                                                          "situacao_da_regra": governo.get((cod, ver), {}).get("situacao"),
                                                          "itens": []})
            escopo = json.loads(escopo_json)
            snaps = escopo.get("snapshots") or ([escopo["rreo_snapshot"]] if "rreo_snapshot" in escopo else [])
            g["itens"].append({"escopo": escopo, "verificados": verificados, "falhas": falhas, "snapshots": snaps})
        saida = []
        for (descricao, cod, ver), g in grupos.items():
            cat = INTERPRETACOES_DE_VERIFICACAO.get(descricao)
            catalogada = cat is not None and cat["regra"] == (cod, ver)
            v, f = sum(i["verificados"] for i in g["itens"]), sum(i["falhas"] for i in g["itens"])
            natureza = cat["natureza"] if catalogada else None
            for i in g["itens"]:
                i["situacao"] = self._situacao_da_verificacao(natureza, i["verificados"], i["falhas"])
                i["anomalias_do_escopo"] = ([{"tipo": t, **self._escopo_das_anomalias(descricao, i["escopo"])}
                                             for t in cat["anomalias"]] if catalogada and i["falhas"] else [])
            g.update(verificados=v, falhas=f, catalogada=catalogada, natureza=natureza,
                     significado_de_verificados=cat["verificados"] if catalogada else None,
                     significado_de_falhas=cat["falhas"] if catalogada else NAO_CATALOGADA,
                     situacao=self._situacao_da_verificacao(natureza, v, f),
                     anomalias_ligadas=[{"tipo": t, "ocorrencias": contagem.get(t, 0)}
                                        for t in (cat["anomalias"] if catalogada else ())])
            saida.append(g)
        return saida

    def _escopo_das_anomalias(self, descricao, escopo):
        """Filtros da lista de anomalias que a mesma regra grava para o escopo de um item de verificacao: a
        continuidade grava no snapshot de abertura de A+1 da entidade; o pareamento, no snapshot da entidade-copia do
        corte (derivar._continuidade e _pareamento)."""
        if descricao == CONTINUIDADE:
            return {"exercicio": escopo["para"], "entidade": escopo["entidade"]}
        par = regras.parametros(self.con, "PAR-24", 1)
        return {"exercicio": escopo["exercicio"], "entidade": par["entidade_copia"], "data_final": escopo["data_final"]}

    @staticmethod
    def _situacao_da_verificacao(natureza, verificados, falhas):
        """Situacao exibida de uma verificacao (contrato E-02), pela natureza catalogada da descricao."""
        if natureza == "conformidade":
            return "sem falha" if falhas == 0 else "com falhas"
        if natureza == "colunas_com_diferenca":
            return f"colunas com diferença: {falhas} de {verificados}"
        if natureza == "pdfs_nao_lidos":
            return f"PDFs não lidos: {falhas}"
        return NAO_CATALOGADA

    def _situacao_das_diferencas(self, did):
        """Contrato E-03: as cinco situacoes, por regra de agregacao (linhas da reconciliacao: coluna x documento x
        regra) e na coerencia entre publicacoes; conferencia com a verificacao CONC-RREO, que conta por snapshot do PDF."""
        rec = self.reconciliacao()
        linhas = rec["linhas"]
        regras_ = sorted({x["regra_agregacao"]["regra"] for x in linhas})
        por_regra = {r: {s: sum(1 for x in linhas if x["regra_agregacao"]["regra"] == r and x["situacao_da_diferenca"] == s)
                         for s in SITUACOES_DAS_DIFERENCAS} for r in regras_}
        coe = self.coerencia_entre_publicacoes()["comparacoes"]
        coerencia = {nome: {s: sum(1 for x in lista if x["situacao_da_diferenca"] == s) for s in SITUACOES_DAS_DIFERENCAS}
                     for nome, lista in (("exibida", [x for x in coe if x["mais_recente"]]), ("todas", coe))}
        repetidos = sorted({u for x in linhas for u in x["pdf"]["mesmo_pdf_coletado_tambem_em"]})
        itens = [(json.loads(e), v, f) for e, v, f in self.con.execute(
            "SELECT escopo_json, verificados, falhas FROM verificacao WHERE derivacao_id=? AND descricao=?",
            (did, "conciliação RREO × API (colunas com diferença)"))]
        conf = {"verificacao": {"itens": len(itens), "colunas": sum(v for _, v, _ in itens),
                                "com_diferenca": sum(f for _, _, f in itens)},
                "pdfs_repetidos": {"snapshots": repetidos,
                                   "itens": sum(1 for e, _, _ in itens if e.get("rreo_snapshot") in repetidos),
                                   "colunas": sum(v for e, v, _ in itens if e.get("rreo_snapshot") in repetidos),
                                   "com_diferenca": sum(f for e, _, f in itens if e.get("rreo_snapshot") in repetidos)},
                "reconciliacao": {"colunas": len(linhas), "com_diferenca": sum(1 for x in linhas if x["diferenca_c"])}}
        conf["confere"] = (conf["verificacao"]["colunas"] - conf["pdfs_repetidos"]["colunas"] == conf["reconciliacao"]["colunas"]
                           and conf["verificacao"]["com_diferenca"] - conf["pdfs_repetidos"]["com_diferenca"]
                           == conf["reconciliacao"]["com_diferenca"])
        return {"situacoes": list(SITUACOES_DAS_DIFERENCAS), "por_regra": por_regra,
                "total_por_regra": {r: sum(v.values()) for r, v in por_regra.items()},
                "documentos": len({x["pdf"]["snapshot_uid"] for x in linhas}), "linhas": len(linhas),
                "coerencia": coerencia, "total_coerencia": {k: sum(v.values()) for k, v in coerencia.items()},
                "conferencia_com_a_verificacao": conf,
                "sem_diferenca_contada_como_explicada": sum(1 for x in linhas + coe if x["diferenca_c"] == 0
                                                             and x["situacao_da_diferenca"] != "sem diferença"),
                "nota": ("'Sem diferença' (diferença zero) não é explicação e nunca é somada às explicadas. A contagem é "
                         "por coluna do RREO, documento e regra de agregação (RREO-COL v1 e v2 separadas).")}

    def anomalias(self, tipo, limite=50, deslocamento=0, exercicio=None, entidade=None, data_final=None):
        """Ocorrencias de UM tipo de anomalia (contrato E-01) COM chave de empenho, paginadas, com o snapshot de cada
        uma; as sem chave completa ficam so no agregado (`sem_chave` conta as do filtro). Filtros opcionais de escopo
        (exercicio, entidade, corte) servem a ligacao vinda de uma verificacao. A ligacao ao registro (drill-down) e
        exata so quando o snapshot da ocorrencia e o vigente do corte (o detalhe do empenho mostra o retrato
        vigente); ocorrencia em retrato anterior leva aos retratos do corte; em coleta que nao e corte do painel
        (tipo de pesquisa, data inicial fora de 01/01), nao tem ligacao."""
        ctx = self.contexto()
        did = ctx["derivacao"]["id"]
        if not self.con.execute("SELECT 1 FROM anomalia_tipo WHERE codigo=?", (tipo,)).fetchone():
            raise ErroDoPainel(f"tipo de anomalia desconhecido: {tipo!r}")
        for nome, valor in (("exercicio", exercicio), ("entidade", entidade)):
            if valor is not None and (isinstance(valor, bool) or not isinstance(valor, int)):
                raise ErroDoPainel(f"{nome} precisa ser inteiro")
        limite, deslocamento = max(1, min(int(limite), LIMITE_LISTA)), max(0, int(deslocamento))
        vig = set(self._vigentes(ctx, None).values())
        filtro, p = "", []
        for coluna, valor in (("c.exercicio", exercicio), ("a.entidade", entidade), ("c.data_final", data_final)):
            if valor is not None:
                filtro, p = filtro + f" AND {coluna} = ?", p + [valor]
        com_chave = " AND a.entidade IS NOT NULL AND a.anoempenho IS NOT NULL AND a.empenho IS NOT NULL"
        base = "FROM anomalia a LEFT JOIN coleta c ON c.id = a.coleta_id WHERE a.derivacao_id=? AND a.tipo=?" + filtro
        total = self.con.execute(f"SELECT COUNT(*) {base}{com_chave}", (did, tipo, *p)).fetchone()[0]
        sem_chave = self.con.execute(f"SELECT COUNT(*) {base} AND NOT (a.entidade IS NOT NULL AND a.anoempenho IS NOT "
                                     "NULL AND a.empenho IS NOT NULL)", (did, tipo, *p)).fetchone()[0]
        itens = []
        for cid, uid, ex, di, df, tp, quando, e, ano, emp, det, cod, ver in self.con.execute(
                "SELECT a.coleta_id, c.snapshot_uid, c.exercicio, c.data_inicial, c.data_final, c.tipo_pesquisa, "
                "c.coletada_em, a.entidade, a.anoempenho, a.empenho, a.detalhe_json, g.codigo, g.versao FROM anomalia a "
                "JOIN regra g ON g.id = a.regra_id LEFT JOIN coleta c ON c.id = a.coleta_id WHERE a.derivacao_id=? AND "
                "a.tipo=?" + filtro + com_chave + " ORDER BY c.exercicio, c.data_final, a.entidade, a.anoempenho, "
                "a.empenho, c.coletada_em, c.snapshot_uid, a.rowid LIMIT ? OFFSET ?", (did, tipo, *p, limite, deslocamento)):
            chave = {"entidade": e, "anoempenho": ano, "empenho": emp}
            corte = cid is not None and tp is None and di == f"{ex}-01-01"
            if not corte:
                retrato = "coleta por tipo de pesquisa ou fora de 01/01 (não é corte do painel)" if cid else "sem snapshot"
            else:
                retrato = "vigente" if cid in vig else "retrato anterior do corte"
            ligacao = {"destino": "empenho" if cid in vig else "retratos", "exercicio": ex, "data_final": df} if corte else None
            itens.append({"snapshot": uid, "exercicio": ex, "data_inicial": di, "data_final": df, "coletada_em": quando,
                          "retrato": retrato, "vigente": cid in vig, "chave": chave,
                          "detalhe": json.loads(det) if det else None, "regra": f"{cod} v{ver}", "ligacao": ligacao})
        t = self.con.execute("SELECT descricao, status_evidencia, fonte FROM anomalia_tipo WHERE codigo=?", (tipo,)).fetchone()
        return {"tipo": tipo, "descricao": t[0], "status_evidencia": t[1], "fonte": t[2],
                "filtros": {k: v for k, v in (("exercicio", exercicio), ("entidade", entidade), ("data_final", data_final))
                            if v is not None},
                "total": total, "sem_chave": sem_chave, "limite": limite, "deslocamento": deslocamento, "itens": itens,
                "derivacao": ctx["derivacao"],
                "nota": ("Uma linha por ocorrência em cada snapshot processado: o mesmo empenho aparece uma vez por "
                         "retrato e por corte em que a condição vale. Ocorrência sem entidade, ano e número do empenho "
                         "fica só na contagem por tipo.")}

    # ------------------------------------------------------------------ registros
    def _registros(self, ctx, coletas, filtro_extra="", params=(), limite=None, deslocamento=0, ordem="saldo"):
        ordens = {"saldo": "d.s1_saldo_total_c DESC, r.entidade, r.anoempenho, r.empenho, r.resposta_id, r.indice",
                  "empenho": "r.entidade, r.anoempenho, r.empenho, r.resposta_id, r.indice"}
        if ordem not in ordens:
            raise ErroDoPainel(f"ordem precisa ser uma de {sorted(ordens)}")
        restritos = list(publico.CAMPOS_RESTRITOS) if self.nivel == "interno" else []
        filtro, p = self._de_coletas(coletas)
        colunas = ([f"r.{c}" for c in CAMPOS_REGISTRO + DINHEIRO] + [f"d.{c}" for c in DERIVADOS] +
                   [f"({EXPR_CANCELAMENTOS})"] +
                   ["r.cnpj", "r.nome", "r.resposta_id", "r.indice", "c.snapshot_uid", "rb.ordem", "rb.sha256", "rb.url"] +
                   [f"r.{c}" for c in restritos])
        sql = (f"SELECT {', '.join(colunas)} FROM rp_registro r "
               f"JOIN rp_derivado d ON d.derivacao_id=? AND d.resposta_id=r.resposta_id AND d.indice=r.indice "
               f"JOIN coleta c ON c.id=r.coleta_id JOIN resposta_bruta rb ON rb.id=r.resposta_id "
               f"WHERE r.normalizacao_id=? AND {filtro}{filtro_extra} ORDER BY {ordens[ordem]}")
        args = [ctx["derivacao"]["id"], ctx["normalizacao"]["id"], *p, *params]
        if limite is not None:
            sql += " LIMIT ? OFFSET ?"
            args += [limite, deslocamento]
        nomes = (CAMPOS_REGISTRO + DINHEIRO + DERIVADOS + ["cancelamentos_c"] +
                 ["_cnpj", "_nome", "_resposta_id", "_indice", "_snapshot_uid", "_ordem", "_sha256", "_url"] + restritos)
        for row in self.con.execute(sql, args):
            reg = dict(zip(nomes, row))
            prov = {"snapshot_uid": reg.pop("_snapshot_uid"), "resposta_ordem": reg.pop("_ordem"),
                    "resposta_url": reg.pop("_url"), "objeto_bruto_sha256": reg.pop("_sha256"),
                    "indice_no_content": reg.pop("_indice"), "resposta_id": reg.pop("_resposta_id"),
                    "normalizacao_id": ctx["normalizacao"]["id"], "derivacao_id": ctx["derivacao"]["id"]}
            cnpj, nome = reg.pop("_cnpj"), reg.pop("_nome")
            reg["tipo_credor"] = publico.tipo_credor(cnpj)
            yield reg, prov, nome, cnpj

    @staticmethod
    def _filtros_empenho(categoria=None, fonte_recurso=None, programatica=None, tipo_credor=None, cnpj=None,
                         anoempenho=None, empenho=None, faixa=None, orgao=None, funcao=None, programa=None,
                         elemento=None, sem_classificacao=None):
        """SQL (sempre parametrizado) dos filtros da listagem de empenhos. Filtro so escolhe registros; nunca muda valor.
        cnpj: so CNPJ completo (14 digitos) de pessoa juridica; CPF nunca e aceito como filtro.
        anoempenho / empenho: busca de um empenho pelo ano e/ou numero (igualdade exata).
        faixa (05.4): a/b escolhem pela faixa do processado, f/g pela do nao processado (FAIXA v1).
        orgao, funcao, programa, elemento (05.4): codigo exato como a API devolve (texto de digitos).
        sem_classificacao (05.4): registros sem o campo da dimensao orcamentaria indicada (valor nulo)."""
        sql, params, eco = "", [], {}
        for nome, valor in (("anoempenho", anoempenho), ("empenho", empenho)):
            if valor is not None:
                if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
                    raise ErroDoPainel(f"{nome} precisa ser um inteiro nao negativo")
                sql, eco[nome] = sql + f" AND r.{nome} = ?", valor
                params.append(valor)
        if categoria is not None:
            if categoria not in CATEGORIAS:
                raise ErroDoPainel(f"categoria precisa ser uma de {CATEGORIAS}")
            sql, eco["categoria"] = sql + " AND d.categoria = ?", categoria
            params.append(categoria)
        if fonte_recurso is not None:
            if isinstance(fonte_recurso, bool) or not isinstance(fonte_recurso, int):
                raise ErroDoPainel("fonte de recurso precisa ser o codigo inteiro")
            sql, eco["fonte_recurso"] = sql + " AND r.fonte_recurso = ?", fonte_recurso
            params.append(fonte_recurso)
        if programatica:
            if not re.fullmatch(r"\d{1,28}", str(programatica)):
                raise ErroDoPainel("programacao orcamentaria: informe de 1 a 28 digitos (inicio do codigo)")
            sql, eco["programatica_comeca_com"] = sql + " AND substr(r.programatica, 1, ?) = ?", programatica
            params += [len(programatica), programatica]
        if tipo_credor is not None:
            if tipo_credor not in publico.TIPOS_CREDOR:
                raise ErroDoPainel(f"tipo de credor precisa ser um de {publico.TIPOS_CREDOR}")
            sql, eco["tipo_credor"] = sql + " AND tipo_credor(r.cnpj) = ?", tipo_credor
            params.append(tipo_credor)
        if cnpj:
            d = re.sub(r"\D", "", str(cnpj))
            if len(d) != 14:
                raise ErroDoPainel("filtro de credor aceita so CNPJ completo (14 digitos) de pessoa juridica")
            formatado = f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
            sql, eco["cnpj"] = sql + " AND r.cnpj = ?", formatado
            params.append(formatado)
        if faixa is not None:
            if faixa not in FAIXAS:
                raise ErroDoPainel(f"faixa precisa ser uma de {FAIXAS}")
            coluna = "d.faixa_processado" if faixa in ("a", "b") else "d.faixa_nao_processado"
            sql, eco["faixa"] = sql + f" AND {coluna} = ?", faixa
            params.append(faixa)
        for nome, valor in (("orgao", orgao), ("funcao", funcao), ("programa", programa), ("elemento", elemento)):
            if valor is not None:
                if not re.fullmatch(r"\d{1,20}", str(valor)):
                    raise ErroDoPainel(f"{nome}: informe o código como a API devolve (de 1 a 20 dígitos)")
                sql, eco[nome] = sql + f" AND r.{nome} = ?", str(valor)
                params.append(str(valor))
        if sem_classificacao is not None:
            if sem_classificacao not in DIMENSOES_ORCAMENTARIAS:
                raise ErroDoPainel(f"sem_classificacao precisa ser uma de {DIMENSOES_ORCAMENTARIAS}")
            sql, eco["sem_classificacao"] = sql + f" AND r.{sem_classificacao} IS NULL", sem_classificacao
        return sql, tuple(params), eco

    def empenhos(self, exercicio, data_final, entidade=None, em=None, limite=100, deslocamento=0, ordem="saldo",
                 categoria=None, fonte_recurso=None, programatica=None, tipo_credor=None, cnpj=None, anoempenho=None,
                 empenho=None, faixa=None, orgao=None, funcao=None, programa=None, elemento=None,
                 sem_classificacao=None):
        """Lista paginada de registros do corte, com filtros opcionais, e os totais do conjunto filtrado.
        No nivel publico, sem nenhuma identificacao do credor (so o tipo).
        Conjunto vazio: `sem_resultado` e totais None (nunca R$ 0,00), com a mensagem do motivo."""
        limite, deslocamento = max(1, min(int(limite), LIMITE_LISTA)), max(0, int(deslocamento))
        filtro, params, eco = self._filtros_empenho(categoria, fonte_recurso, programatica, tipo_credor, cnpj,
                                                    anoempenho, empenho, faixa, orgao, funcao, programa, elemento,
                                                    sem_classificacao)
        ctx, em = self.contexto(), instante(em)
        corte = self._corte(ctx, exercicio, data_final, entidade, em)
        if not corte["disponivel"]:
            return {"disponivel": False, "motivo_indisponivel": corte["motivo"], "filtros": eco, "registros": []}
        regs = [{**reg, "proveniencia": prov} for reg, prov, _, _ in
                self._registros(ctx, corte["somar"], filtro, params, limite=limite, deslocamento=deslocamento, ordem=ordem)]
        totais = self._somas(ctx, corte["somar"], filtro, params) if filtro else self._somas(ctx, corte["somar"])
        regs_ind = self._regras_publicaveis(REGRAS_DO_INDICADOR)
        vazio = totais["registros"] == 0
        if not vazio:
            mensagem = None
        elif eco:
            mensagem = "nenhum registro do corte atende aos filtros aplicados"
        else:
            mensagem = "nenhum registro de RP neste corte: a API devolveu zero registros para as entidades do escopo"
        return {"disponivel": True, "retrato": corte["retrato"], "fonte": fontes.ELOTECH["rotulo"], "nivel": self.nivel,
                "filtros": eco, "entidades": corte["entidades"],
                "naturezas": {**{c: "da_fonte" for c in CAMPOS_REGISTRO + DINHEIRO}, **self._naturezas_derivados(),
                              "cancelamentos_c": "derivado"},
                "total": totais["registros"], "sem_resultado": vazio, "mensagem_sem_resultado": mensagem,
                "totais": {"natureza": "derivado", "regras": [r for r in regs_ind if r["codigo"] in ("S1", "CAT")],
                           "valores": None if vazio else {k: v for k, v in totais.items() if k != "registros"}},
                "limite": limite, "deslocamento": deslocamento, "registros": regs,
                "proveniencia": self._proveniencia(ctx, corte["somar"], "registros dos snapshots do corte; filtro so "
                                                                        "escolhe linhas")}

    def _naturezas_derivados(self):
        """Natureza de cada derivado por registro: 'derivado' se a regra compoe indicador publicado, senao 'analitico'
        (ex.: CANC v1, nao recomendada)."""
        governo = governanca.situacao_atual(self.con)
        return {c: ("derivado" if governo.get(regra, {}).get("compoe_indicador_publicado") else "analitico")
                for c, (_, _, regra) in fontes.DERIVADOS.items()}

    def detalhe_empenho(self, entidade, anoempenho, empenho, exercicio, data_final=None, em=None):
        """Detalhe de UM empenho num corte (padrao: o ultimo corte processado do exercicio para a entidade):
        campos da fonte com nome tecnico e amigavel, derivados com a regra, par espelhado, movimentacao e proveniencia."""
        ctx, em = self.contexto(), instante(em)
        if data_final is None:
            cortes = sorted(df for (e, ex, d0, df) in self._vigentes(ctx, em)
                            if e == entidade and ex == exercicio and d0 == f"{exercicio}-01-01")
            if not cortes:
                return {"encontrado": False, "motivo_indisponivel": "nenhum corte processado desta entidade no exercício"}
            data_final = cortes[-1]
        corte = self._corte(ctx, exercicio, data_final, entidade, em)
        if not corte["disponivel"]:
            return {"encontrado": False, "motivo_indisponivel": corte["motivo"]}
        ocorrencias = list(self._registros(ctx, corte["somar"], " AND r.anoempenho=? AND r.empenho=?",
                                           (anoempenho, empenho), ordem="empenho"))
        chave = {"entidade": entidade, "anoempenho": anoempenho, "empenho": empenho}
        if not ocorrencias:
            return {"encontrado": False, "chave": chave, "motivo_indisponivel": "empenho ausente deste corte",
                    "retrato": corte["retrato"]}
        governo = governanca.situacao_atual(self.con)
        saida = []
        for reg, prov, nome, cnpj in ocorrencias:
            campos = {c: {"campo_api": fontes.CAMPOS[c][0], "rotulo": fontes.CAMPOS[c][1], "valor": reg[c],
                          "natureza": "da_fonte", "significado": fontes.CAMPOS[c][2], "status_semantica": fontes.CAMPOS[c][3]}
                      for c in CAMPOS_REGISTRO + DINHEIRO}
            derivados = {}
            for c in DERIVADOS:
                rot, formula, (cod, ver) = fontes.DERIVADOS[c]
                g = governo.get((cod, ver), {})
                derivados[c] = {"rotulo": rot, "valor": reg[c], "formula": formula, "regra": f"{cod} v{ver}",
                                "situacao_da_regra": g.get("situacao"), "status_evidencia": g.get("status_evidencia"),
                                "natureza": "derivado" if g.get("compoe_indicador_publicado") else "analitico"}
            credor = {"tipo": reg["tipo_credor"], "nome_publico": publico.nome_publico(nome, cnpj)}
            if self.nivel == "interno":
                credor.update({c: reg[c] for c in publico.CAMPOS_RESTRITOS})
            cid = self.con.execute("SELECT id FROM coleta WHERE snapshot_uid=?", (prov["snapshot_uid"],)).fetchone()[0]
            saida.append({"campos": campos, "derivados": derivados, "credor": credor,
                          "par_espelhado": self._par(ctx, prov["resposta_id"], prov["indice_no_content"]),
                          "proveniencia": {**prov, "snapshot": self._snapshot(cid), "cadeia": CADEIA}})
        return {"encontrado": True, "retrato": corte["retrato"], "fonte": fontes.ELOTECH["rotulo"], "nivel": self.nivel,
                "chave": chave, "exercicio": exercicio, "data_final": data_final,
                "ocorrencias": saida, "movimentacao": self._movimentacao(ctx, entidade, anoempenho, empenho, em),
                "nota": ("Mais de uma ocorrência = a mesma chave apareceu mais de uma vez no snapshot; nenhuma é "
                         "descartada.") if len(saida) > 1 else None}

    def _par(self, ctx, resposta_id, indice):
        row = self.con.execute(
            "SELECT entidade_a, anoempenho_a, empenho_a, entidade_b, anoempenho_b, empenho_b, relacao_inscricao, "
            "lado_com_execucao, inscrito_a_c, inscrito_b_c, mesma_inscricao, "
            "CASE WHEN resposta_a_id=? AND indice_a=? THEN 'A' ELSE 'B' END "
            "FROM espelhamento_par WHERE derivacao_id=? AND ((resposta_a_id=? AND indice_a=?) OR "
            "(resposta_b_id=? AND indice_b=?))",
            (resposta_id, indice, ctx["derivacao"]["id"], resposta_id, indice, resposta_id, indice)).fetchone()
        if not row:
            return None
        par = regras.parametros(self.con, "PAR-24", 1)
        return {"este_registro_e_o_lado": row[11],
                "a": {"entidade": row[0], "anoempenho": row[1], "empenho": row[2], "inscrito_c": row[8]},
                "b": {"entidade": row[3], "anoempenho": row[4], "empenho": row[5], "inscrito_c": row[9]},
                "mesma_inscricao": bool(row[10]), "relacao_inscricao": row[6], "lado_com_execucao": row[7],
                "regra": "PAR-24 v1", "parametros_da_regra": par,
                "nota": ("Os dois registros continuam separados no bruto, na normalização e nos indicadores (a API "
                         "conta os dois); a natureza das cópias 24xxxxx não está determinada.")}

    def _movimentacao(self, ctx, entidade, anoempenho, empenho, em):
        filtro, p = (" AND coletada_em <= ?", (em,)) if em else ("", ())
        c = self.con.execute("SELECT id FROM coleta WHERE tipo='movimentacao' AND status='completa' AND entidade=? AND "
                             "anoempenho=? AND empenho=? AND id <= ?" + filtro +
                             " ORDER BY coletada_em DESC, snapshot_uid DESC LIMIT 1",
                             (entidade, anoempenho, empenho, ctx["limite_coleta"], *p)).fetchone()
        if not c:
            return {"coletada": False, "nota": "movimentação deste empenho não coletada"}
        lanc = [{"data": d, "tipo_lancamento": t, "descricao": desc, "valor_c": v, "natureza": "da_fonte",
                 "efeito": ef, "valor_com_sinal_c": vs,
                 "liquidacao_referida": f"{ln}/{le}" if ln is not None and le is not None else None,
                 "interpretacao": "derivado (MOV-REF v1: nos lançamentos 40/41 a liquidação está nos rótulos de pagamento)"}
                for d, t, desc, v, ef, vs, le, ln in self.con.execute(
                    "SELECT m.data, m.tipo_lancamento, m.descricao_tipo, m.valor_c, i.efeito, i.valor_com_sinal_c, "
                    "i.liquidacao_exercicio, i.liquidacao_numero FROM movimentacao_lancamento m LEFT JOIN "
                    "movimentacao_interpretada i ON i.derivacao_id=? AND i.resposta_id=m.resposta_id AND i.indice=m.indice "
                    "WHERE m.normalizacao_id=? AND m.coleta_id=? ORDER BY m.data, m.resposta_id, m.indice",
                    (ctx["derivacao"]["id"], ctx["normalizacao"]["id"], c[0]))]
        return {"coletada": True, "snapshot": self._snapshot(c[0]), "lancamentos": lanc}

    def pares(self, exercicio, data_final, em=None):
        """Pares espelhados (regra PAR-24) do corte: os dois lados continuam registros separados; nada e removido
        nem somado duas vezes por esta consulta. A natureza das copias continua nao determinada."""
        ctx, em = self.contexto(), instante(em)
        did, _ = self._derivacao_da_vigencia(ctx, em)
        if did is None:
            return {"pares": [], "nota": f"não há derivação 'como estava em' {em}"}
        par = regras.parametros(self.con, "PAR-24", 1)
        governo = governanca.situacao_atual(self.con).get(("PAR-24", 1), {})
        pares = [{"a": {"entidade": ea, "anoempenho": aa, "empenho": pa, "inscrito_c": ia},
                  "b": {"entidade": eb, "anoempenho": ab, "empenho": pb, "inscrito_c": ib},
                  "mesma_inscricao": bool(mesma), "relacao_inscricao": rel, "lado_com_execucao": lado,
                  "snapshots": self._uids([ca, cb])}
                 for ea, aa, pa, ia, eb, ab, pb, ib, mesma, rel, lado, ca, cb in self.con.execute(
                     "SELECT entidade_a, anoempenho_a, empenho_a, inscrito_a_c, entidade_b, anoempenho_b, empenho_b, "
                     "inscrito_b_c, mesma_inscricao, relacao_inscricao, lado_com_execucao, coleta_a_id, coleta_b_id "
                     "FROM espelhamento_par WHERE derivacao_id=? AND exercicio=? AND data_inicial=? AND data_final=? "
                     "ORDER BY anoempenho_a, empenho_a", (did, exercicio, f"{exercicio}-01-01", data_final))]
        resumo = {"pares": len(pares), "relacao": {}, "lado_com_execucao": {}, "anoempenho": {}}
        for p in pares:
            for k, v in (("relacao", p["relacao_inscricao"]), ("lado_com_execucao", p["lado_com_execucao"]),
                         ("anoempenho", p["a"]["anoempenho"])):
                resumo[k][v] = resumo[k].get(v, 0) + 1
        coletas = sorted({c for (c,) in self.con.execute(
            "SELECT coleta_a_id FROM espelhamento_par WHERE derivacao_id=? AND exercicio=? AND data_final=? UNION "
            "SELECT coleta_b_id FROM espelhamento_par WHERE derivacao_id=? AND exercicio=? AND data_final=?",
            (did, exercicio, data_final, did, exercicio, data_final))})
        return {"exercicio": exercicio, "data_final": data_final, "como_estava_em": em, "regra": "PAR-24 v1",
                "situacao_da_regra": governo.get("situacao"), "parametros_da_regra": par, "natureza": "derivado",
                "resumo": resumo, "pares": pares,
                "proveniencia": {**self._proveniencia(ctx, coletas, "tabela espelhamento_par da derivacao"),
                                 "derivacao_usada": did},
                "nota": ("Os dois lados de cada par continuam separados no bruto, na normalização e nos indicadores "
                         "(a API devolve os dois). A natureza das cópias (duplicidade ou transferência) não está "
                         "determinada; a consolidação só existe como visão analítica experimental (CONS-PAR).")}

    def fornecedores(self, exercicio, data_final, entidade=None, em=None, limite=100):
        """Totais por credor. No nivel publico, so por tipo de credor (sem identificacao)."""
        ctx, em = self.contexto(), instante(em)
        corte = self._corte(ctx, exercicio, data_final, entidade, em)
        if not corte["disponivel"]:
            return {"disponivel": False, "motivo_indisponivel": corte["motivo"], "linhas": []}
        grupos = {}
        for reg, _, nome, cnpj in self._registros(ctx, corte["somar"]):
            chave = (reg.get("fornecedor"), cnpj, nome) if self.nivel == "interno" else (reg["tipo_credor"],)
            g = grupos.setdefault(chave, {"registros": 0, "saldo_total_c": 0, "pagamentos_c": 0})
            g["registros"] += 1
            g["saldo_total_c"] += reg["s1_saldo_total_c"]
            g["pagamentos_c"] += reg["pago_proc_c"] + reg["pago_aproc_c"]
        rotulo = ("fornecedor", "cnpj", "nome") if self.nivel == "interno" else ("tipo_credor",)
        linhas = sorted(({**dict(zip(rotulo, k)), **v, "natureza": "derivado"} for k, v in grupos.items()),
                        key=lambda x: (-x["saldo_total_c"], str(x.get(rotulo[0]))))
        return {"disponivel": True, "nivel": self.nivel, "retrato": corte["retrato"], "fonte": fontes.ELOTECH["rotulo"],
                "linhas": linhas[:max(1, min(int(limite), LIMITE_LISTA))],
                "proveniencia": self._proveniencia(ctx, corte["somar"], "somas por credor")}

    # ------------------------------------------------------------------ retratos
    def retratos(self, entidade, exercicio, data_final):
        """Todos os retratos (snapshots) de um corte: cada coleta e um retrato independente; nenhum substitui outro.
        Para cada retrato completo e processado: registros, inscricao, saldo S1 e a diferenca para o retrato
        anterior comparavel (tambem completo e processado)."""
        ctx = self.contexto()
        di = f"{exercicio}-01-01"
        vig = self._vigentes(ctx, None).get((entidade, exercicio, di, data_final))
        regs = [r for r in self._regras_publicaveis(REGRAS_DO_INDICADOR) if r["codigo"] == "S1"]
        saida, anterior = [], None
        for cid, uid, quando, origem, status, obs in self.con.execute(
                "SELECT id, snapshot_uid, coletada_em, origem_carimbo, status, observacao FROM coleta WHERE "
                "tipo='rp_listagem' AND tipo_pesquisa IS NULL AND entidade=? AND exercicio=? AND data_inicial=? AND "
                "data_final=? ORDER BY coletada_em, snapshot_uid", (entidade, exercicio, di, data_final)):
            processado = cid <= ctx["limite_coleta"]
            objetos = [h for (h,) in self.con.execute("SELECT sha256 FROM resposta_bruta WHERE coleta_id=? ORDER BY ordem",
                                                      (cid,))]
            item = {"snapshot_uid": uid, "coletada_em": quando, "origem_carimbo": origem, "status": status,
                    "processado": processado, "vigente": cid == vig, "observacao": obs, "objetos": objetos,
                    "retrato": self._retrato(exercicio, data_final, [quando], None)["texto"],
                    "registros": None, "valores": None, "diferenca_para_o_anterior": None}
            if processado and status == "completa":
                s = self._somas(ctx, [cid])
                item["registros"] = s["registros"]
                item["valores"] = {"natureza": "derivado", "regras": regs,
                                   "inscricao_total_c": s["inscricao_total"], "saldo_total_c": s["saldo_total"]}
                if anterior is not None:
                    item["diferenca_para_o_anterior"] = {
                        "natureza": "diferenca", "anterior": anterior["snapshot_uid"],
                        "registros": s["registros"] - anterior["registros"],
                        "inscricao_total_c": s["inscricao_total"] - anterior["valores"]["inscricao_total_c"],
                        "saldo_total_c": s["saldo_total"] - anterior["valores"]["saldo_total_c"],
                        "bytes_identicos": objetos == anterior["objetos"]}
                anterior = item
            saida.append(item)
        return {"entidade": entidade, "exercicio": exercicio, "data_final": data_final, "retratos": saida,
                "fonte": fontes.ELOTECH["rotulo"],
                "nota": ("O mesmo corte coletado em momentos diferentes são retratos diferentes; o anterior nunca é "
                         "substituído. O vigente é o mais recente completo.")}

    def retratos_multiplos(self):
        """Cortes (entidade, exercicio, data final) com mais de um retrato de listagem processado."""
        ctx = self.contexto()
        return [{"entidade": e, "exercicio": ex, "data_final": df, "retratos": n}
                for e, ex, df, n in self.con.execute(
                    "SELECT entidade, exercicio, data_final, COUNT(*) FROM coleta WHERE tipo='rp_listagem' AND "
                    "tipo_pesquisa IS NULL AND id <= ? AND data_inicial = exercicio || '-01-01' "
                    "GROUP BY entidade, exercicio, data_final HAVING COUNT(*) > 1 ORDER BY exercicio, data_final, entidade",
                    (ctx["limite_coleta"],))]

    def entidades_do_corte(self, exercicio, data_final, em=None):
        """Visao por entidade de um corte. Distingue: entidade existente com RP (valores), entidade existente sem RP
        (zero de verdade), entidade fora do catalogo oficial do exercicio (nao existia: sem valor, nunca zero) e
        entidade sem snapshot (nao coletado: sem valor)."""
        ctx, em = self.contexto(), instante(em)
        corte = self._corte(ctx, exercicio, data_final, None, em)
        regs = self._regras_publicaveis(REGRAS_DO_INDICADOR)
        linhas = []
        for item in corte["entidades"]:
            linha = {k: item[k] for k in ("entidade", "nome", "situacao_no_exercicio", "snapshot", "entra_no_total",
                                          "retratos_do_corte")}
            linha["situacao_do_dado"] = item["situacao_do_dado"]
            linha["retrato_mais_novo_nao_processado"] = item["retrato_mais_novo_nao_processado"]
            if item["situacao_no_exercicio"] == "fora do catálogo oficial":
                linha.update(situacao_do_valor="não existia no exercício (fora do catálogo oficial)", valores=None)
            elif item["snapshot"] is None:
                linha.update(situacao_do_valor=item["situacao_do_dado"]["texto"], valores=None)
            else:
                cid = self.con.execute("SELECT id FROM coleta WHERE snapshot_uid=?",
                                       (item["snapshot"]["snapshot_uid"],)).fetchone()[0]
                s = self._somas(ctx, [cid])
                regs_s1 = [r for r in regs if r["codigo"] == "S1"]
                linha.update(situacao_do_valor=("existente, sem RP neste corte" if s["registros"] == 0
                                                else "valores do snapshot"),
                             valores={"natureza": "derivado", "regras": regs_s1, **s},
                             proveniencia=self._prov_curta(ctx, [item["snapshot"]["snapshot_uid"]],
                                                           "somas dos campos da API da entidade", regs_s1))
            linhas.append(linha)
        return {"exercicio": exercicio, "data_final": data_final, "como_estava_em": em, "retrato": corte["retrato"],
                "municipio_disponivel": corte["disponivel"], "motivo_indisponivel": corte["motivo"],
                "fonte": fontes.ELOTECH["rotulo"], "linhas": linhas,
                "nota": ("Entidade fora do catálogo oficial do exercício não existia naquele ano: aparece sem valor, "
                         "nunca como zero. Entidade existente sem RP aparece com zero.")}

    def comparar_retratos(self, snapshot_a, snapshot_b):
        """Comparacao de dois retratos do mesmo corte (comparador somente leitura)."""
        ctx = self.contexto()
        for ref in (snapshot_a, snapshot_b):
            row = self.con.execute("SELECT id FROM coleta WHERE snapshot_uid=?", (ref,)).fetchone()
            if not row:
                raise ErroDoPainel(f"snapshot {ref!r} não existe")
            if row[0] > ctx["limite_coleta"]:
                raise ErroDoPainel(f"snapshot {ref} ainda não processado: rode 'python -m rp processar'")
        r = _comparar(self.con, snapshot_a, snapshot_b, ctx["normalizacao"]["id"], ctx["derivacao"]["id"])
        if self.nivel != "interno":   # identificacao de credor nao sai no nivel publico
            for alt in r["alterados"]:
                alt["campos"] = [c if c["campo"] not in publico.CAMPOS_RESTRITOS else
                                 {"campo": c["campo"], "antes": "[restrito]", "depois": "[restrito]"} for c in alt["campos"]]
        r["natureza"] = "diferenca"
        r["fonte"] = fontes.ELOTECH["rotulo"]
        return r

    # ------------------------------------------------------------------ reconciliacao com o RREO
    def _derivacao_da_vigencia(self, ctx, em):
        if em is None:
            return ctx["derivacao"]["id"], ctx["normalizacao"]["id"]
        row = self.con.execute("SELECT id, normalizacao_id FROM derivacao_execucao WHERE vigencia_em=? "
                               "ORDER BY id DESC LIMIT 1", (em,)).fetchone()
        return (row[0], row[1]) if row else (None, None)

    def _linhas_conciliacao(self, did, nid, filtros, params):
        """Linhas da conciliacao. O mesmo PDF (mesmo SHA-256) coletado em mais de um snapshot aparece uma vez,
        com os demais snapshots listados em pdf.mesmo_pdf_coletado_tambem_em (os valores sao os mesmos bytes)."""
        governo = governanca.situacao_atual(self.con)
        pdfs, extracoes, vistos = {}, {}, {}
        saida = []
        for (rc, escopo, ent, ex, df, api_json, col, vr, va, dif, cod, ver) in self.con.execute(
                "SELECT c.rreo_coleta_id, c.escopo, c.entidade, c.exercicio, c.data_final, c.coletas_api_json, "
                "c.coluna, c.valor_rreo_c, c.valor_api_c, c.diferenca_c, g.codigo, g.versao "
                "FROM conciliacao_rreo c JOIN regra g ON g.id = c.regra_agregacao_id JOIN coleta k ON k.id = c.rreo_coleta_id "
                "WHERE c.derivacao_id=?" + filtros +
                " ORDER BY c.exercicio, c.data_final, c.escopo, g.versao, c.coluna, k.coletada_em, k.snapshot_uid",
                (did, *params)):
            if rc not in pdfs:
                s = self._snapshot(rc)
                emit = self.con.execute("SELECT emitido_em FROM rreo_valor WHERE normalizacao_id=? AND coleta_id=? LIMIT 1",
                                        (nid, rc)).fetchone()
                pdfs[rc] = {"snapshot_uid": s["snapshot_uid"], "id_arquivo": s["parametros"].get("id_arquivo"),
                            "rotulo": s["parametros"].get("rotulo"), "data_arquivo": s["parametros"].get("dataArquivo"),
                            "emitido_em": emit[0] if emit else None, "coletada_em": s["coletada_em"],
                            "objeto_bruto_sha256": s["respostas"][0]["objeto_bruto_sha256"] if s["respostas"] else None,
                            "url": s["respostas"][0]["url"] if s["respostas"] else None,
                            "mesmo_pdf_coletado_tambem_em": []}
                extracoes[rc] = self._extracao(nid, rc)
            chave = (pdfs[rc]["objeto_bruto_sha256"], escopo, ex, df, api_json, col, cod, ver)
            if chave in vistos:
                outro = vistos[chave]["pdf"]
                if pdfs[rc]["snapshot_uid"] not in outro["mesmo_pdf_coletado_tambem_em"]:
                    outro["mesmo_pdf_coletado_tambem_em"].append(pdfs[rc]["snapshot_uid"])
                continue
            regra = f"{cod} v{ver}"
            g = governo.get((cod, ver), {})
            operacional = g.get("situacao") == "operacional"
            achadas, situacao = explicacoes.explicar(ex, df, escopo, col, regra) if dif else ([], "sem diferença")
            vistos[chave] = {
                "exercicio": ex, "data_final": df, "periodo": f"janeiro a {MESES[int(df[5:7]) - 1]} de {ex}",
                "escopo": escopo, "entidade": ent, "coluna": col,
                "api_c": va, "rreo_c": vr, "diferenca_c": dif, "texto": f"API = {va}, RREO = {vr}, Diferença = {dif}",
                "api_natureza": "derivado" if operacional else "analitico",
                "rreo_natureza": "publicado", "diferenca_natureza": "diferenca",
                "api_descricao": f"registros da API agregados na coluna ({col}) do RREO pela regra {regra}",
                "regra_agregacao": {"regra": regra, "situacao": g.get("situacao"),
                                    "status_evidencia": g.get("status_evidencia")},
                "snapshots_api": json.loads(api_json), "pdf": pdfs[rc], "extracao": extracoes[rc],
                "situacao_da_diferenca": situacao,
                "explicacoes": [{k: e[k] for k in explicacoes.CAMPOS_SAIDA} for e in achadas],
                "nota": "A diferença é registro; o valor da API nunca é alterado para coincidir com o RREO."}
            saida.append(vistos[chave])
        saida.sort(key=lambda x: (x["exercicio"], x["data_final"], x["escopo"], x["regra_agregacao"]["regra"],
                                  ORDEM_COLUNAS.index(x["coluna"])))
        return saida

    def _extracao(self, nid, rreo_coleta_id):
        row = self.con.execute("SELECT extrator_versao, biblioteca, biblioteca_versao, sha256_pdf, id_arquivo, rotulo, "
                               "extraida_em, valores, erro FROM rreo_extracao WHERE normalizacao_id=? AND coleta_id=?",
                               (nid, rreo_coleta_id)).fetchone()
        if not row:
            return {"registrada": False, "nota": "normalização anterior ao registro da extração (esquema v4)"}
        return {**dict(zip(("extrator_versao", "biblioteca", "biblioteca_versao", "sha256_pdf", "id_arquivo", "rotulo",
                            "extraida_em", "valores", "erro"), row)), "registrada": True}

    def _reconciliacao_do_corte(self, ctx, exercicio, data_final, entidade, em):
        conc = regras.parametros(self.con, "CONC-RREO", 1)
        if entidade is None:
            escopo = "consolidado"
        elif entidade == conc["entidade_do_rreo_por_entidade"]:
            escopo = "entidade"
        else:
            return {"resumo": "sem RREO individual desta entidade no projeto", "linhas": []}
        did, nid = self._derivacao_da_vigencia(ctx, em)
        if did is None:
            return {"resumo": f"não há derivação 'como estava em' {em}; rode 'python -m rp processar --em ...'",
                    "linhas": []}
        linhas = self._linhas_conciliacao(did, nid, " AND c.exercicio=? AND c.data_final=? AND c.escopo=?",
                                          (exercicio, data_final, escopo))
        if not linhas:
            return {"resumo": "sem RREO transcrito para este corte e escopo", "linhas": []}
        return {"resumo": f"{len(linhas)} comparações coluna a coluna com o RREO ({escopo}); ver 'reconciliacao_rreo' "
                          "em cada valor", "linhas": linhas}

    def reconciliacao(self, exercicio=None, data_final=None, escopo=None, somente_diferencas=False, em=None):
        """Area de reconciliacao API Elotech x RREO: valor de cada lado, diferenca, regra, PDF, extracao e explicacao."""
        ctx, em = self.contexto(), instante(em)
        did, nid = self._derivacao_da_vigencia(ctx, em)
        if did is None:
            return {"linhas": [], "nota": f"não há derivação 'como estava em' {em}"}
        filtros, params = "", []
        for col, val in (("c.exercicio", exercicio), ("c.data_final", data_final), ("c.escopo", escopo)):
            if val is not None:
                filtros += f" AND {col}=?"
                params.append(val)
        if somente_diferencas:
            filtros += " AND c.diferenca_c <> 0"
        sem = [{"snapshot_uid": uid, "exercicio": ex, "rotulo": json.loads(pj).get("rotulo"), "extracao": self._extracao(nid, c)}
               for c, uid, ex, pj in self.con.execute(
                   "SELECT c.id, c.snapshot_uid, c.exercicio, c.parametros_json FROM coleta c WHERE c.tipo='rreo_pdf' AND "
                   "c.status='completa' AND c.id <= ? AND NOT EXISTS (SELECT 1 FROM rreo_valor v WHERE "
                   "v.normalizacao_id=? AND v.coleta_id=c.id) ORDER BY c.exercicio, c.snapshot_uid",
                   (ctx["limite_coleta"], nid))]
        return {"fonte_primaria": fontes.ELOTECH["rotulo"], "fonte_de_reconciliacao": fontes.RREO["rotulo"],
                "derivacao_id": did, "como_estava_em": em, "linhas": self._linhas_conciliacao(did, nid, filtros, params),
                "pdfs_sem_valores_transcritos": sem,
                "nota": ("O lado API é a projeção dos registros nas colunas do RREO pela regra indicada; enquanto "
                         "nenhuma versão de RREO-COL for operacional, essa projeção é valor analítico. O indicador "
                         "principal (somas dos campos da API) não depende dela.")}

    def documentos_rreo(self, em=None):
        """Indice dos RREOs conciliados: um item por documento (PDF) e escopo, com quantas colunas diferem em cada
        regra de agregacao. O detalhe coluna a coluna fica em `reconciliacao`."""
        r = self.reconciliacao(em=em)
        docs = {}
        for x in r["linhas"]:
            k = (x["exercicio"], x["data_final"], x["escopo"], x["pdf"]["snapshot_uid"])
            d = docs.setdefault(k, {"exercicio": x["exercicio"], "data_final": x["data_final"], "periodo": x["periodo"],
                                    "escopo": x["escopo"], "entidade": x["entidade"], "pdf": x["pdf"],
                                    "extracao": x["extracao"], "colunas_com_diferenca": {}, "colunas_comparadas": {}})
            regra = x["regra_agregacao"]["regra"]
            d["colunas_comparadas"][regra] = d["colunas_comparadas"].get(regra, 0) + 1
            d["colunas_com_diferenca"][regra] = d["colunas_com_diferenca"].get(regra, 0) + (x["diferenca_c"] != 0)
        return {"fonte_primaria": r.get("fonte_primaria"), "fonte_de_reconciliacao": r.get("fonte_de_reconciliacao"),
                "como_estava_em": r.get("como_estava_em"),
                "documentos": [docs[k] for k in sorted(docs, key=lambda k: (k[0], k[1], k[2]), reverse=True)],
                "pdfs_sem_valores_transcritos": r.get("pdfs_sem_valores_transcritos", []), "nota": r.get("nota")}

    def _api_do_corte(self, ctx, vig, cat, escopo, exercicio, data_final, ent_rreo):
        """Soma de S1 e (a)+(f) (RP de exercicios anteriores pela regra FAIXA) da API no corte, ou None se indisponivel."""
        corte = self._corte(ctx, exercicio, data_final, ent_rreo if escopo == "entidade" else None, None, vig, cat)
        if not corte["disponivel"]:
            return None
        s1, af = self._s1_e_a_mais_f(ctx, corte["somar"])
        return {"s1_c": s1, "a_mais_f_c": af, "snapshots": self._uids(corte["somar"]),
                "retrato": corte["retrato"]["texto"]}

    def _s1_e_a_mais_f(self, ctx, coletas):
        """Definicao unica (contrato M-04) de S1 e de (a)+(f) de um conjunto de coletas: soma de S1 v1, e soma de proc
        com faixa 'a' + soma de aproc com faixa 'f' (FAIXA v1). Usada pela coerencia entre publicacoes e pela serie entre
        exercicios."""
        filtro, p = self._de_coletas(coletas)
        s1, af = self.con.execute(
            f"SELECT SUM(d.s1_saldo_total_c), SUM(CASE WHEN d.faixa_processado='a' THEN r.proc_c ELSE 0 END) + "
            f"SUM(CASE WHEN d.faixa_nao_processado='f' THEN r.aproc_c ELSE 0 END) FROM rp_registro r JOIN rp_derivado d "
            f"ON d.derivacao_id=? AND d.resposta_id=r.resposta_id AND d.indice=r.indice WHERE r.normalizacao_id=? AND "
            f"{filtro}", (ctx["derivacao"]["id"], ctx["normalizacao"]["id"], *p)).fetchone()
        return s1 or 0, af or 0

    def coerencia_entre_publicacoes(self):
        """Saldo final L do RREO de dezembro de A x (a)+(f) (RP de exercicios anteriores) de cada RREO de A+1:
        duas publicacoes comparadas entre si. Ao lado, os mesmos agregados calculados hoje com a API (soma de S1 no
        fechamento de A e (a)+(f) no corte de A+1), para mostrar qual publicacao a base atual reproduz."""
        ctx = self.contexto()
        nid = ctx["normalizacao"]["id"]
        regs = self._regras_publicaveis({("S1", 1), ("FAIXA", 1)})
        vig, cat = self._vigentes(ctx, None), self._catalogo(ctx, None)
        ent_rreo = regras.parametros(self.con, "CONC-RREO", 1)["entidade_do_rreo_por_entidade"]
        docs, vistos = {}, set()
        for rc, escopo, ex, df, emit, sha in self.con.execute(
                "SELECT DISTINCT v.coleta_id, v.escopo, v.exercicio, v.data_final, v.emitido_em, "
                "(SELECT sha256 FROM resposta_bruta b WHERE b.coleta_id = v.coleta_id ORDER BY ordem LIMIT 1) "
                "FROM rreo_valor v JOIN coleta c ON c.id = v.coleta_id WHERE v.normalizacao_id=? AND "
                "v.linha='TOTAL (III)' ORDER BY v.exercicio, v.data_final, c.coletada_em, c.snapshot_uid", (nid,)):
            if sha in vistos:   # o mesmo PDF coletado outra vez: um documento so
                continue
            vistos.add(sha)
            docs.setdefault((escopo, ex), []).append({"coleta_id": rc, "data_final": df, "emitido_em": emit, "sha256": sha})

        def valores(rc):
            return dict(self.con.execute("SELECT coluna, valor_c FROM rreo_valor WHERE normalizacao_id=? AND coleta_id=? "
                                         "AND linha='TOTAL (III)'", (nid, rc)).fetchall())

        saida = []
        for (escopo, ex), lista in sorted(docs.items()):
            for fim in [d for d in lista if d["data_final"] == f"{ex}-12-31"]:
                va = valores(fim["coleta_id"])
                api_de = self._api_do_corte(ctx, vig, cat, escopo, ex, f"{ex}-12-31", ent_rreo)
                for prox in docs.get((escopo, ex + 1), []):
                    vb = valores(prox["coleta_id"])
                    if "L" not in va or "a" not in vb or "f" not in vb:
                        continue
                    dif = vb["a"] + vb["f"] - va["L"]
                    achadas, situacao = explicacoes.explicar_coerencia(escopo, ex) if dif else ([], "sem diferença")
                    api_para = self._api_do_corte(ctx, vig, cat, escopo, ex + 1, prox["data_final"], ent_rreo)
                    saida.append({
                        "escopo": escopo, "de": ex, "para": ex + 1,
                        "rreo_L_de_c": va["L"], "emitido_de": fim["emitido_em"],
                        "rreo_a_mais_f_para_c": vb["a"] + vb["f"], "data_final_para": prox["data_final"],
                        "emitido_para": prox["emitido_em"], "diferenca_c": dif,
                        "natureza": {"rreo": "publicado", "diferenca": "diferenca", "api": "derivado"},
                        "entre": "duas publicações (RREO × RREO)",
                        "pdfs": self._uids([fim["coleta_id"], prox["coleta_id"]]),
                        "api_s1_de_c": api_de and api_de["s1_c"], "api_a_mais_f_para_c": api_para and api_para["a_mais_f_c"],
                        "api_snapshots": {"de": api_de and api_de["snapshots"], "para": api_para and api_para["snapshots"]},
                        "api_regras": regs, "situacao_da_diferenca": situacao,
                        "explicacoes": [{k: e[k] for k in explicacoes.CAMPOS_SAIDA} for e in achadas],
                        "nota": ("O saldo que fecha A deveria ser o RP de exercícios anteriores que abre A+1; diferença "
                                 "indica alteração da base entre as duas emissões. Os valores da API são o estado atual "
                                 "da base, não o da época de cada emissão.")})
        ultima = {}   # por (escopo, A): a comparacao com a publicacao mais recente de A+1 (a primeira, em empate)
        for x in saida:
            k = (x["escopo"], x["de"])
            if k not in ultima or x["data_final_para"] > ultima[k]["data_final_para"]:
                ultima[k] = x
        for x in saida:
            x["mais_recente"] = ultima[(x["escopo"], x["de"])] is x
        return {"fonte": fontes.RREO["rotulo"], "comparacoes": saida,
                "limitacao": ("Só entram PDFs com valores transcritos pelo extrator de produção; os RREOs de 2016 "
                              "(entidade), 2018 e 2019 não são lidos por ele (ver 'pdfs_sem_valores_transcritos' na "
                              "reconciliação).")}

    def visao_analitica(self, exercicio, data_final, em=None):
        """Visoes do Municipio calculadas pela derivacao: projecao nas colunas do RREO (RREO-COL v1/v2) e visoes
        analiticas CONS-PAR. Nenhuma delas e indicador publicado."""
        ctx, em = self.contexto(), instante(em)
        did, _ = self._derivacao_da_vigencia(ctx, em)
        if did is None:
            return {"valores": [], "nota": f"não há derivação 'como estava em' {em}"}
        governo = governanca.situacao_atual(self.con)
        saida = []
        for visao, ga, va, gc, vc, comp, valor, snaps in self.con.execute(
                "SELECT v.visao, a.codigo, a.versao, c.codigo, c.versao, v.componente, v.valor_c, v.coletas_json "
                "FROM visao_valor v JOIN regra a ON a.id=v.regra_agregacao_id LEFT JOIN regra c ON c.id=v.regra_consolidacao_id "
                "WHERE v.derivacao_id=? AND v.exercicio=? AND v.data_final=? AND v.visao IN ('publicado', 'analitico') "
                "ORDER BY v.visao DESC, a.versao, c.versao, v.componente", (did, exercicio, data_final)):
            usadas = [(ga, va)] + ([(gc, vc)] if gc else [])
            operacional = all(governo.get(k, {}).get("situacao") == "operacional" for k in usadas)
            saida.append({"visao": visao, "componente": comp, "valor_c": valor,
                          "regras": [{"regra": f"{c} v{v}", "situacao": governo.get((c, v), {}).get("situacao")}
                                     for c, v in usadas],
                          "natureza": "derivado" if (visao == "publicado" and operacional) else "analitico",
                          "rotulo_da_visao": ("projeção dos registros da API nas colunas do RREO (NÃO é o valor publicado)"
                                              if visao == "publicado" else
                                              "visão analítica consolidada dos pares espelhados (hipótese experimental)"),
                          "snapshots": json.loads(snaps)})
        return {"exercicio": exercicio, "data_final": data_final, "como_estava_em": em, "derivacao_id": did,
                "valores": saida,
                "nota": ("Na derivação, a visão chamada 'publicado' é calculada a partir da API no formato do RREO; o "
                         "valor publicado de fato está na reconciliação. Nenhuma visão analítica entra no indicador "
                         "publicado, e o lado original de um par nunca é apagado.")}

    # ------------------------------------------------------------------ catalogo, fontes, metodologia
    def regras(self):
        atual = governanca.situacao_atual(self.con)
        params = {}
        for cod, ver, nome, valor in self.con.execute("SELECT r.codigo, r.versao, p.nome, p.valor_json FROM "
                                                      "regra_parametro p JOIN regra r ON r.id = p.regra_id"):
            params.setdefault((cod, ver), {})[nome] = json.loads(valor)
        definicoes = {(c, v): (t, d, f) for c, v, t, d, f in self.con.execute(
            "SELECT codigo, versao, tipo, definicao, fonte FROM regra")}
        return [{**item, "tipo": definicoes[k][0], "definicao": definicoes[k][1], "fonte_da_regra": definicoes[k][2],
                 "parametros": params.get(k, {})} for k, item in sorted(atual.items())]

    def evidencias(self):
        cols = ("id", "tipo", "descricao", "data_documento", "caminho_arquivo", "sha256", "registrada_em", "origem",
                "observacao", "manifesto", "evidencia_uid")
        return [dict(zip(cols, r)) for r in self.con.execute(f"SELECT {', '.join(cols)} FROM evidencia_externa ORDER BY id")]

    @staticmethod
    def fontes():
        return {"fontes": fontes.FONTES, "naturezas": fontes.NATUREZAS,
                "hierarquia": ["API Elotech/Oxy Transparência do Portal da Transparência de Ponta Grossa -> fonte "
                               "primária dos dados operacionais de RP",
                               "RREO Anexo VII -> publicação oficial independente / fonte de reconciliação",
                               "e-SIC, normas e notas técnicas -> fonte externa (evidência registrada)"]}

    def metodologia(self):
        """Textos de metodologia e as datas 'como estava em' com derivacao propria (reconciliacao historica)."""
        datas = [v for (v,) in self.con.execute("SELECT DISTINCT vigencia_em FROM derivacao_execucao WHERE vigencia_em "
                                                "IS NOT NULL ORDER BY vigencia_em")]
        return {**fontes.METODOLOGIA, "datas_como_estava_em_com_derivacao": datas,
                "situacoes_do_dado": {**SITUACOES_DO_DADO, **SITUACOES_DO_PONTO}}

    @staticmethod
    def dicionario_campos():
        return {"campos": {c: {"campo_api": a, "rotulo": r, "significado": s, "status": st,
                               "restrito_no_nivel_publico": c in publico.CAMPOS_RESTRITOS}
                           for c, (a, r, s, st) in fontes.CAMPOS.items()},
                "derivados": {c: {"rotulo": r, "formula": f, "regra": f"{cod} v{ver}"}
                              for c, (r, f, (cod, ver)) in fontes.DERIVADOS.items()},
                "unidade_monetaria": "centavos (inteiros); nenhum valor é arredondado"}
