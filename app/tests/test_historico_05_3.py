"""Testes da Subetapa 05.3: serie entre exercicios (contrato M-03 e M-04; plano, secao 05.3).

* corte representativo unico por exercicio para todos os escopos (R8); exercicio sem cobertura; exercicio sem
  nenhum corte com o Municipio disponivel = lacuna para todos os escopos;
* fechamento de A x abertura de A+1 = (a)+(f)(A+1) - S1(A) pela FAIXA v1 (R2); no Municipio, R7;
* verificacao de continuidade lida da derivacao (regime "derivacao", sem reimplementar a regra);
* texto do retrato em todo ponto: estado atual da base, nunca "o que se sabia na epoca";
* validacao independente: serie = recalculo do JSON bruto (recalculo_bruto.py); tela = painel.
SINTETICO = banco temporario com registros inventados (fixture `mundo`).
"""
import json
import re
import time

import pytest
from conftest import chamar, dados, ok, registro_sintetico as _reg, links_permitidos

import recalculo_bruto as rb
from rp.interface import Aplicacao
from rp.painel.consulta import CONTINUIDADE, INDICADORES_ENTRE_EXERCICIOS, ROTULO_EXERCICIO_EM_ABERTO, SITUACOES_DO_PONTO

T0 = "2026-09-29T20:00:00-03:00"
PROIBIDO = re.compile(r"(?i)situação (conhecida )?em \d{4}|conhecid[ao] (em|na época)|Restos a Pagar de \d{4}")


# ================================================================== SINTETICO
@pytest.fixture
def historico(mundo):
    """2022: entidade 1. 2023: sem nenhuma coleta (no catalogo da entidade 1). 2024: entidades 1 e 15 em 31/12.
    2025: 31/10 com as duas; 31/12 so da entidade 1 (exercicio em aberto -> 31/10). 2026: so a entidade 1, sem o
    Municipio completo em nenhum corte (lacuna para todos os escopos)."""
    mundo.catalogos({1: [2022, 2023, 2024, 2025, 2026], 15: [2024, 2025, 2026]})
    mundo.listagem(1, 2022, "2022-12-31", [_reg(9, ano=2021, aproc=10.0)], T0)
    mundo.listagem(1, 2024, "2024-12-31", [_reg(1, ano=2023, aproc=100.0, pagoAProc=30.0),
                                           _reg(2, ano=2022, aproc=0, proc=50.0, pagoProc=10.0)], T0)
    mundo.listagem(15, 2024, "2024-12-31", [_reg(5, entidade=15, ano=2023, aproc=20.0)], T0)
    for df in ("2025-10-31", "2025-12-31"):
        mundo.listagem(1, 2025, df, [_reg(1, ano=2023, aproc=70.0), _reg(2, ano=2022, aproc=0, proc=40.0),
                                     _reg(3, ano=2024, aproc=500.0)], T0)
    mundo.listagem(15, 2025, "2025-10-31", [_reg(5, entidade=15, ano=2023, aproc=15.0)], T0)
    mundo.listagem(1, 2026, "2026-08-31", [_reg(1, ano=2023, aproc=1.0)], T0)
    mundo.processar()
    return mundo


def _sem_valor(ponto):
    return all(v["valor_c"] is None for v in ponto["valores"].values())


