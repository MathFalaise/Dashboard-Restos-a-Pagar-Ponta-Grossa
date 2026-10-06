"""Tests of the minimal collector (stage 04.1). None of them makes a real request."""
import json
import sqlite3

import pytest
from conftest import pagina

from rp import banco
from rp.coletor import EP_ARQ, EP_MOV, EP_PUB, EP_RP, ParametroInvalido

REG = lambda n: {"entidade": 1, "anoempenho": 2025, "empenho": n, "proc": 1.5, "aproc": 0}


def tres_paginas(portal, total=5, mudar_total_na_ultima=False):
    portal.rotas[(EP_RP, "0")] = [(200, pagina([REG(1), REG(2)], 0, total, False, 3))]
    portal.rotas[(EP_RP, "1")] = [(200, pagina([REG(3), REG(4)], 1, total, False, 3))]
    portal.rotas[(EP_RP, "2")] = [(200, pagina([REG(5)], 2, total + (1 if mudar_total_na_ultima else 0), True, 3))]


# ------------------------------------------------------------------ listing
def test_listagem_pagina_ate_last_e_grava_snapshot_completo(ambiente):
    tres_paginas(ambiente["portal"])
    s = ambiente["coletor"].listagem(1, 2026, "2026-08-31")
    assert s["status"] == "completa" and s["respostas"] == 3
    con = ambiente["con"]
    c = con.execute("SELECT tipo, entidade, exercicio, data_inicial, data_final, tipo_pesquisa, origem_carimbo "
                    "FROM coleta WHERE id=?", (s["coleta_id"],)).fetchone()
    assert c == ("rp_listagem", 1, 2026, "2026-01-01", "2026-08-31", None, "relogio_coletor")
    for _, q in ambiente["portal"].chamadas:
        assert "tipoPesquisa" not in q and q["dataInicial"] == "2026-01-01" and q["size"] == "2000"
    # bytes in the database = bytes served
    for (sha,) in con.execute("SELECT sha256 FROM resposta_bruta WHERE coleta_id=?", (s["coleta_id"],)):
        assert json.loads(banco.corpo(con, sha))["content"]


def test_total_que_muda_durante_a_paginacao_marca_incompleta(ambiente):
    tres_paginas(ambiente["portal"], mudar_total_na_ultima=True)
    s = ambiente["coletor"].listagem(1, 2026, "2026-08-31")
    assert s["status"] == "incompleta" and "totalElements mudou" in s["observacao"]


def test_data_final_fora_do_exercicio_e_recusada(ambiente):
    with pytest.raises(ParametroInvalido):
        ambiente["coletor"].listagem(1, 2026, "2025-12-31")
    assert ambiente["portal"].chamadas == []


def test_repete_em_503_e_completa(ambiente):
    p = ambiente["portal"]
    tres_paginas(p)
    p.rotas[(EP_RP, "1")] = [(503, b"indisponivel"), (200, pagina([REG(3), REG(4)], 1, 5, False, 3))]
    s = ambiente["coletor"].listagem(1, 2026, "2026-08-31")
    # 3 pages + 1 retry of the 503 + 3 of the second read (audit COL-01: a multi-page cut-off is read twice)
    assert s["status"] == "completa" and len(p.chamadas) == 7
    assert 5.0 in ambiente["relogio"].dormiu  # waits before retrying
    m = ambiente["armazem"].ler_manifesto(s["manifesto"])
    assert [r["tentativas"] for r in m["respostas"]] == [1, 2, 1]


