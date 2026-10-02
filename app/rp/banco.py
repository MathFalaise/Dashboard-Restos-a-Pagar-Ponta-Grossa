"""Banco SQLite: criacao, backup, registro da camada 0 e reconstrucao a partir do armazem.

O banco e DERIVAVEL do armazem: `registrar_manifesto` e a unica forma de
colocar um snapshot na camada 0 (e `registrar_evidencia`, uma evidencia externa),
e `reconstruir` refaz o banco inteiro so com os manifestos e objetos do disco.

Seguranca:
  * o banco ATIVO nunca abre dentro de pasta sincronizada pelo OneDrive (SQLite em pasta
    sincronizada pode corromper; decisao da Etapa 04);
  * backup nunca sobrescreve outro backup, e o motivo informado nao consegue mudar a pasta de destino;
  * a conferencia de integridade dos objetos e explicita (nao usa `assert`, que some com `python -O`).
"""
import json
import logging
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from . import BRT, agora, sha256, sha256_valido
from .armazem import ObjetoCorrompido, descomprimir

log = logging.getLogger("rp.banco")

ESQUEMA = Path(__file__).with_name("esquema.sql")   # cria a versao BASE (v2)
VERSAO_BASE = 2
DESCRICAO_BASE = "esquema de produção v2 (objeto_bruto, manifesto, esquema_versao)"
# Migracoes a partir da base. Cada uma e aplicada numa transacao e registrada em esquema_versao
# com o arquivo de backup feito ANTES dela (banco existente). Nunca se edita uma migracao publicada.
MIGRACOES = {
    3: ("derivação com data de vigência ('como estava em')",
        ["ALTER TABLE derivacao_execucao ADD COLUMN vigencia_em TEXT"]),
    # v4 (revisao corretiva 01-04.4): so acrescenta; nenhuma linha existente muda.
    4: ("revisao corretiva: parametros e governanca de regras, metadados da extracao do RREO, "
        "evidencia externa com origem e manifesto, ultima coleta processada pela normalizacao",
        [
            # parametros estruturados de uma versao de regra (ex.: PAR-24 v1 = entidades 1/15, base 2.400.000)
            "CREATE TABLE regra_parametro (regra_id INTEGER NOT NULL REFERENCES regra(id), nome TEXT NOT NULL, "
            "valor_json TEXT NOT NULL, PRIMARY KEY (regra_id, nome))",
            "CREATE TRIGGER regra_parametro_sem_update BEFORE UPDATE ON regra_parametro "
            "BEGIN SELECT RAISE(ABORT, 'parametro de regra nao se edita: crie nova versao da regra'); END",
            "CREATE TRIGGER regra_parametro_sem_delete BEFORE DELETE ON regra_parametro "
            "BEGIN SELECT RAISE(ABORT, 'parametro de regra nao se apaga: crie nova versao da regra'); END",
            # governanca: historico de decisoes sobre cada versao de regra (so acrescenta)
            "CREATE TABLE regra_situacao (id INTEGER PRIMARY KEY, regra_id INTEGER NOT NULL REFERENCES regra(id), "
            "situacao TEXT NOT NULL CHECK (situacao IN ('operacional','experimental','nao_recomendada','supersedida','aposentada')), "
            "status_evidencia TEXT NOT NULL CHECK (status_evidencia IN ('CONFIRMADO','FORTE EVIDÊNCIA','HIPÓTESE','NÃO DETERMINADO')), "
            "compoe_indicador_publicado INTEGER NOT NULL CHECK (compoe_indicador_publicado IN (0,1)), "
            "supersedida_por INTEGER REFERENCES regra(id), motivo TEXT NOT NULL, fonte TEXT NOT NULL, "
            "evidencia_externa_id INTEGER REFERENCES evidencia_externa(id), decidido_em TEXT NOT NULL, "
            "origem_decisao TEXT NOT NULL, UNIQUE (regra_id, decidido_em), "
            "CHECK (compoe_indicador_publicado = 0 OR situacao = 'operacional'))",
            "CREATE TRIGGER regra_situacao_sem_update BEFORE UPDATE ON regra_situacao "
            "BEGIN SELECT RAISE(ABORT, 'decisao de governanca nao se edita: registre uma decisao nova'); END",
            "CREATE TRIGGER regra_situacao_sem_delete BEFORE DELETE ON regra_situacao "
            "BEGIN SELECT RAISE(ABORT, 'decisao de governanca nao se apaga: registre uma decisao nova'); END",
            # camada 1: como cada PDF de RREO foi transcrito nesta normalizacao (inclusive os que falharam)
            "CREATE TABLE rreo_extracao (normalizacao_id INTEGER NOT NULL REFERENCES normalizacao_execucao(id), "
            "resposta_id INTEGER NOT NULL REFERENCES resposta_bruta(id), coleta_id INTEGER NOT NULL REFERENCES coleta(id), "
            "extrator_versao TEXT NOT NULL, biblioteca TEXT NOT NULL, biblioteca_versao TEXT NOT NULL, "
            "sha256_pdf TEXT NOT NULL, id_arquivo INTEGER, rotulo TEXT, extraida_em TEXT NOT NULL, "
            "valores INTEGER NOT NULL, erro TEXT, PRIMARY KEY (normalizacao_id, resposta_id))",
            # evidencia externa: origem, observacao, manifesto no armazem e identidade estavel
            "ALTER TABLE evidencia_externa ADD COLUMN origem TEXT",
            "ALTER TABLE evidencia_externa ADD COLUMN observacao TEXT",
            "ALTER TABLE evidencia_externa ADD COLUMN manifesto TEXT",
            "ALTER TABLE evidencia_externa ADD COLUMN evidencia_uid TEXT",
            "CREATE UNIQUE INDEX ux_evidencia_uid ON evidencia_externa (evidencia_uid)",
            # maior id de coleta que a normalizacao leu: snapshot com 0 registros nao deixa linha nas tabelas da
            # camada 1, entao so este registro diz se ele ja foi processado (NULL nas normalizacoes anteriores)
            "ALTER TABLE normalizacao_execucao ADD COLUMN ultima_coleta_id INTEGER",
        ]),
}
VERSAO_ESQUEMA = max(MIGRACOES)

