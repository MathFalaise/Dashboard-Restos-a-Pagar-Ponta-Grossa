"""Portoes da revisao de seguranca, correcoes e otimizacao (30/09/2026).

Cada teste fixa uma protecao ou uma correcao: se alguem a desfizer, o teste falha.
Os registros montados aqui sao SINTETICOS. Nenhum teste acessa a internet: o teste do
transporte HTTP real usa um servidor local em 127.0.0.1.
"""
import decimal
import http.server
import json
import threading
import zlib
from decimal import Decimal

import pytest
from conftest import Relogio, pagina

from rp import banco, cli, comparador, derivar, execucoes, normalizar
from rp.armazem import Armazem, ManifestoInvalido, ObjetoCorrompido, _publicar_sem_sobrescrever, descomprimir
from rp.coletor import EP_ARQ, EP_PUB, EP_RP
from rp.config import ConfiguracaoInvalida, carregar
from rp.http import Cliente, ErroDeRede, RespostaRecusada, ler_limitado, transporte_requests, validar_caminho
from rp.snapshots import gravar_snapshot

COL = {"nome": "teste", "versao": "1", "sha256_codigo": None}
P = {"entidade": 998, "exercicio": 2026, "dataInicial": "2026-01-01", "dataFinal": "2026-12-31", "size": 2000}
ANEXO_VII = "Anexo VII - Demonstrativo dos Restos a Pagar"
SEXTO = "6º Bimestre"   # rotulo como o portal publica (indicador ordinal)


def _cfg(tmp_path, **kw):
    return carregar(dados_locais=tmp_path / "l", snapshots=tmp_path / "s", backups=tmp_path / "b", **kw)


def _loja(tmp_path):
    cfg = _cfg(tmp_path)
    return cfg, banco.abrir(cfg), Armazem(cfg.snapshots)


def _registro(**kw):
    reg = {k: 0 for k in normalizar.DINHEIRO}
    reg.update({"entidade": 998, "anoempenho": 2025, "empenho": 7})
    reg.update(kw)
    return reg


def _listagem(regs):
    return json.dumps({"content": regs, "last": True, "totalElements": len(regs)}).encode()


def _snap(con, armazem, quando, corpo, tipo="rp_listagem", params=P):
    return gravar_snapshot(con, armazem, tipo=tipo, endpoint="/x", parametros=params, coletada_em=quando,
                           origem_carimbo="relogio_coletor", status="completa", coletor=COL,
                           respostas=[{"url": "sintetico", "http_status": 200, "corpo": corpo}])


# ------------------------------------------------------------------ HTTP
def test_ler_limitado_recusa_corpo_acima_do_teto():
    assert ler_limitado([b"a" * 10, b"b" * 10], 20, float("inf")) == b"a" * 10 + b"b" * 10
    with pytest.raises(RespostaRecusada, match="maior que 15"):
        ler_limitado([b"a" * 10, b"b" * 10], 15, float("inf"))


def test_ler_limitado_recusa_leitura_lenta_demais():
    tempos = iter([1.0, 5.0, 11.0])
    with pytest.raises(RespostaRecusada, match="prazo"):
        ler_limitado([b"a", b"b", b"c"], 100, 10.0, monotonic=lambda: next(tempos))


def test_resposta_recusada_nao_e_repetida(tmp_path):
    chamadas = []

    def transporte(url, timeout):
        chamadas.append(url)
        raise RespostaRecusada("corpo maior que 1 bytes")
    relogio = Relogio()
    c = Cliente(_cfg(tmp_path, tentativas=3), transporte=transporte, dormir=relogio.dormir, monotonic=relogio.monotonic)
    with pytest.raises(ErroDeRede, match="recusada"):
        c.get(EP_RP, {"page": 0})
    assert len(chamadas) == 1 and relogio.dormiu == []


def test_retry_after_do_servidor_tem_teto(tmp_path):
    respostas = [(429, {"Retry-After": "999999"}, b""), (200, {}, b"{}")]
    relogio = Relogio()
    c = Cliente(_cfg(tmp_path, espera_base=5.0, tentativas=3), transporte=lambda url, timeout: respostas.pop(0),
                dormir=relogio.dormir, monotonic=relogio.monotonic)
    assert c.get(EP_RP).status == 200
    assert max(relogio.dormiu) == 300    # e nao 999999 s


@pytest.mark.parametrize("caminho", ["https://outro.host/x", "//outro.host/x", "/a/../b", "/a/./b", "/a?b=1", "/a#b",
                                     "relativo", "/a b", "/a/%2e%2e/b", ""])
