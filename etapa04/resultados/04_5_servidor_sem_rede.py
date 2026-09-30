"""Sobe a interface (python -m rp interface) num processo em que toda conexao ou resolucao de nome para fora
desta maquina e recusada e anotada em tentativas_de_rede.txt. Simula o computador sem internet."""
import socket
import sys
from pathlib import Path

sys.path.insert(0, "C:/Users/maped/OneDrive/Área de Trabalho/Projeto Dashboard Restos a Pagar/app")
REGISTRO = Path(__file__).with_name("tentativas_de_rede.txt")
REGISTRO.write_text("", encoding="utf-8")
LOCAIS = ("127.0.0.1", "::1", "localhost")
_conectar, _conectar_ex, _resolver = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo


def _anotar(alvo):
    with REGISTRO.open("a", encoding="utf-8") as f:
        f.write(f"{alvo}\n")


def conectar(self, endereco):
    host = endereco[0] if isinstance(endereco, tuple) else str(endereco)
    if host not in LOCAIS:
        _anotar(endereco)
        raise OSError(f"sem internet (simulado): {endereco}")
    return _conectar(self, endereco)


def conectar_ex(self, endereco):
    host = endereco[0] if isinstance(endereco, tuple) else str(endereco)
    if host not in LOCAIS:
        _anotar(endereco)
        return 101
    return _conectar_ex(self, endereco)


def resolver(host, *a, **k):
    if host not in LOCAIS:
        _anotar(host)
        raise socket.gaierror(f"sem internet (simulado): {host}")
    return _resolver(host, *a, **k)


socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo = conectar, conectar_ex, resolver
from rp.cli import main  # noqa: E402
sys.exit(main(["interface", "--porta", "8051"]))
