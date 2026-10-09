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

# Fixtures that read REAL data: `real` builds a database from the store data/snapshots and `producao`, from the raw
# data of stages 01/02. Both hold creditor data (name, CNPJ, masked CPF). Every test that uses one of them, directly or
# indirectly, gets the `dados_reais` marker (critical review, item 34): `-m "not dados_reais"` runs only what is
# synthetic, in an environment without the raw data.
FIXTURES_DE_DADOS_REAIS = {"real", "producao"}


def pytest_configure(config):
    config.addinivalue_line("markers", "dados_reais: usa o armazem real ou o bruto das Etapas 01/02 (dados de "
                                       "credores); marcado sozinho pelo conftest")


def pytest_collection_modifyitems(items):
    for item in items:
        if FIXTURES_DE_DADOS_REAIS & set(getattr(item, "fixturenames", ())):
            item.add_marker(pytest.mark.dados_reais)


class Relogio:
    """Fake clock: sleeping moves time forward and gets recorded."""
    def __init__(self):
        self.t = 1000.0
        self.dormiu = []

    def monotonic(self):
        return self.t

    def dormir(self, s):
        self.dormiu.append(s)
        self.t += s


class Portal:
    """Fake transport. `rotas[(path, page)]` = list of responses consumed in order;
    each response is (status, body_bytes) or an exception to raise."""
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


# Defaults that complete a synthetic record to the strict API contract (rp.contrato v2): a test states only the
# fields it is about, and the page still has the real API's shape. A key the test sets is never replaced.
PADRAO_RP = {"entidade": 1, "anoempenho": 2025, "empenho": 1, "empenhoExercicio": "1/2025", "cnpjNome": "x",
             "dataEmissao": "2025-03-01", "programatica": "", "fonteRecurso": 1000, "descricaoFonte": "",
             "fornecedor": 7, "nome": "x", "cnpj": "11.222.333/0001-44", "desdobraDesp": "", "subDesdobramento": "",
             "proc": 0, "aproc": 0, "canceladoProc": 0, "pagoProc": 0, "pagoProcEstornado": 0, "canceladoAProc": 0,
             "pagoAProc": 0, "pagoAProcEstornado": 0, "liquidado": 0, "retencao": 0}
PADRAO_MOV = {"data": "2025-03-01", "descricaoTipoLancamento": "", "exercicioLiquidacao": 0, "exercicioPagamento": 0,
              "noLiquidacao": 0, "noPagamento": 0, "nroDocumento": "", "tipoLancamento": 20, "valor": 0,
              "valorALiquidar": 0, "valorAPagar": 0}


# The echo of the order the collector requests in the RP listing (the real API's form; ignored for other endpoints)
ECO_ORDEM_RP = [{"property": "anoempenho", "ascending": True, "descending": False, "direction": "ASC"},
                {"property": "empenho", "ascending": True, "descending": False, "direction": "ASC"}]


def completar_registro(x):
    """A record of the RP listing (has 'anoempenho') or of the movement list (has 'tipoLancamento') completed with the
    contract's defaults; anything else is returned unchanged."""
    if isinstance(x, dict) and "anoempenho" in x:
        return {**PADRAO_RP, **x}
    if isinstance(x, dict) and "tipoLancamento" in x:
        return {**PADRAO_MOV, **x}
    return x


