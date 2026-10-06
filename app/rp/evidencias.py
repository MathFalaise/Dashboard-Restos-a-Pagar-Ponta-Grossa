"""External evidence: an e-SIC answer, a regulation, a technical note, an official document, a formal explanation
from the Municipality.

Recording an evidence = keeping the FILE (bytes, in the store, addressed by SHA-256), writing an immutable manifest in
evidencias/ and recording the row in evidencia_externa. Like snapshots, evidence is never overwritten or deleted, and
the database rebuilds it from the store (banco.sincronizar).

Governance rule: no new rule relies on an external document unless it is recorded here; the decision in
regra_situacao points to the evidence id.
"""
import re
import uuid
from datetime import date
from pathlib import Path

from . import agora, banco
from .armazem import FORMATO_EVIDENCIA, TIPOS_EVIDENCIA


class EvidenciaInvalida(ValueError):
    pass


def registrar(con, armazem, *, tipo, descricao, arquivo, origem, data_documento=None, observacao=None):
    """Records `arquivo` as external evidence. Returns {evidencia_id, evidencia_uid, sha256, manifesto}."""
    if tipo not in TIPOS_EVIDENCIA:
        raise EvidenciaInvalida(f"tipo precisa ser um de {sorted(TIPOS_EVIDENCIA)}: {tipo!r}")
    for nome, valor in (("descricao", descricao), ("origem", origem)):
        if not isinstance(valor, str) or not valor.strip():
            raise EvidenciaInvalida(f"{nome} e obrigatoria")
    if data_documento is not None:
        try:
            date.fromisoformat(data_documento)
        except (TypeError, ValueError):
            raise EvidenciaInvalida(f"data_documento precisa ser AAAA-MM-DD: {data_documento!r}") from None
    p = Path(arquivo)
    corpo = p.read_bytes()
    h = armazem.gravar_objeto(corpo)
    m = {"formato": FORMATO_EVIDENCIA, "evidencia_uid": uuid.uuid4().hex, "tipo": tipo, "descricao": descricao.strip(),
         "data_documento": data_documento, "arquivo_original": _nome_seguro(p.name), "sha256": h, "tamanho": len(corpo),
         "origem": origem.strip(), "observacao": observacao, "registrada_em": agora()}
    rel = armazem.gravar_manifesto_evidencia(m)
    eid, _ = banco.registrar_evidencia(con, armazem, rel, m)
    return {"evidencia_id": eid, "evidencia_uid": m["evidencia_uid"], "sha256": h, "tamanho": len(corpo), "manifesto": rel}


def _nome_seguro(nome):
    """Only the file name (no folder), with control characters removed."""
    return re.sub(r"[\x00-\x1f\x7f]", "", nome)[:255] or "arquivo"
