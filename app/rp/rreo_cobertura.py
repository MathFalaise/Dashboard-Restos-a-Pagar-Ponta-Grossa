"""Coverage matrix of the RREO Annex VII documents (correction request of 09/10/2026, item 6). READ-ONLY.

Expected = every file of the "Anexo VII - Demonstrativo dos Restos a Pagar" subgroup in the most recent complete
publications list of each fiscal year (coletor.anexo_vii). For each one, the situation in the database:

  transcrito             collected and transcribed by the production extractor of the normalization (all rows whole,
                         the document's identities closing - extractor v2);
  recusado_layout        collected, but the extractor refused it (reason recorded in rreo_extracao): no value;
  coletado_sem_extracao  collected, but the normalization has no extraction row for it (e.g. not processed yet);
  nao_coletado           listed by the portal, never collected: no independent check for that document.

'Conferido' (checked against the original document by an independent method) is NOT decided here: the production
code would be checking itself. The independent check lives in docs/audits/rreo/ (another PDF engine, Poppler).
"""
import json
import re

from . import banco
from .coletor import anexo_vii

SITUACOES = ("transcrito", "recusado_layout", "coletado_sem_extracao", "nao_coletado")


def _bimestre(rotulo):
    m = re.match(r"\s*(\d)\s*º?\s*bimestre", str(rotulo or ""), re.I)
    return int(m.group(1)) if m else None


def matriz(con, nid=None):
    """{"documentos": [...], "resumo": {situation: n}, "por_exercicio": {year: {situation: n}}, "normalizacao": nid}."""
    if nid is None:
        nid = con.execute("SELECT MAX(id) FROM normalizacao_execucao").fetchone()[0]
    listas = {}
    for cid, ex, ent, sha in con.execute(
            "SELECT k.id, k.exercicio, k.entidade, r.sha256 FROM coleta k JOIN resposta_bruta r ON r.coleta_id = k.id "
            "WHERE k.tipo='publicacoes' AND k.status='completa' ORDER BY k.coletada_em, k.snapshot_uid"):
        listas[(ex, ent)] = (cid, sha)                      # the most recent complete list of each year stays
    coletados = {}
    for cid, arq, uid in con.execute("SELECT id, id_arquivo, snapshot_uid FROM coleta WHERE tipo='rreo_pdf' AND "
                                     "status='completa' ORDER BY coletada_em, snapshot_uid"):
        coletados[arq] = (cid, uid)                         # the most recent collection of each file stays
    extracao = {cid: (valores, erro) for cid, valores, erro in con.execute(
        "SELECT coleta_id, valores, erro FROM rreo_extracao WHERE normalizacao_id=?", (nid,))}
    docs = []
    for (ex, ent), (_, sha) in sorted(listas.items()):
        try:
            publicacoes = json.loads(banco.corpo(con, sha))
        except (ValueError, TypeError):
            continue
        for arq in anexo_vii(publicacoes):
            if not isinstance(arq, dict):
                continue
            ident, rotulo = arq.get("idArquivo"), arq.get("valor")
            item = {"exercicio": ex, "entidade_publicacoes": ent, "rotulo": rotulo, "bimestre": _bimestre(rotulo),
                    "escopo": "consolidado" if "consolidado" in str(rotulo).lower() else "entidade",
                    "id_arquivo": ident, "data_arquivo": arq.get("dataArquivo"), "snapshot": None, "motivo": None}
            if ident not in coletados:
                item["situacao"] = "nao_coletado"
            else:
                cid, uid = coletados[ident]
                item["snapshot"] = uid
                valores, erro = extracao.get(cid, (None, None))
                if valores is None and erro is None:
                    item["situacao"] = "coletado_sem_extracao"
                elif erro:
                    item["situacao"], item["motivo"] = "recusado_layout", erro
                else:
                    item["situacao"] = "transcrito"
                    item["valores"] = valores
            docs.append(item)
    resumo = {s: sum(1 for d in docs if d["situacao"] == s) for s in SITUACOES}
    por_exercicio = {}
    for d in docs:
        por_exercicio.setdefault(d["exercicio"], {s: 0 for s in SITUACOES})[d["situacao"]] += 1
    return {"normalizacao": nid, "documentos": docs, "resumo": {"esperados": len(docs), **resumo},
            "por_exercicio": por_exercicio}