def test_caminho_da_api_so_aceita_segmentos_simples(caminho):
    with pytest.raises(ValueError):
        validar_caminho(caminho)


def test_caminhos_usados_pelo_coletor_sao_aceitos():
    for c in (EP_RP, EP_PUB, f"{EP_ARQ}/34898", "/api/exercicios/entidade/15", "/empenhos/detalhe/movimentacao"):
        assert validar_caminho(c) == c


class _Servidor(http.server.BaseHTTPRequestHandler):
    def _responder(self, status, corpo=b"", cabecalhos=(), tamanho=True):
        self.send_response(status)
        for k, v in cabecalhos:
            self.send_header(k, v)
        if tamanho:
            self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if self.path == "/redireciona":
            self._responder(302, cabecalhos=[("Location", "http://127.0.0.1:9/outro")])
        elif self.path == "/grande":
            self._responder(200, b"x" * 5000)
        elif self.path == "/sem-tamanho":
            self._responder(200, b"y" * 5000, tamanho=False)   # HTTP/1.0: corpo ate fechar a conexao
        else:
            self._responder(200, b'{"ok": true}')

    def log_message(self, *args):
        pass


@pytest.fixture
def servidor_local():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Servidor)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def test_transporte_real_nao_segue_redirecionamento_e_limita_o_corpo(servidor_local):
    get = transporte_requests("teste", 1000, 30)
    status, _, corpo = get(servidor_local + "/redireciona", 10)
    assert status == 302 and corpo == b""    # devolvido como veio: o coletor registra como falha
    status, _, corpo = get(servidor_local + "/ok", 10)
    assert status == 200 and corpo == b'{"ok": true}'
    with pytest.raises(RespostaRecusada, match="Content-Length"):
        get(servidor_local + "/grande", 10)
    with pytest.raises(RespostaRecusada, match="maior que 1000"):
        get(servidor_local + "/sem-tamanho", 10)


# ------------------------------------------------------------------ configuracao
@pytest.mark.parametrize("mudanca", [{"api_base": "http://servicos.pontagrossa.pr.gov.br/api"},
                                     {"api_base": "https://usuario:senha@host/api"},
                                     {"api_base": "https://host/api?x=1"},
                                     {"tentativas": 0}, {"timeout": 0.0}, {"pausa": -1.0}, {"espera_base": float("nan")},
                                     {"limite_resposta_bytes": 0}, {"user_agent": "a\r\nX-Injetado: 1"}])
def test_configuracao_fraca_e_recusada(tmp_path, mudanca):
    with pytest.raises(ConfiguracaoInvalida):
        _cfg(tmp_path, **mudanca)


# ------------------------------------------------------------------ armazem
def test_hash_invalido_nunca_vira_caminho(tmp_path):
    a = Armazem(tmp_path / "s")
    for h in ("../../../fora", "AB" * 32, "0" * 63, 123, None):
        with pytest.raises(ObjetoCorrompido, match="hash invalido"):
            a.caminho_objeto(h)


def test_descomprimir_igual_a_zlib_e_com_teto(monkeypatch):
    dados = bytes(range(256)) * 1000
    comp = zlib.compress(dados, 6)
    assert descomprimir(comp) == zlib.decompress(comp) == dados
    assert descomprimir(comp, len(dados)) == dados
    with pytest.raises(ObjetoCorrompido, match="passa de 100 bytes"):
        descomprimir(zlib.compress(b"\0" * 10_000_000), 100)     # bomba: 10 MB a partir de ~10 KB
    with pytest.raises(ObjetoCorrompido, match="difere"):
        descomprimir(comp, len(dados) + 1)
    with pytest.raises(ObjetoCorrompido, match="incompleto"):
        descomprimir(comp[:-10], len(dados))
    import rp.armazem as modulo
    monkeypatch.setattr(modulo, "LIMITE_OBJETO", 1000)
    with pytest.raises(ObjetoCorrompido, match="passa de 1000 bytes"):
        descomprimir(comp)


def test_manifesto_fora_do_formato_e_recusado(tmp_path):
    a = Armazem(tmp_path / "s")
    base = {"tipo": "rp_listagem", "snapshot_uid": "0" * 32, "coletada_em": "2026-09-30T10:00:00-03:00"}
    for campo, valor in (("snapshot_uid", "../../fora"), ("tipo", "../x"), ("coletada_em", "../../2026")):
        with pytest.raises(ManifestoInvalido):
            a.gravar_manifesto(dict(base, **{campo: valor}))
    assert not list((tmp_path / "s").rglob("*.json"))


