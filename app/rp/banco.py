"""Banco SQLite: criacao, backup, registro da camada 0 e reconstrucao a partir do armazem.

O banco e DERIVAVEL do armazem: `registrar_manifesto` e a unica forma de
colocar um snapshot na camada 0 (e `registrar_evidencia`, uma evidencia externa),
e `reconstruir` refaz o banco inteiro so com os manifestos e objetos do disco.

Seguranca:
  * o banco ATIVO nunca abre em pasta sincronizada (OneDrive, Dropbox, Google Drive, iCloud, Box...) nem em
    unidade de rede (SQLite fora de disco local pode corromper; decisao da Etapa 04, ampliada pela revisao critica,
    item 46);
  * backup nunca sobrescreve outro backup, e o motivo informado nao consegue mudar a pasta de destino;
  * a conferencia de integridade dos objetos e explicita (nao usa `assert`, que some com `python -O`).

Impressao do esquema (revisao critica, item 28): a versao em esquema_versao so diz o numero; dois bancos "v4" podem
ter estruturas diferentes se alguem editar esquema.sql sem versao nova. IMPRESSAO_ESQUEMA guarda, por versao, o
SHA-256 da estrutura (sqlite_master sem comentarios nem espacos: comentario e espaco nao sao estrutura - o banco
ativo foi criado antes de os comentarios do esquema.sql perderem os acentos, e a estrutura e a mesma). Um teste
exige que o esquema montado pelo codigo tenha a impressao da sua versao: mudou a estrutura, tem de mudar a versao.
"""
import gzip
import hashlib
import json
import logging
import os
import re
import sqlite3
import sys
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
    # v5 (decisoes D4 e D7 da revisao critica, 06/10/2026): so acrescenta gatilhos e duas colunas; nenhuma tabela e
    # recriada e nenhuma linha muda. Gera _gatilhos_v5().
    5: ("integridade relacional por gatilhos na camada derivada (D4) e criterios de promocao de regra (D7)",
        None),
}
VERSAO_ESQUEMA = max(MIGRACOES)
# Data a partir da qual a promocao de regra a operacional segue os criterios da decisao D7 (governanca.py).
POLITICA_PROMOCAO_DESDE = "2026-10-06"


def _gatilho(nome, evento, tabela, quando, mensagem):
    return (f"CREATE TRIGGER {nome} BEFORE {evento} ON {tabela} WHEN {quando} "
            f"BEGIN SELECT RAISE(ABORT, '{mensagem}'); END")


