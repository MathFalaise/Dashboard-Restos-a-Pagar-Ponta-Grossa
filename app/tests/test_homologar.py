"""Single homologation command (correction request of 09/10/2026, item 9).

The result is never stronger than what was run: 'reprovada' (a technical check failed), 'incompleta' (a mandatory
check was not executed - not homologated), 'aprovada_com_ressalvas' (technical approval, accounting pendencies open)
or 'aprovada_sem_ressalvas'. The suites run here are tiny ones made for the test (the real ones would run themselves
recursively). SINTETICO = temporary database and store (fixture `mundo`).
"""
import json

import pytest
from conftest import registro_sintetico as _reg

from rp import cli, homologar, portoes, proveniencia

T0 = "2026-09-20T10:00:00-03:00"


def _suite(tmp_path, nome, passa=True):
    pasta = tmp_path / f"suite_{nome}"
    (pasta / "tests").mkdir(parents=True)
    (pasta / "tests" / f"test_{nome}.py").write_text(f"def test_{nome}():\n    assert {passa}\n", encoding="utf-8")
    return {nome: (pasta, ["tests"])}


def _carga(mundo, regs=None):
    mundo.catalogos({1: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", regs or [_reg(1), _reg(2, proc=50.0)], T0)
    mundo.processar()
    mundo.con.commit()


def _homologar(mundo, **kw):
    return homologar.homologar(mundo.cfg, mundo.armazem, **kw)


def test_SINTETICO_sem_testes_reproducao_e_referencia_e_incompleta(mundo):
    _carga(mundo)
    r = _homologar(mundo, executar_testes=False, reproduzir_=False)
    assert r["resultado"] == "incompleta" and r["codigo_de_saida"] == 2 and r["aprovacao_tecnica"] is False
    assert set(r["nao_executadas"]) == {"referencia_da_camada_bruta", "reproducao_deterministica", "testes_producao",
                                        "testes_investigacao"}
    assert r["falhas"] == []


def test_SINTETICO_tudo_executado_e_aprovado_com_ressalvas(mundo, tmp_path):
    ref = portoes.gravar_referencia(mundo.cfg.banco, tmp_path / "ref.json")         # BEFORE the load
    _carga(mundo)
    raiz = proveniencia.gerar_raiz(mundo.con)
    r = _homologar(mundo, referencia=ref, raiz=raiz, suites={**_suite(tmp_path, "a"), **_suite(tmp_path, "b")})
    assert r["resultado"] == "aprovada_com_ressalvas" and r["codigo_de_saida"] == 3, (r["falhas"], r["nao_executadas"])
    assert r["aprovacao_tecnica"] is True and r["aprovacao_sem_ressalvas"] is False
    v = {x["id"]: x for x in r["verificacoes"]}
    assert v["reproducao_deterministica"]["ok"] is True
    assert v["raiz_externa_confere"]["ok"] is True and v["camada_bruta_preservada"]["ok"] is True
    assert v["testes_a"]["ok"] is True and "1 passed" in v["testes_a"]["detalhe"]["resumo"]
    # the synthetic world has no RREO and no pair: the pendency is the rule without a governance decision
    assert [p["tipo"] for p in r["pendencias_contabeis"]] == ["regra_sem_decisao"]
    assert "VALOR-OBRIG v1" in r["pendencias_contabeis"][0]["regras"]


def test_SINTETICO_suite_que_falha_reprova(mundo, tmp_path):
    ref = portoes.gravar_referencia(mundo.cfg.banco, tmp_path / "ref.json")
    _carga(mundo)
    r = _homologar(mundo, referencia=ref, suites=_suite(tmp_path, "falha", passa=False))
    assert r["resultado"] == "reprovada" and r["codigo_de_saida"] == 1 and r["falhas"] == ["testes_falha"]
    assert "1 failed" in next(x for x in r["verificacoes"] if x["id"] == "testes_falha")["detalhe"]["resumo"]


def test_SINTETICO_portao_que_falha_reprova(mundo, tmp_path):
    ref = portoes.gravar_referencia(mundo.cfg.banco, tmp_path / "ref.json")
    _carga(mundo, [_reg(1), dict(_reg(2), aproc=None)])                           # a refused money field
    r = _homologar(mundo, referencia=ref, suites=_suite(tmp_path, "a"))
    assert r["resultado"] == "reprovada" and "campos_monetarios_ausentes" in r["falhas"]


def test_SINTETICO_reproducao_acusa_valor_alterado_depois(mundo, tmp_path):
    ref = portoes.gravar_referencia(mundo.cfg.banco, tmp_path / "ref.json")
    _carga(mundo)
    with mundo.con:          # an UPDATE of a value goes through no link trigger; the reproduction catches it
        mundo.con.execute("UPDATE visao_valor SET valor_c = valor_c + 1 WHERE componente='S1'")
    r = _homologar(mundo, referencia=ref, suites=_suite(tmp_path, "a"))
    assert r["resultado"] == "reprovada"
    assert {"reproducao_deterministica", "hash_resultado_confere"} <= set(r["falhas"])
    rep = next(x for x in r["verificacoes"] if x["id"] == "reproducao_deterministica")["detalhe"]
    assert rep["camada0_igual"] is True and rep["derivacao_igual_por_vigencia"] == {"atual": False}


def test_SINTETICO_cli_homologar(mundo, tmp_path, monkeypatch, capsys):
    from test_auditoria_processamento import _config_do_mundo
    monkeypatch.delenv("RP_DADOS_LOCAIS", raising=False)
    _carga(mundo)
    cfg = _config_do_mundo(mundo, tmp_path)
    saida = tmp_path / "homologacao.json"
    assert cli.main(["--config", cfg, "homologar", "--sem-testes", "--sem-reproducao", "--saida", str(saida)]) == 2
    resumo = json.loads(capsys.readouterr().out)
    assert resumo["resultado"] == "incompleta" and json.loads(saida.read_text(encoding="utf-8"))["resultado"] == \
        "incompleta"
    assert cli.main(["--config", cfg, "homologar", "--sem-testes", "--sem-reproducao", "--saida", str(saida)]) == 4


@pytest.mark.parametrize("resultado, codigo", sorted(homologar.CODIGO_DE_SAIDA.items()))
def test_codigos_de_saida_distintos(resultado, codigo):
    assert list(homologar.CODIGO_DE_SAIDA.values()).count(codigo) == 1
