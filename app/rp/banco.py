"""SQLite database: creation, backup, recording of layer 0 and rebuilding from the store.

The database is DERIVABLE from the store: `registrar_manifesto` is the only way to put a snapshot into layer 0
(and `registrar_evidencia`, an external evidence), and `reconstruir` rebuilds the whole database from the
manifests and objects on disk alone.

Security:
  * the ACTIVE database never opens in a synced folder (OneDrive, Dropbox, Google Drive, iCloud, Box...) nor on a
    network drive (SQLite off a local disk can get corrupted; stage 04 decision, extended by the critical review,
    item 46);
  * a backup never overwrites another backup, and the given reason cannot change the target folder;
  * the object integrity check is explicit (it does not use `assert`, which disappears with `python -O`).

Schema fingerprint (critical review, item 28): the version in esquema_versao only says the number; two "v4"
databases may have different structures if someone edits esquema.sql without a new version. IMPRESSAO_ESQUEMA
keeps, per version, the SHA-256 of the structure (sqlite_master without comments or whitespace: comments and
whitespace are not structure - the active database was created before the esquema.sql comments lost their
accents, and the structure is the same). A test requires the schema built by the code to have its version's
fingerprint: if the structure changed, the version must change.
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

from . import BRT, agora, instante, sha256, sha256_valido
from .armazem import ObjetoCorrompido, descomprimir

log = logging.getLogger("rp.banco")

ESQUEMA = Path(__file__).with_name("esquema.sql")   # creates the BASE version (v2)
VERSAO_BASE = 2
DESCRICAO_BASE = "esquema de produção v2 (objeto_bruto, manifesto, esquema_versao)"
# Migrations from the base. Each one is applied in a transaction and recorded in esquema_versao
# with the backup file made BEFORE it (existing database). A published migration is never edited.
MIGRACOES = {
    3: ("derivação com data de vigência ('como estava em')",
        ["ALTER TABLE derivacao_execucao ADD COLUMN vigencia_em TEXT"]),
    # v4 (corrective review 01-04.4): additions only; no existing row changes.
    4: ("revisao corretiva: parametros e governanca de regras, metadados da extracao do RREO, "
        "evidencia externa com origem e manifesto, ultima coleta processada pela normalizacao",
        [
            # structured parameters of a rule version (e.g. PAR-24 v1 = entities 1/15, base 2,400,000)
            "CREATE TABLE regra_parametro (regra_id INTEGER NOT NULL REFERENCES regra(id), nome TEXT NOT NULL, "
            "valor_json TEXT NOT NULL, PRIMARY KEY (regra_id, nome))",
            "CREATE TRIGGER regra_parametro_sem_update BEFORE UPDATE ON regra_parametro "
            "BEGIN SELECT RAISE(ABORT, 'parametro de regra nao se edita: crie nova versao da regra'); END",
            "CREATE TRIGGER regra_parametro_sem_delete BEFORE DELETE ON regra_parametro "
            "BEGIN SELECT RAISE(ABORT, 'parametro de regra nao se apaga: crie nova versao da regra'); END",
            # governance: history of decisions about each rule version (append-only)
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
            # layer 1: how each RREO PDF was transcribed in this normalization (including the ones that failed)
            "CREATE TABLE rreo_extracao (normalizacao_id INTEGER NOT NULL REFERENCES normalizacao_execucao(id), "
            "resposta_id INTEGER NOT NULL REFERENCES resposta_bruta(id), coleta_id INTEGER NOT NULL REFERENCES coleta(id), "
            "extrator_versao TEXT NOT NULL, biblioteca TEXT NOT NULL, biblioteca_versao TEXT NOT NULL, "
            "sha256_pdf TEXT NOT NULL, id_arquivo INTEGER, rotulo TEXT, extraida_em TEXT NOT NULL, "
            "valores INTEGER NOT NULL, erro TEXT, PRIMARY KEY (normalizacao_id, resposta_id))",
            # external evidence: origin, note, manifest in the store and a stable identity
            "ALTER TABLE evidencia_externa ADD COLUMN origem TEXT",
            "ALTER TABLE evidencia_externa ADD COLUMN observacao TEXT",
            "ALTER TABLE evidencia_externa ADD COLUMN manifesto TEXT",
            "ALTER TABLE evidencia_externa ADD COLUMN evidencia_uid TEXT",
            "CREATE UNIQUE INDEX ux_evidencia_uid ON evidencia_externa (evidencia_uid)",
            # highest collection id the normalization read: a snapshot with 0 records leaves no row in the layer 1
            # tables, so only this column says whether it was already processed (NULL in older normalizations)
            "ALTER TABLE normalizacao_execucao ADD COLUMN ultima_coleta_id INTEGER",
        ]),
    # v5 (critical review decisions D4 and D7, 06/10/2026): only adds triggers and two columns; no table is
    # recreated and no row changes. Built by _gatilhos_v5().
    5: ("integridade relacional por gatilhos na camada derivada (D4) e criterios de promocao de regra (D7)",
        None),
}
# Date from which promoting a rule to operational follows the criteria of decision D7 (governanca.py).
POLITICA_PROMOCAO_DESDE = "2026-10-06"


def _gatilho(nome, evento, tabela, quando, mensagem):
    return (f"CREATE TRIGGER {nome} BEFORE {evento} ON {tabela} WHEN {quando} "
            f"BEGIN SELECT RAISE(ABORT, '{mensagem}'); END")


def _gatilhos_v5():
    """Relations that the 'integridade_relacional' gate only checked by reading (audit DB-02) are now refused on
    write: a derived row without its origin in the SAME normalization, a non-existent snapshot cited in JSON, a
    non-existent rule in the derivation, and deleting layer 1 of a normalization that still has derivations. Each
    relation applies on insert and on update of the link columns (an UPDATE of a value is not affected)."""
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
    # D7: promotion to operational after the policy requires a regression test; if it makes up a published indicator,
    # also an independent check (external evidence) or a documented caveat
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
# v6 (correction request of 09/10/2026, item 2): a missing, null or invalid money field of the RP listing is no longer
# typed as zero. The record does not become a row of rp_registro (whose money columns are NOT NULL: a value is
# required there); each refused field becomes a row here, with the field name and what happened. Additions only: no
# table is recreated and no existing row changes (on the 266,787 records of normalization 14 no field is missing).
MIGRACOES[6] = (
    "campo monetario ausente, nulo ou invalido registrado como recusa (nunca zero): tabela valor_recusado",
    [
        "CREATE TABLE valor_recusado (normalizacao_id INTEGER NOT NULL REFERENCES normalizacao_execucao(id), "
        "resposta_id INTEGER NOT NULL REFERENCES resposta_bruta(id), indice INTEGER NOT NULL, "
        "coleta_id INTEGER NOT NULL REFERENCES coleta(id), entidade INTEGER, anoempenho INTEGER, empenho INTEGER, "
        "campo TEXT NOT NULL CHECK (campo IN ('proc','aproc','canceladoProc','pagoProc','pagoProcEstornado',"
        "'canceladoAProc','pagoAProc','pagoAProcEstornado','liquidado','retencao')), "
        "natureza TEXT NOT NULL CHECK (natureza IN ('ausente','nulo','invalido')), valor_bruto TEXT, "
        "CHECK ((natureza = 'invalido') = (valor_bruto IS NOT NULL)), "
        "PRIMARY KEY (normalizacao_id, resposta_id, indice, campo))",
        _gatilho("ri_valor_recusado_insert", "INSERT", "valor_recusado",
                 "NOT EXISTS (SELECT 1 FROM resposta_bruta b WHERE b.id = NEW.resposta_id AND b.coleta_id = "
                 "NEW.coleta_id) OR EXISTS (SELECT 1 FROM rp_registro r WHERE r.normalizacao_id = NEW.normalizacao_id "
                 "AND r.resposta_id = NEW.resposta_id AND r.indice = NEW.indice)",
                 "valor_recusado de outra coleta ou de registro ja normalizado com valor"),
        "CREATE TRIGGER valor_recusado_sem_update BEFORE UPDATE ON valor_recusado "
        "BEGIN SELECT RAISE(ABORT, 'recusa de valor nao se edita: rode nova normalizacao'); END",
        _gatilho("ri_valor_recusado_delete", "DELETE", "valor_recusado",
                 "EXISTS (SELECT 1 FROM derivacao_execucao WHERE normalizacao_id = OLD.normalizacao_id)",
                 "valor_recusado de normalizacao com derivacoes: apague antes as derivacoes"),
        _gatilho("ri_rp_registro_recusado", "INSERT", "rp_registro",
                 "EXISTS (SELECT 1 FROM valor_recusado v WHERE v.normalizacao_id = NEW.normalizacao_id AND "
                 "v.resposta_id = NEW.resposta_id AND v.indice = NEW.indice)",
                 "rp_registro de posicao com valor recusado na mesma normalizacao"),
    ])
# Canonical instant (rp.instante): Brasilia offset, seconds. Every instant compared AS TEXT has this form.
_GLOB_INSTANTE = "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]-03:00'"
# v7 (correction request of 09/10/2026, item 4): start AND conclusion of each collection, in canonical form, with where
# the conclusion came from. A snapshot is only available to an "as it was on" query from its conclusion on (before,
# coletada_em - the START - was compared, and a collection still running counted as available). Additions only: the
# raw layer (coleta) stays immutable; the rows of existing collections come from their manifests (completar_tempos),
# never invented: no evidence = conclusion NULL ('desconhecida'), and such a snapshot is never available to a query
# with a date.
MIGRACOES[7] = (
    "inicio e conclusao de cada coleta em forma canonica (coleta_tempo): retrato so vale a partir da conclusao",
    [
        "CREATE TABLE coleta_tempo (coleta_id INTEGER PRIMARY KEY REFERENCES coleta(id), inicio_em TEXT NOT NULL, "
        "concluida_em TEXT, fonte_conclusao TEXT NOT NULL CHECK (fonte_conclusao IN ('manifesto','ultima_resposta',"
        "'sem_evidencia')), precisao TEXT NOT NULL CHECK (precisao IN ('exata','ultima_resposta','aproximada',"
        "'desconhecida')), CHECK ((concluida_em IS NULL) = (fonte_conclusao = 'sem_evidencia')), "
        "CHECK ((concluida_em IS NULL) = (precisao = 'desconhecida')))",
        _gatilho("coleta_tempo_insert", "INSERT", "coleta_tempo",
                 f"NEW.inicio_em NOT GLOB {_GLOB_INSTANTE} OR (NEW.concluida_em IS NOT NULL AND (NEW.concluida_em NOT "
                 f"GLOB {_GLOB_INSTANTE} OR NEW.concluida_em < NEW.inicio_em)) OR NOT EXISTS (SELECT 1 FROM coleta c "
                 "WHERE c.id = NEW.coleta_id AND julianday(c.coletada_em) = julianday(NEW.inicio_em))",
                 "coleta_tempo fora da forma canonica, conclusao antes do inicio ou inicio diferente da coleta"),
        "CREATE TRIGGER coleta_tempo_sem_update BEFORE UPDATE ON coleta_tempo "
        "BEGIN SELECT RAISE(ABORT, 'tempo da coleta nao se edita: vem do manifesto'); END",
        "CREATE TRIGGER coleta_tempo_sem_delete BEFORE DELETE ON coleta_tempo "
        "BEGIN SELECT RAISE(ABORT, 'tempo da coleta nao se apaga: vem do manifesto'); END",
    ])


def _migracao_v8():
    """Correction request of 09/10/2026, items 1 and 7. Additions only (no table recreated, no existing row changed):
      * layer 1 refuses, on write, a row whose collection is not the one of its HTTP response, is of another type, or
        is beyond what its normalization read (before, the gate only flagged it by reading);
      * derivation layer: every rule a row cites must be one its derivation declared;
      * relations that lived only in JSON get a normalized table with FOREIGN KEYs, filled here from the JSON of the
        existing derivations (deterministic: the JSON stays, as the source of the homologated hash and of the
        interface): derivacao_regra (regras_json), visao_valor_coleta (coletas_json) and conciliacao_rreo_coleta
        (coletas_api_json); a trigger refuses a link the JSON does not have;
      * provenance (item 7): SHA-256 of each manifest (coleta_manifesto, filled from the store by
        completar_do_armazem), and the code and rule hashes and the environment of each normalization/derivation run
        (NULL in the old runs: never back-filled with today's code)."""
    cmds = []
    camada1 = {"rp_registro": ("rp_listagem", True), "movimentacao_lancamento": ("movimentacao", True),
               "rreo_extracao": ("rreo_pdf", True), "valor_recusado": ("rp_listagem", True),
               "rreo_valor": ("rreo_pdf", False), "entidade_ref": ("entidades", False),
               "exercicio_ref": ("exercicios", False)}
    for tabela, (tipo, com_resposta) in camada1.items():
        quando = (f"NOT EXISTS (SELECT 1 FROM coleta k WHERE k.id = NEW.coleta_id AND k.tipo = '{tipo}') OR EXISTS "
                  "(SELECT 1 FROM normalizacao_execucao n WHERE n.id = NEW.normalizacao_id AND n.ultima_coleta_id IS "
                  "NOT NULL AND NEW.coleta_id > n.ultima_coleta_id)")
        if com_resposta:
            quando += (" OR NOT EXISTS (SELECT 1 FROM resposta_bruta b WHERE b.id = NEW.resposta_id AND "
                       "b.coleta_id = NEW.coleta_id)")
        colunas = "normalizacao_id, coleta_id" + (", resposta_id" if com_resposta else "")
        msg = f"{tabela}: coleta de outro tipo, de outra resposta ou alem da ultima lida pela normalizacao"
        cmds.append(_gatilho(f"ri_{tabela}_coleta_insert", "INSERT", tabela, quando, msg))
        cmds.append(_gatilho(f"ri_{tabela}_coleta_update", f"UPDATE OF {colunas}", tabela, quando, msg))
    cmds += [
        "CREATE TABLE derivacao_regra (derivacao_id INTEGER NOT NULL REFERENCES derivacao_execucao(id), "
        "regra_id INTEGER NOT NULL REFERENCES regra(id), PRIMARY KEY (derivacao_id, regra_id))",
        "INSERT INTO derivacao_regra SELECT e.id, j.value FROM derivacao_execucao e, json_each(e.regras_json) j",
        _gatilho("ri_derivacao_regra_insert", "INSERT", "derivacao_regra",
                 "NOT EXISTS (SELECT 1 FROM derivacao_execucao e, json_each(e.regras_json) j WHERE e.id = "
                 "NEW.derivacao_id AND j.value = NEW.regra_id)", "derivacao_regra fora do regras_json da derivacao"),
        "CREATE TABLE visao_valor_coleta (derivacao_id INTEGER NOT NULL REFERENCES derivacao_execucao(id), "
        "visao_valor_id INTEGER NOT NULL REFERENCES visao_valor(id), coleta_id INTEGER NOT NULL REFERENCES coleta(id), "
        "PRIMARY KEY (visao_valor_id, coleta_id))",
        "CREATE INDEX ix_visao_valor_coleta ON visao_valor_coleta (coleta_id)",
        "INSERT INTO visao_valor_coleta SELECT v.derivacao_id, v.id, k.id FROM visao_valor v, json_each(v.coletas_json) j "
        "JOIN coleta k ON k.snapshot_uid = j.value",
        _gatilho("ri_visao_valor_coleta_insert", "INSERT", "visao_valor_coleta",
                 "NOT EXISTS (SELECT 1 FROM visao_valor v, json_each(v.coletas_json) j JOIN coleta k ON k.snapshot_uid = "
                 "j.value WHERE v.id = NEW.visao_valor_id AND v.derivacao_id = NEW.derivacao_id AND k.id = NEW.coleta_id)",
                 "visao_valor_coleta fora do coletas_json do valor"),
        "CREATE UNIQUE INDEX ux_conciliacao_rreo ON conciliacao_rreo (derivacao_id, rreo_coleta_id, regra_agregacao_id, "
        "coluna)",
        "CREATE TABLE conciliacao_rreo_coleta (derivacao_id INTEGER NOT NULL, rreo_coleta_id INTEGER NOT NULL, "
        "regra_agregacao_id INTEGER NOT NULL, coluna TEXT NOT NULL, coleta_id INTEGER NOT NULL REFERENCES coleta(id), "
        "PRIMARY KEY (derivacao_id, rreo_coleta_id, regra_agregacao_id, coluna, coleta_id), FOREIGN KEY (derivacao_id, "
        "rreo_coleta_id, regra_agregacao_id, coluna) REFERENCES conciliacao_rreo (derivacao_id, rreo_coleta_id, "
        "regra_agregacao_id, coluna))",
        "INSERT INTO conciliacao_rreo_coleta SELECT c.derivacao_id, c.rreo_coleta_id, c.regra_agregacao_id, c.coluna, "
        "k.id FROM conciliacao_rreo c, json_each(c.coletas_api_json) j JOIN coleta k ON k.snapshot_uid = j.value",
        _gatilho("ri_conciliacao_rreo_coleta_insert", "INSERT", "conciliacao_rreo_coleta",
                 "NOT EXISTS (SELECT 1 FROM conciliacao_rreo c, json_each(c.coletas_api_json) j JOIN coleta k ON "
                 "k.snapshot_uid = j.value WHERE c.derivacao_id = NEW.derivacao_id AND c.rreo_coleta_id = "
                 "NEW.rreo_coleta_id AND c.regra_agregacao_id = NEW.regra_agregacao_id AND c.coluna = NEW.coluna AND "
                 "k.id = NEW.coleta_id)", "conciliacao_rreo_coleta fora do coletas_api_json"),
    ]
    regras_citadas = {"anomalia": ["regra_id"], "verificacao": ["regra_id"], "espelhamento_par": ["regra_pareamento_id"],
                      "visao_valor": ["regra_agregacao_id", "regra_consolidacao_id"],
                      "conciliacao_rreo": ["regra_agregacao_id"]}
    for tabela, colunas in regras_citadas.items():
        quando = " OR ".join(f"(NEW.{c} IS NOT NULL AND NOT EXISTS (SELECT 1 FROM derivacao_regra d WHERE "
                             f"d.derivacao_id = NEW.derivacao_id AND d.regra_id = NEW.{c}))" for c in colunas)
        msg = f"{tabela} cita regra que a sua derivacao nao declarou"
        cmds.append(_gatilho(f"ri_{tabela}_regra_insert", "INSERT", tabela, quando, msg))
        cmds.append(_gatilho(f"ri_{tabela}_regra_update", f"UPDATE OF derivacao_id, {', '.join(colunas)}", tabela,
                             quando, msg))
    cmds += [
        "CREATE TABLE coleta_manifesto (coleta_id INTEGER PRIMARY KEY REFERENCES coleta(id), sha256 TEXT NOT NULL "
        "CHECK (length(sha256) = 64), tamanho INTEGER NOT NULL CHECK (tamanho > 0))",
        "CREATE TRIGGER coleta_manifesto_sem_update BEFORE UPDATE ON coleta_manifesto "
        "BEGIN SELECT RAISE(ABORT, 'hash do manifesto nao se edita'); END",
        "CREATE TRIGGER coleta_manifesto_sem_delete BEFORE DELETE ON coleta_manifesto "
        "BEGIN SELECT RAISE(ABORT, 'hash do manifesto nao se apaga'); END",
        "ALTER TABLE normalizacao_execucao ADD COLUMN sha256_codigo TEXT",
        "ALTER TABLE normalizacao_execucao ADD COLUMN ambiente_json TEXT",
        "ALTER TABLE derivacao_execucao ADD COLUMN sha256_codigo TEXT",
        "ALTER TABLE derivacao_execucao ADD COLUMN sha256_regras TEXT",
        "ALTER TABLE derivacao_execucao ADD COLUMN ambiente_json TEXT",
    ]
    return cmds


MIGRACOES[8] = ("relacoes por gatilho e tabela (camada 1 x coleta, regra declarada, JSON normalizado) e proveniencia "
                "(hash do manifesto, do codigo e das regras de cada execucao)", _migracao_v8())
VERSAO_ESQUEMA = max(MIGRACOES)
# Structural fingerprint of each schema version (impressao_esquema). New version = new fingerprint here.
IMPRESSAO_ESQUEMA = {
    # v4: checked on 05/10/2026 on the active database (created 29/09, migrated 30/09) and on the one built by the code
    4: "ad45413e4a5431eca73afebbf4640c995513203b9def9b38d8cbb83eaa3d3e5a",
    # v5: checked on 06/10/2026 on the one built by the code and on the active database migrated from v4
    5: "d80f1040f98fe0213388991b8f8b574b27ab0ef3a57ac61c4d8dc70bbb54e34e",
    # v6: computed on 09/10/2026 on the one built by the code (the v5 one above is unchanged)
    6: "46b3b3d6caecfb8ccd8e738520dd07296c641211d7b823f142daf33b11751163",
    # v7: computed on 09/10/2026 on the one built by the code
    7: "3e47c42cfde8d126e6d2581c04b3b2f60eccbaa658a93a702fbecf0c5774e120",
    # v8: computed on 09/10/2026 on the one built by the code
    8: "80244cc5f08288f815cce321c4719e4ea2582b75dafb6e07b8b3e3d10c6bb92d",
}

# Per-connection page cache (KiB, negative value = size in KiB in SQLite). The derivation scans ~100 MB of
# records; with the default cache (~2 MB) the same page is re-read from disk hundreds of times.
# Memory is only used as pages are read.
CACHE_KIB = 256 * 1024
_MOTIVO = re.compile(r"[^A-Za-z0-9._-]+")


class MigracaoPendente(Exception):
    pass


class BancoEmPastaSincronizada(Exception):
    pass


# Known root folders of sync services (exact name of a path part, case-insensitive).
# Conservative list: a generic name ("Box", "Sync") could be an ordinary local folder.
_SINCRONIZADAS = {"google drive", "googledrive", "my drive", "meu drive", "icloud drive", "iclouddrive",
                  "mobile documents", "box sync", "box drive", "nextcloud", "owncloud", "pcloud drive"}
_FS_DE_REDE = {"nfs", "nfs4", "cifs", "smb", "smbfs", "smb3", "afpfs", "9p", "fuse.sshfs", "fuse.rclone", "davfs",
               "fuse.davfs"}


def _unidade_de_rede(p):
    """True if `p` is on a network share: UNC path, mapped drive (Windows) or a mounted network file system (Linux,
    /proc/mounts). Best effort: when there is no way to know, False."""
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
    """True if `caminho` is in a synced folder (OneDrive, Dropbox, Google Drive, iCloud, Box, Nextcloud...) or on a
    network drive. What matters is not which service: it is that the active database stays on a local disk."""
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
    """SQL text without comments (-- and /* */) and with whitespace collapsed OUTSIDE literals; a literal stays intact
    (a CHECK with 'FORTE EVIDÊNCIA' must not change)."""
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
                    if j + 1 < n and sql[j + 1] == c:     # doubled quotes: escape inside the literal
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
    """SHA-256 of the database structure: type, name, table and normalized SQL of every sqlite_master object (tables,
    indexes, triggers). Comments and whitespace do not count; columns, types, constraints, indexes and triggers do."""
    itens = sorted((t, nome, tabela, _sql_normalizado(sql)) for t, nome, tabela, sql in con.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'"))
    return hashlib.sha256(json.dumps(itens, ensure_ascii=False).encode()).hexdigest()


def esquema_do_codigo():
    """In-memory connection with the full schema built by the code (esquema.sql + migrations), without data."""
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
    """Each migration is ONE explicit transaction: commands + row in esquema_versao, or nothing.
    `with con:` would not do: in Python's sqlite3 the implicit BEGIN only comes before INSERT/UPDATE/DELETE, and a
    CREATE/ALTER outside a transaction is committed at once (a failure midway would leave the schema half done)."""
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
    except sqlite3.OperationalError:   # file without the table: not a project database (or an interrupted creation)
        return None


def _criar(caminho):
    """New database built in a temporary file next to the target and published only at the end, without
    overwriting: a failure midway (schema, migrations, catalog) leaves no file at the target that looks like an
    existing database."""
    from .armazem import _publicar_sem_sobrescrever
    tmp = caminho.with_name(f"{caminho.name}.criando{os.getpid()}")
    con = _conectar(tmp)
    try:
        con.executescript(ESQUEMA.read_text(encoding="utf-8"))
        with con:
            con.execute("INSERT INTO esquema_versao VALUES (?,?,?,NULL)", (VERSAO_BASE, DESCRICAO_BASE, agora()))
        _migrar(con, VERSAO_BASE, None)  # new database: nothing to protect
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
    """Opens (creating it if needed) the database. Every structural change to an existing database is preceded by a
    backup. Without `caminho`, opens the ACTIVE database (cfg.banco), which is refused in a synced or network folder."""
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
    if _falta_do_armazem(con):
        from .armazem import Armazem
        completar_do_armazem(con, Armazem(cfg.snapshots))   # v7/v8 rows of the existing collections, from the store
    esperado = IMPRESSAO_ESQUEMA.get(VERSAO_ESQUEMA)
    if esperado and impressao_esquema(con) != esperado:     # warning; the 'esquema_confere' gate fails the load
        log.warning("esquema de %s difere do esquema v%d do código (impressão estrutural): ver portão "
                    "'esquema_confere'", caminho, VERSAO_ESQUEMA)
    _semear_catalogo(con)
    return con


def _semear_catalogo(con):
    """Rules, rule parameters and governance decisions from the code go into the database (INSERT OR IGNORE only)."""
    from . import regras
    with con:
        regras.semear(con)


def backup(con, cfg, motivo, operacional=False, manter=3):
    """Consistent copy (SQLite backup API), written to a temporary file and then moved.

    * default (before a structural change, an import, manual): `backups/`, NEVER deleted automatically;
    * operational (before deleting a run, which can be reprocessed from the raw data): local folder
      `backups_operacionais/`, outside OneDrive. The `manter` most recent of this kind stay as they are; older ones
      are COMPRESSED (<name>.gz, checked byte for byte), never deleted (critical review, D6).
      A file listed in `backups_operacionais/PRESERVAR.txt` (one name per line) is left out of the retention.
    The name never repeats an existing backup's (suffix -2, -3... within the same second)."""
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
    """Operational .sqlite backups subject to retention (without the ones in PRESERVAR.txt), from oldest to newest
    (the name starts with the timestamp)."""
    lista = pasta / "PRESERVAR.txt"
    preservar = set(lista.read_text(encoding="utf-8").split()) if lista.exists() else set()
    return sorted(p for p in pasta.glob("*.sqlite") if p.name not in preservar)


def _fora_da_retencao(pasta, manter):
    """The ones under retention beyond the `manter` most recent."""
    return _na_retencao(pasta)[:-manter] if manter else _na_retencao(pasta)


def comprimir_backup(arquivo, bloco=1 << 20):
    """Compresses a backup into <name>.gz WITHOUT losing anything (critical review, D6): writes to a temporary file,
    checks that decompressing returns the same bytes (SHA-256) and only then removes the original. Refuses to
    overwrite an existing .gz. To get the original file back: python -m gzip -d <name>.gz"""
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
    """Compresses the operational backups outside the window of the `manter` most recent, INCLUDING the preserved ones
    (PRESERVAR.txt protects against deletion; compressing deletes nothing). The most recent stay as they are, ready
    to restore. `simular` only lists."""
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
    """Bytes used per folder (active database, store, backups, operational backups, logs): to follow the growth
    (critical review, D6)."""
    def total(p):
        p = Path(p)
        if p.is_file():
            return p.stat().st_size
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0
    return {"banco": total(cfg.banco), "armazem": total(cfg.snapshots), "backups": total(cfg.backups),
            "backups_operacionais": total(cfg.backups_operacionais), "logs": total(cfg.logs)}


def compactar(con, caminho):
    """VACUUM: returns to the disk the space of deleted runs. It changes no data."""
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
    """Puts a snapshot into layer 0 (in a transaction). Idempotent by snapshot_uid."""
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
            comprimido = armazem.ler_comprimido(r["sha256"])       # validates the hash format
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
        if _tem_tabela(con, "coleta_tempo"):    # v7: start and conclusion, from the manifest
            con.execute(SQL_TEMPO, (cid, *tempos_do_manifesto(m)))
        if _tem_tabela(con, "coleta_manifesto"):    # v8: hash of the manifest bytes just written
            con.execute("INSERT INTO coleta_manifesto VALUES (?,?,?)", (cid, *hash_do_manifesto(armazem, rel)))
    return cid, True


def _falta_do_armazem(con):
    """True if some collection lacks a row that comes from the store (coleta_tempo v7, coleta_manifesto v8)."""
    for tabela in ("coleta_tempo", "coleta_manifesto"):
        if _tem_tabela(con, tabela) and con.execute(
                f"SELECT 1 FROM coleta c LEFT JOIN {tabela} t ON t.coleta_id = c.id WHERE t.coleta_id IS NULL "
                "LIMIT 1").fetchone():
            return True
    return False


def _tem_coluna(con, tabela, coluna):
    return any(r[1] == coluna for r in con.execute(f"PRAGMA table_info({tabela})"))


def _tem_tabela(con, nome):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nome,)).fetchone() is not None


