"""Tests of the snapshot comparator and of re-collection (stage 04.4).

* Cases with REAL data use the `producao` fixture (raw data of stages 01/02).
* Cases marked SINTETICO use invented records, because the real data collected so far has no differences between
  snapshots of the same cut-off.
"""
import json

import pytest
from conftest import pagina

from rp import banco, comparador, consultas, derivar, execucoes, normalizar
from rp.armazem import Armazem
from rp.coletor import EP_RP, ParametroInvalido
from rp.config import carregar
from rp.snapshots import gravar_snapshot

COL = {"nome": "teste", "versao": "1", "sha256_codigo": None}


# ------------------------------------------------------------------ real data
def test_REAL_snapshots_identicos_do_mesmo_corte(producao):
    """Stage 02: two snapshots of entity 1 / 2026 up to 31/08 (20h12 and 20h25), identical bytes."""
    con = producao["con"]
    (c1, t1, _), (c2, t2, _) = consultas.historico(con, 1, 2026, "2026-01-01", "2026-08-31")
    r = comparador.comparar(con, c1, c2)
    assert r["bytes_identicos"] and r["contagens"] == {"novos": 0, "removidos": 0, "comuns": 4557, "alterados": 0,
                                                       "alterados_em_espelhamento": 0, "novos_ou_removidos_em_espelhamento": 0}
    assert r["anterior"]["coletada_em"] == t1 and r["posterior"]["coletada_em"] == t2
    assert all(v["diferenca"] == 0 for v in r["impacto_financeiro_por_campo"].values())


def test_REAL_cortes_diferentes_sao_recusados(producao):
    con = producao["con"]
    a = consultas.snapshot_em(con, 1, 2026, "2026-01-01", "2026-08-31")
    b = consultas.snapshot_em(con, 1, 2026, "2026-01-01", "2026-06-30")
    with pytest.raises(comparador.CorteDiferente):
        comparador.comparar(con, a, b)


def test_REAL_comparacao_nao_altera_nada(producao):
    con = producao["con"]
    (c1, _, _), (c2, _, _) = consultas.historico(con, 1, 2026, "2026-01-01", "2026-08-31")
    antes_mudancas, antes_hash = con.total_changes, execucoes.hash_camada0(con)
    comparador.comparar(con, c1, c2)
    assert con.total_changes == antes_mudancas and execucoes.hash_camada0(con) == antes_hash


# ------------------------------------------------------------------ SINTETICOS
P = {"entidade": 1, "exercicio": 2026, "dataInicial": "2026-01-01", "dataFinal": "2026-12-31", "size": 2000}


def _reg(emp, ano=2025, entidade=1, **kw):
    r = {k: 0 for k in normalizar.DINHEIRO}
    r.update({"entidade": entidade, "anoempenho": ano, "empenho": emp, "empenhoExercicio": f"{emp}/{ano}", "cnpj": "X",
              "dataEmissao": "2025-03-01", "nome": "FORNECEDOR", "fonteRecurso": 1000, "aproc": 100.0})
    r.update(kw)
    return r


def _loja(tmp_path):
    cfg = carregar(dados_locais=tmp_path / "l", snapshots=tmp_path / "s", backups=tmp_path / "b")
    return banco.abrir(cfg), Armazem(cfg.snapshots)


def _snap(con, armazem, quando, regs, params=P):
    corpo = json.dumps({"content": regs, "last": True, "totalElements": len(regs)}).encode()
    return gravar_snapshot(con, armazem, tipo="rp_listagem", endpoint=EP_RP, parametros=params, coletada_em=quando,
                           origem_carimbo="relogio_coletor", status="completa", coletor=COL,
                           respostas=[{"url": "sintetico", "http_status": 200, "corpo": corpo}])


def _comparar(tmp_path, antes, depois, extra=None):
    con, armazem = _loja(tmp_path)
    a = _snap(con, armazem, "2026-09-29T20:00:00-03:00", antes)
    b = _snap(con, armazem, "2026-10-03T20:00:00-03:00", depois)
    if extra:
        extra(con, armazem)
    nid, _ = normalizar.normalizar(con)
    derivar.derivar(con, nid)
    return con, comparador.comparar(con, a["snapshot_uid"], b["snapshot_uid"])


def test_SINTETICO_registro_novo(tmp_path):
    _, r = _comparar(tmp_path, [_reg(1)], [_reg(1), _reg(2, aproc=250.5)])
    assert r["contagens"]["novos"] == 1 and r["novos"][0]["chave"] == (1, 2025, 2) and r["novos"][0]["aproc_c"] == 25050
    assert r["impacto_financeiro_por_campo"]["aproc_c"]["de_registros_novos"] == 25050
    assert r["impacto_financeiro_por_grupo"]["inscricao_nao_processada"]["diferenca"] == 25050