def pagina(conteudo, pagina, total, ultima, total_paginas, completar=True, **metadados):
    """A Spring page with every metadata field of the strict contract. `size` defaults to a value consistent with
    total and totalPages; any metadata field can be overridden (or removed with None via `sem`)."""
    if completar:
        conteudo = [completar_registro(x) for x in conteudo]
    size = max(len(conteudo), -(-total // total_paginas) if isinstance(total, int) and total_paginas else 1, 1)         if isinstance(total_paginas, int) else max(len(conteudo), 1)
    d = {"content": conteudo, "totalElements": total, "totalPages": total_paginas, "number": pagina,
         "numberOfElements": len(conteudo), "last": ultima, "first": pagina == 0, "empty": not conteudo,
         "size": size, "sort": ECO_ORDEM_RP, "pageable": {"pageNumber": pagina, "pageSize": size}}
    sem = metadados.pop("sem", ())
    d.update(metadados)
    for k in sem:
        d.pop(k, None)
    return json.dumps(d).encode()


RAIZ_PROJETO = Path(__file__).resolve().parents[2]


def montar_producao(base, armazem_de=None, so_homologados=False):
    """TEMPORARY production store + database with the raw data of stages 01/02, processed by the production pipeline.
    `armazem_de`: reuses an existing store (rebuild).
    `so_homologados`: records only the snapshots of the homologated base (see BASE_HOMOLOGADA_ATE)."""
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


# ------------------------------------------------------------------ database built from the REAL store
ARMAZEM_REAL = RAIZ_PROJETO / "data" / "snapshots"
EM_2909 = "2026-09-29T23:59:59-03:00"
# HOMOLOGATED base (stages 01-05): the 466 snapshots collected from 29/09 19:56 to 30/09 01:27 of 2026. A new load
# (D1) only ADDS snapshots to the store; the real-case tests keep proving the homologated base, and the new load is
# validated by the gates (D1 procedure, docs/stages/05-analysis/POST_05_CONSOLIDATION.md, section 8).
BASE_HOMOLOGADA_ATE = "2026-09-30T01:27:56-03:00"
SNAPSHOTS_HOMOLOGADOS = 466


def manifestos_homologados(armazem):
    """(path, manifest) of the snapshots of the homologated base: collected up to BASE_HOMOLOGADA_ATE."""
    limite = datetime.fromisoformat(BASE_HOMOLOGADA_ATE)
    return [(rel, m) for rel, m in armazem.manifestos() if datetime.fromisoformat(m["coletada_em"]) <= limite]


def retrato_do_armazem():
    """(path, size, sha256) of every file in the real store."""
    return sorted((p.relative_to(ARMAZEM_REAL).as_posix(), p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest())
                  for p in ARMAZEM_REAL.rglob("*") if p.is_file())


@pytest.fixture(scope="session")
def real(tmp_path_factory):
    """TEMPORARY database built by only reading the real store (the 466 snapshots of the homologated base) -> normalize
    -> derive current and 'as it was on' 29/09/2026. Shared by the real-case tests."""
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


# ------------------------------------------------------------------ SYNTHETIC world (invented records)
COLETOR_SINTETICO = {"nome": "teste", "versao": "1", "sha256_codigo": None}


def registro_sintetico(emp, ano=2024, entidade=1, **kw):
    """An item of the RP listing's content[], with invented values."""
    from rp import normalizar
    r = {k: 0 for k in normalizar.DINHEIRO}
    r.update({"entidade": entidade, "anoempenho": ano, "empenho": emp, "empenhoExercicio": f"{emp}/{ano}",
              "cnpj": "11.222.333/0001-44", "dataEmissao": f"{ano}-03-01", "nome": "11.222.333/0001-44 - EMPRESA LTDA",
              "cnpjNome": "11.222.333/0001-44 - EMPRESA LTDA", "fornecedor": 7, "fonteRecurso": 1000, "aproc": 100.0})
    r.update(kw)
    return r


class Mundo:
    """Temporary database and store with invented catalogs and listings."""

    def __init__(self, tmp_path):
        self.cfg = carregar(dados_locais=tmp_path / "l", snapshots=tmp_path / "s", backups=tmp_path / "b")
        self.con = banco.abrir(self.cfg)
        self.armazem = Armazem(self.cfg.snapshots)

    def _snap(self, tipo, endpoint, params, corpo, quando):
        from rp.snapshots import gravar_snapshot
        return gravar_snapshot(self.con, self.armazem, tipo=tipo, endpoint=endpoint, parametros=params, coletada_em=quando,
                               origem_carimbo="relogio_coletor", status="completa", coletor=COLETOR_SINTETICO,
                               # a synthetic snapshot is concluded at its own instant (schema v7: available from then)
                               finalizada_em=quando,
                               respostas=[{"url": "sintetico", "http_status": 200, "corpo": json.dumps(corpo).encode()}])

    def catalogos(self, exercicios, quando="2026-09-29T10:00:00-03:00"):
        """`exercicios` = {entity: [official fiscal years]}."""
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


# ------------------------------------------------------------------ interface call (WSGI, no server)
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
    """<data value> values (cents) with an id, in the order they appear."""

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
    """Every href is internal ('/' or '#') or, since 06/10/2026 ('onde conferir no Portal'), a link to the official
    portal marked rel="external". No external resource is loaded: that is checked separately (no src)."""
    import re
    from rp.interface import portal
    for tag in re.findall(r"<a\s[^>]*>", corpo):
        href = (re.search(r'href="([^"]*)"', tag) or [None, ""])[1]
        if href.startswith(("/", "#")):
            continue
        if not (href.startswith((portal.SITE + "/", portal.API + "/")) and 'rel="external' in tag):
            return False
    return all(h.startswith(("/", "#", portal.DOMINIO + "/")) for h in re.findall(r'href="([^"]*)"', corpo))


# ------------------------------------------------------------------ synthetic RREO Annex VII (extractor v2)
ROTULOS_RREO_X = [("(a)", 300), ("(b)", 350), ("(c)", 400), ("(d)", 450), ("e=(a+b)", 500), ("(f)", 550), ("(g)", 600),
                  ("(h)", 650), ("(i)", 700), ("(j)", 750), ("k=(f+g)", 800), ("L=(e+k)", 850)]
CABECALHO_RREO = [((50, 40), "DEMONSTRATIVO JANEIRO A AGOSTO 2.026")] + [((x, 100), r) for r, x in ROTULOS_RREO_X]


def numero_pt(centavos):
    """123456 -> '1.234,56' (the PDF's number format)."""
    return f"{centavos / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def linha_rreo(a=0, b=0, c=0, d=0, f=0, g=0, h=0, i=0, j=0):
    """The 12 columns of one Annex VII row in cents, closing the document's identities (e, k and L computed)."""
    e, k = a + b - c - d, f + g - i - j
    return dict(zip("abcdefghijkL", (a, b, c, d, e, f, g, h, i, j, k, a + b - c - d + k)))


def textos_da_linha(palavras, y, valores, deslocar=None):
    """Words of one row: its label (list of (x, word)) and the 12 numbers under the column labels. `deslocar`
    {column: points} moves a number sideways (e.g. a right-aligned '0,00')."""
    xs = dict(zip("abcdefghijkL", (x for _, x in ROTULOS_RREO_X)))
    return [((x, y), w) for x, w in palavras] + [((xs[c] + (deslocar or {}).get(c, 0), y), numero_pt(v))
                                                 for c, v in valores.items()]


TOTAL_RREO = [(50, "TOTAL"), (80, "(III)")]
EXCETO_RREO = [(20, "RESTOS"), (50, "A"), (60, "PAGAR"), (90, "(EXCETO"), (130, "INTRA-ORÇAMENTÁRIOS)")]
INTRA_RREO = [(20, "RESTOS"), (50, "A"), (60, "PAGAR"), (90, "(INTRA-ORÇAMENTÁRIOS)")]
