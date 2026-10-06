-- =====================================================================
-- Restos a Pagar of Ponta Grossa - proposed schema (stage 03)
-- Dialect: SQLite 3.35+ (a proposal; the final choice of technology is the user's)
--
-- Three layers, with dependencies only downwards:
--   0. RAW         immutable: what the source returned, byte by byte
--   1. NORMALIZED  reprocessable: the typed raw data, WITHOUT interpretation
--   2. DERIVED     reprocessable: interpretations, always with the rule version
--
-- Conventions:
--   * money in cents (INTEGER), suffix _c. Normalization refuses a value
--     with more than 2 decimal places instead of rounding.
--   * dates and date/times as ISO-8601 TEXT; Brasilia time (-03:00).
--   * no table of layers 1 and 2 has a key that forces discarding a raw
--     record: the key is always the position of origin (response, index).
-- =====================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- LAYER 0 - RAW (immutable)
-- ---------------------------------------------------------------------

-- Version of the program that collected. The code hash pins what "version" means.
CREATE TABLE coletor_versao (
    id              INTEGER PRIMARY KEY,
    nome            TEXT NOT NULL,
    versao          TEXT NOT NULL,
    sha256_codigo   TEXT,
    descricao       TEXT,
    registrado_em   TEXT NOT NULL,
    UNIQUE (nome, versao)
);

-- One collection = one snapshot: all responses of a query at one moment.
-- The same cut-off (same parameters) collected at another moment is ANOTHER collection.
CREATE TABLE coleta (
    id                  INTEGER PRIMARY KEY,
    tipo                TEXT NOT NULL CHECK (tipo IN (
                            'rp_listagem',        -- /empenhos/restos-a-pagar
                            'movimentacao',       -- /empenhos/detalhe/movimentacao
                            'rreo_pdf',           -- /api/files/arquivo/{id}
                            'publicacoes',        -- /api/publicacoes/{grupo}
                            'entidades',          -- /api/entidades/lista
                            'exercicios')),       -- /api/exercicios/entidade/{id}
    endpoint            TEXT NOT NULL,
    parametros_json     TEXT NOT NULL,            -- canonical JSON (sorted keys)
    -- parameters promoted to columns, for querying; NULL when they do not apply
    entidade            INTEGER,
    exercicio           INTEGER,
    data_inicial        TEXT,
    data_final          TEXT,
    tipo_pesquisa       TEXT,                     -- NULL = query without type
    anoempenho          INTEGER,                  -- movement
    empenho             INTEGER,                  -- movement
    id_arquivo          INTEGER,                  -- RREO
    coletada_em         TEXT NOT NULL,            -- start of the collection
    origem_carimbo      TEXT NOT NULL CHECK (origem_carimbo IN (
                            'relogio_coletor',    -- precise
                            'manifesto',          -- precise (stage 02)
                            'cabecalho_http',     -- precise (server Date)
                            'mtime_arquivo')),    -- APPROXIMATE
    status              TEXT NOT NULL CHECK (status IN ('completa', 'incompleta', 'falhou')),
    coletor_versao_id   INTEGER NOT NULL REFERENCES coletor_versao(id),
    observacao          TEXT
);
CREATE INDEX ix_coleta_corte ON coleta (tipo, entidade, exercicio, data_inicial, data_final, tipo_pesquisa, coletada_em);

-- Each HTTP response, in bytes, with a hash. A paginated collection has several.
CREATE TABLE resposta_bruta (
    id               INTEGER PRIMARY KEY,
    coleta_id        INTEGER NOT NULL REFERENCES coleta(id),
    ordem            INTEGER NOT NULL,             -- page 0, 1, 2...
    url              TEXT NOT NULL,
    http_status      INTEGER,
    cabecalhos_json  TEXT,
    recebida_em      TEXT,
    corpo            BLOB NOT NULL,
    sha256           TEXT NOT NULL,
    tamanho          INTEGER NOT NULL,
    UNIQUE (coleta_id, ordem)
);

-- External documents: FOI response, regulation, technical note. Also immutable.
CREATE TABLE evidencia_externa (
    id               INTEGER PRIMARY KEY,
    tipo             TEXT NOT NULL CHECK (tipo IN ('e-SIC', 'norma', 'nota', 'outro')),
    descricao        TEXT NOT NULL,
    data_documento   TEXT,
    caminho_arquivo  TEXT,
    sha256           TEXT,
    registrada_em    TEXT NOT NULL
);

-- Immutability of layer 0: nothing is changed or deleted.
CREATE TRIGGER coletor_versao_sem_update BEFORE UPDATE ON coletor_versao BEGIN SELECT RAISE(ABORT, 'camada bruta é imutável'); END;
CREATE TRIGGER coletor_versao_sem_delete BEFORE DELETE ON coletor_versao BEGIN SELECT RAISE(ABORT, 'camada bruta é imutável'); END;
CREATE TRIGGER coleta_sem_update         BEFORE UPDATE ON coleta         BEGIN SELECT RAISE(ABORT, 'camada bruta é imutável'); END;
CREATE TRIGGER coleta_sem_delete         BEFORE DELETE ON coleta         BEGIN SELECT RAISE(ABORT, 'camada bruta é imutável'); END;
CREATE TRIGGER resposta_sem_update       BEFORE UPDATE ON resposta_bruta BEGIN SELECT RAISE(ABORT, 'camada bruta é imutável'); END;
CREATE TRIGGER resposta_sem_delete       BEFORE DELETE ON resposta_bruta BEGIN SELECT RAISE(ABORT, 'camada bruta é imutável'); END;
CREATE TRIGGER evidencia_sem_update      BEFORE UPDATE ON evidencia_externa BEGIN SELECT RAISE(ABORT, 'camada bruta é imutável'); END;
CREATE TRIGGER evidencia_sem_delete      BEFORE DELETE ON evidencia_externa BEGIN SELECT RAISE(ABORT, 'camada bruta é imutável'); END;

-- ---------------------------------------------------------------------
-- LAYER 1 - NORMALIZED (reprocessable; faithful typing, without interpretation)
-- ---------------------------------------------------------------------

CREATE TABLE normalizacao_execucao (
    id                  INTEGER PRIMARY KEY,
    normalizador_versao TEXT NOT NULL,
    executada_em        TEXT NOT NULL,
    observacao          TEXT
);

-- One listing record = one content[] item of a response.
-- Key = position of origin: records with the same business key are NOT
-- merged or discarded (rule 6).
CREATE TABLE rp_registro (
    normalizacao_id        INTEGER NOT NULL REFERENCES normalizacao_execucao(id),
    resposta_id            INTEGER NOT NULL REFERENCES resposta_bruta(id),
    indice                 INTEGER NOT NULL,
    coleta_id              INTEGER NOT NULL REFERENCES coleta(id),
    entidade               INTEGER NOT NULL,
    anoempenho             INTEGER NOT NULL,
    empenho                INTEGER NOT NULL,
    empenho_exercicio      TEXT,
    data_emissao           TEXT,
    programatica           TEXT,
    fonte_recurso          INTEGER,
    descricao_fonte        TEXT,
    fornecedor             INTEGER,
    nome                   TEXT,
    cnpj                   TEXT,
    cnpj_nome              TEXT,
    proc_c                 INTEGER NOT NULL,
    aproc_c                INTEGER NOT NULL,
    cancelado_proc_c       INTEGER NOT NULL,
    pago_proc_c            INTEGER NOT NULL,
    pago_proc_estornado_c  INTEGER NOT NULL,
    cancelado_aproc_c      INTEGER NOT NULL,
    pago_aproc_c           INTEGER NOT NULL,
    pago_aproc_estornado_c INTEGER NOT NULL,
    liquidado_c            INTEGER NOT NULL,
    retencao_c             INTEGER NOT NULL,
    orgao                  TEXT,     -- NULL when the key did not come (see chaves_ausentes)
    unidade                TEXT,
    funcao                 TEXT,
    sub_funcao             TEXT,
    programa               TEXT,
    projeto                TEXT,
    elemento               TEXT,
    desdobra_desp          TEXT,
    sub_desdobramento      TEXT,
    chaves_ausentes        TEXT NOT NULL,   -- JSON: expected keys that did not come
    chaves_extras          TEXT NOT NULL,   -- JSON: keys that came and the normalizer does not know
    PRIMARY KEY (normalizacao_id, resposta_id, indice)
);
CREATE INDEX ix_rp_registro_chave ON rp_registro (normalizacao_id, coleta_id, entidade, anoempenho, empenho);

-- Movement entry of a commitment, with the labels EXACTLY as the
-- API gives them (suffix _rotulo). The interpretation of the swapped labels in
-- entries 40/41 lives in layer 2 (rule MOV-REF).
CREATE TABLE movimentacao_lancamento (
    normalizacao_id               INTEGER NOT NULL REFERENCES normalizacao_execucao(id),
    resposta_id                   INTEGER NOT NULL REFERENCES resposta_bruta(id),
    indice                        INTEGER NOT NULL,
    coleta_id                     INTEGER NOT NULL REFERENCES coleta(id),
    entidade                      INTEGER NOT NULL,
    anoempenho                    INTEGER NOT NULL,
    empenho                       INTEGER NOT NULL,
    data                          TEXT NOT NULL,
    tipo_lancamento               INTEGER NOT NULL,
    descricao_tipo                TEXT,
    valor_c                       INTEGER NOT NULL,
    valor_a_liquidar_c            INTEGER,
    valor_a_pagar_c               INTEGER,
    exercicio_liquidacao_rotulo   INTEGER,
    no_liquidacao_rotulo          INTEGER,
    exercicio_pagamento_rotulo    INTEGER,
    no_pagamento_rotulo           INTEGER,
    nro_documento                 TEXT,
    PRIMARY KEY (normalizacao_id, resposta_id, indice)
);

-- Values transcribed from the RREO Annex VII PDF (transcription, not interpretation).
CREATE TABLE rreo_valor (
    normalizacao_id   INTEGER NOT NULL REFERENCES normalizacao_execucao(id),
    coleta_id         INTEGER NOT NULL REFERENCES coleta(id),
    extrator_versao   TEXT NOT NULL,
    escopo            TEXT NOT NULL CHECK (escopo IN ('entidade', 'consolidado')),
    exercicio         INTEGER NOT NULL,
    data_final        TEXT NOT NULL,       -- end of the statement's period
    emitido_em        TEXT,                -- as printed in the footer
    linha             TEXT NOT NULL,       -- 'TOTAL (III)', 'PODER EXECUTIVO', ...
    coluna            TEXT NOT NULL CHECK (coluna IN ('a','b','c','d','e','f','g','h','i','j','k','L')),
    valor_c           INTEGER NOT NULL,
    PRIMARY KEY (normalizacao_id, coleta_id, linha, coluna)
);

CREATE TABLE entidade_ref (
    normalizacao_id  INTEGER NOT NULL REFERENCES normalizacao_execucao(id),
    coleta_id        INTEGER NOT NULL REFERENCES coleta(id),
    entidade         INTEGER NOT NULL,
    nome             TEXT,
    cnpj             TEXT,
    tipo             TEXT,
    PRIMARY KEY (normalizacao_id, coleta_id, entidade)
);

CREATE TABLE exercicio_ref (
    normalizacao_id  INTEGER NOT NULL REFERENCES normalizacao_execucao(id),
    coleta_id        INTEGER NOT NULL REFERENCES coleta(id),
    entidade         INTEGER NOT NULL,
    exercicio        INTEGER NOT NULL,
    aberto           INTEGER,
    fechado          INTEGER,
    PRIMARY KEY (normalizacao_id, coleta_id, entidade, exercicio)
);

-- ---------------------------------------------------------------------
-- LAYER 2 - DERIVED (reprocessable; everything carries the rule version)
-- ---------------------------------------------------------------------

-- Rule catalog. A rule is never edited: a change = a new version.
CREATE TABLE regra (
    id                INTEGER PRIMARY KEY,
    codigo            TEXT NOT NULL,           -- 'S1', 'CAT', 'PAR-24', 'CONS-PAR', ...
    versao            INTEGER NOT NULL,
    tipo              TEXT NOT NULL CHECK (tipo IN ('classificacao','formula','anomalia','pareamento','consolidacao','agregacao','conciliacao','interpretacao')),
    uso               TEXT NOT NULL CHECK (uso IN ('estavel', 'experimental')),
    status_evidencia  TEXT NOT NULL CHECK (status_evidencia IN ('CONFIRMADO','FORTE EVIDÊNCIA','HIPÓTESE','NÃO DETERMINADO')),
    definicao         TEXT NOT NULL,
    fonte             TEXT NOT NULL,           -- report section that supports the rule
    UNIQUE (codigo, versao)
);
CREATE TRIGGER regra_sem_update BEFORE UPDATE ON regra BEGIN SELECT RAISE(ABORT, 'regra não se edita: crie nova versão'); END;

CREATE TABLE derivacao_execucao (
    id               INTEGER PRIMARY KEY,
    normalizacao_id  INTEGER NOT NULL REFERENCES normalizacao_execucao(id),
    derivador_versao TEXT NOT NULL,
    regras_json      TEXT NOT NULL,            -- ids of the rules used
    executada_em     TEXT NOT NULL,
    hash_resultado   TEXT                      -- to test deterministic reprocessing
);

-- Classification and balances per record (1:1 with rp_registro).
CREATE TABLE rp_derivado (
    derivacao_id              INTEGER NOT NULL REFERENCES derivacao_execucao(id),
    resposta_id               INTEGER NOT NULL,
    indice                    INTEGER NOT NULL,
    coleta_id                 INTEGER NOT NULL,
    entidade                  INTEGER NOT NULL,
    anoempenho                INTEGER NOT NULL,
    empenho                   INTEGER NOT NULL,
    categoria                 TEXT NOT NULL CHECK (categoria IN ('processado','nao_processado','ambos','sem_saldo_abertura')),
    faixa_processado          TEXT CHECK (faixa_processado IN ('a','b')),
    faixa_nao_processado      TEXT CHECK (faixa_nao_processado IN ('f','g')),
    s1_saldo_total_c          INTEGER NOT NULL,
    s2_a_liquidar_c           INTEGER NOT NULL,
    s3_liquidado_a_pagar_c    INTEGER NOT NULL,
    cancel_processado_c       INTEGER NOT NULL,
    cancel_nao_processado_c   INTEGER NOT NULL,
    PRIMARY KEY (derivacao_id, resposta_id, indice)
);

-- Interpretation of the movement (resolves swapped labels; rule MOV-REF).
CREATE TABLE movimentacao_interpretada (
    derivacao_id           INTEGER NOT NULL REFERENCES derivacao_execucao(id),
    resposta_id            INTEGER NOT NULL,
    indice                 INTEGER NOT NULL,
    liquidacao_exercicio   INTEGER,     -- which liquidation the entry refers to
    liquidacao_numero      INTEGER,
    efeito                 TEXT NOT NULL,  -- 'empenho','cancelamento','liquidacao','pagamento','retencao', with the sign in the value
    valor_com_sinal_c      INTEGER NOT NULL,
    PRIMARY KEY (derivacao_id, resposta_id, indice)
);

CREATE TABLE anomalia_tipo (
    codigo            TEXT PRIMARY KEY,
    descricao         TEXT NOT NULL,
    status_evidencia  TEXT NOT NULL,
    fonte             TEXT NOT NULL
);

CREATE TABLE anomalia (
    derivacao_id  INTEGER NOT NULL REFERENCES derivacao_execucao(id),
    regra_id      INTEGER NOT NULL REFERENCES regra(id),
    tipo          TEXT NOT NULL REFERENCES anomalia_tipo(codigo),
    coleta_id     INTEGER,
    entidade      INTEGER,
    anoempenho    INTEGER,
    empenho       INTEGER,
    detalhe_json  TEXT
);
CREATE INDEX ix_anomalia ON anomalia (derivacao_id, tipo);

-- Mirrored pair: TWO linked raw records. Neither is removed.
CREATE TABLE espelhamento_par (
    derivacao_id          INTEGER NOT NULL REFERENCES derivacao_execucao(id),
    regra_pareamento_id   INTEGER NOT NULL REFERENCES regra(id),
    exercicio             INTEGER NOT NULL,
    data_inicial          TEXT NOT NULL,
    data_final            TEXT NOT NULL,
    -- side A and side B: position of origin of each record
    coleta_a_id INTEGER NOT NULL, resposta_a_id INTEGER NOT NULL, indice_a INTEGER NOT NULL,
    entidade_a INTEGER NOT NULL, anoempenho_a INTEGER NOT NULL, empenho_a INTEGER NOT NULL,
    coleta_b_id INTEGER NOT NULL, resposta_b_id INTEGER NOT NULL, indice_b INTEGER NOT NULL,
    entidade_b INTEGER NOT NULL, anoempenho_b INTEGER NOT NULL, empenho_b INTEGER NOT NULL,
    inscrito_a_c          INTEGER NOT NULL,   -- proc + aproc at the opening
    inscrito_b_c          INTEGER NOT NULL,
    mesma_inscricao       INTEGER NOT NULL,   -- proc and aproc equal on both sides
    relacao_inscricao     TEXT NOT NULL CHECK (relacao_inscricao IN (
                              'igual',                  -- inscription A = inscription B
                              'a_e_saldo_final_de_b',   -- inscription A = S1 of B at the end of the cut-off
                              'outra')),
    execucao_a_c          INTEGER NOT NULL,   -- |paid| + |cancelled| + |liquidated| of side A
    execucao_b_c          INTEGER NOT NULL,
    lado_com_execucao     TEXT NOT NULL CHECK (lado_com_execucao IN ('A','B','ambos','nenhum'))
);

-- Aggregated value of a view of the Municipality (or of an entity), per component.
CREATE TABLE visao_valor (
    id                        INTEGER PRIMARY KEY,
    derivacao_id              INTEGER NOT NULL REFERENCES derivacao_execucao(id),
    visao                     TEXT NOT NULL CHECK (visao IN ('publicado','analitico','entidade')),
    regra_agregacao_id        INTEGER NOT NULL REFERENCES regra(id),  -- RREO-COL vN: how the records become columns
    regra_consolidacao_id     INTEGER REFERENCES regra(id),   -- only in the analytical view
    entidade                  INTEGER,                         -- only in the per-entity view
    exercicio                 INTEGER NOT NULL,
    data_final                TEXT NOT NULL,
    coletas_json              TEXT NOT NULL,                   -- snapshots used
    componente                TEXT NOT NULL,                   -- 'a'...'k', 'S1', 'S2', 'S3'
    valor_c                   INTEGER NOT NULL
);
-- NULL does not take part in uniqueness in SQLite: IFNULL makes the key effective.
CREATE UNIQUE INDEX ux_visao_valor ON visao_valor
    (derivacao_id, visao, regra_agregacao_id, IFNULL(regra_consolidacao_id, 0), IFNULL(entidade, 0), exercicio, data_final, componente);

-- RREO x API reconciliation: a record of the difference, never a correction.
CREATE TABLE conciliacao_rreo (
    derivacao_id    INTEGER NOT NULL REFERENCES derivacao_execucao(id),
    rreo_coleta_id  INTEGER NOT NULL,
    regra_agregacao_id INTEGER NOT NULL REFERENCES regra(id),
    escopo          TEXT NOT NULL,
    entidade        INTEGER,                 -- NULL in the consolidated view
    exercicio       INTEGER NOT NULL,
    data_final      TEXT NOT NULL,
    coletas_api_json TEXT NOT NULL,
    coluna          TEXT NOT NULL,
    valor_rreo_c    INTEGER NOT NULL,
    valor_api_c     INTEGER NOT NULL,
    diferenca_c     INTEGER NOT NULL,        -- API - RREO
    PRIMARY KEY (derivacao_id, rreo_coleta_id, regra_agregacao_id, coletas_api_json, coluna)
);

-- Result of the integrity checks of each derivation (how many
-- items checked, how many failed). A failure does not block: it is recorded.
CREATE TABLE verificacao (
    derivacao_id  INTEGER NOT NULL REFERENCES derivacao_execucao(id),
    regra_id      INTEGER NOT NULL REFERENCES regra(id),
    descricao     TEXT NOT NULL,
    escopo_json   TEXT NOT NULL,
    verificados   INTEGER NOT NULL,
    falhas        INTEGER NOT NULL
);

-- ---------------------------------------------------------------------
-- "AS IT WAS ON" QUERY: the current snapshot of each cut-off on a date.
-- Usage: SELECT ... FROM coleta WHERE id IN (SELECT id FROM snapshot_vigente WHERE ...)
-- with the :em parameter applied as coletada_em <= :em (see consultas.py).
-- ---------------------------------------------------------------------
CREATE VIEW snapshot_rp AS
SELECT id, entidade, exercicio, data_inicial, data_final, tipo_pesquisa, coletada_em, origem_carimbo
  FROM coleta
 WHERE tipo = 'rp_listagem' AND status = 'completa';
