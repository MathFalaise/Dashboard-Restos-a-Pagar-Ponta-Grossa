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


class DataInvalida(ValueError):
    pass


def instante(em):
    """'AAAA-MM-DD' (fim do dia) ou data/hora ISO -> ISO com fuso de Brasilia, no formato de coleta.coletada_em.
    A vigencia 'como estava em' e comparada com coletada_em COMO TEXTO (derivacao e camada painel), por isso todo
    instante passa por aqui: mesmo instante = mesmo texto (auditoria CLI-01)."""
    if em is None:
        return None
    try:
        d = datetime.fromisoformat(str(em))
    except ValueError as e:
        raise DataInvalida(f"data invalida para 'como estava em': {em!r} (use AAAA-MM-DD ou ISO com fuso)") from e
    if len(str(em)) == 10:
        d = d.replace(hour=23, minute=59, second=59, tzinfo=BRT)
    d = d.replace(tzinfo=BRT) if d.tzinfo is None else d.astimezone(BRT)
    return d.isoformat(timespec="seconds")


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
