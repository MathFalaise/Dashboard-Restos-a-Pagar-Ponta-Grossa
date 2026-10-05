"""Regressao da auditoria tecnica, grupo G7 (DET-02): prova de equivalencia entre um banco e o reconstruido do
armazem. SINTETICO = banco temporario com registros inventados (fixture `mundo`)."""
from conftest import registro_sintetico as _reg

from rp import banco, derivar, equivalencia, execucoes, normalizar

T0 = "2026-09-29T20:00:00-03:00"
T1 = "2026-09-30T08:00:00-03:00"


def _mundo(mundo):
    mundo.catalogos({1: [2025], 15: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1), _reg(2, proc=50.0)], T0)
    mundo.listagem(15, 2025, "2025-12-31", [_reg(3, entidade=15)], T0)
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1), _reg(2, proc=40.0)], T1)     # retrato novo do mesmo corte
    nid, _ = mundo.processar()
    derivar.derivar(mundo.con, nid, "2026-09-29T23:59:59-03:00")
    mundo.con.commit()


def _reconstruido(mundo, tmp_path):
    con, n = banco.reconstruir(mundo.cfg, mundo.armazem, tmp_path / "reconstruido.sqlite")
    nid, _ = normalizar.normalizar(con)
    derivar.derivar(con, nid)
    derivar.derivar(con, nid, "2026-09-29T23:59:59-03:00")
    return con


def test_DET02_banco_reconstruido_e_equivalente_embora_hash_camada0_mude(mundo, tmp_path, monkeypatch):
    _mundo(mundo)
    # reconstrucao "mais tarde": sem relogio fixo, o banco reconstruido podia cair no MESMO segundo do original e, com
    # os uids aleatorios na mesma ordem, repetir ids e carimbos - e o hash antigo saia igual por acaso (teste instavel)
    monkeypatch.setattr(banco, "agora", lambda: "2031-01-01T00:00:00-03:00")
    outro = _reconstruido(mundo, tmp_path)
    r = equivalencia.comparar(mundo.con, outro)
    assert r["equivalentes"] is True, {k: v for k, v in r.items() if k not in ("a", "b")}
    assert set(r["derivacao_igual_por_vigencia"]) == {"atual", "2026-09-29T23:59:59-03:00"}
    # o hash antigo da camada 0 nao serve para isso: inclui ids e carimbos de registro (fica, com o mesmo valor)
    assert execucoes.hash_camada0(mundo.con) != execucoes.hash_camada0(outro)
    assert r["a"]["camada0"]["hash"] == r["b"]["camada0"]["hash"]


def test_DET02_diferenca_em_qualquer_camada_e_apontada(mundo, tmp_path):
    _mundo(mundo)
    outro = _reconstruido(mundo, tmp_path)
    did = outro.execute("SELECT MAX(id) FROM derivacao_execucao WHERE vigencia_em IS NULL").fetchone()[0]
    with outro:
        outro.execute("UPDATE visao_valor SET valor_c = valor_c + 1 WHERE derivacao_id=? AND componente='S1'", (did,))
        nid = outro.execute("SELECT MAX(id) FROM normalizacao_execucao").fetchone()[0]
        outro.execute("UPDATE rp_registro SET aproc_c = aproc_c + 1 WHERE normalizacao_id=? AND empenho=1", (nid,))
    r = equivalencia.comparar(mundo.con, outro)
    assert r["equivalentes"] is False and r["camada0_igual"] is True
    assert r["normalizacao_por_tabela"]["rp_registro"] is False and r["normalizacao_por_tabela"]["rreo_valor"] is True
    assert r["derivacao_igual_por_vigencia"]["atual"] is False and r["hash_gravado_confere_nos_dois"] is False
