"""Snapshot of the state for the corrective review gates (read-only). Usage: python estado.py <saida.json>"""
import hashlib, json, sqlite3, subprocess, sys
from pathlib import Path
RAIZ = Path("C:/Users/maped/OneDrive/Área de Trabalho/Projeto Dashboard Restos a Pagar")
BANCO = "C:/Users/maped/RestosAPagar_local/banco/restos_a_pagar.sqlite"
con = sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True)
def h_tabela(sql):
    h = hashlib.sha256()
    for row in con.execute(sql):
        h.update(repr(row).encode())
    return h.hexdigest()
e = {"git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=RAIZ, capture_output=True, text=True).stdout.strip()}
e["bruto"] = {t: h_tabela(f"SELECT * FROM {t} ORDER BY 1") for t in ("coleta", "resposta_bruta", "objeto_bruto", "coletor_versao")}
e["contagens"] = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("coleta", "resposta_bruta", "objeto_bruto", "coletor_versao", "evidencia_externa")}
e["esquema_versao"] = con.execute("SELECT versao, descricao FROM esquema_versao ORDER BY versao").fetchall()
arq = lambda base: {p.relative_to(RAIZ).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((RAIZ / base).rglob("*")) if p.is_file()}
e["armazem_manifestos"] = arq("snapshots/coletas")
e["armazem_objetos"] = arq("snapshots/objetos")
e["dados_brutos_etapas"] = {**arq("data/stage01-samples"), **arq("data/stage02-raw")}
e["derivacoes"] = con.execute("SELECT id, normalizacao_id, vigencia_em, hash_resultado FROM derivacao_execucao ORDER BY id").fetchall()
for did, _, vig, _ in e["derivacoes"]:
    chave = f"derivacao_{did}_{vig or 'atual'}"
    e[chave] = {"visao_valor": h_tabela(f"SELECT visao, regra_agregacao_id, IFNULL(regra_consolidacao_id,0), IFNULL(entidade,0), exercicio, data_final, coletas_json, componente, valor_c FROM visao_valor WHERE derivacao_id={did} ORDER BY 1,2,3,4,5,6,7,8"),
                "conciliacao_rreo": h_tabela(f"SELECT rreo_coleta_id, regra_agregacao_id, escopo, IFNULL(entidade,0), exercicio, data_final, coluna, valor_rreo_c, valor_api_c, diferenca_c FROM conciliacao_rreo WHERE derivacao_id={did} ORDER BY 1,2,3,4,5,6,7")}
Path(sys.argv[1]).write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")
print({k: (v if not isinstance(v, dict) or len(v) < 8 else f"{len(v)} itens") for k, v in e.items()})
