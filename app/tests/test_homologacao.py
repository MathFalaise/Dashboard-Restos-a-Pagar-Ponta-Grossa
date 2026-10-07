"""Homologation of the interface (sub-stage 04.6): situations the real data does not have or that do not depend on it.

* SINTETICO = invented records in a temporary database (fixture `mundo`).
* The tests over the real store live in test_homologacao_real.py.
Specification sections: 9 and 10 (data situation and entities), 11 and 12 (read-only), 4 (no formula in the
interface), 22 (portability), 27 (gates of a new load).
"""
import ast
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from conftest import COLETOR_SINTETICO, RAIZ_PROJETO, chamar, dados, ok, registro_sintetico as _reg

from rp import portoes
from rp.coletor import EP_RP
from rp.config import carregar
from rp.interface import Aplicacao
from rp.painel.consulta import SITUACOES_DO_DADO
from rp.snapshots import gravar_snapshot

APP = RAIZ_PROJETO / "app"
T0, T1 = "2026-09-29T20:00:00-03:00", "2026-09-30T10:00:00-03:00"


def sha(caminho):
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


def _incompleta(mundo, entidade, exercicio, data_final, quando):
    p = {"entidade": entidade, "exercicio": exercicio, "dataInicial": f"{exercicio}-01-01", "dataFinal": data_final,
         "size": 2000}
    corpo = {"content": [_reg(1, entidade=entidade)], "last": False, "totalElements": 5}
    return gravar_snapshot(mundo.con, mundo.armazem, tipo="rp_listagem", endpoint=EP_RP, parametros=p, coletada_em=quando,
                           origem_carimbo="relogio_coletor", status="incompleta", coletor=COLETOR_SINTETICO,
                           respostas=[{"url": "sintetico", "http_status": 200, "corpo": json.dumps(corpo).encode()}])


def _mundo_com_todas_as_situacoes(mundo):
    """Cut-off 2025-12-31 with one entity in each situation:
    1 existing data (and a newer unprocessed snapshot); 3 outside the 2025 catalog; 5 only an incomplete collection;
    8 never collected; 9 collected after processing; 15 existing with zero records."""
    mundo.catalogos({1: [2025], 3: [2024], 5: [2025], 8: [2025], 9: [2025], 15: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1, aproc=10.0)], T0)
    mundo.listagem(3, 2025, "2025-12-31", [_reg(7, entidade=3)], T0)
    mundo.listagem(15, 2025, "2025-12-31", [], T0)
    _incompleta(mundo, 5, 2025, "2025-12-31", T0)
    mundo.processar()
    mundo.listagem(9, 2025, "2025-12-31", [_reg(2, entidade=9)], T1)
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1, aproc=11.0)], T1)
    return Aplicacao(mundo.cfg.banco)


ESPERADO = {1: "com_dados", 3: "inexistente", 5: "incompleto", 8: "sem_coleta", 9: "nao_processado", 15: "sem_rp"}


# ================================================================== sections 9 and 10: data situation and entities
def test_SINTETICO_cada_situacao_do_dado_e_distinta_na_camada_painel(mundo):
    _mundo_com_todas_as_situacoes(mundo)
    with mundo.painel() as p:
        linhas = {l["entidade"]: l for l in p.entidades_do_corte(2025, "2025-12-31")["linhas"]}
        mun = p.indicadores(2025, "2025-12-31")
    assert {e: l["situacao_do_dado"]["codigo"] for e, l in linhas.items()} == ESPERADO
    for e, codigo in ESPERADO.items():
        assert linhas[e]["situacao_do_dado"]["texto"] == SITUACOES_DO_DADO[codigo]
        if codigo not in ("com_dados", "sem_rp"):
            assert linhas[e]["valores"] is None, e                 # never zero
    assert linhas[15]["valores"]["inscricao_total"] == 0 and linhas[15]["valores"]["registros"] == 0
    assert linhas[1]["retrato_mais_novo_nao_processado"] and not linhas[15]["retrato_mais_novo_nao_processado"]
    assert not mun["disponivel"]
    for trecho in ("corte não coletado para a(s) entidade(s) [8]", "coletado, mas ainda não processado para a(s) "
                   "entidade(s) [9]", "coleta incompleta ou com falha deste corte para a(s) entidade(s) [5]"):
        assert trecho in mun["motivo_indisponivel"], trecho


