"""Strict contract of the paginated endpoints (rp.contrato v2, 09/10/2026; correction request, item 3).

Valid JSON is not a valid response: every page must bring all the Spring Page metadata with its type, and every
record must bring exactly the known keys with their types. A violation makes the snapshot 'incompleta' (never the
current one) with the reason, and the responses stay recorded. SINTETICO = simulated portal (fixture `ambiente`).
"""
import json

import pytest
from conftest import completar_registro, pagina

from rp import contrato
from rp.coletor import EP_MOV, EP_RP

REG = lambda n, **kw: completar_registro({"entidade": 1, "anoempenho": 2025, "empenho": n, "aproc": 1.5, **kw})
GRUPO = {"orgao": "24", "unidade": "1", "funcao": "10", "subFuncao": "301", "programa": "1", "projeto": "1",
         "elemento": "3"}


def _listar(ambiente, *paginas):
    for i, corpo in enumerate(paginas):
        ambiente["portal"].rotas[(EP_RP, str(i))] = [(200, corpo)]
    return ambiente["coletor"].listagem(1, 2026, "2026-08-31")


def _sem(d, *chaves):
    return {k: v for k, v in d.items() if k not in chaves}


# ------------------------------------------------------------------ the real data meets the contract
def test_contrato_aceita_o_formato_real():
    assert contrato.contrato_registro_rp(REG(1)) is None
    assert contrato.contrato_registro_rp(REG(1, **GRUPO)) is None
    assert contrato.contrato_registro_mov(completar_registro({"tipoLancamento": 40, "valor": 1.5})) is None
    assert contrato.contrato_pagina(json.loads(pagina([REG(1)], 0, 1, True, 1))) is None


# ------------------------------------------------------------------ page metadata
@pytest.mark.parametrize("campo", sorted(set(contrato.METADADOS_PAGINA) - {"content"}))
def test_SINTETICO_metadado_ausente_torna_a_coleta_incompleta(ambiente, campo):
    s = _listar(ambiente, pagina([REG(1)], 0, 1, True, 1, sem=(campo,)))
    assert s["status"] == "incompleta"
    assert "contrato da API" in s["observacao"] and campo in s["observacao"]


@pytest.mark.parametrize("campo, valor", [("number", "0"), ("numberOfElements", 1.0), ("size", None),
                                          ("totalElements", "1"), ("totalPages", True), ("first", 1),
                                          ("last", "true"), ("empty", None), ("sort", {}), ("pageable", []),
                                          ("totalPages", -1), ("size", 0)])
def test_SINTETICO_metadado_com_tipo_ou_dominio_errado(ambiente, campo, valor):
    s = _listar(ambiente, pagina([REG(1)], 0, 1, True, 1, **{campo: valor}))
    assert s["status"] == "incompleta" and "contrato da API" in s["observacao"] and campo in s["observacao"]


def test_SINTETICO_sem_content_falha_antes_do_contrato(ambiente):
    s = _listar(ambiente, pagina([REG(1)], 0, 1, True, 1, sem=("content",)))
    assert s["status"] == "falhou" and "não é uma página JSON" in s["observacao"]


def test_SINTETICO_json_valido_que_nao_e_pagina(ambiente):
    s = _listar(ambiente, json.dumps({"content": [], "erro": "sessao expirada"}).encode())
    assert s["status"] == "incompleta" and "metadados de página ausentes" in s["observacao"]


# ------------------------------------------------------------------ records of the RP listing
@pytest.mark.parametrize("campo", contrato.DINHEIRO_RP)
def test_SINTETICO_campo_monetario_ausente_nulo_ou_texto(ambiente, campo):
    for registro, trecho in ((_sem(REG(1), campo), "ausente"), (REG(1, **{campo: None}), "tipo fora do contrato"),
                             (REG(1, **{campo: "1,50"}), "tipo fora do contrato"),
                             (REG(1, **{campo: True}), "tipo fora do contrato")):
        ambiente["portal"].rotas.clear()
        s = _listar(ambiente, pagina([registro], 0, 1, True, 1, completar=False))
        assert s["status"] == "incompleta", (campo, registro)
        assert trecho in s["observacao"] and campo in s["observacao"], s["observacao"]


def test_SINTETICO_zero_valido_e_aceito(ambiente):
    s = _listar(ambiente, pagina([REG(1, **{c: 0 for c in contrato.DINHEIRO_RP})], 0, 1, True, 1))
    assert s["status"] == "completa"


def test_SINTETICO_chave_nova_ou_grupo_parcial(ambiente):
    s = _listar(ambiente, pagina([REG(1, credor="x")], 0, 1, True, 1))
    assert s["status"] == "incompleta" and "fora do contrato: credor" in s["observacao"]
    ambiente["portal"].rotas.clear()
    s = _listar(ambiente, pagina([REG(1, orgao="24")], 0, 1, True, 1))
    assert s["status"] == "incompleta" and "grupo de classificação incompleto" in s["observacao"]


def test_SINTETICO_identidade_com_tipo_errado(ambiente):
    s = _listar(ambiente, pagina([REG(1, anoempenho="2025")], 0, 1, True, 1))
    assert s["status"] == "incompleta" and "anoempenho" in s["observacao"]


def test_SINTETICO_problema_na_segunda_pagina_preserva_as_respostas(ambiente):
    s = _listar(ambiente, pagina([REG(1)], 0, 2, False, 2), pagina([_sem(REG(2), "pagoProc")], 1, 2, True, 2,
                                                                     completar=False))
    assert s["status"] == "incompleta" and "página 1" in s["observacao"] and s["respostas"] == 2
    m = ambiente["armazem"].ler_manifesto(s["manifesto"])
    assert len(m["respostas"]) == 2                     # the problematic response stays recorded


# ------------------------------------------------------------------ movement list
def test_SINTETICO_movimentacao_fora_do_contrato(ambiente):
    p = ambiente["portal"]
    mov = completar_registro({"tipoLancamento": 40, "valor": 1.5})
    p.rotas[(EP_MOV, "0")] = [(200, pagina([_sem(mov, "valor")], 0, 1, True, 1, completar=False))]
    s = ambiente["coletor"].movimentacao(1, 2025, 7)
    assert s["status"] == "incompleta" and "valor" in s["observacao"]
    p.rotas[(EP_MOV, "0")] = [(200, pagina([mov], 0, 1, True, 1))]
    assert ambiente["coletor"].movimentacao(1, 2025, 8)["status"] == "completa"


def test_versao_do_contrato_registrada():
    assert contrato.VERSAO == "rp-api-contrato/2"