def _gatilhos_v5():
    """Relacoes que o portao 'integridade_relacional' so conferia lendo (auditoria DB-02) passam a ser recusadas na
    gravacao: linha derivada sem a origem na MESMA normalizacao, snapshot inexistente citado em JSON, regra
    inexistente na derivacao, e apagar a camada 1 de uma normalizacao que ainda tem derivacoes. Cada relacao vale na
    insercao e na alteracao das colunas de ligacao (UPDATE de valor nao e afetado)."""
    rel = {
        "rp_derivado": ("resposta_id, indice, coleta_id, derivacao_id",
                        "NOT EXISTS (SELECT 1 FROM derivacao_execucao e JOIN rp_registro r ON r.normalizacao_id = "
                        "e.normalizacao_id AND r.resposta_id = NEW.resposta_id AND r.indice = NEW.indice AND "
                        "r.coleta_id = NEW.coleta_id WHERE e.id = NEW.derivacao_id)",
                        "rp_derivado sem o registro da normalizacao da sua derivacao"),
        "movimentacao_interpretada": ("resposta_id, indice, derivacao_id",
                                      "NOT EXISTS (SELECT 1 FROM derivacao_execucao e JOIN movimentacao_lancamento l "
                                      "ON l.normalizacao_id = e.normalizacao_id AND l.resposta_id = NEW.resposta_id "
                                      "AND l.indice = NEW.indice WHERE e.id = NEW.derivacao_id)",
                                      "movimentacao_interpretada sem o lancamento da normalizacao da sua derivacao"),
        "anomalia": ("coleta_id",
                     "NEW.coleta_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM coleta WHERE id = NEW.coleta_id)",
                     "anomalia de coleta inexistente"),
        "espelhamento_par": ("resposta_a_id, indice_a, coleta_a_id, resposta_b_id, indice_b, coleta_b_id, derivacao_id",
                             "NOT EXISTS (SELECT 1 FROM derivacao_execucao e JOIN rp_registro a ON a.normalizacao_id = "
                             "e.normalizacao_id AND a.resposta_id = NEW.resposta_a_id AND a.indice = NEW.indice_a AND "
                             "a.coleta_id = NEW.coleta_a_id JOIN rp_registro b ON b.normalizacao_id = e.normalizacao_id "
                             "AND b.resposta_id = NEW.resposta_b_id AND b.indice = NEW.indice_b AND b.coleta_id = "
                             "NEW.coleta_b_id WHERE e.id = NEW.derivacao_id)",
                             "par espelhado sem os dois registros da normalizacao da sua derivacao"),
        "conciliacao_rreo": ("rreo_coleta_id, coletas_api_json",
                             "NOT EXISTS (SELECT 1 FROM coleta WHERE id = NEW.rreo_coleta_id AND tipo = 'rreo_pdf') OR "
                             "EXISTS (SELECT 1 FROM json_each(NEW.coletas_api_json) j WHERE NOT EXISTS "
                             "(SELECT 1 FROM coleta c WHERE c.snapshot_uid = j.value))",
                             "conciliacao com PDF ou snapshot inexistente"),
        "visao_valor": ("coletas_json",
                        "EXISTS (SELECT 1 FROM json_each(NEW.coletas_json) j WHERE NOT EXISTS "
                        "(SELECT 1 FROM coleta c WHERE c.snapshot_uid = j.value))",
                        "visao_valor cita snapshot inexistente"),
        "normalizacao_execucao": ("ultima_coleta_id",
                                  "NEW.ultima_coleta_id > 0 AND NOT EXISTS (SELECT 1 FROM coleta WHERE id = "
                                  "NEW.ultima_coleta_id)",
                                  "normalizacao com ultima coleta inexistente"),
        "derivacao_execucao": ("regras_json",
                               "EXISTS (SELECT 1 FROM json_each(NEW.regras_json) j WHERE NOT EXISTS "
                               "(SELECT 1 FROM regra r WHERE r.id = j.value))",
                               "derivacao com regra inexistente"),
    }
    cmds = []
    for tabela, (colunas, quando, msg) in rel.items():
        cmds.append(_gatilho(f"ri_{tabela}_insert", "INSERT", tabela, quando, msg))
        cmds.append(_gatilho(f"ri_{tabela}_update", f"UPDATE OF {colunas}", tabela, quando, msg))
    for tabela in ("rp_registro", "movimentacao_lancamento"):
        cmds.append(_gatilho(f"ri_{tabela}_delete", "DELETE", tabela,
                             "EXISTS (SELECT 1 FROM derivacao_execucao WHERE normalizacao_id = OLD.normalizacao_id)",
                             f"{tabela} de normalizacao com derivacoes: apague antes as derivacoes"))
    # D7: promocao a operacional depois da politica exige teste de regressao; se compoe indicador publicado, tambem
    # conferencia independente (evidencia externa) ou ressalva documentada
    cmds += ["ALTER TABLE regra_situacao ADD COLUMN teste_regressao TEXT",
             "ALTER TABLE regra_situacao ADD COLUMN ressalva TEXT",
             _gatilho("regra_situacao_promocao", "INSERT", "regra_situacao",
                      f"NEW.situacao = 'operacional' AND NEW.decidido_em >= '{POLITICA_PROMOCAO_DESDE}' AND "
                      "(IFNULL(TRIM(NEW.teste_regressao), '') = '' OR (NEW.compoe_indicador_publicado = 1 AND "
                      "NEW.evidencia_externa_id IS NULL AND IFNULL(TRIM(NEW.ressalva), '') = ''))",
                      "promocao a operacional sem os criterios da decisao D7: teste de regressao e, se compoe "
                      "indicador publicado, evidencia externa ou ressalva")]
    return cmds


MIGRACOES[5] = (MIGRACOES[5][0], _gatilhos_v5())
# Impressao estrutural de cada versao do esquema (impressao_esquema). Versao nova = impressao nova aqui.
IMPRESSAO_ESQUEMA = {
    # v4: conferida em 05/10/2026 no banco ativo (criado em 29/09, migrado em 30/09) e no montado pelo codigo
    4: "ad45413e4a5431eca73afebbf4640c995513203b9def9b38d8cbb83eaa3d3e5a",
    # v5: conferida em 06/10/2026 no montado pelo codigo e no banco ativo migrado da v4
    5: "d80f1040f98fe0213388991b8f8b574b27ab0ef3a57ac61c4d8dc70bbb54e34e",
}

