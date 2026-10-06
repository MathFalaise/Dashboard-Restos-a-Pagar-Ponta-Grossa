"""Gates of stage 04.3: migration with backup, safe deletion of runs, old x new snapshots of the same cut-off
('as it was on'), RREO with an unknown layout and idempotent import."""
import json
import sqlite3

import pytest
from conftest import RAIZ_PROJETO

from rp import banco, consultas, derivar, execucoes, importar, normalizar
from rp.armazem import Armazem
from rp.config import carregar
from rp.snapshots import gravar_snapshot

COL = {"nome": "teste", "versao": "1", "sha256_codigo": None}
P = {"entidade": 998, "exercicio": 2026, "dataInicial": "2026-01-01", "dataFinal": "2026-12-31", "size": 2000}


def _loja(tmp_path):
    cfg = carregar(dados_locais=tmp_path / "l", snapshots=tmp_path / "s", backups=tmp_path / "b")
    return cfg, banco.abrir(cfg), Armazem(cfg.snapshots)


def _listagem(con, armazem, quando, aproc):
    reg = {k: 0 for k in normalizar.DINHEIRO}
    reg.update({"entidade": 998, "anoempenho": 2025, "empenho": 7, "aproc": aproc})
    corpo = json.dumps({"content": [reg], "last": True, "totalElements": 1}).encode()
    return gravar_snapshot(con, armazem, tipo="rp_listagem", endpoint="/x", parametros=P, coletada_em=quando,
                           origem_carimbo="relogio_coletor", status="completa", coletor=COL,
                           respostas=[{"url": "x", "http_status": 200, "corpo": corpo}])


# ------------------------------------------------------------------ migration
def test_banco_novo_nasce_na_versao_atual(tmp_path):
    _, con, _ = _loja(tmp_path)
    esperado = [(v, None) for v in range(banco.VERSAO_BASE, banco.VERSAO_ESQUEMA + 1)]   # v2 base + all migrations
    assert con.execute("SELECT versao, backup_antes FROM esquema_versao ORDER BY versao").fetchall() == esperado


def test_migracao_v2_para_v3_faz_backup_antes_e_preserva_dados(tmp_path):
    cfg = carregar(dados_locais=tmp_path / "l", snapshots=tmp_path / "s", backups=tmp_path / "b")
    arq = tmp_path / "v2.sqlite"
    c = sqlite3.connect(arq)  # database at v2, like the one of 04.1/04.2
    c.executescript(banco.ESQUEMA.read_text(encoding="utf-8"))
    c.execute("INSERT INTO esquema_versao VALUES (2, 'v2', '2026-09-29T21:00:00-03:00', NULL)")
    c.execute("INSERT INTO normalizacao_execucao (normalizador_versao, executada_em) VALUES ('x', 'y')")
    c.execute("INSERT INTO derivacao_execucao (normalizacao_id, derivador_versao, regras_json, executada_em) VALUES (1,'x','[]','y')")
    c.commit()
    c.close()
    con = banco.abrir(cfg, arq)
    (v, backup_antes), = con.execute("SELECT versao, backup_antes FROM esquema_versao WHERE versao=3").fetchall()
    assert f"antes-migracao-v2-v{banco.VERSAO_ESQUEMA}" in backup_antes and (cfg.backups / backup_antes.split("\\")[-1].split("/")[-1]).exists()
    assert con.execute("SELECT vigencia_em FROM derivacao_execucao WHERE id=1").fetchone() == (None,)
    antigo = sqlite3.connect(backup_antes)  # the backup is the database BEFORE the change
    assert "vigencia_em" not in [r[1] for r in antigo.execute("PRAGMA table_info(derivacao_execucao)")]


