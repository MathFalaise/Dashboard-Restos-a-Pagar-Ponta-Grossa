"""Cliente HTTP do coletor: pausa minima, tempo limite e novas tentativas so quando faz sentido.

Regras:
  * intervalo minimo `pausa` entre duas requisicoes (cortesia com o portal);
  * repete em 5xx, 429 e erro de rede, com espera crescente (respeita Retry-After, com teto);
  * NUNCA repete 4xx (exceto 429): o pedido esta errado e repetir nao muda nada;
  * devolve sempre a ultima resposta; quem decide o que e sucesso e o coletor.

Seguranca:
  * TLS sempre verificado (a URL base e validada como https em config.py);
  * redirecionamento NAO e seguido: um 3xx volta como resposta e o coletor o registra como falha,
    em vez de buscar dados em outro endereco sem que ninguem perceba;
  * corpo lido em blocos, com teto de bytes (`limite_resposta_bytes`) e prazo total de leitura;
    resposta recusada por esses limites nao e repetida (a mesma consulta daria o mesmo resultado);
  * o caminho da consulta so aceita segmentos simples: nada de outro host, "..", query ou fragmento.
"""
import logging
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlencode

from . import agora

log = logging.getLogger("rp.http")

ESPERA_MAXIMA = 300              # teto (s) para o Retry-After informado pelo servidor
BLOCO = 64 * 1024                # tamanho de cada leitura do corpo
FATOR_PRAZO_TOTAL = 3            # prazo total de leitura = timeout x este fator
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
    """Todas as tentativas falharam sem nenhuma resposta HTTP utilizavel."""


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


def transporte_requests(user_agent, limite_bytes, prazo_total):
    import requests
    sessao = requests.Session()
    sessao.headers["User-Agent"] = user_agent

    def get(url, timeout):
        inicio = time.monotonic()
        with sessao.get(url, timeout=timeout, stream=True, allow_redirects=False, verify=True) as r:
            declarado = r.headers.get("Content-Length", "")
            if declarado.isdigit() and int(declarado) > limite_bytes:
                raise RespostaRecusada(f"Content-Length {declarado} maior que {limite_bytes} bytes")
            corpo = ler_limitado(r.iter_content(BLOCO), limite_bytes, inicio + prazo_total)
            return r.status_code, dict(r.headers), corpo
    return get


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
                                                             cfg.timeout * FATOR_PRAZO_TOTAL)
        self.dormir = dormir
        self.monotonic = monotonic
        self._estado = _Estado()
        self.requisicoes = 0

    def url(self, caminho, params=None):
        return f"{self.cfg.api_base}{validar_caminho(caminho)}" + (f"?{urlencode(params)}" if params else "")

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
            except Exception as e:  # rede, tempo esgotado, DNS...
                status, cab, corpo, erro = None, {}, b"", e
            finally:
                self._estado.ultima = self.monotonic()
            repetir = erro is not None or status == 429 or (status is not None and status >= 500)
            if not repetir or tentativa == self.cfg.tentativas:
                break
            espera = self.cfg.espera_base * 2 ** (tentativa - 1)
            ra = (cab or {}).get("Retry-After")
            if ra and str(ra).isdigit():
                espera = max(espera, min(int(ra), ESPERA_MAXIMA))
            log.warning("tentativa %d falhou (%s) em %s; nova tentativa em %.0fs", tentativa, erro or status, url, espera)
            self.dormir(espera)
        if erro is not None:
            raise ErroDeRede(f"{url}: {erro!r} após {self.cfg.tentativas} tentativas")
        return Resposta(url, status, cab, corpo, agora(), tentativa)
