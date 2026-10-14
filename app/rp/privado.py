"""Private storage of the raw data and privacy guard of the public repository (corrective audit, 13/10/2026).

* `copiar_conferido`: copies a folder tree to a private location, file by file, WITHOUT overwriting anything. A file
  that already exists at the destination is only accepted if its bytes are identical; a different one is a conflict
  and nothing is replaced. Every copied file is read back and compared by SHA-256 before it counts as copied.
* `conferir_copia`: the same comparison, read-only (used again before removing the synced copy).
* `achados_pessoais`: patterns of personal data in a text (masked CPF in the portal's format, full CPF with valid
  check digits). Used by the guard test that keeps raw creditor data out of the public repository.
"""
import hashlib
import os
import re
import shutil
from pathlib import Path

BLOCO = 1 << 20

# Folders that hold individual creditor records (raw API responses, stage samples, SQLite copies). They live only in
# the private storage (config.toml [caminhos]); the public repository never versions them again.
CAMINHOS_PRIVADOS = ("data/snapshots", "data/stage01-samples", "data/stage02-raw", "data/backups",
                     "snapshots", "etapa01/amostras_brutas", "etapa02/dados_brutos", "backups")
# File kinds that are never versioned, wherever they are: database copies and raw store objects.
EXTENSOES_PRIVADAS = (".sqlite", ".sqlite3", ".db", ".zlib", ".sqlite.gz")

CPF_MASCARADO = re.compile(r"\*{3,4}\d{3}\*{3,4}")
CPF_COMPLETO = re.compile(r"(?<![\d.])(\d{3})\.(\d{3})\.(\d{3})-(\d{2})(?![\d.])")
# Synthetic values used by the tests and the docs. "****123****" and "***456***" are 3 digits only (they identify
# nobody on their own) and are kept because synthetic tests reproduce the portal's format with them.
SINTETICOS = frozenset({"****123****", "***456***", "****NNN****"})


class CopiaEmConflito(Exception):
    pass


def sha256_arquivo(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while b := f.read(BLOCO):
            h.update(b)
    return h.hexdigest()


def _arquivos(raiz):
    raiz = Path(raiz)
    return sorted(p for p in raiz.rglob("*") if p.is_file())


def copiar_conferido(origem, destino, simular=False):
    """Copies every file of `origem` into `destino` (same relative paths). Never overwrites: identical bytes at the
    destination count as already copied; different bytes are a conflict (nothing is written for that file and the
    whole call raises CopiaEmConflito at the end, listing them). Returns a report with the counts and the total
    bytes. `simular` only compares."""
    origem, destino = Path(origem), Path(destino)
    if not origem.is_dir():
        raise FileNotFoundError(f"{origem} não existe")
    copiados, iguais, conflitos, total = [], [], [], 0
    for arq in _arquivos(origem):
        rel = arq.relative_to(origem)
        alvo = destino / rel
        h = sha256_arquivo(arq)
        total += arq.stat().st_size
        if alvo.exists():
            (iguais if sha256_arquivo(alvo) == h else conflitos).append(rel.as_posix())
            continue
        if simular:
            copiados.append(rel.as_posix())
            continue
        alvo.parent.mkdir(parents=True, exist_ok=True)
        tmp = alvo.with_name(f"{alvo.name}.tmp{os.getpid()}")
        try:
            shutil.copyfile(arq, tmp)
            if sha256_arquivo(tmp) != h:
                raise CopiaEmConflito(f"{rel}: a cópia não tem os mesmos bytes da origem")
            from .armazem import _publicar_sem_sobrescrever
            _publicar_sem_sobrescrever(tmp, alvo)
            shutil.copystat(arq, alvo)
        finally:
            tmp.unlink(missing_ok=True)
        copiados.append(rel.as_posix())
    r = {"origem": str(origem), "destino": str(destino), "arquivos": len(copiados) + len(iguais) + len(conflitos),
         "copiados": len(copiados), "ja_iguais": len(iguais), "conflitos": conflitos, "bytes": total,
         "simulado": simular}
    if conflitos:
        raise CopiaEmConflito(f"{len(conflitos)} arquivo(s) já existem no destino com outro conteúdo: "
                              f"{conflitos[:5]}; nada foi sobrescrito")
    return r


def conferir_copia(origem, destino):
    """Read-only: every file of `origem` exists in `destino` with the same SHA-256. Extra files in `destino` are
    allowed (the private store keeps growing); a missing or different file is a problem."""
    origem, destino = Path(origem), Path(destino)
    faltam, diferentes, n = [], [], 0
    for arq in _arquivos(origem):
        n += 1
        rel = arq.relative_to(origem)
        alvo = destino / rel
        if not alvo.exists():
            faltam.append(rel.as_posix())
        elif sha256_arquivo(alvo) != sha256_arquivo(arq):
            diferentes.append(rel.as_posix())
    return {"arquivos": n, "faltam": faltam, "diferentes": diferentes, "ok": not faltam and not diferentes}


def _cpf_valido(d):
    if len(set(d)) == 1:
        return False
    for n in (9, 10):
        s = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (s * 10 % 11) % 10 != int(d[n]):
            return False
    return True


def achados_pessoais(texto):
    """Masked CPFs (other than the synthetic ones) and full CPFs with valid check digits found in `texto`."""
    mascarados = sorted(set(CPF_MASCARADO.findall(texto)) - SINTETICOS)
    completos = sorted({"".join(m) for m in CPF_COMPLETO.findall(texto) if _cpf_valido("".join(m))})
    return {"cpf_mascarado": mascarados, "cpf_completo": completos}


def caminho_privado(rel):
    """True if a repository path is one that must never be versioned (raw folders or database/object files)."""
    rel = rel.replace("\\", "/")
    return (any(rel == c or rel.startswith(c + "/") for c in CAMINHOS_PRIVADOS)
            or rel.lower().endswith(EXTENSOES_PRIVADAS))