def test_SINTETICO_interface_mostra_cada_situacao_e_nunca_converte_em_zero(mundo):
    app = _mundo_com_todas_as_situacoes(mundo)
    corpo = ok(app, "/entidades", exercicio=2025, data_final="2025-12-31")
    for e, codigo in ESPERADO.items():
        assert f'id="situacao-{e}">{SITUACOES_DO_DADO[codigo]}' in corpo, e
    v = dados(corpo)
    for e in (3, 5, 8, 9):
        assert f'id="sem-valor-{e}"' in corpo and not any(k.startswith(f"ent-{e}-") for k in v)
    assert v["ent-15-total"] == 0 and v["ent-1-total"] == 1000
    assert "há retrato mais novo coletado, ainda não processado" in corpo
    for e, trecho in ((9, "corte coletado, mas ainda não processado"), (5, "dado indisponível"),
                      (8, "corte não coletado"), (3, "não é RP zero")):
        pagina = ok(app, "/resumo", exercicio=2025, data_final="2025-12-31", entidade=e)
        assert 'id="indisponivel"' in pagina and trecho in pagina, e
        assert "R$ 0,00" not in pagina and not re.search(r'<data class="valor', pagina), e
        lista = ok(app, "/empenhos", exercicio=2025, data_final="2025-12-31", entidade=e)
        assert 'id="indisponivel"' in lista and "R$ 0,00" not in lista, e
    zero = ok(app, "/resumo", exercicio=2025, data_final="2025-12-31", entidade=15)
    assert 'id="sem-rp"' in zero and dados(zero)["ind-inscricao_total"] == 0
    vazio = ok(app, "/empenhos", exercicio=2025, data_final="2025-12-31", entidade=15)
    assert 'id="sem-resultado"' in vazio and "zero registros" in vazio and "R$ 0,00" not in vazio


