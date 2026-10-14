"""Independent quality report, one dimension at a time (corrective audit of 13/10/2026, item 9). READ-ONLY.

Seven measurements, NEVER combined into one percentage: each has its own numerator, denominator, universe, cases
left out (and why) and acceptance criterion. The 99.9% target is declared reached for a dimension only when the
measured ratio is >= 0.999 with that documentation; otherwise it is reported as not reached, with the gap.

  1. fidelidade_da_ingestao   records and fields of the normalization that reproduce EXACTLY the raw API response
                              (re-read here from the store: manifest -> object -> JSON, Decimal -> cents);
  2. reprodutibilidade        published panel indicators (Municipality and each entity, every processed cut-off) that
                              equal an INDEPENDENT recalculation from the raw data. The scope rules in force are
                              re-implemented here from their recorded parameters (copies before 2026, 1-15 pairs from
                              2026, entity 7 per period); this file imports neither rp.painel nor rp.derivar;
  3. concordancia_documental  equal cells / comparable cells, per pair of sources, from MATRIZ_CONCORDANCIA.json;
  4. cobertura_documental     RREO Annex VII documents expected, collected, transcribed and checked by an independent
                              reading; SICONFI declarations available per period;
  5. residuos                 count and absolute value of the differences with no proven cause, per year and column;
  6. atualidade               days since the last collection, stored-but-unprocessed snapshots, retrospective alerts;
  7. integridade_da_proveniencia  published cut-offs whose every snapshot re-hashes to its manifest and objects.

Usage (from the repository root):
    python docs/audits/qualidade/medir_qualidade.py --banco DB --saida-json OUT.json --saida-md OUT.md
"""
import argparse
import calendar
import hashlib
import json
import sqlite3
import sys
import zlib
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "app"))
META = Decimal("0.999")
DINHEIRO = {"proc": "proc_c", "aproc": "aproc_c", "canceladoProc": "cancelado_proc_c", "pagoProc": "pago_proc_c",
            "pagoProcEstornado": "pago_proc_estornado_c", "canceladoAProc": "cancelado_aproc_c",
            "pagoAProc": "pago_aproc_c", "pagoAProcEstornado": "pago_aproc_estornado_c", "liquidado": "liquidado_c",
            "retencao": "retencao_c"}
TEXTO = {"entidade": "entidade", "anoempenho": "anoempenho", "empenho": "empenho", "dataEmissao": "data_emissao",
         "cnpj": "cnpj", "nome": "nome", "fonteRecurso": "fonte_recurso", "fornecedor": "fornecedor"}
INDICADORES = ("registros", "inscricao_processada", "inscricao_nao_processada", "inscricao_total", "pago_processado",
               "pago_nao_processado", "pagamentos", "liquidacoes", "cancelamentos", "retencoes", "saldo_total",
               "saldo_a_liquidar", "saldo_liquidado_a_pagar")


def cents(v):
    if v is None:
        return None
    return int((Decimal(str(v)) * 100).to_integral_value())


class Bruto:
    """Raw data read straight from the store (the oracle's only data source besides layer 0 of the database)."""

    def __init__(self, con, armazem):
        self.con, self.armazem = con, Path(armazem)

    def objeto(self, sha):
        corpo = zlib.decompress((self.armazem / "objetos" / sha[:2] / f"{sha}.zlib").read_bytes())
        if hashlib.sha256(corpo).hexdigest() != sha:
            raise ValueError(f"objeto {sha[:12]} não confere")
        return corpo

    def itens(self, coleta_id):
        """[(resposta_id, indice, item)] of a listing snapshot, in page order."""
        saida = []
        for rid, sha in self.con.execute("SELECT id, sha256 FROM resposta_bruta WHERE coleta_id=? ORDER BY ordem",
                                         (coleta_id,)):
            d = json.loads(self.objeto(sha), parse_float=Decimal)
            if isinstance(d, dict) and "content" in d:
                saida += [(rid, i, x) for i, x in enumerate(d["content"])]
        return saida