def test_SINTETICO_registro_removido(tmp_path):
    _, r = _comparar(tmp_path, [_reg(1), _reg(2, aproc=40.0)], [_reg(1)])
    assert r["contagens"]["removidos"] == 1 and r["removidos"][0]["aproc_c"] == 4000
    assert r["impacto_financeiro_por_campo"]["aproc_c"]["diferenca"] == -4000


def test_SINTETICO_alteracao_de_valor_com_anterior_e_posterior(tmp_path):
    """Example from the specification: 500.000,00 -> 300.000,00 = -200.000,00."""
    _, r = _comparar(tmp_path, [_reg(1, aproc=500000.0)], [_reg(1, aproc=300000.0)])
    (alt,) = r["alterados"]
    (campo,) = [c for c in alt["campos"] if c["campo"] == "aproc_c"]
    assert (campo["antes"], campo["depois"], campo["diferenca"]) == (50000000, 30000000, -20000000)
    assert r["saldo_s1"]["diferenca"] == -20000000
    assert {"campo": "s1_saldo_total_c", "antes": 50000000, "depois": 30000000} in alt["classificacao_e_saldos"]


def test_SINTETICO_alteracao_de_campo_nao_monetario(tmp_path):
    _, r = _comparar(tmp_path, [_reg(1)], [_reg(1, nome="FORNECEDOR RENOMEADO")])
    (alt,) = r["alterados"]
    assert alt["campos"] == [{"campo": "nome", "antes": "FORNECEDOR", "depois": "FORNECEDOR RENOMEADO"}]
    assert all(v["diferenca"] == 0 for v in r["impacto_financeiro_por_campo"].values())


def test_SINTETICO_alteracao_em_varios_campos_e_de_classificacao(tmp_path):
    """Payment, liquidation and a category change (not processed -> both) in the same record."""
    _, r = _comparar(tmp_path, [_reg(1, aproc=100.0)],
                     [_reg(1, aproc=100.0, proc=30.0, liquidado=30.0, pagoAProc=20.0, orgao="09")])
    (alt,) = r["alterados"]
    # the agency came to exist: the list of missing keys also changes, and the comparator reports it
    assert {c["campo"] for c in alt["campos"]} == {"proc_c", "liquidado_c", "pago_aproc_c", "orgao", "chaves_ausentes"}
    assert {"campo": "categoria", "antes": "nao_processado", "depois": "ambos"} in alt["classificacao_e_saldos"]
    g = r["impacto_financeiro_por_grupo"]
    assert (g["pagamentos"]["diferenca"], g["liquidacoes"]["diferenca"], g["inscricao_processada"]["diferenca"]) == (2000, 3000, 3000)


def test_SINTETICO_alteracao_relacionada_a_espelhamento(tmp_path):
    """Entity 1's 24xxxxx copy changes between the snapshots; entity 15's original exists at the same cut-off."""
    copia = lambda **kw: _reg(2400021, **kw)
    original = _reg(21, entidade=15)
    extra = lambda con, arm: _snap(con, arm, "2026-10-03T20:00:01-03:00", [original], dict(P, entidade=15))
    _, r = _comparar(tmp_path, [copia()], [copia(pagoAProc=10.0, liquidado=10.0)], extra)
    (alt,) = r["alterados"]
    assert alt["espelhamento"] == "em par espelhado" and r["contagens"]["alterados_em_espelhamento"] == 1


def test_SINTETICO_momentos_diferentes_e_sem_alterar_os_originais(tmp_path):
    con, armazem = _loja(tmp_path)
    a = _snap(con, armazem, "2026-09-29T20:00:00-03:00", [_reg(1)])
    b = _snap(con, armazem, "2026-10-06T09:30:00-03:00", [_reg(1, aproc=90.0)])
    manifestos = {s["manifesto"]: (armazem.raiz / s["manifesto"]).read_bytes() for s in (a, b)}
    nid, _ = normalizar.normalizar(con)
    derivar.derivar(con, nid)
    antes = (con.total_changes, execucoes.hash_camada0(con))
    r = comparador.comparar(con, a["snapshot_uid"], b["snapshot_uid"])
    assert (r["anterior"]["coletada_em"], r["posterior"]["coletada_em"]) == ("2026-09-29T20:00:00-03:00", "2026-10-06T09:30:00-03:00")
    assert not r["bytes_identicos"] and r["contagens"]["alterados"] == 1
    assert (con.total_changes, execucoes.hash_camada0(con)) == antes
    assert all((armazem.raiz / m).read_bytes() == v for m, v in manifestos.items())
    assert con.execute("SELECT COUNT(*) FROM coleta").fetchone()[0] == 2  # no snapshot replaced


