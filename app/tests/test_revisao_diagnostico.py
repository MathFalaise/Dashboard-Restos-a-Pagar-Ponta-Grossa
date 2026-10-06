"""Critical review (05/10/2026), item 49 - `diagnosticar-api`: checks the API contract without writing anything.

Simulated transport (fixture `ambiente`): no query leaves the machine. The structure reference is the snapshots
recorded by the production collector from the same simulated portal.
"""
import json

import pytest
from conftest import pagina

from rp import cli, contrato, diagnostico
from rp.coletor import EP_ENT, EP_EXE, EP_RP, ParametroInvalido

APP_CONFIG = diagnostico.__file__.replace("\\", "/").rsplit("/rp/", 1)[0] + "/config.toml"
REG = lambda n, **kw: {"entidade": 1, "anoempenho": 2025, "empenho": n, "proc": 1.5, "aproc": 0, "credor": None, **kw}
SORT_ECO = [{"property": "anoempenho", "ascending": True, "descending": False, "direction": "ASC"},
            {"property": "empenho", "ascending": True, "descending": False, "direction": "ASC"}]
ENTIDADES = [{"id": 1, "nome": "Prefeitura"}, {"id": 15, "nome": "Fundo"}]
EXERCICIOS = [{"id": {"exercicio": 2025, "entidade": {"id": 1}}}, {"id": {"exercicio": 2026, "entidade": {"id": 1}}}]


