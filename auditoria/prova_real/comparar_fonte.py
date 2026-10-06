"""Prova real (05/10/2026), passo 2: compara o banco ativo com a fonte, em tres niveis, so lendo.

  N2  API hoje x bruto gravado: para cada corte, o snapshot que o painel usa (banco ativo) contra a recoleta feita
      agora no armazem temporario. Registros que faltam, que surgiram e campos diferentes, campo a campo.
  N3  bruto gravado x banco: cada registro do snapshot usado contra a linha de rp_registro da normalizacao atual
      (mapeamento refeito aqui, independente de normalizar.py).
  N4  bruto x tela: os 14 indicadores que o painel mostra contra o recalculo independente (tests/recalculo_bruto.py)
      do bruto gravado e do bruto de hoje.
Tambem: movimentacoes (lancamentos), catalogos (entidades e exercicios) e PDFs do RREO (bytes, por idArquivo).

Nenhum nome, documento ou descricao sai no relatorio: so chaves de empenho, nomes de campo e valores em centavos.
Uso (dentro de app/): python ../auditoria/prova_real/comparar_fonte.py --temp C:/rpaud/prova --saida ARQ.json
"""
import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / "tests"))

import recalculo_bruto as rb               # noqa: E402
from rp.armazem import Armazem             # noqa: E402
from rp.painel import Painel               # noqa: E402

ATIVO = Path.home() / "RestosAPagar_local" / "banco" / "restos_a_pagar.sqlite"
ARMAZEM_ATIVO = APP.parent / "snapshots"
NORMALIZACAO = 13   # normalizacao da derivacao atual (23) do banco ativo

# coluna de rp_registro -> chave da API (refeito aqui de proposito; ver docstring)
TEXTO = {"entidade": "entidade", "anoempenho": "anoempenho", "empenho": "empenho",
         "empenho_exercicio": "empenhoExercicio", "data_emissao": "dataEmissao", "programatica": "programatica",
         "fonte_recurso": "fonteRecurso", "descricao_fonte": "descricaoFonte", "fornecedor": "fornecedor",
         "nome": "nome", "cnpj": "cnpj", "cnpj_nome": "cnpjNome", "orgao": "orgao", "unidade": "unidade",
         "funcao": "funcao", "sub_funcao": "subFuncao", "programa": "programa", "projeto": "projeto",
         "elemento": "elemento", "desdobra_desp": "desdobraDesp", "sub_desdobramento": "subDesdobramento"}
DINHEIRO = {"proc_c": "proc", "aproc_c": "aproc", "cancelado_proc_c": "canceladoProc", "pago_proc_c": "pagoProc",
            "pago_proc_estornado_c": "pagoProcEstornado", "cancelado_aproc_c": "canceladoAProc",
            "pago_aproc_c": "pagoAProc", "pago_aproc_estornado_c": "pagoAProcEstornado", "liquidado_c": "liquidado",
            "retencao_c": "retencao"}
MONETARIOS_API = set(DINHEIRO.values())


def ro(caminho):
    con = sqlite3.connect(f"file:{Path(caminho).as_posix()}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=1")
    return con


def corpos(con, armazem, coleta_id):
    rows = con.execute("SELECT ordem, sha256, tamanho FROM resposta_bruta WHERE coleta_id=? ORDER BY ordem",
                       (coleta_id,)).fetchall()
    return [(o, armazem.ler_objeto(h, t)) for o, h, t in rows]


def itens(con, armazem, coleta_id):
    """[(ordem, indice, item)] de um snapshot de listagem, lidos do armazem (Decimal para numeros)."""
    saida = []
    for o, b in corpos(con, armazem, coleta_id):
        d = json.loads(b, parse_float=Decimal)
        for i, r in enumerate(d.get("content") or []):
            saida.append((o, i, r))
    return saida


def chave(r):
    return (r.get("entidade"), r.get("anoempenho"), r.get("empenho"))


