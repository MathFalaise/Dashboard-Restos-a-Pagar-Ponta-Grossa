"""Regression tests of the corrective audit of 13/10/2026 (phase P1). SINTETICO = temporary database with invented
records (fixture `mundo`); no real data, no network.

* ESCOPO-MUN v2: entity 7 in the Municipality period by period, following the scope proven in the official statement
  (docs/audits/escopo/ESCOPO_ENTIDADE_7.md); outside 'comprovado' the Municipality carries a reservation.
* CONS-PAR v4 in the eight scenarios of item 5.3: the rule is not changed; what is tested is that a pair is only
  consolidated when it should be and that every uncertain case is flagged ("Município com ressalva"), never hidden.
* Methodology in force on a date (item 8): governance decisions up to the date, refused before the first one.
"""
import pytest
from conftest import chamar, registro_sintetico as _reg

from rp import derivar, governanca
from rp.painel.consulta import ErroDoPainel

T0 = "2026-09-29T20:00:00-03:00"
T1 = "2026-10-05T20:00:00-03:00"
TESTE = "tests/test_auditoria_20261013.py::"


def _promover(con, codigo, versao, teste, quando=None):
    governanca.registrar_decisao(con, codigo, versao, "operacional", "FORTE EVIDÊNCIA", True, "promocao de teste",
                                 "docs/audits/escopo/ESCOPO_ENTIDADE_7.md", "teste", decidido_em=quando,
                                 teste_regressao=TESTE + teste, ressalva="teste sintetico")


def _total(p, ex, df, em=None):
    r = p.indicadores(ex, df, em=em)
    return r["valores"]["inscricao_total"]["valor_c"], r


# ================================================================== ESCOPO-MUN v2
# cut-offs and what the recorded period map says about them (regras.PARAMETROS[("ESCOPO-MUN", 2)])
CORTES_V2 = {
    "2018-04-30": ("exclui", None),                 # 2nd bimester 2018: SICONFI proves the exclusion
    "2019-10-31": ("inclui", "inconclusivo"),       # 5th bimester 2019: nothing proves it; v1 kept, with reservation
    "2020-02-29": ("inclui", None),                 # 1st bimester 2020: SICONFI and the portal PDF include it
    "2020-06-30": ("exclui", "contraditorio"),      # 3rd bimester 2020: PDF includes, SICONFI excludes
    "2027-02-28": ("exclui", "sem_demonstrativo"),  # outside the map: no statement checked yet
}


def _mundo_entidade_7(mundo):
    anos = sorted({int(df[:4]) for df in CORTES_V2})
    mundo.catalogos({1: anos})
    for df in CORTES_V2:
        ano = int(df[:4])
        mundo.listagem(1, ano, df, [_reg(1, ano=ano - 1, aproc=100.0)], T0)
        mundo.listagem(7, ano, df, [_reg(5, ano=ano - 1, entidade=7, aproc=40.0)], T0)
    return mundo.processar()[1]


def test_escopo_mun_v2_entra_no_catalogo_como_experimental(mundo):
    mundo.catalogos({1: [2026]})
    mundo.processar()
    g = governanca.situacao_atual(mundo.con)[("ESCOPO-MUN", 2)]
    assert g["situacao"] == "experimental" and not g["compoe_indicador_publicado"]


def test_escopo_mun_v2_segue_o_demonstrativo_de_cada_periodo(mundo):
    _mundo_entidade_7(mundo)
    _promover(mundo.con, "ESCOPO-MUN", 1, "test_escopo_mun_v2_segue_o_demonstrativo_de_cada_periodo")
    with mundo.painel() as p:      # v1 only: entity 7 in every year up to 2020
        assert _total(p, 2018, "2018-04-30")[0] == 14000
        assert _total(p, 2020, "2020-06-30")[0] == 14000
    _promover(mundo.con, "ESCOPO-MUN", 2, "test_escopo_mun_v2_segue_o_demonstrativo_de_cada_periodo")
    with mundo.painel() as p:      # v2 operational: it prevails over v1, period by period
        for df, (tratamento, situacao) in CORTES_V2.items():
            total, r = _total(p, int(df[:4]), df)
            assert total == (14000 if tratamento == "inclui" else 10000), df
            ressalvas = [a for a in r["avisos"] if a.startswith("Município com ressalva (ESCOPO-MUN v2")]
            assert bool(ressalvas) == (situacao is not None) == r["com_ressalva"], df
            if situacao == "contraditorio":
                assert "Siconfi" in ressalvas[0] and "contraditórios" in ressalvas[0]
            (e7,) = [e for e in r["entidades"] if e["entidade"] == 7]
            assert e7["entra_no_total"] == (tratamento == "inclui"), df
            assert "ESCOPO-MUN v2" in r["escopo"]
            assert {"codigo": "ESCOPO-MUN", "versao": 2} == {k: r["regras_de_escopo"][0][k] for k in ("codigo", "versao")}
        # the entity's own view never changes
        assert p.indicadores(2018, "2018-04-30", entidade=7)["valores"]["inscricao_total"]["valor_c"] == 4000


