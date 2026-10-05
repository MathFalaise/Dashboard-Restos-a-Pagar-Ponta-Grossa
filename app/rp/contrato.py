"""Contrato EMPIRICO da API Elotech usado pelo coletor (revisao critica, itens 3, 6, 16, 17, 49 e 50).

Nao e documentacao do fornecedor: `/empenhos/restos-a-pagar` nao aparece na especificacao OpenAPI coletada. E o
comportamento observado e conferido pelo projeto (ver auditoria/CONTRATO_API_ELOTECH.md). Aqui ficam as partes
do contrato que o codigo usa:

  * ORDEM_RP: a ordenacao PEDIDA na listagem de RP. Sondagem de 05/10/2026 (auditoria/sondagem_ordenacao.json):
    a API aceita e ecoa `sort` em dois campos, obedece a ordem pedida (desc inverte) e, com esta ordem, devolve
    o mesmo content, byte a byte, que a ordem implicita (1 e 2 paginas). Pedir a ordem fixa o que antes era so
    observado; o eco e conferido pagina a pagina.
  * forma(): impressao da ESTRUTURA de uma resposta JSON (caminho -> tipos), gravada no manifesto. Campo novo,
    removido ou com outro tipo muda a impressao; `diagnosticar-api` compara a forma de hoje com a dos snapshots.
  * contrato minimo dos catalogos (entidades, exercicios, publicacoes): JSON valido nao basta - um objeto de erro
    com HTTP 200 e JSON. O minimo e o que a normalizacao precisa para gerar linhas.
"""
import hashlib
import json
from collections import defaultdict
from decimal import Decimal

VERSAO = "rp-api-contrato/1"
ORDEM_RP = ("anoempenho,asc", "empenho,asc")
CAMPOS_DA_CHAVE = ("entidade", "anoempenho", "empenho")


def chave_negocio(registro):
    """Identidade logica de um registro da listagem de RP: (entidade, anoempenho, empenho)."""
    return tuple(registro.get(c) for c in CAMPOS_DA_CHAVE)


def canonico(registro):
    """Serializacao canonica de um registro: identidade do CONTEUDO (duas ocorrencias iguais = mesmos bytes aqui)."""
    return json.dumps(registro, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def impressao_registro(registro):
    """SHA-256 da serializacao canonica: identidade do conteudo de um registro (revisao, item 15)."""
    return hashlib.sha256(canonico(registro).encode()).hexdigest()


# ------------------------------------------------------------------ ordem pedida e eco
def sort_ecoado_confere(ecoado, pedido):
    """True se o `sort` ecoado pela pagina e exatamente a ordem pedida (propriedade e direcao, na mesma ordem)."""
    if not isinstance(ecoado, list) or len(ecoado) != len(pedido):
        return False
    for e, p in zip(ecoado, pedido):
        prop, direcao = p.split(",")
        if not isinstance(e, dict) or e.get("property") != prop or str(e.get("direction", "")).lower() != direcao:
            return False
    return True


# ------------------------------------------------------------------ forma da resposta
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
    """Estrutura da uniao das respostas JSON: lista ordenada 'caminho:tipo1|tipo2'. None se nenhum corpo for JSON
    (ex.: PDF). Os VALORES nao entram: so caminhos e tipos."""
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
    """Bloco gravado no manifesto ("contrato_api"), ou None para resposta nao JSON."""
    f = forma(corpos)
    if f is None:
        return None
    return {"versao": VERSAO, "forma_sha256": hashlib.sha256("\n".join(f).encode()).hexdigest(), "forma": f}


def comparar_formas(referencia, atual):
    """Diferencas de estrutura entre duas formas: caminhos novos, removidos e com tipo diferente.
    `null` sozinho nao e mudanca de tipo (campo opcional que veio vazio): so conta tipo que nao existia."""
    ref = {x.rsplit(":", 1)[0]: set(x.rsplit(":", 1)[1].split("|")) for x in referencia or []}
    atu = {x.rsplit(":", 1)[0]: set(x.rsplit(":", 1)[1].split("|")) for x in atual or []}
    novos = sorted(set(atu) - set(ref))
    removidos = sorted(set(ref) - set(atu))
    tipos = sorted(f"{c}: {'|'.join(sorted(ref[c]))} -> {'|'.join(sorted(atu[c]))}"
                   for c in set(ref) & set(atu) if (atu[c] - {"null"}) - ref[c])
    return {"novos": novos, "removidos": removidos, "tipo_diferente": tipos,
            "igual": not (novos or removidos or tipos)}


# Partes da resposta que so ECOAM a requisicao (a ordem pedida). Sao conferidas por sort_ecoado_confere, nao pela
# estrutura: os snapshots coletados antes de o coletor pedir `sort` tem esse eco vazio, e a diferenca nao e mudanca
# da API (medido no portal em 05/10/2026: era a unica diferenca de estrutura entre a amostra e os snapshots).
ECO_DA_REQUISICAO = ("$.sort[]", "$.pageable.sort[]")


def _fora_do_eco(caminho):
    return not caminho.startswith(ECO_DA_REQUISICAO)


def _caminhos(valor, prefixo):
    saida = defaultdict(set)
    _percorrer(valor, prefixo, saida)
    return set(saida)


def _obrigatorios(corpos):
    """(caminhos do topo presentes em TODA resposta, caminhos presentes em TODO registro, numero de registros).
    Registro = item de `content` (pagina Spring) ou da lista (catalogo). Campo raro - presente so em alguns
    registros, ou objeto que as vezes vem nulo - nao e obrigatorio."""
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
    """Estrutura de uma AMOSTRA (ex.: uma pagina pequena pedida agora) contra respostas de referencia (um snapshot
    gravado). `novos` e `tipo_diferente` pela uniao das formas (comparar_formas): caminho ou tipo que nao aparece em
    nenhum registro gravado. `removidos` so entre os caminhos OBRIGATORIOS da referencia (em toda resposta e em todo
    registro): a amostra pequena nao traz os campos raros, e isso nao e mudanca. Amostra sem registros so confere o
    topo. O eco da ordem pedida (ECO_DA_REQUISICAO) fica fora."""
    sem_eco = lambda f: [x for x in f or [] if _fora_do_eco(x.rsplit(":", 1)[0])]
    base = comparar_formas(sem_eco(forma(referencia)), sem_eco(forma(amostra)))
    topo_ref, reg_ref, _ = _obrigatorios(referencia)
    topo_am, reg_am, n_am = _obrigatorios(amostra)
    removidos = sorted(c for c in (topo_ref - topo_am) | ((reg_ref - reg_am) if n_am else set()) if _fora_do_eco(c))
    return {"novos": base["novos"], "removidos": removidos, "tipo_diferente": base["tipo_diferente"],
            "registros_na_amostra": n_am, "igual": not (base["novos"] or removidos or base["tipo_diferente"])}


# ------------------------------------------------------------------ contrato minimo dos catalogos
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
    """Problema (texto) ou None. Lista NAO vazia de objetos com `id` inteiro (o que a normalizacao exige)."""
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
    """Problema (texto) ou None. Lista de objetos com id.exercicio inteiro e id.entidade.id = a entidade pedida."""
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
    """Problema (texto) ou None. Lista de grupos (objetos) cujo `list`, se presente, e lista."""
    problema = _lista_de_objetos(d, "publicações")
    if problema:
        return problema
    ruim = next((i for i, x in enumerate(d) if "list" in x and not isinstance(x["list"], list)), None)
    if ruim is not None:
        return f"publicações: o grupo {ruim} tem 'list' que não é lista"
    return None
