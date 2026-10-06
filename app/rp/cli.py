"""Command line: python -m rp <command> (run inside app/)."""
import argparse
import json
import logging
import re
import sys
from datetime import date, datetime
from pathlib import Path

from . import BRT, VERSAO, DataInvalida, banco, instante
from .armazem import TIPOS_EVIDENCIA, Armazem, ManifestoInvalido, ObjetoCorrompido
from .coletor import Coletor, ParametroInvalido
from .comparador import CorteDiferente
from .config import ConfiguracaoInvalida, carregar
from .evidencias import EvidenciaInvalida
from .execucoes import ExclusaoRecusada
from .governanca import SITUACOES, STATUS, DecisaoInvalida
from .http import Cliente
from .painel.consulta import ErroDoPainel

ERROS_ESPERADOS = (ParametroInvalido, CorteDiferente, ExclusaoRecusada, ConfiguracaoInvalida, banco.MigracaoPendente,
                   banco.BancoEmPastaSincronizada, ManifestoInvalido, ObjetoCorrompido, FileExistsError,
                   FileNotFoundError, KeyError, EvidenciaInvalida, ErroDoPainel, DataInvalida, DecisaoInvalida)
CONSULTAS_PAINEL = ("contexto", "cortes", "entidades", "indicadores", "evolucao", "dimensao", "empenhos", "empenho",
                    "fornecedores", "pares", "retratos", "comparar-retratos", "reconciliacao", "coerencia", "analitica",
                    "regras", "evidencias", "fontes", "metodologia", "dicionario")


# Logs: one file per day; the ones older than RETENCAO_LOGS_DIAS days are removed on startup (critical review, D6).
# Per day, not per size: on Windows, rotating a file that another process has open (the interface and a
# collection at the same time) fails.
RETENCAO_LOGS_DIAS = 90
_LOG_DO_DIA = re.compile(r"^rp-(\d{4}-\d{2}-\d{2})\.log$")


def podar_logs(pasta, hoje, dias=RETENCAO_LOGS_DIAS):
    """Deletes rp-YYYY-MM-DD.log dated before `hoje` - `dias`. No other file in the folder is ever touched."""
    removidos = []
    for p in sorted(Path(pasta).glob("rp-*.log")):
        m = _LOG_DO_DIA.match(p.name)
        if m and (hoje - date.fromisoformat(m.group(1))).days > dias:
            p.unlink()
            removidos.append(p.name)
    return removidos


def _logs(cfg):
    cfg.logs.mkdir(parents=True, exist_ok=True)
    podar_logs(cfg.logs, datetime.now(BRT).date())
    arq = cfg.logs / f"rp-{datetime.now(BRT):%Y-%m-%d}.log"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(arq, encoding="utf-8"), logging.StreamHandler(sys.stderr)])