# ------------------------------------------------------------------ re-collection and bimester filter
def test_recoleta_usa_exatamente_os_mesmos_parametros_e_preserva_o_original(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [(200, pagina([_reg(1)], 0, 1, True, 1))]
    s1 = ambiente["coletor"].listagem(1, 2026, "2026-08-31")
    s2 = ambiente["coletor"].recoletar(s1["snapshot_uid"])
    con = ambiente["con"]
    p1, p2 = (con.execute("SELECT parametros_json FROM coleta WHERE snapshot_uid=?", (s["snapshot_uid"],)).fetchone()[0] for s in (s1, s2))
    assert p1 == p2 and s1["snapshot_uid"] != s2["snapshot_uid"]
    assert p.chamadas[0] == p.chamadas[1]  # same URL, same parameters
    assert "recoleta de " + s1["snapshot_uid"] in s2["observacao"]
    assert con.execute("SELECT COUNT(*) FROM coleta").fetchone()[0] == 2


def test_recoleta_recusa_corte_fora_da_regra(ambiente):
    con, armazem = ambiente["con"], ambiente["armazem"]
    s = _snap(con, armazem, "2026-09-29T20:00:00-03:00", [_reg(1)], dict(P, dataInicial="2026-02-01"))
    with pytest.raises(ParametroInvalido, match="fora da regra"):
        ambiente["coletor"].recoletar(s["snapshot_uid"])


def test_rreo_filtra_bimestres(ambiente):
    from rp.coletor import EP_ARQ, EP_PUB
    p = ambiente["portal"]
    lista = [{"idArquivo": i, "valor": v} for i, v in ((1, "5º Bimestre"), (2, "6º Bimestre"), (3, "6º Bimestre - Consolidado"))]
    p.rotas[(EP_PUB, None)] = [(200, json.dumps([{"list": [{"subGrupoRelatorio": {"valor": "Anexo VII - Demonstrativo dos Restos a Pagar"},
                                                             "list": lista}]}]).encode())]
    for i in (1, 2, 3):
        p.rotas[(f"{EP_ARQ}/{i}", None)] = [(200, b"%PDF-1.3")]
    r = ambiente["coletor"].rreo(2024, bimestres={6})
    assert len(r) == 3 and not any(c[0].endswith("/arquivo/1") for c in p.chamadas)  # the 5th bimester is not downloaded


def test_rreo_filtra_bimestres_rotulo_em_maiusculas(ambiente):
    """In 2019 the portal publishes "6o BIMESTRE" (upper case) and in 2018 there is "4 o Bimestre": the filter cannot
    depend on that."""
    from rp.coletor import EP_ARQ, EP_PUB
    p = ambiente["portal"]
    lista = [{"idArquivo": i, "valor": v} for i, v in ((1, "5º BIMESTRE"), (2, "6º BIMESTRE"), (3, "6 º Bimestre"), (4, "16º Bimestre"))]
    p.rotas[(EP_PUB, None)] = [(200, json.dumps([{"list": [{"subGrupoRelatorio": {"valor": "Anexo VII - Demonstrativo dos Restos a Pagar"},
                                                             "list": lista}]}]).encode())]
    for i in (1, 2, 3, 4):
        p.rotas[(f"{EP_ARQ}/{i}", None)] = [(200, b"%PDF-1.3")]
    r = ambiente["coletor"].rreo(2019, bimestres={6})
    baixados = {c[0].rsplit("/", 1)[1] for c in p.chamadas if "/arquivo/" in c[0]}
    assert len(r) == 3 and baixados == {"2", "3"}  # neither the 5th nor the "16o"


def test_retencao_nunca_apaga_backups_preservados(tmp_path):
    import time
    cfg = carregar(dados_locais=tmp_path / "l", snapshots=tmp_path / "s", backups=tmp_path / "b")
    con = banco.abrir(cfg)
    primeiro = banco.backup(con, cfg, "antes-apagar-preservado", operacional=True)
    (cfg.backups_operacionais / "PRESERVAR.txt").write_text(primeiro.name + "\n", encoding="utf-8")
    for i in range(4):
        time.sleep(1.05)
        banco.backup(con, cfg, f"antes-apagar-{i}", operacional=True)
    nomes = {p.name for p in cfg.backups_operacionais.glob("*.sqlite")}
    assert primeiro.name in nomes and len(nomes) == 4  # 3 from retention + 1 preserved
