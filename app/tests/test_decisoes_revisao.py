"""Decisoes do responsavel sobre as pendencias da revisao critica (06/10/2026): D1, D2, D4, D5, D6 e D7.
SINTETICO = banco temporario com registros inventados (fixture `mundo`) ou arquivos inventados em tmp_path."""
import gzip
import os
import shutil
import sqlite3
import subprocess
import time
from datetime import date

import pytest
from conftest import RAIZ_PROJETO

from rp import banco, cli
from rp.config import carregar

APP = RAIZ_PROJETO / "app"


def _cfg(tmp_path):
    return carregar(dados_locais=tmp_path / "l", snapshots=tmp_path / "s", backups=tmp_path / "b")


# ------------------------------------------------------------------ D6: retencao sem apagar
def test_D6_comprimir_backup_devolve_os_mesmos_bytes_e_nao_sobrescreve(tmp_path):
    arq = tmp_path / "x.sqlite"
    conteudo = os.urandom(3 << 20) + b"fim"            # SINTETICO, maior que um bloco de leitura
    arq.write_bytes(conteudo)
    gz = banco.comprimir_backup(arq)
    assert gz.name == "x.sqlite.gz" and not arq.exists()
    assert gzip.decompress(gz.read_bytes()) == conteudo
    arq.write_bytes(b"outro")
    with pytest.raises(FileExistsError):
        banco.comprimir_backup(arq)
    assert arq.read_bytes() == b"outro" and gzip.decompress(gz.read_bytes()) == conteudo   # nada foi tocado
    assert sorted(p.name for p in tmp_path.iterdir()) == ["x.sqlite", "x.sqlite.gz"]       # nem temporario


def test_D6_retencao_comprime_o_backup_antigo_em_vez_de_apagar(tmp_path):
    cfg = _cfg(tmp_path)
    con = banco.abrir(cfg)
    feitos = []
    for i in range(5):
        feitos.append(banco.backup(con, cfg, f"antes-apagar-{i}", operacional=True))
        time.sleep(1.05)                                # carimbo por segundo
    pasta = cfg.backups_operacionais
    assert sorted(p.name for p in pasta.glob("*.sqlite")) == [p.name for p in feitos[2:]]
    gz = sorted(pasta.glob("*.sqlite.gz"))
    assert [p.name for p in gz] == [p.name + ".gz" for p in feitos[:2]]
    restaurado = tmp_path / "restaurado.sqlite"
    restaurado.write_bytes(gzip.decompress(gz[0].read_bytes()))
    c = sqlite3.connect(restaurado)
    assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert c.execute("SELECT COUNT(*) FROM regra").fetchone()[0] == con.execute("SELECT COUNT(*) FROM regra").fetchone()[0]
    c.close()


def test_D6_comprimir_backups_lista_antes_e_mantem_os_recentes(tmp_path):
    cfg = _cfg(tmp_path)
    pasta = cfg.backups_operacionais
    pasta.mkdir(parents=True)
    nomes = [f"2026093{i}-000000_antes-apagar-{i}.sqlite" for i in range(6)]
    for n in nomes:
        (pasta / n).write_bytes(b"SQLite format 3\x00" + n.encode() * 1000)   # SINTETICO
    (pasta / "PRESERVAR.txt").write_text(nomes[5] + "\n", encoding="utf-8")   # o mais novo, mas preservado
    simulado = banco.comprimir_backups_operacionais(cfg, manter=3, simular=True)
    assert [x["arquivo"] for x in simulado] == [nomes[0], nomes[1], nomes[5]]
    assert sorted(p.name for p in pasta.glob("*.sqlite")) == sorted(nomes)       # simular nao toca em nada
    feito = banco.comprimir_backups_operacionais(cfg, manter=3, simular=False)
    assert [x["arquivo"] for x in feito] == [nomes[0] + ".gz", nomes[1] + ".gz", nomes[5] + ".gz"]
    assert sorted(p.name for p in pasta.glob("*.sqlite")) == nomes[2:5]          # os 3 recentes da retencao
    assert all(x["bytes_depois"] < x["bytes_antes"] for x in feito)
    assert gzip.decompress((pasta / (nomes[5] + ".gz")).read_bytes()) == b"SQLite format 3\x00" + nomes[5].encode() * 1000