def indicadores(itens):
    s = dict.fromkeys(INDICADORES, 0)
    for r in itens:
        v = {k: cents(r.get(k)) or 0 for k in DINHEIRO}
        s["registros"] += 1
        s["inscricao_processada"] += v["proc"]
        s["inscricao_nao_processada"] += v["aproc"]
        s["inscricao_total"] += v["proc"] + v["aproc"]
        s["pago_processado"] += v["pagoProc"]
        s["pago_nao_processado"] += v["pagoAProc"]
        s["pagamentos"] += v["pagoProc"] + v["pagoAProc"]
        s["liquidacoes"] += v["liquidado"]
        s["cancelamentos"] += v["canceladoAProc"] + v["canceladoProc"]
        s["retencoes"] += v["retencao"]
        s["saldo_total"] += v["proc"] + v["aproc"] - v["pagoProc"] - v["pagoAProc"] - v["canceladoAProc"]
        s["saldo_a_liquidar"] += v["aproc"] - v["liquidado"] - v["canceladoAProc"]
        s["saldo_liquidado_a_pagar"] += v["proc"] - v["pagoProc"] + v["liquidado"] - v["pagoAProc"]
    return s


def medida(num, den, universo, criterio, fora=None):
    taxa = None if not den else Decimal(num) / Decimal(den)
    return {"numerador": num, "denominador": den, "taxa": None if taxa is None else float(taxa),
            "universo": universo, "criterio": criterio, "fora_do_denominador": fora or [],
            "meta_99_9": None if taxa is None else bool(taxa >= META)}


def fidelidade(con, bruto, nid, limite):
    """Every rp_registro row of normalization `nid` against its raw item (same response and index)."""
    cols = list(DINHEIRO.values()) + list(TEXTO.values())
    regs = defaultdict(dict)
    for row in con.execute(f"SELECT resposta_id, indice, {', '.join(cols)} FROM rp_registro WHERE normalizacao_id=?",
                           (nid,)):
        regs[row[0]][row[1]] = dict(zip(cols, row[2:]))
    registros = iguais = campos = campos_iguais = 0
    faltando = []
    for (cid,) in con.execute("SELECT id FROM coleta WHERE tipo='rp_listagem' AND status='completa' AND id <= ?",
                              (limite,)):
        for rid, i, item in bruto.itens(cid):
            reg = regs.get(rid, {}).get(i)
            if reg is None:
                faltando.append((cid, rid, i))
                continue
            registros += 1
            ok = True
            for api, col in DINHEIRO.items():
                campos += 1
                if cents(item.get(api)) == reg[col]:
                    campos_iguais += 1
                else:
                    ok = False
            for api, col in TEXTO.items():
                campos += 1
                v = item.get(api)
                if (str(v) if v is not None else None) == (str(reg[col]) if reg[col] is not None else None):
                    campos_iguais += 1
                else:
                    ok = False
            iguais += ok
    total = sum(len(v) for v in regs.values())
    return {"registros": medida(iguais, registros, f"{total} registros da normalização {nid} (listagens completas)",
                                "registro igual ao item bruto em todos os campos conferidos"),
            "campos": medida(campos_iguais, campos, f"{len(DINHEIRO)} campos monetários + {len(TEXTO)} de identificação "
                                                    "por registro", "valor do campo igual ao do bruto (centavos exatos)"),
            "itens_brutos_sem_registro": len(faltando)}


def _bimestre(df):
    return (int(df[5:7]) + 1) // 2


def municipio_independente(con, bruto, ex, df, vigentes, params, catalogo):
    """Municipality items of a cut-off, with the scope rules re-implemented from their recorded parameters."""
    mun_v2 = params.get(("ESCOPO-MUN", 2))
    cop = params.get(("COPIA-ORIGEM", 1))
    par = params.get(("PAR-24", 1))
    entidades = {e for e, anos in catalogo.items() if ex in anos}
    if mun_v2:
        trat, _ = mun_v2["periodos"].get(f"{ex}-{_bimestre(df)}", mun_v2["sem_periodo"])
        if trat == "inclui" and (mun_v2["entidade"], ex, df) in vigentes:
            entidades.add(mun_v2["entidade"])
    if not all((e, ex, df) in vigentes for e in entidades):
        return None
    por_ent = {e: [x for _, _, x in bruto.itens(vigentes[(e, ex, df)])] for e in entidades}
    if cop and ex < cop["primeiro_exercicio"] and cop["entidade_copia"] in por_ent:
        por_ent[cop["entidade_copia"]] = [x for x in por_ent[cop["entidade_copia"]]
                                          if not x["empenho"] >= cop["base_empenho_copia"]]
    if par and cop and ex >= cop["primeiro_exercicio"] and {par["entidade_copia"], par["entidade_original"]} <= set(por_ent):
        copias = {(x["anoempenho"], x["empenho"] - par["base_empenho_copia"]): x for x in por_ent[par["entidade_copia"]]
                  if x["empenho"] >= par["base_empenho_copia"]}
        campos = {"cnpj": "cnpj", "data_emissao": "dataEmissao"}

        def consolidado(b):
            a = copias.get((b["anoempenho"], b["empenho"]))
            return (a is not None and cents(a["proc"]) == cents(b["proc"]) and cents(a["aproc"]) == cents(b["aproc"])
                    and all(a.get(campos[c]) == b.get(campos[c]) for c in par["campos_de_conferencia"])
                    and not any(cents(b.get(k)) for k in ("pagoProc", "pagoAProc", "canceladoAProc", "liquidado")))
        por_ent[par["entidade_original"]] = [b for b in por_ent[par["entidade_original"]] if not consolidado(b)]
    return [x for xs in por_ent.values() for x in xs]


