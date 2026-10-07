"""Tests of the corrective review 01-04.4 (section 23 of the specification) and of the new infrastructure.

* Cases with REAL data use the `producao` fixture (raw data of stages 01/02 processed by the production pipeline).
* Cases marked SINTETICO use invented records in a temporary database, to exercise situations the real data does
  not have (a new snapshot with a different value, a creditor with a document in the name, a downgraded rule...).
The 12 mandatory tests start with test_NN_.
"""
import hashlib
import inspect
import json
import re
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest
from conftest import RAIZ_PROJETO, registro_sintetico

from rp import banco, consultas, derivar, evidencias, governanca, normalizar, regras
from rp.painel import Painel, consulta, explicacoes, fontes, publico

RESTRITOS = set(publico.CAMPOS_RESTRITOS)


_reg = registro_sintetico


def _tudo(p, ex, df, ent=None):
    """Every public query of a cut-off (to sweep what comes out of the layer)."""
    return {"indicadores": p.indicadores(ex, df, ent), "empenhos": p.empenhos(ex, df, ent, limite=500),
            "fornecedores": p.fornecedores(ex, df, ent), "dimensao": p.por_dimensao("fonte_recurso", ex, df, ent),
            "cortes": p.cortes(), "entidades": p.entidades(ex)}


