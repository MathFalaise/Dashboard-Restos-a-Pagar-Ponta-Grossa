"""Tests of the public interface (sub-stage 04.5): read-only WSGI application over the rp.painel layer.

* SINTETICO = invented records in a temporary database (fixture `mundo`), for situations the real data does not
  have (a new snapshot with a different value, an individual creditor, malicious text...).
* `producao` = real raw data from stages 01/02. The real cases of the full store live in test_interface_casos_reais.py.
The 13 mandatory tests of section 20 of the specification start with test_NN_.
"""
import ast
import hashlib
import inspect
import re
import socket
import sqlite3
import stat
import threading
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

import pytest
from conftest import RAIZ_PROJETO, chamar, dados, ok, registro_sintetico as _reg

from rp import consultas, derivar, execucoes, governanca
from rp.interface import Aplicacao, aplicacao, criar_servidor, paginas
from rp.interface import formato as fm
from rp.interface import portal
from rp.painel import Painel, publico

PASTA_INTERFACE = RAIZ_PROJETO / "app" / "rp" / "interface"
CORTE_REAL = dict(exercicio=2026, data_final="2026-08-31")      # stage 02 cut-off present in `producao`


# ------------------------------------------------------------------ utilities
def sha(caminho):
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


def rotas_com_parametros(ex, df, entidade, ano=None, emp=None):
    """One visit to each route, with the typical parameters of a cut-off."""
    visitas = [("/", {}), ("/", dict(exercicio=ex, data_final=df)), ("/", dict(exercicio=ex, data_final=df, entidade=entidade)),
               ("/entidades", dict(exercicio=ex, data_final=df)), ("/empenhos", dict(exercicio=ex, data_final=df)),
               ("/empenhos", dict(exercicio=ex, data_final=df, entidade=entidade, categoria="nao_processado", ordem="empenho")),
               ("/retratos", {}), ("/retratos", dict(entidade=entidade, exercicio=ex, data_final=df)),
               ("/reconciliacao", {}), ("/reconciliacao", dict(exercicio=ex, data_final=df, escopo="entidade")),
               ("/pares", dict(exercicio=ex, data_final=df)), ("/metodologia", {}), ("/estilo.css", {})]
    if emp is not None:
        visitas.append(("/empenho", dict(entidade=entidade, anoempenho=ano, empenho=emp, exercicio=ex, data_final=df)))
    return visitas


@pytest.fixture
def sem_rede(monkeypatch):
    """A connection or name resolution to outside this machine fails and gets recorded. The collection's HTTP client is
    forbidden too: the interface must never use it."""
    tentativas = []
    conectar, resolver = socket.socket.connect, socket.getaddrinfo
    locais = ("127.0.0.1", "::1", "localhost")

    def conectar_local(self, endereco):
        host = endereco[0] if isinstance(endereco, tuple) else str(endereco)
        if host not in locais:
            tentativas.append(endereco)
            raise OSError(f"rede bloqueada no teste: {endereco}")
        return conectar(self, endereco)

    def resolver_local(host, *a, **k):
        if host not in locais:
            tentativas.append(host)
            raise socket.gaierror(f"resolucao de nome bloqueada no teste: {host}")
        return resolver(host, *a, **k)

    def proibido(*a, **k):
        tentativas.append("cliente da coleta")
        raise AssertionError("a interface tentou usar o cliente HTTP da coleta")
    from rp import http as rp_http
    monkeypatch.setattr(socket.socket, "connect", conectar_local)
    monkeypatch.setattr(socket, "getaddrinfo", resolver_local)
    monkeypatch.setattr(rp_http.Cliente, "get", proibido)
    yield tentativas


@pytest.fixture(scope="module")
def app_producao(producao):
    return Aplicacao(producao["cfg"].banco)


def _mundo_basico(mundo):
    """Entity 1 with two records in 2025; catalog 1: 2024-2025, 15: 2025."""
    mundo.catalogos({1: [2024, 2025], 15: [2025]})
    t = "2026-09-29T20:00:00-03:00"
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1, aproc=500.10, liquidado=100.0, pagoAProc=60.05),
                                           _reg(2, proc=77.07, aproc=0, pagoProc=7.07)], t)
    mundo.listagem(15, 2025, "2025-12-31", [], t)
    mundo.processar()
    return Aplicacao(mundo.cfg.banco)