def reprodutibilidade(con, bruto, painel, limite):
    from rp import governanca, regras
    atual = governanca.situacao_atual(con)
    aplicadas = {k for k, g in atual.items() if g["situacao"] == "operacional" and g["compoe_indicador_publicado"]}
    params = {k: regras.parametros(con, *k) for k in (("ESCOPO-MUN", 2), ("COPIA-ORIGEM", 1)) if k in aplicadas}
    if ("CONS-PAR", 4) in aplicadas:
        params[("PAR-24", 1)] = regras.parametros(con, "PAR-24", 1)
    vigentes = {}
    for cid, e, ex, df in con.execute(
            "SELECT id, entidade, exercicio, data_final FROM coleta WHERE tipo='rp_listagem' AND tipo_pesquisa IS NULL "
            "AND status='completa' AND id <= ? AND data_inicial = exercicio || '-01-01' ORDER BY coletada_em, id",
            (limite,)):
        vigentes[(e, ex, df)] = cid       # the most recent complete snapshot of each cut-off (no duplicated keys in this base)
    catalogo = defaultdict(set)
    for (cid,) in con.execute("SELECT MAX(id) FROM coleta WHERE tipo='exercicios' AND status='completa' AND id <= ? "
                              "GROUP BY entidade", (limite,)):
        sha = con.execute("SELECT sha256 FROM resposta_bruta WHERE coleta_id=?", (cid,)).fetchone()[0]
        for x in json.loads(bruto.objeto(sha)):
            catalogo[x["id"]["entidade"]["id"]].add(x["id"]["exercicio"])
    valores = iguais = 0
    divergentes, sem_municipio = [], []
    for c in painel.cortes()["cortes"]:
        ex, df = c["exercicio"], c["data_final"]
        r = painel.indicadores(ex, df)
        if not r["disponivel"]:
            sem_municipio.append(f"{ex}|{df}")
            continue
        itens = municipio_independente(con, bruto, ex, df, vigentes, params, catalogo)
        if itens is None:
            divergentes.append({"corte": f"{ex}|{df}", "motivo": "o oráculo não monta o Município"})
            continue
        ind = indicadores(itens)
        for k in INDICADORES:
            valores += 1
            if ind[k] == r["valores"][k]["valor_c"]:
                iguais += 1
            else:
                divergentes.append({"corte": f"{ex}|{df}", "indicador": k, "painel": r["valores"][k]["valor_c"],
                                    "oraculo": ind[k]})
        for e in c["entidades_com_snapshot"]:
            re_ = painel.indicadores(ex, df, entidade=e)
            if not re_["disponivel"] or (e, ex, df) not in vigentes:
                continue
            itens_e = [x for _, _, x in bruto.itens(vigentes[(e, ex, df)])]
            cop = params.get(("COPIA-ORIGEM", 1))
            if cop and e == cop["entidade_copia"] and ex < cop["primeiro_exercicio"]:
                # COPIA-ORIGEM v1: the copies make up no indicator before their first fiscal year, the entity's own
                # view included (the pairs and entity 7 rules only change the Municipality)
                itens_e = [x for x in itens_e if not x["empenho"] >= cop["base_empenho_copia"]]
            ind = indicadores(itens_e)
            for k in INDICADORES:
                valores += 1
                if ind[k] == re_["valores"][k]["valor_c"]:
                    iguais += 1
                else:
                    divergentes.append({"corte": f"{ex}|{df}", "entidade": e, "indicador": k,
                                        "painel": re_["valores"][k]["valor_c"], "oraculo": ind[k]})
    return medida(iguais, valores, "indicadores publicados de todos os cortes processados (Município e cada entidade)",
                  "valor do painel igual ao recálculo independente a partir do bruto",
                  [f"Município indisponível no painel (nunca zero): {', '.join(sem_municipio)}"] if sem_municipio else []
                  ) | {"divergentes": divergentes[:50], "regras_de_escopo_reimplementadas": sorted(f"{a} v{b}" for a, b in params)}