# Cache de paginas por conexao (KiB, valor negativo = tamanho em KiB no SQLite). A derivacao percorre
# ~100 MB de registros; com o cache padrao (~2 MB) a mesma pagina e relida do disco centenas de vezes.
# A memoria so e ocupada conforme as paginas sao lidas.
CACHE_KIB = 256 * 1024
_MOTIVO = re.compile(r"[^A-Za-z0-9._-]+")


class MigracaoPendente(Exception):
    pass


class BancoEmPastaSincronizada(Exception):
    pass


def em_pasta_sincronizada(caminho):
    """True se `caminho` fica dentro de uma pasta do OneDrive."""
    p = Path(caminho).resolve()
    for var in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        raiz = os.environ.get(var)
        if raiz and p.is_relative_to(Path(raiz).resolve()):
            return True
    return any(parte.lower().startswith("onedrive") for parte in p.parts)


def _conectar(caminho):
    con = sqlite3.connect(caminho)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute(f"PRAGMA cache_size = -{CACHE_KIB}")
    return con


def _migrar(con, de, backup_antes):
    for v in range(de + 1, VERSAO_ESQUEMA + 1):
        descricao, comandos = MIGRACOES[v]
        with con:
            for sql in comandos:
                con.execute(sql)
            con.execute("INSERT INTO esquema_versao VALUES (?,?,?,?)", (v, descricao, agora(),
                                                                         str(backup_antes) if backup_antes else None))
        log.info("esquema migrado para v%d (%s)", v, descricao)


def versao_esquema(con):
    return con.execute("SELECT MAX(versao) FROM esquema_versao").fetchone()[0]


