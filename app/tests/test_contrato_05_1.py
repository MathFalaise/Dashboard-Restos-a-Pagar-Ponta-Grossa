"""Testes da Subetapa 05.1: contrato analitico da Etapa 05 (etapa05/CONTRATO_ANALITICO.md) e a ferramenta de
recalculo independente (recalculo_bruto.py).

A 05.1 nao muda codigo de producao. Estes testes fixam:
  * a ferramenta reproduz Painel.indicadores, ao centavo, em todo ponto com valor dos 22 cortes reais (Municipio e
    cada entidade), escolhendo snapshots e situacoes de forma independente;
  * cada situacao do contrato de disponibilidade (secao 2) e representavel, e nenhuma vira zero;
  * o universo de pontos de uma serie (R1), as diferencas (secao 2.6), as contribuicoes (M-09 a M-11) e o fechamento
    (secao 4.2);
  * o documento do contrato esta completo (14 respostas por metrica; catalogo das verificacoes reais).
SINTETICO = banco temporario com registros inventados (fixture `mundo`).
"""
import ast
import json
import re
from pathlib import Path

import pytest
from conftest import COLETOR_SINTETICO, RAIZ_PROJETO, registro_sintetico as _reg

import recalculo_bruto as rb
from rp.coletor import EP_RP
from rp.snapshots import gravar_snapshot

CONTRATO = RAIZ_PROJETO / "etapa05" / "CONTRATO_ANALITICO.md"
T0, T1 = "2026-09-29T20:00:00-03:00", "2026-09-30T10:00:00-03:00"
SEM_VALOR = ("inexistente", "sem_coleta", "nao_processado", "incompleto", "municipio_indisponivel",
             "exercicio_sem_cobertura")


def _incompleta(mundo, entidade, exercicio, data_final, quando):
    p = {"entidade": entidade, "exercicio": exercicio, "dataInicial": f"{exercicio}-01-01", "dataFinal": data_final,
         "size": 2000}
    corpo = {"content": [_reg(1, entidade=entidade)], "last": False, "totalElements": 5}
    gravar_snapshot(mundo.con, mundo.armazem, tipo="rp_listagem", endpoint=EP_RP, parametros=p, coletada_em=quando,
                    origem_carimbo="relogio_coletor", status="incompleta", coletor=COLETOR_SINTETICO,
                    respostas=[{"url": "sintetico", "http_status": 200, "corpo": json.dumps(corpo).encode()}])


def _valores_nulos(ind):
    return all(v["valor_c"] is None for v in ind["valores"].values())


# ================================================================== disponibilidade (SINTETICO)
@pytest.fixture
def situacoes(mundo):
    """Corte 2025-12-31 com uma entidade em cada situacao, e o exercicio 2023 sem nenhuma coleta:
    1 com dados (2023 no catalogo, sem coleta); 3 fora do catalogo de 2025; 5 so coleta incompleta; 8 nunca coletada;
    9 coletada depois do processamento; 15 existente com zero registros."""
    mundo.catalogos({1: [2023, 2025], 3: [2024], 5: [2025], 8: [2025], 9: [2025], 15: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1, aproc=10.0), _reg(2, aproc=5.5, pagoAProc=1.25)], T0)
    mundo.listagem(3, 2025, "2025-12-31", [_reg(7, entidade=3)], T0)
    mundo.listagem(15, 2025, "2025-12-31", [], T0)
    _incompleta(mundo, 5, 2025, "2025-12-31", T0)
    mundo.processar()
    mundo.listagem(9, 2025, "2025-12-31", [_reg(2, entidade=9)], T1)
    mundo.con.commit()
    return mundo


ESPERADO = {1: "com_dados", 3: "inexistente", 5: "incompleto", 8: "sem_coleta", 9: "nao_processado", 15: "sem_rp"}