# ================================================================== 1. the interface does not call the API
def test_guarda_de_rede_do_teste_bloqueia_de_verdade(sem_rede):
    """Without this proof, 'no attempt' in the tests below could just be a guard that does not work."""
    with pytest.raises(OSError):
        socket.create_connection(("servicos.pontagrossa.pr.gov.br", 443), timeout=5)
    with socket.socket() as s, pytest.raises(OSError):
        s.connect(("8.8.8.8", 53))
    assert sem_rede == ["servicos.pontagrossa.pr.gov.br", ("8.8.8.8", 53)]
    sem_rede.clear()


def test_01_interface_nao_chama_a_api(app_producao, producao, sem_rede):
    cid = consultas.snapshot_em(producao["con"], 1, 2026, "2026-01-01", "2026-08-31")
    assert cid
    for caminho, params in rotas_com_parametros(2026, "2026-08-31", 1, 2025, 5659):
        ok(app_producao, caminho, **params)
    assert sem_rede == []                       # no connection attempt and no use of the collector
    proibidos = {"requests", "urllib.request", "http.client", "socket", "rp.http", "rp.coletor", "rp.importar",
                 "rp.armazem", "rp.snapshots", "rp.normalizar", "rp.derivar", "rp.execucoes"}
    for arq in PASTA_INTERFACE.glob("*.py"):
        arvore = ast.parse(arq.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            nomes = []
            if isinstance(no, ast.Import):
                nomes = [a.name for a in no.names]
            elif isinstance(no, ast.ImportFrom):
                base = ("rp." + (no.module or "").lstrip(".")) if no.level else (no.module or "")
                nomes = [base] + [f"{base}.{a.name}".replace("rp..", "rp.") for a in no.names]
            for n in nomes:
                assert not any(n == p or n.startswith(p + ".") for p in proibidos), (arq.name, n)
        if arq.name != "portal.py":   # portal.py only builds the "where to check" links (href text), it never connects
            assert "pontagrossa.pr.gov.br" not in arq.read_text(encoding="utf-8")


# ================================================================== 2. read-only database
def test_02_interface_funciona_com_arquivo_de_banco_somente_leitura(producao, tmp_path):
    copia = tmp_path / "somente_leitura.sqlite"
    destino = sqlite3.connect(copia)
    with destino:
        producao["con"].backup(destino)
    destino.close()
    antes = sha(copia)
    copia.chmod(stat.S_IREAD)                  # the file itself is read-only at the operating system level
    try:
        app = Aplicacao(copia)
        for caminho, params in rotas_com_parametros(2026, "2026-08-31", 1, 2025, 5659):
            ok(app, caminho, **params)
        with Painel.abrir(copia) as p:
            with pytest.raises(sqlite3.DatabaseError):
                p.con.execute("DELETE FROM rp_derivado")
    finally:
        copia.chmod(stat.S_IREAD | stat.S_IWRITE)
    assert sha(copia) == antes


# ================================================================== 3. the main value comes from the Elotech API
def test_03_valor_principal_vem_da_api_elotech(app_producao, producao):
    con, nid, did = producao["con"], producao["nid"], producao["did"]
    cid = consultas.snapshot_em(con, 1, 2026, "2026-01-01", "2026-08-31")
    s1, liq, insc, n = con.execute(
        "SELECT SUM(d.s1_saldo_total_c), SUM(r.liquidado_c), SUM(r.proc_c + r.aproc_c), COUNT(*) FROM rp_registro r "
        "JOIN rp_derivado d ON d.derivacao_id=? AND d.resposta_id=r.resposta_id AND d.indice=r.indice "
        "WHERE r.normalizacao_id=? AND r.coleta_id=?", (did, nid, cid)).fetchone()
    corpo = ok(app_producao, "/", entidade=1, **CORTE_REAL)
    v = dados(corpo)
    assert (v["ind-saldo_total"], v["ind-liquidacoes"], v["ind-inscricao_total"], v["ind-registros"]) == (s1, liq, insc, n)
    assert "Fonte dos dados:</strong> Portal da Transparência de Ponta Grossa — API do sistema Elotech/Oxy Transparência" in corpo
    cartoes = corpo.split('<div class="indicador')[1:]
    assert len(cartoes) == 13 and all("Fonte: API Elotech" in c and "valor derivado" in c for c in cartoes)


# ================================================================== 4. the RREO never replaces the Elotech value
def test_04_rreo_nao_substitui_valor_elotech(app_producao):
    corpo = ok(app_producao, "/", entidade=1, **CORTE_REAL)
    v = dados(corpo)
    assert v["conf-api"] == v["ind-saldo_total"]                     # the balance shown is the API's
    assert v["conf-rreo"] != v["conf-api"] and v["conf-dif"] == v["conf-api"] - v["conf-rreo"]
    secao = corpo[corpo.index('id="conferencia-rreo"'):]
    assert "Fonte primária:</strong> API Elotech" in secao and "Fonte de reconciliação:</strong> RREO Anexo VII" in secao
    assert "valor publicado" in secao and "nunca é trocado" in secao
    rec = ok(app_producao, "/reconciliacao", escopo="entidade", **CORTE_REAL)
    assert "valor publicado" in rec and "API Elotech" in rec and "RREO" in rec


# ================================================================== 5. an entity outside the catalog does not become zero
def test_05_SINTETICO_entidade_fora_do_catalogo_nao_vira_zero(mundo):
    mundo.catalogos({1: [2024, 2025], 15: [2025]})
    t = "2026-09-29T20:00:00-03:00"
    mundo.listagem(1, 2024, "2024-12-31", [_reg(1, ano=2023, aproc=10.0)], t)
    mundo.listagem(15, 2024, "2024-12-31", [], t)            # did not exist in 2024: the API returns 0 records
    mundo.listagem(1, 2025, "2025-12-31", [_reg(2, aproc=20.0)], t)
    mundo.listagem(15, 2025, "2025-12-31", [], t)            # existed in 2025 and has no RP: a legitimate zero
    mundo.processar()
    app = Aplicacao(mundo.cfg.banco)
    ent_2024 = ok(app, "/entidades", exercicio=2024, data_final="2024-12-31")
    v = dados(ent_2024)
    assert 'id="sem-valor-15"' in ent_2024 and "não existia no exercício" in ent_2024
    assert not any(k.startswith("ent-15-") for k in v) and v["ent-1-total"] == 1000
    ent_2025 = dados(ok(app, "/entidades", exercicio=2025, data_final="2025-12-31"))
    assert ent_2025["ent-15-total"] == 0 and ent_2025["ent-15-registros"] == 0      # existing, with zero
    so_15 = ok(app, "/", exercicio=2024, data_final="2024-12-31", entidade=15)
    assert 'id="indisponivel"' in so_15 and "não é RP zero" in so_15 and "R$ 0,00" not in so_15
    assert not any(k.startswith("ind-") for k in dados(so_15))


# ================================================================== 6. the previous snapshot is still accessible
def _dois_retratos(mundo):
    mundo.catalogos({1: [2025]})
    a = mundo.listagem(1, 2025, "2025-12-31", [_reg(1, aproc=500000.0)], "2026-09-29T20:00:00-03:00")
    b = mundo.listagem(1, 2025, "2025-12-31", [_reg(1, aproc=300000.0)], "2026-10-03T20:00:00-03:00")
    mundo.processar()
    return a, b, Aplicacao(mundo.cfg.banco)


def test_06_SINTETICO_snapshot_anterior_continua_acessivel(mundo):
    a, b, app = _dois_retratos(mundo)
    ret = ok(app, "/retratos", entidade=1, exercicio=2025, data_final="2025-12-31")
    assert a["snapshot_uid"] in ret and b["snapshot_uid"] in ret and "vigente" in ret
    assert "-R$ 200.000,00" in ret                               # difference to the previous snapshot
    comp = ok(app, "/comparar", a=a["snapshot_uid"], b=b["snapshot_uid"])
    assert "-R$ 200.000,00" in comp and "1 alterados" in comp
    antigo = dados(ok(app, "/", exercicio=2025, data_final="2025-12-31", em="2026-09-30"))
    assert antigo["ind-inscricao_total"] == 50000000
    assert (mundo.cfg.snapshots / a["manifesto"]).is_file()


# ================================================================== 7. provenance of every value
def test_07_proveniencia_disponivel_para_todo_valor(app_producao, producao):
    con = producao["con"]
    uids = {u for (u,) in con.execute("SELECT snapshot_uid FROM coleta")}
    shas = {s for (s,) in con.execute("SELECT sha256 FROM objeto_bruto")}
    corpo = ok(app_producao, "/", entidade=1, **CORTE_REAL)
    for cartao in corpo.split('<div class="indicador')[1:]:
        assert "<data" in cartao and "Origem do dado" in cartao
        achados = set(re.findall(r"<code>([0-9a-f]{32})</code>", cartao))
        assert achados and achados <= uids
        assert re.search(r"Derivação</dt><dd>\d+ \(hash <code>[0-9a-f]{64}</code>\)", cartao)
    det = ok(app_producao, "/empenho", entidade=1, anoempenho=2025, empenho=5659, **CORTE_REAL)
    origem = det[det.index('id="origem"'):]
    assert "<code>/empenhos/restos-a-pagar</code>" in origem and "Coletado em" in origem and "Parâmetros" in origem
    sha_objeto = re.search(r"Objeto bruto \(SHA-256\)</dt><dd><code>([0-9a-f]{64})</code>", origem).group(1)
    assert sha_objeto in shas
    assert set(re.findall(r"<code>([0-9a-f]{32})</code>", origem)) <= uids


def test_07b_proveniencia_nas_telas_de_entidades_e_empenhos(app_producao, producao):
    uids = {u for (u,) in producao["con"].execute("SELECT snapshot_uid FROM coleta")}
    ent = ok(app_producao, "/entidades", **CORTE_REAL)
    linhas = [l for l in ent.split("<tr>")[1:] if "<data" in l]
    assert linhas
    for linha in linhas:                            # every row with a value has an origin (snapshot and derivation)
        achados = set(re.findall(r"<code>([0-9a-f]{32})</code>", linha))
        assert 'class="origem"' in linha and "derivação" in linha and achados and achados <= uids
    emp = ok(app_producao, "/empenhos", entidade=1, **CORTE_REAL)
    bloco = emp[emp.index("Origem do dado (snapshots usados)"):]
    bloco = bloco[:bloco.index("</details>")]
    assert set(re.findall(r"<code>([0-9a-f]{32})</code>", bloco)) & uids and "/empenhos/restos-a-pagar" in bloco


# ================================================================== 8. experimental rule out of the main indicators
def test_08_regras_experimentais_nao_aparecem_como_indicador(app_producao):
    corpo = ok(app_producao, "/", entidade=1, **CORTE_REAL)
    indicadores = corpo[corpo.index('<section class="grupo">'):corpo.index("Entidades abrangidas")]
    for termo in ("CONS-PAR", "RREO-COL", "CANC", "analítico", "experimental"):
        assert termo not in indicadores, termo
    assert set(re.findall(r"Regra: (.*?)</p>", indicadores)) <= {"S1 v1 (operacional)", "S2 v1 (operacional)",
                                                                 "S3 v1 (operacional)"}
    for caminho, params in rotas_com_parametros(2026, "2026-08-31", 1):
        if caminho not in ("/metodologia", "/pares", "/estilo.css"):
            assert "CONS-PAR" not in ok(app_producao, caminho, **params), caminho


def test_08b_SINTETICO_regra_rebaixada_bloqueia_o_indicador(mundo):
    app = _mundo_basico(mundo)
    governanca.registrar_decisao(mundo.con, "S1", 1, "experimental", "HIPÓTESE", False, "teste SINTETICO", "teste",
                                 "teste", decidido_em="2026-10-01")
    status, _, corpo = chamar(app, "/", exercicio=2025, data_final="2025-12-31")
    assert status == "400 Bad Request" and "S1 v1" in corpo and "<data" not in corpo


# ================================================================== 9. sensitive data out of the default view
MEI = "12.345.678/0001-90 - JOAO DA SILVA 12345678901"


def test_09_SINTETICO_dados_sensiveis_nao_aparecem_por_padrao(mundo):
    mundo.catalogos({1: [2025]})
    t = "2026-09-29T20:00:00-03:00"
    regs = [_reg(1, cnpj="12.345.678/0001-90", nome=MEI, cnpjNome=MEI, fornecedor=99),
            _reg(2, cnpj="****123****", nome="FULANA DE TAL", cnpjNome="****123**** - FULANA DE TAL", fornecedor=98)]
    a = mundo.listagem(1, 2025, "2025-12-31", regs, t)
    regs[0]["nome"] = MEI + " ME"
    b = mundo.listagem(1, 2025, "2025-12-31", regs, "2026-10-03T20:00:00-03:00")
    mundo.processar()
    app = Aplicacao(mundo.cfg.banco)
    base = dict(exercicio=2025, data_final="2025-12-31")
    paginas_gerais = [ok(app, "/", **base), ok(app, "/entidades", **base), ok(app, "/empenhos", **base),
                      ok(app, "/empenhos", nivel="interno", **base),     # unknown parameter: stays public
                      ok(app, "/retratos", entidade=1, **base), ok(app, "/comparar", a=a["snapshot_uid"], b=b["snapshot_uid"]),
                      ok(app, "/reconciliacao"), ok(app, "/metodologia")]
    for corpo in paginas_gerais:
        for proibido in ("12345678901", "12.345.678/0001-90", "JOAO", "FULANA", "****123****"):
            assert proibido not in corpo, proibido
    pj = ok(app, "/empenho", entidade=1, anoempenho=2024, empenho=1, **base)
    pf = ok(app, "/empenho", entidade=1, anoempenho=2024, empenho=2, **base)
    assert "JOAO DA SILVA [documento omitido] ME (pessoa jurídica)" in pj
    assert publico.PESSOA_FISICA_OMITIDA in pf and "FULANA" not in pf
    for corpo in (pj, pf):
        assert "12345678901" not in corpo and "12.345.678/0001-90" not in corpo and "****123****" not in corpo
    assert "/fornecedores" not in aplicacao.ROTAS                  # no "all suppliers" screen
    status, _, _ = chamar(app, "/empenhos", cnpj="123.456.789-01", **base)   # a CPF is never a filter
    assert status == "400 Bad Request"


# ================================================================== 10. filters do not change data
def test_10_filtros_nao_alteram_dados(app_producao, producao):
    arquivo = producao["cfg"].banco
    antes, camada0 = sha(arquivo), execucoes.hash_camada0(producao["con"])
    total = dados(ok(app_producao, "/empenhos", entidade=1, **CORTE_REAL))
    soma_s1 = soma_n = 0
    for cat in ("processado", "nao_processado", "ambos", "sem_saldo_abertura"):
        corpo = ok(app_producao, "/empenhos", entidade=1, categoria=cat, **CORTE_REAL)
        v = dados(corpo)
        if v["tot-registros"] == 0:   # 04.6: empty set = "Nenhum resultado encontrado", no R$ 0,00
            assert "tot-s1" not in v and 'id="sem-resultado"' in corpo
        soma_s1, soma_n = soma_s1 + v.get("tot-s1", 0), soma_n + v["tot-registros"]
    assert (soma_s1, soma_n) == (total["tot-s1"], total["tot-registros"])
    for params in (dict(tipo_credor="pessoa jurídica"), dict(tipo_credor="pessoa física"), dict(programatica="09"),
                   dict(fonte_recurso=1000), dict(ordem="empenho", pagina=3), dict(cnpj="00000000000000")):
        v = dados(ok(app_producao, "/empenhos", entidade=1, **CORTE_REAL, **params))
        assert v["tot-registros"] <= total["tot-registros"]
    assert sha(arquivo) == antes and execucoes.hash_camada0(producao["con"]) == camada0


# ================================================================== 11. missing data is not zero
def test_11_SINTETICO_ausencia_de_dado_e_diferente_de_zero(mundo):
    mundo.catalogos({1: [2025], 15: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1)], "2026-09-29T20:00:00-03:00")     # entity 15 was not collected
    mundo.processar()
    app = Aplicacao(mundo.cfg.banco)
    for caminho in ("/", "/empenhos"):
        corpo = ok(app, caminho, exercicio=2025, data_final="2025-12-31")
        assert 'id="indisponivel"' in corpo and "não coletado" in corpo and "ausência de dado não é zero" in corpo
        assert "R$ 0,00" not in corpo and not any(k.startswith(("ind-", "tot-")) for k in dados(corpo))
    ent = ok(app, "/entidades", exercicio=2025, data_final="2025-12-31")
    assert 'id="sem-valor-15"' in ent and "não coletado" in ent