def test_SINTETICO_entidade_existente_sem_rp_e_diferente_de_inexistente_e_de_sem_coleta(mundo):
    mundo.catalogos({1: [2024, 2025], 15: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", [], T0)          # existed in 2025 and has no RP
    mundo.listagem(1, 2024, "2024-12-31", [_reg(1)], T0)
    mundo.processar()
    with mundo.painel() as p:
        a = {l["entidade"]: l["situacao_do_dado"]["codigo"] for l in p.entidades_do_corte(2025, "2025-12-31")["linhas"]}
        b = {l["entidade"]: l["situacao_do_dado"]["codigo"] for l in p.entidades_do_corte(2024, "2024-12-31")["linhas"]}
    assert a == {1: "sem_rp", 15: "sem_coleta"} and b == {1: "com_dados", 15: "inexistente"}


# ================================================================== sections 11 and 12: read-only
ESCRITAS = ["INSERT INTO evidencia_externa (tipo, descricao, registrada_em) VALUES ('nota', 'x', 'x')",
            "UPDATE rp_registro SET proc_c = 0", "DELETE FROM rp_derivado", "DELETE FROM coleta",
            "CREATE TABLE t (x)", "DROP TABLE rp_derivado", "ALTER TABLE rp_registro ADD COLUMN x INTEGER",
            "CREATE INDEX i_teste ON rp_registro (proc_c)", "PRAGMA user_version = 99", "VACUUM",
            "CREATE TEMP TABLE x AS SELECT * FROM coleta"]


def test_SINTETICO_banco_da_interface_so_permite_leitura(mundo):
    app = _mundo_com_todas_as_situacoes(mundo)
    mundo.con.commit()
    arquivo = mundo.cfg.banco
    antes, mtime = sha(arquivo), arquivo.stat().st_mtime_ns
    from rp.painel import Painel
    with Painel.abrir(arquivo) as p:
        assert p.con.execute("SELECT COUNT(*) FROM rp_registro").fetchone()[0] > 0         # SELECT allowed
        for sql in ESCRITAS:
            with pytest.raises(sqlite3.DatabaseError):
                p.con.execute(sql)
    for caminho, params in (("/", {}), ("/resumo", {}), ("/entidades", {}),
                            ("/empenhos", dict(exercicio=2025, data_final="2025-12-31")),
                            ("/retratos", {}), ("/reconciliacao", {}), ("/pares", {}), ("/metodologia", {})):
        chamar(app, caminho, **params)
    assert sha(arquivo) == antes and arquivo.stat().st_mtime_ns == mtime
    assert not [x for x in arquivo.parent.iterdir() if x.name.startswith(arquivo.name + "-")]   # no -wal/-journal


def test_interface_nao_carrega_coleta_nem_processamento():
    """Importing the interface loads no HTTP client, collector, normalizer, deriver, importer nor snapshot writing: the
    interface has no way to collect, process, derive or write a snapshot."""
    codigo = ("import sys, json; import rp.interface, rp.painel; "
              "print(json.dumps(sorted(m for m in sys.modules if m.split('.')[0] in ('rp', 'requests', 'pymupdf', 'fitz', "
              "'urllib3'))))")
    r = subprocess.run([sys.executable, "-c", codigo], cwd=APP, capture_output=True, text=True, check=True)
    carregados = set(json.loads(r.stdout))
    proibidos = {"rp.http", "rp.coletor", "rp.normalizar", "rp.derivar", "rp.importar", "rp.snapshots", "rp.execucoes",
                 "rp.evidencias", "requests", "pymupdf", "fitz", "urllib3"}
    assert not carregados & proibidos, carregados & proibidos


# ================================================================== section 4: the interface does not recreate formulas
def test_interface_nao_soma_nem_subtrai_valores_monetarios():
    """Every sum or difference of values comes from the panel layer: the interface has no arithmetic operation on a field
    in cents (key ending in _c) nor a call to sum()."""
    pasta = APP / "rp" / "interface"
    arquivos = [pasta / "formato.py", pasta / "aplicacao.py", *sorted((pasta / "paginas").glob("*.py"))]
    assert len(arquivos) > 3                            # the pages package was found
    for arq in arquivos:
        arvore = ast.parse(arq.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.BinOp) and isinstance(no.op, (ast.Add, ast.Sub)):
                for lado in (no.left, no.right):
                    chave = getattr(getattr(lado, "slice", None), "value", None)
                    assert not (isinstance(lado, ast.Subscript) and isinstance(chave, str) and chave.endswith("_c")), (
                        arq, no.lineno)
            if isinstance(no, ast.Call) and getattr(no.func, "id", None) == "sum":
                pytest.fail(f"{arq}:{no.lineno} usa sum()")
        assert "SELECT" not in arq.read_text(encoding="utf-8")


# ================================================================== section 17: search by commitment
def test_SINTETICO_busca_por_empenho_e_parametros_invalidos(mundo):
    mundo.catalogos({1: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1, ano=2024, aproc=10.0), _reg(2, ano=2023, aproc=20.0),
                                           _reg(1, ano=2023, aproc=30.0)], T0)
    mundo.processar()
    app = Aplicacao(mundo.cfg.banco)
    base = dict(exercicio=2025, data_final="2025-12-31")
    assert dados(ok(app, "/empenhos", empenho=1, **base))["tot-registros"] == 2
    v = dados(ok(app, "/empenhos", empenho=1, anoempenho=2023, **base))
    assert (v["tot-registros"], v["tot-aproc"]) == (1, 3000)
    assert dados(ok(app, "/empenhos", anoempenho=2023, **base))["tot-aproc"] == 5000
    for params in (dict(empenho="abc"), dict(anoempenho="20x5"), dict(anoempenho=1800), dict(empenho=-1)):
        status, _, _ = chamar(app, "/empenhos", **base, **params)
        assert status == "400 Bad Request", params


# ================================================================== section 22: portability
def test_configuracao_versionada_sem_caminho_da_maquina_do_desenvolvedor():
    c = tomllib.loads((APP / "config.toml").read_text(encoding="utf-8"))["caminhos"]
    for chave in ("dados_locais", "snapshots", "backups"):
        assert not Path(c[chave]).is_absolute() and not re.match(r"[A-Za-z]:", c[chave]), chave
    padrao = re.compile(r"[A-Za-z]:[\\/]+Users|/home/|maped", re.I)
    arquivos = list((APP / "rp").rglob("*.py")) + list((APP / "rp").rglob("*.css")) + [
        APP / "config.toml", APP / "requirements.txt", APP / "requirements-dev.txt"]
    achados = [str(a) for a in arquivos if padrao.search(a.read_text(encoding="utf-8"))]
    assert not achados, achados


def test_pasta_local_configuravel_por_variavel_de_ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("RP_DADOS_LOCAIS", str(tmp_path / "dados"))
    assert carregar().dados_locais == tmp_path / "dados"
    assert carregar().banco == tmp_path / "dados" / "banco" / "restos_a_pagar.sqlite"
    monkeypatch.delenv("RP_DADOS_LOCAIS")
    assert carregar().dados_locais == Path.home() / "RestosAPagar_local"
    outro = tmp_path / "cfg" / "config.toml"            # relative path: from the file's folder
    outro.parent.mkdir()
    outro.write_text((APP / "config.toml").read_text(encoding="utf-8").replace('"~/RestosAPagar_local"', '"local"'),
                     encoding="utf-8")
    cfg = carregar(outro)
    assert cfg.dados_locais == (tmp_path / "cfg" / "local").resolve()
    assert cfg.snapshots == (tmp_path / "data" / "snapshots").resolve()     # "../data/snapshots" since 06/10/2026


# ================================================================== section 27: gates of a new load
def test_SINTETICO_portoes_da_carga_nova(mundo, tmp_path):
    mundo.catalogos({1: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1)], T0)
    mundo.processar()
    mundo.con.commit()
    arq = tmp_path / "referencia.json"
    ref = portoes.gravar_referencia(mundo.cfg.banco, arq)
    with pytest.raises(FileExistsError):                 # the reference is never overwritten
        portoes.gravar_referencia(mundo.cfg.banco, arq)
    antes = sha(mundo.cfg.banco)
    r = portoes.avaliar(mundo.cfg.banco, mundo.armazem, ref)
    assert r["apto"] and all(p["ok"] for p in r["portoes"] if p["ok"] is not None)
    assert sha(mundo.cfg.banco) == antes                  # avaliar only reads
    ok_ = lambda r: {p["id"]: p["ok"] for p in r["portoes"]}

    mundo.listagem(1, 2025, "2025-12-31", [_reg(1, aproc=5.0)], T1)          # new load, not yet processed
    r = portoes.avaliar(mundo.cfg.banco, mundo.armazem, ref)
    assert not r["apto"] and ok_(r)["normalizacao"] is False and ok_(r)["camada_bruta_preservada"] is True
    mundo.processar()
    assert portoes.avaliar(mundo.cfg.banco, mundo.armazem, ref)["apto"]

    _incompleta(mundo, 1, 2025, "2025-06-30", T1)                            # newer snapshot incomplete
    mundo.processar()
    r = portoes.avaliar(mundo.cfg.banco, mundo.armazem, ref)
    assert not r["apto"] and ok_(r)["coleta_completa"] is False

    adulterada = dict(ref, hash_respostas="0" * 64)
    assert ok_(portoes.avaliar(mundo.cfg.banco, mundo.armazem, adulterada))["camada_bruta_preservada"] is False
    sem_ref = portoes.avaliar(mundo.cfg.banco, mundo.armazem)
    assert ok_(sem_ref)["camada_bruta_preservada"] is None and ok_(sem_ref)["testes"] is None
