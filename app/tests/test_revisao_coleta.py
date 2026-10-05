"""Revisao critica (05/10/2026), etapa A - coleta: itens 2, 3, 6, 8, 17, 18, 20, 21, 35 e 50.

Cada teste cita o item da revisao (auditoria/REVISAO_CRITICA_RESPOSTA.md). Transporte simulado (fixture `ambiente`),
exceto os do item 8, que sobem um servidor HTTP local de verdade em 127.0.0.1 (nada sai da maquina).
"""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from conftest import pagina

from rp import contrato, importar
from rp.coletor import EP_ENT, EP_EXE, EP_PUB, EP_RP
from rp.http import RespostaRecusada, com_prazo_total, transporte_requests
from rp.snapshots import status_de_paginas

REG = lambda n, **kw: {"entidade": 1, "anoempenho": 2025, "empenho": n, "proc": 1.5, "aproc": 0, **kw}
SORT_ECO = [{"property": "anoempenho", "ascending": True, "descending": False, "direction": "ASC"},
            {"property": "empenho", "ascending": True, "descending": False, "direction": "ASC"}]


def _pag(regs, numero, total, ultima, paginas, size=2000, sort=None):
    d = json.loads(pagina(regs, numero, total, ultima, paginas))
    d["size"] = size
    if sort is not None:
        d["sort"] = sort
    return json.dumps(d).encode()


def _listar(ambiente):
    return ambiente["coletor"].listagem(1, 2026, "2026-08-31")


# ------------------------------------------------------------------ itens 1, 2 e 35: chave de negocio unica
def test_REV02_chave_repetida_dentro_da_pagina_copia_exata(ambiente):
    p = ambiente["portal"]   # a regra antiga so olhava paginas ANTERIORES: [A, A] na mesma pagina passava
    p.rotas[(EP_RP, "0")] = [(200, _pag([REG(1), REG(2), REG(2)], 0, 3, True, 1))]
    s = _listar(ambiente)
    assert s["status"] == "incompleta" and len(p.chamadas) == 1
    assert "1 exata(s)" in s["observacao"] and "0 conflitante(s)" in s["observacao"]
    assert "não vira o retrato vigente" in s["observacao"]


