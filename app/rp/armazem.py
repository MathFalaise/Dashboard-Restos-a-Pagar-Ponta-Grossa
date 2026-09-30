"""Armazem de snapshots em disco: a fonte bruta da qual o banco e reconstruivel.

Estrutura (raiz = cfg.snapshots):
  objetos/<ab>/<sha256>.zlib        bytes da resposta, comprimidos; nome = sha256 do ORIGINAL
  coletas/<AAAA>/<MM>/<carimbo>_<tipo>_<uid8>.json   manifesto de um snapshot

Regras:
  * objeto e manifesto sao gravados uma unica vez (arquivo temporario + rename);
  * manifesto existente NUNCA e sobrescrito, nem por duas gravacoes simultaneas: a publicacao do
    arquivo temporario e exclusiva (falha se o destino ja existir);
  * bytes iguais viram um so objeto, referenciado por quantos snapshots precisarem.
    Isso e economia de armazenamento, nao deduplicacao de registros: cada snapshot
    continua existindo, com o proprio manifesto.

Seguranca:
  * todo hash usado para montar caminho e validado (64 hexadecimais): um manifesto adulterado
    nao consegue apontar para fora da pasta `objetos`;
  * a descompressao tem teto (tamanho esperado, ou LIMITE_OBJETO): um objeto adulterado nao
    consegue esgotar a memoria (bomba de descompressao).
"""
import json
import os
import re
import zlib
from pathlib import Path

from . import sha256, sha256_valido

FORMATO = "rp-snapshot/1"
FORMATO_EVIDENCIA = "rp-evidencia/1"
# tipos aceitos pela tabela evidencia_externa -> nome usado no arquivo do manifesto
TIPOS_EVIDENCIA = {"e-SIC": "esic", "norma": "norma", "nota": "nota", "outro": "outro"}
LIMITE_OBJETO = 256 * 1024 * 1024      # teto de descompressao quando o tamanho esperado nao e conhecido
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
    """zlib com teto de saida. Para objeto integro o resultado e identico a zlib.decompress;
    objeto truncado, com tamanho diferente do esperado ou maior que o teto vira ObjetoCorrompido."""
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
    """Move `tmp` para `destino` de forma atomica, falhando (FileExistsError) se o destino ja existir."""
    if os.name == "nt":
        os.rename(tmp, destino)          # no Windows, rename falha se o destino existir
    else:
        os.link(tmp, destino)            # no POSIX, link falha se o destino existir
        os.unlink(tmp)


class Armazem:
    def __init__(self, raiz):
        self.raiz = Path(raiz)

    # ------------------------------------------------------------ objetos
    def caminho_objeto(self, h):
        if not sha256_valido(h):
            raise ObjetoCorrompido(f"hash invalido: {h!r}")
        return self.raiz / "objetos" / h[:2] / f"{h}.zlib"

    def gravar_objeto(self, corpo):
        h = sha256(corpo)
        destino = self.caminho_objeto(h)
        if destino.exists():
            self.ler_objeto(h, len(corpo))  # confere o que ja estava la
            return h
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_name(destino.name + f".tmp{os.getpid()}")
        try:
            tmp.write_bytes(zlib.compress(corpo, 6))
            os.replace(tmp, destino)     # objeto e enderecado pelo conteudo: substituir por bytes iguais e inocuo
        finally:
            tmp.unlink(missing_ok=True)
        self.ler_objeto(h, len(corpo))  # confere a gravacao
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

    # ------------------------------------------------------------ manifestos
    def gravar_manifesto(self, m):
        tipo, uid, quando = m.get("tipo"), m.get("snapshot_uid"), m.get("coletada_em")
        if not (isinstance(tipo, str) and _TIPO.fullmatch(tipo) and isinstance(uid, str) and _UID.fullmatch(uid)
                and isinstance(quando, str) and _ISO.match(quando)):
            raise ManifestoInvalido(f"tipo, snapshot_uid ou coletada_em fora do formato: {tipo!r}, {uid!r}, {quando!r}")
        carimbo = quando[:19].replace("-", "").replace(":", "").replace("T", "-")
        rel = Path("coletas") / quando[:4] / quando[5:7] / f"{carimbo}_{tipo}_{uid[:8]}.json"
        return self._gravar_json_uma_vez(rel, m)

    def gravar_manifesto_evidencia(self, m):
        """Manifesto de uma evidencia externa (e-SIC, norma, nota...), em evidencias/AAAA/MM/. Nunca sobrescrito."""
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
        p = (self.raiz / rel).resolve()
        if not p.is_relative_to((self.raiz / "coletas").resolve()):
            raise ManifestoInvalido(f"manifesto fora do armazem: {rel!r}")
        return json.loads(p.read_text(encoding="utf-8"))

    def manifestos_e_erros(self):
        """(itens, erros): itens = (caminho relativo, manifesto) em ordem de coleta; erros = arquivos ilegiveis."""
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
        """(caminho relativo, manifesto) em ordem de coleta. Manifesto ilegivel interrompe (ManifestoInvalido)."""
        itens, erros = self.manifestos_e_erros()
        if erros:
            raise ManifestoInvalido("; ".join(erros))
        return itens

    def evidencias_e_erros(self):
        """(itens, erros) dos manifestos de evidencia externa, em ordem de registro."""
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
        """(caminho relativo, manifesto) das evidencias externas. Manifesto ilegivel interrompe (ManifestoInvalido)."""
        itens, erros = self.evidencias_e_erros()
        if erros:
            raise ManifestoInvalido("; ".join(erros))
        return itens

    def verificar(self):
        """Problemas encontrados (lista vazia = integro)."""
        itens, problemas = self.manifestos_e_erros()
        evid, erros_evid = self.evidencias_e_erros()
        problemas += erros_evid
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