SQL_TEMPO = "INSERT INTO coleta_tempo VALUES (?,?,?,?,?)"
# Clock precision by stamp origin when the conclusion is the last response received (no recorded conclusion).
_PRECISAO_DA_ORIGEM = {"relogio_coletor": "ultima_resposta", "manifesto": "ultima_resposta",
                       "cabecalho_http": "ultima_resposta", "mtime_arquivo": "aproximada"}


def tempos_do_manifesto(m):
    """(inicio_em, concluida_em, fonte_conclusao, precisao) of a snapshot, from its manifest ONLY:
      * 'manifesto': the recorded conclusion (coleta_finalizada_em, collector since 05/10/2026) - 'exata' when the
        stamp is the collector's clock;
      * 'ultima_resposta': the latest recebida_em of the responses and of the second read - the last byte received;
        the stamp origin says how precise it is (file mtime = 'aproximada');
      * 'sem_evidencia': no conclusion and no response time - NULL, never invented.
    Every instant goes through rp.instante (Brasilia offset): equivalent time zones become the same text."""
    inicio = instante(m["coletada_em"])
    origem = m.get("origem_carimbo")
    if m.get("coleta_finalizada_em"):
        return inicio, instante(m["coleta_finalizada_em"]), "manifesto", \
            "exata" if origem == "relogio_coletor" else _PRECISAO_DA_ORIGEM.get(origem, "aproximada")
    recebidas = [instante(r["recebida_em"]) for r in list(m.get("respostas") or []) + list(m.get("segunda_leitura") or [])
                 if r.get("recebida_em")]
    if recebidas:
        return inicio, max(recebidas), "ultima_resposta", _PRECISAO_DA_ORIGEM.get(origem, "aproximada")
    return inicio, None, "sem_evidencia", "desconhecida"