def test_D6_logs_de_mais_de_90_dias_saem_e_o_resto_fica(tmp_path):
    for n in ("rp-2026-01-01.log", "rp-2026-07-08.log", "rp-2026-07-07.log", "rp-2026-10-06.log", "outro.log",
              "rp-sem-data.log"):
        (tmp_path / n).write_text("x", encoding="utf-8")
    removidos = cli.podar_logs(tmp_path, date(2026, 10, 6))
    assert removidos == ["rp-2026-01-01.log", "rp-2026-07-07.log"]                 # 91 e 278 dias
    assert sorted(p.name for p in tmp_path.iterdir()) == ["outro.log", "rp-2026-07-08.log", "rp-2026-10-06.log",
                                                         "rp-sem-data.log"]


def test_D6_espaco_por_pasta(tmp_path):
    cfg = _cfg(tmp_path)
    con = banco.abrir(cfg)
    banco.backup(con, cfg, "manual")
    e = banco.espaco(cfg)
    assert set(e) == {"banco", "armazem", "backups", "backups_operacionais", "logs"}
    assert e["banco"] == cfg.banco.stat().st_size and e["backups"] > 0 and e["armazem"] == 0


# ------------------------------------------------------------------ D2: bruto novo fora do Git
@pytest.mark.skipif(shutil.which("git") is None or not (RAIZ_PROJETO / ".git").exists(), reason="sem git/repositorio")
def test_D2_snapshot_novo_e_ignorado_e_os_versionados_continuam_no_git():
    def git(*a):
        return subprocess.run(["git", *a], cwd=RAIZ_PROJETO, capture_output=True, text=True, encoding="utf-8")
    assert git("check-ignore", "-q", "--no-index", "snapshots/coletas/2099/01/novo.json").returncode == 0
    assert git("check-ignore", "-q", "--no-index", "snapshots/objetos/ab/" + "a" * 64 + ".zlib").returncode == 0
    versionados = git("ls-files", "snapshots/coletas").stdout.split()
    assert len(versionados) >= 466        # a base homologada continua versionada


# ------------------------------------------------------------------ D1: bloquear e dizer como recoletar
def test_D1_portao_da_chave_repetida_diz_o_comando_de_recoleta_e_nao_recoleta_sozinho(mundo):
    from test_revisao_duplicidade import R1, R2, T1, T2, _cenario, _portao
    snaps, _, _ = _cenario(mundo, [(T1, [R1, R2]), (T2, [R1, R2, R2])])
    coletas = mundo.con.execute("SELECT COUNT(*) FROM coleta").fetchone()[0]
    p, r = _portao(mundo, "retrato_sem_chave_repetida")
    assert p["ok"] is False and not r["apto"]
    uid = snaps[1]["snapshot_uid"]
    assert p["detalhe"]["recoletar"] == [f"python -m rp recoletar --snapshot {uid}"]
    assert "MAIS TARDE" in p["detalhe"]["nota"] and "segunda leitura" in p["detalhe"]["nota"]
    assert mundo.con.execute("SELECT COUNT(*) FROM coleta").fetchone()[0] == coletas    # nada foi coletado sozinho


# ------------------------------------------------------------------ D5: trava com hashes
def _trava():
    import re
    texto = (APP / "requirements-lock.txt").read_text(encoding="utf-8").replace("\\" + "\n", " ")   # continuacao
    pacotes = {}
    for linha in texto.splitlines():
        linha = linha.split("#", 1)[0].strip()
        if linha:
            m = re.match(r"^([A-Za-z0-9_.-]+)==([^\s]+)((?:\s+--hash=sha256:[0-9a-f]{64})*)\s*$", linha)
            assert m, f"linha fora do formato: {linha!r}"
            pacotes[m.group(1).lower()] = (m.group(2), re.findall(r"[0-9a-f]{64}", m.group(3)))
    return pacotes


def test_D5_todo_pacote_da_trava_tem_hash_e_as_versoes_batem_com_os_requirements():
    trava = _trava()
    assert trava and all(hashes for _, hashes in trava.values()), "pacote sem hash na trava"
    for arq in ("requirements.txt", "requirements-dev.txt"):
        for linha in (APP / arq).read_text(encoding="utf-8").splitlines():
            linha = linha.split("#", 1)[0].strip()
            if linha and not linha.startswith("-r"):
                nome, versao = linha.split("==")
                assert trava[nome.lower()][0] == versao, (arq, nome)