def coleta_id(con, uid):
    return con.execute("SELECT id FROM coleta WHERE snapshot_uid=?", (uid,)).fetchone()[0]


def ultima_coleta(con, tipo, **p):
    where = " AND ".join(f"{k}=?" for k in p)
    return con.execute(f"SELECT id, snapshot_uid, coletada_em, status, observacao FROM coleta WHERE tipo=? AND {where} "
                       f"AND (tipo_pesquisa IS NULL) ORDER BY coletada_em DESC, id DESC LIMIT 1",
                       (tipo, *p.values())).fetchone()


def iguais(a, b):
    if isinstance(a, (int, Decimal, float)) and isinstance(b, (int, Decimal, float)) and not isinstance(a, bool):
        return Decimal(str(a)) == Decimal(str(b))
    return a == b


def centavos_api(v):
    return rb.centavos(v)


# ------------------------------------------------------------------ N3: bruto gravado x banco
def bruto_x_banco(con, cid, brutos):
    cols = list(TEXTO) + list(DINHEIRO)
    linhas = {(o, i): row for o, i, *row in con.execute(
        f"SELECT rb.ordem, r.indice, {', '.join('r.' + c for c in cols)} FROM rp_registro r "
        "JOIN resposta_bruta rb ON rb.id = r.resposta_id WHERE r.normalizacao_id=? AND r.coleta_id=?", (NORMALIZACAO, cid))}
    problemas = Counter()
    exemplos = []
    if len(linhas) != len(brutos):
        problemas["contagem"] += 1
    for o, i, r in brutos:
        row = linhas.get((o, i))
        if row is None:
            problemas["registro_sem_linha_no_banco"] += 1
            continue
        v = dict(zip(cols, row))
        for col, api in TEXTO.items():
            if not iguais(v[col], r.get(api)):
                problemas[f"campo:{col}"] += 1
                if len(exemplos) < 5:
                    exemplos.append({"chave": chave(r), "campo": col})
        for col, api in DINHEIRO.items():
            if v[col] != centavos_api(r.get(api)):
                problemas[f"campo:{col}"] += 1
                if len(exemplos) < 5:
                    exemplos.append({"chave": chave(r), "campo": col, "banco_c": v[col], "bruto_c": centavos_api(r.get(api))})
    return {"registros_bruto": len(brutos), "linhas_banco": len(linhas), "problemas": dict(problemas),
            "exemplos": exemplos}


