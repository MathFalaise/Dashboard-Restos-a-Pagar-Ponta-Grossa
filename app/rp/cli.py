"""Linha de comando: python -m rp <comando> (rodar dentro de app/)."""
import argparse
import json
import logging
import sys
from datetime import datetime

from . import BRT, VERSAO, banco
from .armazem import Armazem, ManifestoInvalido, ObjetoCorrompido
from .coletor import Coletor, ParametroInvalido
from .comparador import CorteDiferente
from .config import ConfiguracaoInvalida, carregar
from .execucoes import ExclusaoRecusada
from .http import Cliente

ERROS_ESPERADOS = (ParametroInvalido, CorteDiferente, ExclusaoRecusada, ConfiguracaoInvalida, banco.MigracaoPendente,
                   banco.BancoEmPastaSincronizada, ManifestoInvalido, ObjetoCorrompido, FileExistsError,
                   FileNotFoundError, KeyError)


def _logs(cfg):
    cfg.logs.mkdir(parents=True, exist_ok=True)
    arq = cfg.logs / f"rp-{datetime.now(BRT):%Y-%m-%d}.log"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(arq, encoding="utf-8"), logging.StreamHandler(sys.stderr)])


def main(argv=None):
    """Executa um comando. Codigos de saida: 0 ok; 1 `verificar` achou problema; 2 coleta incompleta ou com falha;
    3 exclusao recusada; 4 comando recusado (parametro, configuracao, corte, arquivo existente...), com uma linha
    JSON {"erro": ...} na saida e o detalhe completo no log.
    Caractere que a codificacao da saida nao representa (ex.: cp1252 com saida redirecionada para arquivo) sai
    como escape \\uXXXX, em vez de derrubar o programa depois do trabalho feito."""
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(errors="backslashreplace")
    try:
        return _main(argv)
    except ERROS_ESPERADOS as e:
        logging.getLogger("rp.cli").exception("comando recusado")
        print(json.dumps({"erro": type(e).__name__, "mensagem": str(e)}, ensure_ascii=False))
        return 4