def test_escopo_mun_v2_contraditorio_tem_explicacao_na_conferencia_do_saldo():
    from rp.painel import explicacoes
    achadas, situacao = explicacoes.explicar(2020, "2020-06-30", "consolidado", "L", "S1 v1",
                                             frozenset({"ESCOPO-MUN v2"}))
    assert situacao == "explicada" and "contraditórios" in achadas[0]["texto"]
    sem_v2 = explicacoes.explicar(2020, "2020-06-30", "consolidado", "L", "S1 v1", frozenset())[0]
    assert not any("ESCOPO-MUN v2" in e["texto"] for e in sem_v2)      # only while v2 is in the indicator


def test_escopo_mun_v2_parametros_transcrevem_a_evidencia():
    import json
    from conftest import RAIZ_PROJETO
    from rp import regras
    ev = json.loads((RAIZ_PROJETO / "docs/audits/escopo/ESCOPO_ENTIDADE_7.json").read_text(encoding="utf-8"))
    norm = {"comprovado pelo RREO do portal": "comprovado_rreo_portal"}
    esperado = {f"{x['exercicio']}-{x['bimestre']}": [x["tratamento"], norm.get(x["situacao"], x["situacao"])]
                for x in ev["periodos"]}
    assert regras.PARAMETROS[("ESCOPO-MUN", 2)]["periodos"] == esperado


# ================================================================== CONS-PAR v4: the eight scenarios of item 5.3
CORTE = (2026, "2026-02-28")


def _pares(mundo, copia=None, original=None, sem_original=False, original_duplicado=False, cnpj="11.222.333/0001-44",
           quando=T0, catalogos=True):
    """Entity 1: own record 10 (100) and the copy 2400005 (30). Entity 15: the original 5 (30) and own record 6 (50)."""
    if catalogos:
        mundo.catalogos({1: [2026], 15: [2026]})
    mundo.listagem(1, 2026, CORTE[1], [_reg(10, ano=2025, aproc=100.0),
                                       _reg(2400005, ano=2025, **{"aproc": 30.0, "cnpj": cnpj, **(copia or {})})],
                   quando)
    lado_b = [_reg(6, ano=2025, entidade=15, aproc=50.0)]
    if not sem_original:
        b = _reg(5, ano=2025, entidade=15, **{"aproc": 30.0, "cnpj": cnpj, **(original or {})})
        lado_b += [b, b] if original_duplicado else [b]
    mundo.listagem(15, 2026, CORTE[1], lado_b, quando)


def _promover_pares(mundo, teste):
    for codigo, versao in (("COPIA-ORIGEM", 1), ("CONS-PAR", 4)):
        _promover(mundo.con, codigo, versao, teste)


def _ressalva_pares(r):
    return [a for a in r["avisos"] if a.startswith("Município com ressalva (CONS-PAR v4)")]


def _anomalias(con, did, codigo):
    return con.execute("SELECT COUNT(*) FROM anomalia WHERE derivacao_id=? AND tipo=?", (did, codigo)).fetchone()[0]


def test_par_cenario_1_inscricao_nos_dois_lados_execucao_so_na_copia(mundo):
    _pares(mundo, copia={"liquidado": 10.0, "pagoAProc": 10.0})
    mundo.processar()
    _promover_pares(mundo, "test_par_cenario_1_inscricao_nos_dois_lados_execucao_so_na_copia")
    with mundo.painel() as p:
        total, r = _total(p, *CORTE)
        assert total == 18000                                   # counted once
        assert r["valores"]["pagamentos"]["valor_c"] == 1000    # the copy's execution stays
        assert not _ressalva_pares(r) and not r["com_ressalva"]