def test_REV02_chave_repetida_dentro_da_pagina_conteudo_diferente(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [(200, _pag([REG(1), REG(2), REG(2, proc=9.0)], 0, 3, True, 1))]
    s = _listar(ambiente)
    assert s["status"] == "incompleta" and "1 conflitante(s)" in s["observacao"] and "0 exata(s)" in s["observacao"]


def test_REV02_repeticao_classificada_por_chave_e_sem_segunda_leitura(ambiente):
    p = ambiente["portal"]   # chave 2 com 3 copias (uma diferente) e chave 4 com 2 copias iguais, na pagina 1
    p.rotas[(EP_RP, "0")] = [(200, _pag([REG(1)], 0, 6, False, 2, size=5))]
    p.rotas[(EP_RP, "1")] = [(200, _pag([REG(2), REG(2), REG(2, aproc=3.0), REG(4), REG(4)], 1, 6, True, 2, size=5))]
    s = _listar(ambiente)
    assert s["status"] == "incompleta" and len(p.chamadas) == 2          # parou na pagina 1, sem segunda leitura
    assert "2 chave(s), 1 exata(s)" in s["observacao"] and "1 conflitante(s)" in s["observacao"]
    assert "segunda_leitura" not in ambiente["armazem"].ler_manifesto(s["manifesto"])


def test_REV02_mesmo_empenho_em_anos_diferentes_nao_e_repeticao(ambiente):
    p = ambiente["portal"]   # a chave e (entidade, anoempenho, empenho): o numero do empenho sozinho repete entre anos
    p.rotas[(EP_RP, "0")] = [(200, _pag([REG(5, anoempenho=2024), REG(5, anoempenho=2025)], 0, 2, True, 1))]
    assert _listar(ambiente)["status"] == "completa"


def test_REV02_chave_repetida_entre_paginas_continua_recusada(ambiente):
    # caso 1 do item 35: pagina 0 = A B, pagina 1 = B C (B com outro valor): ordem e chave denunciam
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [(200, _pag([REG(1), REG(2)], 0, 4, False, 2, size=2))]
    p.rotas[(EP_RP, "1")] = [(200, _pag([REG(2, proc=7.0), REG(3)], 1, 4, True, 2, size=2))]
    assert _listar(ambiente)["status"] == "incompleta"


@pytest.mark.parametrize("pagina1, trecho", [
    # item 35, teste 2: a pagina 1 chega dizendo number=0
    (lambda: _pag([REG(3), REG(4)], 0, 4, True, 2, size=2), "a API devolveu a página number=0"),
    # item 35, teste 3: numberOfElements diferente do content
    (lambda: _alterar(_pag([REG(3), REG(4)], 1, 4, True, 2, size=2), numberOfElements=3), "numberOfElements=3"),
    # item 2: first e empty coerentes (presentes e coerentes nas 322 paginas reais gravadas)
    (lambda: _alterar(_pag([REG(3), REG(4)], 1, 4, True, 2, size=2), first=True), "first=True incoerente"),
    (lambda: _alterar(_pag([REG(3), REG(4)], 1, 4, True, 2, size=2), empty=True), "empty=True mas content tem 2"),
])
def test_REV35_contrato_da_pagina_seguinte(ambiente, pagina1, trecho):
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [(200, _alterar(_pag([REG(1), REG(2)], 0, 4, False, 2, size=2), first=True, empty=False))]
    p.rotas[(EP_RP, "1")] = [(200, pagina1())]
    s = _listar(ambiente)
    assert s["status"] == "incompleta" and trecho in s["observacao"], s["observacao"]


def _alterar(corpo, **campos):
    d = json.loads(corpo)
    d.update(campos)
    return json.dumps(d).encode()


def test_REV02_status_de_paginas_do_importador_com_chave_unica():
    repetida = [json.dumps({"content": [REG(1), REG(1)], "totalElements": 2, "last": True}).encode()]
    assert status_de_paginas(repetida) == "completa"                    # movimentacao: lancamentos repetem a chave
    assert status_de_paginas(repetida, chave_unica=True) == "incompleta"  # listagem de RP: nao pode
    unica = [json.dumps({"content": [REG(1), REG(2)], "totalElements": 2, "last": True}).encode()]
    assert status_de_paginas(unica, chave_unica=True) == "completa"


def test_REV15_identidade_do_conteudo_e_da_chave():
    a, b = REG(1, proc=1.5), {"proc": 1.5, "aproc": 0, "empenho": 1, "anoempenho": 2025, "entidade": 1}
    assert contrato.chave_negocio(a) == (1, 2025, 1)
    assert contrato.impressao_registro(a) == contrato.impressao_registro(b)     # ordem das chaves nao importa
    assert contrato.impressao_registro(a) != contrato.impressao_registro(REG(1, proc=1.51))


# ------------------------------------------------------------------ item 3: ordenacao pedida e eco conferido
def test_REV03_listagem_pede_a_ordem_em_dois_campos(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [(200, _pag([REG(1)], 0, 1, True, 1, sort=SORT_ECO))]
    s = _listar(ambiente)
    assert s["status"] == "completa"
    m = ambiente["armazem"].ler_manifesto(s["manifesto"])
    assert m["parametros"]["sort"] == ["anoempenho,asc", "empenho,asc"]
    assert "sort=anoempenho%2Casc&sort=empenho%2Casc" in m["respostas"][0]["url"]   # parametro repetido (doseq)


def test_REV03_servidor_que_ignora_a_ordem_pedida(ambiente):
    p = ambiente["portal"]   # a API real ecoa sort=[] quando nao aplica ordem nenhuma
    p.rotas[(EP_RP, "0")] = [(200, _pag([REG(1)], 0, 1, True, 1, sort=[]))]
    s = _listar(ambiente)
    assert s["status"] == "incompleta" and "não aplicou a ordenação pedida" in s["observacao"]


def test_REV03_eco_com_outra_ordem(ambiente):
    p = ambiente["portal"]
    outra = [{"property": "empenho", "direction": "DESC"}]
    p.rotas[(EP_RP, "0")] = [(200, _pag([REG(1)], 0, 1, True, 1, sort=outra))]
    assert _listar(ambiente)["status"] == "incompleta"


def test_REV03_sort_ecoado_confere():
    pedido = contrato.ORDEM_RP
    assert contrato.sort_ecoado_confere(SORT_ECO, pedido)
    assert not contrato.sort_ecoado_confere(SORT_ECO[::-1], pedido)
    assert not contrato.sort_ecoado_confere(SORT_ECO[:1], pedido)
    assert not contrato.sort_ecoado_confere([], pedido)
    assert not contrato.sort_ecoado_confere("anoempenho,asc", pedido)


# ------------------------------------------------------------------ item 6: contrato minimo dos catalogos
ENTIDADES_OK = [{"id": 1, "nome": "MUNICIPIO", "cnpj": None, "tipo": "A"}]


@pytest.mark.parametrize("corpo, trecho", [
    ({"erro": "não autorizado"}, "não é uma lista"),        # o exemplo da revisao: HTTP 200 com objeto de erro
    ([], "vazio"),
    ([{"nome": "SEM ID"}], "não tem 'id' inteiro"),
    ([{"id": "1"}], "não tem 'id' inteiro"),
    ([1, 2], "não é um objeto"),
])
def test_REV06_catalogo_de_entidades_fora_do_contrato_falha(ambiente, corpo, trecho):
    ambiente["portal"].rotas[(EP_ENT, None)] = [(200, json.dumps(corpo).encode())]
    s = ambiente["coletor"].catalogos([])[0]
    assert s["status"] == "falhou" and trecho in s["observacao"]


def test_REV06_catalogos_dentro_do_contrato(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_ENT, None)] = [(200, json.dumps(ENTIDADES_OK).encode())]
    p.rotas[(f"{EP_EXE}/1", None)] = [(200, json.dumps(
        [{"id": {"entidade": {"id": 1}, "exercicio": 2025}, "aberto": False, "fechado": True}]).encode())]
    assert [s["status"] for s in ambiente["coletor"].catalogos([1])] == ["completa", "completa"]


def test_REV06_exercicios_de_outra_entidade_falha(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_ENT, None)] = [(200, json.dumps(ENTIDADES_OK).encode())]
    p.rotas[(f"{EP_EXE}/1", None)] = [(200, json.dumps(
        [{"id": {"entidade": {"id": 15}, "exercicio": 2025}}]).encode())]
    s = ambiente["coletor"].catalogos([1])[1]
    assert s["status"] == "falhou" and "é da entidade 15" in s["observacao"]