def test_SINTETICO_cada_situacao_da_entidade_igual_no_painel_e_na_regra_independente(situacoes):
    b = rb.Bruto(situacoes.con, situacoes.armazem)
    assert {e: b.situacao(e, 2025, "2025-12-31") for e in ESPERADO} == ESPERADO
    with situacoes.painel() as p:
        linhas = {l["entidade"]: l for l in p.entidades_do_corte(2025, "2025-12-31")["linhas"]}
        assert {e: l["situacao_do_dado"]["codigo"] for e, l in linhas.items()} == ESPERADO
        for e, codigo in ESPERADO.items():
            ind = p.indicadores(2025, "2025-12-31", e)
            pt = b.ponto(2025, "2025-12-31", e)
            assert pt["situacao"] == codigo and pt["tem_valor"] == (codigo in rb.TEM_VALOR)
            if codigo in SEM_VALOR:      # sem valor: nunca R$ 0,00
                assert not ind["disponivel"] and _valores_nulos(ind) and pt["valores"] is None, e
            else:
                assert ind["disponivel"] and {k: v["valor_c"] for k, v in ind["valores"].items()} == pt["valores"], e
    assert b.ponto(2025, "2025-12-31", 15)["valores"]["inscricao_total"] == 0          # zero verdadeiro


def test_SINTETICO_municipio_indisponivel_nunca_vira_zero(situacoes):
    b = rb.Bruto(situacoes.con, situacoes.armazem)
    pt = b.ponto(2025, "2025-12-31")
    assert pt["situacao"] == "municipio_indisponivel" and pt["valores"] is None
    assert {e: s for e, s in pt["entidades"].items() if s in rb.SEM_SNAPSHOT} == {5: "incompleto", 8: "sem_coleta",
                                                                                 9: "nao_processado"}
    with situacoes.painel() as p:
        ind = p.indicadores(2025, "2025-12-31")
        assert not ind["disponivel"] and _valores_nulos(ind)
        for trecho in ("corte não coletado", "ainda não processado", "incompleta ou com falha"):
            assert trecho in ind["motivo_indisponivel"]


def test_SINTETICO_exercicio_sem_cobertura(situacoes):
    """Contrato secao 2.1: no painel atual o exercicio sem coleta aparece como indisponivel generico (o codigo proprio
    e da 05.3); o que a 05.1 fixa e que ele e reconhecivel e nunca vira zero."""
    b = rb.Bruto(situacoes.con, situacoes.armazem)
    assert b.ponto(2023, "2023-12-31")["situacao"] == "exercicio_sem_cobertura"
    assert b.situacao(1, 2023, "2023-12-31") == "exercicio_sem_cobertura"        # 2023 esta no catalogo da entidade 1
    assert b.situacao(15, 2023, "2023-12-31") == "inexistente"                   # precedencia: inexistente primeiro
    assert b.cortes_do_exercicio(2023) == []
    with situacoes.painel() as p:
        for ent in (None, 1):
            ind = p.indicadores(2023, "2023-12-31", ent)
            assert not ind["disponivel"] and _valores_nulos(ind)
        assert all(c["exercicio"] != 2023 for c in p.cortes()["cortes"])


