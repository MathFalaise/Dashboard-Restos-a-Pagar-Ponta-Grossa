"""EMPIRICAL contract of the Elotech API used by the collector (critical review, items 3, 6, 16, 17, 49 and 50).

It is not vendor documentation: `/empenhos/restos-a-pagar` is not in the collected OpenAPI specification. It is the
behavior observed and checked by the project (see docs/audits/ELOTECH_API_CONTRACT.md). The parts of the contract
the code uses live here:

  * ORDEM_RP: the order REQUESTED in the RP listing. Probe of 05/10/2026 (docs/audits/sondagem_ordenacao.json):
    the API accepts and echoes `sort` on two fields, obeys the requested order (desc reverses it) and, with this
    order, returns the same content, byte for byte, as the implicit order (1 and 2 pages). Requesting the order
    pins down what used to be only observed; the echo is checked page by page.
  * forma(): fingerprint of the STRUCTURE of a JSON response (path -> types), recorded in the manifest. A new field,
    a removed one or one with another type changes the fingerprint; `diagnosticar-api` compares today's shape with
    the snapshots'.
  * minimum contract of the catalogs (entities, fiscal years, publications): valid JSON is not enough - an error
    object with HTTP 200 is JSON. The minimum is what the normalization needs to produce rows.
"""
import hashlib
import json
from collections import defaultdict
from decimal import Decimal

VERSAO = "rp-api-contrato/1"
ORDEM_RP = ("anoempenho,asc", "empenho,asc")
CAMPOS_DA_CHAVE = ("entidade", "anoempenho", "empenho")


def chave_negocio(registro):
    """Logical identity of an RP listing record: (entidade, anoempenho, empenho)."""
    return tuple(registro.get(c) for c in CAMPOS_DA_CHAVE)