@pytest.mark.parametrize("original", [
    {"pagoAProc": 5.0, "liquidado": 5.0},          # scenario 2: payment in the original
    {"canceladoAProc": 5.0},                       # scenario 3: cancellation in the original
    {"liquidado": 5.0},                            # scenario 4: liquidation in the original
    {"liquidado": -5.0},                           # scenario 4: reversal of a liquidation in the original
], ids=["pagamento", "cancelamento", "liquidacao", "estorno_de_liquidacao"])
def test_par_cenarios_2_a_4_execucao_no_original_nao_consolida_e_avisa(mundo, original):
    _pares(mundo, original=original)
    _, did = mundo.processar()
    assert mundo.con.execute("SELECT verificados, falhas FROM verificacao WHERE derivacao_id=? AND descricao=?",
                             (did, derivar.VERIF_CONS_PAR_V4)).fetchall() == [(1, 1)]
    _promover_pares(mundo, "test_par_cenarios_2_a_4_execucao_no_original_nao_consolida_e_avisa")
    with mundo.painel() as p:
        total, r = _total(p, *CORTE)
        assert total == 21000                                   # nothing is dropped: both sides stay ...
        (aviso,) = _ressalva_pares(r)                           # ... and the possible double counting is stated
        assert "1 par(es)" in aviso and "R$ 30,00" in aviso and r["com_ressalva"]


def test_par_cenario_5_execucao_nos_dois_lados(mundo):
    _pares(mundo, copia={"pagoAProc": 10.0, "liquidado": 10.0}, original={"pagoAProc": 5.0, "liquidado": 5.0})
    _, did = mundo.processar()
    assert _anomalias(mundo.con, did, "PAR-EXECUCAO-DOIS-LADOS") == 1
    _promover_pares(mundo, "test_par_cenario_5_execucao_nos_dois_lados")
    with mundo.painel() as p:
        total, r = _total(p, *CORTE)
        assert total == 21000 and len(_ressalva_pares(r)) == 1
        assert r["valores"]["pagamentos"]["valor_c"] == 1500    # the flows of both sides are kept


def test_par_cenario_6_alteracao_retrospectiva_no_mesmo_corte(mundo):
    _pares(mundo, quando=T0)                                    # first snapshot: original without execution
    _pares(mundo, original={"canceladoAProc": 30.0}, quando=T1, catalogos=False)   # later: cancelled, same cut-off
    mundo.processar()
    _promover_pares(mundo, "test_par_cenario_6_alteracao_retrospectiva_no_mesmo_corte")
    with mundo.painel() as p:
        antes, r_antes = _total(p, *CORTE, em="2026-10-01T00:00:00-03:00")
        depois, r_depois = _total(p, *CORTE)
        assert antes == 18000 and not _ressalva_pares(r_antes)          # as it was: consolidated
        assert depois == 21000 and len(_ressalva_pares(r_depois)) == 1  # now: the original has execution
        assert r_antes["retrato"]["snapshots"] != r_depois["retrato"]["snapshots"]


def test_par_cenario_7_par_ausente_nao_consolida_nada(mundo):
    _pares(mundo, sem_original=True)
    _, did = mundo.processar()
    assert _anomalias(mundo.con, did, "COPIA-SEM-PAR") == 1
    _promover_pares(mundo, "test_par_cenario_7_par_ausente_nao_consolida_nada")
    with mundo.painel() as p:
        total, r = _total(p, *CORTE)
        assert total == 18000 and not _ressalva_pares(r)        # the copy counts once; no double counting


def test_par_cenario_7_inscricao_divergente_nao_consolida_e_avisa(mundo):
    _pares(mundo, original={"aproc": 25.0})
    _, did = mundo.processar()
    assert _anomalias(mundo.con, did, "PAR-INSCRICAO-DIVERGENTE") == 1
    _promover_pares(mundo, "test_par_cenario_7_inscricao_divergente_nao_consolida_e_avisa")
    with mundo.painel() as p:
        total, r = _total(p, *CORTE)
        assert total == 20500 and len(_ressalva_pares(r)) == 1