def test_SINTETICO_municipio_com_zero_verdadeiro(mundo):
    mundo.catalogos({1: [2025], 15: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", [], T0)
    mundo.listagem(15, 2025, "2025-12-31", [], T0)
    mundo.processar()
    pt = rb.Bruto(mundo.con, mundo.armazem).ponto(2025, "2025-12-31")
    assert pt["situacao"] == "sem_rp" and pt["valores"]["saldo_total"] == 0 and pt["valores"]["registros"] == 0
    with mundo.painel() as p:
        ind = p.indicadores(2025, "2025-12-31")
        assert ind["disponivel"] and ind["valores"]["saldo_total"]["valor_c"] == 0


def test_SINTETICO_serie_lista_todos_os_cortes_e_nao_pula_lacuna(mundo):
    """Contrato secoes 2.4 e 2.6: a serie de uma entidade tem todos os cortes do exercicio; corte sem a entidade e
    lacuna com situacao; diferenca contra lacuna e None."""
    mundo.catalogos({1: [2025], 15: [2025]})
    for df in ("2025-02-28", "2025-04-30", "2025-06-30"):
        mundo.listagem(1, 2025, df, [_reg(1, aproc=100.0, pagoAProc={"2025-02-28": 10.0, "2025-04-30": 30.0,
                                                                    "2025-06-30": 35.0}[df])], T0)
    mundo.listagem(15, 2025, "2025-02-28", [_reg(1, entidade=15, aproc=50.0)], T0)
    mundo.listagem(15, 2025, "2025-06-30", [_reg(1, entidade=15, aproc=50.0, pagoAProc=20.0)], T0)
    mundo.processar()
    b = rb.Bruto(mundo.con, mundo.armazem)
    serie = b.serie(2025, 15)
    assert [x["data_final"] for x in serie] == ["2025-02-28", "2025-04-30", "2025-06-30"]
    assert [x["situacao"] for x in serie] == ["com_dados", "sem_coleta", "com_dados"]
    assert serie[1]["valores"] is None and serie[1]["diferenca_saldo"] is None and serie[2]["diferenca_saldo"] is None
    mun = b.serie(2025)
    assert [x["situacao"] for x in mun] == ["com_dados", "municipio_indisponivel", "com_dados"]
    um = b.serie(2025, 1)
    assert [x["diferenca_saldo"] for x in um] == [None, -2000, -500]
    with mundo.painel() as p:      # R1 corrigido na 05.2: o painel lista todos os cortes, com a situacao
        ev = p.evolucao(2025, 15)["serie"]
        assert [x["data_final"] for x in ev] == ["2025-02-28", "2025-04-30", "2025-06-30"]
        assert [x["situacao"]["codigo"] for x in ev] == [x["situacao"] for x in serie]
        assert [l["situacao_do_dado"]["codigo"] for l in p.entidades_do_corte(2025, "2025-04-30")["linhas"]
                if l["entidade"] == 15] == ["sem_coleta"]


# ================================================================== contribuicoes e fechamento (SINTETICO)
def _par_de_cortes(mundo, repetir=False):
    mundo.catalogos({1: [2025]})
    ant = [_reg(1, aproc=100.0, pagoAProc=10.0), _reg(2, aproc=50.0), _reg(3, aproc=40.0, pagoAProc=5.0),
           _reg(5, aproc=30.0), _reg(6, aproc=30.0)]
    post = [_reg(1, aproc=100.0, pagoAProc=60.0), _reg(2, aproc=50.0), _reg(4, aproc=70.0, pagoAProc=7.0),
            _reg(5, aproc=30.0, pagoAProc=12.0), _reg(6, aproc=30.0, pagoAProc=12.0)]
    if repetir:
        post.append(_reg(2, aproc=1.0))
    mundo.listagem(1, 2025, "2025-06-30", ant, T0)
    mundo.listagem(1, 2025, "2025-12-31", post, T0)
    mundo.processar()
    return rb.Bruto(mundo.con, mundo.armazem)


def test_SINTETICO_contribuicoes_por_situacao_da_chave_e_fechamento(mundo):
    b = _par_de_cortes(mundo)
    r = b.contribuicoes(2025, "2025-06-30", "2025-12-31", 1, "s1", top=1)
    por_chave = {x["chave"][2]: (x["classe"], x["contribuicao_c"]) for x in r["linhas"]}
    assert por_chave == {1: ("nos_dois", -5000), 2: ("nos_dois", 0), 3: ("so_anterior", -3500),
                         4: ("so_posterior", 6300), 5: ("nos_dois", -1200), 6: ("nos_dois", -1200)}
    assert r["variacao_c"] == (10000 - 6000 + 5000 + 6300 + 1800 + 1800) - (9000 + 5000 + 3500 + 3000 + 3000)
    for f in ("fechamento_grupos", "fechamento_classes", "fechamento_linhas"):
        assert r[f]["fecha"] and r[f]["diferenca_c"] == 0, f
    assert [x["chave"][2] for x in r["linhas"]] == [4, 2, 5, 6, 3, 1]    # decrescente; empate 5/6 pela chave
    assert dict(r["grupos"]) == {"top_aumentos": 6300, "outros_aumentos": 0, "top_reducoes": -5000,
                                 "outras_reducoes": -5900, "sem_variacao": 0}
    assert r["sem_variacao"] == 1
    assert sum(x["contribuicao_c"] for x in r["linhas"]) == r["variacao_c"] != sum(abs(x["contribuicao_c"])
                                                                                    for x in r["linhas"])
    pag = b.contribuicoes(2025, "2025-06-30", "2025-12-31", 1, "pagamentos")
    assert pag["fechamento_classes"]["fecha"] and dict(pag["classes"]) == {"nos_dois": 5000 + 1200 + 1200,
                                                                          "so_posterior": 700, "so_anterior": -500}


def test_SINTETICO_chave_duplicada_bloqueia_o_par(mundo):
    # revisao critica (05/10/2026), item 1: o retrato com a chave repetida nunca e o vigente - o oraculo decide
    # lendo o bruto. Sem retrato valido anterior o lado fica 'ambiguo', sem valor, e o par continua bloqueado sem
    # escolher copia (antes o retrato era vigente e o bloqueio vinha de `chaves_repetidas`)
    b = _par_de_cortes(mundo, repetir=True)
    r = b.contribuicoes(2025, "2025-06-30", "2025-12-31", 1, "s1")
    assert not r["disponivel"] and "ambiguo" in r["motivo"] and "linhas" not in r
    assert b.situacao(1, 2025, "2025-12-31") == "ambiguo" and b.repetida(b._listagens(1, 2025, "2025-12-31")[-1][0])


def test_SINTETICO_par_com_lado_sem_valor_e_indisponivel(situacoes):
    b = rb.Bruto(situacoes.con, situacoes.armazem)
    situacoes.listagem(1, 2025, "2025-06-30", [_reg(1, aproc=10.0)], T0)    # nao processado
    r = b.contribuicoes(2025, "2025-06-30", "2025-12-31", 1, "s1")
    assert not r["disponivel"] and "sem valor" in r["motivo"]


def test_fechamento_aprova_so_com_diferenca_zero_e_nunca_mascara():
    ok = rb.fechamento(100, [("a", 60), ("b", 40)])
    assert ok["fecha"] and ok["diferenca_c"] == 0
    for comps, dif in (([("a", 60), ("b", 39)], -1), ([("a", 150), ("b", -49)], 1), ([("a", 100), ("b", 1)], 1)):
        r = rb.fechamento(100, comps)
        assert not r["fecha"] and r["diferenca_c"] == dif          # nem 1 centavo passa; sinal preservado
    assert not rb.fechamento(-100, [("a", 100)])["fecha"]          # sem valor absoluto
    for ruim in (100.0, True, "100"):
        with pytest.raises(TypeError):
            rb.fechamento(100, [("a", ruim)])
    assert rb.diferenca(None, 5) is None and rb.diferenca(5, None) is None and rb.diferenca(7, 5) == -2
    with pytest.raises(TypeError):
        rb.diferenca(1.5, 2)


# ================================================================== independencia da ferramenta
def test_ferramenta_de_recalculo_nao_reaproveita_a_producao_nem_reimplementa_a_derivacao():
    fonte = (Path(__file__).with_name("recalculo_bruto.py")).read_text(encoding="utf-8")
    modulos = {n.module if isinstance(n, ast.ImportFrom) else a.name
               for n in ast.walk(ast.parse(fonte)) if isinstance(n, (ast.Import, ast.ImportFrom))
               for a in (n.names if isinstance(n, ast.Import) else [n])}
    assert not [m for m in modulos if m and m.split(".")[0] == "rp"], modulos
    for codigo in ("LIQ-NEG", "COPIA-24", "SALDO-SEM-CONTINUIDADE", "DESCONTINUIDADE", "PAR-24", "verificacao",
                   "anomalia ("):
        assert codigo not in fonte, codigo        # anomalias e verificacoes: regime "derivacao", nao recalculadas


# ================================================================== documento do contrato
def _secoes(texto, prefixo):
    partes = re.split(rf"^### ({prefixo}-\d+)", texto, flags=re.M)
    return dict(zip(partes[1::2], partes[2::2]))


def test_contrato_tem_as_14_respostas_de_cada_metrica():
    metricas = _secoes(CONTRATO.read_text(encoding="utf-8"), "M")
    assert sorted(metricas) == [f"M-{i:02d}" for i in range(1, 13)]
    for mid, corpo in metricas.items():
        corpo = corpo.split("\n## ")[0]
        respostas = dict(re.findall(r"^\| (\d+) \| (.+?) \|\s*$", corpo, flags=re.M))
        assert sorted(map(int, respostas)) == list(range(1, 15)), mid
        assert all(v.strip() for v in respostas.values()), mid


def test_contrato_cobre_taxonomia_regimes_e_grafico():
    texto = CONTRATO.read_text(encoding="utf-8")
    for codigo in rb.TEM_VALOR + SEM_VALOR:
        assert f"`{codigo}`" in texto, codigo
    for trecho in ("SEM DIFERENÇA", "EXPLICADA", "PARCIALMENTE EXPLICADA", "HIPÓTESE", "NÃO DETERMINADA",
                   "significado não catalogado", "SVG gerado no servidor", "sem JavaScript", "375 px",
                   "Nenhum gráfico foi implementado na 05.1", "R1", "R4"):
        assert trecho in texto, trecho


# ================================================================== armazem real
@pytest.fixture(scope="module")
def bruto_real(real):
    return rb.Bruto(real["con"], real["armazem"])


def test_recalculo_reproduz_o_painel_em_todo_ponto_dos_22_cortes(real, bruto_real):
    """Criterio de aceitacao da 05.1: bruto = painel ao centavo em todo ponto com valor; ponto sem valor tem valores
    nulos nos dois; snapshots e situacao escolhidos de forma independente coincidem com os do painel."""
    p, b = real["painel"], bruto_real
    cortes = p.cortes()["cortes"]
    assert len(cortes) == 22
    entidades = [e["entidade"] for e in p.entidades()["entidades"]]
    com_valor = sem_valor = 0
    for c in cortes:
        ex, df = c["exercicio"], c["data_final"]
        sits = {l["entidade"]: l["situacao_do_dado"]["codigo"] for l in p.entidades_do_corte(ex, df)["linhas"]}
        for ent in [None] + entidades:
            ind, pt = p.indicadores(ex, df, ent), b.ponto(ex, df, ent)
            assert ind["disponivel"] == pt["tem_valor"], (ex, df, ent)
            if ent is not None:
                assert sits[ent] == pt["situacao"], (ex, df, ent)
            if pt["tem_valor"]:
                com_valor += 1
                assert {k: v["valor_c"] for k, v in ind["valores"].items()} == pt["valores"], (ex, df, ent)
                assert sorted(ind["retrato"]["snapshots"]) == sorted(b.uid(cid) for cid in pt["coletas"])
                assert ind["proveniencia"]["derivacao"]["id"] == p.contexto()["derivacao"]["id"]
            else:
                sem_valor += 1
                assert _valores_nulos(ind), (ex, df, ent)
    assert com_valor > 0 and sem_valor > 0
    print(f"pontos com valor: {com_valor}; sem valor: {sem_valor}")


def test_universo_da_serie_e_R1_no_dado_real(real, bruto_real):
    p, b = real["painel"], bruto_real
    for ex in range(2016, 2027):
        assert b.cortes_do_exercicio(ex) == [c["data_final"] for c in p.cortes()["cortes"] if c["exercicio"] == ex]
    universo = b.cortes_do_exercicio(2026)
    assert universo == ["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30", "2026-06-30", "2026-08-31", "2026-12-31"]
    for ent in (5, 15):
        serie = b.serie(2026, ent)
        assert [x["situacao"] for x in serie] == ["sem_coleta", "com_dados", "sem_coleta", "com_dados", "com_dados",
                                                  "com_dados", "sem_coleta"]
        assert all(x["valores"] is None for x in serie if x["situacao"] == "sem_coleta")
        ev = p.evolucao(2026, ent)["serie"]                 # R1 corrigido na 05.2: os 7 cortes, com situacao
        assert [x["situacao"]["codigo"] for x in ev] == [x["situacao"] for x in serie]
    assert [x["situacao"] for x in b.serie(2026)] == ["municipio_indisponivel", "com_dados", "municipio_indisponivel",
                                                     "com_dados", "com_dados", "com_dados", "municipio_indisponivel"]


def test_R4_corte_posterior_a_coleta_tem_valor_e_rotulo(real, bruto_real):
    ind = real["painel"].indicadores(2026, "2026-12-31", 1)
    assert ind["disponivel"] and ind["retrato"]["corte_posterior_a_coleta"]
    assert bruto_real.ponto(2026, "2026-12-31", 1)["valores"]["saldo_total"] == ind["valores"]["saldo_total"]["valor_c"]


def test_diferencas_adjacentes_no_dado_real(real, bruto_real):
    p, b = real["painel"], bruto_real
    serie = b.serie(2025)
    saldos = [p.indicadores(2025, x["data_final"])["valores"]["saldo_total"]["valor_c"] for x in serie]
    assert [x["diferenca_saldo"] for x in serie] == [None] + [d - a for a, d in zip(saldos, saldos[1:])]
    assert sum(x["diferenca_saldo"] for x in serie[1:]) == saldos[-1] - saldos[0]       # sem lacuna: identidade
    s26 = {x["data_final"]: x["diferenca_saldo"] for x in b.serie(2026)}
    assert s26["2026-03-31"] is None and s26["2026-04-30"] is None and s26["2026-02-28"] is None   # nao pula lacuna


@pytest.mark.parametrize("ent, ex, pares", [
    (None, 2025, [("2025-02-28", "2025-04-30"), ("2025-10-31", "2025-12-31")]),
    (1, 2026, [("2026-01-31", "2026-02-28"), ("2026-08-31", "2026-12-31")]),
    (None, 2026, [("2026-02-28", "2026-04-30")]),             # par que salta a lacuna de 31/03 (escolha explicita)
])
def test_contribuicoes_fecham_no_dado_real(real, bruto_real, ent, ex, pares):
    p = real["painel"]
    for ant, post in pares:
        for metrica, indicador in (("s1", "saldo_total"), ("pagamentos", "pagamentos")):
            r = bruto_real.contribuicoes(ex, ant, post, ent, metrica)
            assert r["disponivel"], r.get("motivo")
            for f in ("fechamento_grupos", "fechamento_classes", "fechamento_linhas"):
                assert r[f]["fecha"], (ent, ant, post, metrica, f)
            esperado = (p.indicadores(ex, post, ent)["valores"][indicador]["valor_c"]
                        - p.indicadores(ex, ant, ent)["valores"][indicador]["valor_c"])
            assert r["variacao_c"] == esperado, (ent, ant, post, metrica)


def test_catalogo_de_verificacoes_cobre_as_descricoes_reais(real):
    texto = CONTRATO.read_text(encoding="utf-8")
    descricoes = {d for (d,) in real["con"].execute("SELECT DISTINCT descricao FROM verificacao WHERE derivacao_id=?",
                                                    (real["did"],))}
    assert len(descricoes) == 4
    for d in descricoes:
        assert f"`{d}`" in texto, d