def completar_do_armazem(con, armazem):
    """Rows that come from the store and that a database from before v7/v8 does not have yet: start and conclusion
    (coleta_tempo) and the manifest hash (coleta_manifesto). Returns {"tempos": (filled, problems), "manifestos": ...}."""
    saida = {}
    if _tem_tabela(con, "coleta_tempo"):
        saida["tempos"] = completar_tempos(con, armazem)
    if _tem_tabela(con, "coleta_manifesto"):
        saida["manifestos"] = completar_manifestos(con, armazem)
    return saida


def hash_do_manifesto(armazem, rel):
    """(sha256, size) of the manifest file bytes as they are in the store."""
    b = armazem.bytes_do_manifesto(rel)
    return sha256(b), len(b)


def completar_manifestos(con, armazem):
    """coleta_manifesto for the collections without it (databases from before v8): the hash of the manifest file AS IT
    IS TODAY. It does not prove the file was never changed before this moment - `verificar` compares its content with
    the database field by field, and the root manifest (rp.raiz) kept OUTSIDE the database is the external
    reference. Returns (filled, problems)."""
    faltam = con.execute("SELECT c.id, c.manifesto FROM coleta c LEFT JOIN coleta_manifesto m ON m.coleta_id = c.id "
                         "WHERE m.coleta_id IS NULL ORDER BY c.id").fetchall()
    feitos, problemas = 0, []
    for cid, rel in faltam:
        try:
            h, n = hash_do_manifesto(armazem, rel)
        except (OSError, ValueError) as e:
            problemas.append(f"coleta {cid}: manifesto {rel} ilegível ({type(e).__name__}: {e})")
            continue
        with con:
            con.execute("INSERT INTO coleta_manifesto VALUES (?,?,?)", (cid, h, n))
        feitos += 1
    if problemas:
        log.warning("%d coleta(s) sem hash de manifesto: %s", len(problemas), "; ".join(problemas[:3]))
    return feitos, problemas