def test_par_cenario_8_chave_repetida_deixa_o_municipio_indisponivel(mundo):
    _pares(mundo, original_duplicado=True)
    mundo.processar()
    _promover_pares(mundo, "test_par_cenario_8_chave_repetida_deixa_o_municipio_indisponivel")
    with mundo.painel() as p:
        r = p.indicadores(*CORTE)
        assert not r["disponivel"] and r["valores"]["inscricao_total"]["valor_c"] is None   # never a guessed total


def test_par_cenario_8_evidencia_incompleta_e_sinalizada(mundo):
    """CONS-PAR v4 compares the matching fields with IS: two null CNPJ are 'equal'. The rule is not changed (a semantic
    fix would be a new version); the consolidation is flagged as a reservation instead of passing silently."""
    _pares(mundo, cnpj=None)
    mundo.processar()
    _promover_pares(mundo, "test_par_cenario_8_evidencia_incompleta_e_sinalizada")
    with mundo.painel() as p:
        total, r = _total(p, *CORTE)
        assert total == 18000
        (aviso,) = _ressalva_pares(r)
        assert "campo de conferência nulo" in aviso and r["com_ressalva"]


# ================================================================== methodology in force on a date (item 8)
def test_metodologia_vigente_na_data_usa_so_as_decisoes_ate_ela(mundo):
    _mundo_entidade_7(mundo)
    _promover(mundo.con, "ESCOPO-MUN", 1, "test_metodologia_vigente_na_data_usa_so_as_decisoes_ate_ela",
              "2026-10-09T21:00:00-03:00")
    _promover(mundo.con, "ESCOPO-MUN", 2, "test_metodologia_vigente_na_data_usa_so_as_decisoes_ate_ela",
              "2026-10-13T12:00:00-03:00")
    with mundo.painel() as p:
        assert _total(p, 2018, "2018-04-30")[0] == 10000                       # today: v2
        p.definir_metodologia("vigente", "2026-10-10T00:00:00-03:00")
        total, r = _total(p, 2018, "2018-04-30", em="2026-10-10T00:00:00-03:00")
        assert total == 14000                                                    # on 10/10: only v1 was in force
        assert r["retrato"]["metodologia"]["modo"] == "vigente"
        assert r["retrato"]["metodologia"]["regras_de_escopo"] == ["ESCOPO-MUN v1"]
        with pytest.raises(ErroDoPainel, match="indisponível"):            # the catalog events start on 29/09:
            p.definir_metodologia("vigente", "2026-09-28T00:00:00-03:00")   # before any decision, refused
        with pytest.raises(ErroDoPainel, match="exige a data"):
            p.definir_metodologia("vigente")
        p.definir_metodologia("atual")
        r = p.indicadores(2018, "2018-04-30")
        assert r["retrato"]["metodologia"]["modo"] == "atual"
        assert r["retrato"]["metodologia"]["regras_de_escopo"] == ["ESCOPO-MUN v2"]


def test_metodologia_na_interface(mundo):
    from rp.interface import Aplicacao
    _mundo_entidade_7(mundo)
    mundo.con.commit()
    app = Aplicacao(mundo.cfg.banco)
    status, _, html = chamar(app, "/", exercicio=2018, data_final="2018-04-30", em="2026-09-01", metodologia="vigente")
    assert status.startswith("400") and "indisponível" in html     # before the first decision: nothing to reconstruct
    _promover(mundo.con, "ESCOPO-MUN", 1, "test_metodologia_na_interface", "2026-10-09T21:00:00-03:00")
    mundo.con.commit()
    status, _, html = chamar(app, "/", exercicio=2018, data_final="2018-04-30", em="2026-10-10", metodologia="vigente")
    assert status.startswith("200") and "metodologia vigente na data" in html
    status, _, html = chamar(app, "/", exercicio=2018, data_final="2018-04-30", metodologia="vigente")
    assert status.startswith("400") and "exige a data" in html
    status, _, _ = chamar(app, "/", exercicio=2018, metodologia="outra")
    assert status.startswith("400")


