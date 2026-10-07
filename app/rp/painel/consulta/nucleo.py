"""Painel mixin: Core of the Painel: connection, context, catalog, cut-offs, provenance and the helpers shared
by more than one topic."""
import json
import sqlite3
from pathlib import Path

from ... import banco, governanca, regras, vigencia
from .. import fontes, publico
from .comum import (CADEIA, CAMPOS_REGISTRO, _data_br, DERIVADOS, DINHEIRO, ErroDoPainel, ESQUEMA_MINIMO,
                    EsquemaAntigo, EXPR_CANCELAMENTOS, _in, instante, _instante_br, NIVEIS, NivelInvalido,
                    RegraNaoOperacional, SemProcessamento, SITUACOES_DO_DADO, SOMAS, VERSAO)


class Nucleo:
    """Core of the Painel: connection, context, catalog, cut-offs, provenance and the helpers shared"""

    def __init__(self, con, nivel="publico"):
        if nivel not in NIVEIS:
            raise NivelInvalido(f"nivel precisa ser um de {NIVEIS}: {nivel!r}")
        self.con, self.nivel = con, nivel
        # creditor type computed in SQL by the same function as the public layer (registering a function does not write to the database)
        con.create_function("tipo_credor", 1, publico.tipo_credor, deterministic=True)

    @classmethod
    def abrir(cls, caminho, nivel="publico"):
        """READ-ONLY connection to the database (the panel never writes). Requires schema v4 or newer."""
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

    # ------------------------------------------------------------------ context
    def contexto(self):
        """Most recent current derivation, the normalization it was made on and the highest collection id that
        normalization read (normalizacao_execucao.ultima_coleta_id). Collection ids only grow (layer 0 does not
        delete), so every collection with an id up to that limit was already in the database when the normalization
        ran. A normalization older than schema v4 (without the column): limit = highest collection with a row in
        layer 1, which is conservative (a newer empty snapshot shows as not processed, never as zero)."""
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

    def _ambiguas(self, ctx):
        """Collections with a repeated key (CHAVE-DUP) in the context's derivation: never the current snapshot. The current
        derivation covers all complete collections, including the ones before any `em`."""
        did = ctx["derivacao"]["id"]
        if getattr(self, "_ambiguas_de", None) != did:
            self._ambiguas_de, self._ambiguas_cache = did, vigencia.coletas_ambiguas(self.con, did)
        return self._ambiguas_cache

    def _vigentes(self, ctx, em):
        """Current snapshot of each listing cut-off: the single rule of `vigencia.coletas_vigentes` (the same as the
        derivation's), restricted to the snapshots the context's normalization processed."""
        return vigencia.coletas_vigentes(self.con, em, excluir=self._ambiguas(ctx), limite_coleta=ctx["limite_coleta"])

    def _cortes_ambiguos(self, ctx, em):
        """Cut-offs (entidade, exercicio, data_inicial, data_final) with a snapshot processed up to `em` that has a repeated
        key. They enter the universe of cut-offs (R1: a cut-off without data appears with its situation, never
        omitted), but the ambiguous snapshot is never summed."""
        amb = self._ambiguas(ctx)
        if not amb:
            return set()
        filtro, p = (" AND coletada_em <= ?", (em,)) if em else ("", ())
        return {tuple(r) for r in self.con.execute(
            f"SELECT entidade, exercicio, data_inicial, data_final FROM coleta WHERE id IN ({','.join('?' * len(amb))}) "
            "AND tipo='rp_listagem' AND tipo_pesquisa IS NULL AND status='completa' AND id <= ?" + filtro,
            (*sorted(amb), ctx["limite_coleta"], *p))}

    def _retrato_recusado(self, ctx, e, exercicio, di, data_final, em, usado):
        """Warning when the cut-off's newest snapshot (processed, up to `em`) has a repeated key and the panel uses the
        previous valid one, or None. Only queries the database if there is an ambiguous collection."""
        if not self._ambiguas(ctx):
            return None
        filtro, p = (" AND coletada_em <= ?", (em,)) if em else ("", ())
        mais_novo = self.con.execute(
            "SELECT id, snapshot_uid, coletada_em FROM coleta WHERE tipo='rp_listagem' AND tipo_pesquisa IS NULL AND "
            "status='completa' AND entidade=? AND exercicio=? AND data_inicial=? AND data_final=? AND id <= ?" + filtro +
            " ORDER BY coletada_em DESC, snapshot_uid DESC LIMIT 1",
            (e, exercicio, di, data_final, ctx["limite_coleta"], *p)).fetchone()
        if not mais_novo or mais_novo[0] == usado or mais_novo[0] not in self._ambiguas(ctx):
            return None
        return (f"entidade {e}: o retrato mais novo do corte (snapshot {mais_novo[1][:8]}, coletado em "
                f"{_data_br(mais_novo[2])}) tem chave de empenho repetida (CHAVE-DUP) e não é usado"
                + ("; vale o retrato válido anterior" if usado else "; não há retrato válido anterior"))

    def _pendentes(self, ctx):
        return self.con.execute("SELECT COUNT(*) FROM coleta WHERE tipo='rp_listagem' AND id > ?",
                                (ctx["limite_coleta"],)).fetchone()[0]

    # ------------------------------------------------------------------ historical entity catalog
    def _catalogo(self, ctx, em):
        """Entity catalog and, per entity, the fiscal year catalog: the most recent snapshots up to `em` (same choice as
        derivar._entidades_do_catalogo), among the processed ones."""
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
            exerc[e] = {"coleta_id": cid, "snapshot_uid": uid, "coletada_em": quando}   # the most recent one stays
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
        """Historical catalog: for each entity, official period, observed period and situation in the fiscal year."""
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

    # ------------------------------------------------------------------ cut-off
    def _estado_sem_snapshot(self, ctx, e, exercicio, di, data_final, em):
        """Why an entity has no processed snapshot at the cut-off: never collected, collected and not yet processed, or
        only incomplete/failed collections. Looks at every collection of the cut-off up to `em` (including the ones
        after the normalization in use)."""
        filtro_em, p_em = (" AND coletada_em <= ?", (em,)) if em else ("", ())
        linhas = self.con.execute(
            "SELECT id, status FROM coleta WHERE tipo='rp_listagem' AND tipo_pesquisa IS NULL AND entidade=? AND "
            "exercicio=? AND data_inicial=? AND data_final=?" + filtro_em, (e, exercicio, di, data_final, *p_em)).fetchall()
        if any(st == "completa" and cid > ctx["limite_coleta"] for cid, st in linhas):
            return "nao_processado"
        if any(st == "completa" and cid in self._ambiguas(ctx) for cid, st in linhas):
            return "ambiguo"
        if any(st != "completa" for _, st in linhas):
            return "incompleto"
        return "sem_coleta"

    def _corte(self, ctx, exercicio, data_final, entidade, em, vig=None, cat=None):
        di = f"{exercicio}-01-01"
        vig = self._vigentes(ctx, em) if vig is None else vig
        cat = self._catalogo(ctx, em) if cat is None else cat
        com_snapshot = {e for (e, ex, d0, df) in vig if ex == exercicio and d0 == di and df == data_final}
        ambiguas = {e for (e, ex, d0, df) in self._cortes_ambiguos(ctx, em) if ex == exercicio and d0 == di
                    and df == data_final}
        universo = [entidade] if entidade is not None else sorted(set(cat["entidades"]) | com_snapshot | ambiguas)
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
            recusado = self._retrato_recusado(ctx, e, exercicio, di, data_final, em, cid)
            if recusado:
                avisos.append(recusado)
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
        """Mandatory label of every value: current snapshot or 'as the base was on', with the snapshots used."""
        if not coletadas:
            return None
        ini, fim = min(coletadas), max(coletadas)
        d0, d1 = _data_br(ini), _data_br(fim)
        quando = f"coletado em {d0}" if d0 == d1 else f"coletado entre {d0} e {d1}"
        base = f"exercício de {exercicio}, corte {_data_br(data_final)}, {quando}"
        texto = f"Como a base estava em {_instante_br(em)}: {base}" if em else f"Estado atual da base para o {base}"
        return {"tipo": "historico" if em else "atual", "texto": texto, "exercicio": exercicio, "data_final": data_final,
                "coletado_de": ini, "coletado_ate": fim, "como_estava_em": em, "snapshots": snapshots or [],
                "corte_posterior_a_coleta": data_final > ini[:10],   # e.g. a 31/12 cut-off collected in September
                "nota": fontes.METODOLOGIA["importante"]}

    def cortes(self, em=None):
        """Cut-offs with a processed snapshot: covered entities and whether the Municipality total is available."""
        ctx, em = self.contexto(), instante(em)
        vig, cat = self._vigentes(ctx, em), self._catalogo(ctx, em)
        por_corte = {}
        for (e, ex, di, df) in vig:
            if di == f"{ex}-01-01":
                por_corte.setdefault((ex, df), set()).add(e)
        for (e, ex, di, df) in self._cortes_ambiguos(ctx, em):     # only an ambiguous snapshot: shown, unavailable
            if di == f"{ex}-01-01":
                por_corte.setdefault((ex, df), set())
        saida = []
        for (ex, df), ents in sorted(por_corte.items()):
            c = self._corte(ctx, ex, df, None, em, vig, cat)
            saida.append({"exercicio": ex, "data_final": df, "entidades_com_snapshot": sorted(ents),
                          "municipio_disponivel": c["disponivel"], "motivo": c["motivo"],
                          "fora_do_catalogo": c["fora_do_catalogo"]})
        return {"como_estava_em": em, "cortes": saida, "snapshots_nao_processados": self._pendentes(ctx)}

    # ------------------------------------------------------------------ governance and provenance
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

    # ------------------------------------------------------------------ indicators
    def _de_coletas(self, coletas):
        """Filter of the records of a set of collections by the primary key (resposta_id IN ...)."""
        ph = _in(len(coletas))
        return (f"r.resposta_id IN (SELECT id FROM resposta_bruta WHERE coleta_id IN ({ph})) AND r.coleta_id IN ({ph})",
                (*coletas, *coletas))

    def _somas(self, ctx, coletas, filtro_extra="", params_extra=()):
        """SOMAS sums over the collections' records (with an optional filter). Without a filter, checks that the
        derivation covers every record of the cut-off: if it does not, there is no total (an error, never a smaller
        total)."""
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
        if n != valores["registros"]:   # the derivation covers every processed record; if it does not, there is no total
            raise ErroDoPainel(f"derivacao {ctx['derivacao']['id']} sem os valores derivados de {n - valores['registros']} "
                               "registro(s) do corte: reprocesse ('python -m rp processar')")
        return valores

    @staticmethod
    def _campos(colunas):
        return [{"coluna": c, "campo_api": fontes.CAMPOS[c][0], "rotulo": fontes.CAMPOS[c][1]} for c in colunas]

    @staticmethod
    def _situacao_do_ponto(r, entidade):
        """Situation of a point (contract section 2.2) from the result of `indicadores`."""
        if entidade is not None:
            return r["entidades"][0]["situacao_do_dado"]["codigo"]
        if not r["disponivel"]:
            return "municipio_indisponivel"
        somadas = [e for e in r["entidades"] if e["entra_no_total"]]
        return "sem_rp" if all(e["situacao_do_dado"]["codigo"] == "sem_rp" for e in somadas) else "com_dados"

    def _pares_no_corte(self, ctx, exercicio, data_final, entidade):
        """Distinct 24xxxxx copies with a pair at the cut-off (PAR-24 v1), when the scope involves the pair's entities;
        otherwise 0."""
        par = regras.parametros(self.con, "PAR-24", 1)
        if entidade is not None and entidade not in (par["entidade_copia"], par["entidade_original"]):
            return 0
        return self.con.execute(
            "SELECT COUNT(DISTINCT anoempenho_a || '/' || empenho_a) FROM espelhamento_par WHERE derivacao_id=? AND "
            "exercicio=? AND data_inicial=? AND data_final=?",
            (ctx["derivacao"]["id"], exercicio, f"{exercicio}-01-01", data_final)).fetchone()[0]

    # ------------------------------------------------------------------ investigation of variations (05.5)
    def _universo_do_exercicio(self, ctx, vig, exercicio, em):
        """Processed cut-offs of the fiscal year, of any entity (contract section 2.4), including the cut-off whose only
        snapshot has a repeated key: it appears with the situation 'ambiguo', without a value."""
        di = f"{exercicio}-01-01"
        return sorted({df for (e, ex, d0, df) in set(vig) | self._cortes_ambiguos(ctx, em) if ex == exercicio and d0 == di})

    # ------------------------------------------------------------------ records
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

    def _naturezas_derivados(self):
        """Nature of each per-record derived value: 'derivado' if the rule makes up a published indicator, otherwise
        'analitico' (e.g. CANC v1, not recommended)."""
        governo = governanca.situacao_atual(self.con)
        return {c: ("derivado" if governo.get(regra, {}).get("compoe_indicador_publicado") else "analitico")
                for c, (_, _, regra) in fontes.DERIVADOS.items()}

    # ------------------------------------------------------------------ reconciliation with the RREO
    def _derivacao_da_vigencia(self, ctx, em):
        if em is None:
            return ctx["derivacao"]["id"], ctx["normalizacao"]["id"]
        row = self.con.execute("SELECT id, normalizacao_id FROM derivacao_execucao WHERE vigencia_em=? "
                               "ORDER BY id DESC LIMIT 1", (em,)).fetchone()
        return (row[0], row[1]) if row else (None, None)

    def _s1_e_a_mais_f(self, ctx, coletas):
        """Single definition (contract M-04) of S1 and of (a)+(f) for a set of collections: sum of S1 v1, and sum of proc
        with band 'a' + sum of aproc with band 'f' (FAIXA v1). Used by the consistency between publications and by the
        series across fiscal years."""
        filtro, p = self._de_coletas(coletas)
        s1, af = self.con.execute(
            f"SELECT SUM(d.s1_saldo_total_c), SUM(CASE WHEN d.faixa_processado='a' THEN r.proc_c ELSE 0 END) + "
            f"SUM(CASE WHEN d.faixa_nao_processado='f' THEN r.aproc_c ELSE 0 END) FROM rp_registro r JOIN rp_derivado d "
            f"ON d.derivacao_id=? AND d.resposta_id=r.resposta_id AND d.indice=r.indice WHERE r.normalizacao_id=? AND "
            f"{filtro}", (ctx["derivacao"]["id"], ctx["normalizacao"]["id"], *p)).fetchone()
        return s1 or 0, af or 0