# ================================================================== 12. money in cents
def test_12_SINTETICO_valores_monetarios_em_centavos_sem_arredondamento(mundo):
    app = _mundo_basico(mundo)
    v = dados(ok(app, "/", exercicio=2025, data_final="2025-12-31", entidade=1))
    assert (v["ind-inscricao_nao_processada"], v["ind-inscricao_processada"], v["ind-pago_nao_processado"]) == (50010, 7707, 6005)
    assert v["ind-saldo_total"] == 50010 + 7707 - 707 - 6005
    assert fm.moeda(0) == "R$ 0,00" and fm.moeda(1) == "R$ 0,01" and fm.moeda(-5) == "-R$ 0,05"
    assert fm.moeda(123456789012345) == "R$ 1.234.567.890.123,45" and fm.moeda(-1234567) == "-R$ 12.345,67"
    with pytest.raises(TypeError):
        fm.moeda(1.5)
    fonte = "".join(inspect.getsource(m) for m in (fm, paginas, aplicacao))
    assert "float(" not in fonte and "round(" not in fonte and "/ 100" not in fonte


# ================================================================== 13. independent snapshots
def test_13_SINTETICO_mesma_consulta_em_snapshots_diferentes_da_retratos_independentes(mundo):
    _, _, app = _dois_retratos(mundo)
    atual = ok(app, "/", exercicio=2025, data_final="2025-12-31")
    antigo = ok(app, "/", exercicio=2025, data_final="2025-12-31", em="2026-09-30")
    assert dados(atual)["ind-inscricao_total"] == 30000000 and dados(antigo)["ind-inscricao_total"] == 50000000
    assert "Estado atual da base para o exercício de 2025, corte 31/12/2025, coletado em 03/10/2026" in atual
    assert "Como a base estava em 30/09/2026: exercício de 2025, corte 31/12/2025, coletado em 29/09/2026" in antigo