# ------------------------------------------------------------------ D4: integridade relacional por gatilhos (v5)
def _processado(mundo):
    from conftest import registro_sintetico as _reg
    mundo.catalogos({1: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1), _reg(2, proc=50.0)], "2026-09-29T20:00:00-03:00")
    nid, did = mundo.processar()
    mundo.con.commit()
    return nid, did


def test_D4_esquema_v5_tem_os_gatilhos_e_a_impressao_confere(mundo):
    con = mundo.con
    assert banco.versao_esquema(con) == banco.VERSAO_ESQUEMA == 5
    assert banco.impressao_esquema(con) == banco.IMPRESSAO_ESQUEMA[5]
    nomes = {n for (n,) in con.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'ri_%'")}
    assert len(nomes) == 18 and "ri_rp_derivado_insert" in nomes and "ri_rp_registro_delete" in nomes


@pytest.mark.parametrize("sql, mensagem", [
    ("INSERT INTO anomalia VALUES ((SELECT MAX(id) FROM derivacao_execucao), (SELECT id FROM regra WHERE "
     "codigo='ANOM-REG'), 'LIQ-NEG', 999999, 1, 2024, 1, NULL)", "coleta inexistente"),
    ("INSERT INTO rp_derivado SELECT derivacao_id, 999999, indice, coleta_id, entidade, anoempenho, empenho, categoria, "
     "faixa_processado, faixa_nao_processado, s1_saldo_total_c, s2_a_liquidar_c, s3_liquidado_a_pagar_c, "
     "cancel_processado_c, cancel_nao_processado_c FROM rp_derivado LIMIT 1", "rp_derivado sem o registro"),
    ("UPDATE rp_derivado SET coleta_id = 999999 WHERE rowid = (SELECT MIN(rowid) FROM rp_derivado)",
     "rp_derivado sem o registro"),
    ("UPDATE visao_valor SET coletas_json = '[\"nao-existe\"]' WHERE id = (SELECT MIN(id) FROM visao_valor)",
     "snapshot inexistente"),
    ("UPDATE derivacao_execucao SET regras_json = '[999999]' WHERE id = (SELECT MAX(id) FROM derivacao_execucao)",
     "regra inexistente"),
    ("DELETE FROM rp_registro WHERE rowid = (SELECT MIN(rowid) FROM rp_registro)", "apague antes as derivacoes"),
])
def test_D4_linha_orfa_e_recusada_na_gravacao(mundo, sql, mensagem):
    _processado(mundo)
    with pytest.raises(sqlite3.IntegrityError, match=mensagem):
        with mundo.con:
            mundo.con.execute(sql)


def test_D4_mudar_valor_continua_permitido_e_o_portao_e_quem_acusa(mundo):
    from rp import portoes
    _, did = _processado(mundo)
    with mundo.con:          # UPDATE de valor nao passa pelos gatilhos de ligacao: e o hash recalculado que acusa
        mundo.con.execute("UPDATE visao_valor SET valor_c = valor_c + 1 WHERE derivacao_id=? AND componente='S1'", (did,))
    r = portoes.avaliar(mundo.cfg.banco, mundo.armazem)
    p = next(x for x in r["portoes"] if x["id"] == "hash_resultado_confere")
    assert p["ok"] is False


def test_D4_banco_v4_migra_para_v5_com_backup_e_sem_mudar_linha(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(banco, "VERSAO_ESQUEMA", 4)        # um banco v4 de verdade, como o ativo antes da v5
    con = banco.abrir(cfg)
    assert banco.versao_esquema(con) == 4 and banco.impressao_esquema(con) == banco.IMPRESSAO_ESQUEMA[4]
    tabelas = [t for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    antes = {t: con.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in tabelas if t != "regra_situacao"}
    situacoes = con.execute("SELECT * FROM regra_situacao ORDER BY id").fetchall()
    con.close()
    monkeypatch.undo()
    novo = banco.abrir(cfg)                                # migra para a v5, com backup antes
    assert banco.versao_esquema(novo) == 5 and banco.impressao_esquema(novo) == banco.IMPRESSAO_ESQUEMA[5]
    depois = {t: novo.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in antes}
    assert {t: v for t, v in depois.items() if t != "esquema_versao"} == {t: v for t, v in antes.items()
                                                                          if t != "esquema_versao"}
    assert [r[:-2] for r in novo.execute("SELECT * FROM regra_situacao ORDER BY id")] == situacoes   # + 2 colunas vazias
    (backup,) = novo.execute("SELECT backup_antes FROM esquema_versao WHERE versao = 5").fetchone()
    assert "antes-migracao-v4-v5" in backup
    novo.close()


# ------------------------------------------------------------------ D7: promocao em dois trilhos
TESTE_OK = "tests/test_decisoes_revisao.py::test_D6_espaco_por_pasta"


def _decidir(con, **kw):
    from rp import governanca
    base = dict(codigo="PAR-24", versao=1, situacao="operacional", status_evidencia="FORTE EVIDÊNCIA",
                compoe_indicador_publicado=False, motivo="teste SINTETICO", fonte="relatorio X", origem="teste",
                decidido_em="2026-10-07T10:00:00-03:00")
    base.update(kw)
    return governanca.registrar_decisao(con, **base)


def test_D7_promocao_exige_teste_de_regressao_existente(mundo):
    from rp.governanca import DecisaoInvalida
    for teste in (None, "tests/nao_existe.py::test_x", "tests/test_decisoes_revisao.py::test_nao_existe", "rp/cli.py::main"):
        with pytest.raises(DecisaoInvalida, match="teste de regressao"):
            _decidir(mundo.con, teste_regressao=teste)
    with pytest.raises(DecisaoInvalida, match="fonte"):
        _decidir(mundo.con, teste_regressao=TESTE_OK, fonte=" ")
    assert _decidir(mundo.con, teste_regressao=TESTE_OK)            # trilho 1: nao compoe indicador


def test_D7_regra_do_indicador_exige_conferencia_ou_ressalva_que_aparece_na_metodologia(mundo):
    from rp import governanca
    from rp.governanca import DecisaoInvalida
    with pytest.raises(DecisaoInvalida, match="conferencia independente"):
        _decidir(mundo.con, codigo="S1", compoe_indicador_publicado=True, teste_regressao=TESTE_OK)
    _decidir(mundo.con, codigo="S1", compoe_indicador_publicado=True, teste_regressao=TESTE_OK,
             ressalva="e-SIC sem resposta em 30 dias")
    g = governanca.situacao_atual(mundo.con)[("S1", 1)]
    assert g["situacao"] == "operacional" and g["ressalva"] == "e-SIC sem resposta em 30 dias"
    assert g["historico"][-1]["teste_regressao"] == TESTE_OK
    from rp.interface import formato
    assert "operacional com ressalva: e-SIC sem resposta em 30 dias" in formato.situacao_regra("S1 v1", "operacional",
                                                                                               g["ressalva"])
    with pytest.raises(DecisaoInvalida, match="ressalva so existe"):
        _decidir(mundo.con, situacao="experimental", ressalva="x")


def test_D7_o_banco_recusa_promocao_fora_dos_criterios_mesmo_sem_o_codigo(mundo):
    rid = mundo.con.execute("SELECT id FROM regra WHERE codigo='S1' AND versao=1").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError, match="decisao D7"):
        with mundo.con:
            mundo.con.execute("INSERT INTO regra_situacao (regra_id, situacao, status_evidencia, compoe_indicador_publicado, "
                              "motivo, fonte, decidido_em, origem_decisao) VALUES (?, 'operacional', 'CONFIRMADO', 1, "
                              "'x', 'y', '2026-10-07', 'z')", (rid,))


def test_D7_nenhum_evento_versionado_promove_depois_da_politica():
    from rp import governanca
    assert not [e for e in governanca.EVENTOS
                if e[2] == "operacional" and e[8] >= banco.POLITICA_PROMOCAO_DESDE], \
        "promocao nova vai por registrar_decisao (criterios D7), nao por evento versionado"


def test_D7_comando_decidir_regra(mundo, tmp_path, monkeypatch, capsys):
    from test_auditoria_processamento import _config_do_mundo
    monkeypatch.delenv("RP_DADOS_LOCAIS", raising=False)
    mundo.con.close()
    cfg = _config_do_mundo(mundo, tmp_path)
    args = ["--config", cfg, "decidir-regra", "--codigo", "PAR-24", "--versao", "1", "--situacao", "operacional",
            "--status", "FORTE EVIDÊNCIA", "--motivo", "teste SINTETICO", "--fonte", "relatorio X"]
    assert cli.main(args) == 4 and "teste de regressao" in capsys.readouterr().out
    assert cli.main(args + ["--teste", TESTE_OK]) == 0
    assert '"situacao": "operacional"' in capsys.readouterr().out
