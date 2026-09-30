"""Camada de consulta do dashboard: SOMENTE LEITURA sobre o banco do projeto.

Fluxo:  API Elotech -> coleta -> snapshot imutavel -> normalizacao -> derivacao -> ESTA CAMADA -> dashboard.
  * Nao chama a API: le o banco aberto em modo read-only (URI mode=ro + PRAGMA query_only). A coleta continua
    sendo do coletor; nenhuma tela depende do portal estar no ar.
  * Indicador principal = registros da API Elotech (somas de campos e formulas S1-S3). O RREO so aparece na
    reconciliacao, lado a lado; uma divergencia nunca altera o valor da API.
  * Todo valor sai com: natureza (fonte, publicado, derivado, analitico, diferenca), regras usadas com a
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
    dict(id="pagamentos", rotulo="Pagamentos no período", sql="SUM(r.pago_proc_c + r.pago_aproc_c)",
         colunas=["pago_proc_c", "pago_aproc_c"], regras=[], formula="soma de pagoProc + pagoAProc"),
    dict(id="estornos_de_pagamento", rotulo="Estornos de pagamento (informativo; já descontados dos pagamentos)",
         sql="SUM(r.pago_proc_estornado_c + r.pago_aproc_estornado_c)",
         colunas=["pago_proc_estornado_c", "pago_aproc_estornado_c"], regras=[],
         formula="soma dos estornos brutos; já descontados de pagoProc e pagoAProc"),
    dict(id="liquidacoes", rotulo="Liquidações no período (líquidas de estornos)", sql="SUM(r.liquidado_c)",
         colunas=["liquidado_c"], regras=[], formula="soma de liquidado", rreo=["h"]),
    dict(id="cancelamentos", rotulo="Cancelamentos no período", sql="SUM(r.cancelado_aproc_c + r.cancelado_proc_c)",
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

    @classmethod
    def abrir(cls, caminho, nivel="publico"):
        """Conexao SOMENTE LEITURA ao banco (o painel nunca escreve). Exige esquema v4 ou mais novo."""
        p = Path(caminho)
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
    def _corte(self, ctx, exercicio, data_final, entidade, em, vig=None, cat=None):
        di = f"{exercicio}-01-01"
        vig = self._vigentes(ctx, em) if vig is None else vig
        cat = self._catalogo(ctx, em) if cat is None else cat
        com_snapshot = {e for (e, ex, d0, df) in vig if ex == exercicio and d0 == di and df == data_final}
        universo = [entidade] if entidade is not None else sorted(set(cat["entidades"]) | com_snapshot)
        itens, somar, faltam, fora, avisos = [], [], [], [], []
        for e in universo:
            status = self._status_no_exercicio(cat, e, exercicio)
            cid = vig.get((e, exercicio, di, data_final))
            item = {"entidade": e, "nome": cat["entidades"].get(e, {}).get("nome"), "situacao_no_exercicio": status,
                    "snapshot": None, "entra_no_total": False}
            if cid is not None:
                uid, quando = self.con.execute("SELECT snapshot_uid, coletada_em FROM coleta WHERE id=?", (cid,)).fetchone()
                n = self.con.execute("SELECT COUNT(*) FROM rp_registro WHERE normalizacao_id=? AND coleta_id=?",
                                     (ctx["normalizacao"]["id"], cid)).fetchone()[0]
                item["snapshot"] = {"snapshot_uid": uid, "coletada_em": quando, "registros": n}
            if status == "fora do catálogo oficial":
                fora.append(e)
                if item["snapshot"] and item["snapshot"]["registros"]:
                    avisos.append(f"entidade {e} fora do catálogo oficial de {exercicio} com registros no snapshot: "
                                  "não somados ao Município")
            elif cid is None:
                faltam.append(e)
            else:
                somar.append(cid)
                item["entra_no_total"] = True
            itens.append(item)
        if entidade is not None and fora:
            motivo = "entidade fora do catálogo oficial do exercício: não existia; não é RP zero"
        elif faltam:
            motivo = f"corte não coletado (ou ainda não processado) para a(s) entidade(s) {faltam}"
        elif not somar:
            motivo = "nenhuma entidade do catálogo oficial com snapshot neste corte"
        else:
            motivo = None
        coletadas = [i["snapshot"]["coletada_em"] for i in itens if i["entra_no_total"]]
        return {"exercicio": exercicio, "data_inicial": di, "data_final": data_final, "entidade": entidade, "em": em,
                "entidades": itens, "fora_do_catalogo": fora, "faltam": faltam, "somar": somar, "avisos": avisos,
                "disponivel": motivo is None, "motivo": motivo,
                "retrato": self._retrato(exercicio, data_final, coletadas, em)}

    @staticmethod
    def _retrato(exercicio, data_final, coletadas, em):
        """Rotulo obrigatorio de todo valor: retrato atual ou 'como a base estava em'."""
        if not coletadas:
            return None
        ini, fim = min(coletadas), max(coletadas)
        d0, d1 = _data_br(ini), _data_br(fim)
        quando = f"coletado em {d0}" if d0 == d1 else f"coletado entre {d0} e {d1}"
        base = f"exercício de {exercicio}, corte {_data_br(data_final)}, {quando}"
        texto = f"Como a base estava em {_instante_br(em)}: {base}" if em else f"Estado atual da base para o {base}"
        return {"tipo": "historico" if em else "atual", "texto": texto, "exercicio": exercicio, "data_final": data_final,
                "coletado_de": ini, "coletado_ate": fim, "como_estava_em": em,
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

    def _somas(self, ctx, coletas):
        filtro, p = self._de_coletas(coletas)
        linha = self.con.execute(
            f"SELECT {', '.join(s['sql'] for s in SOMAS)} FROM rp_registro r JOIN rp_derivado d ON d.derivacao_id=? "
            f"AND d.resposta_id=r.resposta_id AND d.indice=r.indice WHERE r.normalizacao_id=? AND {filtro}",
            (ctx["derivacao"]["id"], ctx["normalizacao"]["id"], *p)).fetchone()
        valores = {s["id"]: (v or 0) for s, v in zip(SOMAS, linha)}
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
            filtro, p = self._de_coletas(corte["somar"])
            regs_cat = [r for r in regras_usadas if r["codigo"] in ("CAT", "S1")]
            for cat, n, insc, s1 in self.con.execute(
                    f"SELECT d.categoria, COUNT(*), SUM(r.proc_c + r.aproc_c), SUM(d.s1_saldo_total_c) FROM rp_registro r "
                    f"JOIN rp_derivado d ON d.derivacao_id=? AND d.resposta_id=r.resposta_id AND d.indice=r.indice "
                    f"WHERE r.normalizacao_id=? AND {filtro} GROUP BY d.categoria ORDER BY d.categoria",
                    (ctx["derivacao"]["id"], ctx["normalizacao"]["id"], *p)):
                categorias.append({"categoria": cat, "registros": n, "inscricao_total_c": insc or 0,
                                   "saldo_total_c": s1 or 0, "natureza": "derivado", "regras": regs_cat,
                                   "proveniencia": self._prov_curta(ctx, uids, "agrupamento por categoria (CAT v1)",
                                                                    regs_cat)})
        avisos = [fontes.METODOLOGIA["importante"]] + corte["avisos"]
        if self._pendentes(ctx):
            avisos.append("Há snapshots de listagem ainda não processados; rode 'python -m rp processar'.")
        return {"consulta": {"exercicio": exercicio, "data_final": data_final, "entidade": entidade, "como_estava_em": em},
                "escopo": f"entidade {entidade}" if entidade is not None else "Município (entidades do catálogo oficial do exercício)",
                "disponivel": corte["disponivel"], "motivo_indisponivel": corte["motivo"], "retrato": corte["retrato"],
                "fonte": fontes.ELOTECH["rotulo"], "entidades": corte["entidades"], "valores": valores,
                "categorias": categorias, "reconciliacao": rec.get("resumo"), "avisos": avisos,
                "proveniencia": self._proveniencia(ctx, corte["somar"], "somas sobre rp_registro + rp_derivado")}

    def evolucao(self, exercicio, entidade=None, em=None):
        """Indicadores de todos os cortes processados do exercicio (evolucao dentro do ano)."""
        ctx, em = self.contexto(), instante(em)
        di = f"{exercicio}-01-01"
        cortes = sorted({df for (e, ex, d0, df) in self._vigentes(ctx, em)
                         if ex == exercicio and d0 == di and (entidade is None or e == entidade)})
        serie = []
        for df in cortes:
            r = self.indicadores(exercicio, df, entidade, em)
            serie.append({"data_final": df, "disponivel": r["disponivel"], "motivo_indisponivel": r["motivo_indisponivel"],
                          "retrato": r["retrato"],
                          "valores": {k: {x: v[x] for x in ("rotulo", "valor_c", "natureza", "proveniencia")}
                                      for k, v in r["valores"].items()}})
        return {"exercicio": exercicio, "entidade": entidade, "como_estava_em": em, "fonte": fontes.ELOTECH["rotulo"],
                "serie": serie}

    def por_dimensao(self, dimensao, exercicio, data_final, entidade=None, em=None):
        """Totais por fonte de recurso, programacao orcamentaria, orgao, categoria etc. (lista fechada de dimensoes)."""
        if dimensao not in DIMENSOES:
            raise ErroDoPainel(f"dimensao precisa ser uma de {sorted(DIMENSOES)}")
        ctx, em = self.contexto(), instante(em)
        corte = self._corte(ctx, exercicio, data_final, entidade, em)
        regras_usadas = self._regras_publicaveis(REGRAS_DO_INDICADOR)
        if not corte["disponivel"]:
            return {"dimensao": dimensao, "disponivel": False, "motivo_indisponivel": corte["motivo"], "linhas": []}
        grupo = ", ".join(DIMENSOES[dimensao])
        filtro, p = self._de_coletas(corte["somar"])
        uids = self._uids(corte["somar"])
        regs = [r for r in regras_usadas if r["codigo"] in ("S1",) + (("CAT",) if dimensao == "categoria" else ())]
        k = len(DIMENSOES[dimensao])
        linhas = []
        for row in self.con.execute(
                f"SELECT {grupo}, COUNT(*), SUM(r.proc_c + r.aproc_c), SUM(r.pago_proc_c + r.pago_aproc_c), "
                f"SUM(r.liquidado_c), SUM(r.cancelado_aproc_c + r.cancelado_proc_c), SUM(d.s1_saldo_total_c) "
                f"FROM rp_registro r JOIN rp_derivado d ON d.derivacao_id=? AND d.resposta_id=r.resposta_id "
                f"AND d.indice=r.indice WHERE r.normalizacao_id=? AND {filtro} GROUP BY {grupo} "
                f"ORDER BY SUM(d.s1_saldo_total_c) DESC, {grupo}",
                (ctx["derivacao"]["id"], ctx["normalizacao"]["id"], *p)):
            chave = dict(zip([c.split(".")[1] for c in DIMENSOES[dimensao]], row[:k]))
            n, insc, pag, liq, canc, s1 = row[k:]
            linhas.append({**chave, "registros": n, "inscricao_total_c": insc or 0, "pagamentos_c": pag or 0,
                           "liquidacoes_c": liq or 0, "cancelamentos_c": canc or 0, "saldo_total_c": s1 or 0,
                           "natureza": "derivado",
                           "proveniencia": self._prov_curta(ctx, uids, f"somas agrupadas por {dimensao}", regs)})
        return {"dimensao": dimensao, "disponivel": True, "retrato": corte["retrato"], "fonte": fontes.ELOTECH["rotulo"],
                "linhas": linhas, "proveniencia": self._proveniencia(ctx, corte["somar"], f"somas agrupadas por {dimensao}")}

    # ------------------------------------------------------------------ registros
    def _registros(self, ctx, coletas, filtro_extra="", params=(), limite=None, deslocamento=0, ordem="saldo"):
        ordens = {"saldo": "d.s1_saldo_total_c DESC, r.entidade, r.anoempenho, r.empenho, r.resposta_id, r.indice",
                  "empenho": "r.entidade, r.anoempenho, r.empenho, r.resposta_id, r.indice"}
        if ordem not in ordens:
            raise ErroDoPainel(f"ordem precisa ser uma de {sorted(ordens)}")
        restritos = list(publico.CAMPOS_RESTRITOS) if self.nivel == "interno" else []
        filtro, p = self._de_coletas(coletas)
        colunas = ([f"r.{c}" for c in CAMPOS_REGISTRO + DINHEIRO] + [f"d.{c}" for c in DERIVADOS] +
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
        nomes = (CAMPOS_REGISTRO + DINHEIRO + DERIVADOS +
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

    def empenhos(self, exercicio, data_final, entidade=None, em=None, limite=100, deslocamento=0, ordem="saldo"):
        """Lista paginada de registros do corte. No nivel publico, sem nenhuma identificacao do credor."""
        limite, deslocamento = max(1, min(int(limite), LIMITE_LISTA)), max(0, int(deslocamento))
        ctx, em = self.contexto(), instante(em)
        corte = self._corte(ctx, exercicio, data_final, entidade, em)
        if not corte["disponivel"]:
            return {"disponivel": False, "motivo_indisponivel": corte["motivo"], "registros": []}
        regs = [{**reg, "proveniencia": prov} for reg, prov, _, _ in
                self._registros(ctx, corte["somar"], limite=limite, deslocamento=deslocamento, ordem=ordem)]
        return {"disponivel": True, "retrato": corte["retrato"], "fonte": fontes.ELOTECH["rotulo"], "nivel": self.nivel,
                "naturezas": {**{c: "fonte" for c in CAMPOS_REGISTRO + DINHEIRO}, **{c: "derivado" for c in DERIVADOS}},
                "total": self._somas(ctx, corte["somar"])["registros"], "limite": limite, "deslocamento": deslocamento,
                "registros": regs}

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
                          "natureza": "fonte", "significado": fontes.CAMPOS[c][2], "status_semantica": fontes.CAMPOS[c][3]}
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
        lanc = [{"data": d, "tipo_lancamento": t, "descricao": desc, "valor_c": v, "natureza": "fonte",
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
        return {"exercicio": exercicio, "data_final": data_final, "como_estava_em": em, "regra": "PAR-24 v1",
                "situacao_da_regra": governo.get("situacao"), "parametros_da_regra": par, "natureza": "derivado",
                "resumo": resumo, "pares": pares,
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
        """Todos os retratos (snapshots) de um corte: cada coleta e um retrato independente; nenhum substitui outro."""
        ctx = self.contexto()
        di = f"{exercicio}-01-01"
        vig = self._vigentes(ctx, None).get((entidade, exercicio, di, data_final))
        saida = []
        for cid, uid, quando, origem, status, obs in self.con.execute(
                "SELECT id, snapshot_uid, coletada_em, origem_carimbo, status, observacao FROM coleta WHERE "
                "tipo='rp_listagem' AND tipo_pesquisa IS NULL AND entidade=? AND exercicio=? AND data_inicial=? AND "
                "data_final=? ORDER BY coletada_em, snapshot_uid", (entidade, exercicio, di, data_final)):
            n = self.con.execute("SELECT COUNT(*) FROM rp_registro WHERE normalizacao_id=? AND coleta_id=?",
                                 (ctx["normalizacao"]["id"], cid)).fetchone()[0]
            saida.append({"snapshot_uid": uid, "coletada_em": quando, "origem_carimbo": origem, "status": status,
                          "processado": cid <= ctx["limite_coleta"], "registros": n, "vigente": cid == vig,
                          "observacao": obs,
                          "objetos": [h for (h,) in self.con.execute(
                              "SELECT sha256 FROM resposta_bruta WHERE coleta_id=? ORDER BY ordem", (cid,))],
                          "retrato": self._retrato(exercicio, data_final, [quando], None)["texto"]})
        return {"entidade": entidade, "exercicio": exercicio, "data_final": data_final, "retratos": saida,
                "nota": ("O mesmo corte coletado em momentos diferentes são retratos diferentes; o anterior nunca é "
                         "substituído. O vigente é o mais recente completo.")}

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

    def _api_do_corte(self, ctx, vig, cat, escopo, exercicio, data_final, ent_rreo):
        """Soma de S1 e (a)+(f) (RP de exercicios anteriores pela regra FAIXA) da API no corte, ou None se indisponivel."""
        corte = self._corte(ctx, exercicio, data_final, ent_rreo if escopo == "entidade" else None, None, vig, cat)
        if not corte["disponivel"]:
            return None
        filtro, p = self._de_coletas(corte["somar"])
        s1, af = self.con.execute(
            f"SELECT SUM(d.s1_saldo_total_c), SUM(CASE WHEN d.faixa_processado='a' THEN r.proc_c ELSE 0 END) + "
            f"SUM(CASE WHEN d.faixa_nao_processado='f' THEN r.aproc_c ELSE 0 END) FROM rp_registro r JOIN rp_derivado d "
            f"ON d.derivacao_id=? AND d.resposta_id=r.resposta_id AND d.indice=r.indice WHERE r.normalizacao_id=? AND "
            f"{filtro}", (ctx["derivacao"]["id"], ctx["normalizacao"]["id"], *p)).fetchone()
        return {"s1_c": s1 or 0, "a_mais_f_c": af or 0, "snapshots": self._uids(corte["somar"]),
                "retrato": corte["retrato"]["texto"]}

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

    @staticmethod
    def metodologia():
        return fontes.METODOLOGIA

    @staticmethod
    def dicionario_campos():
        return {"campos": {c: {"campo_api": a, "rotulo": r, "significado": s, "status": st,
                               "restrito_no_nivel_publico": c in publico.CAMPOS_RESTRITOS}
                           for c, (a, r, s, st) in fontes.CAMPOS.items()},
                "derivados": {c: {"rotulo": r, "formula": f, "regra": f"{cod} v{ver}"}
                              for c, (r, f, (cod, ver)) in fontes.DERIVADOS.items()},
                "unidade_monetaria": "centavos (inteiros); nenhum valor é arredondado"}
