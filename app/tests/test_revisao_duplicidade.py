"""Revisao critica (05/10/2026), etapas B e C - duplicidade e elegibilidade: itens 1, 13, 14, 15 e 35 (casos 5 e 6).

Mundo sintetico (fixture `mundo`): o snapshot e gravado direto como 'completa', como um retrato antigo ou importado
que nao passou pela trava nova do coletor. A derivacao, o painel e os portoes tem de tratar a chave repetida sozinhos:
nenhuma copia somada duas vezes, nenhuma escolhida em silencio.
"""
import json

import pytest
import recalculo_bruto as rb
from conftest import registro_sintetico

from rp import derivar, portoes

CORTE = (2025, "2025-12-31")
T1, T2 = "2026-09-20T10:00:00-03:00", "2026-09-25T10:00:00-03:00"
R1 = registro_sintetico(1, ano=2024, aproc=100.0)
R2 = registro_sintetico(2, ano=2024, aproc=50.0)
R2_OUTRO = registro_sintetico(2, ano=2024, aproc=70.0)


def _cenario(mundo, retratos):
    """`retratos`: [(quando, registros)] do mesmo corte da entidade 1. Devolve (snapshots, nid, did)."""
    mundo.catalogos({1: [2025]})
    snaps = [mundo.listagem(1, *CORTE, regs, quando) for quando, regs in retratos]
    nid, did = mundo.processar()
    return snaps, nid, did


def _anomalias(con, did):
    return [json.loads(d) for (d,) in con.execute(
        "SELECT detalhe_json FROM anomalia WHERE derivacao_id=? AND tipo='CHAVE-DUP'", (did,))]


def _portao(mundo, ident):
    r = portoes.avaliar(mundo.cfg.banco, mundo.armazem)
    return next(p for p in r["portoes"] if p["id"] == ident), r


def _inscricao(painel):
    return painel.indicadores(*CORTE, entidade=1)["valores"]["inscricao_total"]["valor_c"]


# ------------------------------------------------------------------ caso 6 do item 35: copia exata
def test_REV01_copia_exata_nao_e_somada_e_retrato_anterior_vale(mundo):
    (s1, s2), _, did = _cenario(mundo, [(T1, [R1, R2]), (T2, [R1, R2, R2])])
    con = mundo.con
    [a] = _anomalias(con, did)
    assert a == {"ocorrencias": 2, "natureza": "exata", "posicoes": [[0, 1], [0, 2]]}
    assert derivar.coletas_vigentes(con)[(1, 2025, "2025-01-01", "2025-12-31")] == s1["coleta_id"]
    # visao da derivacao: 100 + 50 (a regra antiga somava 100 + 50 + 50 do retrato novo)
    g = con.execute("SELECT valor_c FROM visao_valor WHERE derivacao_id=? AND visao='entidade' AND componente='g' "
                    "AND coletas_json=?", (did, json.dumps([s1["snapshot_uid"]]))).fetchall()
    assert g and all(v == 15000 for (v,) in g)
    verif = con.execute("SELECT escopo_json, verificados, falhas FROM verificacao WHERE derivacao_id=? AND descricao=?",
                        (did, derivar.VERIF_RETRATO_AMBIGUO)).fetchall()
    assert [(json.loads(e)["snapshot_recusado"], json.loads(e)["snapshot_vigente"], v, f) for e, v, f in verif] == \
           [(s2["snapshot_uid"], s1["snapshot_uid"], 1, 1)]


def test_REV01_painel_usa_o_retrato_valido_e_avisa(mundo):
    (s1, s2), _, _ = _cenario(mundo, [(T1, [R1, R2]), (T2, [R1, R2, R2])])
    with mundo.painel() as p:
        r = p.indicadores(*CORTE, entidade=1)
        assert r["disponivel"] and r["valores"]["inscricao_total"]["valor_c"] == 15000
        assert r["entidades"][0]["snapshot"]["snapshot_uid"] == s1["snapshot_uid"]
        assert any("chave de empenho repetida" in a and s2["snapshot_uid"][:8] in a for a in r["avisos"])
        assert p._vigentes(p.contexto(), None) == derivar.coletas_vigentes(mundo.con)


# ------------------------------------------------------------------ caso 5 do item 35: conteudo diferente
def test_REV01_copia_conflitante_bloqueia_o_retrato(mundo):
    (s1, _), _, did = _cenario(mundo, [(T1, [R1, R2]), (T2, [R1, R2, R2_OUTRO])])
    [a] = _anomalias(mundo.con, did)
    assert a["natureza"] == "conflitante" and a["ocorrencias"] == 2
    with mundo.painel() as p:      # nenhuma das duas versoes do empenho 2 (50 ou 70) e escolhida
        assert _inscricao(p) == 15000
        assert p.indicadores(*CORTE, entidade=1)["entidades"][0]["snapshot"]["snapshot_uid"] == s1["snapshot_uid"]


