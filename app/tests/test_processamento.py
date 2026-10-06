"""Specific gates of stage 04.2 (production processing)."""
import hashlib
import json
from decimal import Decimal

from conftest import montar_producao

from rp import banco, derivar, normalizar
from rp.armazem import Armazem
from rp.config import carregar
from rp.snapshots import gravar_snapshot

MAPA = {"entidade": "entidade", "anoempenho": "anoempenho", "empenho": "empenho", "empenhoExercicio": "empenho_exercicio",
        "dataEmissao": "data_emissao", "programatica": "programatica", "fonteRecurso": "fonte_recurso",
        "descricaoFonte": "descricao_fonte", "fornecedor": "fornecedor", "nome": "nome", "cnpj": "cnpj",
        "cnpjNome": "cnpj_nome", "orgao": "orgao", "unidade": "unidade", "funcao": "funcao", "subFuncao": "sub_funcao",
        "programa": "programa", "projeto": "projeto", "elemento": "elemento", "desdobraDesp": "desdobra_desp",
        "subDesdobramento": "sub_desdobramento"}
DINHEIRO = {"proc": "proc_c", "aproc": "aproc_c", "canceladoProc": "cancelado_proc_c", "pagoProc": "pago_proc_c",
            "pagoProcEstornado": "pago_proc_estornado_c", "canceladoAProc": "cancelado_aproc_c", "pagoAProc": "pago_aproc_c",
            "pagoAProcEstornado": "pago_aproc_estornado_c", "liquidado": "liquidado_c", "retencao": "retencao_c"}


# ------------------------------------------------------------ 1. raw -> normalized
def test_fidelidade_campo_a_campo_de_todos_os_registros(producao):
    """No record lost or invented; each field equal to the raw data; exact money in cents; origin preserved."""
    con, nid = producao["con"], producao["nid"]
    cur = con.execute("SELECT * FROM rp_registro WHERE normalizacao_id=?", (nid,))
    nomes = [c[0] for c in cur.description]
    norm = {(r["resposta_id"], r["indice"]): r for r in (dict(zip(nomes, x)) for x in cur)}
    vistos = 0
    for rid, sha in con.execute("SELECT r.id, r.sha256 FROM resposta_bruta r JOIN coleta c ON c.id=r.coleta_id "
                                "WHERE c.tipo='rp_listagem'").fetchall():
        for i, bruto in enumerate(json.loads(banco.corpo(con, sha), parse_float=Decimal)["content"]):
            n = norm[(rid, i)]
            vistos += 1
            for k, col in MAPA.items():
                assert n[col] == bruto.get(k), (rid, i, k)
            for k, col in DINHEIRO.items():
                assert Decimal(n[col]) == Decimal(str(bruto[k])) * 100, (rid, i, k)
            assert json.loads(n["chaves_ausentes"]) == [k for k in normalizar.BASE + normalizar.OPCIONAIS if k not in bruto]
            assert (n["resposta_id"], n["indice"]) == (rid, i)
    assert vistos == len(norm) == 82988  # not one more, not one less


def _camada0(con, armazem):
    h = hashlib.sha256()
    for t in ("coleta", "resposta_bruta", "objeto_bruto", "coletor_versao", "esquema_versao"):
        for row in con.execute(f"SELECT * FROM {t} ORDER BY 1"):
            h.update(repr(row).encode())
    for p in sorted(armazem.raiz.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(armazem.raiz).as_posix().encode() + p.read_bytes())
    return h.hexdigest()


def test_processar_nao_altera_a_camada_bruta(producao):
    antes = _camada0(producao["con"], producao["armazem"])
    nid, _ = normalizar.normalizar(producao["con"])
    derivar.derivar(producao["con"], nid)
    assert _camada0(producao["con"], producao["armazem"]) == antes


# ------------------------------------------------------------ 4. reproducibility
def _hash(con, did):
    return con.execute("SELECT hash_resultado FROM derivacao_execucao WHERE id=?", (did,)).fetchone()[0]


def test_mesmo_resultado_em_banco_reconstruido_do_armazem(producao, tmp_path):
    """Another database, different internal ids, built only from the store's manifests -> same hash."""
    outro = montar_producao(tmp_path, armazem_de=producao["cfg"].snapshots)
    assert outro["importacao"]["sincronizados"] == 197
    assert _hash(outro["con"], outro["did"]) == _hash(producao["con"], producao["did"])


