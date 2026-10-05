"""Cliente HTTP do coletor: pausa minima, tempo limite e novas tentativas so quando faz sentido.

Regras:
  * intervalo minimo `pausa` entre duas requisicoes (cortesia com o portal);
  * repete em 5xx, 429 e falha TRANSITORIA de rede (tempo esgotado, conexao recusada ou interrompida), com espera
    crescente (respeita Retry-After em segundos ou em data HTTP, com teto);
  * NUNCA repete 4xx (exceto 429): o pedido esta errado e repetir nao muda nada;
  * NUNCA repete erro de TLS (certificado) nem URL invalida: viram ErroDeRede na hora;
  * qualquer outra excecao do transporte (ex.: TypeError) e defeito de programa: propaga, nunca vira "rede";
  * devolve sempre a ultima resposta; quem decide o que e sucesso e o coletor.

Seguranca:
  * TLS sempre verificado (a URL base e validada como https em config.py);
  * redirecionamento NAO e seguido: um 3xx volta como resposta e o coletor o registra como falha,
    em vez de buscar dados em outro endereco sem que ninguem perceba;
  * corpo lido em blocos, com teto de bytes (`limite_resposta_bytes`) e prazo total de leitura;
    resposta recusada por esses limites nao e repetida (a mesma consulta daria o mesmo resultado);
  * o caminho da consulta so aceita segmentos simples: nada de outro host, "..", query ou fragmento.

Tres prazos, cada um com uma funcao (revisao critica, item 8):
  * conexao (`timeout_conexao`, padrao 30 s): estabelecer a conexao TCP/TLS;
  * leitura (`timeout`): o maior silencio aceito entre dois pedacos recebidos;
  * prazo TOTAL (timeout x FATOR_PRAZO_TOTAL): barreira absoluta da requisicao inteira, conexao + cabecalhos +
    corpo. O prazo de leitura sozinho nao a garante: um servidor que mande 1 byte a cada poucos segundos nunca
    deixa a leitura esgotar, e um bloco de 64 KiB so termina quando enche. Por isso a requisicao roda numa thread
    de trabalho e quem chamou desiste no prazo, derrubando a conexao; o resultado tardio e descartado.

Espera entre tentativas: base x 2^(tentativa-1), ou o Retry-After (segundos ou data HTTP) se for maior, com teto
ESPERA_MAXIMA. Sem sorteio (jitter): o coletor e um unico cliente sequencial, com pausa minima entre requisicoes;
jitter serve para espalhar muitos clientes que falharam juntos, e aqui so tiraria o determinismo dos testes.
"""
import logging
import re
import socket
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode

from . import agora

log = logging.getLogger("rp.http")

ESPERA_MAXIMA = 300              # teto (s) para o Retry-After informado pelo servidor
BLOCO = 64 * 1024                # tamanho de cada leitura do corpo
FATOR_PRAZO_TOTAL = 3            # prazo total da requisicao = timeout x este fator
TIMEOUT_CONEXAO = 30             # padrao (s) para estabelecer a conexao; nunca maior que o timeout de leitura
_SEGMENTO = re.compile(r"[A-Za-z0-9_.\-]+")


@dataclass
class Resposta:
    url: str
    status: int
    cabecalhos: dict
    corpo: bytes
    recebida_em: str
    tentativas: int = 1


class ErroDeRede(Exception):
    """Nenhuma resposta HTTP utilizavel: tentativas esgotadas, ou falha que repetir nao resolve (TLS, URL invalida)."""


class FalhaTransitoria(Exception):
    """Falha de rede que pode passar sozinha (tempo esgotado, conexao recusada ou interrompida). So ela e repetida.
    O transporte traduz as excecoes da biblioteca HTTP para esta; TimeoutError e ConnectionError nativos contam igual."""


TRANSITORIAS = (FalhaTransitoria, TimeoutError, ConnectionError)


class RespostaRecusada(Exception):
    """Resposta descartada por limite de seguranca (tamanho ou prazo total). Nao e repetida."""


@dataclass
class _Estado:
    ultima: float = field(default=None)


