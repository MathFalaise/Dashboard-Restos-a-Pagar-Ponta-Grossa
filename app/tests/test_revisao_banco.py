"""Critical review (05/10/2026), stage D - database, normalization and verification: items 7, 11, 12, 25, 28, 29, 30,
44 and 46.

Temporary databases (fixture `mundo`) and synthetic PDFs; nothing reads the active database.
"""
import json
import re
import sqlite3
from pathlib import Path

import pytest
from conftest import registro_sintetico

from rp import banco, derivar, equivalencia, normalizar, portoes

T1 = "2026-09-20T10:00:00-03:00"


def _processado(mundo):
    """2025 closing and 2026 opening: generates views and the continuity check (diagnostic)."""
    mundo.catalogos({1: [2025, 2026]})
    mundo.listagem(1, 2025, "2025-12-31", [registro_sintetico(1, ano=2024), registro_sintetico(2, ano=2023)], T1)
    mundo.listagem(1, 2026, "2026-08-31", [registro_sintetico(1, ano=2024)], T1)
    return mundo.processar()


def _portao(mundo, ident, caminho=None):
    r = portoes.avaliar(caminho or mundo.cfg.banco, mundo.armazem)
    return next(p for p in r["portoes"] if p["id"] == ident)


# ------------------------------------------------------------------ item 28: schema fingerprint
def test_REV28_codigo_tem_a_impressao_da_sua_versao():
    # did a table, column, constraint, index or trigger change? This test fails until the new version has the new fingerprint
    assert banco.impressao_esquema(banco.esquema_do_codigo()) == banco.IMPRESSAO_ESQUEMA[banco.VERSAO_ESQUEMA]


def test_REV28_comentario_e_espaco_nao_mudam_a_impressao_mas_estrutura_muda():
    texto = banco.ESQUEMA.read_text(encoding="utf-8")
    sem_acento = texto.replace("estável", "estavel").replace("também", "tambem")
    outros_comentarios = re.sub(r"--[^\n]*", "-- comentario reescrito", sem_acento).replace("    ", "  ")

    def montar(sql, extra=None):
        con = sqlite3.connect(":memory:")
        con.executescript(sql)
        for v in range(banco.VERSAO_BASE + 1, banco.VERSAO_ESQUEMA + 1):
            for s in banco.MIGRACOES[v][1]:
                con.execute(s)
        if extra:
            con.execute(extra)
        return banco.impressao_esquema(con)
    referencia = banco.IMPRESSAO_ESQUEMA[banco.VERSAO_ESQUEMA]
    assert montar(outros_comentarios) == referencia
    assert montar(texto, "ALTER TABLE anomalia ADD COLUMN extra TEXT") != referencia
    assert montar(texto.replace("CHECK (escopo IN ('entidade', 'consolidado'))",
                                "CHECK (escopo IN ('entidade'))")) != referencia     # a constraint changes the fingerprint


def test_REV28_portao_do_esquema(mundo, tmp_path):
    _processado(mundo)
    assert _portao(mundo, "esquema_confere")["ok"] is True
    copia = tmp_path / "alterado.sqlite"
    destino = sqlite3.connect(copia)
    mundo.con.backup(destino)
    destino.execute("ALTER TABLE anomalia ADD COLUMN extra TEXT")
    destino.commit()
    destino.close()
    p = _portao(mundo, "esquema_confere", copia)
    assert p["ok"] is False and p["detalhe"]["versao"] == banco.VERSAO_ESQUEMA


# ------------------------------------------------------------------ item 46: active database only on a local disk
@pytest.mark.parametrize("caminho", [
    "C:/Users/x/Dropbox/RP/banco.sqlite", "C:/Users/x/Dropbox (Empresa)/banco.sqlite",
    "G:/My Drive/banco.sqlite", "G:/Meu Drive/RP/banco.sqlite", "C:/Users/x/iCloudDrive/banco.sqlite",
    "C:/Users/x/Box Sync/banco.sqlite", "C:/Users/x/OneDrive - Empresa/banco.sqlite",
])
def test_REV46_pastas_sincronizadas_conhecidas(caminho):
    assert banco.em_pasta_sincronizada(caminho)