# ================================================================== section 21: writing refused
def test_interface_recusa_qualquer_escrita(app_producao, producao):
    arquivo = producao["cfg"].banco
    antes, camada0 = sha(arquivo), execucoes.hash_camada0(producao["con"])
    n_deriv = producao["con"].execute("SELECT COUNT(*) FROM derivacao_execucao").fetchone()[0]
    for metodo in ("POST", "PUT", "DELETE", "PATCH"):
        status, cab, _ = chamar(app_producao, "/", metodo=metodo)
        assert status == "405 Method Not Allowed" and cab["Allow"] == "GET, HEAD"
    with Painel.abrir(arquivo) as p:                   # the same connection the interface uses per request
        for sql in ("UPDATE coleta SET status='falhou'", "DELETE FROM rp_registro", "INSERT INTO evidencia_externa "
                    "(tipo, descricao, registrada_em) VALUES ('nota','x','x')",
                    "INSERT INTO regra (codigo, versao, tipo, uso, status_evidencia, definicao, fonte) VALUES "
                    "('X', 1, 'formula', 'experimental', 'HIPÓTESE', 'x', 'x')",
                    "UPDATE derivacao_execucao SET hash_resultado='0'"):
            with pytest.raises(sqlite3.DatabaseError):
                p.con.execute(sql)
        with pytest.raises(sqlite3.DatabaseError):     # not even a new derivation
            derivar.derivar(p.con, producao["nid"])
        with pytest.raises(sqlite3.DatabaseError):
            governanca.registrar_decisao(p.con, "S1", 1, "experimental", "HIPÓTESE", False, "x", "x", "x")
    assert sha(arquivo) == antes and execucoes.hash_camada0(producao["con"]) == camada0
    assert producao["con"].execute("SELECT COUNT(*) FROM derivacao_execucao").fetchone()[0] == n_deriv