def test_publicacao_exclusiva_nao_sobrescreve_destino_existente(tmp_path):
    destino, tmp = tmp_path / "m.json", tmp_path / "m.json.tmp"
    destino.write_text("original", encoding="utf-8")
    tmp.write_text("novo", encoding="utf-8")
    with pytest.raises(FileExistsError):
        _publicar_sem_sobrescrever(tmp, destino)
    assert destino.read_text(encoding="utf-8") == "original"


def test_manifesto_ilegivel_e_relatado_e_nao_derruba_a_verificacao(tmp_path):
    cfg, con, a = _loja(tmp_path)
    _snap(con, a, "2026-09-30T10:00:00-03:00", _listagem([_registro(aproc=10)]))
    ruim = cfg.snapshots / "coletas" / "2026" / "09" / "ruim.json"
    ruim.write_text("{nao e json", encoding="utf-8")
    assert any("ruim.json" in p and "ilegivel" in p for p in a.verificar())
    assert any("ruim.json" in p for p in banco.verificar(con, a))
    with pytest.raises(ManifestoInvalido):
        a.manifestos()


# ------------------------------------------------------------------ banco
def test_banco_ativo_em_pasta_do_onedrive_e_recusado(tmp_path):
    cfg = carregar(dados_locais=tmp_path / "OneDrive" / "dados", snapshots=tmp_path / "s", backups=tmp_path / "b")
    with pytest.raises(banco.BancoEmPastaSincronizada):
        banco.abrir(cfg)
    assert not cfg.banco.exists()


def test_backups_no_mesmo_segundo_nunca_se_sobrescrevem(tmp_path):
    cfg, con, _ = _loja(tmp_path)
    a = banco.backup(con, cfg, "manual")
    b = banco.backup(con, cfg, "manual")
    assert a != b and a.exists() and b.exists()


def test_motivo_do_backup_nao_escolhe_a_pasta(tmp_path):
    cfg, con, _ = _loja(tmp_path)
    arq = banco.backup(con, cfg, "../../fora/x")
    assert arq.parent == cfg.backups and ".." not in arq.name and arq.exists()


def test_objeto_adulterado_no_banco_e_detectado_sem_assert(tmp_path):
    cfg, con, a = _loja(tmp_path)
    s = _snap(con, a, "2026-09-30T10:00:00-03:00", _listagem([_registro(aproc=10)]))
    (sha,) = con.execute("SELECT sha256 FROM resposta_bruta WHERE coleta_id=?", (s["coleta_id"],)).fetchone()
    con.execute("DROP TRIGGER objeto_sem_update")   # so neste banco de teste: simula adulteracao direta do arquivo
    con.execute("UPDATE objeto_bruto SET dados=? WHERE sha256=?", (zlib.compress(b'{"content": []}'), sha))
    con.commit()
    with pytest.raises(ObjetoCorrompido):
        banco.corpo(con, sha)
    assert any("objeto corrompido no banco" in p for p in banco.verificar(con, a))


# ------------------------------------------------------------------ coletor
def test_servidor_que_ignora_page_nao_prende_o_coletor(ambiente):
    p = ambiente["portal"]
    # a mesma pagina, sempre com last=false e sem totalPages: sem a trava, o coletor pediria paginas para sempre
    p.rotas[(EP_RP, None)] = [(200, pagina([_registro(aproc=1)] * 2, 0, 5, False, None))]
    s = ambiente["coletor"].listagem(998, 2026, "2026-12-31")
    # auditoria COL-02: a pagina 1 volta com number=0 e e recusada ja na segunda chamada (antes: 3 chamadas, pela soma)
    assert s["status"] == "incompleta" and len(p.chamadas) == 2
    assert "devolveu a página number=0" in s["observacao"]
    # sem `number` na resposta, a trava antiga continua valendo: 2 + 2 + 2 = 6 > 5 na terceira pagina
    p.chamadas.clear()
    p.rotas[(EP_RP, None)] = [(200, json.dumps({"content": [_registro(aproc=1)] * 2, "totalElements": 5,
                                                "last": False}).encode())]
    s = ambiente["coletor"].listagem(997, 2026, "2026-12-31")
    assert s["status"] == "incompleta" and len(p.chamadas) <= 3