# Cache de paginas por conexao (KiB, valor negativo = tamanho em KiB no SQLite). A derivacao percorre
# ~100 MB de registros; com o cache padrao (~2 MB) a mesma pagina e relida do disco centenas de vezes.
# A memoria so e ocupada conforme as paginas sao lidas.
CACHE_KIB = 256 * 1024
_MOTIVO = re.compile(r"[^A-Za-z0-9._-]+")


class MigracaoPendente(Exception):
    pass


class BancoEmPastaSincronizada(Exception):
    pass


# Pastas-raiz conhecidas de servicos de sincronizacao (nome exato de uma parte do caminho, sem diferenciar
# maiusculas). Lista conservadora: nome generico ("Box", "Sync") poderia ser uma pasta local comum.
_SINCRONIZADAS = {"google drive", "googledrive", "my drive", "meu drive", "icloud drive", "iclouddrive",
                  "mobile documents", "box sync", "box drive", "nextcloud", "owncloud", "pcloud drive"}
_FS_DE_REDE = {"nfs", "nfs4", "cifs", "smb", "smbfs", "smb3", "afpfs", "9p", "fuse.sshfs", "fuse.rclone", "davfs",
               "fuse.davfs"}


def _unidade_de_rede(p):
    """True se `p` esta em compartilhamento de rede: caminho UNC, unidade mapeada (Windows) ou sistema de arquivos
    de rede montado (Linux, /proc/mounts). Melhor esforco: sem como saber, False."""
    if str(p).startswith("\\\\") or p.drive.startswith("\\\\"):
        return True
    if sys.platform == "win32" and p.drive:
        try:
            import ctypes
            return ctypes.windll.kernel32.GetDriveTypeW(f"{p.drive}\\") == 4      # DRIVE_REMOTE
        except (AttributeError, OSError):
            return False
    montagens = Path("/proc/mounts")
    if montagens.exists():
        melhor, tipo = "", None
        for linha in montagens.read_text(encoding="utf-8", errors="replace").splitlines():
            partes = linha.split()
            if len(partes) >= 3 and (str(p) == partes[1] or str(p).startswith(partes[1].rstrip("/") + "/")) \
                    and len(partes[1]) > len(melhor):
                melhor, tipo = partes[1], partes[2]
        return tipo in _FS_DE_REDE
    return False


def em_pasta_sincronizada(caminho):
    """True se `caminho` fica numa pasta sincronizada (OneDrive, Dropbox, Google Drive, iCloud, Box, Nextcloud...)
    ou numa unidade de rede. O que importa nao e qual servico: e que o banco ativo fique em disco local."""
    p = Path(caminho).resolve()
    for var in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        raiz = os.environ.get(var)
        if raiz and p.is_relative_to(Path(raiz).resolve()):
            return True
    for parte in p.parts:
        nome = parte.lower()
        if nome.startswith("onedrive") or nome.startswith("dropbox") or nome in _SINCRONIZADAS:
            return True
    return _unidade_de_rede(p)


_LITERAL_ABRE = ("'", '"')


def _sql_normalizado(sql):
    """Texto SQL sem comentarios (-- e /* */) e com os espacos colapsados FORA de literais; literal fica intacto
    (um CHECK com 'FORTE EVIDÊNCIA' nao pode mudar)."""
    sql = sql or ""
    saida, codigo, i, n = [], [], 0, len(sql)

    def fechar_codigo():
        if codigo:
            t = re.sub(r"\s+", " ", "".join(codigo))
            saida.append(re.sub(r" ?([(),;]) ?", r"\1", t))
            codigo.clear()
    while i < n:
        c = sql[i]
        if c in _LITERAL_ABRE:
            j = i + 1
            while j < n:
                if sql[j] == c:
                    if j + 1 < n and sql[j + 1] == c:     # aspas duplicadas: escape dentro do literal
                        j += 2
                        continue
                    break
                j += 1
            fechar_codigo()
            saida.append(sql[i:j + 1])
            i = j + 1
        elif sql.startswith("--", i):
            fim = sql.find("\n", i)
            i = n if fim < 0 else fim
            codigo.append(" ")
        elif sql.startswith("/*", i):
            fim = sql.find("*/", i + 2)
            i = n if fim < 0 else fim + 2
            codigo.append(" ")
        else:
            codigo.append(c)
            i += 1
    fechar_codigo()
    return "".join(saida).strip()


