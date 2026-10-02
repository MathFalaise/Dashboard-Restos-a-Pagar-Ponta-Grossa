"""Retrato do estado para os portoes da 04.6 (somente leitura).

Uso (dentro de app/):  python ../etapa04/resultados/04_6_estado.py SAIDA.json [--banco CAMINHO]

Sem caminho fixo: o banco vem de --banco ou do config.toml (RP_CONFIG / RP_DADOS_LOCAIS), o armazem do config.
Registra:
  * git HEAD; hash da camada bruta (execucoes.hash_camada0) e de cada tabela do bruto; contagens;
  * PRAGMA integrity_check; versoes do esquema; derivacoes com hash_resultado e hashes de visao/conciliacao;
  * SHA-256 de cada manifesto e objeto do armazem (snapshots/);
  * valores da camada painel: indicadores de todo corte (Municipio e cada entidade), entidades do corte,
    reconciliacao, coerencia e pares;
  * valores exibidos pela interface: todo <data id=... value=...> das telas de cada corte (sem servidor: WSGI direto).
"""
import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "app"))

from rp import execucoes  # noqa: E402
from rp.config import carregar  # noqa: E402
from rp.interface.aplicacao import Aplicacao  # noqa: E402
from rp.painel import Painel  # noqa: E402

_DATA = re.compile(r'<data class="[^"]*" id="([^"]+)" value="(-?\d+)">')


def h_tabela(con, sql):
    h = hashlib.sha256()
    for row in con.execute(sql):
        h.update(repr(row).encode())
    return h.hexdigest()


def arquivos(base):
    return {p.relative_to(RAIZ).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(base.rglob("*")) if p.is_file()}