def test_nao_repete_4xx(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [(400, b"ruim")]
    s = ambiente["coletor"].listagem(1, 2026, "2026-08-31")
    assert s["status"] == "falhou" and len(p.chamadas) == 1


def test_erro_de_rede_esgota_tentativas_e_registra_falha(ambiente):
    p = ambiente["portal"]
    p.rotas[(EP_RP, "0")] = [ConnectionError("sem rede")]
    s = ambiente["coletor"].listagem(1, 2026, "2026-08-31")
    assert s["status"] == "falhou" and s["respostas"] == 0 and len(p.chamadas) == 3


def test_pausa_minima_entre_requisicoes(ambiente):
    tres_paginas(ambiente["portal"])
    ambiente["coletor"].listagem(1, 2026, "2026-08-31")
    assert ambiente["relogio"].dormiu == [1.5] * 5  # 3 pages + 3 of the second read = 6 requests, 5 pauses


# ------------------------------------------------------------------ store and database
def test_mesmo_conteudo_vira_um_objeto_e_dois_snapshots(ambiente):
    tres_paginas(ambiente["portal"])
    a = ambiente["coletor"].listagem(1, 2026, "2026-08-31")
    b = ambiente["coletor"].listagem(1, 2026, "2026-08-31")
    con = ambiente["con"]
    assert a["snapshot_uid"] != b["snapshot_uid"]
    assert con.execute("SELECT COUNT(*) FROM coleta").fetchone()[0] == 2
    assert con.execute("SELECT COUNT(*) FROM objeto_bruto").fetchone()[0] == 3


def test_camada_0_imutavel(ambiente):
    tres_paginas(ambiente["portal"])
    ambiente["coletor"].listagem(1, 2026, "2026-08-31")
    con = ambiente["con"]
    for sql in ("UPDATE coleta SET status='falhou'", "DELETE FROM coleta", "UPDATE objeto_bruto SET tamanho=0",
                "DELETE FROM objeto_bruto", "DELETE FROM resposta_bruta", "DELETE FROM esquema_versao"):
        with pytest.raises(sqlite3.DatabaseError, match="imutável"):
            con.execute(sql)


def test_manifesto_nunca_e_sobrescrito(ambiente):
    tres_paginas(ambiente["portal"])
    s = ambiente["coletor"].listagem(1, 2026, "2026-08-31")
    m = ambiente["armazem"].ler_manifesto(s["manifesto"])
    from rp.armazem import ManifestoJaExiste
    with pytest.raises(ManifestoJaExiste):
        ambiente["armazem"].gravar_manifesto(m)


def test_objeto_corrompido_e_detectado(ambiente):
    tres_paginas(ambiente["portal"])
    s = ambiente["coletor"].listagem(1, 2026, "2026-08-31")
    sha = ambiente["armazem"].ler_manifesto(s["manifesto"])["respostas"][0]["sha256"]
    arq = ambiente["armazem"].caminho_objeto(sha)
    arq.write_bytes(arq.read_bytes()[:-3] + b"xyz")
    assert any("objeto" in p or sha[:12] in p for p in banco.verificar(ambiente["con"], ambiente["armazem"]))


def test_reconstrucao_do_banco_a_partir_do_armazem(ambiente, tmp_path):
    p = ambiente["portal"]
    tres_paginas(p)
    ambiente["coletor"].listagem(1, 2026, "2026-08-31")
    p.rotas[(EP_RP, "0")] = [(400, b"ruim")]
    ambiente["coletor"].listagem(1, 2026, "2026-06-30")
    p.rotas[(EP_MOV, "0")] = [(200, pagina([{"tipoLancamento": 20}], 0, 1, True, 1))]
    ambiente["coletor"].movimentacao(1, 2025, 5659)
    novo, n = banco.reconstruir(ambiente["cfg"], ambiente["armazem"], tmp_path / "reconstruido.sqlite")
    assert n == 3 and banco.verificar(novo, ambiente["armazem"]) == []
    q = ("SELECT c.snapshot_uid, c.tipo, c.status, c.parametros_json, c.coletada_em, r.ordem, r.sha256, r.url "
         "FROM coleta c LEFT JOIN resposta_bruta r ON r.coleta_id=c.id ORDER BY 1, 6")
    assert novo.execute(q).fetchall() == ambiente["con"].execute(q).fetchall()
    with pytest.raises(FileExistsError):
        banco.reconstruir(ambiente["cfg"], ambiente["armazem"], tmp_path / "reconstruido.sqlite")


def test_manifesto_fora_do_banco_e_detectado_e_sincronizado(ambiente):
    """Simulates a crash between writing the manifest and recording it in the database."""
    tres_paginas(ambiente["portal"])
    ambiente["coletor"].listagem(1, 2026, "2026-08-31")
    outro = banco.abrir(ambiente["cfg"], ambiente["cfg"].dados_locais / "vazio.sqlite")
    assert any("manifesto fora do banco" in p for p in banco.verificar(outro, ambiente["armazem"]))
    assert banco.sincronizar(outro, ambiente["armazem"]) == 1
    assert banco.verificar(outro, ambiente["armazem"]) == []


def test_backup_e_copia_integra(ambiente):
    tres_paginas(ambiente["portal"])
    ambiente["coletor"].listagem(1, 2026, "2026-08-31")
    arq = banco.backup(ambiente["con"], ambiente["cfg"], "teste")
    assert arq.parent == ambiente["cfg"].backups
    c = sqlite3.connect(arq)
    assert c.execute("SELECT COUNT(*) FROM coleta").fetchone()[0] == 1


def test_banco_em_versao_antiga_faz_backup_antes_de_recusar(ambiente, tmp_path):
    antigo = tmp_path / "antigo.sqlite"
    c = sqlite3.connect(antigo)
    c.execute("CREATE TABLE esquema_versao (versao INTEGER PRIMARY KEY, descricao TEXT, aplicada_em TEXT, backup_antes TEXT)")
    c.execute("INSERT INTO esquema_versao VALUES (1, 'v1', '2026-01-01', NULL)")
    c.commit()
    c.close()
    with pytest.raises(banco.MigracaoPendente, match="backup em"):
        banco.abrir(ambiente["cfg"], antigo)
    assert any("antes-migracao-v1-v" in p.name for p in ambiente["cfg"].backups.iterdir())


# ------------------------------------------------------------------ other types
def test_rreo_baixa_so_anexo_vii_e_nao_repete(ambiente):
    p = ambiente["portal"]
    pubs = [{"list": [
        {"subGrupoRelatorio": {"valor": "Anexo VII - Demonstrativo dos Restos a Pagar por Poder e Órgão"},
         "list": [{"idArquivo": 11, "valor": "1º Bimestre", "nomeArquivo": "a.pdf"},
                  {"idArquivo": 12, "valor": "1º Bimestre - Consolidado", "nomeArquivo": "b.pdf"}]},
        {"subGrupoRelatorio": {"valor": "Anexo I - Balanço Orçamentário"}, "list": [{"idArquivo": 99, "valor": "x"}]}]}]
    p.rotas[(EP_PUB, None)] = [(200, json.dumps(pubs).encode())]
    p.rotas[(f"{EP_ARQ}/11", None)] = [(200, b"%PDF-1.3 a")]
    p.rotas[(f"{EP_ARQ}/12", None)] = [(200, b"%PDF-1.3 b")]
    r1 = ambiente["coletor"].rreo(2026)
    assert [s["status"] for s in r1] == ["completa"] * 3
    r2 = ambiente["coletor"].rreo(2026)
    assert len(r2) == 1  # only the listing; PDFs already collected are not repeated
    assert not any(q[0].endswith("/99") for q in p.chamadas)


def test_pdf_invalido_fica_como_falha(ambiente):
    p = ambiente["portal"]
    pubs = [{"list": [{"subGrupoRelatorio": {"valor": "Anexo VII - Demonstrativo dos Restos a Pagar"},
                       "list": [{"idArquivo": 11, "valor": "1º Bimestre"}]}]}]
    p.rotas[(EP_PUB, None)] = [(200, json.dumps(pubs).encode())]
    p.rotas[(f"{EP_ARQ}/11", None)] = [(200, b"<html>erro</html>")]
    assert [s["status"] for s in ambiente["coletor"].rreo(2026)] == ["completa", "falhou"]


def test_versao_do_coletor_inclui_hash_do_codigo(ambiente):
    tres_paginas(ambiente["portal"])
    ambiente["coletor"].listagem(1, 2026, "2026-08-31")
    nome, versao, h = ambiente["con"].execute("SELECT nome, versao, sha256_codigo FROM coletor_versao").fetchone()
    assert nome == "rp-coletor" and versao.endswith(h[:12]) and len(h) == 64
