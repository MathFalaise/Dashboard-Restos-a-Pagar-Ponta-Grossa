"""WSGI application of the public interface (read-only).

Flow: browser -> this application -> rp.painel.Painel (database opened read-only) -> HTML page.
  * Never calls the Elotech API or any other service: it imports no HTTP client and opens no outgoing connection.
    The only network is the local server itself; the interface works with the internet off. Links to the official
    portal ("where to check") are plain hrefs: the browser follows them, the server never does.
  * Only GET and HEAD. A filter only chooses what to read; each request opens the database read-only (SQLite
    refuses writes: URI mode=ro + PRAGMA query_only).
  * Always the public level: no parameter shows a creditor's name, code or document in a list.
  * HTML without JavaScript and without external resources (no font, no CDN), with security headers: strict CSP,
    nosniff, no-referrer, no framing.
  * WSGI (PEP 3333): locally it runs on wsgiref (standard library); a future deployment can use any WSGI server
    without changing the code.
"""
import logging
import re
import socketserver
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer

from ..painel import Painel
from ..painel.consulta import ErroDoPainel, EsquemaAntigo, SemProcessamento
from . import paginas

log = logging.getLogger("rp.interface")

LIMITE_CONSULTA = 2048          # maximum query string size
ESTILO = Path(__file__).with_name("estilo.css").read_bytes()
CABECALHOS = [
    ("Content-Security-Policy", "default-src 'none'; style-src 'self'; form-action 'self'; base-uri 'none'; "
                                "frame-ancestors 'none'"),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("X-Frame-Options", "DENY"),
    ("Cache-Control", "no-store"),
]
ROTAS = {
    "/": paginas.resumo, "/evolucao": paginas.evolucao, "/historico": paginas.historico, "/composicao": paginas.composicao, "/variacao": paginas.variacao, "/empenho/cortes": paginas.empenho_cortes, "/qualidade": paginas.qualidade, "/entidades": paginas.entidades, "/empenhos": paginas.empenhos, "/empenho": paginas.empenho,
    "/retratos": paginas.retratos, "/comparar": paginas.comparar, "/reconciliacao": paginas.reconciliacao,
    "/pares": paginas.pares, "/metodologia": paginas.metodologia,
}
_UID = re.compile(r"[0-9a-f]{32}")


class ParametroInvalido(ValueError):
    pass


class Parametros:
    """Query string parameters, validated one by one: an invalid value becomes a 400 error, never a guessed value.
    An empty field counts as absent."""

    def __init__(self, consulta):
        if len(consulta) > LIMITE_CONSULTA:
            raise ParametroInvalido("consulta longa demais")
        try:
            self._d = parse_qs(consulta, max_num_fields=40)
        except ValueError as e:
            raise ParametroInvalido("parametros demais na consulta") from e

    def _um(self, nome):
        v = self._d.get(nome)
        v = v[-1].strip() if v else ""
        return v or None

    def texto(self, nome, maximo):
        v = self._um(nome)
        if v is not None and (len(v) > maximo or any(ord(c) < 32 for c in v)):
            raise ParametroInvalido(f"{nome}: texto invalido")
        return v

    def inteiro(self, nome, minimo, maximo):
        v = self._um(nome)
        if v is None:
            return None
        if not re.fullmatch(r"\d{1,10}", v) or not minimo <= int(v) <= maximo:
            raise ParametroInvalido(f"{nome}: informe um inteiro entre {minimo} e {maximo}")
        return int(v)

    def data(self, nome):
        v = self._um(nome)
        if v is None:
            return None
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
                raise ValueError
            date.fromisoformat(v)
        except ValueError:
            raise ParametroInvalido(f"{nome}: informe a data como AAAA-MM-DD") from None
        return v

    def escolha(self, nome, opcoes):
        v = self._um(nome)
        if v is not None and v not in opcoes:
            raise ParametroInvalido(f"{nome}: valor fora da lista")
        return v

    def marcado(self, nome):
        return self._um(nome) in ("1", "sim", "on")

    def snapshot(self, nome):
        v = self._um(nome)
        if v is not None and not _UID.fullmatch(v):
            raise ParametroInvalido(f"{nome}: identificador de snapshot invalido")
        return v