# ================================================================== official consolidated series (item 5.1)
def _leitura_siconfi(pasta, itens_por_periodo, extrato=None):
    import hashlib
    import json
    pasta.mkdir(parents=True)
    arquivos = {}
    for (ano, bim), itens in itens_por_periodo.items():
        corpo = json.dumps({"items": itens, "hasMore": False}).encode()
        (pasta / f"rreo_anexo07_{ano}_{bim}.json").write_bytes(corpo)
        arquivos[f"rreo_anexo07_{ano}_{bim}.json"] = {"sha256": hashlib.sha256(corpo).hexdigest()}
    for ano, itens in (extrato or {}).items():
        corpo = json.dumps({"items": itens}).encode()
        (pasta / f"extrato_entregas_{ano}.json").write_bytes(corpo)
        arquivos[f"extrato_entregas_{ano}.json"] = {"sha256": hashlib.sha256(corpo).hexdigest()}
    (pasta / "manifest.json").write_text(json.dumps({"arquivos": arquivos}), encoding="utf-8")


def _linha(conta, valores):
    rot = {"a": "Em Exercícios Anteriores (a)", "b": "Em 31 de dezembro de 2025 (b)", "c": "Pagos (c)",
           "d": "Cancelados (d)", "e": "Saldo e = (a+ b) - (c + d)", "f": "Em Exercícios Anteriores (f)",
           "g": "Em 31 de dezembro de 2025 (g)", "h": "Liquidados (h)", "i": "Pagos (i)", "j": "Cancelados (j)",
           "k": "Saldo k = (f + g) - (i + j)", "L": "Saldo Total L = (e + k)"}
    return [{"conta": conta, "coluna": rot[c], "valor": v} for c, v in valores.items()]


def test_SINTETICO_siconfi_ausente_nao_vira_zero_e_sha_divergente_e_recusado(tmp_path):
    from rp import siconfi
    exe = {"a": 0, "b": 0, "f": 0, "g": 130.0, "h": 10.0, "i": 10.0, "j": 0, "k": 120.0, "L": 120.0, "e": 0}
    pasta = tmp_path / "raw" / "coleta_x"
    _leitura_siconfi(pasta, {
        (2026, 1): _linha("RESTOS A PAGAR (EXCETO INTRA-ORÇAMENTÁRIOS) (I)", {**exe, "c": 0, "d": 0})
        + _linha("PODER EXECUTIVO", {**exe, "c": 0, "d": 0}),
        (2026, 2): _linha("PODER EXECUTIVO", {k: v for k, v in exe.items() if k != "i"}),    # identity breaks
    }, extrato={2026: [{"entregavel": "Relatório Resumido de Execução Orçamentária", "periodo": 1,
                         "periodicidade": "B", "status_relatorio": "RE", "data_status": "2026-03-30T10:00:00Z"}]})
    d1 = siconfi.declaracao(pasta, 2026, 1)
    assert d1["linhas"]["executivo"]["c"] == 0                      # omitted, identities close: zero
    assert d1["linhas"]["legislativo"] == {c: 0 for c in siconfi.COLUNAS}   # (I) == Executive: no Legislative RP
    assert siconfi.grupos(d1["linhas"]["executivo"]) == {"inscricao": 13000, "pagos": 1000, "cancelados": 0,
                                                         "liquidados": 1000, "saldo": 12000}
    d2 = siconfi.declaracao(pasta, 2026, 2)
    assert d2["linhas"]["executivo"]["c"] is None and d2["linhas"]["executivo"]["i"] is None   # absent, never zero
    assert siconfi.grupos(d2["linhas"]["executivo"])["pagos"] is None
    assert "legislativo" not in d2["linhas"]                         # no row (I): nothing inferred
    assert siconfi.situacao_da_entrega(pasta, 2026, 1)["situacao"] == "retificada"
    (pasta / "rreo_anexo07_2026_1.json").write_bytes(b'{"items": []}')
    with pytest.raises(siconfi.LeituraInvalida, match="SHA-256"):
        siconfi.declaracao(pasta, 2026, 1)