def test_SINTETICO_universo_corte_representativo_e_lacunas(historico):
    with historico.painel() as p:
        assert p.corte_representativo(2024)["data_final"] == "2024-12-31" and not p.corte_representativo(2024)["aberto"]
        rep25 = p.corte_representativo(2025)
        assert rep25["data_final"] == "2025-10-31" and rep25["aberto"]                       # R8: nao 31/12
        assert p.corte_representativo(2026)["motivo"] == "Município indisponível em todos os cortes do exercício"
        for ent in (None, 1, 15):
            pts = {x["exercicio"]: x for x in p.serie_entre_exercicios(ent)["exercicios"]}
            assert sorted(pts) == [2022, 2023, 2024, 2025, 2026]
            assert pts[2023]["situacao"]["codigo"] == "exercicio_sem_cobertura" and _sem_valor(pts[2023])
            assert pts[2025]["data_final"] == "2025-10-31"                                 # o mesmo para todo escopo
            assert pts[2026]["situacao"]["codigo"] == "municipio_indisponivel" and _sem_valor(pts[2026])
            assert pts[2026]["motivo_indisponivel"] == "Município indisponível em todos os cortes do exercício"
        um = {x["exercicio"]: x for x in p.serie_entre_exercicios(1)["exercicios"]}
        assert um[2025]["rotulos"] == [ROTULO_EXERCICIO_EM_ABERTO] and um[2024]["rotulos"] == []
        q15 = {x["exercicio"]: x for x in p.serie_entre_exercicios(15)["exercicios"]}
        assert q15[2022]["situacao"]["codigo"] == "inexistente" and _sem_valor(q15[2022])


def test_SINTETICO_fechamento_e_abertura_com_sinal_e_faixa(historico):
    with historico.painel() as p:
        fa = {f["de"]: f for f in p.serie_entre_exercicios()["fechamento_abertura"]}
        assert fa[2022]["motivo_indisponivel"].startswith("exercício 2023 sem valor")
        f = fa[2024]                     # S1(2024) = 70+40 (ent. 1) + 20 (ent. 15); abertura 2025 sem a faixa g (ano 2024)
        assert (f["s1_de_c"], f["a_mais_f_para_c"], f["diferenca_c"]) == (13000, 7000 + 4000 + 1500, -500)
        assert f["natureza"] == "diferenca" and f["regras"] == ["S1 v1", "FAIXA v1"]
        assert f["proveniencia"]["de"]["snapshots"] and f["proveniencia"]["para"]["snapshots"]
        um = {g["de"]: g for g in p.serie_entre_exercicios(1)["fechamento_abertura"]}
        assert (um[2024]["s1_de_c"], um[2024]["a_mais_f_para_c"], um[2024]["diferenca_c"]) == (11000, 11000, 0)
        assert fa[2025]["motivo_indisponivel"].startswith("exercício 2026 sem valor")


def _r7(mundo, registros_da_7):
    mundo.catalogos({1: [2024, 2025], 7: [2024]})
    mundo.listagem(1, 2024, "2024-12-31", [_reg(1, ano=2023, aproc=10.0)], T0)
    mundo.listagem(7, 2024, "2024-12-31", [_reg(1, entidade=7, ano=2023, aproc=5.0)] if registros_da_7 else [], T0)
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1, ano=2023, aproc=10.0)], T0)
    mundo.processar()
    with mundo.painel() as p:
        return p.serie_entre_exercicios()["fechamento_abertura"][0]


def test_SINTETICO_R7_entidade_que_sai_com_registros_bloqueia_o_municipio(mundo):
    f = _r7(mundo, True)
    assert f["diferenca_c"] is None and "[7]" in f["motivo_indisponivel"] and "(R7)" in f["motivo_indisponivel"]


def test_SINTETICO_R7_entidade_que_sai_sem_registros_e_listada(mundo):
    f = _r7(mundo, False)
    assert f["diferenca_c"] == 0 and f["entidades_que_saem"] == [7] and f["motivo_indisponivel"] is None


def test_SINTETICO_continuidade_e_lida_da_derivacao(historico):
    with historico.painel() as p:
        f = {g["de"]: g for g in p.serie_entre_exercicios(1)["fechamento_abertura"]}[2024]
        linhas = [(json.loads(e), v, fa) for e, v, fa in historico.con.execute(
            "SELECT escopo_json, verificados, falhas FROM verificacao WHERE descricao=? AND derivacao_id="
            "(SELECT MAX(id) FROM derivacao_execucao WHERE vigencia_em IS NULL)", (CONTINUIDADE,))]
        esperado = [(v, fa) for e, v, fa in linhas if e["entidade"] == 1 and e["de"] == 2024]
        assert [(x["verificados"], x["falhas"]) for x in f["continuidade"]["linhas"]] == esperado
        assert f["continuidade"]["falhas"] == sum(fa for _, fa in esperado) > 0      # o dado sintetico tem falhas


