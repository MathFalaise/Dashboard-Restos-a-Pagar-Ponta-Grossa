-- =====================================================================
-- Restos a Pagar de Ponta Grossa — esquema proposto (Etapa 03)
-- Dialeto: SQLite 3.35+ (proposta; a escolha final da tecnologia é do usuário)
--
-- Três camadas, com dependência só para baixo:
--   0. BRUTO       imutável: o que a fonte devolveu, byte a byte
--   1. NORMALIZADO reprocessável: o bruto tipado, SEM interpretação
--   2. DERIVADO    reprocessável: interpretações, sempre com a versão da regra
--
-- Convenções:
--   * dinheiro em centavos (INTEGER), sufixo _c. A normalização recusa
--     valor com mais de 2 casas decimais em vez de arredondar.
--   * datas e datas/horas em TEXT ISO-8601; horário de Brasília (-03:00).
--   * nenhuma tabela das camadas 1 e 2 tem chave que obrigue a descartar um
--     registro bruto: a chave é sempre a posição de origem (resposta, índice).
-- =====================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- CAMADA 0 — BRUTO (imutável)
-- ---------------------------------------------------------------------

-- Versão do programa que coletou. O hash do código fixa o que "versão" quer dizer.
CREATE TABLE coletor_versao (
    id              INTEGER PRIMARY KEY,
    nome            TEXT NOT NULL,
    versao          TEXT NOT NULL,
    sha256_codigo   TEXT,
    descricao       TEXT,
    registrado_em   TEXT NOT NULL,
    UNIQUE (nome, versao)
);

-- Uma coleta = um snapshot: todas as respostas de uma consulta num momento.
-- O mesmo corte (mesmos parâmetros) coletado em outro momento é OUTRA coleta.
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
    parametros_json     TEXT NOT NULL,            -- JSON canônico (chaves ordenadas)
    -- parâmetros promovidos a coluna, para consulta; NULL quando não se aplicam
    entidade            INTEGER,
    exercicio           INTEGER,
    data_inicial        TEXT,
    data_final          TEXT,
    tipo_pesquisa       TEXT,                     -- NULL = consulta sem tipo
    anoempenho          INTEGER,                  -- movimentação
    empenho             INTEGER,                  -- movimentação
    id_arquivo          INTEGER,                  -- RREO
    coletada_em         TEXT NOT NULL,            -- início da coleta
    origem_carimbo      TEXT NOT NULL CHECK (origem_carimbo IN (
                            'relogio_coletor',    -- preciso
                            'manifesto',          -- preciso (Etapa 02)
                            'cabecalho_http',     -- preciso (Date do servidor)
                            'mtime_arquivo')),    -- APROXIMADO
    status              TEXT NOT NULL CHECK (status IN ('completa', 'incompleta', 'falhou')),
    coletor_versao_id   INTEGER NOT NULL REFERENCES coletor_versao(id),
    observacao          TEXT
);
CREATE INDEX ix_coleta_corte ON coleta (tipo, entidade, exercicio, data_inicial, data_final, tipo_pesquisa, coletada_em);

-- Cada resposta HTTP, em bytes, com hash. Uma coleta paginada tem várias.
CREATE TABLE resposta_bruta (
    id               INTEGER PRIMARY KEY,
    coleta_id        INTEGER NOT NULL REFERENCES coleta(id),
    ordem            INTEGER NOT NULL,             -- página 0, 1, 2...
    url              TEXT NOT NULL,
    http_status      INTEGER,
    cabecalhos_json  TEXT,
    recebida_em      TEXT,
    corpo            BLOB NOT NULL,
    sha256           TEXT NOT NULL,
    tamanho          INTEGER NOT NULL,
    UNIQUE (coleta_id, ordem)
);