def completar_tempos(con, armazem):
    """coleta_tempo for the collections that do not have it yet (databases from before v7), read from each one's
    manifest in the store. Idempotent. A manifest that cannot be read leaves the collection without a row (the
    'tempos_das_coletas' gate fails), never a guessed time. Returns (filled, problems)."""
    faltam = con.execute("SELECT c.id, c.manifesto FROM coleta c LEFT JOIN coleta_tempo t ON t.coleta_id = c.id "
                         "WHERE t.coleta_id IS NULL ORDER BY c.id").fetchall()
    feitos, problemas = 0, []
    for cid, rel in faltam:
        try:
            m = armazem.ler_manifesto(rel)
        except (OSError, ValueError, KeyError, TypeError) as e:   # missing or invalid manifest: recorded, never guessed
            problemas.append(f"coleta {cid}: manifesto {rel} ilegível ({type(e).__name__}: {e})")
            continue
        with con:
            con.execute(SQL_TEMPO, (cid, *tempos_do_manifesto(m)))
        feitos += 1
    if problemas:
        log.warning("%d coleta(s) sem tempo de conclusão: %s", len(problemas), "; ".join(problemas[:3]))
    return feitos, problemas


def corpo(con, sha):
    """Original bytes of a layer 0 object, checked against size and hash."""
    linha = con.execute("SELECT dados, tamanho FROM objeto_bruto WHERE sha256=?", (sha,)).fetchone()
    if linha is None:
        raise KeyError(f"objeto {sha} nao esta no banco")
    comp, tam = linha
    b = descomprimir(comp, tam)
    if sha256(b) != sha:
        raise ObjetoCorrompido(f"{sha}: conteúdo não confere com o hash")
    return b


