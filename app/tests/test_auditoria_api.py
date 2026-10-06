"""Regression of the technical audit, groups G2 and G3: HTTP client and pagination (phase 15 of the audit).

Simulated transport (fixture `ambiente`): no real request. Each test cites the phase 15 case or the finding's ID in
docs/audits/TECHNICAL_AUDIT.md.
"""
import json
from datetime import datetime, timezone

import pytest
from conftest import pagina

from rp.coletor import EP_ENT, EP_EXE, EP_RP
from rp.http import ErroDeRede, RespostaRecusada, espera_retry_after

REG = lambda n, **kw: {"entidade": 1, "anoempenho": 2025, "empenho": n, "proc": 1.5, "aproc": 0, **kw}


def _pag(regs, numero, total, ultima, paginas, size=2000):
    d = json.loads(pagina(regs, numero, total, ultima, paginas))
    d["size"] = size
    return json.dumps(d).encode()


def _listar(ambiente):
    return ambiente["coletor"].listagem(1, 2026, "2026-08-31")


def test_API01_normal_varias_paginas_completa_com_segunda_leitura_no_manifesto(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [(200, _pag([REG(1), REG(2)], 0, 3, False, 2, size=2))]
    p.rotas[(EP_RP, "1")] = [(200, _pag([REG(3)], 1, 3, True, 2, size=2))]
    s = _listar(ambiente)
    assert s["status"] == "completa" and len(p.chamadas) == 4 and s["respostas"] == 2
    m = ambiente["armazem"].ler_manifesto(s["manifesto"])
    assert [x["igual"] for x in m["segunda_leitura"]] == [True, True]
    for x in m["segunda_leitura"]:                                      # bytes kept, outside the responses
        ambiente["armazem"].ler_objeto(x["sha256"], x["tamanho"])
    con = ambiente["con"]
    assert con.execute("SELECT COUNT(*) FROM resposta_bruta WHERE coleta_id=?", (s["coleta_id"],)).fetchone()[0] == 2
    assert "segunda leitura das 2 páginas idêntica" in s["observacao"]


def test_API01_uma_pagina_nao_e_lida_duas_vezes(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [(200, _pag([REG(1), REG(2)], 0, 2, True, 1))]
    s = _listar(ambiente)
    assert s["status"] == "completa" and len(p.chamadas) == 1
    assert "segunda_leitura" not in ambiente["armazem"].ler_manifesto(s["manifesto"])


def test_API02_total_que_muda_entre_paginas(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [(200, _pag([REG(1), REG(2)], 0, 3, False, 2, size=2))]
    p.rotas[(EP_RP, "1")] = [(200, _pag([REG(3)], 1, 4, True, 2, size=2))]
    s = _listar(ambiente)
    assert s["status"] == "incompleta" and "totalElements mudou" in s["observacao"]


def test_API03_mesma_pagina_repetida_com_number_ecoado_certo(ambiente):
    p = ambiente["portal"]   # the server ignores page but echoes the requested number: the identical record gives it away
    p.rotas[(EP_RP, "0")] = [(200, _pag([REG(1), REG(2)], 0, 4, False, 2, size=2))]
    p.rotas[(EP_RP, "1")] = [(200, _pag([REG(1), REG(2)], 1, 4, True, 2, size=2))]
    s = _listar(ambiente)
    assert s["status"] == "incompleta" and "registro idêntico" in s["observacao"]


def test_API04_registro_duplicado_entre_paginas_com_soma_igual_ao_total(ambiente):
    # the audit's example: A B C | C D E, total 6 - the old rule (sum = total) accepted it
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [(200, _pag([REG(1), REG(2), REG(3)], 0, 6, False, 2, size=3))]
    p.rotas[(EP_RP, "1")] = [(200, _pag([REG(3), REG(4), REG(5)], 1, 6, True, 2, size=3))]
    s = _listar(ambiente)
    assert s["status"] == "incompleta" and "registro idêntico" in s["observacao"]
    # same key with a changed value across the page change (record shifted and updated): the order gives it away
    p.chamadas.clear()
    p.rotas[(EP_RP, "1")] = [(200, _pag([REG(3, proc=9.0), REG(4), REG(5)], 1, 6, True, 2, size=3))]
    s = _listar(ambiente)
    assert s["status"] == "incompleta" and "não cresce" in s["observacao"]


def test_API05_registro_que_some_entre_paginas_com_soma_igual_ao_total(ambiente):
    # 1 2 3 | 5 6 7: 2 was deleted and 7 added during pagination; 4 was lost. Sum, total and order
    # pass; only the second read (page 0 now different) shows that the base changed
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [(200, _pag([REG(1), REG(2), REG(3)], 0, 6, False, 2, size=3)),
                             (200, _pag([REG(1), REG(3), REG(4)], 0, 6, False, 2, size=3))]
    p.rotas[(EP_RP, "1")] = [(200, _pag([REG(5), REG(6), REG(7)], 1, 6, True, 2, size=3))]
    s = _listar(ambiente)
    assert s["status"] == "incompleta" and "segunda leitura da página 0 diferente" in s["observacao"]
    m = ambiente["armazem"].ler_manifesto(s["manifesto"])
    assert m["segunda_leitura"][-1]["igual"] is False                   # the evidence stays in the manifest


def test_API06_size_limitado_pelo_servidor_e_aceito_se_coerente(ambiente):
    p = ambiente["portal"]   # asked for 2000, the server uses 2 (as the real API does with 5000 -> 2000)
    p.rotas[(EP_RP, "0")] = [(200, _pag([REG(1), REG(2)], 0, 3, False, 2, size=2))]
    p.rotas[(EP_RP, "1")] = [(200, _pag([REG(3)], 1, 3, True, 2, size=2))]
    assert _listar(ambiente)["status"] == "completa"


def test_API06_size_ecoado_maior_que_o_pedido_e_recusado(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [(200, _pag([REG(1)], 0, 1, True, 1, size=5000))]
    s = _listar(ambiente)
    assert s["status"] == "incompleta" and "size ecoado 5000" in s["observacao"]


def test_API07_page_ignorado(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_RP, None)] = [(200, _pag([REG(1), REG(2)], 0, 4, False, 2, size=2))]
    s = _listar(ambiente)
    assert s["status"] == "incompleta" and len(p.chamadas) == 2 and "number=0" in s["observacao"]


def test_API08_last_incorreto_e_totais_inconsistentes(ambiente):
    p = ambiente["portal"]
    # last=false on the last page: stops at totalPages, without asking for a page out of range (COL-04: 2 calls)
    p.rotas[(EP_RP, "0")] = [(200, _pag([REG(1), REG(2)], 0, 3, False, 2, size=2))]
    p.rotas[(EP_RP, "1")] = [(200, _pag([REG(3)], 1, 3, False, 2, size=2))]
    s = _listar(ambiente)
    assert s["status"] == "incompleta" and len(p.chamadas) == 2 and "não é a última" in s["observacao"]
    # last=true too early
    p.chamadas.clear()
    p.rotas[(EP_RP, "0")] = [(200, _pag([REG(1)], 0, 3, True, 2, size=2))]
    assert _listar(ambiente)["status"] == "incompleta"
    # totalElements missing (COL-03): fails on the first page, without paginating further
    p.chamadas.clear()
    p.rotas[(EP_RP, "0")] = [(200, json.dumps({"content": [REG(1)], "last": False}).encode())]
    s = _listar(ambiente)
    assert s["status"] == "incompleta" and len(p.chamadas) == 1 and "totalElements ausente" in s["observacao"]
    # totalPages inconsistent with total and size
    p.chamadas.clear()
    p.rotas[(EP_RP, "0")] = [(200, _pag([REG(1)], 0, 1, True, 7, size=2000))]
    assert "totalPages=7 incoerente" in _listar(ambiente)["observacao"]


def test_API09_429_respeita_retry_after_e_repete(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [(429, b"devagar"), (200, _pag([REG(1)], 0, 1, True, 1))]
    original = p.get

    def get(url, timeout):   # the 429 comes with Retry-After in the header
        st, h, corpo = original(url, timeout)
        return st, ({**h, "Retry-After": "40"} if st == 429 else h), corpo
    ambiente["coletor"].cliente.transporte = get
    s = _listar(ambiente)
    assert s["status"] == "completa" and len(p.chamadas) == 2 and 40 in ambiente["relogio"].dormiu


def test_API09_retry_after_em_data_http():
    agora = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    assert espera_retry_after("Fri, 02 Oct 2026 12:01:30 GMT", agora) == 90
    assert espera_retry_after("120", agora) == 120
    assert espera_retry_after("data ruim", agora) is None and espera_retry_after(None, agora) is None


def test_API10_500_repete_e_esgota(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [(500, b"erro")]
    s = _listar(ambiente)
    assert s["status"] == "falhou" and len(p.chamadas) == 3 and "HTTP 500" in s["observacao"]


def test_API11_timeout_e_transitorio(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [TimeoutError("tempo esgotado")]
    s = _listar(ambiente)
    assert s["status"] == "falhou" and len(p.chamadas) == 3 and "TimeoutError" in s["observacao"]


def test_API12_json_invalido(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [(200, b"<html>manutencao</html>")]
    s = _listar(ambiente)
    assert s["status"] == "falhou" and len(p.chamadas) == 1 and "não é uma página JSON" in s["observacao"]


def test_API13_resposta_grande_demais_nao_e_repetida(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [RespostaRecusada("corpo maior que 10 bytes")]
    s = _listar(ambiente)
    assert s["status"] == "falhou" and len(p.chamadas) == 1 and "resposta recusada" in s["observacao"]


def test_API14_redirecionamento_nao_e_seguido(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [(302, b"")]
    s = _listar(ambiente)
    assert s["status"] == "falhou" and len(p.chamadas) == 1 and "HTTP 302" in s["observacao"]


def test_API15_erro_de_programacao_no_transporte_propaga_sem_repetir(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [TypeError("bug no transporte")]
    with pytest.raises(TypeError, match="bug no transporte"):
        _listar(ambiente)
    assert len(p.chamadas) == 1                                         # neither retried nor turned into "rede"


def test_HTTP01_transporte_requests_classifica_as_excecoes(monkeypatch):
    import requests
    from requests import exceptions as rx

    from rp import http
    casos = [(rx.ConnectTimeout("t"), http.FalhaTransitoria), (rx.ConnectionError("c"), http.FalhaTransitoria),
             (rx.ChunkedEncodingError("x"), http.FalhaTransitoria), (rx.SSLError("certificado"), ErroDeRede),
             (rx.InvalidURL("u"), ErroDeRede), (AttributeError("bug"), AttributeError)]
    for exc, esperado in casos:
        def get(self, *a, exc=exc, **k):
            raise exc
        monkeypatch.setattr(requests.Session, "get", get)
        with pytest.raises(esperado):
            http.transporte_requests("ua", 100, 10)("https://exemplo.invalido/x", 1)


def test_HTTP01_tls_nao_e_repetido(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [ErroDeRede("falha de TLS: certificado")]
    s = _listar(ambiente)
    assert s["status"] == "falhou" and len(p.chamadas) == 1 and "TLS" in s["observacao"]


def test_COL05_entidade_fora_do_catalogo_fica_registrada(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_ENT, None)] = [(200, json.dumps([{"id": 1, "nome": "A"}, {"id": 15, "nome": "B"}]).encode())]
    p.rotas[(f"{EP_EXE}/1", None)] = [(200, json.dumps([{"id": {"entidade": {"id": 1}, "exercicio": 2026}}]).encode())]
    ambiente["coletor"].catalogos([1])
    p.rotas[(EP_RP, "0")] = [(200, _pag([], 0, 0, True, 0))]
    s = ambiente["coletor"].listagem(51, 2026, "2026-08-31")
    assert s["status"] == "completa" and "entidade 51 fora do catálogo vigente" in s["observacao"]
    s = ambiente["coletor"].listagem(1, 2026, "2026-08-31")
    assert "fora do catálogo" not in (s["observacao"] or "")
    s = ambiente["coletor"].listagem(1, 2025, "2025-08-31")
    assert "exercício 2025 da entidade 1 fora do catálogo" in s["observacao"]