-- Documentos externos: resposta de e-SIC, norma, nota técnica. Também imutável.
CREATE TABLE evidencia_externa (
    id               INTEGER PRIMARY KEY,
    tipo             TEXT NOT NULL CHECK (tipo IN ('e-SIC', 'norma', 'nota', 'outro')),
    descricao        TEXT NOT NULL,
    data_documento   TEXT,
    caminho_arquivo  TEXT,
    sha256           TEXT,
    registrada_em    TEXT NOT NULL
);

-- Imutabilidade da camada 0: nada se altera nem se apaga.
CREATE TRIGGER coletor_versao_sem_update BEFORE UPDATE ON coletor_versao BEGIN SELECT RAISE(ABORT, 'camada bruta é imutável'); END;
CREATE TRIGGER coletor_versao_sem_delete BEFORE DELETE ON coletor_versao BEGIN SELECT RAISE(ABORT, 'camada bruta é imutável'); END;
CREATE TRIGGER coleta_sem_update         BEFORE UPDATE ON coleta         BEGIN SELECT RAISE(ABORT, 'camada bruta é imutável'); END;
CREATE TRIGGER coleta_sem_delete         BEFORE DELETE ON coleta         BEGIN SELECT RAISE(ABORT, 'camada bruta é imutável'); END;
CREATE TRIGGER resposta_sem_update       BEFORE UPDATE ON resposta_bruta BEGIN SELECT RAISE(ABORT, 'camada bruta é imutável'); END;
CREATE TRIGGER resposta_sem_delete       BEFORE DELETE ON resposta_bruta BEGIN SELECT RAISE(ABORT, 'camada bruta é imutável'); END;
CREATE TRIGGER evidencia_sem_update      BEFORE UPDATE ON evidencia_externa BEGIN SELECT RAISE(ABORT, 'camada bruta é imutável'); END;
CREATE TRIGGER evidencia_sem_delete      BEFORE DELETE ON evidencia_externa BEGIN SELECT RAISE(ABORT, 'camada bruta é imutável'); END;

-- ---------------------------------------------------------------------
-- CAMADA 1 — NORMALIZADO (reprocessável; tipagem fiel, sem interpretação)
-- ---------------------------------------------------------------------

CREATE TABLE normalizacao_execucao (
    id                  INTEGER PRIMARY KEY,
    normalizador_versao TEXT NOT NULL,
    executada_em        TEXT NOT NULL,
    observacao          TEXT
);

-- Um registro da listagem = um item de content[] de uma resposta.
-- Chave = posição de origem: registros com a mesma chave de negócio NÃO são
-- fundidos nem descartados (regra 6).
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
    orgao                  TEXT,     -- NULL quando a chave não veio (ver chaves_ausentes)
    unidade                TEXT,
    funcao                 TEXT,
    sub_funcao             TEXT,
    programa               TEXT,
    projeto                TEXT,
    elemento               TEXT,
    desdobra_desp          TEXT,
    sub_desdobramento      TEXT,
    chaves_ausentes        TEXT NOT NULL,   -- JSON: chaves esperadas que não vieram
    chaves_extras          TEXT NOT NULL,   -- JSON: chaves que vieram e o normalizador não conhece
    PRIMARY KEY (normalizacao_id, resposta_id, indice)
);
CREATE INDEX ix_rp_registro_chave ON rp_registro (normalizacao_id, coleta_id, entidade, anoempenho, empenho);

-- Lançamento da movimentação de um empenho, com os rótulos EXATAMENTE como a
-- API os dá (sufixo _rotulo). A interpretação dos rótulos trocados nos
-- lançamentos 40/41 fica na camada 2 (regra MOV-REF).
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

