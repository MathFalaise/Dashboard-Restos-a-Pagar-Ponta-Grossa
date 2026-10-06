"""Writing a snapshot: the ONLY write path of the raw layer.

Used by the collector (responses from the portal) and by the importer (responses downloaded in stages 01/02).
Order: objects -> manifest (immutable) -> database.
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
    """respostas: list of dicts {url, http_status, cabecalhos, recebida_em, corpo(bytes), tentativas}.
    segunda_leitura (audit COL-01): the same pages read again to check that the base did not change during
    pagination; the bytes go to the store and the manifest keeps the list in "segunda_leitura" (with "igual" per
    page). They stay OUT of "respostas": they enter neither the database nor the normalization.
    finalizada_em and contrato_api (critical review, items 17, 18 and 50): when the last response was recorded
    (`coletada_em` is the START; the base may have changed in between) and the shape of the JSON responses. Both
    fields are additive, like "segunda_leitura": older manifests stay valid, and the database and the normalization
    ignore them."""
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
    """'completa' if the last page says last=true and the sum of content = totalElements (same rule as the collector).
    `chave_unica` (RP listing): the business key (entidade, anoempenho, empenho) cannot repeat in the snapshot -
    repeated means 'incompleta', as in the collector (critical review, items 1 and 2)."""
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