def proveniencia_publicada(con, bruto, painel):
    ok_cortes = cortes = 0
    falhas = []
    vistos = {}
    for c in painel.cortes()["cortes"]:
        r = painel.indicadores(c["exercicio"], c["data_final"])
        if not r["disponivel"]:
            continue
        cortes += 1
        bom = True
        for uid in r["retrato"]["snapshots"]:
            if uid not in vistos:
                cid, rel = con.execute("SELECT id, manifesto FROM coleta WHERE snapshot_uid=?", (uid,)).fetchone()
                h = con.execute("SELECT sha256 FROM coleta_manifesto WHERE coleta_id=?", (cid,)).fetchone()
                arq = bruto.armazem / rel
                certo = h is not None and arq.exists() and hashlib.sha256(arq.read_bytes()).hexdigest() == h[0]
                try:
                    for (sha,) in con.execute("SELECT sha256 FROM resposta_bruta WHERE coleta_id=?", (cid,)):
                        bruto.objeto(sha)
                except (ValueError, FileNotFoundError):
                    certo = False
                vistos[uid] = certo
            bom = bom and vistos[uid]
            if not vistos[uid]:
                falhas.append(uid[:8])
        ok_cortes += bom
    return medida(ok_cortes, cortes, f"cortes publicados do Município ({len(vistos)} snapshots distintos)",
                  "todo snapshot do corte: manifesto com o SHA-256 registrado e todo objeto bruto com o SHA-256 do nome")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--banco", required=True)
    ap.add_argument("--saida-json", required=True)
    ap.add_argument("--saida-md", required=True)
    a = ap.parse_args()
    from rp import atualizacao, rreo_cobertura, siconfi
    from rp.config import carregar
    from rp.painel import Painel
    con = sqlite3.connect(f"file:{a.banco}?mode=ro", uri=True)
    bruto = Bruto(con, carregar().snapshots)
    nid, limite = con.execute("SELECT id, ultima_coleta_id FROM normalizacao_execucao ORDER BY id DESC LIMIT 1").fetchone()
    r = {"normalizacao": nid}
    r["fidelidade_da_ingestao"] = fidelidade(con, bruto, nid, limite)
    with Painel.abrir(a.banco) as painel:
        r["reprodutibilidade"] = reprodutibilidade(con, bruto, painel, limite)
        r["integridade_da_proveniencia"] = proveniencia_publicada(con, bruto, painel)
    matriz = json.loads((RAIZ / "docs/audits/rreo/MATRIZ_CONCORDANCIA.json").read_text(encoding="utf-8"))
    conc = defaultdict(lambda: [0, 0])
    for x in matriz["celulas"]:
        conc[x["comparacao"]][1] += 1
        conc[x["comparacao"]][0] += x["classe"] == "concorda"
    r["concordancia_documental"] = {k: medida(v[0], v[1], f"células comparáveis ({k})", "valores iguais ao centavo")
                                    for k, v in conc.items()}
    cob = rreo_cobertura.matriz(con, nid)
    val = json.loads((RAIZ / "docs/audits/rreo/COBERTURA_E_CONFERENCIA.json").read_text(encoding="utf-8"))
    esperados = {k: v for k, v in cob["resumo"].items() if k in rreo_cobertura.SITUACOES}
    transcritos = esperados.get("transcrito", 0)
    total = sum(esperados.values())
    conferidos = val.get("resumo", {}).get("conferidos")
    leitura = siconfi.leituras()[-1]
    declaracoes = sum(1 for ano in range(2016, 2027) for b in range(1, 7) if siconfi.declaracao(leitura, ano, b))
    r["cobertura_documental"] = {
        "rreo_transcritos": medida(transcritos, total, f"documentos do Anexo VII listados pelo portal ({total})",
                                   "coletado e transcrito pelo extrator de produção",
                                   [f"{k}: {v}" for k, v in esperados.items() if k != "transcrito"]),
        "rreo_conferidos_por_leitura_independente": medida(conferidos or 0, transcritos,
                                                           "documentos transcritos",
                                                           "todas as células iguais na segunda leitura (xpdf)"),
        "siconfi_declaracoes": {"periodos_com_declaracao": declaracoes, "leitura": leitura.name},
        "por_exercicio": cob["por_exercicio"]}
    r["residuos"] = matriz["residuos"]
    r["residuos_resumo"] = matriz["resumo"]
    r["atualidade"] = atualizacao.atualidade(con)
    Path(a.saida_json).write_text(json.dumps(r, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    pct = lambda m: "—" if m["taxa"] is None else f"{m['taxa'] * 100:.4f}%".replace(".", ",")
    meta = lambda m: "—" if m["meta_99_9"] is None else ("atingida" if m["meta_99_9"] else "não atingida")
    linhas = [("1. Fidelidade da ingestão (registros)", r["fidelidade_da_ingestao"]["registros"]),
              ("1. Fidelidade da ingestão (campos)", r["fidelidade_da_ingestao"]["campos"]),
              ("2. Reprodutibilidade do cálculo", r["reprodutibilidade"]),
              *[(f"3. Concordância documental: {k}", m) for k, m in r["concordancia_documental"].items()],
              ("4. Cobertura: RREO transcritos", r["cobertura_documental"]["rreo_transcritos"]),
              ("4. Cobertura: RREO conferidos por leitura independente",
               r["cobertura_documental"]["rreo_conferidos_por_leitura_independente"]),
              ("7. Integridade da proveniência (cortes publicados)", r["integridade_da_proveniencia"])]
    md = ["# Relatório de qualidade por dimensão", "",
          f"Gerado por `docs/audits/qualidade/medir_qualidade.py` sobre a normalização {nid}. Cada dimensão tem o seu "
          "numerador, denominador e critério; **nenhum percentual global** é calculado. A meta de 99,9% só é dada como "
          "atingida na dimensão em que a medição a confirma.", "",
          "| Dimensão | Numerador | Denominador | Taxa | Meta 99,9% | Universo | Critério |", "|---|---:|---:|---:|---|---|---|"]
    for nome, m in linhas:
        md.append(f"| {nome} | {m['numerador']} | {m['denominador']} | {pct(m)} | {meta(m)} | {m['universo']} | "
                  f"{m['criterio']} |")
    md += ["", "## 5. Resíduos sem causa determinada", "",
           "Por comparação e exercício (valor absoluto da parte sem causa comprovada; detalhe por coluna em "
           "`docs/audits/rreo/MATRIZ_CONCORDANCIA.md`):", "",
           "| Comparação | Exercício | Células | Valor |", "|---|---|---:|---:|"]
    br = lambda c: f"{c / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    for x in r["residuos_resumo"]:
        if x["nao_determinadas"]:
            md.append(f"| {x['comparacao']} | {x['exercicio']} | {x['nao_determinadas']} | {br(x['valor_nao_determinado_c'])} |")
    at = r["atualidade"]
    md += ["", "## 6. Atualidade", "",
           f"- Última coleta de listagem: {at['ultima_coleta_por_tipo'].get('rp_listagem')} "
           f"({at['dias_desde_a_ultima_listagem']} dia(s) antes desta medição).",
           f"- Retratos armazenados ainda não processados (não publicados): {at['retratos_armazenados_nao_processados']}.",
           f"- Cortes com alteração entre retratos: {at['cortes_com_alteracao']}; alertas retrospectivos: "
           f"{at['alertas_retrospectivos']}.", "",
           "## Casos fora dos denominadores", ""]
    for nome, m in linhas:
        for f in m["fora_do_denominador"]:
            md.append(f"- {nome}: {f}")
    if r["reprodutibilidade"]["divergentes"]:
        md += ["", "## Divergências da reprodutibilidade (até 50)", ""]
        md += [f"- {json.dumps(d, ensure_ascii=False)}" for d in r["reprodutibilidade"]["divergentes"]]
    Path(a.saida_md).write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({n: pct(m) for n, m in linhas}, ensure_ascii=False))


if __name__ == "__main__":
    main()