def canonico(registro):
    """Canonical serialization of a record: identity of the CONTENT (two equal occurrences = same bytes here)."""
    return json.dumps(registro, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def impressao_registro(registro):
    """SHA-256 of the canonical serialization: identity of a record's content (review, item 15)."""
    return hashlib.sha256(canonico(registro).encode()).hexdigest()


# ------------------------------------------------------------------ requested order and echo
def sort_ecoado_confere(ecoado, pedido):
    """True if the `sort` echoed by the page is exactly the requested order (property and direction, same order)."""
    if not isinstance(ecoado, list) or len(ecoado) != len(pedido):
        return False
    for e, p in zip(ecoado, pedido):
        prop, direcao = p.split(",")
        if not isinstance(e, dict) or e.get("property") != prop or str(e.get("direction", "")).lower() != direcao:
            return False
    return True


# ------------------------------------------------------------------ response shape
def _tipo(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, (int, float, Decimal)):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    return type(v).__name__


def _percorrer(valor, caminho, saida):
    saida[caminho].add(_tipo(valor))
    if isinstance(valor, dict):
        for k, v in valor.items():
            _percorrer(v, f"{caminho}.{k}", saida)
    elif isinstance(valor, list):
        for v in valor:
            _percorrer(v, f"{caminho}[]", saida)


def forma(corpos):
    """Structure of the union of the JSON responses: sorted list 'path:type1|type2'. None if no body is JSON
    (e.g. PDF). VALUES do not go in: only paths and types."""
    saida = defaultdict(set)
    algum = False
    for corpo in corpos:
        try:
            d = json.loads(corpo, parse_float=Decimal)
        except (ValueError, RecursionError, TypeError):
            continue
        algum = True
        _percorrer(d, "$", saida)
    if not algum:
        return None
    return sorted(f"{c}:{'|'.join(sorted(t))}" for c, t in saida.items())


def descricao_forma(corpos):
    """Block recorded in the manifest ("contrato_api"), or None for a non-JSON response."""
    f = forma(corpos)
    if f is None:
        return None
    return {"versao": VERSAO, "forma_sha256": hashlib.sha256("\n".join(f).encode()).hexdigest(), "forma": f}


def comparar_formas(referencia, atual):
    """Structural differences between two shapes: new paths, removed paths and paths with a different type.
    `null` alone is not a type change (an optional field that came empty): only a type that did not exist counts."""
    ref = {x.rsplit(":", 1)[0]: set(x.rsplit(":", 1)[1].split("|")) for x in referencia or []}
    atu = {x.rsplit(":", 1)[0]: set(x.rsplit(":", 1)[1].split("|")) for x in atual or []}
    novos = sorted(set(atu) - set(ref))
    removidos = sorted(set(ref) - set(atu))
    tipos = sorted(f"{c}: {'|'.join(sorted(ref[c]))} -> {'|'.join(sorted(atu[c]))}"
                   for c in set(ref) & set(atu) if (atu[c] - {"null"}) - ref[c])
    return {"novos": novos, "removidos": removidos, "tipo_diferente": tipos,
            "igual": not (novos or removidos or tipos)}


# Parts of the response that only ECHO the request (the requested order). They are checked by sort_ecoado_confere,
# not by the structure: snapshots collected before the collector requested `sort` have this echo empty, and that
# is not an API change (measured on the portal on 05/10/2026: the only structural difference between sample and snapshots).
ECO_DA_REQUISICAO = ("$.sort[]", "$.pageable.sort[]")


def _fora_do_eco(caminho):
    return not caminho.startswith(ECO_DA_REQUISICAO)


def _caminhos(valor, prefixo):
    saida = defaultdict(set)
    _percorrer(valor, prefixo, saida)
    return set(saida)


def _obrigatorios(corpos):
    """(top-level paths present in EVERY response, paths present in EVERY record, number of records).
    Record = item of `content` (Spring page) or of the list (catalog). A rare field - present only in some records,
    or an object that is sometimes null - is not mandatory."""
    topo, registro, n = None, None, 0
    for corpo in corpos:
        try:
            d = json.loads(corpo, parse_float=Decimal)
        except (ValueError, RecursionError, TypeError):
            continue
        if isinstance(d, dict) and isinstance(d.get("content"), list):
            t, registros, prefixo = {f"$.{k}" for k in d}, d["content"], "$.content[]"
        elif isinstance(d, list):
            t, registros, prefixo = set(), d, "$[]"
        else:
            t, registros, prefixo = _caminhos(d, "$"), [], None
        topo = t if topo is None else topo & t
        for r in registros:
            c = _caminhos(r, prefixo)
            registro = c if registro is None else registro & c
            n += 1
    return topo or set(), registro or set(), n


def comparar_amostra(referencia, amostra):
    """Structure of a SAMPLE (e.g. a small page requested now) against reference responses (a recorded snapshot).
    `novos` and `tipo_diferente` by the union of the shapes (comparar_formas): a path or type that appears in no
    recorded record. `removidos` only among the reference's MANDATORY paths (in every response and every record):
    the small sample lacks the rare fields, and that is not a change. A sample without records only checks the top
    level. The echo of the requested order (ECO_DA_REQUISICAO) stays out."""
    sem_eco = lambda f: [x for x in f or [] if _fora_do_eco(x.rsplit(":", 1)[0])]
    base = comparar_formas(sem_eco(forma(referencia)), sem_eco(forma(amostra)))
    topo_ref, reg_ref, _ = _obrigatorios(referencia)
    topo_am, reg_am, n_am = _obrigatorios(amostra)
    removidos = sorted(c for c in (topo_ref - topo_am) | ((reg_ref - reg_am) if n_am else set()) if _fora_do_eco(c))
    return {"novos": base["novos"], "removidos": removidos, "tipo_diferente": base["tipo_diferente"],
            "registros_na_amostra": n_am, "igual": not (base["novos"] or removidos or base["tipo_diferente"])}


# ------------------------------------------------------------------ minimum contract of the catalogs
def _inteiro(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _lista_de_objetos(d, alvo):
    if not isinstance(d, list):
        return f"{alvo}: a resposta não é uma lista (veio {_tipo(d)})"
    ruim = next((i for i, x in enumerate(d) if not isinstance(x, dict)), None)
    if ruim is not None:
        return f"{alvo}: o item {ruim} não é um objeto"
    return None


def contrato_entidades(d):
    """Problem (text) or None. A NON-empty list of objects with an integer `id` (what the normalization requires)."""
    problema = _lista_de_objetos(d, "catálogo de entidades")
    if problema:
        return problema
    if not d:
        return "catálogo de entidades vazio"
    ruim = next((i for i, x in enumerate(d) if not _inteiro(x.get("id"))), None)
    if ruim is not None:
        return f"catálogo de entidades: o item {ruim} não tem 'id' inteiro"
    return None


def contrato_exercicios(d, entidade):
    """Problem (text) or None. A list of objects with an integer id.exercicio and id.entidade.id = the requested entity."""
    problema = _lista_de_objetos(d, f"catálogo de exercícios da entidade {entidade}")
    if problema:
        return problema
    for i, x in enumerate(d):
        ident = x.get("id")
        ent = ident.get("entidade") if isinstance(ident, dict) else None
        if not isinstance(ident, dict) or not _inteiro(ident.get("exercicio")) or not isinstance(ent, dict) \
                or not _inteiro(ent.get("id")):
            return f"catálogo de exercícios da entidade {entidade}: o item {i} não tem id.exercicio e id.entidade.id inteiros"
        if ent["id"] != entidade:
            return (f"catálogo de exercícios da entidade {entidade}: o item {i} é da entidade {ent['id']} "
                    "(resposta de outra consulta)")
    return None


def contrato_publicacoes(d):
    """Problem (text) or None. A list of groups (objects) whose `list`, if present, is a list."""
    problema = _lista_de_objetos(d, "publicações")
    if problema:
        return problema
    ruim = next((i for i, x in enumerate(d) if "list" in x and not isinstance(x["list"], list)), None)
    if ruim is not None:
        return f"publicações: o grupo {ruim} tem 'list' que não é lista"
    return None
