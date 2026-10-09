"""Single homologation command for making a load available (correction request of 09/10/2026, item 9).

It reads the active database (read-only) and the store, and runs, in this order:
  1. the gates (portoes.avaliar): SQLite integrity, relations, store x database (verificar), complete collection and
     normalization, derivation of the current normalization, recomputed hashes, no impeding repeated key, no refused
     money field, collection times, provenance, identification of the runs, schema;
  2. the integrity reference of the raw layer BEFORE the load: the gate reference (--referencia, gravar-referencia)
     and/or the root manifest kept outside (--raiz); at least one is mandatory;
  3. deterministic reproduction: a NEW database built from the store alone in a temporary folder, normalized and
     derived for every validity of the active database, compared layer by layer (equivalencia);
  4. the production tests (app/tests) and the investigation tests (docs/stages/03-data-model/validation);
  5. accounting pendencies, which never fail the technical approval but keep it from being "without caveats":
     reconciliation differences with the RREO, RREO documents not transcribed, mirrored pairs whose nature is not
     determined, rules in use without a governance decision.

Result, never stronger than what was run:
  reprovada               some executed technical check failed;
  incompleta              no technical failure, but a mandatory check was not executed (listed): NOT homologated;
  aprovada_com_ressalvas  technical approval: every mandatory check executed and passed; accounting pendencies remain;
  aprovada_sem_ressalvas  technical approval and no pendency.
Nothing is written to the active database or the store; the reproduction lives in a temporary folder.
"""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import agora, banco, equivalencia, governanca, hash_do_codigo, portoes, proveniencia

RAIZ_APP = Path(__file__).resolve().parents[1]
SUITES = {"producao": (RAIZ_APP, ["tests"]),
          "investigacao": (RAIZ_APP.parent / "docs" / "stages" / "03-data-model" / "validation", ["tests"])}
CODIGO_DE_SAIDA = {"aprovada_sem_ressalvas": 0, "reprovada": 1, "incompleta": 2, "aprovada_com_ressalvas": 3}


def _verif(ident, descricao, ok, detalhe, obrigatoria=True):
    """ok: True / False / None (not executed)."""
    return {"id": ident, "descricao": descricao, "obrigatoria": obrigatoria, "executada": ok is not None, "ok": ok,
            "detalhe": detalhe}


def rodar_testes(nome, pasta, args, timeout=3600):
    """Runs one pytest suite in a separate process; the summary line and the return code are the evidence."""
    t = time.time()
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args], cwd=pasta,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return _verif(f"testes_{nome}", f"suíte de testes '{nome}' ({pasta})", False,
                      {"erro": f"{type(e).__name__}: {e}"})
    linhas = [x for x in r.stdout.strip().splitlines() if x.strip()]
    resumo = linhas[-1] if linhas else ""
    return _verif(f"testes_{nome}", f"suíte de testes '{nome}' executada e aprovada", r.returncode == 0,
                  {"comando": f"python -m pytest -q {' '.join(args)}", "pasta": str(pasta), "codigo": r.returncode,
                   "resumo": resumo, "segundos": round(time.time() - t, 1),
                   "falhas": [x for x in linhas if x.startswith(("FAILED", "ERROR"))][:20]})


