"""Regression of the technical audit, groups G4 and G5: validity, determinism, RREO normalization, derivation and the
rule catalog. SINTETICO = temporary database with invented records (fixture `mundo`)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import (CABECALHO_RREO, EXCETO_RREO, RAIZ_PROJETO, TOTAL_RREO, linha_rreo, registro_sintetico as _reg,
                      textos_da_linha)

from rp import DataInvalida, cli, derivar, governanca, instante, normalizar, regras
from rp.snapshots import gravar_snapshot

T0 = "2026-09-29T20:00:00-03:00"
APP = RAIZ_PROJETO / "app"


# ------------------------------------------------------------------ CLI-01: validity "as it was on"
def test_CLI01_instante_unico_para_derivacao_painel_e_cli():
    assert instante("2026-09-29") == "2026-09-29T23:59:59-03:00"            # date = end of the day
    assert instante("2026-09-30T02:59:59Z") == "2026-09-29T23:59:59-03:00"  # same instant, same text
    assert instante("2026-09-29T23:59:59-03:00") == "2026-09-29T23:59:59-03:00"
    with pytest.raises(DataInvalida):
        instante("ontem")
    from rp.painel.consulta import ErroDoPainel
    from rp.painel.consulta import instante as do_painel
    assert do_painel("2026-09-29") == instante("2026-09-29")
    with pytest.raises(ErroDoPainel):
        do_painel("ontem")


def test_CLI01_derivacao_recusa_vigencia_fora_da_forma_canonica(mundo):
    mundo.catalogos({1: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1)], T0)
    nid, _ = mundo.processar()
    for ruim in ("2026-09-29", "2026-09-30T02:59:59Z", "ontem"):
        with pytest.raises(DataInvalida):
            derivar.derivar(mundo.con, nid, ruim)


def _config_do_mundo(mundo, tmp_path):
    base = mundo.cfg.dados_locais.parent
    arq = tmp_path / "cfg" / "config.toml"
    arq.parent.mkdir()
    texto = (APP / "config.toml").read_text(encoding="utf-8")
    texto = (texto.replace('"~/RestosAPagar_local"', json.dumps(str(mundo.cfg.dados_locais)))
             .replace('"../data/snapshots"', json.dumps(str(mundo.cfg.snapshots)))
             .replace('"../data/backups"', json.dumps(str(mundo.cfg.backups))))
    arq.write_text(texto, encoding="utf-8")
    assert base.exists()
    return str(arq)


def test_CLI01_processar_em_normaliza_a_data_e_recusa_texto_invalido(mundo, tmp_path, monkeypatch):
    monkeypatch.delenv("RP_DADOS_LOCAIS", raising=False)
    mundo.catalogos({1: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1)], T0)
    cfg = _config_do_mundo(mundo, tmp_path)
    n = lambda: mundo.con.execute("SELECT COUNT(*) FROM normalizacao_execucao").fetchone()[0]
    antes = n()
    assert cli.main(["--config", cfg, "processar", "--em", "ontem"]) == 4
    assert n() == antes                                                   # refused before normalizing
    assert cli.main(["--config", cfg, "processar", "--em", "2026-09-29"]) == 0
    vig = mundo.con.execute("SELECT vigencia_em FROM derivacao_execucao ORDER BY id DESC LIMIT 1").fetchone()[0]
    assert vig == "2026-09-29T23:59:59-03:00"                             # the snapshot of 20h on the 29th is included
    did = mundo.con.execute("SELECT MAX(id) FROM derivacao_execucao").fetchone()[0]
    assert mundo.con.execute("SELECT COUNT(*) FROM rp_derivado WHERE derivacao_id=?", (did,)).fetchone()[0] == 1


# ------------------------------------------------------------------ NORM-02 and DET-01: RREO transcription
def _pdf(*textos):
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf
    doc = pymupdf.open()
    pg = doc.new_page(width=1000, height=600)
    for (x, y), t in textos:
        pg.insert_text((x, y), t, fontsize=7)
    return doc.tobytes()


ROTULOS_X = [("(a)", 300), ("(b)", 350), ("(c)", 400), ("(d)", 450), ("e=(a+b)", 500), ("(f)", 550), ("(g)", 600),
             ("(h)", 650), ("(i)", 700), ("(j)", 750), ("k=(f+g)", 800), ("L=(e+k)", 850)]


class _Captura:
    def executemany(self, sql, linhas):
        self.linhas = list(linhas)

        class R:
            rowcount = len(self.linhas)
        return R()


def _rreo(*numeros):
    textos = [((50, 40), "DEMONSTRATIVO JANEIRO A AGOSTO 2.026")] + [((x, 100), r) for r, x in ROTULOS_X]
    textos += [((50, 300), "TOTAL"), ((80, 300), "(III)")] + [((x, 300), n) for x, n in numeros]
    cap = _Captura()
    n = normalizar._rreo(cap, 1, 1, {"rotulo": "4º Bimestre"}, _pdf(*textos))
    return n, cap


def _rreo_completo(*extras):
    """Extractor v2 (09/10/2026): rows are transcribed whole, with the document's identities closing."""
    v = linha_rreo(a=123456, b=1000, c=500, f=2000, i=300)
    textos = CABECALHO_RREO + textos_da_linha(EXCETO_RREO, 200, v) + textos_da_linha(TOTAL_RREO, 300, v) + list(extras)
    cap = _Captura()
    return normalizar._rreo(cap, 1, 1, {"rotulo": "4º Bimestre"}, _pdf(*textos)), cap


