"""Gravacao de um snapshot: o UNICO caminho de escrita da camada bruta.

Usado pelo coletor (respostas vindas do portal) e pelo importador (respostas
baixadas nas Etapas 01/02). Ordem: objetos -> manifesto (imutavel) -> banco.
"""
import json
import uuid

from . import banco
from .armazem import FORMATO


def gravar_snapshot(con, armazem, *, tipo, endpoint, parametros, coletada_em, origem_carimbo, status, coletor,
                    respostas, observacao=None, snapshot_uid=None):
    """respostas: lista de dicts {url, http_status, cabecalhos, recebida_em, corpo(bytes), tentativas}."""
    uid = snapshot_uid or uuid.uuid4().hex
    itens = []
    for ordem, r in enumerate(respostas):
        h = armazem.gravar_objeto(r["corpo"])
        itens.append({"ordem": ordem, "url": r["url"], "http_status": r.get("http_status"),
                      "cabecalhos": r.get("cabecalhos") or {}, "recebida_em": r.get("recebida_em"),
                      "tentativas": r.get("tentativas", 1), "sha256": h, "tamanho": len(r["corpo"])})
    m = {"formato": FORMATO, "snapshot_uid": uid, "tipo": tipo, "endpoint": endpoint, "parametros": parametros,
         "coletada_em": coletada_em, "origem_carimbo": origem_carimbo, "status": status, "coletor": coletor,
         "observacao": observacao, "respostas": itens}
    rel = armazem.gravar_manifesto(m)
    cid, _ = banco.registrar_manifesto(con, armazem, rel, m)
    return {"coleta_id": cid, "snapshot_uid": uid, "status": status, "manifesto": rel, "respostas": len(itens),
            "observacao": observacao}


def status_de_paginas(corpos):
    """'completa' se a ultima pagina diz last=true e a soma de content = totalElements (mesma regra do coletor)."""
    try:
        ds = [json.loads(c) for c in corpos]
        total = ds[0]["totalElements"]
        ok = (ds[-1].get("last") and all(d["totalElements"] == total for d in ds)
              and sum(len(d["content"]) for d in ds) == total)
    except (ValueError, KeyError, TypeError, IndexError, AttributeError, RecursionError):
        return "falhou"
    return "completa" if ok else "incompleta"