def _sha_arquivo(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ================================================================== 1. primary source = Elotech API
def test_01_indicador_principal_vem_da_api_elotech_e_nao_do_rreo(producao):
    con, nid = producao["con"], producao["nid"]
    with Painel.abrir(producao["cfg"].banco) as p:
        r = p.indicadores(2026, "2026-08-31", entidade=1)
    assert r["disponivel"] and r["fonte"] == fontes.ELOTECH["rotulo"]
    cid = consultas.snapshot_em(con, 1, 2026, "2026-01-01", "2026-08-31")
    n, liq, insc = con.execute("SELECT COUNT(*), SUM(liquidado_c), SUM(proc_c + aproc_c) FROM rp_registro "
                               "WHERE normalizacao_id=? AND coleta_id=?", (nid, cid)).fetchone()
    v = r["valores"]
    assert (v["registros"]["valor_c"], v["liquidacoes"]["valor_c"], v["inscricao_total"]["valor_c"]) == (n, liq, insc)
    assert all(x["natureza"] == "derivado" and x["fonte"] == fontes.ELOTECH["rotulo"] for x in v.values())
    # the RREO only appears as a reconciliation reference, with its own nature, and never becomes the indicator's value
    rec = v["liquidacoes"]["reconciliacao_rreo"]
    assert rec and {x["rreo_natureza"] for x in rec} == {"publicado"}
    assert v["liquidacoes"]["valor_c"] not in {x["rreo_c"] for x in rec}
    # computing the indicators does not read the RREO table
    assert "rreo" not in inspect.getsource(consulta.Painel._somas).lower()


# ================================================================== 2. a divergence does not change the API value
def test_02_divergencia_com_rreo_nao_altera_valor_da_api(producao):
    con, nid = producao["con"], producao["nid"]
    cid = consultas.snapshot_em(con, 1, 2026, "2026-01-01", "2026-08-31")
    h_api = con.execute("SELECT SUM(liquidado_c) FROM rp_registro WHERE normalizacao_id=? AND coleta_id=? AND aproc_c > 0",
                        (nid, cid)).fetchone()[0]
    antes = hashlib.sha256(repr(con.execute("SELECT * FROM rp_registro WHERE normalizacao_id=? ORDER BY 2, 3",
                                            (nid,)).fetchall()).encode()).hexdigest()
    with Painel.abrir(producao["cfg"].banco) as p:
        r = p.reconciliacao(exercicio=2026, data_final="2026-08-31", escopo="entidade")
        (h1,) = [x for x in r["linhas"] if x["coluna"] == "h" and x["regra_agregacao"]["regra"] == "RREO-COL v1"]
        ind = p.indicadores(2026, "2026-08-31", entidade=1)
    assert h1["api_c"] == h_api and h1["diferenca_c"] == -34547956 == h1["api_c"] - h1["rreo_c"]
    assert h1["situacao_da_diferenca"] == "não determinada" and "nunca é alterado" in h1["nota"]
    assert ind["valores"]["liquidacoes"]["valor_c"] == con.execute(
        "SELECT SUM(liquidado_c) FROM rp_registro WHERE normalizacao_id=? AND coleta_id=?", (nid, cid)).fetchone()[0]
    depois = hashlib.sha256(repr(con.execute("SELECT * FROM rp_registro WHERE normalizacao_id=? ORDER BY 2, 3",
                                             (nid,)).fetchall()).encode()).hexdigest()
    assert antes == depois


# ================================================================== 3 and 4. snapshots
def _dois_retratos(mundo):
    mundo.catalogos({1: [2024, 2025]})
    a = mundo.listagem(1, 2025, "2025-12-31", [_reg(1, aproc=500000.0)], "2026-09-29T20:00:00-03:00")
    mundo.processar()
    manifesto_a = mundo.cfg.snapshots / a["manifesto"]
    return a, manifesto_a, manifesto_a.read_bytes()


def test_03_SINTETICO_snapshot_antigo_intacto_apos_nova_coleta(mundo):
    a, manifesto_a, bytes_a = _dois_retratos(mundo)
    obj_a = mundo.con.execute("SELECT sha256 FROM resposta_bruta r JOIN coleta c ON c.id=r.coleta_id WHERE c.snapshot_uid=?",
                              (a["snapshot_uid"],)).fetchone()[0]
    linha_a = mundo.con.execute("SELECT * FROM coleta WHERE snapshot_uid=?", (a["snapshot_uid"],)).fetchone()
    b = mundo.listagem(1, 2025, "2025-12-31", [_reg(1, aproc=300000.0)], "2026-10-03T20:00:00-03:00")
    mundo.processar()
    assert a["snapshot_uid"] != b["snapshot_uid"]
    assert manifesto_a.read_bytes() == bytes_a                                   # manifest intact
    assert mundo.armazem.ler_objeto(obj_a)                                        # object intact (hash checked)
    assert mundo.con.execute("SELECT * FROM coleta WHERE snapshot_uid=?", (a["snapshot_uid"],)).fetchone() == linha_a
    with mundo.painel() as p:
        rt = p.retratos(1, 2025, "2025-12-31")["retratos"]
    assert [(x["snapshot_uid"], x["vigente"]) for x in rt] == [(a["snapshot_uid"], False), (b["snapshot_uid"], True)]


def test_04_SINTETICO_dois_retratos_independentes(mundo):
    a, _, _ = _dois_retratos(mundo)
    b = mundo.listagem(1, 2025, "2025-12-31", [_reg(1, aproc=300000.0)], "2026-10-03T20:00:00-03:00")
    mundo.processar()
    with mundo.painel() as p:
        atual = p.indicadores(2025, "2025-12-31", entidade=1)
        antigo = p.indicadores(2025, "2025-12-31", entidade=1, em="2026-09-30")
        dif = p.comparar_retratos(a["snapshot_uid"], b["snapshot_uid"])
    assert atual["valores"]["inscricao_total"]["valor_c"] == 30000000
    assert antigo["valores"]["inscricao_total"]["valor_c"] == 50000000
    assert atual["retrato"]["texto"] == ("Estado atual da base para o exercício de 2025, corte 31/12/2025, "
                                         "coletado em 03/10/2026")
    assert antigo["retrato"]["texto"] == ("Como a base estava em 30/09/2026: exercício de 2025, corte 31/12/2025, "
                                          "coletado em 29/09/2026")
    assert atual["valores"]["saldo_total"]["proveniencia"]["snapshots"] == [b["snapshot_uid"]]
    assert antigo["valores"]["saldo_total"]["proveniencia"]["snapshots"] == [a["snapshot_uid"]]
    assert dif["saldo_s1"]["diferenca"] == -20000000 and dif["natureza"] == "diferenca"


# ================================================================== 5. provenance
def test_05_todo_valor_tem_proveniencia_ate_o_endpoint(producao):
    con = producao["con"]
    with Painel.abrir(producao["cfg"].banco) as p:
        ctx = p.contexto()
        r = p.indicadores(2026, "2026-08-31", entidade=1)
        e = p.empenhos(2026, "2026-08-31", 1, limite=50)
        d = p.detalhe_empenho(1, 2025, 5659, 2026, "2026-08-31")
    uids = {u for (u,) in con.execute("SELECT snapshot_uid FROM coleta")}
    for v in r["valores"].values():
        pv = v["proveniencia"]
        assert pv["snapshots"] and set(pv["snapshots"]) <= uids
        assert (pv["derivacao_id"], pv["normalizacao_id"]) == (ctx["derivacao"]["id"], ctx["normalizacao"]["id"])
        assert v["retrato"]["texto"].startswith("Estado atual da base")
    (s,) = r["proveniencia"]["snapshots"]
    assert s["endpoint"] == "/empenhos/restos-a-pagar" and s["manifesto"].startswith("coletas/")
    for resp in s["respostas"]:
        assert resp["url"].startswith("https://servicos.pontagrossa.pr.gov.br/portaltransparencia-api/empenhos/restos-a-pagar")
        assert producao["armazem"].ler_objeto(resp["objeto_bruto_sha256"], resp["tamanho"])
    assert r["proveniencia"]["cadeia"][-1] == "endpoint da API Elotech"
    for reg in e["registros"]:
        assert reg["proveniencia"]["objeto_bruto_sha256"] and reg["proveniencia"]["resposta_url"]
    assert d["ocorrencias"][0]["proveniencia"]["snapshot"]["snapshot_uid"] in uids


# ================================================================== 6. entity outside the catalog != zero
def test_06_SINTETICO_entidade_fora_do_catalogo_nao_e_rp_zero(mundo):
    mundo.catalogos({1: [2024, 2025, 2026], 15: [2026]})
    t = "2026-09-29T20:00:00-03:00"
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1, aproc=10.0)], t)
    mundo.listagem(15, 2025, "2025-12-31", [], t)              # the API returns 0 records for an entity that did not exist
    mundo.listagem(1, 2026, "2026-08-31", [_reg(2, ano=2025, aproc=20.0)], t)
    mundo.listagem(15, 2026, "2026-08-31", [], t)               # exists and has no RP: a legitimate zero
    mundo.processar()
    with mundo.painel() as p:
        fora = p.indicadores(2025, "2025-12-31", entidade=15)
        mun = p.indicadores(2025, "2025-12-31")
        zero = p.indicadores(2026, "2026-08-31", entidade=15)
        cortes = {(c["exercicio"], c["data_final"]): c for c in p.cortes()["cortes"]}
    assert not fora["disponivel"] and "não é RP zero" in fora["motivo_indisponivel"]
    assert all(v["valor_c"] is None for v in fora["valores"].values())
    (e15,) = [e for e in mun["entidades"] if e["entidade"] == 15]
    assert e15["situacao_no_exercicio"] == "fora do catálogo oficial" and not e15["entra_no_total"]
    assert mun["disponivel"] and mun["valores"]["inscricao_total"]["valor_c"] == 1000
    assert cortes[(2025, "2025-12-31")]["fora_do_catalogo"] == [15]
    assert zero["disponivel"] and zero["valores"]["registros"]["valor_c"] == 0


