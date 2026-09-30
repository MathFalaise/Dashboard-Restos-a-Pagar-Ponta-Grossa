import json
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rp import banco  # noqa: E402
from rp.armazem import Armazem  # noqa: E402
from rp.coletor import Coletor  # noqa: E402
from rp.config import carregar  # noqa: E402
from rp.http import Cliente  # noqa: E402


class Relogio:
    """Relogio falso: dormir avanca o tempo e fica registrado."""
    def __init__(self):
        self.t = 1000.0
        self.dormiu = []

    def monotonic(self):
        return self.t

    def dormir(self, s):
        self.dormiu.append(s)
        self.t += s


class Portal:
    """Transporte falso. `rotas[(caminho, pagina)]` = lista de respostas consumidas em ordem;
    cada resposta e (status, corpo_bytes) ou uma excecao a lancar."""
    def __init__(self):
        self.rotas = {}
        self.chamadas = []

    def get(self, url, timeout):
        u = urlsplit(url)
        q = dict(parse_qsl(u.query))
        self.chamadas.append((u.path, q))
        chave = (u.path.split("/portaltransparencia-api", 1)[-1], q.get("page"))
        fila = self.rotas.get(chave) or self.rotas.get((chave[0], None))
        if not fila:
            return 404, {}, b"nao encontrado"
        r = fila.pop(0) if len(fila) > 1 else fila[0]
        if isinstance(r, Exception):
            raise r
        return r[0], {"Content-Type": "application/json"}, r[1]


def pagina(conteudo, pagina, total, ultima, total_paginas):
    return json.dumps({"content": conteudo, "totalElements": total, "totalPages": total_paginas, "number": pagina,
                       "numberOfElements": len(conteudo), "last": ultima}).encode()


RAIZ_PROJETO = Path(__file__).resolve().parents[2]


def montar_producao(base, armazem_de=None):
    """Armazem + banco TEMPORARIOS de producao com os dados brutos das Etapas 01/02, processados
    pelo pipeline de producao. `armazem_de`: reaproveita um armazem existente (reconstrucao)."""
    from rp import derivar, importar, normalizar
    cfg = carregar(dados_locais=base / "local", snapshots=armazem_de or base / "snapshots", backups=base / "backups")
    con = banco.abrir(cfg)
    armazem = Armazem(cfg.snapshots)
    if armazem_de is None:
        resumo_import = importar.importar_etapas_anteriores(con, armazem, RAIZ_PROJETO)
    else:
        resumo_import = {"sincronizados": banco.sincronizar(con, armazem)}
    nid, resumo_norm = normalizar.normalizar(con)
    did = derivar.derivar(con, nid)
    return {"cfg": cfg, "con": con, "armazem": armazem, "nid": nid, "did": did,
            "importacao": resumo_import, "normalizacao": resumo_norm}


@pytest.fixture(scope="session")
def producao(tmp_path_factory):
    return montar_producao(tmp_path_factory.mktemp("producao"))


@pytest.fixture
def ambiente(tmp_path):
    cfg = carregar(dados_locais=tmp_path / "local", snapshots=tmp_path / "snapshots", backups=tmp_path / "backups",
                   pausa=1.5, espera_base=5.0, tentativas=3)
    relogio, portal = Relogio(), Portal()
    con = banco.abrir(cfg)
    armazem = Armazem(cfg.snapshots)
    cliente = Cliente(cfg, transporte=portal.get, dormir=relogio.dormir, monotonic=relogio.monotonic)
    return {"cfg": cfg, "con": con, "armazem": armazem, "portal": portal, "relogio": relogio,
            "coletor": Coletor(cfg, con, armazem, cliente)}
