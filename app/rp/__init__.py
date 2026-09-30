"""Restos a Pagar de Ponta Grossa - coletor e pipeline (codigo de producao)."""
import hashlib
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

VERSAO = "0.4.0"

# Brasil sem horario de verao desde 2019: deslocamento fixo evita depender de tzdata no Windows.
BRT = timezone(timedelta(hours=-3), "BRT")

_HEX64 = re.compile(r"[0-9a-f]{64}")


def agora():
    return datetime.now(BRT).isoformat(timespec="seconds")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def sha256_valido(h):
    """True se `h` e um SHA-256 em hexadecimal minusculo (64 caracteres), e nada alem disso."""
    return isinstance(h, str) and _HEX64.fullmatch(h) is not None


def hash_do_codigo():
    """Hash dos fontes do pacote: fixa o que a versao do coletor quer dizer."""
    h = hashlib.sha256()
    for p in sorted(Path(__file__).parent.glob("*.py")) + [Path(__file__).parent / "esquema.sql"]:
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()