-- Valores transcritos do PDF do RREO Anexo VII (transcrição, não interpretação).
CREATE TABLE rreo_valor (
    normalizacao_id   INTEGER NOT NULL REFERENCES normalizacao_execucao(id),
    coleta_id         INTEGER NOT NULL REFERENCES coleta(id),
    extrator_versao   TEXT NOT NULL,
    escopo            TEXT NOT NULL CHECK (escopo IN ('entidade', 'consolidado')),
    exercicio         INTEGER NOT NULL,
    data_final        TEXT NOT NULL,       -- fim do período do demonstrativo
    emitido_em        TEXT,                -- como impresso no rodapé
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
-- CAMADA 2 — DERIVADO (reprocessável; tudo carrega a versão da regra)
-- ---------------------------------------------------------------------

-- Catálogo de regras. Uma regra nunca é editada: mudança = nova versão.
CREATE TABLE regra (
    id                INTEGER PRIMARY KEY,
    codigo            TEXT NOT NULL,           -- 'S1', 'CAT', 'PAR-24', 'CONS-PAR', ...
    versao            INTEGER NOT NULL,
    tipo              TEXT NOT NULL CHECK (tipo IN ('classificacao','formula','anomalia','pareamento','consolidacao','agregacao','conciliacao','interpretacao')),
    uso               TEXT NOT NULL CHECK (uso IN ('estavel', 'experimental')),
    status_evidencia  TEXT NOT NULL CHECK (status_evidencia IN ('CONFIRMADO','FORTE EVIDÊNCIA','HIPÓTESE','NÃO DETERMINADO')),
    definicao         TEXT NOT NULL,
    fonte             TEXT NOT NULL,           -- seção do relatório que sustenta a regra
    UNIQUE (codigo, versao)
);
CREATE TRIGGER regra_sem_update BEFORE UPDATE ON regra BEGIN SELECT RAISE(ABORT, 'regra não se edita: crie nova versão'); END;

CREATE TABLE derivacao_execucao (
    id               INTEGER PRIMARY KEY,
    normalizacao_id  INTEGER NOT NULL REFERENCES normalizacao_execucao(id),
    derivador_versao TEXT NOT NULL,
    regras_json      TEXT NOT NULL,            -- ids das regras usadas
    executada_em     TEXT NOT NULL,
    hash_resultado   TEXT                      -- para testar reprocessamento determinístico
);

-- Classificação e saldos por registro (1:1 com rp_registro).
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

-- Interpretação da movimentação (resolve rótulos trocados; regra MOV-REF).
CREATE TABLE movimentacao_interpretada (
    derivacao_id           INTEGER NOT NULL REFERENCES derivacao_execucao(id),
    resposta_id            INTEGER NOT NULL,
    indice                 INTEGER NOT NULL,
    liquidacao_exercicio   INTEGER,     -- a que liquidação o lançamento se refere
    liquidacao_numero      INTEGER,
    efeito                 TEXT NOT NULL,  -- 'empenho','cancelamento','liquidacao','pagamento','retencao', com sinal no valor
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

-- Par espelhado: DOIS registros brutos ligados. Nenhum dos dois é removido.
CREATE TABLE espelhamento_par (
    derivacao_id          INTEGER NOT NULL REFERENCES derivacao_execucao(id),
    regra_pareamento_id   INTEGER NOT NULL REFERENCES regra(id),
    exercicio             INTEGER NOT NULL,
    data_inicial          TEXT NOT NULL,
    data_final            TEXT NOT NULL,
    -- lado A e lado B: posição de origem de cada registro
    coleta_a_id INTEGER NOT NULL, resposta_a_id INTEGER NOT NULL, indice_a INTEGER NOT NULL,
    entidade_a INTEGER NOT NULL, anoempenho_a INTEGER NOT NULL, empenho_a INTEGER NOT NULL,
    coleta_b_id INTEGER NOT NULL, resposta_b_id INTEGER NOT NULL, indice_b INTEGER NOT NULL,
    entidade_b INTEGER NOT NULL, anoempenho_b INTEGER NOT NULL, empenho_b INTEGER NOT NULL,
    inscrito_a_c          INTEGER NOT NULL,   -- proc + aproc na abertura
    inscrito_b_c          INTEGER NOT NULL,
    mesma_inscricao       INTEGER NOT NULL,   -- proc e aproc iguais nos dois lados
    relacao_inscricao     TEXT NOT NULL CHECK (relacao_inscricao IN (
                              'igual',                  -- inscrição A = inscrição B
                              'a_e_saldo_final_de_b',   -- inscrição A = S1 de B no fim do corte
                              'outra')),
    execucao_a_c          INTEGER NOT NULL,   -- |pago| + |cancelado| + |liquidado| do lado A
    execucao_b_c          INTEGER NOT NULL,
    lado_com_execucao     TEXT NOT NULL CHECK (lado_com_execucao IN ('A','B','ambos','nenhum'))
);

-- Valor agregado de uma visão do Município (ou de uma entidade), por componente.
CREATE TABLE visao_valor (
    id                        INTEGER PRIMARY KEY,
    derivacao_id              INTEGER NOT NULL REFERENCES derivacao_execucao(id),
    visao                     TEXT NOT NULL CHECK (visao IN ('publicado','analitico','entidade')),
    regra_agregacao_id        INTEGER NOT NULL REFERENCES regra(id),  -- RREO-COL vN: como os registros viram colunas
    regra_consolidacao_id     INTEGER REFERENCES regra(id),   -- só na visão analítica
    entidade                  INTEGER,                         -- só na visão por entidade
    exercicio                 INTEGER NOT NULL,
    data_final                TEXT NOT NULL,
    coletas_json              TEXT NOT NULL,                   -- snapshots usados
    componente                TEXT NOT NULL,                   -- 'a'...'k', 'S1', 'S2', 'S3'
    valor_c                   INTEGER NOT NULL
);
-- NULL não participa de unicidade em SQLite: IFNULL torna a chave efetiva.
CREATE UNIQUE INDEX ux_visao_valor ON visao_valor
    (derivacao_id, visao, regra_agregacao_id, IFNULL(regra_consolidacao_id, 0), IFNULL(entidade, 0), exercicio, data_final, componente);

-- Conciliação RREO × API: registro de diferença, nunca correção.
CREATE TABLE conciliacao_rreo (
    derivacao_id    INTEGER NOT NULL REFERENCES derivacao_execucao(id),
    rreo_coleta_id  INTEGER NOT NULL,
    regra_agregacao_id INTEGER NOT NULL REFERENCES regra(id),
    escopo          TEXT NOT NULL,
    entidade        INTEGER,                 -- NULL no consolidado
    exercicio       INTEGER NOT NULL,
    data_final      TEXT NOT NULL,
    coletas_api_json TEXT NOT NULL,
    coluna          TEXT NOT NULL,
    valor_rreo_c    INTEGER NOT NULL,
    valor_api_c     INTEGER NOT NULL,
    diferenca_c     INTEGER NOT NULL,        -- API − RREO
    PRIMARY KEY (derivacao_id, rreo_coleta_id, regra_agregacao_id, coletas_api_json, coluna)
);

-- Resultado das verificações de integridade de cada derivação (quantos
-- itens verificados, quantos falharam). Falha não bloqueia: é registrada.
CREATE TABLE verificacao (
    derivacao_id  INTEGER NOT NULL REFERENCES derivacao_execucao(id),
    regra_id      INTEGER NOT NULL REFERENCES regra(id),
    descricao     TEXT NOT NULL,
    escopo_json   TEXT NOT NULL,
    verificados   INTEGER NOT NULL,
    falhas        INTEGER NOT NULL
);

-- ---------------------------------------------------------------------
-- CONSULTA "COMO ESTAVA EM": o snapshot vigente de cada corte numa data.
-- Uso: SELECT ... FROM coleta WHERE id IN (SELECT id FROM snapshot_vigente WHERE ...)
-- com o parâmetro :em aplicado em coletada_em <= :em (ver consultas.py).
-- ---------------------------------------------------------------------
CREATE VIEW snapshot_rp AS
SELECT id, entidade, exercicio, data_inicial, data_final, tipo_pesquisa, coletada_em, origem_carimbo
  FROM coleta
 WHERE tipo = 'rp_listagem' AND status = 'completa';
