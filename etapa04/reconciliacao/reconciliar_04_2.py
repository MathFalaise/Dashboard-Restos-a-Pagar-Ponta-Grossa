"""Reconciliacao INVESTIGACAO x PRODUCAO (Etapa 04.2). Artefato de validacao, nao e producao.

    bruto das Etapas 01/02 --> pipeline de investigacao (etapa03/validacao) --> ESPERADO
    bruto das Etapas 01/02 --> importador + pipeline de producao (app/rp)   --> OBTIDO
    ESPERADO == OBTIDO, tabela a tabela, linha a linha

Os snapshots dos dois lados sao pareados pelo CONTEUDO: (tipo, coletada_em, SHA-256 de cada
resposta em ordem). Ids internos, nomes de versao e carimbos de execucao nao entram na comparacao.
Nao faz nenhuma requisicao a internet.

Uso: python reconciliar_04_2.py PASTA_TEMPORARIA [BANCO_ATIVO]
"""
import json
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "etapa03" / "validacao"))
sys.path.insert(0, str(RAIZ / "app"))

import construir_banco as inv  # noqa: E402  (investigacao)
from rp import banco, derivar, importar, normalizar  # noqa: E402  (producao)
from rp.armazem import Armazem  # noqa: E402
from rp.config import carregar  # noqa: E402


def chaves_snapshot(con):
    """{coleta_id: (tipo, coletada_em, (sha256, ...))}"""
    out = {}
    for cid, tipo, quando in con.execute("SELECT id, tipo, coletada_em FROM coleta"):
        shas = tuple(s for (s,) in con.execute("SELECT sha256 FROM resposta_bruta WHERE coleta_id=? ORDER BY ordem", (cid,)))
        out[cid] = (tipo, quando, shas)
    return out


def origem(con, K):
    """{resposta_id: (chave do snapshot, ordem)}"""
    return {rid: (K[cid], o) for rid, cid, o in con.execute("SELECT id, coleta_id, ordem FROM resposta_bruta")}


def regras(con):
    return {i: (c, v) for i, c, v in con.execute("SELECT id, codigo, versao FROM regra")}


def uids(con):
    return dict(con.execute("SELECT snapshot_uid, id FROM coleta")) if "snapshot_uid" in \
        [r[1] for r in con.execute("PRAGMA table_info(coleta)")] else {}