# ------------------------------------------------------------------ safe deletion
def _duas_execucoes(tmp_path):
    cfg, con, armazem = _loja(tmp_path)
    _listagem(con, armazem, "2026-09-30T10:00:00-03:00", 10)
    n1, _ = normalizar.normalizar(con)
    d1 = derivar.derivar(con, n1)
    n2, _ = normalizar.normalizar(con)
    d2 = derivar.derivar(con, n2)
    return cfg, con, armazem, (n1, d1, n2, d2)


def test_exclusao_recusa_o_que_nao_esta_claramente_identificado(tmp_path):
    cfg, con, _, (n1, d1, n2, d2) = _duas_execucoes(tmp_path)
    antes = execucoes.listar(con)
    casos = [("derivacao", d1, d1 + 100, "não confere"),         # wrong confirmation
             ("derivacao", 999, 999, "não existe"),                # nonexistent id
             ("normalizacao", n1, n1, "derivações dependentes"),   # still used by a derivation
             ("derivacao", d2, d2, "mais recente"),                # run in use
             ("outra", 1, 1, "tipo desconhecido")]
    for tipo, ident, conf, msg in casos:
        with pytest.raises(execucoes.ExclusaoRecusada, match=msg):
            execucoes.apagar(con, cfg, tipo, ident, conf)
    assert execucoes.listar(con) == antes  # nothing was deleted


def test_exclusao_de_execucao_inteira_com_backup_e_verificacao(tmp_path):
    cfg, con, armazem, (n1, d1, n2, d2) = _duas_execucoes(tmp_path)
    h2 = con.execute("SELECT hash_resultado FROM derivacao_execucao WHERE id=?", (d2,)).fetchone()[0]
    r = execucoes.apagar(con, cfg, "derivacao", d1, d1)
    assert r["camada0_intacta"] and all(v == 0 for v in r["restantes"].values())
    nome = r["backup"].replace("\\", "/").split("/")[-1]
    assert r["apagado"]["linhas"]["rp_derivado"] == 1 and (cfg.backups_operacionais / nome).exists()
    assert not (cfg.backups / nome).exists()  # the operational backup stays outside the synced folder
    r = execucoes.apagar(con, cfg, "normalizacao", n1, n1)  # now without dependents
    assert r["camada0_intacta"] and r["restantes"]["rp_registro"] == 0
    assert con.execute("SELECT hash_resultado FROM derivacao_execucao WHERE id=?", (d2,)).fetchone()[0] == h2  # the other one intact
    assert derivar.hash_resultado(con, d2) == h2
    assert banco.verificar(con, armazem) == []


def test_backups_operacionais_tem_retencao_e_os_demais_nao(tmp_path):
    cfg, con, _ = _loja(tmp_path)
    import time
    for i in range(5):
        banco.backup(con, cfg, f"antes-apagar-derivacao-{i}", operacional=True)
        banco.backup(con, cfg, f"manual-{i}")
        time.sleep(1.05)  # per-second timestamp
    assert len(list(cfg.backups_operacionais.glob("*.sqlite"))) == 3
    assert len(list(cfg.backups.glob("*.sqlite"))) == 5  # non-operational backups are never deleted


def test_compactar_nao_altera_dados(tmp_path):
    cfg, con, armazem, (n1, d1, n2, d2) = _duas_execucoes(tmp_path)
    h = derivar.hash_resultado(con, d2)
    execucoes.apagar(con, cfg, "derivacao", d1, d1)
    antes, depois = banco.compactar(con, cfg.banco)
    assert depois <= antes and derivar.hash_resultado(con, d2) == h and banco.verificar(con, armazem) == []


