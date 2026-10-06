"""Regression of the technical audit, group G6: verification and gates that used to let corruption through.
SINTETICO = temporary database with invented records (fixture `mundo`)."""
import json

from conftest import registro_sintetico as _reg

from rp import banco, portoes
from rp.snapshots import gravar_snapshot

T0 = "2026-09-29T20:00:00-03:00"


def _mundo_processado(mundo, regs=None):
    mundo.catalogos({1: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", regs or [_reg(1), _reg(2, proc=50.0)], T0)
    nid, did = mundo.processar()
    mundo.con.commit()
    return nid, did


def _portao(r, ident):
    return next(p for p in r["portoes"] if p["id"] == ident)


def test_POR01_portoes_dizem_o_que_nao_foi_verificado(mundo):
    _mundo_processado(mundo)
    r = portoes.avaliar(mundo.cfg.banco, mundo.armazem)
    assert r["apto"] is True and r["apto_sem_ressalvas"] is False
    assert r["nao_verificados"] == ["camada_bruta_preservada", "testes"]
    for ident in ("hash_resultado_confere", "integridade_relacional", "campos_monetarios_ausentes", "lancamento_desconhecido"):
        assert _portao(r, ident)["ok"] is True, ident


def test_DB01_alteracao_direta_em_tabela_derivada_reprova_o_portao(mundo):
    _, did = _mundo_processado(mundo)
    with mundo.con:
        mundo.con.execute("UPDATE visao_valor SET valor_c = valor_c + 1 WHERE derivacao_id=? AND componente='S1'", (did,))
    r = portoes.avaliar(mundo.cfg.banco, mundo.armazem)
    p = _portao(r, "hash_resultado_confere")
    assert p["ok"] is False and r["apto"] is False and p["detalhe"][0]["confere"] is False
    assert banco.verificar(mundo.con, mundo.armazem) == []               # layer 0 is still intact


def test_DB02_linha_orfa_nas_tabelas_sem_FK_reprova_o_portao(mundo):
    _, did = _mundo_processado(mundo)
    regra = mundo.con.execute("SELECT id FROM regra WHERE codigo='ANOM-REG'").fetchone()[0]
    # since schema v5 (decision D4) the ri_* triggers refuse these rows on write; without them (a v4 database or
    # a tampered schema) the gate is still the defense that reads
    for (nome,) in mundo.con.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'ri_%'").fetchall():
        mundo.con.execute(f"DROP TRIGGER {nome}")
    with mundo.con:
        mundo.con.execute("INSERT INTO anomalia VALUES (?,?,?,?,?,?,?,?)", (did, regra, "LIQ-NEG", 9999, 1, 2024, 1, None))
        mundo.con.execute("INSERT INTO rp_derivado SELECT derivacao_id, 9999, indice, coleta_id, entidade, anoempenho, "
                          "empenho, categoria, faixa_processado, faixa_nao_processado, s1_saldo_total_c, s2_a_liquidar_c, "
                          "s3_liquidado_a_pagar_c, cancel_processado_c, cancel_nao_processado_c FROM rp_derivado "
                          "WHERE derivacao_id=? LIMIT 1", (did,))
    p = _portao(portoes.avaliar(mundo.cfg.banco, mundo.armazem), "integridade_relacional")
    assert p["ok"] is False
    assert p["detalhe"]["anomalia_sem_coleta"] == 1 and p["detalhe"]["rp_derivado_sem_registro_da_normalizacao"] == 1


def test_NORM01_campo_monetario_ausente_reprova_o_portao(mundo):
    sem = _reg(1)
    del sem["pagoProc"]
    nid, _ = _mundo_processado(mundo, [sem])
    valor, ausentes = mundo.con.execute("SELECT pago_proc_c, chaves_ausentes FROM rp_registro WHERE normalizacao_id=?",
                                        (nid,)).fetchone()
    assert valor == 0 and "pagoProc" in json.loads(ausentes)               # the homologated behavior is kept
    p = _portao(portoes.avaliar(mundo.cfg.banco, mundo.armazem), "campos_monetarios_ausentes")
    assert p["ok"] is False and p["detalhe"]["registros"] == 1


def test_DER02_tipo_de_lancamento_desconhecido_reprova_o_portao(mundo):
    mundo.catalogos({1: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1)], T0)
    lanc = {"data": "2025-03-01", "tipoLancamento": 99, "valor": 10.0}
    gravar_snapshot(mundo.con, mundo.armazem, tipo="movimentacao", endpoint="/empenhos/detalhe/movimentacao",
                    parametros={"entidade": 1, "anoempenho": 2024, "empenho": 1, "size": 500}, coletada_em=T0,
                    origem_carimbo="relogio_coletor", status="completa",
                    coletor={"nome": "teste", "versao": "1", "sha256_codigo": None},
                    respostas=[{"url": "x", "http_status": 200,
                                "corpo": json.dumps({"content": [lanc], "totalElements": 1, "last": True}).encode()}])
    mundo.processar()
    mundo.con.commit()
    p = _portao(portoes.avaliar(mundo.cfg.banco, mundo.armazem), "lancamento_desconhecido")
    assert p["ok"] is False and p["detalhe"]["lancamentos"] == 1


def test_REC01_manifesto_alterado_depois_do_registro_e_detectado(mundo):
    _mundo_processado(mundo)
    rel = mundo.con.execute("SELECT manifesto FROM coleta WHERE tipo='rp_listagem'").fetchone()[0]
    arq = mundo.armazem.raiz / rel
    m = json.loads(arq.read_text(encoding="utf-8"))
    m["status"], m["parametros"]["dataFinal"] = "incompleta", "2025-11-30"
    arq.write_text(json.dumps(m), encoding="utf-8")
    problemas = banco.verificar(mundo.con, mundo.armazem)
    assert any("coleta difere do manifesto" in x and "status" in x and "parametros" in x for x in problemas), problemas


def test_ARM01_objeto_orfao_e_temporario_abandonado_sao_relatados(mundo):
    _mundo_processado(mundo)
    assert mundo.armazem.verificar() == []
    h = mundo.armazem.gravar_objeto(b"bytes gravados por uma coleta que caiu antes do manifesto")
    (mundo.armazem.caminho_objeto(h).parent / "x.zlib.tmp123").write_bytes(b"meio arquivo")
    problemas = mundo.armazem.verificar()
    assert any("objeto sem manifesto" in x and h in x for x in problemas)
    assert any("temporário abandonado" in x for x in problemas)
    assert mundo.armazem.caminho_objeto(h).exists()                       # reported, never deleted