def abrir(cfg, caminho=None):
    """Abre (criando, se preciso) o banco. Toda mudanca estrutural de banco existente e precedida de backup.
    Sem `caminho`, abre o banco ATIVO (cfg.banco), que e recusado dentro de pasta do OneDrive."""
    if caminho is None and em_pasta_sincronizada(cfg.banco):
        raise BancoEmPastaSincronizada(f"banco ativo em pasta do OneDrive: {cfg.banco}. "
                                       "Aponte [caminhos].dados_locais para uma pasta local.")
    caminho = Path(caminho or cfg.banco)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    novo = not caminho.exists()
    con = _conectar(caminho)
    if novo:
        with con:
            con.executescript(ESQUEMA.read_text(encoding="utf-8"))
            con.execute("INSERT INTO esquema_versao VALUES (?,?,?,NULL)", (VERSAO_BASE, DESCRICAO_BASE, agora()))
        _migrar(con, VERSAO_BASE, None)  # banco novo: nada a proteger
        _semear_catalogo(con)
        log.info("banco criado em %s (esquema v%d)", caminho, VERSAO_ESQUEMA)
        return con
    atual = versao_esquema(con)
    if atual > VERSAO_ESQUEMA:
        raise MigracaoPendente(f"banco na v{atual} é mais novo que o código (v{VERSAO_ESQUEMA})")
    if atual < VERSAO_BASE:
        arq = backup(con, cfg, f"antes-migracao-v{atual}-v{VERSAO_ESQUEMA}")
        raise MigracaoPendente(f"banco na v{atual}: não há migração a partir dela; backup em {arq}")
    if atual < VERSAO_ESQUEMA:
        arq = backup(con, cfg, f"antes-migracao-v{atual}-v{VERSAO_ESQUEMA}")
        _migrar(con, atual, arq)
    _semear_catalogo(con)
    return con


def _semear_catalogo(con):
    """Regras, parametros de regra e decisoes de governanca do codigo vao para o banco (so INSERT OR IGNORE)."""
    from . import regras
    with con:
        regras.semear(con)


def backup(con, cfg, motivo, operacional=False, manter=3):
    """Copia consistente (API de backup do SQLite), gravada num temporario e depois movida.

    * padrao (antes de mudanca estrutural, importacao, manual): `backups/`, NUNCA apagado automaticamente;
    * operacional (antes de apagar uma execucao, que e reprocessavel do bruto): pasta local
      `backups_operacionais/`, fora do OneDrive, mantendo so os `manter` mais recentes desse tipo.
      Arquivo listado em `backups_operacionais/PRESERVAR.txt` (um nome por linha) nunca e apagado.
    O nome nunca repete o de um backup existente (sufixo -2, -3... no mesmo segundo)."""
    carimbo = datetime.now(BRT).strftime("%Y%m%d-%H%M%S")
    motivo = _MOTIVO.sub("-", str(motivo)).strip(".-") or "sem-motivo"
    pasta = cfg.backups_operacionais if operacional else cfg.backups
    cfg.temporario.mkdir(parents=True, exist_ok=True)
    pasta.mkdir(parents=True, exist_ok=True)
    nome, n = f"{carimbo}_{motivo}.sqlite", 1
    while (pasta / nome).exists() or (cfg.temporario / nome).exists():
        n += 1
        nome = f"{carimbo}_{motivo}-{n}.sqlite"
    tmp, destino = cfg.temporario / nome, pasta / nome
    try:
        alvo = sqlite3.connect(tmp)
        try:
            with alvo:
                con.backup(alvo)
        finally:
            alvo.close()
        os.replace(tmp, destino)
    finally:
        tmp.unlink(missing_ok=True)
    log.info("backup gravado em %s", destino)
    if operacional:
        lista = pasta / "PRESERVAR.txt"
        preservar = set(lista.read_text(encoding="utf-8").split()) if lista.exists() else set()
        for velho in sorted(p for p in pasta.glob("*.sqlite") if p.name not in preservar)[:-manter]:
            velho.unlink()
            log.info("backup operacional antigo removido (retenção %d): %s", manter, velho.name)
    return destino