# ================================================================== 7. mirrored pairs kept apart
def test_07_SINTETICO_pares_espelhados_continuam_separados_no_bruto(mundo):
    mundo.catalogos({1: [2024], 15: [2024]})
    t = "2026-09-29T20:00:00-03:00"
    copia = _reg(2401751, ano=2023, aproc=84.10)
    original = _reg(1751, ano=2023, entidade=15, aproc=197.50, pagoAProc=10.0, liquidado=10.0)
    mundo.listagem(1, 2024, "2024-12-31", [copia], t)
    mundo.listagem(15, 2024, "2024-12-31", [original], t)
    mundo.processar()
    linhas = mundo.con.execute("SELECT entidade, empenho, aproc_c FROM rp_registro ORDER BY entidade").fetchall()
    assert linhas == [(1, 2401751, 8410), (15, 1751, 19750)]
    objetos = {s for (s,) in mundo.con.execute("SELECT sha256 FROM resposta_bruta r JOIN coleta c ON c.id=r.coleta_id "
                                               "WHERE c.tipo='rp_listagem'")}
    assert len(objetos) == 2                                      # two raw objects, one per entity
    with mundo.painel() as p:
        pares = p.pares(2024, "2024-12-31")
        mun = p.indicadores(2024, "2024-12-31")
        d = p.detalhe_empenho(1, 2023, 2401751, 2024, "2024-12-31")
    assert pares["resumo"]["pares"] == 1 and pares["pares"][0]["lado_com_execucao"] == "B"
    assert mun["valores"]["registros"]["valor_c"] == 2 and mun["valores"]["inscricao_total"]["valor_c"] == 28160
    par = d["ocorrencias"][0]["par_espelhado"]
    assert par["este_registro_e_o_lado"] == "A" and par["b"]["empenho"] == 1751
    assert "não está determinada" in par["nota"]