def test_REV46_unidade_de_rede_e_disco_local(tmp_path):
    assert banco._unidade_de_rede(Path(r"\\servidor\compartilhamento\banco.sqlite"))
    assert not banco.em_pasta_sincronizada(tmp_path / "banco.sqlite")
    assert not banco.em_pasta_sincronizada(tmp_path / "Box" / "toolbox" / "banco.sqlite")   # generic name: local


def test_REV46_abrir_recusa_banco_ativo_em_pasta_sincronizada(tmp_path):
    from rp.config import carregar
    cfg = carregar(dados_locais=tmp_path / "Dropbox" / "rp", snapshots=tmp_path / "s", backups=tmp_path / "b")
    with pytest.raises(banco.BancoEmPastaSincronizada, match="sincronizada ou de rede"):
        banco.abrir(cfg)
    assert not cfg.banco.exists()


# ------------------------------------------------------------------ items 7, 11 and 12: RREO transcription
def _pdf(paginas):
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf
    doc = pymupdf.open()
    for textos in paginas:
        pg = doc.new_page(width=1000, height=600)
        for (x, y), t in textos:
            pg.insert_text((x, y), t, fontsize=7)
    return doc.tobytes()


ROTULOS_X = [("(a)", 300), ("(b)", 350), ("(c)", 400), ("(d)", 450), ("e=(a+b)", 500), ("(f)", 550), ("(g)", 600),
             ("(h)", 650), ("(i)", 700), ("(j)", 750), ("k=(f+g)", 800), ("L=(e+k)", 850)]
CABECALHO = [((50, 40), "DEMONSTRATIVO JANEIRO A AGOSTO 2.026")] + [((x, 100), r) for r, x in ROTULOS_X]


class _Captura:
    def executemany(self, sql, linhas):
        self.sql, self.linhas = sql, list(linhas)

        class R:
            rowcount = len(self.linhas)
        return R()


def test_REV11_linha_repetida_com_mesmo_valor_vira_uma_linha_sem_OR_IGNORE():
    total = lambda y: [((50, y), "TOTAL"), ((80, y), "(III)"), ((300, y), "1.234,56")]
    cap = _Captura()
    n = normalizar._rreo(cap, 1, 1, {"rotulo": "4º Bimestre"}, _pdf([CABECALHO + total(300) + total(400)]))
    assert n == 1 and [(l[7], l[8], l[9]) for l in cap.linhas] == [("TOTAL (III)", "a", 123456)]
    assert "OR IGNORE" not in cap.sql and "OR IGNORE" not in normalizar.SQL_RREO


def test_REV12_pdf_com_mais_de_uma_pagina_nao_e_transcrito_pela_metade():
    pagina1 = CABECALHO + [((50, 300), "TOTAL"), ((80, 300), "(III)"), ((300, 300), "1.234,56")]
    with pytest.raises(normalizar.LayoutDesconhecido, match="2 página"):
        normalizar._rreo(_Captura(), 1, 1, {"rotulo": "4º Bimestre"}, _pdf([pagina1, [((50, 40), "continuação")]]))


def _mundo_com_pdf(mundo):
    """A snapshot of an RREO PDF (raw bytes: Mundo._snap writes JSON)."""
    from rp.snapshots import gravar_snapshot
    from conftest import COLETOR_SINTETICO
    gravar_snapshot(mundo.con, mundo.armazem, tipo="rreo_pdf", endpoint="/api/files/arquivo/10",
                    parametros={"id_arquivo": 10, "exercicio": 2026, "entidade": 1, "rotulo": "4º Bimestre"},
                    coletada_em=T1, origem_carimbo="relogio_coletor", status="completa", coletor=COLETOR_SINTETICO,
                    respostas=[{"url": "sintetico", "http_status": 200, "corpo": b"%PDF-1.4 sintetico"}])


def test_REV07_erro_de_layout_fica_registrado(mundo, monkeypatch):
    _mundo_com_pdf(mundo)
    monkeypatch.setattr(normalizar, "_rreo", lambda *a: (_ for _ in ()).throw(normalizar.LayoutDesconhecido("x")))
    nid, resumo = normalizar.normalizar(mundo.con)
    assert any("LayoutDesconhecido" in p["erro"] for p in resumo["problemas"])