def test_resultado_nao_depende_do_relogio(producao, monkeypatch):
    monkeypatch.setattr(normalizar, "agora", lambda: "2099-01-01T00:00:00-03:00")
    monkeypatch.setattr(derivar, "agora", lambda: "2099-01-01T00:00:00-03:00")
    nid, _ = normalizar.normalizar(producao["con"])
    did = derivar.derivar(producao["con"], nid)
    assert _hash(producao["con"], did) == _hash(producao["con"], producao["did"])


# ------------------------------------------------------------ 3. rules side by side
def test_todas_as_versoes_de_regra_calculadas_lado_a_lado_sem_promocao(producao):
    con, did = producao["con"], producao["did"]
    combos = set(con.execute(
        "SELECT g.versao, IFNULL(r.versao, 0), v.visao FROM visao_valor v JOIN regra g ON g.id=v.regra_agregacao_id "
        "LEFT JOIN regra r ON r.id=v.regra_consolidacao_id WHERE v.derivacao_id=?", (did,)).fetchall())
    for agg in (1, 2):
        assert {(agg, 0, "entidade"), (agg, 0, "publicado"), (agg, 1, "analitico"), (agg, 2, "analitico")} <= combos
    usos = dict(((c, v), u) for c, v, u in con.execute("SELECT codigo, versao, uso FROM regra"))
    assert usos[("CONS-PAR", 1)] == usos[("CONS-PAR", 2)] == usos[("RREO-COL", 2)] == "experimental"
    usadas = set(json.loads(con.execute("SELECT regras_json FROM derivacao_execucao WHERE id=?", (did,)).fetchone()[0]))
    assert usadas == {i for (i,) in con.execute("SELECT id FROM regra")}


# ------------------------------------------------------------ robustness
def _loja(tmp_path):
    cfg = carregar(dados_locais=tmp_path / "l", snapshots=tmp_path / "s", backups=tmp_path / "b")
    return banco.abrir(cfg), Armazem(cfg.snapshots)


COL = {"nome": "teste", "versao": "1", "sha256_codigo": None}
P = {"entidade": 998, "exercicio": 2026, "dataInicial": "2026-01-01", "dataFinal": "2026-12-31", "size": 2000}


def test_snapshot_com_falha_nao_e_processado(tmp_path):
    con, armazem = _loja(tmp_path)
    gravar_snapshot(con, armazem, tipo="rp_listagem", endpoint="/x", parametros=P, coletada_em="2026-09-30T10:00:00-03:00",
                    origem_carimbo="relogio_coletor", status="falhou", coletor=COL,
                    respostas=[{"url": "x", "http_status": 500, "corpo": b"<html>erro</html>"}])
    nid, resumo = normalizar.normalizar(con)
    did = derivar.derivar(con, nid)
    assert resumo["ignoradas_sem_pagina"] == 1 and resumo["rp_registro"] == 0
    assert con.execute("SELECT COUNT(*) FROM visao_valor WHERE derivacao_id=?", (did,)).fetchone()[0] == 0


def test_chave_duplicada_mantem_as_duas_linhas_e_vira_anomalia(tmp_path):
    """Rule 6: nothing is discarded for looking duplicated."""
    con, armazem = _loja(tmp_path)
    reg = {k: 0 for k in normalizar.DINHEIRO}
    reg.update({"entidade": 998, "anoempenho": 2025, "empenho": 7, "aproc": 10.5})
    corpo = json.dumps({"content": [reg, dict(reg, aproc=20)], "last": True, "totalElements": 2}).encode()
    gravar_snapshot(con, armazem, tipo="rp_listagem", endpoint="/x", parametros=P, coletada_em="2026-09-30T10:00:00-03:00",
                    origem_carimbo="relogio_coletor", status="completa", coletor=COL,
                    respostas=[{"url": "x", "http_status": 200, "corpo": corpo}])
    nid, _ = normalizar.normalizar(con)
    did = derivar.derivar(con, nid)
    assert con.execute("SELECT COUNT(*) FROM rp_registro WHERE normalizacao_id=?", (nid,)).fetchone()[0] == 2
    assert con.execute("SELECT COUNT(*) FROM rp_derivado WHERE derivacao_id=?", (did,)).fetchone()[0] == 2
    assert con.execute("SELECT COUNT(*) FROM anomalia WHERE derivacao_id=? AND tipo='CHAVE-DUP'", (did,)).fetchone()[0] == 1