def _main(argv=None):
    ap = argparse.ArgumentParser(prog="rp", description=f"Restos a Pagar de Ponta Grossa — coletor {VERSAO}")
    ap.add_argument("--config")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("iniciar", help="cria pastas e banco (se não existirem)")
    p = sub.add_parser("coletar-catalogos")
    p.add_argument("--entidades", type=int, nargs="*")
    p = sub.add_parser("coletar-listagem")
    p.add_argument("--entidade", type=int, required=True)
    p.add_argument("--exercicio", type=int, required=True)
    p.add_argument("--data-final", required=True)
    p = sub.add_parser("coletar-rreo")
    p.add_argument("--exercicio", type=int, required=True)
    p.add_argument("--entidade", type=int, default=1)
    p.add_argument("--ids", type=int, nargs="*", help="só estes idArquivo")
    p.add_argument("--sem-pdf", action="store_true")
    p.add_argument("--bimestres", type=int, nargs="*", help="só PDFs destes bimestres (ex.: 6)")
    p = sub.add_parser("recoletar", help="nova coleta de um corte com EXATAMENTE os parâmetros de um snapshot anterior")
    p.add_argument("--snapshot", required=True, help="snapshot_uid ou id da coleta original")
    p = sub.add_parser("comparar", help="compara dois snapshots do mesmo corte (somente leitura)")
    p.add_argument("--a", required=True, help="snapshot anterior (uid ou id)")
    p.add_argument("--b", required=True, help="snapshot posterior (uid ou id)")
    p.add_argument("--saida", help="grava o relatório completo em JSON")
    p = sub.add_parser("coletar-movimentacao")
    p.add_argument("--entidade", type=int, required=True)
    p.add_argument("--anoempenho", type=int, required=True)
    p.add_argument("--empenho", type=int, required=True)
    p = sub.add_parser("backup")
    p.add_argument("--motivo", default="manual")
    sub.add_parser("verificar", help="integridade do armazém e do banco")
    sub.add_parser("sincronizar", help="registra no banco manifestos que ainda não estão nele")
    p = sub.add_parser("reconstruir", help="banco novo só a partir do armazém (nunca sobrescreve)")
    p.add_argument("--destino", required=True)
    sub.add_parser("situacao")
    p = sub.add_parser("processar", help="normalização + derivação sobre os snapshots do banco")
    p.add_argument("--em", help="vigência 'como estava em' (ISO com fuso, ex. 2026-09-29T23:59:59-03:00)")
    p.add_argument("--normalizacao", type=int, help="derivar sobre esta normalização (sem normalizar de novo)")
    sub.add_parser("execucoes", help="lista normalizações e derivações")
    p = sub.add_parser("apagar-execucao", help="apaga UMA execução inteira (nunca linhas avulsas nem bruto)")
    p.add_argument("--tipo", choices=["normalizacao", "derivacao"], required=True)
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--confirmar", type=int, help="repita o id para confirmar")
    p.add_argument("--simular", action="store_true", help="só mostra o que seria apagado")
    p.add_argument("--permitir-mais-recente", action="store_true")
    sub.add_parser("importar-etapas-anteriores", help="bruto das Etapas 01/02 como snapshots históricos")
    sub.add_parser("compactar", help="VACUUM: devolve ao disco o espaço de execuções apagadas")
    p = sub.add_parser("comparar-snapshots", help="retratos do mesmo corte: bytes e registros")
    p.add_argument("--entidade", type=int, required=True)
    p.add_argument("--exercicio", type=int, required=True)
    p.add_argument("--data-final", required=True)
    a = ap.parse_args(argv)

    cfg = carregar(a.config)
    _logs(cfg)
    armazem = Armazem(cfg.snapshots)
    if a.cmd == "reconstruir":
        con, n = banco.reconstruir(cfg, armazem, a.destino)
        print(json.dumps({"destino": a.destino, "snapshots_registrados": n, "problemas": banco.verificar(con, armazem)},
                         ensure_ascii=False, indent=1))
        return 0
    con = banco.abrir(cfg)
    if a.cmd == "iniciar":
        cfg.snapshots.mkdir(parents=True, exist_ok=True)
        cfg.backups.mkdir(parents=True, exist_ok=True)
        print(json.dumps({"banco": str(cfg.banco), "snapshots": str(cfg.snapshots), "backups": str(cfg.backups),
                          "logs": str(cfg.logs)}, ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "backup":
        print(banco.backup(con, cfg, a.motivo))
        return 0
    if a.cmd == "verificar":
        problemas = banco.verificar(con, armazem)
        print(json.dumps({"problemas": problemas}, ensure_ascii=False, indent=1))
        return 1 if problemas else 0
    if a.cmd == "sincronizar":
        print(json.dumps({"novos": banco.sincronizar(con, armazem)}))
        return 0
    if a.cmd == "execucoes":
        from . import execucoes
        print(json.dumps(execucoes.listar(con), ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "apagar-execucao":
        from . import execucoes
        try:  # recusa tem saida propria (codigo 3), mantida por compatibilidade
            if a.simular:
                r = {"simulacao": execucoes.plano(con, a.tipo, a.id, a.permitir_mais_recente)}
            else:
                r = execucoes.apagar(con, cfg, a.tipo, a.id, a.confirmar, a.permitir_mais_recente)
                r["integridade"] = banco.verificar(con, armazem)
        except execucoes.ExclusaoRecusada as e:
            print(json.dumps({"recusado": str(e)}, ensure_ascii=False, indent=1))
            return 3
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "comparar":
        from . import comparador
        r = comparador.comparar(con, a.a, a.b)
        if a.saida:  # modo "x": nunca sobrescreve um arquivo existente
            with open(a.saida, "x", encoding="utf-8") as f:
                f.write(json.dumps(r, ensure_ascii=False, indent=1, default=str))
        resumo = {k: r[k] for k in ("corte", "anterior", "posterior", "bytes_identicos", "contagens", "impacto_financeiro_por_grupo", "saldo_s1")}
        print(json.dumps(resumo, ensure_ascii=False, indent=1, default=str))
        return 0
    if a.cmd == "compactar":
        antes, depois = banco.compactar(con, cfg.banco)
        print(json.dumps({"bytes_antes": antes, "bytes_depois": depois, "problemas": banco.verificar(con, armazem)}))
        return 0
    if a.cmd == "importar-etapas-anteriores":
        from . import importar
        from .config import RAIZ_APP
        arq = banco.backup(con, cfg, "antes-importar-etapas-anteriores")
        r = importar.importar_etapas_anteriores(con, armazem, RAIZ_APP.parent)
        print(json.dumps({"backup": str(arq), "novos": r, "problemas": banco.verificar(con, armazem)}, ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "comparar-snapshots":
        from . import consultas
        di = f"{a.exercicio}-01-01"
        hist = consultas.historico(con, a.entidade, a.exercicio, di, a.data_final)
        nid = con.execute("SELECT MAX(id) FROM normalizacao_execucao").fetchone()[0]
        shas = lambda c: [s for (s,) in con.execute("SELECT sha256 FROM resposta_bruta WHERE coleta_id=? ORDER BY ordem", (c,))]
        out = {"corte": [a.entidade, a.exercicio, di, a.data_final], "retratos": hist, "comparacoes": []}
        for (c1, t1, _), (c2, t2, _) in zip(hist, hist[1:]):
            d = consultas.diferencas(con, nid, c1, c2) if nid else None
            out["comparacoes"].append({"de": t1, "para": t2, "bytes_identicos": shas(c1) == shas(c2),
                                       "novos": len(d["novos"]) if d else None, "sumidos": len(d["sumidos"]) if d else None,
                                       "campos_alterados": len(d["alterados"]) if d else None,
                                       "exemplos": (d["novos"][:3] + d["sumidos"][:3] + d["alterados"][:5]) if d else None})
        print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
        return 0
    if a.cmd == "processar":
        from . import derivar, normalizar
        if a.normalizacao:
            nid, resumo = a.normalizacao, {"reusada": a.normalizacao}
        else:
            nid, resumo = normalizar.normalizar(con)
        did = derivar.derivar(con, nid, a.em)
        h = con.execute("SELECT hash_resultado FROM derivacao_execucao WHERE id=?", (did,)).fetchone()[0]
        verif = con.execute("SELECT descricao, escopo_json, verificados, falhas FROM verificacao WHERE derivacao_id=?",
                            (did,)).fetchall()
        print(json.dumps({"normalizacao": nid, "resumo": resumo, "derivacao": did, "hash_resultado": h,
                          "verificacoes": verif}, ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "situacao":
        r = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
             for t in ("coleta", "resposta_bruta", "objeto_bruto", "coletor_versao")}
        r["por_tipo_status"] = con.execute("SELECT tipo, status, COUNT(*) FROM coleta GROUP BY 1,2").fetchall()
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0

    coletor = Coletor(cfg, con, armazem, Cliente(cfg))
    if a.cmd == "coletar-catalogos":
        r = coletor.catalogos(a.entidades or cfg.entidades)
    elif a.cmd == "coletar-listagem":
        r = [coletor.listagem(a.entidade, a.exercicio, a.data_final)]
    elif a.cmd == "coletar-rreo":
        r = coletor.rreo(a.exercicio, a.entidade, set(a.ids) if a.ids else None, not a.sem_pdf,
                         set(a.bimestres) if a.bimestres else None)
    elif a.cmd == "recoletar":
        r = [coletor.recoletar(a.snapshot)]
    elif a.cmd == "coletar-movimentacao":
        r = [coletor.movimentacao(a.entidade, a.anoempenho, a.empenho)]
    print(json.dumps({"snapshots": r, "requisicoes": coletor.cliente.requisicoes}, ensure_ascii=False, indent=1))
    return 0 if all(s["status"] == "completa" for s in r) else 2