class Aplicacao:
    """WSGI application. `caminho_banco` is opened read-only, one connection per request."""

    def __init__(self, caminho_banco):
        self.caminho = Path(caminho_banco)
        with Painel.abrir(self.caminho):   # fail early: missing database or old schema
            pass

    def __call__(self, environ, start_response):
        metodo = environ.get("REQUEST_METHOD", "GET").upper()
        caminho = environ.get("PATH_INFO") or "/"
        if metodo not in ("GET", "HEAD"):
            return self._pagina(start_response, metodo, "405 Method Not Allowed", "Método não permitido",
                                "A interface é somente leitura: só aceita GET e HEAD.", [("Allow", "GET, HEAD")])
        if caminho == "/estilo.css":
            return self._responder(start_response, metodo, "200 OK", "text/css; charset=utf-8", ESTILO)
        rota = ROTAS.get(caminho)
        if rota is None:
            return self._pagina(start_response, metodo, "404 Not Found", "Página não encontrada",
                                "Endereço desconhecido. Use o menu.")
        try:
            q = Parametros(environ.get("QUERY_STRING", ""))
            with Painel.abrir(self.caminho) as p:
                titulo, corpo = rota(p, q)
                html = paginas.documento(titulo, corpo, p.contexto(), caminho)
        except ParametroInvalido as e:
            return self._pagina(start_response, metodo, "400 Bad Request", "Consulta inválida", str(e))
        except (SemProcessamento, EsquemaAntigo) as e:
            return self._pagina(start_response, metodo, "503 Service Unavailable", "Base não processada", str(e))
        except ErroDoPainel as e:
            return self._pagina(start_response, metodo, "400 Bad Request", "Consulta recusada", str(e))
        except Exception:   # details only in the log; the response exposes neither path nor stack
            log.exception("erro ao montar %s", caminho)
            return self._pagina(start_response, metodo, "500 Internal Server Error", "Erro interno",
                                "Não foi possível montar a página. O detalhe ficou no log.")
        return self._responder(start_response, metodo, "200 OK", "text/html; charset=utf-8", html.encode("utf-8"))

    def _pagina(self, start_response, metodo, status, titulo, mensagem, extra=()):
        corpo = (f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
                 '<meta name="viewport" content="width=device-width, initial-scale=1">'
                 f'<title>{paginas.esc(titulo)}</title>'
                 f'<link rel="stylesheet" href="/estilo.css"></head><body><main><h1>{paginas.esc(titulo)}</h1>'
                 f'<p class="aviso">{paginas.esc(mensagem)}</p><p><a href="/">Voltar ao resumo</a></p></main></body></html>')
        return self._responder(start_response, metodo, status, "text/html; charset=utf-8", corpo.encode("utf-8"), extra)

    @staticmethod
    def _responder(start_response, metodo, status, tipo, corpo, extra=()):
        start_response(status, [("Content-Type", tipo), ("Content-Length", str(len(corpo))), *CABECALHOS, *extra])
        return [b"" if metodo == "HEAD" else corpo]


class _Servidor(WSGIServer):
    """WSGIServer without socket.getfqdn on bind: no name resolution, not even local."""

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]
        self.setup_environ()


class _Manipulador(WSGIRequestHandler):
    def log_message(self, formato, *args):   # goes to the program log, not straight to the terminal
        log.info("%s %s", self.address_string(), formato % args)


def criar_servidor(caminho_banco, host="127.0.0.1", porta=8050):
    servidor = _Servidor((host, porta), _Manipulador)
    servidor.set_app(Aplicacao(caminho_banco))
    return servidor


def servir(caminho_banco, host="127.0.0.1", porta=8050):
    """Local development/query server (one request at a time). Ctrl+C stops it."""
    servidor = criar_servidor(caminho_banco, host, porta)
    if host not in ("127.0.0.1", "localhost", "::1"):
        print(f"ATENCAO: a interface ficara acessivel pela rede em {host}. Ela e somente leitura, mas nao tem "
              "autenticacao nem limite de acesso.")
    print(f"Interface em http://{host}:{servidor.server_port}/ (somente leitura; Ctrl+C para parar)", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