def reproduzir(cfg, armazem, con_ativo, pasta):
    """New database from the store alone, processed for every validity of the active one, compared layer by layer."""
    from . import derivar, normalizar
    from .config import carregar
    t = time.time()
    destino = Path(pasta) / "reproducao.sqlite"
    cfg_tmp = carregar(dados_locais=Path(pasta) / "dl", snapshots=cfg.snapshots, backups=Path(pasta) / "bk")
    con, _ = banco.reconstruir(cfg_tmp, armazem, destino)
    try:
        nid, _ = normalizar.normalizar(con)
        vigencias = [v for (v,) in con_ativo.execute("SELECT DISTINCT vigencia_em FROM derivacao_execucao")]
        for em in sorted(vigencias, key=lambda v: (v is not None, v or "")):
            derivar.derivar(con, nid, em)
        con.commit()
        r = equivalencia.comparar(con_ativo, con)
    finally:
        con.close()
    a, b = r["a"]["normalizacao"] or {}, r["b"]["normalizacao"] or {}
    ok = (r["camada0_igual"] and all(v is not False for v in r["complementos_camada0_iguais"].values())
          and all(r["normalizacao_por_tabela"].values()) and all(r["derivacao_igual_por_vigencia"].values())
          and r["hash_gravado_confere_nos_dois"])
    return _verif("reproducao_deterministica", "um banco novo construído só do armazém, normalizado e derivado pelo "
                  "código atual, é igual ao ativo camada a camada (bruto, tempos, manifestos, normalização e cada "
                  "vigência)", ok,
                  {"camada0_igual": r["camada0_igual"], "complementos_camada0": r["complementos_camada0_iguais"],
                   "normalizacao_por_tabela": r["normalizacao_por_tabela"],
                   "normalizador": {"ativo": a.get("normalizador_versao"), "reproducao": b.get("normalizador_versao")},
                   "derivacao_igual_por_vigencia": r["derivacao_igual_por_vigencia"],
                   "hashes": {v: d["hash_recalculado"] for v, d in r["b"]["derivacoes"].items()},
                   "segundos": round(time.time() - t, 1)})


def pendencias_contabeis(con):
    """Accounting and governance pendencies of the current derivation: shown, never a technical failure."""
    did = con.execute("SELECT MAX(id) FROM derivacao_execucao WHERE vigencia_em IS NULL").fetchone()[0]
    nid = con.execute("SELECT normalizacao_id FROM derivacao_execucao WHERE id=?", (did,)).fetchone()[0] if did else None
    saida = []
    if did:
        dif = con.execute(
            "SELECT g.codigo || ' v' || g.versao, COUNT(*), COUNT(DISTINCT c.rreo_coleta_id) FROM conciliacao_rreo c JOIN "
            "regra g ON g.id = c.regra_agregacao_id WHERE c.derivacao_id=? AND c.diferenca_c <> 0 GROUP BY 1 ORDER BY 1",
            (did,)).fetchall()
        if dif:
            saida.append({"tipo": "divergencia_rreo", "descricao": "colunas do RREO com diferença em relação à API "
                          "(a diferença é mostrada; o valor da API não muda)",
                          "por_regra_de_agregacao": {r: {"colunas": n, "documentos": d} for r, n, d in dif}})
        nao_lidos = con.execute("SELECT c.snapshot_uid, x.rotulo, x.erro FROM rreo_extracao x JOIN coleta c ON c.id = "
                                "x.coleta_id WHERE x.normalizacao_id=? AND x.erro IS NOT NULL ORDER BY c.snapshot_uid",
                                (nid,)).fetchall()
        if nao_lidos:
            saida.append({"tipo": "rreo_nao_transcrito", "descricao": "PDF do RREO Anexo VII sem transcrição (layout "
                          "desconhecido): sem conferência independente nesse documento",
                          "documentos": [{"snapshot": u[:8], "rotulo": r, "erro": e} for u, r, e in nao_lidos]})
        linhas, distintos = con.execute(
            "SELECT COUNT(*), COUNT(DISTINCT entidade_a || '/' || anoempenho_a || '/' || empenho_a) FROM espelhamento_par "
            "WHERE derivacao_id=?", (did,)).fetchone()
        if linhas:
            saida.append({"tipo": "pares_espelhados", "descricao": "pares entidade 1 x 15 (PAR-24) cuja natureza "
                          "contábil (duplicidade ou transferência) não está determinada; os dois lados entram nos "
                          "indicadores; consolidação só como visão experimental",
                          "empenhos_distintos_em_par": distintos, "linhas_de_par_somando_todos_os_cortes": linhas})
    em_uso = {tuple(json.loads(x)) for (x,) in con.execute("SELECT DISTINCT json_array(g.codigo, g.versao) FROM "
                                                             "derivacao_regra d JOIN regra g ON g.id = d.regra_id WHERE "
                                                             "d.derivacao_id=?", (did,))} if did and banco._tem_tabela(
        con, "derivacao_regra") else set()
    sem_decisao = sorted(f"{c} v{v}" for (c, v), item in governanca.situacao_atual(con).items()
                         if item["situacao"] is None and (c, v) in em_uso)
    if sem_decisao:
        saida.append({"tipo": "regra_sem_decisao", "descricao": "regra usada pela derivação sem decisão de governança "
                      "registrada (decidir-regra)", "regras": sem_decisao})
    return saida