def registrar_evidencia(con, armazem, rel, m):
    """Puts an external evidence (e-SIC, regulation, note...) into layer 0. Idempotent by evidencia_uid.
    The file itself lives in the store and in the database (objeto_bruto), checked against SHA-256 and size."""
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
    """Records in the database every manifest of the store (collections and evidence) not yet in it."""
    novos = 0
    for rel, m in armazem.manifestos():
        _, criado = registrar_manifesto(con, armazem, rel, m)
        novos += criado
    for rel, m in armazem.evidencias():
        _, criado = registrar_evidencia(con, armazem, rel, m)
        novos += criado
    return novos


def reconstruir(cfg, armazem, destino):
    """NEW database at `destino`, from the store only. Refuses to overwrite an existing file.
    '~' becomes the user's folder even when the shell does not expand it (PowerShell)."""
    destino = Path(destino).expanduser()
    if destino.exists():
        raise FileExistsError(f"{destino} já existe: a reconstrução nunca sobrescreve um banco")
    con = abrir(cfg, destino)
    n = sincronizar(con, armazem)
    return con, n


def _diferencas_do_manifesto(con, rel, m, armazem=None):
    """Fields in which the database's layer 0 differs from the manifest (audit REC-01): the snapshot_uid being present
    is not enough; the database must have the same parameters, status, dates and the same responses (order, URL,
    hash, size)."""
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
        if _tem_tabela(con, "coleta_tempo"):      # v7: start and conclusion recomputed from the manifest
            tempo = con.execute("SELECT inicio_em, concluida_em, fonte_conclusao, precisao FROM coleta_tempo WHERE "
                                "coleta_id=?", (cid,)).fetchone()
            if tempo is None or tuple(tempo) != tempos_do_manifesto(m):
                dif.append("tempo_da_coleta")
        if armazem is not None and _tem_tabela(con, "coleta_manifesto"):   # v8: the manifest is the recorded one
            gravado = con.execute("SELECT sha256, tamanho FROM coleta_manifesto WHERE coleta_id=?", (cid,)).fetchone()
            if gravado is None or tuple(gravado) != hash_do_manifesto(armazem, rel):
                dif.append("hash_do_manifesto")
        return dif
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        return [f"manifesto sem campo esperado ({type(e).__name__}: {e})"]