# ------------------------------------------------------------------ N2: bruto gravado x API hoje
def antes_x_hoje(antes, hoje):
    a = {chave(r): r for _, _, r in antes}
    b = {chave(r): r for _, _, r in hoje}
    faltam = sorted(set(a) - set(b))
    surgiram = sorted(set(b) - set(a))
    campos = Counter()
    mudancas = []
    for k in sorted(set(a) & set(b)):
        ra, rb_ = a[k], b[k]
        dif = [c for c in sorted(set(ra) | set(rb_)) if not iguais(ra.get(c), rb_.get(c))]
        if dif:
            for c in dif:
                campos[c] += 1
            mudancas.append({"chave": k, "campos": dif,
                             "monetarios_c": {c: [centavos_api(ra.get(c)), centavos_api(rb_.get(c))]
                                              for c in dif if c in MONETARIOS_API}})
    return {"registros_antes": len(a), "registros_hoje": len(b), "faltam_hoje": faltam, "surgiram_hoje": surgiram,
            "registros_alterados": len(mudancas), "campos_alterados": dict(campos), "alteracoes": mudancas,
            "duplicadas_antes": len(antes) - len(a), "duplicadas_hoje": len(hoje) - len(b)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--temp", required=True)
    ap.add_argument("--saida", required=True)
    a = ap.parse_args()
    temp = Path(a.temp)
    con_a, con_t = ro(ATIVO), ro(temp / "local" / "banco" / "restos_a_pagar.sqlite")
    arm_a, arm_t = Armazem(ARMAZEM_ATIVO), Armazem(temp / "snapshots")
    painel = Painel(con_a)

    cortes = con_a.execute("SELECT DISTINCT entidade, exercicio, data_final FROM visao_valor WHERE derivacao_id=23 "
                           "AND visao='entidade' ORDER BY 2, 3, 1").fetchall()
    rel = {"cortes": [], "movimentacoes": [], "catalogos": {}, "rreo_pdf": []}
    for ent, ex, df in cortes:
        p = painel.indicadores(ex, df, ent)
        e = p["entidades"][0]
        uid = (e.get("snapshot") or {}).get("snapshot_uid")
        item = {"entidade": ent, "exercicio": ex, "data_final": df, "situacao_painel": e["situacao_do_dado"]["codigo"],
                "snapshot_usado": uid}
        valores_tela = {k: v["valor_c"] for k, v in p["valores"].items()} if p["disponivel"] else None
        novo = ultima_coleta(con_t, "rp_listagem", entidade=ent, exercicio=ex, data_final=df)
        item["recoleta"] = {"snapshot": novo[1], "coletada_em": novo[2], "status": novo[3], "observacao": novo[4]} if novo else None
        antes = itens(con_a, arm_a, coleta_id(con_a, uid)) if uid else []
        hoje = itens(con_t, arm_t, novo[0]) if novo and novo[3] == "completa" else None
        if uid:
            item["N3_bruto_x_banco"] = bruto_x_banco(con_a, coleta_id(con_a, uid), antes)
            calc = rb.indicadores([r for _, _, r in antes])
            item["N4_tela_x_recalculo_do_bruto"] = {k: [valores_tela.get(k), calc[k]] for k in calc
                                                    if valores_tela and valores_tela.get(k) != calc[k]}
        if hoje is not None:
            item["N2_antes_x_hoje"] = antes_x_hoje(antes, hoje)
            calc_h = rb.indicadores([r for _, _, r in hoje])
            item["N4_tela_x_api_hoje"] = {k: [valores_tela.get(k) if valores_tela else None, calc_h[k]] for k in calc_h
                                          if not valores_tela or valores_tela.get(k) != calc_h[k]}
        rel["cortes"].append(item)

    # movimentacoes: lancamentos do snapshot mais recente de cada empenho, antes x hoje
    for ent, ano, emp in con_a.execute("SELECT DISTINCT entidade, anoempenho, empenho FROM coleta WHERE tipo='movimentacao' "
                                       "AND status='completa' ORDER BY 1, 2, 3").fetchall():
        va = ultima_coleta(con_a, "movimentacao", entidade=ent, anoempenho=ano, empenho=emp)
        vt = ultima_coleta(con_t, "movimentacao", entidade=ent, anoempenho=ano, empenho=emp)

        def lanc(con, arm, c):
            out = []
            for _, b in corpos(con, arm, c[0]):
                d = json.loads(b, parse_float=Decimal)
                out += d.get("content") if isinstance(d, dict) else d
            return out
        la = lanc(con_a, arm_a, va)
        lt = lanc(con_t, arm_t, vt) if vt and vt[3] == "completa" else None
        def norm(ls):
            return sorted(json.dumps(x, sort_keys=True, default=str) for x in ls)
        rel["movimentacoes"].append({"chave": [ent, ano, emp], "lancamentos_antes": len(la),
                                     "lancamentos_hoje": None if lt is None else len(lt),
                                     "iguais": None if lt is None else norm(la) == norm(lt),
                                     "status_hoje": vt[3] if vt else None})

    # catalogos: conteudo do snapshot mais recente, antes x hoje
    def cat(con, arm, tipo, endpoint):
        c = con.execute("SELECT id FROM coleta WHERE tipo=? AND endpoint=? AND status='completa' "
                        "ORDER BY coletada_em DESC LIMIT 1", (tipo, endpoint)).fetchone()
        return json.loads(corpos(con, arm, c[0])[0][1]) if c else None
    for tipo, ep in con_a.execute("SELECT DISTINCT tipo, endpoint FROM coleta WHERE tipo IN ('entidades','exercicios')"):
        x, y = cat(con_a, arm_a, tipo, ep), cat(con_t, arm_t, tipo, ep)
        rel["catalogos"][ep] = {"iguais": x == y, "itens_antes": len(x or []), "itens_hoje": len(y or []),
                                "so_antes": [i for i in (x or []) if i not in (y or [])],
                                "so_hoje": [i for i in (y or []) if i not in (x or [])]}

    # PDFs do RREO: mesmos bytes pelo idArquivo?
    for (ida,) in con_a.execute("SELECT DISTINCT id_arquivo FROM coleta WHERE tipo='rreo_pdf' ORDER BY 1"):
        ha = {r[0] for r in con_a.execute("SELECT r.sha256 FROM resposta_bruta r JOIN coleta c ON c.id=r.coleta_id "
                                          "WHERE c.tipo='rreo_pdf' AND c.id_arquivo=?", (ida,))}
        ht = {r[0] for r in con_t.execute("SELECT r.sha256 FROM resposta_bruta r JOIN coleta c ON c.id=r.coleta_id "
                                          "WHERE c.tipo='rreo_pdf' AND c.id_arquivo=? AND c.status='completa'", (ida,))}
        rel["rreo_pdf"].append({"id_arquivo": ida, "baixado_hoje": bool(ht), "mesmos_bytes": bool(ht) and ht <= ha})

    # resumo
    cs = rel["cortes"]
    n2 = [c["N2_antes_x_hoje"] for c in cs if "N2_antes_x_hoje" in c]
    resumo = {
        "cortes": len(cs),
        "cortes_recoletados_completos": len(n2),
        "N3_cortes_com_problema_bruto_x_banco": sum(1 for c in cs if c.get("N3_bruto_x_banco", {}).get("problemas")),
        "N3_registros_conferidos": sum(c.get("N3_bruto_x_banco", {}).get("registros_bruto", 0) for c in cs),
        "N4_cortes_tela_diferente_do_recalculo": sum(1 for c in cs if c.get("N4_tela_x_recalculo_do_bruto")),
        "N2_cortes_identicos_hoje": sum(1 for x in n2 if not (x["faltam_hoje"] or x["surgiram_hoje"] or x["registros_alterados"])),
        "N2_registros_antes": sum(x["registros_antes"] for x in n2),
        "N2_registros_hoje": sum(x["registros_hoje"] for x in n2),
        "N2_faltam_hoje": sum(len(x["faltam_hoje"]) for x in n2),
        "N2_surgiram_hoje": sum(len(x["surgiram_hoje"]) for x in n2),
        "N2_registros_alterados": sum(x["registros_alterados"] for x in n2),
        "N2_campos_alterados": dict(sum((Counter(x["campos_alterados"]) for x in n2), Counter())),
        "N4_cortes_tela_diferente_da_api_hoje": sum(1 for c in cs if c.get("N4_tela_x_api_hoje")),
        "movimentacoes": len(rel["movimentacoes"]),
        "movimentacoes_iguais": sum(1 for m in rel["movimentacoes"] if m["iguais"]),
        "catalogos_iguais": sum(1 for v in rel["catalogos"].values() if v["iguais"]),
        "catalogos": len(rel["catalogos"]),
        "rreo_pdf": len(rel["rreo_pdf"]),
        "rreo_pdf_mesmos_bytes": sum(1 for r in rel["rreo_pdf"] if r["mesmos_bytes"]),
    }
    rel = {"resumo": resumo, **rel}
    Path(a.saida).write_text(json.dumps(rel, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(resumo, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
