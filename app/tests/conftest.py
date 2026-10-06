import hashlib
import json
import sys
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit
from wsgiref.util import setup_testing_defaults

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rp import banco  # noqa: E402
from rp.armazem import Armazem  # noqa: E402
from rp.coletor import EP_ENT, EP_EXE, EP_RP, Coletor  # noqa: E402
from rp.config import carregar  # noqa: E402
from rp.http import Cliente  # noqa: E402

# Fixtures que leem dados REAIS: `real` monta um banco a partir do armazem ../snapshots e `producao`, a partir do bruto
# das Etapas 01/02. Os dois tem dados de credores (nome, CNPJ, CPF mascarado). Todo teste que usa uma delas, direta ou
# indiretamente, recebe o marcador `dados_reais` (revisao critica, item 34): `-m "not dados_reais"` roda so o que e
# sintetico, num ambiente sem o bruto.
FIXTURES_DE_DADOS_REAIS = {"real", "producao"}


def pytest_configure(config):
    config.addinivalue_line("markers", "dados_reais: usa o armazem real ou o bruto das Etapas 01/02 (dados de "
                                       "credores); marcado sozinho pelo conftest")


def pytest_collection_modifyitems(items):
    for item in items:
        if FIXTURES_DE_DADOS_REAIS & set(getattr(item, "fixturenames", ())):
            item.add_marker(pytest.mark.dados_reais)


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


def montar_producao(base, armazem_de=None, so_homologados=False):
    """Armazem + banco TEMPORARIOS de producao com os dados brutos das Etapas 01/02, processados
    pelo pipeline de producao. `armazem_de`: reaproveita um armazem existente (reconstrucao).
    `so_homologados`: registra so os snapshots da base homologada (ver BASE_HOMOLOGADA_ATE)."""
    from rp import derivar, importar, normalizar
    cfg = carregar(dados_locais=base / "local", snapshots=armazem_de or base / "snapshots", backups=base / "backups")
    con = banco.abrir(cfg)
    armazem = Armazem(cfg.snapshots)
    if armazem_de is None:
        resumo_import = importar.importar_etapas_anteriores(con, armazem, RAIZ_PROJETO)
    else:
        if so_homologados:
            novos = sum(banco.registrar_manifesto(con, armazem, rel, m)[1] for rel, m in manifestos_homologados(armazem))
            novos += sum(banco.registrar_evidencia(con, armazem, rel, m)[1] for rel, m in armazem.evidencias())
            resumo_import = {"sincronizados": novos}
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


# ------------------------------------------------------------------ banco montado a partir do ARMAZEM REAL
ARMAZEM_REAL = RAIZ_PROJETO / "data" / "snapshots"
EM_2909 = "2026-09-29T23:59:59-03:00"
# Base HOMOLOGADA (Etapas 01-05): os 466 snapshots coletados de 29/09 19h56 a 30/09 01h27 de 2026. Uma carga nova
# (D1) so ACRESCENTA snapshots ao armazem; os testes de casos reais continuam provando a base homologada, e a carga
# nova e validada pelos portoes (procedimento da D1, etapa05/CONSOLIDACAO_POS_05.md, secao 8).
BASE_HOMOLOGADA_ATE = "2026-09-30T01:27:56-03:00"
SNAPSHOTS_HOMOLOGADOS = 466


def manifestos_homologados(armazem):
    """(caminho, manifesto) dos snapshots da base homologada: coletados ate BASE_HOMOLOGADA_ATE."""
    limite = datetime.fromisoformat(BASE_HOMOLOGADA_ATE)
    return [(rel, m) for rel, m in armazem.manifestos() if datetime.fromisoformat(m["coletada_em"]) <= limite]


def retrato_do_armazem():
    """(caminho, tamanho, sha256) de todo arquivo do armazem real."""
    return sorted((p.relative_to(ARMAZEM_REAL).as_posix(), p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest())
                  for p in ARMAZEM_REAL.rglob("*") if p.is_file())


@pytest.fixture(scope="session")
def real(tmp_path_factory):
    """Banco TEMPORARIO montado so com leitura do armazem real (os 466 snapshots da base homologada) -> normalizar ->
    derivar atual e 'como estava em' 29/09/2026. Compartilhado pelos testes de casos reais."""
    from rp import derivar
    from rp.painel import Painel
    antes = retrato_do_armazem()
    base = tmp_path_factory.mktemp("real")
    m = montar_producao(base, armazem_de=ARMAZEM_REAL, so_homologados=True)
    m["did_2909"] = derivar.derivar(m["con"], m["nid"], EM_2909)
    m["armazem_antes"], m["armazem_depois"] = antes, retrato_do_armazem()
    m["painel"] = Painel.abrir(m["cfg"].banco)
    yield m
    m["painel"].fechar()
    m["con"].close()


# ------------------------------------------------------------------ mundo SINTETICO (registros inventados)
COLETOR_SINTETICO = {"nome": "teste", "versao": "1", "sha256_codigo": None}


