"""Evidencia externa: resposta de e-SIC, norma, nota tecnica, documento oficial, explicacao formal do Municipio.

Registrar uma evidencia = guardar o ARQUIVO (bytes, no armazem, enderecado pelo SHA-256), escrever um manifesto
imutavel em evidencias/ e registrar a linha em evidencia_externa. Como os snapshots, a evidencia nunca e
sobrescrita nem apagada, e o banco a reconstroi a partir do armazem (banco.sincronizar).

Regra de governanca: nenhuma regra nova se apoia em documento externo sem que ele esteja registrado aqui;
a decisao em regra_situacao aponta para o id da evidencia.
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
    """Registra `arquivo` como evidencia externa. Devolve {evidencia_id, evidencia_uid, sha256, manifesto}."""
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
    """So o nome do arquivo (sem pasta), com caracteres de controle removidos."""
    return re.sub(r"[\x00-\x1f\x7f]", "", nome)[:255] or "arquivo"