def test_SINTETICO_tela_retrato_lacunas_e_grafico(historico):
    app = Aplicacao(historico.cfg.banco)
    status, cab, corpo = chamar(app, "/historico", entidade=1)
    assert status == "200 OK" and "default-src 'none'" in cab["Content-Security-Policy"]
    assert re.search(r'id="ret-2024">Estado atual da base para o exercício de 2024, corte 31/12/2024, coletado em '
                     r"\d{2}/\d{2}/\d{4}<", corpo)
    assert 'id="hist-lacuna-2023"' in corpo and 'id="hist-lacuna-2026"' in corpo
    assert SITUACOES_DO_PONTO["exercicio_sem_cobertura"].split(":")[0] in corpo
    linha = re.search(r'id="hist-lacuna-2023".*?</tr>', corpo, re.S).group(0)
    assert "R$" not in linha
    svg = re.search(r"<svg.*?</svg>", corpo, re.S).group(0)
    assert svg.count('class="ponto"') == 5 and svg.count('class="lacuna"') == 2 and "style=" not in svg
    assert links_permitidos(corpo)
    assert not PROIBIDO.search(re.sub(r"<[^>]+>", " ", corpo))
    v = dados(ok(app, "/historico"))
    assert (v["fa-2024-s1"], v["fa-2024-af"], v["fa-2024-dif"]) == (13000, 12500, -500)


# ================================================================== armazem real
@pytest.fixture(scope="module")
def app_real(real):
    return Aplicacao(real["cfg"].banco)


@pytest.fixture(scope="module")
def bruto_real(real):
    return rb.Bruto(real["con"], real["armazem"])


@pytest.fixture(scope="module")
def entidades_reais(real):
    return [None] + [e["entidade"] for e in real["painel"].entidades()["entidades"]]


def test_corte_representativo_real_igual_para_todos_os_escopos(real, bruto_real, entidades_reais):
    p = real["painel"]
    for ex in range(2016, 2027):
        rep = p.corte_representativo(ex)
        assert (rep["data_final"], rep["aberto"]) == bruto_real.corte_representativo(ex)
        assert rep["data_final"] == (f"{ex}-12-31" if ex < 2026 else "2026-08-31") and rep["aberto"] == (ex == 2026)
    for ent in entidades_reais:
        assert {x["exercicio"]: x["data_final"] for x in p.serie_entre_exercicios(ent)["exercicios"]} == {
            ex: (f"{ex}-12-31" if ex < 2026 else "2026-08-31") for ex in range(2016, 2027)}


def test_serie_e_fechamento_iguais_ao_recalculo_do_bruto(real, bruto_real, entidades_reais):
    p, b = real["painel"], bruto_real
    for ent in entidades_reais:
        r = p.serie_entre_exercicios(ent)
        brutos = {}
        for x in r["exercicios"]:
            ex = x["exercicio"]
            assert not b.sem_cobertura(ex)
            pt = b.ponto(ex, x["data_final"], ent)
            brutos[ex] = pt
            assert x["situacao"]["codigo"] == pt["situacao"], (ent, ex)
            valores = {k: v["valor_c"] for k, v in x["valores"].items()}
            assert valores == (pt["valores"] or dict.fromkeys(valores)), (ent, ex)
        for f in r["fechamento_abertura"]:
            a, bb = brutos[f["de"]], brutos[f["para"]]
            if f["motivo_indisponivel"]:
                assert f["diferenca_c"] is None and not (a["tem_valor"] and bb["tem_valor"]), (ent, f["de"])
                continue
            af = b.a_mais_f(f["para"], bb["coletas"])
            assert (f["s1_de_c"], f["a_mais_f_para_c"]) == (a["valores"]["saldo_total"], af), (ent, f["de"])
            assert f["diferenca_c"] == rb.diferenca(a["valores"]["saldo_total"], af), (ent, f["de"])


