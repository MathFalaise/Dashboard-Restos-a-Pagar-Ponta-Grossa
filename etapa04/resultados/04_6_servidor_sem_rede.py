"""Sobe a interface com TODA conexao de saida bloqueada (equivalente a internet desligada), para o teste da 04.6.

Uso (dentro de app/):  python ../etapa04/resultados/04_6_servidor_sem_rede.py BANCO PORTA REGISTRO.jsonl

Antes de importar o programa, troca socket.connect e socket.getaddrinfo por versoes que so aceitam 127.0.0.1/::1/
localhost. Toda tentativa de sair da maquina falha e fica gravada em REGISTRO.jsonl (uma linha por tentativa).
Tambem aponta os proxies do ambiente para um endereco morto. Nao altera nenhuma configuracao do sistema.
"""
import json
import os
import socket
import sys
from pathlib import Path

banco, porta, registro = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])
LOCAIS = ("127.0.0.1", "::1", "localhost")
for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ[var] = "http://127.0.0.1:9"


def _anotar(alvo):
    with registro.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"tentativa": str(alvo)}) + "\n")


_conectar, _resolver = socket.socket.connect, socket.getaddrinfo


def conectar(self, endereco):
    host = endereco[0] if isinstance(endereco, tuple) else str(endereco)
    if host not in LOCAIS:
        _anotar(endereco)
        raise OSError(f"rede bloqueada: {endereco}")
    return _conectar(self, endereco)


def resolver(host, *a, **k):
    if host not in LOCAIS:
        _anotar(host)
        raise socket.gaierror(f"resolucao bloqueada: {host}")
    return _resolver(host, *a, **k)


socket.socket.connect, socket.getaddrinfo = conectar, resolver
registro.write_text("", encoding="utf-8")
sys.path.insert(0, str(Path.cwd()))
from rp.cli import main  # noqa: E402

sys.exit(main(["interface", "--banco", banco, "--porta", str(porta)]))
