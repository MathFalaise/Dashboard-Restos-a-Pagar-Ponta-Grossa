"""On-disk snapshot store: the raw source the database can be rebuilt from.

Layout (root = cfg.snapshots):
  objetos/<ab>/<sha256>.zlib        response bytes, compressed; name = sha256 of the ORIGINAL
  coletas/<YYYY>/<MM>/<stamp>_<type>_<uid8>.json   manifest of one snapshot

Rules:
  * object and manifest are written only once (temporary file + rename);
  * an existing manifest is NEVER overwritten, not even by two simultaneous writes: publishing the temporary file
    is exclusive (it fails if the target already exists);
  * identical bytes become a single object, referenced by as many snapshots as needed.
    This saves storage, it does not deduplicate records: every snapshot still exists, with its own manifest.

Security:
  * every hash used to build a path is validated (64 hexadecimal characters): a tampered manifest cannot point
    outside the `objetos` folder;
  * decompression has a ceiling (expected size, or LIMITE_OBJETO): a tampered object cannot exhaust memory
    (decompression bomb).
"""
import json
import os
import re
import zlib
from pathlib import Path

from . import sha256, sha256_valido

FORMATO = "rp-snapshot/1"
FORMATO_EVIDENCIA = "rp-evidencia/1"
# types accepted by the evidencia_externa table -> name used in the manifest file
TIPOS_EVIDENCIA = {"e-SIC": "esic", "norma": "norma", "nota": "nota", "outro": "outro"}
LIMITE_OBJETO = 256 * 1024 * 1024      # decompression ceiling when the expected size is unknown
_TIPO = re.compile(r"[a-z_]+")
_UID = re.compile(r"[0-9a-f]{32}")
_ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


class ObjetoCorrompido(Exception):
    pass


class ManifestoJaExiste(Exception):
    pass


class ManifestoInvalido(ValueError):
    pass


def descomprimir(comprimido, tamanho=None):
    """zlib with an output ceiling. For an intact object the result is identical to zlib.decompress;
    a truncated object, or one whose size differs from the expected or exceeds the ceiling, raises ObjetoCorrompido."""
    limite = LIMITE_OBJETO if tamanho is None else tamanho
    d = zlib.decompressobj()
    try:
        corpo = d.decompress(comprimido, limite + 1)
    except zlib.error as e:
        raise ObjetoCorrompido(f"zlib: {e}") from e
    if len(corpo) > limite:
        raise ObjetoCorrompido(f"conteudo descomprimido passa de {limite} bytes")
    if not d.eof:
        raise ObjetoCorrompido("fluxo zlib incompleto")
    if tamanho is not None and len(corpo) != tamanho:
        raise ObjetoCorrompido(f"tamanho descomprimido {len(corpo)} difere do esperado {tamanho}")
    return corpo


def _publicar_sem_sobrescrever(tmp, destino):
    """Atomically moves `tmp` to `destino`, failing (FileExistsError) if the target already exists."""
    if os.name == "nt":
        os.rename(tmp, destino)          # on Windows, rename fails if the target exists
    else:
        os.link(tmp, destino)            # on POSIX, link fails if the target exists
        os.unlink(tmp)