def test_fechamento_igual_a_coerencia_ja_homologada(real):
    """Para os escopos com RREO, a serie usa a mesma definicao da coerencia entre publicacoes (04.5)."""
    p = real["painel"]
    coe = {(x["escopo"], x["de"]): x for x in p.coerencia_entre_publicacoes()["comparacoes"] if x["api_s1_de_c"] is not None
           and x["data_final_para"] == (f"{x['para']}-12-31" if x["para"] < 2026 else "2026-08-31")}
    for escopo, ent in (("consolidado", None), ("entidade", 1)):
        fa = {f["de"]: f for f in p.serie_entre_exercicios(ent)["fechamento_abertura"]}
        for de in range(2020, 2026):
            x = coe[(escopo, de)]
            assert (fa[de]["s1_de_c"], fa[de]["a_mais_f_para_c"]) == (x["api_s1_de_c"], x["api_a_mais_f_para_c"]), (escopo, de)
            assert fa[de]["diferenca_c"] == 0


def test_R7_nas_transicoes_reais(real):
    fa = {f["de"]: f for f in real["painel"].serie_entre_exercicios()["fechamento_abertura"]}
    assert fa[2018]["entidades_que_entram"] == [15] and fa[2022]["entidades_que_saem"] == [10]
    assert fa[2025]["entidades_que_saem"] == [3, 6, 9, 11]
    assert all(f["motivo_indisponivel"] is None and f["diferenca_c"] == 0 for f in fa.values())


def test_continuidade_igual_a_tabela_da_derivacao(real, entidades_reais):
    linhas = [(json.loads(e), v, f) for e, v, f in real["con"].execute(
        "SELECT escopo_json, verificados, falhas FROM verificacao WHERE derivacao_id=? AND descricao=?",
        (real["did"], CONTINUIDADE))]
    for ent in entidades_reais:
        for f in real["painel"].serie_entre_exercicios(ent)["fechamento_abertura"]:
            c = f["continuidade"]
            esperado = [(e["entidade"], v, fa) for e, v, fa in linhas if e["de"] == f["de"]
                        and (ent is None or e["entidade"] == ent)]
            if ent is None:
                esperado = [x for x in esperado if x[0] in {y["entidade"] for y in c["linhas"]}]
            assert sorted((x["entidade"], x["verificados"], x["falhas"]) for x in c["linhas"]) == sorted(esperado)
            assert c["falhas"] == 0


def test_tela_igual_ao_painel_com_retrato_em_todo_ponto(real, app_real):
    for ent in (None, 15):
        r = real["painel"].serie_entre_exercicios(ent)
        corpo = ok(app_real, "/historico", entidade=ent)
        v = dados(corpo)
        for x in r["exercicios"]:
            ex = x["exercicio"]
            if x["tem_valor"]:
                texto = re.search(rf'id="ret-{ex}">(.*?)</span>', corpo).group(1)
                assert texto == x["retrato"]["texto"]
                assert texto.startswith(f"Estado atual da base para o exercício de {ex}, corte ")
                for k in INDICADORES_ENTRE_EXERCICIOS:
                    assert v[f"hist-{ex}-{k}"] == x["valores"][k]["valor_c"]
            else:
                assert f'id="hist-lacuna-{ex}"' in corpo and not any(k.startswith(f"hist-{ex}-") for k in v)
        for f in r["fechamento_abertura"]:
            if f["motivo_indisponivel"]:
                assert f'id="fa-lacuna-{f["de"]}"' in corpo
            else:
                assert (v[f"fa-{f['de']}-s1"], v[f"fa-{f['de']}-af"], v[f"fa-{f['de']}-dif"]) == (
                    f["s1_de_c"], f["a_mais_f_para_c"], f["diferenca_c"])
        assert not PROIBIDO.search(re.sub(r"<[^>]+>", " ", corpo))
        assert 'id="aviso-pares"' in corpo and 'id="aviso-historico"' in corpo


def test_desempenho_da_serie_entre_exercicios(app_real):
    for ent in (None, 1, 15):
        t = time.perf_counter()
        status, _, _ = chamar(app_real, "/historico", entidade=ent)
        assert status == "200 OK" and time.perf_counter() - t < 3, ent