def tabelas(con, nid, did):
    K = chaves_snapshot(con)
    O = origem(con, K)
    Rg = regras(con)
    U = uids(con)
    nk = lambda x: K[U.get(x, x)] if x is not None else None
    t = {}
    cols_rp = [c[1] for c in con.execute("PRAGMA table_info(rp_registro)")
               if c[1] not in ("normalizacao_id", "resposta_id", "indice", "coleta_id")]
    t["rp_registro"] = {(O[r[0]], r[1]): r[2:] for r in con.execute(
        f"SELECT resposta_id, indice, {','.join(cols_rp)} FROM rp_registro WHERE normalizacao_id=?", (nid,))}
    cols_mov = [c[1] for c in con.execute("PRAGMA table_info(movimentacao_lancamento)")
                if c[1] not in ("normalizacao_id", "resposta_id", "indice", "coleta_id")]
    t["movimentacao_lancamento"] = {(O[r[0]], r[1]): r[2:] for r in con.execute(
        f"SELECT resposta_id, indice, {','.join(cols_mov)} FROM movimentacao_lancamento WHERE normalizacao_id=?", (nid,))}
    t["rreo_valor"] = {(K[r[0]], r[1], r[2]): r[3:] for r in con.execute(
        "SELECT coleta_id, linha, coluna, escopo, exercicio, data_final, emitido_em, valor_c FROM rreo_valor WHERE normalizacao_id=?", (nid,))}
    t["entidade_ref"] = {(K[r[0]], r[1]): r[2:] for r in con.execute(
        "SELECT coleta_id, entidade, nome, cnpj, tipo FROM entidade_ref WHERE normalizacao_id=?", (nid,))}
    t["exercicio_ref"] = {(K[r[0]], r[1], r[2]): r[3:] for r in con.execute(
        "SELECT coleta_id, entidade, exercicio, aberto, fechado FROM exercicio_ref WHERE normalizacao_id=?", (nid,))}
    t["rp_derivado"] = {(O[r[0]], r[1]): r[2:] for r in con.execute(
        "SELECT resposta_id, indice, entidade, anoempenho, empenho, categoria, faixa_processado, faixa_nao_processado, "
        "s1_saldo_total_c, s2_a_liquidar_c, s3_liquidado_a_pagar_c, cancel_processado_c, cancel_nao_processado_c "
        "FROM rp_derivado WHERE derivacao_id=?", (did,))}
    t["movimentacao_interpretada"] = {(O[r[0]], r[1]): r[2:] for r in con.execute(
        "SELECT resposta_id, indice, liquidacao_exercicio, liquidacao_numero, efeito, valor_com_sinal_c "
        "FROM movimentacao_interpretada WHERE derivacao_id=?", (did,))}
    t["anomalia"] = Counter((Rg[r[0]], r[1], nk(r[2]), *r[3:]) for r in con.execute(
        "SELECT regra_id, tipo, coleta_id, entidade, anoempenho, empenho, IFNULL(detalhe_json,'') FROM anomalia WHERE derivacao_id=?", (did,)))
    t["espelhamento_par"] = {(r[0], r[1], r[2], O[r[3]], r[4], O[r[5]], r[6]): r[7:] for r in con.execute(
        "SELECT exercicio, data_inicial, data_final, resposta_a_id, indice_a, resposta_b_id, indice_b, entidade_a, anoempenho_a, "
        "empenho_a, entidade_b, anoempenho_b, empenho_b, inscrito_a_c, inscrito_b_c, mesma_inscricao, relacao_inscricao, "
        "execucao_a_c, execucao_b_c, lado_com_execucao FROM espelhamento_par WHERE derivacao_id=?", (did,))}
    t["visao_valor"] = {(r[0], Rg[r[1]], Rg.get(r[2]), r[3], r[4], r[5], r[6]): (r[7], tuple(sorted(nk(x) for x in json.loads(r[8]))))
                        for r in con.execute(
        "SELECT visao, regra_agregacao_id, regra_consolidacao_id, entidade, exercicio, data_final, componente, valor_c, coletas_json "
        "FROM visao_valor WHERE derivacao_id=?", (did,))}
    t["conciliacao_rreo"] = {(K[r[0]], Rg[r[1]], r[2]): (*r[3:10], tuple(sorted(nk(x) for x in json.loads(r[10])))) for r in con.execute(
        "SELECT rreo_coleta_id, regra_agregacao_id, coluna, escopo, entidade, exercicio, data_final, valor_rreo_c, valor_api_c, "
        "diferenca_c, coletas_api_json FROM conciliacao_rreo WHERE derivacao_id=?", (did,))}
    ver = Counter()
    ver_sem_snapshot = Counter()
    for rg, desc, esc, v, f in con.execute("SELECT regra_id, descricao, escopo_json, verificados, falhas FROM verificacao WHERE derivacao_id=?", (did,)):
        e = json.loads(esc)
        # investigacao guarda ids ("coletas", "rreo_coleta"); producao guarda uids ("snapshots", "rreo_snapshot")
        ids = e.pop("coletas", None) or e.pop("snapshots", None)
        if ids is not None:
            e["snapshots"] = [nk(x) for x in ids]
        rreo = e.pop("rreo_coleta", None) or e.pop("rreo_snapshot", None)
        if rreo is not None:
            e["rreo"] = nk(rreo)
        ver[(Rg[rg], desc, json.dumps(e, sort_keys=True, default=str), v, f)] += 1
        e.pop("snapshots", None)
        ver_sem_snapshot[(Rg[rg], desc, json.dumps(e, sort_keys=True, default=str), v, f)] += 1
    t["verificacao"] = ver
    t["verificacao (sem a escolha do snapshot)"] = ver_sem_snapshot
    return t


def comparar(esperado, obtido):
    linhas = []
    for nome in esperado:
        E, O = esperado[nome], obtido[nome]
        if isinstance(E, Counter):
            iguais = E == O
            n = sum(E.values())
            dif = list((E - O).items())[:3] + list((O - E).items())[:3]
        else:
            iguais = E == O
            n = len(E)
            so_e = [k for k in E if k not in O][:2]
            so_o = [k for k in O if k not in E][:2]
            diverg = [(k, E[k], O[k]) for k in E if k in O and E[k] != O[k]][:3]
            dif = so_e + so_o + diverg
        linhas.append((nome, n, sum(O.values()) if isinstance(O, Counter) else len(O), iguais, dif))
    return linhas