# ================================================================== 8. experimental rule out of the indicator
def test_08_SINTETICO_regra_nao_operacional_nunca_entra_no_indicador_publicado(mundo):
    mundo.catalogos({1: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1)], "2026-09-29T20:00:00-03:00")
    mundo.processar()
    atual = governanca.situacao_atual(mundo.con)
    for k in consulta.REGRAS_DO_INDICADOR:
        assert atual[k]["situacao"] == "operacional" and atual[k]["compoe_indicador_publicado"]
    for k in (("RREO-COL", 1), ("RREO-COL", 2), ("CONS-PAR", 1), ("CONS-PAR", 2), ("CANC", 1)):
        assert not atual[k]["compoe_indicador_publicado"] and k not in consulta.REGRAS_DO_INDICADOR
    with pytest.raises(governanca.DecisaoInvalida):   # an experimental rule cannot make up the indicator
        governanca.registrar_decisao(mundo.con, "S1", 1, "experimental", "HIPÓTESE", True, "teste", "teste", "teste")
    rid = regras.ids(mundo.con)[("S1", 1)]
    with pytest.raises(sqlite3.IntegrityError):         # not even through direct SQL (table CHECK)
        mundo.con.execute("INSERT INTO regra_situacao (regra_id, situacao, status_evidencia, compoe_indicador_publicado, "
                          "motivo, fonte, decidido_em, origem_decisao) VALUES (?, 'experimental', 'HIPÓTESE', 1, 'x', 'x', "
                          "'2026-10-01', 'x')", (rid,))
    governanca.registrar_decisao(mundo.con, "S1", 1, "experimental", "HIPÓTESE", False, "teste SINTETICO", "teste",
                                 "teste", decidido_em="2026-10-01")
    with mundo.painel() as p:
        with pytest.raises(consulta.RegraNaoOperacional):
            p.indicadores(2025, "2025-12-31", entidade=1)
        (s1,) = [x for x in p.regras() if (x["codigo"], x["versao"]) == ("S1", 1)]
    assert [h["situacao"] for h in s1["historico"]] == ["operacional", "experimental"]   # the old decision is still there


# ================================================================== 9. a rule change = a new version
def test_09_mudanca_de_regra_exige_nova_versao(mundo):
    con = mundo.con
    rid = regras.ids(con)[("PAR-24", 1)]
    for sql in ("UPDATE regra SET definicao='outra' WHERE id=?",
                "UPDATE regra_parametro SET valor_json='3000000' WHERE regra_id=? AND nome='base_empenho_copia'",
                "DELETE FROM regra_parametro WHERE regra_id=?",
                "UPDATE regra_situacao SET situacao='aposentada' WHERE regra_id=?",
                "DELETE FROM regra_situacao WHERE regra_id=?",
                "DELETE FROM regra WHERE id=?"):
        with pytest.raises(sqlite3.DatabaseError):
            con.execute(sql, (rid,))
    assert regras.parametros(con, "PAR-24", 1) == regras.PARAMETROS[("PAR-24", 1)]
    assert regras.parametros(con, "CONC-RREO", 1) == {"entidade_do_rreo_por_entidade": 1}
    with pytest.raises(regras.ParametroAusente):
        regras.parametros(con, "S1", 1)
    antes = [con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("regra", "regra_parametro", "regra_situacao")]
    regras.semear(con)                                  # seeding again neither duplicates nor changes
    assert antes == [con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                     for t in ("regra", "regra_parametro", "regra_situacao")]