# ================================================================== sections 23 and 24: no internet
def test_interface_funciona_sem_internet(producao, sem_rede):
    """Real HTTP server on 127.0.0.1, with every outgoing connection blocked: all screens answer."""
    servidor = criar_servidor(producao["cfg"].banco, "127.0.0.1", 0)
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))    # no proxy from the environment
    try:
        base = f"http://127.0.0.1:{servidor.server_port}"
        for caminho, params in rotas_com_parametros(2026, "2026-08-31", 1, 2025, 5659):
            url = base + caminho + ("?" + urlencode(params) if params else "")
            with abridor.open(url, timeout=30) as r:
                assert r.status == 200, url
                corpo = r.read().decode("utf-8")
            assert corpo
    finally:
        servidor.shutdown()
        servidor.server_close()
    assert sem_rede == []


# ================================================================== HTML security
def test_cabecalhos_de_seguranca_e_nenhum_recurso_externo(app_producao):
    for caminho, params in rotas_com_parametros(2026, "2026-08-31", 1, 2025, 5659):
        status, cab, corpo = chamar(app_producao, caminho, **params)
        assert status == "200 OK"
        assert "default-src 'none'" in cab["Content-Security-Policy"] and cab["X-Content-Type-Options"] == "nosniff"
        assert cab["Referrer-Policy"] == "no-referrer" and cab["X-Frame-Options"] == "DENY"
        if caminho != "/estilo.css":
            assert "<script" not in corpo.lower() and " src=" not in corpo.lower()
            # an outgoing link only to the official portal (where to check the value), marked rel="external"; no external
            # resource is loaded (no src) and the interface keeps working without network
            for tag in re.findall(r"<a\s[^>]*>", corpo):
                href = re.search(r'href="([^"]*)"', tag).group(1)
                assert href.startswith(("/", "#")) or (href.startswith(portal.SITE + "/") or href.startswith(portal.API + "/")) \
                    and 'rel="external' in tag, (caminho, tag)
            assert all(h.startswith(("/", "#", portal.DOMINIO + "/")) for h in re.findall(r'href="([^"]*)"', corpo)), caminho
    assert "@import" not in aplicacao.ESTILO.decode() and "url(" not in aplicacao.ESTILO.decode()