def main(tmp, banco_ativo=None):
    tmp = Path(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    # ESPERADO: pipeline de investigacao
    ci, ni, di, _, _ = inv.construir(tmp / "investigacao.sqlite")
    esperado = tabelas(ci, ni, di)
    # OBTIDO: importador + pipeline de producao
    cfg = carregar(dados_locais=tmp / "prod_local", snapshots=tmp / "prod_snapshots", backups=tmp / "prod_backups")
    cp = banco.abrir(cfg)
    importar.importar_etapas_anteriores(cp, Armazem(cfg.snapshots), RAIZ)
    np_, _ = normalizar.normalizar(cp)
    dp = derivar.derivar(cp, np_)
    obtido = tabelas(cp, np_, dp)

    out = ["# Reconciliação investigação × produção (Etapa 04.2)", "",
           "Gerado por `etapa04/reconciliacao/reconciliar_04_2.py`, sem acesso à internet.",
           "", "- **Esperado:** pipeline de investigação (`etapa03/validacao`) sobre o bruto das Etapas 01/02.",
           "- **Obtido:** importador + pipeline de produção (`app/rp`) sobre o mesmo bruto.",
           "- Snapshots pareados por conteúdo: tipo, horário e SHA-256 de cada resposta.", "",
           "## 1. Tabela a tabela", "", "| Tabela | Linhas esperadas | Linhas obtidas | Igual? | Primeiras diferenças |",
           "|---|--:|--:|---|---|"]
    ok = True
    for nome, ne, no, iguais, dif in comparar(esperado, obtido):
        out.append(f"| `{nome}` | {ne} | {no} | {'**SIM**' if iguais else '**NÃO**'} | {'' if iguais else str(dif)[:300]} |")
        if not iguais and nome != "verificacao":
            ok = False
    ks_i, ks_p = set(chaves_snapshot(ci).values()), set(chaves_snapshot(cp).values())
    out += ["", f"Snapshots: {len(ks_i)} na investigação, {len(ks_p)} na produção, **{len(ks_i & ks_p)} pareados por conteúdo**.", ""]

    # casos relevantes, lado a lado
    def val(con, did, sql, *p):
        return con.execute(sql, (did,) + p).fetchall()
    casos = [
        ("11963/2016, corte 2026 (01/01–31/12): categoria, S1, cancel. processado",
         "SELECT d.categoria, d.s1_saldo_total_c, d.cancel_processado_c FROM rp_derivado d JOIN coleta c ON c.id=d.coleta_id "
         "WHERE d.derivacao_id=? AND d.anoempenho=2016 AND d.empenho=11963 AND c.data_final='2026-12-31' AND c.tipo_pesquisa IS NULL", ()),
        ("5659/2025, corte 2026: S1, S3",
         "SELECT d.s1_saldo_total_c, d.s3_liquidado_a_pagar_c FROM rp_derivado d JOIN coleta c ON c.id=d.coleta_id "
         "WHERE d.derivacao_id=? AND d.anoempenho=2025 AND d.empenho=5659 AND c.data_final='2026-12-31' AND c.tipo_pesquisa IS NULL", ()),
        ("Pares 2025 por relação × lado com execução",
         "SELECT relacao_inscricao, lado_com_execucao, COUNT(*) FROM espelhamento_par WHERE derivacao_id=? AND exercicio=2025 GROUP BY 1,2 ORDER BY 1,2", ()),
        ("Pares 2026 por lado com execução",
         "SELECT lado_com_execucao, COUNT(*) FROM espelhamento_par WHERE derivacao_id=? AND exercicio=2026 GROUP BY 1 ORDER BY 1", ()),
        ("Conciliação 4º bim/2026, entidade, RREO-COL v1: h, i",
         "SELECT c.coluna, c.diferenca_c FROM conciliacao_rreo c JOIN regra g ON g.id=c.regra_agregacao_id WHERE c.derivacao_id=? "
         "AND c.escopo='entidade' AND c.data_final='2026-08-31' AND g.versao=1 AND c.coluna IN ('h','i') ORDER BY 1", ()),
        ("Conciliação 2025 consolidado, RREO-COL v2: colunas ≠ 0",
         "SELECT c.coluna, c.diferenca_c FROM conciliacao_rreo c JOIN regra g ON g.id=c.regra_agregacao_id WHERE c.derivacao_id=? "
         "AND c.escopo='consolidado' AND c.exercicio=2025 AND g.versao=2 AND c.diferenca_c<>0 ORDER BY 1", ()),
        ("Visão analítica 2025, RREO-COL v2 × CONS-PAR v2: g, L",
         "SELECT v.componente, v.valor_c FROM visao_valor v JOIN regra g ON g.id=v.regra_agregacao_id JOIN regra r ON r.id=v.regra_consolidacao_id "
         "WHERE v.derivacao_id=? AND v.visao='analitico' AND v.exercicio=2025 AND g.versao=2 AND r.versao=2 AND v.componente IN ('g','L') ORDER BY 1", ()),
        ("Anomalias por tipo (todas)",
         "SELECT tipo, COUNT(*) FROM anomalia WHERE derivacao_id=? GROUP BY 1 ORDER BY 1", ()),
    ]
    out += ["## 2. Casos relevantes: esperado × obtido", "", "| Caso | Esperado (investigação) | Obtido (produção) | Igual? |", "|---|---|---|---|"]
    for nome, sql, p in casos:
        e, o = val(ci, di, sql, *p), val(cp, dp, sql, *p)
        ok &= e == o
        out.append(f"| {nome} | `{e}` | `{o}` | {'**SIM**' if e == o else '**NÃO**'} |")

    # snapshots reais da 04.1 (banco ativo) x investigacao, mesmos bytes
    if banco_ativo:
        import sqlite3
        ca = sqlite3.connect(banco_ativo)
        na = ca.execute("SELECT MAX(id) FROM normalizacao_execucao").fetchone()[0]
        da = ca.execute("SELECT MAX(id) FROM derivacao_execucao WHERE normalizacao_id=?", (na,)).fetchone()[0]
        real = tabelas(ca, na, da)
        # a listagem real (04.1) tem os MESMOS bytes da recoleta da Etapa 02: comparar registro a registro
        Kr = chaves_snapshot(ca)
        lst = [k for k in Kr.values() if k[0] == "rp_listagem"]
        out += ["", "## 3. Snapshots reais da 04.1 (banco ativo) × investigação", ""]
        for k in lst:
            par = [ki for ki in ks_i if ki[0] == k[0] and ki[2] == k[2]]
            out.append(f"- Listagem real coletada em {k[1]}: bytes idênticos a {len(par)} snapshot(s) da investigação "
                       f"({', '.join(p[1] for p in sorted(par))}).")
            for p in par:
                for tab in ("rp_registro", "rp_derivado"):
                    er = {(o, i): v for ((sk, o), i), v in esperado[tab].items() if sk == p}
                    rr = {(o, i): v for ((sk, o), i), v in real[tab].items() if sk == k}
                    igual = er == rr
                    ok &= igual
                    out.append(f"  - `{tab}` do snapshot real × snapshot de {p[1]}: {len(rr)} × {len(er)} linhas, "
                               f"**{'idênticas' if igual else 'DIFERENTES'}**")
        cr = {(k[0][0], k[1], k[2]): v[:7] for k, v in real["conciliacao_rreo"].items()}
        ce = {(k[0][0], k[1], k[2]): v[:7] for k, v in esperado["conciliacao_rreo"].items()
              if k[0][2] in {kk[2] for kk in Kr.values() if kk[0] == "rreo_pdf"}}
        out.append(f"- Conciliação do PDF real (4º bim/2026, entidade) × investigação: {len(cr)} × {len(ce)} linhas "
                   f"(2 regras × 12 colunas), **{'idênticas' if cr == ce else 'DIFERENTES'}**.")
        ok &= cr == ce
    out += ["", f"## Resultado: {'**ESPERADO == OBTIDO**' if ok else '**HÁ DIFERENÇAS**'}", ""]
    texto = "\n".join(out)
    print(texto)
    return ok, texto


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")   # saida em cp1252 (arquivo) nao derruba o script
    ok, texto = main(*sys.argv[1:3])
    Path(RAIZ / "etapa04" / "resultados" / "04_2_reconciliacao.md").write_text(texto + "\n", encoding="utf-8")
    sys.exit(0 if ok else 1)