def test_SINTETICO_consolidado_oficial_separa_os_escopos(mundo, tmp_path):
    from rp.interface import Aplicacao
    from rp.painel.consulta import oficial
    mundo.catalogos({1: [2026]})
    mundo.listagem(1, 2026, "2026-02-28", [_reg(1, ano=2025, aproc=130.0, liquidado=10.0, pagoAProc=10.0)], T0)
    mundo.processar()
    mundo.con.commit()
    exe = {"a": 0, "b": 0, "c": 0, "d": 0, "e": 0, "f": 0, "g": 130.0, "h": 10.0, "i": 10.0, "j": 0, "k": 120.0,
           "L": 120.0}
    leg = {**{c: 0 for c in exe}, "b": 5.0, "e": 5.0, "L": 5.0}
    total = {c: exe[c] + leg[c] for c in exe}
    pasta = tmp_path / "raw"
    _leitura_siconfi(pasta / "coleta_1", {(2026, 1): _linha("RESTOS A PAGAR (EXCETO INTRA-ORÇAMENTÁRIOS) (I)", total)
                                          + _linha("PODER EXECUTIVO", exe) + _linha("PODER LEGISLATIVO", leg)})
    with mundo.painel() as p:
        r = p.consolidado_oficial(2026, pasta=pasta)
        (b1,) = [b for b in r["bimestres"] if b["bimestre"] == 1]
        assert b1["declaracao"]["linhas"]["I"]["saldo"] == 12500           # the official consolidated, as declared
        assert b1["declaracao"]["linhas"]["legislativo"]["saldo"] == 500   # the Câmara, never added to Elotech
        assert b1["executivo_elotech"]["valores"]["saldo"] == 12000
        assert b1["diferencas"] == {"inscricao": 0, "pagos": 0, "cancelados": 0, "liquidados": 0, "saldo": 0}
        assert "Poder Executivo, fonte Elotech" in b1["executivo_elotech"]["escopo"]
    status, _, html = chamar(Aplicacao(mundo.cfg.banco), "/oficial", exercicio=2026)
    assert status.startswith("200") and "Consolidado oficial" in html
    assert oficial.CORRESPONDENCIA["saldo"] == "saldo_total"


# ================================================================== freshness and retrospective changes (item 7)
def test_SINTETICO_alteracao_retrospectiva_por_empenho_com_alerta(mundo):
    from rp import atualizacao
    mundo.catalogos({1: [2026]})
    mundo.listagem(1, 2026, "2026-04-30", [_reg(1, ano=2025, aproc=100.0), _reg(2, ano=2025, aproc=50.0)],
                   "2026-09-29T20:00:00-03:00")
    mundo.listagem(1, 2026, "2026-04-30", [_reg(1, ano=2025, aproc=100.0, canceladoAProc=40.0),
                                           _reg(2, ano=2025, aproc=50.0)], "2026-10-06T20:00:00-03:00")
    mundo.processar()
    r = atualizacao.alteracoes_retrospectivas(mundo.con)
    (c,) = r["cortes"]
    assert c["retrospectiva"] and r["alertas"] == 1                       # 30/04 had ended before the first collection
    assert c["impacto_por_grupo"]["cancelamentos"]["diferenca"] == 4000 and c["saldo_s1"]["diferenca"] == -4000
    (e,) = c["empenhos"]
    assert e["chave"] == [1, 2025, 1] and e["diferencas_c"] == {"cancelado_aproc_c": 4000}
    assert e["data_de_registro_no_sistema"] == "não disponível na API"    # never assumed equal to the document date
    a = atualizacao.atualidade(mundo.con, "2026-10-13")
    assert a["dias_desde_a_ultima_listagem"] == 7 and a["alertas_retrospectivos"] == 1
    assert a["retratos_armazenados_nao_processados"] == 0
    mundo.listagem(1, 2026, "2026-04-30", [_reg(1, ano=2025, aproc=100.0)], "2026-10-12T20:00:00-03:00")
    assert atualizacao.atualidade(mundo.con, "2026-10-13")["retratos_armazenados_nao_processados"] == 1   # stored, not published