def test_parametros_de_negocio_nao_estao_espalhados_no_codigo():
    """2,400,000, the pair's entities 1/15 and the RREO entity come from regra_parametro, not from constants."""
    raiz = RAIZ_PROJETO / "app" / "rp"
    arquivos = [raiz / "derivar.py", raiz / "comparador.py", *sorted((raiz / "painel" / "consulta").glob("*.py"))]
    assert len(arquivos) > 3                            # the panel package was found
    for arq in arquivos:
        fonte = arq.read_text(encoding="utf-8")
        codigo = "\n".join(l.split("#")[0] for l in fonte.splitlines())
        assert not re.search(r"2[._]?400[._]?000", codigo), arq
        assert not re.search(r"\b(ENT_ORIGINAL|ENT_COPIA|BASE_COPIA|ENTIDADE_RREO)\b", codigo), arq
        assert "entidade=1" not in codigo.replace(" ", ""), arq


# ================================================================== 10. no rounding
def test_10_SINTETICO_nenhum_valor_monetario_e_arredondado(mundo):
    with pytest.raises(normalizar.ValorNaoRepresentavel):
        normalizar.centavos(Decimal("0.001"))
    valores = ["0.01", "0.07", "1234567.89", "0.10", "99999999.99", "3.33"]
    mundo.catalogos({1: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", [_reg(i, aproc=0, proc=float(v)) for i, v in enumerate(valores)],
                   "2026-09-29T20:00:00-03:00")
    mundo.processar()
    esperado = sum(int(Decimal(v) * 100) for v in valores)
    with mundo.painel() as p:
        v = p.indicadores(2025, "2025-12-31", entidade=1)["valores"]["inscricao_processada"]["valor_c"]
    assert v == esperado and type(v) is int
    fonte = inspect.getsource(consulta)
    assert "round(" not in fonte and "/ 100" not in fonte and "float(" not in fonte


# ================================================================== 11. the interface does not write
def test_11_interface_nao_consegue_sobrescrever_nada(producao):
    arq = producao["cfg"].banco
    antes = _sha_arquivo(arq)
    with Painel.abrir(arq, "interno") as p:
        assert p.con.execute("PRAGMA query_only").fetchone()[0] == 1
        for sql in ("INSERT INTO evidencia_externa (tipo, descricao, registrada_em) VALUES ('nota', 'x', 'x')",
                    "DELETE FROM rp_derivado", "UPDATE rp_registro SET proc_c = 0", "CREATE TABLE x (y)"):
            with pytest.raises(sqlite3.DatabaseError):
                p.con.execute(sql)
        ctx = p.contexto()
        p.cortes(), p.entidades(2026), p.indicadores(2026, "2026-08-31", 1), p.evolucao(2026, 1)
        p.empenhos(2026, "2026-08-31", 1), p.detalhe_empenho(1, 2025, 5659, 2026), p.fornecedores(2026, "2026-08-31", 1)
        p.reconciliacao(), p.coerencia_entre_publicacoes(), p.visao_analitica(2026, "2026-08-31"), p.regras()
        p.pares(2026, "2026-08-31"), p.retratos(1, 2026, "2026-08-31"), p.evidencias(), p.dicionario_campos()
    assert _sha_arquivo(arq) == antes
    assert ctx["derivacao"]["hash_resultado"] == derivar.hash_resultado(producao["con"], ctx["derivacao"]["id"])


def test_painel_recusa_banco_antigo_sem_migrar(tmp_path):
    arq = tmp_path / "v3.sqlite"
    con = sqlite3.connect(arq)
    with con:
        con.executescript(banco.ESQUEMA.read_text(encoding="utf-8"))
        con.execute("INSERT INTO esquema_versao VALUES (2, 'base', '2026-09-29T00:00:00-03:00', NULL)")
        con.execute("INSERT INTO esquema_versao VALUES (3, 'vigencia', '2026-09-29T00:00:00-03:00', NULL)")
    con.close()
    antes = _sha_arquivo(arq)
    with pytest.raises(consulta.EsquemaAntigo):
        Painel.abrir(arq)
    assert _sha_arquivo(arq) == antes                 # the panel never migrates


# ================================================================== 12. sensitive data
MEI = "12.345.678/0001-90 - JOAO DA SILVA 12345678901"


def _mundo_sensivel(mundo):
    mundo.catalogos({1: [2025]})
    regs = [_reg(1, cnpj="12.345.678/0001-90", nome=MEI, cnpjNome=MEI, fornecedor=99),
            _reg(2, cnpj="****123****", nome="FULANA DE TAL", cnpjNome="****123**** - FULANA DE TAL", fornecedor=98)]
    a = mundo.listagem(1, 2025, "2025-12-31", regs, "2026-09-29T20:00:00-03:00")
    regs[0]["nome"] = MEI + " ME"
    b = mundo.listagem(1, 2025, "2025-12-31", regs, "2026-10-03T20:00:00-03:00")
    mundo.processar()
    return a, b


def test_12_SINTETICO_dado_sensivel_fora_da_visao_publica(mundo):
    a, b = _mundo_sensivel(mundo)
    with mundo.painel() as p:
        tudo = _tudo(p, 2025, "2025-12-31", 1)
        det_pj = p.detalhe_empenho(1, 2024, 1, 2025, "2025-12-31")
        det_pf = p.detalhe_empenho(1, 2024, 2, 2025, "2025-12-31")
        dif = p.comparar_retratos(a["snapshot_uid"], b["snapshot_uid"])
    texto = json.dumps([tudo, dif], ensure_ascii=False, default=str)
    for proibido in ("12345678901", "12.345.678/0001-90", "JOAO", "FULANA", "****123****"):
        assert proibido not in texto, proibido
    for reg in tudo["empenhos"]["registros"]:
        assert not RESTRITOS & set(reg)
    assert {x["tipo_credor"] for x in tudo["fornecedores"]["linhas"]} == {"pessoa jurídica", "pessoa física"}
    assert det_pj["ocorrencias"][0]["credor"] == {"tipo": "pessoa jurídica",
                                                  "nome_publico": "JOAO DA SILVA [documento omitido] ME"}
    assert det_pf["ocorrencias"][0]["credor"]["nome_publico"] == publico.PESSOA_FISICA_OMITIDA
    assert "12345678901" not in json.dumps([det_pj, det_pf], ensure_ascii=False)
    with mundo.painel("interno") as p:                # only at the internal level, explicitly requested
        det = p.detalhe_empenho(1, 2024, 1, 2025, "2025-12-31")
        assert det["ocorrencias"][0]["credor"]["cnpj"] == "12.345.678/0001-90"
        assert "nome" in p.empenhos(2025, "2025-12-31", 1)["registros"][0]


def test_publico_mascara_documentos_no_nome():
    casos = {("11.222.333/0001-44 - MARIA SOUZA 1234567890", "11.222.333/0001-44"): "MARIA SOUZA [documento omitido]",
             ("11.222.333/0001-44 - 12.345.678 JOSE", "11.222.333/0001-44"): "[documento omitido] JOSE",
             ("EMPRESA 2020 LTDA", "11.222.333/0001-44"): "EMPRESA 2020 LTDA",
             ("CONSTRUTORA A-1 123.456.789-01", "11.222.333/0001-44"): "CONSTRUTORA A-1 [documento omitido]",
             ("QUALQUER NOME", "****123****"): publico.PESSOA_FISICA_OMITIDA}
    for (nome, doc), esperado in casos.items():
        assert publico.nome_publico(nome, doc) == esperado
    assert publico.tipo_credor("****123****") == "pessoa física" and publico.tipo_credor(None) == "não identificado"


# ================================================================== governance, evidence, extraction
def test_governanca_da_revisao_corretiva(producao):
    atual = governanca.situacao_atual(producao["con"])
    esperado = {("RREO-COL", 1): "nao_recomendada", ("RREO-COL", 2): "experimental", ("CANC", 1): "nao_recomendada",
                ("CONS-PAR", 1): "experimental", ("CONS-PAR", 2): "experimental", ("PAR-24", 1): "operacional",
                ("S1", 1): "operacional", ("CAT", 1): "operacional"}
    for k, situacao in esperado.items():
        assert atual[k]["situacao"] == situacao, k
    # RREO-COL v1 was preserved: the original decision (operational) is still in the history
    assert [h["situacao"] for h in atual[("RREO-COL", 1)]["historico"]] == ["operacional", "nao_recomendada"]
    assert atual[("RREO-COL", 1)]["uso_original"] == "estavel"    # the regra table was not edited
    # no automatic promotion
    assert not any(h["situacao"] == "operacional" for h in atual[("RREO-COL", 2)]["historico"])
    assert {c for c, _ in atual} >= {"RREO-COL", "CANC", "CONS-PAR"} and ("CANC", 2) not in atual
    assert ("CONS-PAR", 3) not in atual


def test_evidencia_externa_registrada_com_sha256_e_reconstruivel(mundo, tmp_path):
    doc = tmp_path / "resposta_esic.pdf"
    doc.write_bytes(b"%PDF-1.4 resposta sintetica do e-SIC")
    r = evidencias.registrar(mundo.con, mundo.armazem, tipo="e-SIC", descricao="Resposta sobre as copias 24xxxxx",
                             arquivo=doc, origem="e-SIC Ponta Grossa, protocolo 123 (SINTETICO)",
                             data_documento="2026-10-15", observacao="teste")
    assert r["sha256"] == hashlib.sha256(doc.read_bytes()).hexdigest()
    assert (mundo.cfg.snapshots / r["manifesto"]).is_file() and r["manifesto"].startswith("evidencias/")
    linha = mundo.con.execute("SELECT tipo, sha256, origem, data_documento, caminho_arquivo, evidencia_uid FROM "
                              "evidencia_externa WHERE id=?", (r["evidencia_id"],)).fetchone()
    assert linha == ("e-SIC", r["sha256"], "e-SIC Ponta Grossa, protocolo 123 (SINTETICO)", "2026-10-15",
                     "resposta_esic.pdf", r["evidencia_uid"])
    assert banco.verificar(mundo.con, mundo.armazem) == []
    con2, _ = banco.reconstruir(mundo.cfg, mundo.armazem, tmp_path / "reconstruido.sqlite")
    assert con2.execute("SELECT evidencia_uid, sha256 FROM evidencia_externa").fetchall() == [(r["evidencia_uid"], r["sha256"])]
    assert banco.corpo(con2, r["sha256"]) == doc.read_bytes()
    con2.close()
    with pytest.raises(evidencias.EvidenciaInvalida):
        evidencias.registrar(mundo.con, mundo.armazem, tipo="boato", descricao="x", arquivo=doc, origem="x")
    with pytest.raises(sqlite3.DatabaseError):
        mundo.con.execute("DELETE FROM evidencia_externa")
    with mundo.painel() as p:
        assert [e["evidencia_uid"] for e in p.evidencias()] == [r["evidencia_uid"]]


def test_extracao_do_rreo_registra_metodo_e_pdf(producao):
    con, nid = producao["con"], producao["nid"]
    pdfs = con.execute("SELECT r.id, r.sha256, c.id FROM resposta_bruta r JOIN coleta c ON c.id=r.coleta_id "
                       "WHERE c.tipo='rreo_pdf'").fetchall()
    assert pdfs
    for rid, sha, cid in pdfs:
        ext = con.execute("SELECT extrator_versao, biblioteca_versao, sha256_pdf, valores, erro FROM rreo_extracao "
                          "WHERE normalizacao_id=? AND resposta_id=?", (nid, rid)).fetchone()
        assert ext[0] == normalizar.EXTRATOR_RREO and ext[1].startswith("PyMuPDF ") and ext[2] == sha
        n = con.execute("SELECT COUNT(*) FROM rreo_valor WHERE normalizacao_id=? AND coleta_id=?", (nid, cid)).fetchone()[0]
        assert ext[3] == n and (ext[4] is None) == (n > 0)


# ================================================================== panel: consistency with the derivation
def test_painel_usa_os_mesmos_snapshots_vigentes_da_derivacao(producao):
    with Painel.abrir(producao["cfg"].banco) as p:
        ctx = p.contexto()
        assert p._vigentes(ctx, None) == derivar.coletas_vigentes(producao["con"])
        assert p.cortes()["snapshots_nao_processados"] == 0


def test_SINTETICO_snapshot_ainda_nao_processado_nao_vira_zero(mundo):
    mundo.catalogos({1: [2025]})
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1, aproc=10.0)], "2026-09-29T20:00:00-03:00")
    mundo.processar()
    mundo.listagem(1, 2025, "2025-12-31", [_reg(1, aproc=99.0)], "2026-10-03T20:00:00-03:00")   # not processed
    mundo.listagem(1, 2025, "2025-06-30", [_reg(1, aproc=10.0)], "2026-10-03T20:00:00-03:00")   # new cut-off
    with mundo.painel() as p:
        r = p.indicadores(2025, "2025-12-31", entidade=1)
        novo = p.indicadores(2025, "2025-06-30", entidade=1)
        assert p.cortes()["snapshots_nao_processados"] == 2
    assert r["valores"]["inscricao_total"]["valor_c"] == 1000 and any("não processados" in a for a in r["avisos"])
    assert not novo["disponivel"] and "não processado" in novo["motivo_indisponivel"]