def compactar(con, caminho):
    """VACUUM: devolve ao disco o espaco de execucoes apagadas. Nao altera nenhum dado."""
    antes = Path(caminho).stat().st_size
    con.execute("VACUUM")
    return antes, Path(caminho).stat().st_size


def coletor_versao_id(con, coletor):
    con.execute("INSERT OR IGNORE INTO coletor_versao (nome, versao, sha256_codigo, descricao, registrado_em) "
                "VALUES (?,?,?,?,?)", (coletor["nome"], coletor["versao"], coletor["sha256_codigo"],
                                       coletor.get("descricao"), agora()))
    return con.execute("SELECT id FROM coletor_versao WHERE nome=? AND versao=?",
                       (coletor["nome"], coletor["versao"])).fetchone()[0]


def registrar_manifesto(con, armazem, rel, m):
    """Coloca um snapshot na camada 0 (numa transacao). Idempotente pelo snapshot_uid."""
    ja = con.execute("SELECT id FROM coleta WHERE snapshot_uid=?", (m["snapshot_uid"],)).fetchone()
    if ja:
        return ja[0], False
    p = m["parametros"]
    with con:
        cvid = coletor_versao_id(con, m["coletor"])
        cid = con.execute(
            "INSERT INTO coleta (snapshot_uid, manifesto, tipo, endpoint, parametros_json, entidade, exercicio, "
            "data_inicial, data_final, tipo_pesquisa, anoempenho, empenho, id_arquivo, coletada_em, origem_carimbo, "
            "status, coletor_versao_id, observacao) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (m["snapshot_uid"], rel, m["tipo"], m["endpoint"], json.dumps(p, sort_keys=True, ensure_ascii=False),
             p.get("entidade"), p.get("exercicio"), p.get("dataInicial"), p.get("dataFinal"), p.get("tipoPesquisa"),
             p.get("anoempenho"), p.get("empenho"), p.get("id_arquivo"), m["coletada_em"], m["origem_carimbo"],
             m["status"], cvid, m.get("observacao"))).lastrowid
        for r in m["respostas"]:
            comprimido = armazem.ler_comprimido(r["sha256"])       # valida o formato do hash
            try:
                corpo = descomprimir(comprimido, r["tamanho"])
            except ObjetoCorrompido as e:
                raise ValueError(f"objeto {r['sha256'][:12]} não confere com o manifesto {rel} ({e})") from e
            if sha256(corpo) != r["sha256"]:
                raise ValueError(f"objeto {r['sha256'][:12]} não confere com o manifesto {rel}")
            con.execute("INSERT OR IGNORE INTO objeto_bruto VALUES (?,?,?,?)", (r["sha256"], r["tamanho"], "zlib", comprimido))
            con.execute("INSERT INTO resposta_bruta (coleta_id, ordem, url, http_status, cabecalhos_json, recebida_em, "
                        "sha256, tamanho) VALUES (?,?,?,?,?,?,?,?)",
                        (cid, r["ordem"], r["url"], r["http_status"], json.dumps(r.get("cabecalhos") or {}, sort_keys=True),
                         r["recebida_em"], r["sha256"], r["tamanho"]))
    return cid, True


def corpo(con, sha):
    """Bytes originais de um objeto da camada 0, conferidos pelo tamanho e pelo hash."""
    linha = con.execute("SELECT dados, tamanho FROM objeto_bruto WHERE sha256=?", (sha,)).fetchone()
    if linha is None:
        raise KeyError(f"objeto {sha} nao esta no banco")
    comp, tam = linha
    b = descomprimir(comp, tam)
    if sha256(b) != sha:
        raise ObjetoCorrompido(f"{sha}: conteúdo não confere com o hash")
    return b