def main(argv=None):
    """Runs a command. Exit codes: 0 ok; 1 `verificar` found a problem (or: `portoes` not fit, `comparar-bancos`
    different, `diagnosticar-api` saw the API change); 2 incomplete or failed collection (or: `diagnosticar-api`
    could not query); 3 deletion refused; 4 command refused (parameter, config, cut-off, existing file...), with a
    JSON line {"erro": ...} on the output and the full detail in the log.
    A character the output encoding cannot represent (e.g. cp1252 with output redirected to a file) comes out as a
    \\uXXXX escape, instead of crashing the program after the work is done."""
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
    p.add_argument("--entidade", type=int, help="padrao: [rreo] entidade_publicacoes do config.toml")
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
    p = sub.add_parser("comprimir-backups", help="comprime (gzip conferido) os backups operacionais antigos; "
                                                 "sem --confirmar so lista")
    p.add_argument("--manter", type=int, default=3, help="os N mais recentes ficam sem comprimir (padrao 3)")
    p.add_argument("--confirmar", action="store_true")
    p = sub.add_parser("comparar-snapshots", help="retratos do mesmo corte: bytes e registros")
    p.add_argument("--entidade", type=int, required=True)
    p.add_argument("--exercicio", type=int, required=True)
    p.add_argument("--data-final", required=True)
    p = sub.add_parser("decidir-regra", help="acrescenta uma decisao de governanca sobre uma versao de regra "
                                             "(nunca edita); promocao a operacional segue a decisao D7")
    p.add_argument("--codigo", required=True)
    p.add_argument("--versao", type=int, required=True)
    p.add_argument("--situacao", choices=SITUACOES, required=True)
    p.add_argument("--status", choices=STATUS, required=True, help="status da evidencia")
    p.add_argument("--compoe-indicador", action="store_true", help="compoe o indicador publicado (so operacional)")
    p.add_argument("--motivo", required=True)
    p.add_argument("--fonte", required=True, help="evidencia documentada (relatorio, secao)")
    p.add_argument("--origem", default="decisao do responsavel pelo projeto")
    p.add_argument("--teste", help="teste de regressao: tests/<arquivo>.py::<teste> (obrigatorio na promocao)")
    p.add_argument("--evidencia", type=int, help="id da evidencia externa da conferencia independente")
    p.add_argument("--ressalva", help="sem conferencia independente no prazo: o motivo (aparece na metodologia)")
    p = sub.add_parser("registrar-evidencia", help="registra documento externo (e-SIC, norma, nota...) com SHA-256")
    p.add_argument("--tipo", choices=sorted(TIPOS_EVIDENCIA), required=True)
    p.add_argument("--descricao", required=True)
    p.add_argument("--arquivo", required=True)
    p.add_argument("--origem", required=True, help="quem emitiu ou de onde veio (ex.: e-SIC protocolo n.)")
    p.add_argument("--data", help="data do documento (AAAA-MM-DD)")
    p.add_argument("--observacao")
    p = sub.add_parser("painel", help="camada de consulta do dashboard: somente leitura, saida JSON")
    p.add_argument("consulta", choices=CONSULTAS_PAINEL)
    p.add_argument("--banco", help="padrao: banco ativo do config.toml (aberto so para leitura)")
    p.add_argument("--nivel", choices=["publico", "interno"], default="publico",
                   help="'interno' inclui identificacao do credor; use so fora de publicacao")
    p.add_argument("--exercicio", type=int)
    p.add_argument("--data-final")
    p.add_argument("--entidade", type=int)
    p.add_argument("--em", help="'como a base estava em' (AAAA-MM-DD = fim do dia, ou ISO com fuso)")
    p.add_argument("--dimensao")
    p.add_argument("--anoempenho", type=int)
    p.add_argument("--empenho", type=int)
    p.add_argument("--escopo", choices=["entidade", "consolidado"])
    p.add_argument("--somente-diferencas", action="store_true")
    p.add_argument("--limite", type=int, default=100)
    p.add_argument("--deslocamento", type=int, default=0)
    p.add_argument("--ordem", choices=["saldo", "empenho"], default="saldo")
    p.add_argument("--a", help="snapshot_uid anterior (comparar-retratos)")
    p.add_argument("--b", help="snapshot_uid posterior (comparar-retratos)")
    p = sub.add_parser("interface", help="interface publica somente leitura (servidor local; nao consulta o portal)")
    p.add_argument("--banco", help="padrao: banco ativo do config.toml (aberto so para leitura)")
    p.add_argument("--host", default="127.0.0.1", help="padrao 127.0.0.1 (so esta maquina)")
    p.add_argument("--porta", type=int, default=8050)
    p = sub.add_parser("comparar-bancos", help="prova de equivalencia entre dois bancos, camada a camada, por "
                                               "identificadores estaveis (somente leitura)")
    p.add_argument("--outro", required=True, help="o outro banco (ex.: reconstruido do armazem)")
    p.add_argument("--banco", help="padrao: banco ativo do config.toml (aberto so para leitura)")
    p = sub.add_parser("portoes", help="portoes de qualidade antes de disponibilizar uma carga nova (somente leitura)")
    p.add_argument("--banco", help="padrao: banco ativo do config.toml (aberto so para leitura)")
    p.add_argument("--referencia", help="JSON gravado antes da carga (--gravar-referencia): confere o bruto anterior")
    p.add_argument("--gravar-referencia", help="grava o retrato do bruto atual neste arquivo (nunca sobrescreve) e sai")
    p = sub.add_parser("diagnosticar-api", help="confere se a API ainda responde como o coletor espera, sem gravar "
                                                "nada (saida 0 ok, 1 a API mudou, 2 nao deu para conferir)")
    p.add_argument("--entidade", type=int, help="padrao: a primeira entidade de [escopo] no config.toml")
    p.add_argument("--exercicio", type=int, help="padrao: o ano corrente")
    p.add_argument("--data-final", help="padrao: hoje (AAAA-MM-DD), no mesmo ano do exercicio")
    p.add_argument("--tamanho", type=int, help="registros na amostra da listagem (padrao 20)")
    p.add_argument("--banco", help="referencia da estrutura; padrao: banco ativo do config.toml (so leitura)")
    a = ap.parse_args(argv)

    cfg = carregar(a.config)
    _logs(cfg)
    if a.cmd == "painel":   # before banco.abrir: the panel never migrates nor writes
        return _painel(a, cfg)
    if a.cmd == "interface":   # same: the interface only reads, through the panel layer
        from .interface import servir
        servir(a.banco or cfg.banco, a.host, a.porta)
        return 0
    if a.cmd == "comparar-bancos":   # same: both databases opened read-only
        from . import equivalencia
        from .portoes import _abrir
        con_a, con_b = _abrir(a.banco or cfg.banco), _abrir(a.outro)
        try:
            r = equivalencia.comparar(con_a, con_b)
        finally:
            con_a.close()
            con_b.close()
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["equivalentes"] else 1
    if a.cmd == "portoes":     # same: read-only on the database and the store
        from . import portoes
        if a.gravar_referencia:
            print(json.dumps(portoes.gravar_referencia(a.banco or cfg.banco, a.gravar_referencia), indent=1))
            return 0
        ref = json.loads(open(a.referencia, encoding="utf-8").read()) if a.referencia else None
        r = portoes.avaliar(a.banco or cfg.banco, Armazem(cfg.snapshots), ref)
        print(json.dumps(r, ensure_ascii=False, indent=1, default=str))
        return 0 if r["apto"] else 1
    if a.cmd == "diagnosticar-api":   # same: queries the portal, but records no snapshot and does not open the database for writing
        return _diagnosticar_api(a, cfg)
    if a.cmd == "comprimir-backups":   # backup files only: does not open the database
        r = banco.comprimir_backups_operacionais(cfg, a.manter, simular=not a.confirmar)
        print(json.dumps({"simulado": not a.confirmar, "arquivos": r}, ensure_ascii=False, indent=1))
        return 0
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
        try:  # a refusal has its own exit code (3), kept for compatibility
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
        if a.saida:  # mode "x": never overwrites an existing file
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
        em = instante(a.em)   # same form as the panel layer; an invalid date is refused before normalizing (CLI-01)
        if a.normalizacao:
            nid, resumo = a.normalizacao, {"reusada": a.normalizacao}
        else:
            nid, resumo = normalizar.normalizar(con)
        did = derivar.derivar(con, nid, em)
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
        r["espaco_bytes"] = banco.espaco(cfg)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "decidir-regra":
        from . import governanca
        ident = governanca.registrar_decisao(con, a.codigo, a.versao, a.situacao, a.status, a.compoe_indicador, a.motivo,
                                             a.fonte, a.origem, evidencia_externa_id=a.evidencia,
                                             teste_regressao=a.teste, ressalva=a.ressalva)
        print(json.dumps({"decisao": ident, **governanca.situacao_atual(con)[(a.codigo, a.versao)]},
                         ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "registrar-evidencia":
        from . import evidencias
        r = evidencias.registrar(con, armazem, tipo=a.tipo, descricao=a.descricao, arquivo=a.arquivo, origem=a.origem,
                                 data_documento=a.data, observacao=a.observacao)
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


def _diagnosticar_api(a, cfg):
    """API contract diagnosis (diagnostico.py). Without an active database yet, only the structure stops being compared."""
    from . import diagnostico
    from .portoes import _abrir
    hoje = datetime.now(BRT).date()
    exercicio = a.exercicio or hoje.year
    data_final = a.data_final or (hoje.isoformat() if exercicio == hoje.year else f"{exercicio}-12-31")
    caminho = Path(a.banco or cfg.banco).expanduser()
    con = _abrir(caminho) if caminho.is_file() or a.banco else None
    try:
        r = diagnostico.diagnosticar(con, Cliente(cfg), a.entidade or cfg.entidades[0], exercicio, data_final,
                                     a.tamanho or diagnostico.TAMANHO_AMOSTRA)
    finally:
        if con is not None:
            con.close()
    if con is None:
        r["nota"] += f" Banco {caminho} não encontrado: estrutura não comparada."
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return diagnostico.CODIGO_DE_SAIDA[r["resultado"]]


def _exigir(a, *nomes):
    faltam = [f"--{n.replace('_', '-')}" for n in nomes if getattr(a, n) is None]
    if faltam:
        raise ErroDoPainel(f"a consulta '{a.consulta}' exige {', '.join(faltam)}")


def _painel(a, cfg):
    """Dashboard layer queries (read-only; never opens the database for writing)."""
    from .painel import Painel
    with Painel.abrir(a.banco or cfg.banco, a.nivel) as p:
        c = a.consulta
        if c == "contexto":
            r = p.contexto()
        elif c == "cortes":
            r = p.cortes(a.em)
        elif c == "entidades":
            r = p.entidades(a.exercicio, a.em)
        elif c == "indicadores":
            _exigir(a, "exercicio", "data_final")
            r = p.indicadores(a.exercicio, a.data_final, a.entidade, a.em)
        elif c == "evolucao":
            _exigir(a, "exercicio")
            r = p.evolucao(a.exercicio, a.entidade, a.em)
        elif c == "dimensao":
            _exigir(a, "dimensao", "exercicio", "data_final")
            r = p.por_dimensao(a.dimensao, a.exercicio, a.data_final, a.entidade, a.em)
        elif c == "empenhos":
            _exigir(a, "exercicio", "data_final")
            r = p.empenhos(a.exercicio, a.data_final, a.entidade, a.em, a.limite, a.deslocamento, a.ordem,
                           anoempenho=a.anoempenho, empenho=a.empenho)
        elif c == "empenho":
            _exigir(a, "entidade", "anoempenho", "empenho", "exercicio")
            r = p.detalhe_empenho(a.entidade, a.anoempenho, a.empenho, a.exercicio, a.data_final, a.em)
        elif c == "fornecedores":
            _exigir(a, "exercicio", "data_final")
            r = p.fornecedores(a.exercicio, a.data_final, a.entidade, a.em, a.limite)
        elif c == "pares":
            _exigir(a, "exercicio", "data_final")
            r = p.pares(a.exercicio, a.data_final, a.em)
        elif c == "retratos":
            _exigir(a, "entidade", "exercicio", "data_final")
            r = p.retratos(a.entidade, a.exercicio, a.data_final)
        elif c == "comparar-retratos":
            _exigir(a, "a", "b")
            r = p.comparar_retratos(a.a, a.b)
        elif c == "reconciliacao":
            r = p.reconciliacao(a.exercicio, a.data_final, a.escopo, a.somente_diferencas, a.em)
        elif c == "coerencia":
            r = p.coerencia_entre_publicacoes()
        elif c == "analitica":
            _exigir(a, "exercicio", "data_final")
            r = p.visao_analitica(a.exercicio, a.data_final, a.em)
        elif c == "regras":
            r = p.regras()
        elif c == "evidencias":
            r = p.evidencias()
        elif c == "fontes":
            r = p.fontes()
        elif c == "metodologia":
            r = p.metodologia()
        else:
            r = p.dicionario_campos()
    print(json.dumps(r, ensure_ascii=False, indent=1, default=str))
    return 0
