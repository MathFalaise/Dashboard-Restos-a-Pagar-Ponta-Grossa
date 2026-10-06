"""Processing runs: list them and delete ONE whole run, safely.

It never deletes individual rows nor anything from the raw layer. Flow:
    list -> choose (type, id) -> simulate -> confirm (repeated id) -> backup -> delete -> verify

A run "in use" (only removed with --permitir-mais-recente):
  * normalization: the most recent;
  * derivation: the most recent of each validity - the current one (no date) and the one for each "as it was on" date.
    An "as it was on" derivation created after the current one does not make the current one deletable.
"""
import hashlib

from . import banco

TABELAS_NORMALIZACAO = ["rp_registro", "movimentacao_lancamento", "rreo_valor", "rreo_extracao", "entidade_ref",
                        "exercicio_ref"]
TABELAS_DERIVACAO = ["rp_derivado", "movimentacao_interpretada", "anomalia", "espelhamento_par", "visao_valor",
                     "conciliacao_rreo", "verificacao"]
CAMADA0 = ["coletor_versao", "coleta", "resposta_bruta", "objeto_bruto", "esquema_versao", "evidencia_externa"]


class ExclusaoRecusada(Exception):
    pass


def listar(con):
    norm = []
    for nid, versao, quando in con.execute("SELECT id, normalizador_versao, executada_em FROM normalizacao_execucao ORDER BY id"):
        deps = [d for (d,) in con.execute("SELECT id FROM derivacao_execucao WHERE normalizacao_id=? ORDER BY id", (nid,))]
        linhas = sum(con.execute(f"SELECT COUNT(*) FROM {t} WHERE normalizacao_id=?", (nid,)).fetchone()[0]
                     for t in TABELAS_NORMALIZACAO)
        norm.append({"tipo": "normalizacao", "id": nid, "versao": versao, "executada_em": quando, "linhas": linhas,
                     "derivacoes_dependentes": deps})
    deriv = []
    for did, nid, versao, quando, vig, h in con.execute(
            "SELECT id, normalizacao_id, derivador_versao, executada_em, vigencia_em, hash_resultado "
            "FROM derivacao_execucao ORDER BY id"):
        linhas = sum(con.execute(f"SELECT COUNT(*) FROM {t} WHERE derivacao_id=?", (did,)).fetchone()[0]
                     for t in TABELAS_DERIVACAO)
        deriv.append({"tipo": "derivacao", "id": did, "normalizacao_id": nid, "versao": versao, "executada_em": quando,
                      "vigencia_em": vig, "hash_resultado": h, "linhas": linhas})
    return {"normalizacoes": norm, "derivacoes": deriv}


def hash_camada0(con):
    h = hashlib.sha256()
    for t in CAMADA0:
        for row in con.execute(f"SELECT * FROM {t} ORDER BY 1"):
            h.update(repr(row).encode())
    return h.hexdigest()


def plano(con, tipo, ident, permitir_mais_recente=False):
    """What would be deleted. Refuses anything not clearly identified or still in use."""
    if tipo == "derivacao":
        tabela_exec, col, tabelas = "derivacao_execucao", "derivacao_id", TABELAS_DERIVACAO
    elif tipo == "normalizacao":
        tabela_exec, col, tabelas = "normalizacao_execucao", "normalizacao_id", TABELAS_NORMALIZACAO
    else:
        raise ExclusaoRecusada(f"tipo desconhecido: {tipo!r} (use 'normalizacao' ou 'derivacao')")
    if isinstance(ident, bool) or not isinstance(ident, int):
        raise ExclusaoRecusada(f"id precisa ser inteiro: {ident!r}")
    if not con.execute(f"SELECT 1 FROM {tabela_exec} WHERE id=?", (ident,)).fetchone():
        raise ExclusaoRecusada(f"{tipo} {ident} não existe")
    if tipo == "normalizacao":
        deps = [d for (d,) in con.execute("SELECT id FROM derivacao_execucao WHERE normalizacao_id=?", (ident,))]
        if deps:
            raise ExclusaoRecusada(f"normalização {ident} ainda tem derivações dependentes {deps}: apague-as antes")
        ultima = con.execute("SELECT MAX(id) FROM normalizacao_execucao").fetchone()[0]
        grupo = ""
    else:
        (vig,) = con.execute("SELECT vigencia_em FROM derivacao_execucao WHERE id=?", (ident,)).fetchone()
        ultima = con.execute("SELECT MAX(id) FROM derivacao_execucao WHERE vigencia_em IS ?", (vig,)).fetchone()[0]
        grupo = f" da vigencia {vig or 'atual'}"
    if ident == ultima and not permitir_mais_recente:
        raise ExclusaoRecusada(f"{tipo} {ident} é a mais recente (em uso){grupo}; use --permitir-mais-recente se for isso mesmo")
    return {"tipo": tipo, "id": ident, "tabela_execucao": tabela_exec, "coluna": col,
            "linhas": {t: con.execute(f"SELECT COUNT(*) FROM {t} WHERE {col}=?", (ident,)).fetchone()[0] for t in tabelas}}


def apagar(con, cfg, tipo, ident, confirmar, permitir_mais_recente=False):
    if confirmar != ident:
        raise ExclusaoRecusada(f"confirmação ({confirmar}) não confere com o id ({ident}); nada foi apagado")
    p = plano(con, tipo, ident, permitir_mais_recente)
    antes = hash_camada0(con)
    arq = banco.backup(con, cfg, f"antes-apagar-{tipo}-{ident}", operacional=True)
    with con:
        for t in p["linhas"]:
            con.execute(f"DELETE FROM {t} WHERE {p['coluna']}=?", (ident,))
        con.execute(f"DELETE FROM {p['tabela_execucao']} WHERE id=?", (ident,))
    restantes = {t: con.execute(f"SELECT COUNT(*) FROM {t} WHERE {p['coluna']}=?", (ident,)).fetchone()[0] for t in p["linhas"]}
    return {"apagado": p, "backup": str(arq), "restantes": restantes,
            "camada0_intacta": hash_camada0(con) == antes}
