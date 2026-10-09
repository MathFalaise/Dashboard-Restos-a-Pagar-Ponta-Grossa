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
  * STRICT contract of the paginated endpoints (v2, 09/10/2026): every page must bring all the Spring Page metadata
    with its type, and every record of the RP listing and of the movement list must bring exactly the known keys with
    their types. Measured on the 383 RP pages (266,787 records) and 148 movement pages (2,352 entries) in the store on
    09/10/2026: all of them meet it, so it refuses no recorded collection. A new key, a missing key or another type
    makes the collection 'incompleta' (never the current snapshot) until someone looks at it: a change of structure is
    never absorbed silently. Valid JSON is not a semantically valid response.
"""
import hashlib
import json
from collections import defaultdict
from decimal import Decimal

VERSAO = "rp-api-contrato/2"
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


# ------------------------------------------------------------------ strict contract of the paginated endpoints
INTEIRO, NUMERO, TEXTO, BOOLEANO, LISTA, OBJETO = "inteiro", "numero", "texto", "booleano", "lista", "objeto"

# Spring Page metadata: all mandatory, with these types (checked on every recorded page).
METADADOS_PAGINA = {"content": LISTA, "number": INTEIRO, "numberOfElements": INTEIRO, "size": INTEIRO,
                    "totalElements": INTEIRO, "totalPages": INTEIRO, "first": BOOLEANO, "last": BOOLEANO,
                    "empty": BOOLEANO, "sort": LISTA, "pageable": OBJETO}

# Monetary fields of the RP listing (API names). None of them may be missing, null or non-numeric.
DINHEIRO_RP = ("proc", "aproc", "canceladoProc", "pagoProc", "pagoProcEstornado", "canceladoAProc", "pagoAProc",
               "pagoAProcEstornado", "liquidado", "retencao")
REGISTRO_RP = {"entidade": INTEIRO, "anoempenho": INTEIRO, "empenho": INTEIRO, "empenhoExercicio": TEXTO,
               "cnpjNome": TEXTO, "dataEmissao": TEXTO, "programatica": TEXTO, "fonteRecurso": INTEIRO,
               "descricaoFonte": TEXTO, "fornecedor": INTEIRO, "nome": TEXTO, "cnpj": TEXTO,
               "desdobraDesp": TEXTO, "subDesdobramento": TEXTO, **{c: NUMERO for c in DINHEIRO_RP}}
# Classification keys that the API sends all together or not at all (6,956 records without the 7, never part of them).
GRUPO_OPCIONAL_RP = {"orgao": TEXTO, "unidade": TEXTO, "funcao": TEXTO, "subFuncao": TEXTO, "programa": TEXTO,
                     "projeto": TEXTO, "elemento": TEXTO}
REGISTRO_MOV = {"data": TEXTO, "descricaoTipoLancamento": TEXTO, "exercicioLiquidacao": INTEIRO,
                "exercicioPagamento": INTEIRO, "noLiquidacao": INTEIRO, "noPagamento": INTEIRO, "nroDocumento": TEXTO,
                "tipoLancamento": INTEIRO, "valor": NUMERO, "valorALiquidar": NUMERO, "valorAPagar": NUMERO}


def tem_tipo(valor, tipo):
    """True if `valor` (decoded JSON) has the contract type. bool is never a number; null is never any type."""
    if tipo == INTEIRO:
        return _inteiro(valor)
    if tipo == NUMERO:
        return isinstance(valor, (int, float, Decimal)) and not isinstance(valor, bool)
    if tipo == TEXTO:
        return isinstance(valor, str)
    if tipo == BOOLEANO:
        return isinstance(valor, bool)
    if tipo == LISTA:
        return isinstance(valor, list)
    if tipo == OBJETO:
        return isinstance(valor, dict)
    raise ValueError(f"tipo de contrato desconhecido: {tipo}")


def contrato_pagina(d):
    """Problem (text) or None: the page is an object with every metadata field of METADADOS_PAGINA, each with its type.
    totalElements, totalPages and number are never negative; size is positive."""
    if not isinstance(d, dict):
        return f"a resposta não é um objeto de página (veio {_tipo(d)})"
    ausentes = [k for k in METADADOS_PAGINA if k not in d]
    if ausentes:
        return f"metadados de página ausentes: {', '.join(ausentes)}"
    errados = [f"{k} ({_tipo(d[k])}, esperado {t})" for k, t in METADADOS_PAGINA.items() if not tem_tipo(d[k], t)]
    if errados:
        return f"metadados de página com tipo errado: {', '.join(errados)}"
    negativos = [k for k in ("number", "numberOfElements", "totalElements", "totalPages") if d[k] < 0]
    if negativos or d["size"] <= 0:
        return f"metadados de página fora do domínio: {', '.join(negativos or ['size'])}"
    return None


def _contrato_registro(x, obrigatorios, grupo, alvo):
    if not isinstance(x, dict):
        return f"{alvo}: o registro não é um objeto (veio {_tipo(x)})"
    conhecidas = set(obrigatorios) | set(grupo)
    extras = sorted(k for k in x if k not in conhecidas)
    if extras:
        return f"{alvo}: chave(s) fora do contrato: {', '.join(extras)}"
    ausentes = [k for k in obrigatorios if k not in x]
    if ausentes:
        return f"{alvo}: chave(s) obrigatória(s) ausente(s): {', '.join(ausentes)}"
    presentes = [k for k in grupo if k in x]
    if presentes and len(presentes) != len(grupo):
        return (f"{alvo}: grupo de classificação incompleto (veio {', '.join(presentes)}; vem inteiro ou não vem)")
    errados = [f"{k} ({_tipo(x[k])}, esperado {t})" for k, t in {**obrigatorios, **grupo}.items()
               if k in x and not tem_tipo(x[k], t)]
    if errados:
        return f"{alvo}: tipo fora do contrato: {', '.join(errados)}"
    return None


def contrato_registro_rp(x):
    """Problem (text) or None for one record of the RP listing (REGISTRO_RP + GRUPO_OPCIONAL_RP, nothing else)."""
    return _contrato_registro(x, REGISTRO_RP, GRUPO_OPCIONAL_RP, "registro de RP")


def contrato_registro_mov(x):
    """Problem (text) or None for one entry of the movement list (REGISTRO_MOV, nothing else)."""
    return _contrato_registro(x, REGISTRO_MOV, {}, "lançamento de movimentação")