# ------------------------------------------------------------------ old x new snapshots of the same cut-off
def test_snapshot_antigo_e_coleta_nova_do_mesmo_corte_sao_independentes(tmp_path):
    cfg, con, armazem = _loja(tmp_path)
    velho = _listagem(con, armazem, "2026-09-29T20:00:00-03:00", 100)   # e.g. imported from stage 02
    manifesto_velho = (armazem.raiz / velho["manifesto"]).read_bytes()
    novo = _listagem(con, armazem, "2026-09-30T10:00:00-03:00", 80)     # new collection, changed base
    assert velho["snapshot_uid"] != novo["snapshot_uid"]
    assert (armazem.raiz / velho["manifesto"]).read_bytes() == manifesto_velho  # the old one was not touched
    nid, _ = normalizar.normalizar(con)
    d_antes = derivar.derivar(con, nid, em="2026-09-29T23:59:59-03:00")
    d_hoje = derivar.derivar(con, nid)
    val = lambda d: con.execute("SELECT valor_c, coletas_json FROM visao_valor v JOIN regra g ON g.id=v.regra_agregacao_id "
                                "WHERE derivacao_id=? AND visao='entidade' AND componente='g' AND g.versao=1", (d,)).fetchone()
    assert val(d_antes) == (10000, json.dumps([velho["snapshot_uid"]]))
    assert val(d_hoje) == (8000, json.dumps([novo["snapshot_uid"]]))
    assert con.execute("SELECT vigencia_em FROM derivacao_execucao WHERE id=?", (d_antes,)).fetchone()[0] == "2026-09-29T23:59:59-03:00"
    c1, c2 = (h[0] for h in consultas.historico(con, 998, 2026, "2026-01-01", "2026-12-31"))
    assert consultas.diferencas(con, nid, c1, c2)["alterados"] == [((998, 2025, 7), "aproc_c", 10000, 8000)]


# ------------------------------------------------------------------ RREO with an unknown layout
def test_rreo_com_layout_desconhecido_nao_derruba_e_fica_registrado(tmp_path):
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "RELATORIO EM LAYOUT NOVO SEM AS COLUNAS CONHECIDAS")
    pdf = doc.tobytes()
    cfg, con, armazem = _loja(tmp_path)
    _listagem(con, armazem, "2026-09-30T10:00:00-03:00", 10)
    gravar_snapshot(con, armazem, tipo="rreo_pdf", endpoint="/api/files/arquivo/1", coletor=COL, status="completa",
                    parametros={"id_arquivo": 1, "exercicio": 2026, "rotulo": "4º Bimestre"}, origem_carimbo="relogio_coletor",
                    coletada_em="2026-09-30T10:00:01-03:00", respostas=[{"url": "x", "http_status": 200, "corpo": pdf}])
    nid, resumo = normalizar.normalizar(con)
    assert len(resumo["problemas"]) == 1 and resumo["rp_registro"] == 1  # the rest was normalized
    assert "LayoutDesconhecido" in json.loads(con.execute("SELECT observacao FROM normalizacao_execucao WHERE id=?", (nid,)).fetchone()[0])["problemas"][0]["erro"]
    did = derivar.derivar(con, nid)
    assert con.execute("SELECT COUNT(*) FROM verificacao WHERE derivacao_id=? AND descricao LIKE 'RREO sem valores extraídos%'", (did,)).fetchone()[0] == 1


def test_nova_normalizacao_nao_sobrescreve_extracao_anterior(producao):
    con = producao["con"]
    q = "SELECT coleta_id, linha, coluna, valor_c, extrator_versao FROM rreo_valor WHERE normalizacao_id=? ORDER BY 1,2,3"
    antes = con.execute(q, (producao["nid"],)).fetchall()
    normalizar.normalizar(con)
    assert con.execute(q, (producao["nid"],)).fetchall() == antes and len(antes) == 517


# ------------------------------------------------------------------ idempotent import
def test_importar_de_novo_nao_duplica_nada(producao):
    con = producao["con"]
    antes = con.execute("SELECT COUNT(*) FROM coleta").fetchone()[0]
    r = importar.importar_etapas_anteriores(con, producao["armazem"], RAIZ_PROJETO)
    assert all(v == 0 for v in r.values()) and con.execute("SELECT COUNT(*) FROM coleta").fetchone()[0] == antes == 197