def test_instante_normaliza_para_brasilia():
    assert consulta.instante("2026-09-29") == "2026-09-29T23:59:59-03:00"
    assert consulta.instante("2026-09-30T02:00:00+00:00") == "2026-09-29T23:00:00-03:00"
    assert consulta.instante("2026-09-29T10:00:00") == "2026-09-29T10:00:00-03:00"
    with pytest.raises(consulta.ErroDoPainel):
        consulta.instante("29/09/2026")


def test_resumo_so_chama_de_explicada_quando_tudo_esta_explicado():
    e = lambda s: {"situacao": s}
    assert explicacoes.resumo([]) == "não determinada"
    assert explicacoes.resumo([e("explicada"), e("explicada")]) == "explicada"
    assert explicacoes.resumo([e("explicada"), e("não determinada")]) == "parcialmente explicada"
    assert explicacoes.resumo([e("parcialmente explicada"), e("explicada")]) == "parcialmente explicada"
    assert explicacoes.resumo([e("hipótese"), e("não determinada")]) == "hipótese"
    # 2024, entity, L: the 2401751 copy (8,410.00) is explained, the rest is not
    achadas, situacao = explicacoes.explicar(2024, "2024-12-31", "entidade", "L", "RREO-COL v2")
    assert {x["classe"] for x in achadas} == {"T", "C"} and situacao == "parcialmente explicada"


def test_explicacoes_apontam_documentos_que_existem():
    for e in explicacoes.EXPLICACOES + explicacoes.COERENCIA:
        assert e["situacao"] in explicacoes.SITUACOES and e["status_evidencia"] in governanca.STATUS
        for parte in e["fonte"].split(";"):
            caminho = re.match(r"\s*([\w./-]+\.(?:md|py))", parte).group(1)
            assert (RAIZ_PROJETO / caminho).is_file(), caminho


def test_fontes_declaram_a_hierarquia_elotech_rreo():
    f = Painel.fontes()
    assert f["hierarquia"][0].startswith("API Elotech") and "fonte primária" in f["hierarquia"][0]
    assert "reconciliação" in f["hierarquia"][1]
    assert fontes.RREO["papel"] == "publicação oficial independente / fonte de reconciliação"
    assert "nunca é ajustado" in fontes.METODOLOGIA["tratamento"]
    assert set(fontes.NATUREZAS) == {"da_fonte", "publicado", "derivado", "analitico", "diferenca"}
    d = Painel.dicionario_campos()["campos"]
    assert d["pago_aproc_c"]["campo_api"] == "pagoAProc" and d["cnpj"]["restrito_no_nivel_publico"]