def registrar_evidencia(con, armazem, rel, m):
    """Coloca uma evidencia externa (e-SIC, norma, nota...) na camada 0. Idempotente pelo evidencia_uid.
    O arquivo em si fica no armazem e no banco (objeto_bruto), conferido pelo SHA-256 e pelo tamanho."""
    ja = con.execute("SELECT id FROM evidencia_externa WHERE evidencia_uid=?", (m["evidencia_uid"],)).fetchone()
    if ja:
        return ja[0], False
    comprimido = armazem.ler_comprimido(m["sha256"])
    corpo_ = descomprimir(comprimido, m["tamanho"])
    if sha256(corpo_) != m["sha256"]:
        raise ValueError(f"arquivo da evidencia {m['evidencia_uid'][:8]} nao confere com o manifesto {rel}")
    with con:
        con.execute("INSERT OR IGNORE INTO objeto_bruto VALUES (?,?,?,?)", (m["sha256"], m["tamanho"], "zlib", comprimido))
        eid = con.execute(
            "INSERT INTO evidencia_externa (tipo, descricao, data_documento, caminho_arquivo, sha256, registrada_em, "
            "origem, observacao, manifesto, evidencia_uid) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (m["tipo"], m["descricao"], m.get("data_documento"), m["arquivo_original"], m["sha256"], m["registrada_em"],
             m["origem"], m.get("observacao"), rel, m["evidencia_uid"])).lastrowid
    return eid, True


def sincronizar(con, armazem):
    """Registra no banco todo manifesto do armazem (coletas e evidencias) que ainda nao esta nele."""
    novos = 0
    for rel, m in armazem.manifestos():
        _, criado = registrar_manifesto(con, armazem, rel, m)
        novos += criado
    for rel, m in armazem.evidencias():
        _, criado = registrar_evidencia(con, armazem, rel, m)
        novos += criado
    return novos


def reconstruir(cfg, armazem, destino):
    """Banco NOVO em `destino`, so a partir do armazem. Recusa sobrescrever arquivo existente."""
    destino = Path(destino)
    if destino.exists():
        raise FileExistsError(f"{destino} já existe: a reconstrução nunca sobrescreve um banco")
    con = abrir(cfg, destino)
    n = sincronizar(con, armazem)
    return con, n


def verificar(con, armazem):
    """Problemas de integridade entre banco e armazem (lista vazia = integro)."""
    problemas = [f"armazém: {p}" for p in armazem.verificar()]
    registrados = {u for (u,) in con.execute("SELECT snapshot_uid FROM coleta")}
    no_disco = {}
    itens, _ = armazem.manifestos_e_erros()      # os ilegiveis ja vieram de armazem.verificar()
    for rel, m in itens:
        no_disco[m["snapshot_uid"]] = rel
        if m["snapshot_uid"] not in registrados:
            problemas.append(f"manifesto fora do banco: {rel}")
    for uid, rel in con.execute("SELECT snapshot_uid, manifesto FROM coleta"):
        if uid not in no_disco:
            problemas.append(f"coleta sem manifesto no armazém: {uid} ({rel})")
    evid, _ = armazem.evidencias_e_erros()        # os ilegiveis ja vieram de armazem.verificar()
    evid_no_disco = {m["evidencia_uid"]: rel for rel, m in evid}
    evid_no_banco = dict(con.execute("SELECT evidencia_uid, manifesto FROM evidencia_externa WHERE evidencia_uid IS NOT NULL"))
    for uid, rel in evid_no_disco.items():
        if uid not in evid_no_banco:
            problemas.append(f"evidencia fora do banco: {rel}")
    for uid, rel in evid_no_banco.items():
        if uid not in evid_no_disco:
            problemas.append(f"evidencia sem manifesto no armazem: {uid} ({rel})")
    for (sha,) in con.execute("SELECT e.sha256 FROM evidencia_externa e LEFT JOIN objeto_bruto o ON o.sha256=e.sha256 "
                              "WHERE e.sha256 IS NOT NULL AND o.sha256 IS NULL"):
        problemas.append(f"evidencia sem objeto no banco: {sha[:12]}")
    for sha, tam, comp in con.execute("SELECT sha256, tamanho, dados FROM objeto_bruto"):
        try:
            b = descomprimir(comp, tam)
        except ObjetoCorrompido:
            b = None
        if b is None or not sha256_valido(sha) or sha256(b) != sha:
            problemas.append(f"objeto corrompido no banco: {sha[:12]}")
    return problemas