def homologar(cfg, armazem, caminho_banco=None, referencia=None, raiz=None, executar_testes=True, reproduzir_=True,
              suites=None):
    """Homologation report (dict). `referencia` / `raiz`: dicts already read from their files (or None)."""
    caminho_banco = caminho_banco or cfg.banco
    inicio = time.time()
    verificacoes = []
    g = portoes.avaliar(caminho_banco, armazem, referencia)
    for p in g["portoes"]:
        if p["id"] == "testes":
            continue                          # replaced by the suites actually run below
        if p["id"] == "camada_bruta_preservada" and p["ok"] is None:
            continue                          # judged together with the root manifest below
        verificacoes.append(_verif(p["id"], p["descricao"], p["ok"], p["detalhe"]))
    con = portoes._abrir(caminho_banco)
    try:
        if raiz is not None:
            problemas = proveniencia.conferir_raiz(con, raiz)
            verificacoes.append(_verif("raiz_externa_confere", "o manifesto-raiz guardado fora do banco confere: nenhum "
                                       "snapshot, objeto ou resultado anterior mudou ou sumiu", not problemas,
                                       {"problemas": problemas[:20], "gerada_em": raiz.get("gerada_em")}))
        tem_referencia = referencia is not None or raiz is not None
        verificacoes.append(_verif("referencia_da_camada_bruta", "existe referência de integridade da camada bruta "
                                   "anterior à carga (--referencia e/ou --raiz)", True if tem_referencia else None,
                                   {"referencia": referencia is not None, "raiz": raiz is not None}))
        if reproduzir_:
            with tempfile.TemporaryDirectory(prefix="rp-homologar-") as pasta:
                verificacoes.append(reproduzir(cfg, armazem, con, pasta))
        else:
            verificacoes.append(_verif("reproducao_deterministica", "reprodução a partir do armazém", None,
                                       "não executada (--sem-reproducao)"))
        pendencias = pendencias_contabeis(con)
    finally:
        con.close()
    for nome, (pasta, args) in (suites or SUITES).items():
        if executar_testes:
            verificacoes.append(rodar_testes(nome, pasta, args))
        else:
            verificacoes.append(_verif(f"testes_{nome}", f"suíte de testes '{nome}'", None, "não executada (--sem-testes)"))

    falhas = [v["id"] for v in verificacoes if v["ok"] is False]
    nao_executadas = [v["id"] for v in verificacoes if v["obrigatoria"] and v["ok"] is None]
    if falhas:
        resultado = "reprovada"
    elif nao_executadas:
        resultado = "incompleta"
    elif pendencias:
        resultado = "aprovada_com_ressalvas"
    else:
        resultado = "aprovada_sem_ressalvas"
    return {"resultado": resultado, "codigo_de_saida": CODIGO_DE_SAIDA[resultado],
            "aprovacao_tecnica": not falhas and not nao_executadas,
            "aprovacao_sem_ressalvas": resultado == "aprovada_sem_ressalvas",
            "falhas": falhas, "nao_executadas": nao_executadas, "pendencias_contabeis": pendencias,
            "verificacoes": verificacoes, "banco": str(caminho_banco), "codigo": hash_do_codigo(),
            "executado_em": agora(), "segundos": round(time.time() - inicio, 1),
            "nota": ("'incompleta' não é homologação: alguma verificação obrigatória não foi executada. "
                     "'aprovada_com_ressalvas' é aprovação técnica com pendências contábeis abertas (listadas); nenhum "
                     "resultado deste comando afirma que a apuração está 100% correta.")}