# ================================================================== governance (item 8)
def test_SINTETICO_cli_registra_a_versao_sucessora(mundo, tmp_path, capsys):
    import json
    from rp import cli
    mundo.catalogos({1: [2026]})
    mundo.processar()
    mundo.con.commit()
    cfg = tmp_path / "config.toml"
    from conftest import RAIZ_PROJETO
    texto = (RAIZ_PROJETO / "app" / "config.toml").read_text(encoding="utf-8")
    for velho, novo in (('"~/RestosAPagar_local"', mundo.cfg.dados_locais), ('"~/RestosAPagar_local/armazem"', mundo.cfg.snapshots),
                        ('"~/RestosAPagar_local/backups"', mundo.cfg.backups),
                        ('"~/RestosAPagar_local/etapas_anteriores"', tmp_path / "etapas")):
        texto = texto.replace(velho, json.dumps(str(novo)))
    assert "~/RestosAPagar_local" not in texto
    cfg.write_text(texto, encoding="utf-8")
    base = ["--config", str(cfg), "decidir-regra", "--codigo", "CONS-PAR", "--versao", "2", "--status", "HIPÓTESE",
            "--motivo", "teste", "--fonte", "docs/x.md"]
    assert cli.main(base + ["--situacao", "experimental", "--supersedida-por", "CONS-PAR:4"]) != 0   # only with supersedida
    assert cli.main(base + ["--situacao", "supersedida", "--supersedida-por", "CONS-PAR:4"]) == 0
    capsys.readouterr()
    import sqlite3
    con = sqlite3.connect(mundo.cfg.banco)
    sup = con.execute("SELECT r2.codigo, r2.versao FROM regra_situacao s JOIN regra r ON r.id = s.regra_id JOIN regra r2 "
                      "ON r2.id = s.supersedida_por WHERE r.codigo='CONS-PAR' AND r.versao=2").fetchall()
    con.close()
    assert sup == [("CONS-PAR", 4)]


# ================================================================== retention of runs (item 10)
def test_SINTETICO_manutencao_mantem_a_atual_e_cada_vigencia_e_recupera_do_backup(mundo):
    import sqlite3
    from rp import manutencao
    mundo.catalogos({1: [2026]})
    mundo.listagem(1, 2026, "2026-02-28", [_reg(1, ano=2025, aproc=100.0)], T0)
    mundo.processar()                                         # normalization 1, derivation 1
    mundo.processar("2026-09-29T23:59:59-03:00")              # normalization 2, derivation 2 ('as it was on')
    nid, did = mundo.processar()                              # normalization 3, derivation 3 (current)
    from rp import derivar
    did_vig = derivar.derivar(mundo.con, nid, "2026-09-29T23:59:59-03:00")
    mundo.con.commit()
    (mundo.cfg.dados_locais / manutencao.PRESERVAR).write_text("derivacao 1  # kept on purpose\n", encoding="utf-8")
    p = manutencao.plano(mundo.con, mundo.cfg)
    assert p["manter"] == {"normalizacoes": [1, nid], "derivacoes": [1, did, did_vig]}
    assert [d["id"] for d in p["apagar"]["derivacoes"]] == [2] and [n["id"] for n in p["apagar"]["normalizacoes"]] == [2]
    camada0 = mundo.con.execute("SELECT COUNT(*) FROM coleta").fetchone()[0]
    r = manutencao.executar(mundo.con, mundo.cfg, mundo.armazem, mundo.cfg.banco)
    assert r["executada"] and r["backup"]["integrity_check"] == "ok" and r["camada0_intacta"]
    assert [d for (d,) in mundo.con.execute("SELECT id FROM derivacao_execucao ORDER BY id")] == [1, did, did_vig]
    assert mundo.con.execute("SELECT COUNT(*) FROM coleta").fetchone()[0] == camada0          # raw layer untouched
    assert manutencao.executar(mundo.con, mundo.cfg, mundo.armazem, mundo.cfg.banco)["executada"] is False
    b = sqlite3.connect(r["backup"]["arquivo"])                # the removed runs are in the checked backup
    assert b.execute("SELECT COUNT(*) FROM derivacao_execucao WHERE id=2").fetchone()[0] == 1
    b.close()


def test_SINTETICO_manutencao_recusa_backup_que_nao_confere(mundo, monkeypatch):
    from rp import banco, manutencao
    mundo.catalogos({1: [2026]})
    mundo.listagem(1, 2026, "2026-02-28", [_reg(1, ano=2025, aproc=100.0)], T0)
    mundo.processar()
    mundo.processar()
    mundo.con.commit()
    vazio = mundo.cfg.dados_locais / "vazio.sqlite"
    import sqlite3
    sqlite3.connect(vazio).close()
    monkeypatch.setattr(banco, "backup", lambda *a, **k: vazio)
    with pytest.raises(manutencao.ManutencaoRecusada, match="não confere"):
        manutencao.executar(mundo.con, mundo.cfg, mundo.armazem, mundo.cfg.banco)
    assert mundo.con.execute("SELECT COUNT(*) FROM derivacao_execucao").fetchone()[0] == 2     # nothing deleted