def _pag(regs, size=2000, sort=SORT_ECO, total=None, ultima=True, paginas=None):
    total = len(regs) if total is None else total
    d = json.loads(pagina(regs, 0, total, ultima, -(-total // size) if paginas is None else paginas))
    d["size"] = size
    if sort is not None:
        d["sort"] = sort
    return json.dumps(d).encode()


def _api(portal, entidades=ENTIDADES, exercicios=EXERCICIOS, listagem=None):
    portal.rotas[(EP_ENT, None)] = [(200, json.dumps(entidades).encode())]
    portal.rotas[(f"{EP_EXE}/1", None)] = [(200, json.dumps(exercicios).encode())]
    portal.rotas[(EP_RP, "0")] = [(200, _pag([REG(4), REG(5)], size=20) if listagem is None else listagem)]


def _referencia(ambiente):
    """Complete snapshots recorded by the collector. The creditor is an object in ONE record only: a rare field."""
    _api(ambiente["portal"], listagem=_pag([REG(1), REG(2, credor={"nome": "X"}), REG(3)]))
    c = ambiente["coletor"]
    assert [s["status"] for s in c.catalogos([1])] == ["completa", "completa"]
    assert c.listagem(1, 2025, "2025-12-31")["status"] == "completa"


def _diagnosticar(ambiente, con="banco", **kw):
    return diagnostico.diagnosticar(ambiente["con"] if con == "banco" else con, ambiente["coletor"].cliente,
                                    kw.pop("entidade", 1), kw.pop("exercicio", 2025), kw.pop("data_final", "2025-12-31"),
                                    **kw)


def _por_alvo(r):
    return {v["alvo"]: v for v in r["verificacoes"]}


def _arquivos(ambiente):
    return sorted((p.as_posix(), p.stat().st_size) for p in ambiente["cfg"].snapshots.rglob("*") if p.is_file())


# ------------------------------------------------------------------ same API: ok, and nothing written
def test_REV49_api_igual_da_ok_e_nao_grava_nada(ambiente):
    _referencia(ambiente)
    _api(ambiente["portal"])
    con = ambiente["con"]
    antes = (con.total_changes, con.execute("SELECT COUNT(*) FROM coleta").fetchone()[0], _arquivos(ambiente))
    r = _diagnosticar(ambiente)
    assert r["resultado"] == "ok" and diagnostico.CODIGO_DE_SAIDA[r["resultado"]] == 0
    assert all(v["situacao"] == "ok" and not v["problemas"] for v in r["verificacoes"])
    assert all(v["estrutura"]["igual"] for v in r["verificacoes"])
    # the creditor object of ONE recorded record is not required: the sample without it is not a "removed field"
    assert "$.content[].credor.nome" not in _por_alvo(r)["rp_listagem"]["estrutura"]["removidos"]
    assert (con.total_changes, con.execute("SELECT COUNT(*) FROM coleta").fetchone()[0], _arquivos(ambiente)) == antes
    assert r["requisicoes"] == 3 + 4          # 3 from the reference collection + 4 from the diagnostic
    assert r["portal"]["http_status"] == 404 and r["portal"]["versao"] is None   # informative: does not change the result
    url = _por_alvo(r)["rp_listagem"]["url"]
    assert "sort=anoempenho%2Casc&sort=empenho%2Casc" in url and "size=20" in url


def test_REV49_versao_do_portal_e_informativa(ambiente):
    _api(ambiente["portal"])
    ambiente["portal"].rotas[(diagnostico.EP_INFO, None)] = [
        (200, json.dumps({"build": {"version": "3.128.0", "time": "2026-09-22T10:00:00Z", "name": "x"}}).encode())]
    r = _diagnosticar(ambiente, con=None)
    assert r["resultado"] == "ok"
    assert (r["portal"]["versao"], r["portal"]["build"]) == ("3.128.0", "2026-09-22T10:00:00Z")


# ------------------------------------------------------------------ structure
def test_REV49_campo_novo_tipo_novo_e_campo_obrigatorio_sumido(ambiente):
    _referencia(ambiente)
    regs = [REG(4, novoCampo=1, proc="1,50"), {k: v for k, v in REG(5).items() if k != "aproc"}]
    _api(ambiente["portal"], listagem=_pag(regs, size=20))
    r = _diagnosticar(ambiente)
    lst = _por_alvo(r)["rp_listagem"]
    assert r["resultado"] == "mudou" and diagnostico.CODIGO_DE_SAIDA["mudou"] == 1 and lst["situacao"] == "mudou"
    e = lst["estrutura"]
    assert e["novos"] == ["$.content[].novoCampo"]
    assert e["tipo_diferente"] == ["$.content[].proc: number -> number|string"]
    assert e["removidos"] == ["$.content[].aproc"]
    assert _por_alvo(r)["entidades"]["situacao"] == "ok"


def test_REV49_amostra_vazia_so_confere_o_topo_da_pagina(ambiente):
    _referencia(ambiente)
    _api(ambiente["portal"], listagem=_pag([], size=20))
    lst = _por_alvo(_diagnosticar(ambiente))["rp_listagem"]
    assert lst["situacao"] == "ok" and lst["estrutura"]["removidos"] == []
    assert any("amostra sem registros" in a for a in lst["avisos"])
    sem_total = json.loads(_pag([], size=20))
    del sem_total["totalElements"]
    _api(ambiente["portal"], listagem=json.dumps(sem_total).encode())
    lst = _por_alvo(_diagnosticar(ambiente))["rp_listagem"]
    assert lst["situacao"] == "mudou" and "$.totalElements" in lst["estrutura"]["removidos"]
    assert any("totalElements ausente" in p for p in lst["problemas"])


def test_REV49_comparar_amostra_nao_acusa_campo_raro():
    ref = [json.dumps({"content": [REG(1), REG(2, credor={"nome": "X"})], "totalElements": 2}).encode()]
    amostra = [json.dumps({"content": [REG(3)], "totalElements": 1}).encode()]
    c = contrato.comparar_amostra(ref, amostra)
    assert c["igual"] and c["registros_na_amostra"] == 1
    assert contrato.comparar_formas(contrato.forma(ref), contrato.forma(amostra))["removidos"] == \
        ["$.content[].credor.nome"]           # the union comparison would flag it; the required-fields one does not


def test_REV49_eco_da_ordem_pedida_nao_e_mudanca_de_estrutura():
    # measured on the portal on 05/10/2026: the only difference between the sample and the recorded snapshots was the `sort` echo,
    # empty in the snapshots collected before the collector asked for the order
    pag = lambda reg, sort, sort_pageable: json.dumps(
        {"content": [reg], "sort": sort, "pageable": {"sort": sort_pageable, "pageNumber": 0}}).encode()
    antigo = [pag(REG(1), [], [])]
    assert contrato.comparar_amostra(antigo, [pag(REG(2), SORT_ECO, SORT_ECO)])["igual"]
    objeto = contrato.comparar_amostra(antigo, [pag(REG(2), {"sorted": True}, [])])
    assert objeto["tipo_diferente"] == ["$.sort: array -> object"] and objeto["novos"] == ["$.sort.sorted"]


# ------------------------------------------------------------------ page and order contract
@pytest.mark.parametrize("listagem, trecho", [
    (_pag([REG(4)], size=20, sort=None), "não ecoa 'sort'"),
    (_pag([REG(4)], size=20, sort=[{**SORT_ECO[0], "direction": "DESC"}, SORT_ECO[1]]), "não aplicou a ordenação"),
    (_pag([REG(5), REG(4)], size=20), "não cresce dentro da página"),
    (_pag([REG(4), REG(5, entidade=15)], size=20), "da entidade 15 na listagem da entidade 1"),
    (_pag([REG(4), REG(4)], size=20), "repetida na amostra"),
    (_pag([REG(4)], size=20, total=7), "é a última (last=true), mas totalElements=7"),
    (_pag([REG(4)], size=20, total=50, ultima=False), "não é a última (last=false), mas veio com 1 de 20"),
    (_pag([REG(4)], size=20, paginas=3), "totalPages=3 incoerente"),
    (b'{"erro": "sessao expirada"}', "não é uma página JSON"),
])
def test_REV49_contrato_da_listagem(ambiente, listagem, trecho):
    _api(ambiente["portal"], listagem=listagem)
    r = _diagnosticar(ambiente, con=None)
    lst = _por_alvo(r)["rp_listagem"]
    assert r["resultado"] == "mudou" and lst["situacao"] == "mudou"
    assert any(trecho in p for p in lst["problemas"]), lst["problemas"]


@pytest.mark.parametrize("entidades, exercicios, alvo, trecho", [
    ({"erro": "x"}, EXERCICIOS, "entidades", "não é uma lista"),
    ([], EXERCICIOS, "entidades", "vazio"),
    (ENTIDADES, [{"id": {"exercicio": 2025, "entidade": {"id": 15}}}], "exercicios/1", "é da entidade 15"),
])
def test_REV49_contrato_dos_catalogos(ambiente, entidades, exercicios, alvo, trecho):
    _api(ambiente["portal"], entidades=entidades, exercicios=exercicios)
    v = _por_alvo(_diagnosticar(ambiente, con=None))[alvo]
    assert v["situacao"] == "mudou" and any(trecho in p for p in v["problemas"])


def test_REV49_fora_do_catalogo_e_so_aviso(ambiente):
    _api(ambiente["portal"], entidades=[{"id": 15}], exercicios=[{"id": {"exercicio": 2026, "entidade": {"id": 1}}}])
    r = _diagnosticar(ambiente, con=None)
    v = _por_alvo(r)
    assert r["resultado"] == "ok"
    assert v["entidades"]["avisos"] == ["entidade 1 fora do catálogo de entidades",
                                        "nenhum snapshot completo do tipo entidades no banco: estrutura não comparada"]
    assert "exercício 2025 fora do catálogo" in v["exercicios/1"]["avisos"][0]


# ------------------------------------------------------------------ network and HTTP
def test_REV49_rede_e_5xx_sao_indisponivel_e_4xx_e_mudanca(ambiente):
    p = ambiente["portal"]
    _api(p)
    p.rotas[(EP_ENT, None)] = [(503, b"fora")]
    p.rotas[(f"{EP_EXE}/1", None)] = [ConnectionError("caiu")]
    r = _diagnosticar(ambiente, con=None)
    v = _por_alvo(r)
    assert r["resultado"] == "indisponivel" and diagnostico.CODIGO_DE_SAIDA["indisponivel"] == 2
    assert (v["entidades"]["situacao"], v["entidades"]["http_status"]) == ("indisponivel", 503)
    assert (v["exercicios/1"]["situacao"], v["exercicios/1"]["http_status"]) == ("indisponivel", None)
    assert v["rp_listagem"]["situacao"] == "ok"
    del p.rotas[(EP_RP, "0")]                       # the simulated portal returns 404: the endpoint changed
    r = _diagnosticar(ambiente, con=None)
    assert r["resultado"] == "mudou" and _por_alvo(r)["rp_listagem"]["http_status"] == 404


@pytest.mark.parametrize("kw", [{"data_final": "2026-01-31"}, {"data_final": "31/12/2025"}, {"tamanho": 0},
                                {"tamanho": 2001}, {"tamanho": True}])
def test_REV49_parametros_recusados_antes_de_consultar(ambiente, kw):
    with pytest.raises(ParametroInvalido):
        _diagnosticar(ambiente, con=None, **kw)
    assert ambiente["portal"].chamadas == []


# ------------------------------------------------------------------ CLI
def test_REV49_cli_codigo_de_saida_e_banco_so_leitura(ambiente, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("RP_DADOS_LOCAIS", raising=False)
    _referencia(ambiente)
    _api(ambiente["portal"])
    cfg = ambiente["cfg"]
    arq = tmp_path / "cfg" / "config.toml"
    arq.parent.mkdir()
    texto = open(APP_CONFIG, encoding="utf-8").read()
    arq.write_text(texto.replace('"~/RestosAPagar_local"', json.dumps(str(cfg.dados_locais)))
                   .replace('"../data/snapshots"', json.dumps(str(cfg.snapshots)))
                   .replace('"../data/backups"', json.dumps(str(cfg.backups))), encoding="utf-8")
    monkeypatch.setattr(cli, "Cliente", lambda _cfg: ambiente["coletor"].cliente)
    ambiente["con"].commit()
    mtime = cfg.banco.stat().st_mtime_ns
    args = ["--config", str(arq), "diagnosticar-api", "--entidade", "1", "--exercicio", "2025", "--data-final",
            "2025-12-31"]
    assert cli.main(args) == 0
    r = json.loads(capsys.readouterr().out)
    assert r["resultado"] == "ok" and all(v["estrutura"] for v in r["verificacoes"])
    assert cfg.banco.stat().st_mtime_ns == mtime
    _api(ambiente["portal"], listagem=_pag([REG(4, novoCampo=1)], size=20))
    assert cli.main(args) == 1
    capsys.readouterr()
    assert cli.main(args[:-1] + ["2026-01-31"]) == 4          # end date outside the fiscal year: refused
    assert "ParametroInvalido" in capsys.readouterr().out
