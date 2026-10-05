"""Gravacao de um snapshot: o UNICO caminho de escrita da camada bruta.

Usado pelo coletor (respostas vindas do portal) e pelo importador (respostas
baixadas nas Etapas 01/02). Ordem: objetos -> manifesto (imutavel) -> banco.
"""
import json
import uuid

from . import banco
from .armazem import FORMATO


def _item(ordem, r, armazem):
    h = armazem.gravar_objeto(r["corpo"])
    return {"ordem": ordem, "url": r["url"], "http_status": r.get("http_status"),
            "cabecalhos": r.get("cabecalhos") or {}, "recebida_em": r.get("recebida_em"),
            "tentativas": r.get("tentativas", 1), "sha256": h, "tamanho": len(r["corpo"])}


def gravar_snapshot(con, armazem, *, tipo, endpoint, parametros, coletada_em, origem_carimbo, status, coletor,
                    respostas, observacao=None, snapshot_uid=None, segunda_leitura=None, finalizada_em=None,
                    contrato_api=None):
    """respostas: lista de dicts {url, http_status, cabecalhos, recebida_em, corpo(bytes), tentativas}.
    segunda_leitura (auditoria COL-01): as mesmas paginas lidas de novo para conferir que a base nao mudou durante a
    paginacao; os bytes vao para o armazem e o manifesto guarda a lista em "segunda_leitura" (com "igual" por
    pagina). Ficam FORA de "respostas": nao entram no banco nem na normalizacao.
    finalizada_em e contrato_api (revisao critica, itens 17, 18 e 50): quando a ultima resposta foi gravada
    (`coletada_em` e o INICIO; entre os dois a base pode ter mudado) e a forma das respostas JSON. Os dois campos sao
    aditivos, como "segunda_leitura": manifestos antigos continuam validos, e o banco e a normalizacao os ignoram."""
    uid = snapshot_uid or uuid.uuid4().hex
    itens = [_item(ordem, r, armazem) for ordem, r in enumerate(respostas)]
    m = {"formato": FORMATO, "snapshot_uid": uid, "tipo": tipo, "endpoint": endpoint, "parametros": parametros,
         "coletada_em": coletada_em, "origem_carimbo": origem_carimbo, "status": status, "coletor": coletor,
         "observacao": observacao, "respostas": itens}
    if finalizada_em is not None:
        m["coleta_finalizada_em"] = finalizada_em
    if contrato_api is not None:
        m["contrato_api"] = contrato_api
    if segunda_leitura is not None:
        m["segunda_leitura"] = [{**_item(r["ordem"], r, armazem), "igual": r["igual"]} for r in segunda_leitura]
    rel = armazem.gravar_manifesto(m)
    cid, _ = banco.registrar_manifesto(con, armazem, rel, m)
    return {"coleta_id": cid, "snapshot_uid": uid, "status": status, "manifesto": rel, "respostas": len(itens),
            "observacao": observacao}


def status_de_paginas(corpos, chave_unica=False):
    """'completa' se a ultima pagina diz last=true e a soma de content = totalElements (mesma regra do coletor).
    `chave_unica` (listagem de RP): a chave de negocio (entidade, anoempenho, empenho) nao pode repetir no retrato -
    repetida, 'incompleta', como no coletor (revisao critica, itens 1 e 2)."""
    from .contrato import chave_negocio
    try:
        ds = [json.loads(c) for c in corpos]
        total = ds[0]["totalElements"]
        ok = (ds[-1].get("last") and all(d["totalElements"] == total for d in ds)
              and sum(len(d["content"]) for d in ds) == total)
        if ok and chave_unica:
            chaves = [chave_negocio(x) for d in ds for x in d["content"]]
            ok = len(chaves) == len(set(chaves))
    except (ValueError, KeyError, TypeError, IndexError, AttributeError, RecursionError):
        return "falhou"
    return "completa" if ok else "incompleta"