def ler_limitado(blocos, limite, prazo, monotonic=time.monotonic):
    """Junta `blocos` recusando corpo maior que `limite` bytes ou leitura que termine depois de `prazo`
    (instante de `monotonic`)."""
    partes, total = [], 0
    for b in blocos:
        total += len(b)
        if total > limite:
            raise RespostaRecusada(f"corpo maior que {limite} bytes")
        if monotonic() > prazo:
            raise RespostaRecusada("prazo total de leitura excedido")
        partes.append(b)
    return b"".join(partes)


def _socket_da_resposta(resposta):
    """Socket por baixo de uma resposta do requests/urllib3, ou None. Dois caminhos: a conexao do urllib3 (HTTP/1.1
    com keep-alive) e o arquivo do http.client (quando o servidor fecha a conexao, ela passa o socket a resposta)."""
    raw = getattr(resposta, "raw", None)
    sock = getattr(getattr(raw, "_connection", None), "sock", None)
    if sock is None:
        sock = getattr(getattr(getattr(getattr(raw, "_fp", None), "fp", None), "raw", None), "_sock", None)
    return sock if isinstance(sock, socket.socket) else None


def _derrubar(resposta):
    """Derruba a conexao de uma resposta em andamento (prazo total vencido): `shutdown` faz a leitura bloqueada na
    thread de trabalho voltar com erro em vez de continuar presa ao servidor. So o shutdown: `close()` daqui
    esperaria a trava do buffer que a propria leitura bloqueada segura. Melhor esforco: sem resposta ainda (presa na
    conexao ou nos cabecalhos), a thread termina pelo prazo de leitura; o resultado dela e descartado de todo jeito."""
    sock = _socket_da_resposta(resposta) if resposta is not None else None
    if sock is not None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


def com_prazo_total(funcao, prazo, ao_vencer=None):
    """Executa `funcao(estado)` numa thread de trabalho e espera no maximo `prazo` segundos. Vencido o prazo, chama
    `ao_vencer(estado)` e levanta RespostaRecusada (nao repetida: a mesma consulta daria o mesmo resultado). A
    excecao levantada pela funcao e repassada a quem chamou, com o tipo original."""
    estado, feito = {}, threading.Event()

    def trabalho():
        try:
            estado["resultado"] = funcao(estado)
        except BaseException as e:        # noqa: BLE001 - repassada intacta a thread de quem chamou
            estado["erro"] = e
        finally:
            feito.set()

    threading.Thread(target=trabalho, name="rp-http", daemon=True).start()
    if not feito.wait(prazo):
        estado["vencido"] = True
        if ao_vencer:
            ao_vencer(estado)
        raise RespostaRecusada(f"prazo total de {prazo:g} s excedido")
    if "erro" in estado:
        raise estado["erro"]
    return estado["resultado"]


def transporte_requests(user_agent, limite_bytes, prazo_total, timeout_conexao=TIMEOUT_CONEXAO):
    import requests
    sessao = requests.Session()
    sessao.headers["User-Agent"] = user_agent

    from requests import exceptions as rx

    def _get(url, timeout, inicio, estado):
        try:
            with sessao.get(url, timeout=(min(timeout_conexao, timeout), timeout), stream=True, allow_redirects=False,
                            verify=True) as r:
                estado["resposta"] = r
                declarado = r.headers.get("Content-Length", "")
                if declarado.isdigit() and int(declarado) > limite_bytes:
                    raise RespostaRecusada(f"Content-Length {declarado} maior que {limite_bytes} bytes")
                # corpo ja descomprimido pelo requests (a API responde gzip, chunked, sem Content-Length): o teto vale
                # para os bytes descomprimidos, que sao os gravados no armazem
                corpo = ler_limitado(r.iter_content(BLOCO), limite_bytes, inicio + prazo_total)
                return r.status_code, dict(r.headers), corpo
        except rx.SSLError as e:            # certificado/TLS: repetir nao resolve e nao deve ser contornado
            raise ErroDeRede(f"falha de TLS: {e}") from e
        except (rx.InvalidURL, rx.InvalidSchema, rx.MissingSchema, rx.InvalidHeader) as e:
            raise ErroDeRede(f"pedido invalido: {type(e).__name__}: {e}") from e
        except (rx.Timeout, rx.ConnectionError, rx.ChunkedEncodingError, rx.ContentDecodingError) as e:
            if estado.get("vencido"):      # conexao derrubada pelo prazo total: quem chamou ja recebeu a recusa
                raise RespostaRecusada("prazo total excedido") from e
            raise FalhaTransitoria(f"{type(e).__name__}: {e}") from e

    def get(url, timeout):
        inicio = time.monotonic()
        return com_prazo_total(lambda estado: _get(url, timeout, inicio, estado), prazo_total,
                               lambda estado: _derrubar(estado.get("resposta")))
    return get