def test_NORM02_um_numero_por_celula_e_transcrito():
    n, cap = _rreo_completo()
    assert n == 24 and ("TOTAL (III)", "a", 123456) in [(l[7], l[8], l[9]) for l in cap.linhas]


def test_NORM02_dois_numeros_diferentes_na_mesma_celula_nao_sao_descartados_em_silencio():
    # before v2 the message named the column; now the row has 13 numbers and is refused as a whole
    with pytest.raises(normalizar.LayoutDesconhecido, match=r"13 número\(s\).*transcrição parcial recusada"):
        _rreo_completo(((315, 300), "9.999,99"))


def test_DET01_mensagem_de_layout_desconhecido_igual_com_qualquer_PYTHONHASHSEED(tmp_path):
    pdf = tmp_path / "sem_colunas.pdf"
    pdf.write_bytes(_pdf(((50, 40), "DEMONSTRATIVO JANEIRO A AGOSTO 2.026"), ((300, 100), "(a)")))
    codigo = ("import sys; sys.path.insert(0, sys.argv[1]); from rp import normalizar\n"
              "try:\n    normalizar._rreo(None, 1, 1, {}, open(sys.argv[2], 'rb').read())\n"
              "except normalizar.LayoutDesconhecido as e:\n    print(e)")
    saidas = {subprocess.run([sys.executable, "-c", codigo, str(APP), str(pdf)], capture_output=True, text=True,
                             env={**os.environ, "PYTHONHASHSEED": str(s)}, check=True).stdout for s in (1, 2, 3, 4)}
    assert len(saidas) == 1 and "colunas não encontradas" in saidas.pop()


# ------------------------------------------------------------------ DER-01: movement only from a complete snapshot
def test_DER01_movimentacao_de_snapshot_incompleto_nao_entra_na_derivacao(mundo):
    mundo.catalogos({1: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1)], T0)
    lanc = {"data": "2025-03-01", "tipoLancamento": 40, "valor": 10.0, "exercicioPagamento": 2024, "noPagamento": 1}
    pagina = json.dumps({"content": [lanc], "totalElements": 2, "last": True}).encode()
    for status, uid in (("completa", "a" * 32), ("incompleta", "b" * 32)):
        gravar_snapshot(mundo.con, mundo.armazem, tipo="movimentacao", endpoint="/empenhos/detalhe/movimentacao",
                        parametros={"entidade": 1, "anoempenho": 2024, "empenho": 1, "size": 500}, coletada_em=T0,
                        origem_carimbo="relogio_coletor", status=status, snapshot_uid=uid,
                        coletor={"nome": "teste", "versao": "1", "sha256_codigo": None},
                        respostas=[{"url": "x", "http_status": 200, "corpo": pagina}])
    _, did = mundo.processar()
    por_status = dict(mundo.con.execute(
        "SELECT c.status, COUNT(*) FROM movimentacao_interpretada m JOIN resposta_bruta r ON r.id = m.resposta_id "
        "JOIN coleta c ON c.id = r.coleta_id WHERE m.derivacao_id=? GROUP BY 1", (did,)).fetchall())
    assert por_status == {"completa": 1}


# ------------------------------------------------------------------ DB-03: rule catalog code x database
def test_DB03_editar_regra_ja_gravada_e_recusado(mundo, monkeypatch):
    assert regras.conferir_catalogo(mundo.con) == []
    editada = [r if r[:2] != ("S1", 1) else (*r[:5], r[5] + " (editada)", r[6]) for r in regras.REGRAS]
    monkeypatch.setattr(regras, "REGRAS", editada)
    with pytest.raises(regras.CatalogoDivergente, match="regra S1 v1"):
        with mundo.con:
            regras.semear(mundo.con)


def test_DB03_parametro_ou_decisao_editados_sao_recusados(mundo, monkeypatch):
    p = {**regras.PARAMETROS, ("PAR-24", 1): {**regras.PARAMETROS[("PAR-24", 1)], "base_empenho_copia": 2500000}}
    monkeypatch.setattr(regras, "PARAMETROS", p)
    with pytest.raises(regras.CatalogoDivergente, match="parâmetros de PAR-24 v1"):
        regras.semear(mundo.con)
    monkeypatch.undo()
    ev = list(governanca.EVENTOS)
    ev[0] = (*ev[0][:6], ev[0][6] + " (editado)", *ev[0][7:])
    monkeypatch.setattr(governanca, "EVENTOS", ev)
    with pytest.raises(regras.CatalogoDivergente, match="decisão de CAT v1"):
        regras.semear(mundo.con)


def test_DB03_decisao_nova_acrescentada_e_aceita(mundo, monkeypatch):
    nova = ("RREO-COL", 2, "nao_recomendada", "FORTE EVIDÊNCIA", 0, None, "teste", "teste", "2099-01-01", "teste")
    monkeypatch.setattr(governanca, "EVENTOS", governanca.EVENTOS + [nova])
    with mundo.con:
        regras.semear(mundo.con)
    assert mundo.con.execute("SELECT COUNT(*) FROM regra_situacao WHERE decidido_em='2099-01-01'").fetchone()[0] == 1


def test_DB03_banco_criado_tem_o_catalogo_do_codigo(tmp_path):
    from rp import banco
    from rp.config import carregar
    cfg = carregar(dados_locais=tmp_path / "l", snapshots=tmp_path / "s", backups=tmp_path / "b")
    con = banco.abrir(cfg)
    assert regras.conferir_catalogo(con) == [] and Path(cfg.banco).exists()
    con.close()