def test_SINTETICO_texto_do_banco_e_escapado(mundo):
    mundo.catalogos({1: [2025]})
    ataque = '<script>alert("x")</script>'
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1, descricaoFonte=ataque, nome="EMPRESA <b>X</b>",
                                               cnpjNome="11.222.333/0001-44 - EMPRESA <b>X</b>")],
                   "2026-09-29T20:00:00-03:00")
    mundo.processar()
    app = Aplicacao(mundo.cfg.banco)
    base = dict(exercicio=2025, data_final="2025-12-31")
    for corpo in (ok(app, "/empenhos", **base), ok(app, "/empenho", entidade=1, anoempenho=2024, empenho=1, **base)):
        assert "<script" not in corpo and "&lt;script&gt;" in corpo
    assert "<b>X</b>" not in ok(app, "/empenho", entidade=1, anoempenho=2024, empenho=1, **base)


def test_parametros_invalidos_e_rotas(app_producao):
    assert chamar(app_producao, "/", exercicio="dois mil")[0] == "400 Bad Request"
    assert chamar(app_producao, "/", data_final="31/12/2025")[0] == "400 Bad Request"
    assert chamar(app_producao, "/", em="2026-13-45")[0] == "400 Bad Request"
    assert chamar(app_producao, "/empenhos", categoria="qualquer", **CORTE_REAL)[0] == "400 Bad Request"
    assert chamar(app_producao, "/comparar", a="../../etc", b="x")[0] == "400 Bad Request"
    assert chamar(app_producao, "/", x="a" * 3000)[0] == "400 Bad Request"
    assert chamar(app_producao, "/nao-existe")[0] == "404 Not Found"
    status, cab, corpo = chamar(app_producao, "/", metodo="HEAD")
    assert status == "200 OK" and corpo == "" and int(cab["Content-Length"]) > 0


def test_listagem_paginada_nao_carrega_o_corte_inteiro(app_producao):
    corpo = ok(app_producao, "/empenhos", entidade=1, **CORTE_REAL)
    tabela = corpo[corpo.index('class="tabela empenhos"'):]
    tabela = tabela[:tabela.index("</table>")]
    assert tabela.count("<tr>") == paginas.TAMANHO_PAGINA + 1       # header + one page
    assert "Página 1 de" in corpo and "próxima »" in corpo