def test_id_de_arquivo_que_nao_e_inteiro_nao_entra_na_url(ambiente):
    p = ambiente["portal"]
    lista = [{"idArquivo": "../../api/outra", "valor": SEXTO}, {"idArquivo": True, "valor": SEXTO},
             {"idArquivo": 7, "valor": SEXTO}]
    p.rotas[(EP_PUB, None)] = [(200, json.dumps([{"list": [{"subGrupoRelatorio": {"valor": ANEXO_VII},
                                                             "list": lista}]}]).encode())]
    p.rotas[(f"{EP_ARQ}/7", None)] = [(200, b"%PDF-1.3")]
    r = ambiente["coletor"].rreo(2024, bimestres={6})
    arquivos = [c[0].rsplit("/", 1)[1] for c in p.chamadas if "/arquivo/" in c[0]]
    assert len(r) == 2 and arquivos == ["7"]


# ------------------------------------------------------------------ normalizacao
def test_catalogo_malformado_nao_derruba_a_normalizacao(tmp_path):
    cfg, con, a = _loja(tmp_path)
    _snap(con, a, "2026-09-30T10:00:00-03:00", b'{"erro": "nao e lista"}', tipo="entidades", params={})
    _snap(con, a, "2026-09-30T10:01:00-03:00", json.dumps([{"sem_id": 1}]).encode(), tipo="exercicios",
          params={"entidade": 1})
    _snap(con, a, "2026-09-30T10:02:00-03:00", _listagem([_registro(aproc=10)]))
    nid, resumo = normalizar.normalizar(con)
    assert resumo["ignoradas_sem_pagina"] == 1 and resumo["rp_registro"] == 1
    assert [p["catalogo"] for p in resumo["problemas"]] == ["exercicios"]
    assert con.execute("SELECT COUNT(*) FROM exercicio_ref WHERE normalizacao_id=?", (nid,)).fetchone()[0] == 0


def _centavos_de_referencia(v):
    """Implementacao anterior a otimizacao, copiada literalmente: a nova tem de dar o mesmo resultado."""
    if v is None:
        return None
    d = Decimal(str(v))
    q = d.quantize(Decimal("0.01"))
    if q != d:
        raise normalizar.ValorNaoRepresentavel(f"{v!r} tem mais de 2 casas decimais")
    return int(q * 100)


@pytest.mark.parametrize("v", [0, 1, -1, 7, 123456789, -98765432101234567, 10 ** 19, Decimal("0"), Decimal("12.3"),
                               Decimal("12.30"), Decimal("-0.01"), Decimal("1E+2"), Decimal("123456789.99"),
                               "4.5", 2.5, None])
def test_centavos_otimizado_da_o_mesmo_resultado(v):
    assert normalizar.centavos(v) == _centavos_de_referencia(v)


@pytest.mark.parametrize("v", [Decimal("0.001"), Decimal("1.005"), 0.1 + 0.2, "1.234"])
def test_centavos_continua_recusando_mais_de_duas_casas(v):
    for f in (normalizar.centavos, _centavos_de_referencia):
        with pytest.raises(normalizar.ValorNaoRepresentavel):
            f(v)


def test_centavos_trata_booleano_como_antes():
    for f in (normalizar.centavos, _centavos_de_referencia):
        with pytest.raises(decimal.InvalidOperation):
            f(True)


# ------------------------------------------------------------------ execucoes
def test_derivacao_atual_continua_protegida_quando_ha_como_estava_em_mais_nova(tmp_path):
    cfg, con, a = _loja(tmp_path)
    _snap(con, a, "2026-09-30T10:00:00-03:00", _listagem([_registro(aproc=10)]))
    nid, _ = normalizar.normalizar(con)
    atual = derivar.derivar(con, nid)
    como_estava = derivar.derivar(con, nid, "2026-09-30T23:59:59-03:00")
    for d in (atual, como_estava):
        with pytest.raises(execucoes.ExclusaoRecusada, match="mais recente"):
            execucoes.apagar(con, cfg, "derivacao", d, d)
    nova = derivar.derivar(con, nid)
    assert execucoes.apagar(con, cfg, "derivacao", atual, atual)["camada0_intacta"]
    assert {d["id"] for d in execucoes.listar(con)["derivacoes"]} == {como_estava, nova}