def test_REV01_so_retrato_ambiguo_deixa_o_dado_indisponivel(mundo):
    _, _, did = _cenario(mundo, [(T2, [R1, R2, R2_OUTRO])])
    assert derivar.coletas_vigentes(mundo.con) == {}
    assert mundo.con.execute("SELECT COUNT(*) FROM visao_valor WHERE derivacao_id=?", (did,)).fetchone()[0] == 0
    with mundo.painel() as p:
        r = p.indicadores(*CORTE, entidade=1)
        assert not r["disponivel"] and r["valores"]["inscricao_total"]["valor_c"] is None
        assert r["entidades"][0]["situacao_do_dado"]["codigo"] == "ambiguo"
        assert "não há retrato válido anterior" in " ".join(r["avisos"])
        m = p.indicadores(*CORTE)                        # Municipio: entidade do catalogo sem retrato valido
        assert not m["disponivel"] and "CHAVE-DUP" in m["motivo_indisponivel"]


def test_REV01_corte_so_com_retrato_ambiguo_aparece_e_confere_com_o_bruto(mundo):
    # R1 do contrato analitico: corte sem dado aparece com a situacao, nunca omitido. O oraculo bruto decide a mesma
    # elegibilidade lendo o JSON do armazem (sem a anomalia gravada pela derivacao)
    _cenario(mundo, [(T1, [R1, R2])])
    mundo.listagem(1, 2025, "2025-04-30", [R1, R2, R2], T2)
    mundo.processar()
    b = rb.Bruto(mundo.con, mundo.armazem)
    with mundo.painel() as p:
        cortes = {c["data_final"]: c for c in p.cortes()["cortes"] if c["exercicio"] == 2025}
        assert sorted(cortes) == b.cortes_do_exercicio(2025) == ["2025-04-30", "2025-12-31"]
        amb = cortes["2025-04-30"]
        assert not amb["municipio_disponivel"] and "CHAVE-DUP" in amb["motivo"] and amb["entidades_com_snapshot"] == []
        for ent, esperado in ((1, "ambiguo"), (None, "municipio_indisponivel")):
            serie = [(x["data_final"], x["situacao"]["codigo"]) for x in p.evolucao(2025, ent)["serie"]]
            assert serie == [(x["data_final"], x["situacao"]) for x in b.serie(2025, ent)]
            assert serie == [("2025-04-30", esperado), ("2025-12-31", "com_dados")]


# ------------------------------------------------------------------ item 14: portao
def test_REV14_portao_reprova_com_a_natureza_da_repeticao(mundo):
    _cenario(mundo, [(T1, [R1, R2]), (T2, [R1, R2, R2, R1, registro_sintetico(1, ano=2024, aproc=1.0)])])
    p, r = _portao(mundo, "retrato_sem_chave_repetida")
    assert p["ok"] is False and not r["apto"]
    assert (p["detalhe"]["chaves"], p["detalhe"]["exata"], p["detalhe"]["conflitante"]) == (2, 1, 1)


def test_REV14_sem_repeticao_o_portao_aprova_e_nada_novo_e_gravado(mundo):
    _, _, did = _cenario(mundo, [(T1, [R1, R2]), (T2, [R1, R2_OUTRO])])
    p, _ = _portao(mundo, "retrato_sem_chave_repetida")
    assert p["ok"] is True and p["detalhe"]["chaves"] == 0
    con = mundo.con
    assert not _anomalias(con, did)
    assert con.execute("SELECT COUNT(*) FROM verificacao WHERE derivacao_id=? AND descricao=?",
                       (did, derivar.VERIF_RETRATO_AMBIGUO)).fetchone()[0] == 0
    with mundo.painel() as painel:                       # o retrato mais novo e o vigente, como sempre foi
        assert _inscricao(painel) == 17000


# ------------------------------------------------------------------ item 13: mapa por chave nunca escolhe uma copia
def test_REV13_mapa_por_chave_recusa_repeticao():
    linha = lambda emp, v: {"anoempenho": 2024, "empenho": emp, "coleta_id": 9, "proc_c": v}
    assert set(derivar._por_chave([linha(1, 1), linha(2, 2)], "teste")) == {(2024, 1), (2024, 2)}
    with pytest.raises(derivar.ChaveAmbigua, match="repetida"):      # antes: {k: r} ficava com a ULTIMA copia
        derivar._por_chave([linha(1, 1), linha(1, 2)], "teste")


def test_REV13_continuidade_nunca_recebe_retrato_ambiguo(mundo):
    # fechamento 2024 ambiguo + abertura 2025: o ambiguo nao e vigente, entao nao ha continuidade a calcular (antes:
    # o fechamento entrava com a ultima copia de cada chave)
    mundo.catalogos({1: [2024, 2025]})
    mundo.listagem(1, 2024, "2024-12-31", [registro_sintetico(1, ano=2023), registro_sintetico(1, ano=2023)], T1)
    mundo.listagem(1, 2025, "2025-12-31", [registro_sintetico(1, ano=2023)], T1)
    _, did = mundo.processar()
    assert mundo.con.execute("SELECT COUNT(*) FROM verificacao WHERE derivacao_id=? AND descricao=?",
                             (did, "continuidade fechamento→abertura")).fetchone()[0] == 0
