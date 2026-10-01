"""Aplicacao WSGI da interface publica (somente leitura).

Fluxo: navegador -> esta aplicacao -> rp.painel.Painel (banco aberto em modo somente leitura) -> pagina HTML.
  * Nunca chama a API da Elotech nem outro servico: nao importa cliente HTTP e nao abre conexao de saida. A unica
    rede e a do proprio servidor local; a interface funciona com a internet desligada.
  * So GET e HEAD. Filtro so escolhe o que ler; cada requisicao abre o banco em modo somente leitura (a escrita e
    recusada pelo SQLite: URI mode=ro + PRAGMA query_only).
  * Sempre nivel publico: nao ha parametro que mostre nome, codigo ou documento de credor em lista.
  * HTML sem JavaScript e sem recurso externo (nem fonte, nem CDN), com cabecalhos de seguranca: CSP restritiva,
    nosniff, no-referrer, sem enquadramento.
  * WSGI (PEP 3333): localmente roda com wsgiref (biblioteca padrao); numa publicacao futura, com qualquer
    servidor WSGI, sem mudar o codigo.
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

LIMITE_CONSULTA = 2048          # tamanho maximo da query string
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
    "/": paginas.resumo, "/evolucao": paginas.evolucao, "/historico": paginas.historico, "/entidades": paginas.entidades, "/empenhos": paginas.empenhos, "/empenho": paginas.empenho,
    "/retratos": paginas.retratos, "/comparar": paginas.comparar, "/reconciliacao": paginas.reconciliacao,
    "/pares": paginas.pares, "/metodologia": paginas.metodologia,
}
_UID = re.compile(r"[0-9a-f]{32}")


class ParametroInvalido(ValueError):
    pass


class Parametros:
    """Parametros da query string, validados um a um: valor invalido vira erro 400, nunca um valor adivinhado.
    Campo vazio conta como ausente."""

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
    """Aplicacao WSGI. `caminho_banco` e aberto so para leitura, uma conexao por requisicao."""

    def __init__(self, caminho_banco):
        self.caminho = Path(caminho_banco)
        with Painel.abrir(self.caminho):   # falha cedo: banco ausente ou esquema antigo
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
        except Exception:   # detalhe so no log; a resposta nao expoe caminho nem pilha
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
    """WSGIServer sem socket.getfqdn no bind: nenhuma resolucao de nome, nem local."""

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]
        self.setup_environ()


class _Manipulador(WSGIRequestHandler):
    def log_message(self, formato, *args):   # vai para o log do programa, nao direto para o terminal
        log.info("%s %s", self.address_string(), formato % args)


def criar_servidor(caminho_banco, host="127.0.0.1", porta=8050):
    servidor = _Servidor((host, porta), _Manipulador)
    servidor.set_app(Aplicacao(caminho_banco))
    return servidor


def servir(caminho_banco, host="127.0.0.1", porta=8050):
    """Servidor local de desenvolvimento/consulta (um pedido por vez). Ctrl+C encerra."""
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
