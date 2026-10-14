"""Privacy guard of the public repository (corrective audit of 13/10/2026, phase P0).

The raw API responses, the raw data of stages 01/02 and the database copies hold creditor records (names, masked
CPF). They live only in the private storage of config.toml [caminhos]. These tests fail if any of them is versioned
again, if a versioned text file carries a real masked CPF or a full CPF with valid check digits, or if the config
points the private folders back into the repository. They need git and the repository, not the raw data.
"""
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from conftest import RAIZ_PROJETO
from rp import privado
from rp.banco import BancoEmPastaSincronizada, em_pasta_sincronizada, recusar_pastas_privadas_sincronizadas
from rp.config import carregar

TEM_GIT = shutil.which("git") is not None and (RAIZ_PROJETO / ".git").exists()


def _versionados():
    r = subprocess.run(["git", "ls-files", "-z"], cwd=RAIZ_PROJETO, capture_output=True, check=True)
    return [p for p in r.stdout.decode("utf-8").split("\0") if p]


@pytest.mark.skipif(not TEM_GIT, reason="sem git/repositorio")
def test_nenhum_bruto_ou_banco_versionado():
    proibidos = [p for p in _versionados() if privado.caminho_privado(p)]
    assert not proibidos, proibidos[:20]


@pytest.mark.skipif(not TEM_GIT, reason="sem git/repositorio")
def test_nenhum_cpf_real_em_arquivo_versionado():
    achados = {}
    for rel in _versionados():
        p = RAIZ_PROJETO / rel
        if not p.is_file() or p.stat().st_size > 20 * 1024 * 1024:
            continue
        try:
            texto = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        a = privado.achados_pessoais(texto)
        if a["cpf_mascarado"] or a["cpf_completo"]:
            achados[rel] = a
    assert not achados, achados


@pytest.mark.skipif(not TEM_GIT, reason="sem git/repositorio")
def test_gitignore_cobre_as_pastas_privadas():
    for rel in ("data/snapshots/x.json", "data/stage01-samples/x.json", "data/stage02-raw/api/x.json",
                "data/backups/x.sqlite", "app/qualquer.sqlite", "objetos/ab/x.zlib"):
        r = subprocess.run(["git", "check-ignore", "-q", "--no-index", rel], cwd=RAIZ_PROJETO)
        assert r.returncode == 0, f"{rel} não está no .gitignore"


def test_SINTETICO_padroes_de_dado_pessoal():
    # built at run time: the literal patterns would make this very file fail the guard above
    mascarado = "*" * 4 + "987" + "*" * 4
    assert privado.achados_pessoais(f"credor {mascarado} pago")["cpf_mascarado"] == [mascarado]
    assert privado.achados_pessoais("exemplo ****123**** e ***456***")["cpf_mascarado"] == []      # synthetic
    valido = "529.982.247" + "-25"                                                                  # valid digits
    assert privado.achados_pessoais(f"CPF {valido}")["cpf_completo"] == ["52998224725"]
    assert privado.achados_pessoais("CPF 123.456.789-01")["cpf_completo"] == []                    # invalid digits
    assert privado.achados_pessoais("CNPJ 11.222.333/0001-44") == {"cpf_mascarado": [], "cpf_completo": []}
    for rel in ("data/snapshots/coletas/a.json", "snapshots/objetos/ab/c.zlib", "etapa02/dados_brutos/x.json",
                "backups/b.sqlite", "docs/x.sqlite.gz", "data/backups/y.sqlite"):
        assert privado.caminho_privado(rel), rel
    for rel in ("data/stage02-raw.SHA256.txt", "data/stage01-samples.SHA256.txt", "docs/audits/rreo/siconfi/raw/a.json",
                "app/rp/banco.py"):
        assert not privado.caminho_privado(rel), rel


def test_config_aponta_o_bruto_para_fora_do_repositorio():
    c = tomllib.loads((RAIZ_PROJETO / "app" / "config.toml").read_text(encoding="utf-8"))["caminhos"]
    cfg = carregar()
    for chave in ("snapshots", "backups", "etapas_anteriores"):
        assert c[chave].startswith("~/"), (chave, c[chave])
        assert not getattr(cfg, chave).resolve().is_relative_to(RAIZ_PROJETO.resolve()), chave


def test_SINTETICO_pasta_privada_sincronizada_e_recusada(tmp_path, monkeypatch):
    monkeypatch.setenv("OneDrive", str(tmp_path / "OneDrive"))
    assert em_pasta_sincronizada(tmp_path / "OneDrive" / "projeto" / "armazem")
    ok = carregar(dados_locais=tmp_path / "local", snapshots=tmp_path / "armazem", backups=tmp_path / "bk",
                  etapas_anteriores=tmp_path / "etapas")
    recusar_pastas_privadas_sincronizadas(ok)          # nothing synced: no error
    for campo in ("snapshots", "backups", "etapas_anteriores"):
        ruim = carregar(**{"dados_locais": tmp_path / "local", "snapshots": tmp_path / "armazem",
                           "backups": tmp_path / "bk", "etapas_anteriores": tmp_path / "etapas",
                           campo: tmp_path / "OneDrive" / campo})
        with pytest.raises(BancoEmPastaSincronizada):
            recusar_pastas_privadas_sincronizadas(ruim)


def test_SINTETICO_copia_conferida_nunca_sobrescreve(tmp_path):
    origem, destino = tmp_path / "o", tmp_path / "d"
    (origem / "sub").mkdir(parents=True)
    (origem / "a.json").write_bytes(b'{"a": 1}')
    (origem / "sub" / "b.zlib").write_bytes(b"\x78\x9c\x00")
    r = privado.copiar_conferido(origem, destino)
    assert (r["copiados"], r["ja_iguais"], r["conflitos"]) == (2, 0, [])
    assert privado.conferir_copia(origem, destino)["ok"]
    r = privado.copiar_conferido(origem, destino)       # idempotent: identical bytes count as copied
    assert (r["copiados"], r["ja_iguais"]) == (0, 2)
    (destino / "a.json").write_bytes(b'{"a": 2}')       # a different file at the destination is a conflict
    with pytest.raises(privado.CopiaEmConflito):
        privado.copiar_conferido(origem, destino)
    assert (destino / "a.json").read_bytes() == b'{"a": 2}'     # nothing overwritten
    c = privado.conferir_copia(origem, destino)
    assert not c["ok"] and c["diferentes"] == ["a.json"]
    (destino / "sub" / "b.zlib").unlink()
    assert privado.conferir_copia(origem, destino)["faltam"] == ["sub/b.zlib"]