def pagina(app, caminho, **q):
    from urllib.parse import urlencode
    status = []
    corpo = b"".join(app({"REQUEST_METHOD": "GET", "PATH_INFO": caminho,
                          "QUERY_STRING": urlencode({k: v for k, v in q.items() if v is not None})},
                         lambda s, h: status.append(s)))
    return status[0], corpo.decode("utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("saida")
    ap.add_argument("--banco")
    a = ap.parse_args()
    cfg = carregar()
    banco = Path(a.banco) if a.banco else cfg.banco
    con = sqlite3.connect(f"{banco.resolve().as_uri()}?mode=ro", uri=True)
    e = {"git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=RAIZ, capture_output=True, text=True).stdout.strip()}
    e["integrity_check"] = con.execute("PRAGMA integrity_check").fetchall()
    e["hash_camada0"] = execucoes.hash_camada0(con)
    e["bruto"] = {t: h_tabela(con, f"SELECT * FROM {t} ORDER BY 1")
                  for t in ("coleta", "resposta_bruta", "objeto_bruto", "coletor_versao")}
    e["contagens"] = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                      for t in ("coleta", "resposta_bruta", "objeto_bruto", "coletor_versao", "evidencia_externa",
                                "normalizacao_execucao", "derivacao_execucao", "regra", "regra_situacao")}
    e["esquema_versao"] = [v for (v,) in con.execute("SELECT versao FROM esquema_versao ORDER BY versao")]
    e["derivacoes"] = con.execute("SELECT id, normalizacao_id, vigencia_em, hash_resultado FROM derivacao_execucao "
                                  "ORDER BY id").fetchall()
    for did, _, vig, _ in e["derivacoes"]:
        e[f"derivacao_{did}"] = {
            "visao_valor": h_tabela(con, f"SELECT visao, regra_agregacao_id, IFNULL(regra_consolidacao_id,0), "
                                         f"IFNULL(entidade,0), exercicio, data_final, coletas_json, componente, valor_c "
                                         f"FROM visao_valor WHERE derivacao_id={did} ORDER BY 1,2,3,4,5,6,7,8"),
            "conciliacao_rreo": h_tabela(con, f"SELECT rreo_coleta_id, regra_agregacao_id, escopo, IFNULL(entidade,0), "
                                              f"exercicio, data_final, coluna, valor_rreo_c, valor_api_c, diferenca_c "
                                              f"FROM conciliacao_rreo WHERE derivacao_id={did} ORDER BY 1,2,3,4,5,6,7")}
    e["regra_situacao"] = h_tabela(con, "SELECT * FROM regra_situacao ORDER BY 1")
    con.close()
    e["armazem_manifestos"] = arquivos(cfg.snapshots / "coletas")
    e["armazem_objetos"] = arquivos(cfg.snapshots / "objetos")

    painel, tela = {}, {}
    app = Aplicacao(banco)
    with Painel.abrir(banco) as p:
        cortes = p.cortes()["cortes"]
        ents = [x["entidade"] for x in p.entidades()["entidades"]]
        for c in cortes:
            ex, df = c["exercicio"], c["data_final"]
            for ent in [None] + ents:
                r = p.indicadores(ex, df, ent)
                painel[f"indicadores|{ex}|{df}|{ent}"] = {
                    "disponivel": r["disponivel"], "motivo": r["motivo_indisponivel"],
                    "retrato": r["retrato"] and r["retrato"]["texto"],
                    "valores": {k: v["valor_c"] for k, v in r["valores"].items()},
                    "conferencia": r["conferencia_rreo"] and {k: r["conferencia_rreo"][k] for k in
                                                              ("diferenca_c", "situacao_da_diferenca")}}
                _, html = pagina(app, "/", exercicio=ex, data_final=df, entidade=ent)
                tela[f"resumo|{ex}|{df}|{ent}"] = dict(_DATA.findall(html))
            d = p.entidades_do_corte(ex, df)
            painel[f"entidades|{ex}|{df}"] = [
                {"entidade": l["entidade"], "situacao": l["situacao_do_valor"],
                 "valores": l["valores"] and {k: v for k, v in l["valores"].items() if k not in ("natureza", "regras")}}
                for l in d["linhas"]]
            _, html = pagina(app, "/entidades", exercicio=ex, data_final=df)
            tela[f"entidades|{ex}|{df}"] = dict(_DATA.findall(html))
            pr = p.pares(ex, df)
            painel[f"pares|{ex}|{df}"] = pr.get("resumo")
        rec = p.reconciliacao()
        painel["reconciliacao"] = [[x["exercicio"], x["data_final"], x["escopo"], x["regra_agregacao"]["regra"],
                                    x["coluna"], x["api_c"], x["rreo_c"], x["diferenca_c"], x["situacao_da_diferenca"]]
                                   for x in rec["linhas"]]
        painel["coerencia"] = [[x["escopo"], x["de"], x["data_final_para"], x["rreo_L_de_c"], x["rreo_a_mais_f_para_c"],
                                x["diferenca_c"], x["api_s1_de_c"], x["api_a_mais_f_para_c"], x["situacao_da_diferenca"]]
                               for x in p.coerencia_entre_publicacoes()["comparacoes"]]
        for d in p.documentos_rreo()["documentos"]:
            _, html = pagina(app, "/reconciliacao", exercicio=d["exercicio"], data_final=d["data_final"],
                             escopo=d["escopo"])
            tela[f"reconciliacao|{d['exercicio']}|{d['data_final']}|{d['escopo']}"] = dict(_DATA.findall(html))
        _, html = pagina(app, "/reconciliacao")
        tela["reconciliacao|indice"] = dict(_DATA.findall(html))
    e["cortes"] = [[c["exercicio"], c["data_final"], c["municipio_disponivel"]] for c in cortes]
    e["painel"] = painel
    e["painel_sha256"] = hashlib.sha256(json.dumps(painel, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    e["tela"] = tela
    Path(a.saida).write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: (v if not isinstance(v, (dict, list)) or len(v) < 6 else f"{len(v)} itens")
                      for k, v in e.items()}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