class Armazem:
    def __init__(self, raiz):
        self.raiz = Path(raiz)

    # ------------------------------------------------------------ objects
    def caminho_objeto(self, h):
        if not sha256_valido(h):
            raise ObjetoCorrompido(f"hash invalido: {h!r}")
        return self.raiz / "objetos" / h[:2] / f"{h}.zlib"

    def gravar_objeto(self, corpo):
        h = sha256(corpo)
        destino = self.caminho_objeto(h)
        if destino.exists():
            self.ler_objeto(h, len(corpo))  # checks what was already there
            return h
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_name(destino.name + f".tmp{os.getpid()}")
        try:
            tmp.write_bytes(zlib.compress(corpo, 6))
            os.replace(tmp, destino)     # objects are content-addressed: replacing with identical bytes is harmless
        finally:
            tmp.unlink(missing_ok=True)
        self.ler_objeto(h, len(corpo))  # checks the write
        return h

    def ler_comprimido(self, h):
        return self.caminho_objeto(h).read_bytes()

    def ler_objeto(self, h, tamanho=None):
        try:
            corpo = descomprimir(self.ler_comprimido(h), tamanho)
        except OSError as e:
            if isinstance(e, FileNotFoundError):
                raise
            raise ObjetoCorrompido(f"{h}: {e}") from e
        except ObjetoCorrompido as e:
            raise ObjetoCorrompido(f"{h}: {e}") from e
        if sha256(corpo) != h:
            raise ObjetoCorrompido(f"{h}: conteúdo não confere com o hash")
        return corpo

    # ------------------------------------------------------------ manifests
    def gravar_manifesto(self, m):
        tipo, uid, quando = m.get("tipo"), m.get("snapshot_uid"), m.get("coletada_em")
        if not (isinstance(tipo, str) and _TIPO.fullmatch(tipo) and isinstance(uid, str) and _UID.fullmatch(uid)
                and isinstance(quando, str) and _ISO.match(quando)):
            raise ManifestoInvalido(f"tipo, snapshot_uid ou coletada_em fora do formato: {tipo!r}, {uid!r}, {quando!r}")
        carimbo = quando[:19].replace("-", "").replace(":", "").replace("T", "-")
        rel = Path("coletas") / quando[:4] / quando[5:7] / f"{carimbo}_{tipo}_{uid[:8]}.json"
        return self._gravar_json_uma_vez(rel, m)

    def gravar_manifesto_evidencia(self, m):
        """Manifest of an external evidence (e-SIC, regulation, note...), in evidencias/YYYY/MM/. Never overwritten."""
        tipo, uid, quando = m.get("tipo"), m.get("evidencia_uid"), m.get("registrada_em")
        if not (tipo in TIPOS_EVIDENCIA and isinstance(uid, str) and _UID.fullmatch(uid)
                and isinstance(quando, str) and _ISO.match(quando) and sha256_valido(m.get("sha256"))):
            raise ManifestoInvalido(f"tipo, evidencia_uid, registrada_em ou sha256 fora do formato: {tipo!r}, {uid!r}, {quando!r}")
        carimbo = quando[:19].replace("-", "").replace(":", "").replace("T", "-")
        rel = Path("evidencias") / quando[:4] / quando[5:7] / f"{carimbo}_{TIPOS_EVIDENCIA[tipo]}_{uid[:8]}.json"
        return self._gravar_json_uma_vez(rel, m)

    def _gravar_json_uma_vez(self, rel, m):
        destino = self.raiz / rel
        if destino.exists():
            raise ManifestoJaExiste(str(destino))
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_name(destino.name + f".tmp{os.getpid()}")
        try:
            tmp.write_text(json.dumps(m, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
            try:
                _publicar_sem_sobrescrever(tmp, destino)
            except FileExistsError:
                raise ManifestoJaExiste(str(destino)) from None
        finally:
            tmp.unlink(missing_ok=True)
        return rel.as_posix()

    def ler_manifesto(self, rel):
        return json.loads(self.bytes_do_manifesto(rel).decode("utf-8"))

    def bytes_do_manifesto(self, rel):
        """The manifest file bytes exactly as stored (versioned with -text: the same bytes after a clone)."""
        p = (self.raiz / rel).resolve()
        if not p.is_relative_to((self.raiz / "coletas").resolve()):
            raise ManifestoInvalido(f"manifesto fora do armazem: {rel!r}")
        return p.read_bytes()

    def manifestos_e_erros(self):
        """(items, errors): items = (relative path, manifest) in collection order; errors = unreadable files."""
        base = self.raiz / "coletas"
        itens, erros = [], []
        for p in base.rglob("*.json") if base.exists() else []:
            rel = p.relative_to(self.raiz).as_posix()
            try:
                m = json.loads(p.read_text(encoding="utf-8"))
                chave = (m["coletada_em"], m["snapshot_uid"])
            except (OSError, ValueError, KeyError, TypeError, RecursionError) as e:
                erros.append(f"{rel}: manifesto ilegivel ({type(e).__name__})")
                continue
            itens.append((rel, m, chave))
        itens.sort(key=lambda x: x[2])
        return [(rel, m) for rel, m, _ in itens], erros

    def manifestos(self):
        """(relative path, manifest) in collection order. An unreadable manifest stops it (ManifestoInvalido)."""
        itens, erros = self.manifestos_e_erros()
        if erros:
            raise ManifestoInvalido("; ".join(erros))
        return itens

    def evidencias_e_erros(self):
        """(items, errors) of the external evidence manifests, in recording order."""
        base = self.raiz / "evidencias"
        itens, erros = [], []
        for p in base.rglob("*.json") if base.exists() else []:
            rel = p.relative_to(self.raiz).as_posix()
            try:
                m = json.loads(p.read_text(encoding="utf-8"))
                chave = (m["registrada_em"], m["evidencia_uid"])
            except (OSError, ValueError, KeyError, TypeError, RecursionError) as e:
                erros.append(f"{rel}: manifesto de evidencia ilegivel ({type(e).__name__})")
                continue
            itens.append((rel, m, chave))
        itens.sort(key=lambda x: x[2])
        return [(rel, m) for rel, m, _ in itens], erros

    def evidencias(self):
        """(relative path, manifest) of the external evidence. An unreadable manifest stops it (ManifestoInvalido)."""
        itens, erros = self.evidencias_e_erros()
        if erros:
            raise ManifestoInvalido("; ".join(erros))
        return itens

    def verificar(self):
        """Problems found (empty list = intact). Besides manifests and objects, reports objects no manifest
        references and abandoned temporary files: both are traces of an interrupted write (objects are written
        before the manifest) and are never deleted automatically (audit ARM-01)."""
        itens, problemas = self.manifestos_e_erros()
        evid, erros_evid = self.evidencias_e_erros()
        problemas += erros_evid
        referenciados = set()
        for _, m in itens:
            referenciados |= {r.get("sha256") for r in m.get("respostas", []) + m.get("segunda_leitura", [])
                              if isinstance(r, dict)}
        referenciados |= {m.get("sha256") for _, m in evid}
        if (self.raiz / "objetos").exists():
            for p in sorted((self.raiz / "objetos").rglob("*")):
                if p.is_file() and ".tmp" in p.name:
                    problemas.append(f"arquivo temporário abandonado: {p.relative_to(self.raiz).as_posix()}")
                elif p.is_file() and p.suffix == ".zlib" and p.stem not in referenciados:
                    problemas.append(f"objeto sem manifesto que o referencie: {p.relative_to(self.raiz).as_posix()}")
        for p in sorted(self.raiz.glob("*/**/*.json.tmp*")):
            problemas.append(f"arquivo temporário abandonado: {p.relative_to(self.raiz).as_posix()}")
        for rel, m in itens:
            for r in m.get("segunda_leitura", []):
                try:
                    self.ler_objeto(r["sha256"], r["tamanho"])
                except FileNotFoundError:
                    problemas.append(f"{rel}: objeto da segunda leitura ausente {str(r.get('sha256'))[:12]}")
                except (ObjetoCorrompido, KeyError, TypeError) as e:
                    problemas.append(f"{rel}: segunda leitura: {e}")
        for rel, m in evid:
            if m.get("formato") != FORMATO_EVIDENCIA:
                problemas.append(f"{rel}: formato desconhecido {m.get('formato')!r}")
            try:
                self.ler_objeto(m["sha256"], m["tamanho"])
            except FileNotFoundError:
                problemas.append(f"{rel}: arquivo da evidencia ausente {str(m.get('sha256'))[:12]}")
            except ObjetoCorrompido as e:
                problemas.append(f"{rel}: {e}")
            except (KeyError, TypeError) as e:
                problemas.append(f"{rel}: evidencia sem sha256/tamanho ({type(e).__name__})")
        for rel, m in itens:
            if m.get("formato") != FORMATO:
                problemas.append(f"{rel}: formato desconhecido {m.get('formato')!r}")
            for r in m.get("respostas", []):
                try:
                    self.ler_objeto(r["sha256"], r["tamanho"])
                except FileNotFoundError:
                    problemas.append(f"{rel}: objeto ausente {str(r.get('sha256'))[:12]}")
                except ObjetoCorrompido as e:
                    problemas.append(f"{rel}: {e}")
                except (KeyError, TypeError) as e:
                    problemas.append(f"{rel}: resposta sem sha256/tamanho ({type(e).__name__})")
        return problemas