def registro_sintetico(emp, ano=2024, entidade=1, **kw):
    """Um item de content[] da listagem de RP, com valores inventados."""
    from rp import normalizar
    r = {k: 0 for k in normalizar.DINHEIRO}
    r.update({"entidade": entidade, "anoempenho": ano, "empenho": emp, "empenhoExercicio": f"{emp}/{ano}",
              "cnpj": "11.222.333/0001-44", "dataEmissao": f"{ano}-03-01", "nome": "11.222.333/0001-44 - EMPRESA LTDA",
              "cnpjNome": "11.222.333/0001-44 - EMPRESA LTDA", "fornecedor": 7, "fonteRecurso": 1000, "aproc": 100.0})
    r.update(kw)
    return r


class Mundo:
    """Banco e armazem temporarios com catalogos e listagens inventados."""

    def __init__(self, tmp_path):
        self.cfg = carregar(dados_locais=tmp_path / "l", snapshots=tmp_path / "s", backups=tmp_path / "b")
        self.con = banco.abrir(self.cfg)
        self.armazem = Armazem(self.cfg.snapshots)

    def _snap(self, tipo, endpoint, params, corpo, quando):
        from rp.snapshots import gravar_snapshot
        return gravar_snapshot(self.con, self.armazem, tipo=tipo, endpoint=endpoint, parametros=params, coletada_em=quando,
                               origem_carimbo="relogio_coletor", status="completa", coletor=COLETOR_SINTETICO,
                               respostas=[{"url": "sintetico", "http_status": 200, "corpo": json.dumps(corpo).encode()}])

    def catalogos(self, exercicios, quando="2026-09-29T10:00:00-03:00"):
        """`exercicios` = {entidade: [exercicios oficiais]}."""
        self._snap("entidades", EP_ENT, {}, [{"id": e, "nome": f"ENTIDADE {e}", "cnpj": None, "tipo": "A"}
                                             for e in exercicios], quando)
        for e, anos in exercicios.items():
            self._snap("exercicios", f"{EP_EXE}/{e}", {"entidade": e},
                       [{"id": {"entidade": {"id": e}, "exercicio": x}, "aberto": False, "fechado": True} for x in anos],
                       quando)

    def listagem(self, entidade, exercicio, data_final, regs, quando):
        p = {"entidade": entidade, "exercicio": exercicio, "dataInicial": f"{exercicio}-01-01", "dataFinal": data_final,
             "size": 2000}
        return self._snap("rp_listagem", EP_RP, p, {"content": regs, "last": True, "totalElements": len(regs)}, quando)

    def processar(self, em=None):
        from rp import derivar, normalizar
        nid, _ = normalizar.normalizar(self.con)
        return nid, derivar.derivar(self.con, nid, em)

    def painel(self, nivel="publico"):
        from rp.painel import Painel
        return Painel.abrir(self.cfg.banco, nivel)


@pytest.fixture
def mundo(tmp_path):
    m = Mundo(tmp_path)
    yield m
    m.con.close()


# ------------------------------------------------------------------ chamada da interface (WSGI, sem servidor)
def chamar(app, caminho, metodo="GET", **params):
    env = {}
    setup_testing_defaults(env)
    env.update(PATH_INFO=caminho, QUERY_STRING=urlencode({k: v for k, v in params.items() if v is not None}),
               REQUEST_METHOD=metodo)
    r = {}

    def start_response(status, headers, exc_info=None):
        r["status"], r["headers"] = status, dict(headers)
    corpo = b"".join(app(env, start_response)).decode("utf-8")
    return r["status"], r["headers"], corpo


class _Dados(HTMLParser):
    """Valores <data value> (centavos) com id, na ordem em que aparecem."""

    def __init__(self):
        super().__init__()
        self.por_id, self.todos = {}, []

    def handle_starttag(self, tag, attrs):
        if tag == "data":
            a = dict(attrs)
            self.todos.append(int(a["value"]))
            if a.get("id"):
                self.por_id[a["id"]] = int(a["value"])


def dados(html):
    d = _Dados()
    d.feed(html)
    return d.por_id


def ok(app, caminho, **params):
    status, _, corpo = chamar(app, caminho, **params)
    assert status == "200 OK", (caminho, params, status, corpo[:400])
    return corpo


def links_permitidos(corpo):
    """Todo href e interno ('/' ou '#') ou, desde 06/10/2026 ('onde conferir no Portal'), link para o portal oficial
    marcado rel="external". Nenhum recurso externo e carregado: isso e conferido a parte (sem src)."""
    import re
    from rp.interface import portal
    for tag in re.findall(r"<a\s[^>]*>", corpo):
        href = (re.search(r'href="([^"]*)"', tag) or [None, ""])[1]
        if href.startswith(("/", "#")):
            continue
        if not (href.startswith((portal.SITE + "/", portal.API + "/")) and 'rel="external' in tag):
            return False
    return all(h.startswith(("/", "#", portal.DOMINIO + "/")) for h in re.findall(r'href="([^"]*)"', corpo))
