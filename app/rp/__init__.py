"""Restos a Pagar of Ponta Grossa - collector and pipeline (production code)."""
import hashlib
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

VERSAO = "0.4.0"

# Brazil has had no daylight saving time since 2019: a fixed offset avoids depending on tzdata on Windows.
BRT = timezone(timedelta(hours=-3), "BRT")

_HEX64 = re.compile(r"[0-9a-f]{64}")


def agora():
    return datetime.now(BRT).isoformat(timespec="seconds")


class DataInvalida(ValueError):
    pass


def instante(em):
    """'YYYY-MM-DD' (end of day) or ISO date/time -> ISO with the Brasilia offset, in the format of coleta.coletada_em.
    The 'as it was on' validity is compared with coletada_em AS TEXT (derivation and panel layer), so every instant
    goes through here: same instant = same text (audit CLI-01)."""
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
    """True if `h` is a lowercase hexadecimal SHA-256 (64 characters), and nothing else."""
    return isinstance(h, str) and _HEX64.fullmatch(h) is not None


def hash_do_codigo():
    """Hash of the package sources: pins down what the collector version means."""
    h = hashlib.sha256()
    for p in sorted(Path(__file__).parent.glob("*.py")) + [Path(__file__).parent / "esquema.sql"]:
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()
