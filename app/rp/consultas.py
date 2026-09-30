"""Consultas temporais sobre snapshots ("como estava em")."""
from .derivar import coletas_vigentes

CAMPOS = ["proc_c", "aproc_c", "cancelado_proc_c", "pago_proc_c", "pago_proc_estornado_c", "cancelado_aproc_c",
          "pago_aproc_c", "pago_aproc_estornado_c", "liquidado_c", "retencao_c"]


def snapshot_em(con, entidade, exercicio, data_inicial, data_final, em=None):
    """Id da coleta que o portal mostrava para o corte na data `em` (ou a mais recente)."""
    return coletas_vigentes(con, em).get((entidade, exercicio, data_inicial, data_final))


def historico(con, entidade, exercicio, data_inicial, data_final):
    return con.execute(
        "SELECT id, coletada_em, origem_carimbo FROM coleta WHERE tipo='rp_listagem' AND status='completa' "
        "AND tipo_pesquisa IS NULL AND entidade=? AND exercicio=? AND data_inicial=? AND data_final=? "
        "ORDER BY coletada_em, snapshot_uid", (entidade, exercicio, data_inicial, data_final)).fetchall()


def diferencas(con, nid, coleta_1, coleta_2):
    """O que mudou entre dois snapshots do mesmo corte: chaves novas, sumidas e campos alterados."""
    def carregar(cid):
        cur = con.execute(f"SELECT entidade, anoempenho, empenho, {','.join(CAMPOS)} FROM rp_registro "
                          "WHERE normalizacao_id=? AND coleta_id=?", (nid, cid))
        return {r[:3]: dict(zip(CAMPOS, r[3:])) for r in cur}
    a, b = carregar(coleta_1), carregar(coleta_2)
    alterados = sorted((k, c, a[k][c], b[k][c]) for k in a.keys() & b.keys() for c in CAMPOS if a[k][c] != b[k][c])
    return {"novos": sorted(b.keys() - a.keys()), "sumidos": sorted(a.keys() - b.keys()), "alterados": alterados}
