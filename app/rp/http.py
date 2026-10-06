"""The collector's HTTP client: minimum pause, timeouts and retries only when they make sense.

Rules:
  * minimum interval `pausa` between two requests (courtesy to the portal);
  * retries on 5xx, 429 and TRANSIENT network failures (timeout, connection refused or interrupted), with a growing
    wait (honors Retry-After in seconds or as an HTTP date, with a ceiling);
  * NEVER retries 4xx (except 429): the request is wrong and repeating changes nothing;
  * NEVER retries a TLS (certificate) error or an invalid URL: they become ErroDeRede at once;
  * any other transport exception (e.g. TypeError) is a program bug: it propagates, it never becomes "network";
  * always returns the last response; the collector decides what counts as success.

Security:
  * TLS always verified (the base URL is validated as https in config.py);
  * redirects are NOT followed: a 3xx comes back as a response and the collector records it as a failure, instead
    of fetching data from another address without anyone noticing;
  * the body is read in blocks, with a byte ceiling (`limite_resposta_bytes`) and a total read deadline; a response
    rejected by these limits is not retried (the same query would give the same result);
  * the query path only accepts simple segments: no other host, "..", query or fragment.

Three time limits, each with its own job (critical review, item 8):
  * connection (`timeout_conexao`, default 30 s): establishing the TCP/TLS connection;
  * read (`timeout`): the longest silence accepted between two received chunks;
  * TOTAL deadline (timeout x FATOR_PRAZO_TOTAL): an absolute barrier for the whole request, connection + headers +
    body. The read timeout alone does not guarantee it: a server that sends 1 byte every few seconds never lets the
    read time out, and a 64 KiB block only completes when it fills. So the request runs in a worker thread and the
    caller gives up at the deadline, dropping the connection; the late result is discarded.

Wait between attempts: base x 2^(attempt-1), or the Retry-After (seconds or HTTP date) if larger, capped at
ESPERA_MAXIMA. No jitter: the collector is a single sequential client with a minimum pause between requests;
jitter spreads many clients that failed together, and here it would only make the tests non-deterministic.
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

ESPERA_MAXIMA = 300              # ceiling (s) for the Retry-After sent by the server
BLOCO = 64 * 1024                # size of each body read
FATOR_PRAZO_TOTAL = 3            # total request deadline = timeout x this factor
TIMEOUT_CONEXAO = 30             # default (s) to establish the connection; never larger than the read timeout
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
    """No usable HTTP response: attempts exhausted, or a failure that retrying does not fix (TLS, invalid URL)."""


class FalhaTransitoria(Exception):
    """A network failure that may go away by itself (timeout, connection refused or interrupted). Only this is retried.
    The transport translates the HTTP library's exceptions into this one; native TimeoutError and ConnectionError count too."""


TRANSITORIAS = (FalhaTransitoria, TimeoutError, ConnectionError)


class RespostaRecusada(Exception):
    """Response discarded by a safety limit (size or total deadline). It is not retried."""


@dataclass
class _Estado:
    ultima: float = field(default=None)


def ler_limitado(blocos, limite, prazo, monotonic=time.monotonic):
    """Joins `blocos`, refusing a body larger than `limite` bytes or a read that ends after `prazo`
    (a `monotonic` instant)."""
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
    """Socket under a requests/urllib3 response, or None. Two paths: the urllib3 connection (HTTP/1.1 with
    keep-alive) and the http.client file (when the server closes the connection, it hands the socket to the response)."""
    raw = getattr(resposta, "raw", None)
    sock = getattr(getattr(raw, "_connection", None), "sock", None)
    if sock is None:
        sock = getattr(getattr(getattr(getattr(raw, "_fp", None), "fp", None), "raw", None), "_sock", None)
    return sock if isinstance(sock, socket.socket) else None


def _derrubar(resposta):
    """Drops the connection of an ongoing response (total deadline expired): `shutdown` makes the blocked read in the
    worker thread return with an error instead of staying stuck on the server. Only the shutdown: `close()` from here
    would wait for the buffer lock that the blocked read itself holds. Best effort: with no response yet (stuck on
    the connection or the headers), the thread ends by the read timeout; its result is discarded either way."""
    sock = _socket_da_resposta(resposta) if resposta is not None else None
    if sock is not None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


def com_prazo_total(funcao, prazo, ao_vencer=None):
    """Runs `funcao(estado)` in a worker thread and waits at most `prazo` seconds. When the deadline expires, calls
    `ao_vencer(estado)` and raises RespostaRecusada (not retried: the same query would give the same result). An
    exception raised by the function is passed to the caller with its original type."""
    estado, feito = {}, threading.Event()

    def trabalho():
        try:
            estado["resultado"] = funcao(estado)
        except BaseException as e:        # noqa: BLE001 - passed intact to the caller's thread
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
                # body already decompressed by requests (the API answers gzip, chunked, no Content-Length): the ceiling applies
                # to the decompressed bytes, which are the ones written to the store
                corpo = ler_limitado(r.iter_content(BLOCO), limite_bytes, inicio + prazo_total)
                return r.status_code, dict(r.headers), corpo
        except rx.SSLError as e:            # certificate/TLS: retrying does not fix it and must not be bypassed
            raise ErroDeRede(f"falha de TLS: {e}") from e
        except (rx.InvalidURL, rx.InvalidSchema, rx.MissingSchema, rx.InvalidHeader) as e:
            raise ErroDeRede(f"pedido invalido: {type(e).__name__}: {e}") from e
        except (rx.Timeout, rx.ConnectionError, rx.ChunkedEncodingError, rx.ContentDecodingError) as e:
            if estado.get("vencido"):      # connection dropped by the total deadline: the caller already got the refusal
                raise RespostaRecusada("prazo total excedido") from e
            raise FalhaTransitoria(f"{type(e).__name__}: {e}") from e

    def get(url, timeout):
        inicio = time.monotonic()
        return com_prazo_total(lambda estado: _get(url, timeout, inicio, estado), prazo_total,
                               lambda estado: _derrubar(estado.get("resposta")))
    return get


def espera_retry_after(valor, agora_utc=None):
    """Seconds requested by the server in Retry-After (integer or HTTP date), or None if absent/unreadable."""
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
    """Path relative to the API: '/seg/seg/...', each segment only with letters, digits, '_', '.' and '-'."""
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
        """Query URL. A parameter with a list (e.g. sort on two fields) becomes a repeated parameter (doseq); a simple
        value comes out as before."""
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
            except RespostaRecusada as e:   # safety limit: retrying would give the same result
                raise ErroDeRede(f"{url}: resposta recusada: {e}") from e
            except TRANSITORIAS as e:       # only network failures are retried; ErroDeRede and program bugs propagate
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