def impressao_esquema(con):
    """SHA-256 da estrutura do banco: tipo, nome, tabela e SQL normalizado de cada objeto de sqlite_master (tabelas,
    indices, gatilhos). Comentario e espaco nao contam; coluna, tipo, restricao, indice e gatilho contam."""
    itens = sorted((t, nome, tabela, _sql_normalizado(sql)) for t, nome, tabela, sql in con.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'"))
    return hashlib.sha256(json.dumps(itens, ensure_ascii=False).encode()).hexdigest()


def esquema_do_codigo():
    """Conexao em memoria com o esquema completo montado pelo codigo (esquema.sql + migracoes), sem dados."""
    con = sqlite3.connect(":memory:")
    con.executescript(ESQUEMA.read_text(encoding="utf-8"))
    for v in range(VERSAO_BASE + 1, VERSAO_ESQUEMA + 1):
        for sql in MIGRACOES[v][1]:
            con.execute(sql)
    return con


def _conectar(caminho):
    con = sqlite3.connect(caminho)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute(f"PRAGMA cache_size = -{CACHE_KIB}")
    return con


def _migrar(con, de, backup_antes):
    """Cada migracao e UMA transacao explicita: comandos + registro em esquema_versao, ou nada.
    `with con:` nao bastaria: no sqlite3 do Python o BEGIN implicito so vem antes de INSERT/UPDATE/DELETE, e um
    CREATE/ALTER fora de transacao e confirmado na hora (falha no meio deixaria o esquema pela metade)."""
    for v in range(de + 1, VERSAO_ESQUEMA + 1):
        descricao, comandos = MIGRACOES[v]
        con.execute("BEGIN")
        try:
            for sql in comandos:
                con.execute(sql)
            con.execute("INSERT INTO esquema_versao VALUES (?,?,?,?)", (v, descricao, agora(),
                                                                         str(backup_antes) if backup_antes else None))
        except BaseException:
            con.rollback()
            raise
        con.commit()
        log.info("esquema migrado para v%d (%s)", v, descricao)


def versao_esquema(con):
    try:
        return con.execute("SELECT MAX(versao) FROM esquema_versao").fetchone()[0]
    except sqlite3.OperationalError:   # arquivo sem a tabela: nao e um banco do projeto (ou criacao interrompida)
        return None


def _criar(caminho):
    """Banco novo montado num arquivo temporario ao lado do destino e publicado so no fim, sem sobrescrever:
    uma falha no meio (esquema, migracoes, catalogo) nao deixa no destino um arquivo que pareca banco existente."""
    from .armazem import _publicar_sem_sobrescrever
    tmp = caminho.with_name(f"{caminho.name}.criando{os.getpid()}")
    con = _conectar(tmp)
    try:
        con.executescript(ESQUEMA.read_text(encoding="utf-8"))
        with con:
            con.execute("INSERT INTO esquema_versao VALUES (?,?,?,NULL)", (VERSAO_BASE, DESCRICAO_BASE, agora()))
        _migrar(con, VERSAO_BASE, None)  # banco novo: nada a proteger
        _semear_catalogo(con)
        con.close()
        _publicar_sem_sobrescrever(tmp, caminho)
    except BaseException:
        con.close()
        tmp.unlink(missing_ok=True)
        raise
    log.info("banco criado em %s (esquema v%d)", caminho, VERSAO_ESQUEMA)
    return _conectar(caminho)


def abrir(cfg, caminho=None):
    """Abre (criando, se preciso) o banco. Toda mudanca estrutural de banco existente e precedida de backup.
    Sem `caminho`, abre o banco ATIVO (cfg.banco), que e recusado em pasta sincronizada ou de rede."""
    if caminho is None and em_pasta_sincronizada(cfg.banco):
        raise BancoEmPastaSincronizada(f"banco ativo em pasta sincronizada ou de rede: {cfg.banco}. "
                                       "Aponte [caminhos].dados_locais para uma pasta local.")
    caminho = Path(caminho or cfg.banco)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if not caminho.exists():
        return _criar(caminho)
    con = _conectar(caminho)
    atual = versao_esquema(con)
    if atual is None:
        con.close()
        raise MigracaoPendente(f"{caminho} não tem versão de esquema: não é um banco do projeto ou a criação foi "
                               "interrompida. Nada foi alterado.")
    if atual > VERSAO_ESQUEMA:
        raise MigracaoPendente(f"banco na v{atual} é mais novo que o código (v{VERSAO_ESQUEMA})")
    if atual < VERSAO_BASE:
        arq = backup(con, cfg, f"antes-migracao-v{atual}-v{VERSAO_ESQUEMA}")
        raise MigracaoPendente(f"banco na v{atual}: não há migração a partir dela; backup em {arq}")
    if atual < VERSAO_ESQUEMA:
        arq = backup(con, cfg, f"antes-migracao-v{atual}-v{VERSAO_ESQUEMA}")
        _migrar(con, atual, arq)
    esperado = IMPRESSAO_ESQUEMA.get(VERSAO_ESQUEMA)
    if esperado and impressao_esquema(con) != esperado:     # aviso; o portao 'esquema_confere' reprova a carga
        log.warning("esquema de %s difere do esquema v%d do código (impressão estrutural): ver portão "
                    "'esquema_confere'", caminho, VERSAO_ESQUEMA)
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
      `backups_operacionais/`, fora do OneDrive. Os `manter` mais recentes desse tipo ficam como estao; os mais
      antigos sao COMPRIMIDOS (<nome>.gz, conferido byte a byte), nunca apagados (revisao critica, D6).
      Arquivo listado em `backups_operacionais/PRESERVAR.txt` (um nome por linha) nao entra na retencao.
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
        for velho in _fora_da_retencao(pasta, manter):
            comprimido = comprimir_backup(velho)
            log.info("backup operacional antigo comprimido (retenção %d): %s", manter, comprimido.name)
    return destino


def _na_retencao(pasta):
    """Backups operacionais .sqlite sujeitos a retencao (sem os listados em PRESERVAR.txt), do mais antigo ao mais
    novo (o nome comeca pelo carimbo)."""
    lista = pasta / "PRESERVAR.txt"
    preservar = set(lista.read_text(encoding="utf-8").split()) if lista.exists() else set()
    return sorted(p for p in pasta.glob("*.sqlite") if p.name not in preservar)


def _fora_da_retencao(pasta, manter):
    """Os da retencao alem dos `manter` mais recentes."""
    return _na_retencao(pasta)[:-manter] if manter else _na_retencao(pasta)


def comprimir_backup(arquivo, bloco=1 << 20):
    """Comprime um backup em <nome>.gz SEM perder nada (revisao critica, D6): grava num temporario, confere que a
    descompressao devolve os mesmos bytes (SHA-256) e so entao remove o original. Recusa sobrescrever um .gz
    existente. Para voltar ao arquivo original: python -m gzip -d <nome>.gz"""
    arquivo = Path(arquivo)
    destino = arquivo.with_name(arquivo.name + ".gz")
    if destino.exists():
        raise FileExistsError(f"{destino} já existe: nada foi comprimido")
    tmp = arquivo.with_name(f"{destino.name}.tmp{os.getpid()}")
    h = hashlib.sha256()
    try:
        with open(arquivo, "rb") as ent, gzip.open(tmp, "wb", compresslevel=6) as sai:
            while b := ent.read(bloco):
                h.update(b)
                sai.write(b)
        conferido = hashlib.sha256()
        with gzip.open(tmp, "rb") as ent:
            while b := ent.read(bloco):
                conferido.update(b)
        if conferido.hexdigest() != h.hexdigest():
            raise ObjetoCorrompido(f"{tmp}: a descompressão não devolve os bytes de {arquivo.name}")
        from .armazem import _publicar_sem_sobrescrever
        _publicar_sem_sobrescrever(tmp, destino)
    finally:
        tmp.unlink(missing_ok=True)
    arquivo.unlink()
    return destino


def comprimir_backups_operacionais(cfg, manter=3, simular=True):
    """Comprime os backups operacionais fora da janela dos `manter` mais recentes, INCLUSIVE os preservados
    (PRESERVAR.txt protege contra apagar; comprimir nao apaga nada). Os mais recentes ficam como estao, prontos para
    restaurar. `simular` so lista."""
    pasta = cfg.backups_operacionais
    if not pasta.exists():
        return []
    recentes = set(_na_retencao(pasta)[-manter:]) if manter else set()
    saida = []
    for arq in sorted(pasta.glob("*.sqlite")):
        if arq in recentes:
            continue
        antes = arq.stat().st_size
        if simular:
            saida.append({"arquivo": arq.name, "bytes": antes, "simulado": True})
            continue
        gz = comprimir_backup(arq)
        saida.append({"arquivo": gz.name, "bytes_antes": antes, "bytes_depois": gz.stat().st_size})
        log.info("backup operacional comprimido: %s (%d -> %d bytes)", gz.name, antes, gz.stat().st_size)
    return saida


def espaco(cfg):
    """Bytes ocupados por pasta (banco ativo, armazem, backups, backups operacionais, logs): para acompanhar o
    crescimento (revisao critica, D6)."""
    def total(p):
        p = Path(p)
        if p.is_file():
            return p.stat().st_size
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0
    return {"banco": total(cfg.banco), "armazem": total(cfg.snapshots), "backups": total(cfg.backups),
            "backups_operacionais": total(cfg.backups_operacionais), "logs": total(cfg.logs)}


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
    """Banco NOVO em `destino`, so a partir do armazem. Recusa sobrescrever arquivo existente.
    '~' vira a pasta do usuario tambem quando o shell nao expande (PowerShell)."""
    destino = Path(destino).expanduser()
    if destino.exists():
        raise FileExistsError(f"{destino} já existe: a reconstrução nunca sobrescreve um banco")
    con = abrir(cfg, destino)
    n = sincronizar(con, armazem)
    return con, n


def _diferencas_do_manifesto(con, rel, m):
    """Campos em que a camada 0 do banco nao e a do manifesto (auditoria REC-01): a presenca do snapshot_uid nao
    basta; o banco precisa ter os mesmos parametros, status, datas e as mesmas respostas (ordem, URL, hash, tamanho)."""
    try:
        cid, manif, tipo, ep, pj, ent, ex, di, df, tp, ano, emp, arq, quando, origem, st, obs, cv = con.execute(
            "SELECT id, manifesto, tipo, endpoint, parametros_json, entidade, exercicio, data_inicial, data_final, "
            "tipo_pesquisa, anoempenho, empenho, id_arquivo, coletada_em, origem_carimbo, status, observacao, "
            "coletor_versao_id FROM coleta WHERE snapshot_uid=?", (m["snapshot_uid"],)).fetchone()
        p = m["parametros"]
        esperado = {"manifesto": rel, "tipo": m["tipo"], "endpoint": m["endpoint"], "parametros": p,
                    "entidade": p.get("entidade"), "exercicio": p.get("exercicio"), "data_inicial": p.get("dataInicial"),
                    "data_final": p.get("dataFinal"), "tipo_pesquisa": p.get("tipoPesquisa"),
                    "anoempenho": p.get("anoempenho"), "empenho": p.get("empenho"), "id_arquivo": p.get("id_arquivo"),
                    "coletada_em": m["coletada_em"], "origem_carimbo": m["origem_carimbo"], "status": m["status"],
                    "observacao": m.get("observacao")}
        no_banco = {"manifesto": manif, "tipo": tipo, "endpoint": ep, "parametros": json.loads(pj), "entidade": ent,
                    "exercicio": ex, "data_inicial": di, "data_final": df, "tipo_pesquisa": tp, "anoempenho": ano,
                    "empenho": emp, "id_arquivo": arq, "coletada_em": quando, "origem_carimbo": origem, "status": st,
                    "observacao": obs}
        dif = [k for k in esperado if esperado[k] != no_banco[k]]
        col = con.execute("SELECT nome, versao, sha256_codigo FROM coletor_versao WHERE id=?", (cv,)).fetchone()
        if tuple(col) != (m["coletor"]["nome"], m["coletor"]["versao"], m["coletor"]["sha256_codigo"]):
            dif.append("coletor")
        resp = [(o, u, s, json.loads(c or "{}"), r, h, t) for o, u, s, c, r, h, t in con.execute(
            "SELECT ordem, url, http_status, cabecalhos_json, recebida_em, sha256, tamanho FROM resposta_bruta "
            "WHERE coleta_id=? ORDER BY ordem", (cid,))]
        esperadas = [(r["ordem"], r["url"], r["http_status"], r.get("cabecalhos") or {}, r["recebida_em"], r["sha256"],
                      r["tamanho"]) for r in sorted(m["respostas"], key=lambda r: r["ordem"])]
        if resp != esperadas:
            dif.append("respostas")
        return dif
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        return [f"manifesto sem campo esperado ({type(e).__name__}: {e})"]


def verificar(con, armazem):
    """Problemas de integridade entre banco e armazem (lista vazia = integro): objetos e manifestos do armazem, os
    dois sentidos da presenca (manifesto x coleta, evidencia x banco), cada coleta igual ao seu manifesto campo a
    campo e cada objeto do banco conferido pelo hash."""
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
    for rel, m in itens:
        if m["snapshot_uid"] in registrados:
            dif = _diferencas_do_manifesto(con, rel, m)
            if dif:
                problemas.append(f"coleta difere do manifesto {rel}: {', '.join(dif)}")
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