def verificar(con, armazem):
    """Integrity problems between database and store (empty list = intact): store objects and manifests, presence in
    both directions (manifest x collection, evidence x database), each collection equal to its manifest field by
    field and each database object checked against its hash."""
    problemas = [f"armazém: {p}" for p in armazem.verificar()]
    registrados = {u for (u,) in con.execute("SELECT snapshot_uid FROM coleta")}
    no_disco = {}
    itens, _ = armazem.manifestos_e_erros()      # the unreadable ones already came from armazem.verificar()
    for rel, m in itens:
        no_disco[m["snapshot_uid"]] = rel
        if m["snapshot_uid"] not in registrados:
            problemas.append(f"manifesto fora do banco: {rel}")
    for uid, rel in con.execute("SELECT snapshot_uid, manifesto FROM coleta"):
        if uid not in no_disco:
            problemas.append(f"coleta sem manifesto no armazém: {uid} ({rel})")
    for rel, m in itens:
        if m["snapshot_uid"] in registrados:
            dif = _diferencas_do_manifesto(con, rel, m, armazem)
            if dif:
                problemas.append(f"coleta difere do manifesto {rel}: {', '.join(dif)}")
    evid, _ = armazem.evidencias_e_erros()        # the unreadable ones already came from armazem.verificar()
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