# ------------------------------------------------------------------ comparador
def test_SINTETICO_chave_repetida_nao_some_do_saldo_s1(tmp_path):
    cfg, con, a = _loja(tmp_path)
    regs = [_registro(aproc=10), _registro(aproc=20)]            # a mesma chave duas vezes
    s1 = _snap(con, a, "2026-09-29T20:00:00-03:00", _listagem(regs))
    s2 = _snap(con, a, "2026-10-03T20:00:00-03:00", _listagem(regs))
    nid, _ = normalizar.normalizar(con)
    derivar.derivar(con, nid)
    r = comparador.comparar(con, s1["snapshot_uid"], s2["snapshot_uid"])
    assert r["saldo_s1"] == {"antes": 3000, "depois": 3000, "diferenca": 0}
    assert r["chaves_duplicadas"]["anterior"] == [(998, 2025, 7)] and r["contagens"]["alterados"] == 0


# ------------------------------------------------------------------ linha de comando
def test_comparar_com_saida_nunca_sobrescreve_arquivo(tmp_path):
    arq = tmp_path / "config.toml"
    arq.write_text(
        f'[caminhos]\ndados_locais = "{(tmp_path / "l").as_posix()}"\nsnapshots = "{(tmp_path / "s").as_posix()}"\n'
        f'backups = "{(tmp_path / "b").as_posix()}"\n[api]\nbase = "https://exemplo.invalid/api"\npausa_segundos = 0\n'
        'timeout_segundos = 5\ntentativas = 1\nespera_base_segundos = 0\nuser_agent = "teste"\n'
        '[escopo]\nentidades = [998]\nexercicios = [2026]\n', encoding="utf-8")
    cfg = carregar(arq)
    con, a = banco.abrir(cfg), Armazem(cfg.snapshots)
    s1 = _snap(con, a, "2026-09-29T20:00:00-03:00", _listagem([_registro(aproc=10)]))
    s2 = _snap(con, a, "2026-10-03T20:00:00-03:00", _listagem([_registro(aproc=10)]))
    nid, _ = normalizar.normalizar(con)
    derivar.derivar(con, nid)
    con.close()
    args = ["--config", str(arq), "comparar", "--a", s1["snapshot_uid"], "--b", s2["snapshot_uid"], "--saida"]
    existente = tmp_path / "comparacao.json"
    existente.write_text("existente", encoding="utf-8")
    assert cli.main(args + [str(existente)]) == 4
    assert existente.read_text(encoding="utf-8") == "existente"
    nova = tmp_path / "nova.json"
    assert cli.main(args + [str(nova)]) == 0
    assert json.loads(nova.read_text(encoding="utf-8"))["contagens"]["comuns"] == 1


def test_saida_em_cp1252_nao_derruba_a_linha_de_comando(tmp_path):
    """`processar` imprime "continuidade fechamento->abertura" com a seta U+2192, que o cp1252 nao tem.
    Com a saida em cp1252 (redirecionamento para arquivo no Windows), o comando tem de terminar com 0."""
    import os
    import subprocess
    import sys
    from pathlib import Path
    arq = tmp_path / "config.toml"
    arq.write_text(
        f'[caminhos]\ndados_locais = "{(tmp_path / "l").as_posix()}"\nsnapshots = "{(tmp_path / "s").as_posix()}"\n'
        f'backups = "{(tmp_path / "b").as_posix()}"\n[api]\nbase = "https://exemplo.invalid/api"\npausa_segundos = 0\n'
        'timeout_segundos = 5\ntentativas = 1\nespera_base_segundos = 0\nuser_agent = "teste"\n'
        '[escopo]\nentidades = [998]\nexercicios = [2025, 2026]\n', encoding="utf-8")
    cfg = carregar(arq)
    con, a = banco.abrir(cfg), Armazem(cfg.snapshots)
    for ex in (2025, 2026):   # fechamento de 2025 e abertura de 2026: gera a verificacao de continuidade
        params = {"entidade": 998, "exercicio": ex, "dataInicial": f"{ex}-01-01", "dataFinal": f"{ex}-12-31", "size": 2000}
        quando = f"2026-09-30T1{ex - 2024}:00:00-03:00"   # 2025 -> 11h, 2026 -> 12h
        _snap(con, a, quando, _listagem([_registro(anoempenho=2024, aproc=10)]), params=params)
    con.close()
    env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONUTF8="0")
    r = subprocess.run([sys.executable, "-m", "rp", "--config", str(arq), "processar"], cwd=Path(cli.__file__).parents[1],
                       env=env, capture_output=True)
    assert r.returncode == 0, r.stderr.decode("cp1252", "replace")[-500:]
    assert b"continuidade fechamento\\u2192abertura" in r.stdout