def test_REV07_erro_de_programa_no_extrator_derruba_o_processamento(mundo, monkeypatch):
    _mundo_com_pdf(mundo)
    monkeypatch.setattr(normalizar, "_rreo", lambda *a: None + 1)     # TypeError: a program defect, not a layout
    antes = mundo.con.execute("SELECT COUNT(*) FROM normalizacao_execucao").fetchone()[0]
    with pytest.raises(TypeError):
        normalizar.normalizar(mundo.con)
    assert mundo.con.execute("SELECT COUNT(*) FROM normalizacao_execucao").fetchone()[0] == antes   # nothing written


# ------------------------------------------------------------------ item 25: semantic hash x run hash
def test_REV25_diagnostico_muda_o_hash_da_execucao_mas_nao_o_semantico(mundo):
    _, did = _processado(mundo)
    con = mundo.con
    h, s = derivar.hash_resultado(con, did), derivar.hash_semantico(con, did)
    assert con.execute("SELECT COUNT(*) FROM verificacao WHERE derivacao_id=?", (did,)).fetchone()[0] > 0
    with con:
        con.execute("UPDATE verificacao SET descricao = descricao || ' (texto revisto)' WHERE derivacao_id=?", (did,))
    assert derivar.hash_resultado(con, did) != h and derivar.hash_semantico(con, did) == s
    with con:
        con.execute("UPDATE visao_valor SET valor_c = valor_c + 1 WHERE derivacao_id=? AND componente='g'", (did,))
    assert derivar.hash_semantico(con, did) != s


# ------------------------------------------------------------------ item 44: reference in canonical serialization
def test_REV44_referencia_canonica_e_compatibilidade_com_a_antiga(mundo, tmp_path):
    _processado(mundo)
    arq = tmp_path / "ref.json"
    ref = portoes.gravar_referencia(mundo.cfg.banco, arq)
    assert ref["formato"] == portoes.FORMATO_REFERENCIA and json.loads(arq.read_text(encoding="utf-8")) == ref
    r = portoes.avaliar(mundo.cfg.banco, mundo.armazem, ref)
    assert next(p for p in r["portoes"] if p["id"] == "camada_bruta_preservada")["ok"] is True
    with sqlite3.connect(f"{Path(mundo.cfg.banco).resolve().as_uri()}?mode=ro", uri=True) as con:
        antiga = portoes._referencia(con, canonico=False)          # like the references recorded before (repr)
    assert "formato" not in antiga and antiga["hash_coletas"] != ref["hash_coletas"]
    r = portoes.avaliar(mundo.cfg.banco, mundo.armazem, antiga)
    assert next(p for p in r["portoes"] if p["id"] == "camada_bruta_preservada")["ok"] is True
    # after a new load the old rows stay the same: the canonical reference matches
    mundo.listagem(1, 2025, "2025-06-30", [registro_sintetico(3, ano=2024)], "2026-09-21T10:00:00-03:00")
    r = portoes.avaliar(mundo.cfg.banco, mundo.armazem, ref)
    assert next(p for p in r["portoes"] if p["id"] == "camada_bruta_preservada")["ok"] is True


# ------------------------------------------------------------------ items 29 and 30: backup -> restore -> result
def test_REV30_backup_restaurado_reproduz_o_mesmo_resultado(mundo):
    _, did = _processado(mundo)
    arq = banco.backup(mundo.con, mundo.cfg, "teste-restauracao")
    restaurado = sqlite3.connect(arq)
    try:
        assert [r[0] for r in restaurado.execute("PRAGMA integrity_check")] == ["ok"]
        assert restaurado.execute("PRAGMA foreign_key_check").fetchall() == []
        assert banco.impressao_esquema(restaurado) == banco.IMPRESSAO_ESQUEMA[banco.VERSAO_ESQUEMA]
        gravado = restaurado.execute("SELECT hash_resultado FROM derivacao_execucao WHERE id=?", (did,)).fetchone()[0]
        assert derivar.hash_resultado(restaurado, did) == gravado
        c = equivalencia.comparar(mundo.con, restaurado)
        assert c["equivalentes"] and all(c["resultado_semantico_igual_por_vigencia"].values())
    finally:
        restaurado.close()
    r = portoes.avaliar(arq, mundo.armazem)
    assert all(p["ok"] is not False for p in r["portoes"] if p["id"] in (
        "integridade_sqlite", "hash_resultado_confere", "integridade_relacional", "esquema_confere",
        "retrato_sem_chave_repetida"))