def test_REV06_publicacoes_fora_do_contrato_nao_baixam_pdf(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_PUB, None)] = [(200, json.dumps({"erro": "x"}).encode())]
    feitos = ambiente["coletor"].rreo(2025, entidade=1)
    assert len(feitos) == 1 and feitos[0]["status"] == "falhou" and "publicações" in feitos[0]["observacao"]


# ------------------------------------------------------------------ itens 17, 18 e 50: manifesto
def test_REV18_manifesto_tem_inicio_fim_e_forma(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [(200, _pag([REG(1), REG(2)], 0, 3, False, 2, size=2))]
    p.rotas[(EP_RP, "1")] = [(200, _pag([REG(3)], 1, 3, True, 2, size=2))]
    s = _listar(ambiente)
    m = ambiente["armazem"].ler_manifesto(s["manifesto"])
    assert m["coleta_finalizada_em"] >= m["coletada_em"]
    c = m["contrato_api"]
    assert c["versao"] == contrato.VERSAO and len(c["forma_sha256"]) == 64
    assert "$.content[].proc:number" in c["forma"] and "$.totalElements:number" in c["forma"]
    # o banco e a verificacao ignoram os campos novos (aditivos, como segunda_leitura)
    from rp import banco
    assert banco.verificar(ambiente["con"], ambiente["armazem"]) == []


def test_REV50_forma_detecta_campo_novo_removido_e_tipo_diferente():
    base = contrato.forma([json.dumps({"content": [REG(1)], "totalElements": 1}).encode()])
    assert contrato.comparar_formas(base, base)["igual"]
    tipo = contrato.forma([json.dumps({"content": [REG(1, proc="1,50")], "totalElements": 1}).encode()])
    d = contrato.comparar_formas(base, tipo)
    assert not d["igual"] and d["tipo_diferente"] == ["$.content[].proc: number -> string"]
    novo = contrato.forma([json.dumps({"content": [REG(1, extra=1)], "totalElements": 1}).encode()])
    assert contrato.comparar_formas(base, novo)["novos"] == ["$.content[].extra"]
    assert contrato.comparar_formas(novo, base)["removidos"] == ["$.content[].extra"]
    nulo = contrato.forma([json.dumps({"content": [REG(1, proc=None)], "totalElements": 1}).encode()])
    assert contrato.comparar_formas(base, nulo)["igual"]      # campo opcional que veio vazio nao e mudanca de tipo
    assert contrato.forma([b"%PDF-1.4 ..."]) is None


# ------------------------------------------------------------------ item 8: prazo total absoluto (servidor local)
class _Lento(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _pingar(self, dados, pausa):
        for i in range(len(dados)):
            self.wfile.write(dados[i:i + 1])
            self.wfile.flush()
            time.sleep(pausa)

    def do_GET(self):
        try:
            if self.path == "/corpo-lento":         # cabecalhos na hora; 40 bytes de corpo, 1 a cada 0,25 s (10 s)
                self.send_response(200)
                self.send_header("Content-Length", "40")
                self.end_headers()
                self._pingar(b"x" * 40, 0.25)
            elif self.path == "/cabecalho-lento":   # a linha de status e os cabecalhos chegam a conta-gotas (~8 s)
                self._pingar(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok", 0.2)
            else:
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"ok")
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            return                                   # o cliente desistiu: fim


@pytest.fixture
def servidor_lento(monkeypatch):
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Lento)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


@pytest.mark.parametrize("caminho", ["/corpo-lento", "/cabecalho-lento"])
def test_REV08_prazo_total_e_absoluto_com_servidor_que_pinga(servidor_lento, caminho):
    # leitura de 1 s nunca esgota (chega 1 byte a cada 0,2-0,25 s); o prazo total de 1,5 s tem de valer mesmo assim.
    # Codigo anterior: o corpo so era conferido ao fim de um bloco de 64 KiB (10 s) e o cabecalho nunca.
    get = transporte_requests("teste", 10 ** 6, prazo_total=1.5, timeout_conexao=1)
    antes = {t.ident for t in threading.enumerate() if t.name == "rp-http"}
    inicio = time.monotonic()
    with pytest.raises(RespostaRecusada, match="prazo total"):
        get(servidor_lento + caminho, 1.0)
    assert time.monotonic() - inicio < 3.0
    if caminho == "/corpo-lento":   # com a resposta em maos, a conexao e derrubada: a thread de leitura termina logo
        limite = time.monotonic() + 2.0
        while time.monotonic() < limite and any(t.name == "rp-http" and t.ident not in antes
                                               for t in threading.enumerate()):
            time.sleep(0.05)
        assert not any(t.name == "rp-http" and t.ident not in antes for t in threading.enumerate())


def test_REV08_resposta_rapida_continua_normal(servidor_lento):
    get = transporte_requests("teste", 10 ** 6, prazo_total=5, timeout_conexao=1)
    status, _, corpo = get(servidor_lento + "/rapido", 1.0)
    assert (status, corpo) == (200, b"ok")


def test_REV08_com_prazo_total_repassa_erro_e_resultado():
    assert com_prazo_total(lambda e: 42, 1) == 42
    with pytest.raises(KeyError):                # erro de programa propaga com o tipo original (nunca vira "rede")
        com_prazo_total(lambda e: {}["x"], 1)
    vencidos = []
    with pytest.raises(RespostaRecusada):
        com_prazo_total(lambda e: time.sleep(2), 0.2, vencidos.append)
    assert vencidos and vencidos[0]["vencido"] is True


# ------------------------------------------------------------------ itens 20 e 21: importador
def test_REV21_fuso_convertido_e_nao_sobrescrito():
    assert importar._iso("2026-09-29T10:00:00") == "2026-09-29T10:00:00-03:00"          # sem fuso: Brasilia
    assert importar._iso("2026-09-29T13:00:00+00:00") == "2026-09-29T10:00:00-03:00"    # 13h UTC = 10h BRT
    assert importar._iso("2026-09-29T10:00:00-03:00") == "2026-09-29T10:00:00-03:00"


def test_REV20_mesmo_uid_com_outro_conteudo_e_conflito(ambiente):
    con, arm = ambiente["con"], ambiente["armazem"]
    kw = dict(tipo="rp_listagem", endpoint=EP_RP, parametros={"entidade": 1, "exercicio": 2026},
              coletada_em="2026-09-29T10:00:00-03:00", origem_carimbo="manifesto", status="completa",
              coletor={"nome": "teste", "versao": "1", "sha256_codigo": None})
    original = [{"url": "u", "corpo": b'{"content": []}'}]
    assert importar._gravar(con, arm, "etapa02/api/x", respostas=original, **kw) == 1
    assert importar._gravar(con, arm, "etapa02/api/x", respostas=original, **kw) == 0     # mesmo conteudo: nada
    with pytest.raises(importar.ConflitoDeImportacao, match="bytes"):
        importar._gravar(con, arm, "etapa02/api/x", respostas=[{"url": "u", "corpo": b'{"content": [1]}'}], **kw)
    with pytest.raises(importar.ConflitoDeImportacao, match="parâmetros"):
        importar._gravar(con, arm, "etapa02/api/x", respostas=original, **{**kw, "parametros": {"entidade": 2}})
    assert con.execute("SELECT COUNT(*) FROM coleta").fetchone()[0] == 1