def espera_retry_after(valor, agora_utc=None):
    """Segundos pedidos pelo servidor em Retry-After (inteiro ou data HTTP), ou None se ausente/ilegivel."""
    if not valor:
        return None
    v = str(valor).strip()
    if v.isdigit():
        return int(v)
    try:
        quando = parsedate_to_datetime(v)
    except (TypeError, ValueError, IndexError):
        return None
    if quando is None or quando.tzinfo is None:
        return None
    return max(0, int((quando - (agora_utc or datetime.now(timezone.utc))).total_seconds()))


def validar_caminho(caminho):
    """Caminho relativo a API: '/seg/seg/...', cada segmento so com letras, digitos, '_', '.' e '-'."""
    if not isinstance(caminho, str) or not caminho.startswith("/") or caminho.startswith("//"):
        raise ValueError(f"caminho invalido para a API: {caminho!r}")
    for seg in caminho[1:].split("/"):
        if seg in (".", "..") or not _SEGMENTO.fullmatch(seg):
            raise ValueError(f"caminho invalido para a API: {caminho!r}")
    return caminho


class Cliente:
    def __init__(self, cfg, transporte=None, dormir=time.sleep, monotonic=time.monotonic):
        self.cfg = cfg
        self.transporte = transporte or transporte_requests(cfg.user_agent, cfg.limite_resposta_bytes,
                                                             cfg.timeout * FATOR_PRAZO_TOTAL, cfg.timeout_conexao)
        self.dormir = dormir
        self.monotonic = monotonic
        self._estado = _Estado()
        self.requisicoes = 0

    def url(self, caminho, params=None):
        """URL da consulta. Parametro com lista (ex.: sort em dois campos) vira o parametro repetido (doseq); valor
        simples sai igual a antes."""
        return f"{self.cfg.api_base}{validar_caminho(caminho)}" + (f"?{urlencode(params, doseq=True)}" if params else "")

    def _pausar(self):
        if self._estado.ultima is not None:
            falta = self.cfg.pausa - (self.monotonic() - self._estado.ultima)
            if falta > 0:
                self.dormir(falta)

    def get(self, caminho, params=None):
        url = self.url(caminho, params)
        erro = None
        for tentativa in range(1, self.cfg.tentativas + 1):
            self._pausar()
            try:
                self.requisicoes += 1
                status, cab, corpo = self.transporte(url, self.cfg.timeout)
                erro = None
            except RespostaRecusada as e:   # limite de seguranca: repetir daria o mesmo resultado
                raise ErroDeRede(f"{url}: resposta recusada: {e}") from e
            except TRANSITORIAS as e:       # so falha de rede repete; ErroDeRede e defeitos de programa propagam
                status, cab, corpo, erro = None, {}, b"", e
            finally:
                self._estado.ultima = self.monotonic()
            repetir = erro is not None or status == 429 or (status is not None and status >= 500)
            if not repetir or tentativa == self.cfg.tentativas:
                break
            espera = self.cfg.espera_base * 2 ** (tentativa - 1)
            ra = espera_retry_after((cab or {}).get("Retry-After"))
            if ra is not None:
                espera = max(espera, min(ra, ESPERA_MAXIMA))
            log.warning("tentativa %d falhou (%s) em %s; nova tentativa em %.0fs", tentativa, erro or status, url, espera)
            self.dormir(espera)
        if erro is not None:
            raise ErroDeRede(f"{url}: {erro!r} após {self.cfg.tentativas} tentativas")
        return Resposta(url, status, cab, corpo, agora(), tentativa)
