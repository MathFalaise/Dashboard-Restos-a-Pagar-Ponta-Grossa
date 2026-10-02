# Auditoria técnica completa — coleta, preservação, transformação e publicação de RP

**Data:** 02/10/2026.
**Ramo:** `auditoria-tecnica`, criado de `main` (`333ab3d`).
**Escopo:** todo o código de `app/rp` (coleta, HTTP, armazém, banco, migrações, normalização, derivação, portões, painel, interface), os testes, o repositório e a API real.

**Esta fase não alterou código.** Todo achado foi conferido no código e, quando possível, reproduzido. A coluna "natureza" separa:
- **BUG:** confirmado por reprodução;
- **RISCO:** caminho de falha real, sem ocorrência nos dados atuais;
- **DÍVIDA:** custo de manutenção;
- **MELHORIA:** arquitetura, otimização ou sugestão futura.

Hipótese não aparece como fato: quando algo não foi reproduzido, o texto diz isso.

---

## 0. Linha de base (antes de qualquer mudança)

| Item | Valor |
|---|---|
| Testes de produção | **353 passed, 0 failed**, 174 s (`python -m pytest tests`, Python 3.14.3) |
| Testes da investigação | 26 passed |
| `verificar` | sem problemas |
| `portoes` | apto (com 2 portões "não verificados": camada bruta sem referência e testes) |
| `hash_resultado` | `2f6b4e295ce79593…` (derivações 21 e 23, atual) e `b8a0b2ed2328bf09…` (22 e 24, "como estava em" 29/09/2026) |
| `hash_camada0` | `733670693c01d015…` |
| Esquema | v4 (v2 base + migrações 3 e 4); SQLite 3.50.4; `journal_mode=delete` |
| Banco ativo | 219,4 MB (56.164 páginas de 4 KiB, 0 livres), fora do OneDrive |
| `PRAGMA integrity_check` | ok (3,7 s) |
| `PRAGMA foreign_key_check` | 0 violações |
| Armazém `snapshots/` | 15 MB: 466 manifestos, 375 objetos (0 órfãos, 0 faltando, 0 temporários) |
| Backups | `backups/` 126 MB (4 versionados, 10,8 MB; 1 de 120,5 MB só local) |
| Linhas principais | coleta 466; resposta_bruta 536; rp_registro 457.746 (2 normalizações × 228.873); rp_derivado 632.836 (4 derivações); anomalia 62.516; visao_valor 17.040; conciliacao_rreo 2.064; verificacao 448 |
| Índices explícitos | `ix_coleta_corte`, `ix_rp_registro_chave`, `ix_anomalia`, `ux_visao_valor`, `ux_evidencia_uid` (+17 automáticos de PK/UNIQUE) |
| Gatilhos | 17: imutabilidade da camada 0, do esquema, de `regra` (só UPDATE), `regra_parametro` e `regra_situacao` |

**Reconstrução (fases 9 e 10), executada nesta auditoria:**
- banco novo em `C:\rpaud` só a partir do armazém, em 4 s, seguido de `processar` (11 s) e `processar --em` (2 s);
- `hash_resultado` **igual** nas duas vigências;
- normalização igual registro a registro, por identificadores estáveis: `rp_registro`, movimentação, `rreo_valor`, `entidade_ref` e `exercicio_ref`;
- **diferenças:** `hash_camada0` (DET-02) e o texto de 1 erro em `rreo_extracao` (DET-01).

**Backup e restauração (fase 11):**
- backup pela API do SQLite, cópia restaurada, `integrity_check` ok, 0 violações de FK;
- `hash_resultado` recalculado no restaurado igual ao gravado nas 2 derivações;
- `hash_camada0` igual.

## 1. API do portal (fase 2)

**Sondagem controlada:**
- 25 requisições, com 2 s entre elas, só GET e sem seguir redirecionamento;
- evidência em `auditoria/sondagem_api.json`, só com metadados: nenhum nome de credor.

Contrato observado em `/empenhos/restos-a-pagar`:

| Comportamento | Observado |
|---|---|
| Formato | `Page` do Spring: `content`, `totalElements`, `totalPages`, `number`, `size`, `numberOfElements`, `first`, `last`, `empty`, `sort`, `pageable` |
| Transporte | `Content-Type: application/json`, **`Content-Encoding: gzip`**, **`Transfer-Encoding: chunked` (sem `Content-Length`)**, `ETag` fraco, `Server: nginx` |
| `size=2000` | aceito: 2000 por página |
| `size=5000` | **limitado em silêncio a 2000** (`size` ecoado 2000; `totalPages` recalculado) |
| `size=0` ou ausente | 20 (padrão do Spring) |
| `page=-1` | tratado como 0, sem erro |
| `page` além do fim (99) | 200, `content` vazio, `last=true`, `number=99` |
| Ordenação | `sort: []` (nenhuma pedida). A ordem efetiva é **(anoempenho, empenho) estritamente crescente**: em 100% dos 247 snapshots completos gravados (203 de uma página, 44 de várias) e entre páginas. **Não é contrato documentado** |
| `sort=empenho,asc` | aceito e ecoado; ordena |
| Estabilidade | duas consultas seguidas: bytes de `content` idênticos; páginas de 100 = mesmo conjunto, ordem e registros de `size=2000` |
| Chave (entidade, anoempenho, empenho) | única em todos os cortes reais (CHAVE-DUP = 0). Não é garantida pela API |
| Exercício inexistente (1900), entidade inexistente (99999) | **200 com 0 registros**: indistinguível de "sem RP" |
| Data inválida | 400 (BindException do Spring) |
| Sem `dataFinal` | **500**, com mensagem do banco do servidor |
| Parâmetro desconhecido | ignorado |
| `dataFinal` em outro ano | aceito pela API (o coletor proíbe) |
| Caminho inexistente | 404 |

**Não testado** (não é possível provocar sem abusar do portal): 429 real, 5xx real, timeout real, corpo truncado, redirecionamento real e mudança da base durante a paginação. Esses casos são cobertos por simulação (fase 15).

## 2. Achados

Formato de cada linha: **ID · severidade · natureza · categoria**.

Cada item traz:
- **onde:** arquivo e trecho;
- **problema** e por que é um problema;
- **cenário:** caso concreto de falha;
- **impacto;**
- **reprodução;**
- **correção** e o risco dela;
- **teste:** o que impede a regressão.

### 2.1 Coleta e paginação

**COL-01 · ALTA · RISCO · coleta.** `coletor.py`, `Coletor._paginado`.
- **Problema:** "completa" exige `last`, `totalElements` constante e Σ`content` = `totalElements`. A soma não prova que os registros são distintos nem que formam um estado da base. O exemplo do enunciado (A B C | C D E, total 6) passaria hoje; o mesmo vale para uma exclusão antes do deslocamento compensada por uma inclusão depois dele (1 2 3 | 5 6 7, com o 4 perdido e o 2, já excluído, presente).
- **Cenário:** a entidade 1 tem 3 páginas por corte. Um empenho lançado durante a coleta desloca a paginação.
- **Impacto:** snapshot marcado `completa` com registro repetido ou perdido. Ele vira o vigente do corte e altera indicadores publicados **sem nenhum aviso**.
- **Reprodução:** transporte simulado (fase 15, casos 4 e 5).
- **Correção:**
  - (a) exigir ordem (anoempenho, empenho) estritamente crescente entre páginas: detecta página repetida, fora de ordem ou deslocada para trás;
  - (b) proibir registro idêntico repetido entre páginas;
  - (c) segunda leitura de todas as páginas quando há mais de uma, exigindo bytes iguais. Isso detecta o deslocamento compensado, que a ordem não detecta. Os hashes da segunda leitura vão no manifesto, sem entrar na normalização;
  - qualquer falha marca `incompleta`, com a observação.
- **Risco da correção:**
  - (a) depende de uma ordem não contratual. Se a API mudar a ordem, a coleta falha visivelmente, que é o comportamento desejado diante de mudança de contrato;
  - (c) custa 1 leitura a mais por página em cortes de várias páginas;
  - nenhum snapshot existente muda.
- **Teste:** casos 2 a 8 da fase 15.

**COL-02 · MÉDIA · RISCO · coleta.** `_paginado`.
- **Problema:** os metadados da página não são validados: `number` (página pedida × devolvida), `numberOfElements`, `size` ecoado e coerência de `totalPages`.
- **Cenário:** uma API que passe a ignorar `page` só é detectada indiretamente, pela soma.
- **Impacto:** coleta incorreta aceita ou mudança de contrato não explicada.
- **Correção:** validar `number == page pedida`, `numberOfElements == len(content)`, `len(content) <= size` ecoado e `totalPages` coerente. A observação diz qual campo divergiu.
- **Risco:** baixo; a validação aplica-se a campos que a API real sempre mandou (verificado nos 247 snapshots).
- **Teste:** casos 6 a 8.

**COL-03 · MÉDIA · RISCO · coleta.** `_paginado`.
- **Problema:** sem `totalElements` inteiro, o limite pela soma não se aplica. Um servidor que ignore `page` e nunca mande `last` leva o coletor até `MAX_PAGINAS` = 10.000 requisições (cerca de 4 h com pausa de 1,5 s).
- **Correção:** `totalElements` precisa ser inteiro ≥ 0 na primeira página; senão, falha imediata.
- **Teste:** caso 8 com `totalElements` ausente.

**COL-04 · BAIXA · BUG · coleta.** `_paginado`.
- **Problema:** o teste `pagina > paginas` deveria ser `>=` (as páginas começam em 0). Por isso o coletor faz uma requisição a mais, fora do intervalo, antes de concluir.
- **Impacto:** uma requisição desnecessária; o resultado não muda.
- **Correção:** `>=`.

**COL-05 · MÉDIA · RISCO · coleta.** `Coletor.listagem`.
- **Problema:** a API responde 200 vazio para entidade ou exercício inexistentes. Um erro de digitação (`--entidade 51`) gera snapshot `completa` com 0 registros, que a camada painel apresentaria como "sem RP" se a entidade estivesse no catálogo.
- **Correção:** a coleta de listagem compara a entidade com o catálogo vigente. Se a entidade não estiver nele, a observação do snapshot registra o fato. A coleta não é recusada, porque entidade extinta pode faltar do catálogo.
- **Teste:** entidade fora do catálogo deixa a observação.

**COL-06 · BAIXA · RISCO · coleta.** `Coletor._simples`.
- **Problema:** o catálogo é aceito como "completa" se for JSON qualquer. Um objeto de erro com HTTP 200 passaria.
- **Mitigação existente:** a normalização recusa estrutura inesperada e registra o problema.
- **Correção:** validar o tipo (lista de objetos). Adiada (P2).

**COL-07 · BAIXA · RISCO · coleta.** `Coletor.rreo`.
- **Problema:** um PDF com o mesmo `idArquivo` já coletado nunca é baixado de novo. Se o portal substituir o arquivo mantendo o id, a mudança não é vista.
- **Correção futura:** recoleta periódica comparando bytes (P3).

### 2.2 Cliente HTTP

**HTTP-01 · MÉDIA · BUG · HTTP.** `http.py`, `Cliente.get`: `except Exception`.
- **Problema:** qualquer exceção do transporte vira "erro de rede": `TypeError`, `AttributeError`, `NameError` (erro de programação), `InvalidURL`, `MissingSchema`.
- **Cenário:** um bug no transporte gera 3 tentativas com espera crescente, `ErroDeRede` e snapshot `falhou` com a mensagem "rede".
- **Impacto:** defeito de código escondido como instabilidade do portal; diagnóstico errado; repetição inútil.
- **Reprodução:** transporte que lança `TypeError` → hoje sai `ErroDeRede` depois de 3 chamadas (caso 15).
- **Correção:**
  - o transporte traduz as exceções do `requests` em `FalhaTransitoria`, as únicas repetidas: timeout, conexão, protocolo e leitura interrompida;
  - erro de TLS e URL inválida viram `ErroDeRede` imediato, sem repetição;
  - qualquer outra exceção propaga.
- **Teste:** casos 9 a 15.

**HTTP-02 · BAIXA · RISCO · HTTP.**
- **Problema:** `Retry-After` em formato de data HTTP é ignorado; só segundos são aceitos.
- **Correção:** aceitar data (RFC 9110), com o mesmo teto de 300 s.

**HTTP-03 · BAIXA · RISCO · HTTP.** `transporte_requests`.
- **Problema:** a verificação de `Content-Length` nunca atua na API real, que responde em chunked + gzip. A proteção efetiva é `ler_limitado` sobre os bytes **descomprimidos**, que limita também uma bomba gzip.
- **Implicação:** os bytes guardados no armazém são o corpo **já descomprimido** pelo `requests`, e o cabeçalho guardado diz `Content-Encoding: gzip`.
- **Correção:** documentar (não é defeito).

**HTTP-04 · BAIXA · RISCO · HTTP.**
- **Problema:** `requests` honra `HTTPS_PROXY` e `NO_PROXY` do ambiente (`trust_env`). Um proxy configurado na máquina recebe as requisições (o TLS continua verificado).
- **Correção:** documentar; desligar `trust_env` só se o responsável decidir (P3).

### 2.3 Armazém, snapshots e reconstrução

**REC-01 · MÉDIA · RISCO · integridade.** `banco.verificar`.
- **Problema:** a conferência banco × armazém compara só a **presença** dos `snapshot_uid`. Não confere se a linha `coleta` e as linhas `resposta_bruta` são as do manifesto (tipo, parâmetros, status, data, ordem, URL, SHA-256 e tamanho de cada resposta).
- **Cenário:** um banco sincronizado de um manifesto depois alterado, ou um banco de outro armazém com os mesmos uids, passa no `verificar`.
- **Correção:** conferir campo a campo manifesto × banco.
- **Risco:** baixo; o banco ativo foi conferido sem divergência.
- **Teste:** coleta com status adulterado num banco de teste é detectada.

**REC-02 · MÉDIA · RISCO · integridade.** Manifestos.
- **Problema:** o manifesto não tem autenticação própria. Uma edição de `status` ou `parametros` no JSON só é detectável pelo histórico do Git.
- **Correção:** estrutural (P2): gravar o SHA-256 do manifesto em `coleta` (migração) ou num índice assinado.

**ARM-01 · BAIXA · RISCO · armazém.** `Armazem.verificar`.
- **Problema:** objetos não referenciados por nenhum manifesto e temporários abandonados (`*.tmp<pid>`, sinal de gravação interrompida) não são relatados. Hoje há 0 de cada.
- **Correção:** relatar os dois.

**DET-02 · MÉDIA · RISCO · reprodutibilidade.** `execucoes.hash_camada0`.
- **Problema:** o hash inclui ids internos, `coletor_versao.registrado_em` e `esquema_versao.aplicada_em`. No banco reconstruído deu `4c35f81b…`, contra `73367069…` no ativo. Ele só prova a integridade **do mesmo arquivo** ao longo do tempo, não a equivalência de um banco reconstruído.
- **Impacto:** não há como **provar**, com um número, que a camada bruta de dois bancos é a mesma.
- **Correção:**
  - hash estável da camada 0, calculado por identificadores do armazém (uid, ordem, URL, SHA-256);
  - comando `comparar-bancos`, que compara camada 0, normalização e derivação por identificadores estáveis;
  - o `hash_camada0` antigo é mantido, com o mesmo valor, porque está nos relatórios homologados.

### 2.4 Banco SQLite

**DB-01 · ALTA · RISCO · integridade.** Tabelas de execução e derivadas.
- **Problema:** `rp_derivado`, `visao_valor`, `anomalia` e as demais tabelas derivadas, além de `derivacao_execucao.hash_resultado`, aceitam UPDATE e DELETE. Nada recalcula o `hash_resultado` gravado: `verificar` e `portoes` só o **exibem**.
- **Cenário:** uma alteração manual, ou um bug que reescreva `visao_valor`, muda o valor publicado, e o hash gravado continua o antigo.
- **Impacto:** **falsa aparência de integridade**: o portão diz "apto" e mostra o hash homologado.
- **Correção:** portão `hash_resultado_confere`, que recalcula o hash de cada derivação vigente (atual e "como estava em") e compara com o gravado.
- **Teste:** UPDATE em `visao_valor` → portão falha.

**DB-02 · MÉDIA · RISCO · integridade.** FKs ausentes.
- **Inventário:**

  | Tabela | Coluna sem FK | Referencia |
  |---|---|---|
  | `rp_derivado` | `resposta_id`, `coleta_id` | `resposta_bruta`, `coleta` |
  | `rp_derivado` | (resposta_id, indice) | `rp_registro` da normalização da derivação (relação composta) |
  | `movimentacao_interpretada` | `resposta_id` | `resposta_bruta` |
  | `anomalia` | `coleta_id` | `coleta` |
  | `espelhamento_par` | `coleta_a_id`, `resposta_a_id`, `coleta_b_id`, `resposta_b_id` | `coleta`, `resposta_bruta` |
  | `conciliacao_rreo` | `rreo_coleta_id` | `coleta` |
  | `normalizacao_execucao` | `ultima_coleta_id` | `coleta` |
  | `evidencia_externa` | `sha256` | `objeto_bruto` |

- **Por que hoje não houve órfão:** a camada 0 não se apaga (gatilhos), então a ausência de FK não permite um órfão por exclusão. Mas uma inserção com id errado ou inexistente (bug de derivação) não é recusada.
- **Correção em duas partes:**
  - (a) **já:** portão `integridade_relacional`, com `PRAGMA foreign_key_check` e consultas de órfãos para cada relação lógica acima;
  - (b) **P2, com decisão:** migração v5 com FKs e gatilhos de inserção. Muda `esquema_versao` e, portanto, o `hash_camada0` homologado; não é aplicada sem decisão.
- **Teste:** linha órfã inserida num banco de teste → portão falha.

**DB-03 · MÉDIA · RISCO · governança.** `regras.semear` e `governanca.semear`.
- **Problema:** `INSERT OR IGNORE` faz com que editar no código a definição, o status ou um parâmetro de uma regra **já existente** não chegue ao banco, sem nenhum aviso. Código e banco divergem; a derivação lê os parâmetros do banco, enquanto a documentação mostra os do código.
- **Hoje:** 15/15 regras, 12/12 tipos, 5/5 parâmetros e 22/22 decisões iguais.
- **Correção:** depois do semear, conferir banco × código e recusar a divergência (`CatalogoDivergente`). Mudança de regra exige versão nova, como a documentação já manda.
- **Teste:** alterar a definição de S1 v1 no código num banco de teste → erro.

**DB-04 · BAIXA · RISCO · imutabilidade.**
- **Problema:** `regra` não tem gatilho contra DELETE: só a FK impede, e só se houver referência. `anomalia_tipo` aceita UPDATE e DELETE.
- **Correção:** entra na migração v5 (P2).

**DB-05 · BAIXA · DÍVIDA · modelo.**
- **Problema:** `anomalia`, `verificacao` e `espelhamento_par` não têm chave. Uma linha duplicada por bug seria contada duas vezes.
- **Correção:** P2 (v5). O portão de hash da derivação (DB-01) detecta a duplicação depois de gravada.

**DB-06 · BAIXA · MELHORIA · modelo.** Colunas JSON.
- **Devem continuar JSON:** `parametros_json` (há colunas promovidas para consulta), `detalhe_json` e `escopo_json` (descritivos, sem relação a proteger) e `regras_json` (lista de ids, redundante com `regra`).
- **`coletas_json`** (`visao_valor`) e **`coletas_api_json`** (`conciliacao_rreo`):
  - guardam **uids** de snapshot, que são identificadores estáveis;
  - porém sem integridade referencial;
  - e o segundo faz parte da chave primária.
- **Proposta P2:** tabela `visao_coleta (derivacao_id, visao_valor_id, coleta_id REFERENCES coleta)`. Hoje o portão de integridade relacional confere que todo uid em `coletas_json` existe em `coleta`.

**DB-07 · BAIXA · DÍVIDA · operação.** Crescimento.
- **Problema:** cada `processar` normaliza **todo** o bruto (+228.873 linhas, cerca de 50 MB) e deriva tudo (+158.209 linhas, cerca de 25 MB). Não há política de retenção de execuções; `apagar-execucao` existe, mas é manual.
- **Correção:** P2: política documentada ("manter as 2 últimas normalizações e as derivações de cada vigência").

**DB-08 · BAIXA · MELHORIA · desempenho.** Índices.
- **Medição:** com o banco atual, toda chamada da interface termina em ≤ 0,3 s (seção 3). Os únicos SCAN de tabela inteira são em `derivacao_execucao` (4 linhas) e `espelhamento_par` (7.592).
- **Decisão:** nenhum índice novo agora. Criar índice sem ganho medido só custa escrita.
- **Índice redundante:** nenhum; `ix_coleta_corte` e `ix_rp_registro_chave` são usados.

### 2.5 Migrações

**MIG-01 · ALTA · BUG · migração.** `banco._migrar`.
- **Problema:** `with con:` **não** abre transação para DDL no `sqlite3` do Python (modo legado: BEGIN implícito só antes de INSERT/UPDATE/DELETE). Cada `CREATE` ou `ALTER` é confirmado na hora.
- **Reprodução:** migração `[CREATE nova_a, CREATE nova_b, ALTER inexistente]` → falha no 3º comando, e `nova_a` e `nova_b` continuam criadas, sem registro em `esquema_versao`.
- **Impacto:** o banco fica em estado intermediário e a nova tentativa falha ("table already exists"). O backup anterior existe, mas o código e a documentação afirmam atomicidade.
- **Correção:** `BEGIN` explícito, com COMMIT ou ROLLBACK. O SQLite tem DDL transacional.
- **Teste:** migração com comando inválido no meio → nenhuma tabela nova e versão inalterada; a migração corrigida aplica depois.

**MIG-02 · MÉDIA · BUG · migração.** `banco.abrir`, banco novo.
- **Problema:** `executescript` também não é atômico. Uma falha no meio da criação deixa um arquivo que `abrir` passa a tratar como banco existente; `versao_esquema` devolve `None` ou dá erro.
- **Correção:** criar num arquivo temporário e só renomear para o destino com o esquema, as migrações e o catálogo completos.
- **Teste:** falha simulada no catálogo → nenhum arquivo no destino.

**MIG-03 · BAIXA · RISCO · migração.**
- **Problema:** `esquema_versao.backup_antes` grava caminho **absoluto** da máquina (ex.: `C:\Users\maped\OneDrive\...`), que não é portável.
- **Correção:** documentar; gravar caminho relativo a `cfg.backups` (P3; muda texto da camada 0 em migrações futuras).

**Perguntas obrigatórias da fase 6:**

| Pergunta | Resposta |
|---|---|
| 1. Migração parcial deixa estado intermediário? | **sim (MIG-01)** |
| 2. Backup antes? | sim, para banco existente |
| 3. Atômica? | **não** |
| 4. Repetível? | não, depois de falha parcial |
| 5. Banco mais novo que o código? | detectado (`MigracaoPendente`) |
| 6. Downgrade? | recusado, mesma verificação |
| 7. Base + migrações reproduzível? | sim (banco reconstruído com o mesmo esquema; verificado) |
| 8. Reconstrução com o mesmo esquema? | sim |
| 9. Migração altera dados? | a 3 e a 4 só acrescentam estrutura |

### 2.6 Normalização

**NORM-01 · MÉDIA · RISCO · dados.** `normalizar._linha_rp`: `centavos(r.get(c, 0))`.
- **Problema:** campo monetário **ausente** vira **0**. A ausência fica em `chaves_ausentes`, mas o zero entra em todas as somas. É interpretação na normalização ("ausência = zero"), contra o princípio do projeto.
- **Hoje:** 0 registros com campo monetário ausente; só faltam as 7 chaves orçamentárias opcionais, em 6.851 registros.
- **Correção sem mudar regra homologada:** portão `campos_monetarios_ausentes`, que reprova a carga se algum registro da normalização atual tiver campo monetário em `chaves_ausentes`. A mudança da semântica (NULL) fica como **REGRA HOMOLOGADA A REVISAR**: muda o esquema e a derivação.
- **Teste:** registro sintético sem `pagoProc` → portão falha.

**NORM-02 · MÉDIA · RISCO · dados.** `normalizar._rreo`.
- **Problema:** dois números que caem na mesma coluna da mesma linha: o segundo é descartado (`vistos.setdefault`). A mesma (linha, coluna) repetida: `INSERT OR IGNORE`. Ambos sem registro.
- **Hoje:** 1.529 valores extraídos e 1.529 gravados: nenhuma perda nos 33 PDFs lidos.
- **Correção:** valor diferente na mesma célula → `LayoutDesconhecido` (o PDF inteiro fica sem transcrição e o erro registrado). Valor igual → aceito.
- **Teste:** palavras sintéticas com conflito → erro registrado.

**NORM-03 · BAIXA · RISCO · dados.** `normalizar.normalizar`.
- **Problema:** `except Exception` na transcrição do RREO também esconde erro de programação do extrator como "layout".
- **Mitigação existente:** o erro fica em `rreo_extracao` e numa verificação com falha.
- **Correção:** P3, separar `LayoutDesconhecido` de exceção inesperada.

**NORM-04 · BAIXA · RISCO · segurança.**
- **Problema:** o PDF (até 64 MiB) é aberto pelo MuPDF no mesmo processo. A origem é o portal oficial por TLS.
- **Correção:** P3, processo isolado com limite de tempo e memória.

### 2.7 Derivação

**DER-01 · MÉDIA · BUG (latente) · regra.** `derivar._movimentacao`.
- **Problema:** lê lançamentos de coletas de qualquer status, inclusive `incompleta` e `falhou`. `_registros` usa só `completa`, e a documentação diz que snapshot incompleto "não vira retrato válido".
- **Hoje:** 0 lançamentos de coleta não completa, logo o resultado não muda.
- **Correção:** filtrar `c.status = 'completa'`.
- **Teste:** movimentação de coleta incompleta fora da derivação.

**DER-02 · MÉDIA · RISCO · regra.** `derivar._movimentacao`.
- **Problema:** tipo de lançamento desconhecido vira efeito `desconhecido` com **valor 0**, sem anomalia.
- **Hoje:** só tipos conhecidos (20, 21, 22, 30, 31, 40, 41, 50, 51).
- **Correção:** portão `lancamento_desconhecido`, sem mudar a regra MOV-REF.

**DER-03 · BAIXA · RISCO · regra.** `_continuidade` e `_pareamento`.
- **Problema:** um dicionário por (anoempenho, empenho) colapsa chave repetida (fica a última).
- **Mitigação:** CHAVE-DUP é anomalia registrada.
- **Correção:** P3.

**DER-04 · BAIXA · RISCO · determinismo.** `resultado_estavel`.
- **Problema:** `sorted` de tuplas com `None` dá `TypeError` se dois itens empatarem até a posição do `None`. Hoje não ocorre: toda anomalia tem coleta.
- **Por que não mexer:** mudar a chave de ordenação mudaria o hash homologado.
- **Correção:** documentar; P3 com nova versão do hash.

**Fórmulas** (conferidas contra `regras.REGRAS` e o código):
- S1 = proc + aproc − pagoProc − pagoAProc − canceladoAProc; S2 = aproc − liquidado − canceladoAProc; S3 = proc − pagoProc + liquidado − pagoAProc;
- RREO-COL: e = a + b − c − d; k = f + g − i − j; L = e + k;
- código e definição coincidem;
- **nenhuma fórmula homologada foi considerada suspeita.**

**Por que (a) e (b) ignoram proc ≤ 0:** os dados atuais têm 0 registros com proc ou aproc negativos, então a relação "faixas fecham com S1" vale hoje. A **REGRA HOMOLOGADA A REVISAR** é o tratamento de inscrição negativa, se aparecer: entraria em S1 e não em nenhuma faixa. Nenhuma mudança.

**Dinheiro:**
- JSON lido com `parse_float=Decimal`;
- mais de 2 casas é erro, nunca arredondamento;
- `bool`, `NaN` e `Infinity` geram exceção, sem valor inventado;
- inteiro além de 2⁶³ gera `OverflowError` no SQLite, que derruba a normalização inteira (falha alta, não silenciosa).

### 2.8 Determinismo

**DET-01 · BAIXA · BUG · determinismo.** `normalizar._rreo`.
- **Problema:** a mensagem `LayoutDesconhecido` inclui a representação de um `set`, cuja ordem varia com o `PYTHONHASHSEED`.
- **Reprodução:** o mesmo PDF gerou `{'f','i','c',…}` no banco ativo e `{'d','e','k',…}` no reconstruído.
- **Impacto:** o texto de auditoria em `rreo_extracao.erro` e `normalizacao_execucao.observacao` muda entre execuções; o `hash_resultado` não muda.
- **Correção:** `sorted`.

**CLI-01 · MÉDIA · BUG · determinismo.** `cli.py`, `processar --em`.
- **Problema:** o valor vai cru para a derivação, que compara `coletada_em <= em` **como texto**. A camada painel normaliza com `instante()`, a derivação não.
- **Cenários:**
  - `--em 2026-09-29` exclui todos os snapshots do dia 29 (`'2026-09-29T19:56…' > '2026-09-29'`);
  - `--em 2026-09-30T02:59:59Z` compara com outro fuso;
  - `--em ontem` inclui todos (`'o' > '2'`);
  - em todos os casos, `vigencia_em` é gravado num formato que a camada painel não encontra.
- **Correção:** `instante()` compartilhado (painel e CLI); a derivação recusa valor fora do formato canônico.
- **Hashes:** não mudam, porque `2026-09-29T23:59:59-03:00` já é canônico.
- **Teste:** `--em 2026-09-29` equivale a fim do dia; `--em ontem` é recusado.

**Fontes de não determinismo verificadas e ausentes:**
- SQL de derivação sem `ORDER BY`: as leituras têm ORDER BY, e o hash ordena tudo;
- `set` em serialização do hash: não há;
- relógio no resultado: `executada_em` fica fora do hash;
- ids internos: trocados por uid no hash;
- ordem de arquivos: manifestos ordenados por (data, uid);
- `float`: não há; dinheiro é inteiro;
- fuso: fixo em −03:00;
- locale: não é usado.

**Prova:** reconstruir e processar reproduziu os dois hashes.

### 2.9 Portões

**POR-01 · MÉDIA · RISCO · portões.** `portoes.avaliar`.
- **Problema:** `apto = true` com portões `ok = null` (camada bruta sem referência e testes). A saída parece uma aprovação completa.
- **Correção:**
  - acrescentar `nao_verificados` (lista) e `apto_sem_ressalvas`;
  - manter `apto` e o código de saída, que outros scripts leem.

**POR-02 · BAIXA · RISCO · portões.**
- **Problema:** os portões só olham a derivação atual; as derivações "como estava em" ficam de fora.
- **Correção:** o portão novo de hash (DB-01) cobre todas as vigências.

### 2.10 Painel e interface

**PNL-01 · BAIXA · DÍVIDA · desempenho.**
- **Problema:** padrão N+1:
  - `serie_entre_exercicios`: 2.321 comandos SQL;
  - `pares`: 1.472;
  - `qualidade`: 1.430;
  - `coerencia`: 1.282.
- **Medição:** todos ≤ 0,3 s.
- **Correção:** só se a base crescer (P3).

**PNL-02 · BAIXA · RISCO · apresentação.** `Painel.pares`.
- **Problema:** para corte não processado, devolve `pares = 0` sem indicador de disponibilidade. A interface já trata isso desde a pós-05; a saída JSON do CLI (`rp painel pares`) não.
- **Correção:** P2. Mudar a saída da camada painel exige refazer a comparação de estado homologada.

**SQL injection:** nomes de coluna dinâmicos só vêm de listas fechadas (`DIMENSOES`, `FAIXAS`, `DIMENSOES_ORCAMENTARIAS`), e os valores são sempre parâmetros. Nenhum vetor encontrado.

**XSS:** toda saída passa por `esc`. CSP `default-src 'none'`, sem JavaScript. Coberto pelos testes da 04.5/04.6.

### 2.11 Segurança (fase 13)

| Vetor | Situação |
|---|---|
| Path traversal | protegido: hash validado antes de virar caminho; manifesto lido só sob `coletas/`; nome de evidência saneado |
| Symlink | não tratado: um symlink criado dentro de `snapshots/` por quem já tem acesso de escrita seria seguido (BAIXA; o modelo de ameaça é local) |
| Bomba de descompressão | protegida: zlib com teto e corpo HTTP limitado aos bytes descomprimidos |
| JSON profundo | `RecursionError` tratada no coletor, no armazém e na normalização |
| SSRF e redirecionamento | URL base fixa e validada (https, sem credencial); segmentos de caminho em lista fechada; redirecionamento não seguido; `idArquivo` só inteiro positivo |
| PDF malformado | NORM-04 |
| Logs | só URLs públicas e mensagens; nenhuma credencial existe |
| Comandos shell | nenhum |
| Temporários | nomes com pid, em pasta própria; órfãos não relatados (ARM-01) |
| Exposição de dados | ver seção 4 (repositório público com dados de pessoa física) |
| Interface | só leitura, só GET/HEAD; aviso ao abrir fora de 127.0.0.1; sem autenticação (documentado) |

### 2.12 Testes (fase 14)

**Suíte:** extensa (353), com boa parte por recálculo independente do bruto (`recalculo_bruto.py`), o que **não** é só reprodução da implementação.

**Lacunas encontradas:**

| Lacuna | Achado ligado |
|---|---|
| migração interrompida | MIG-01 |
| criação de banco interrompida | MIG-02 |
| paginação defeituosa além de "total muda" (duplicação, página repetida, `page` ou `size` ignorados, `last` errado, metadado divergente) | COL-01/02 |
| erro de programação no transporte | HTTP-01 |
| corrupção relacional e derivada (FK, órfão, UPDATE em tabela derivada) | DB-01/02 |
| divergência de catálogo | DB-03 |
| determinismo entre processos com hash aleatório diferente | DET-01 |
| `--em` em formatos diferentes | CLI-01 |
| equivalência de bancos reconstruídos por camada | DET-02 |
| conferência manifesto × banco campo a campo | REC-01 |
| restauração de backup | coberta só por `test_backup_e_copia_integra` (cópia íntegra), não por restauração seguida de recálculo |

## 3. Desempenho (fase 16; medido)

**Ferramenta:** `auditoria/benchmark_painel.py`, somente leitura. Mediana de 3 execuções no banco ativo; evidência em `auditoria/benchmark_painel_antes.json`.

| Operação | Tempo |
|---|---|
| `reconstruir` (466 snapshots) | 4,1 s |
| `processar` (normalização + derivação atual) | 10,8 s |
| `processar --em` (só derivação) | 2,0 s |
| `integrity_check` | 3,7 s |
| `foreign_key_check` | 0,2 s |
| suíte de produção | 174 s |
| interface (19 chamadas típicas) | todas ≤ 0,30 s; maiores: série 0,30 s, qualidade 0,24 s, coerência 0,19 s |

## 4. Repositório (fase 12)

**Situação:**
- pack do Git: 37,6 MB;
- `snapshots/`: 15 MB comprimidos, endereçados por conteúdo e deduplicados;
- `etapa02/dados_brutos`: ~89 MB, incluindo PDFs e normas;
- `backups/`: 4 SQLite versionados (10,8 MB); o de 120 MB fica fora pelo `.gitignore`, citado **pelo nome**;
- repositório **público**, com 44.503 registros de pessoa física com nome no bruto.

| Alternativa | Prós | Contras |
|---|---|---|
| A — bruto no Git (hoje) | clone autossuficiente; o histórico do Git é uma prova extra de imutabilidade | crescimento permanente (cerca de 3–5 MB comprimidos por carga completa); remoção exige reescrever o histórico (invalida tags e SHAs); dados pessoais públicos; **backups SQLite no Git são redundantes** com o armazém (o banco é reconstruível) |
| B — bruto fora do Git, manifestos e hashes no Git | repositório pequeno; prova de integridade mantida | reprodução depende de um segundo armazenamento; a primeira obtenção do bruto vira passo manual |
| C — bruto em releases, LFS ou armazenamento de objetos, com manifestos no Git | clone leve; bruto versionado e baixável | LFS tem cota e custo; outro serviço a manter; mesmo problema de privacidade se for público |
| D — híbrido | — | — |

**Recomendação (não executada):** D.
- **Já:** parar de versionar backups SQLite (`backups/*.sqlite` no `.gitignore`, sem apagar nada).
- **Bruto:** manter os snapshots no Git enquanto o volume for pequeno (decisão de privacidade pendente).
- **Se o repositório continuar público:** mover o bruto para armazenamento privado (B ou C), mantendo manifestos e hashes no Git. O `config.toml` já aceita `snapshots` em outra pasta.
- **Histórico:** nenhuma remoção, porque reescrever invalidaria `etapa-04-final` e `etapa-05-final`.

## 5. Portabilidade (fase 18)

**Testado:**

| Caso | Situação |
|---|---|
| caminho com espaço e acento (`Área de Trabalho`, OneDrive) | uso diário |
| caminho curto (`C:\rpaud`): reconstrução e processamento | nesta auditoria |
| banco fora do projeto (`RP_DADOS_LOCAIS`) | nesta auditoria |
| ambiente virtual limpo, Python 3.14.3 | 05.7 |
| caminho profundo (> 260 caracteres) | falha documentada na 05.7 |
| sem rede | 05.7, 25 visitas, 0 tentativas de conexão |

**Não testado:**

| Caso | Situação |
|---|---|
| outra versão do Python | não testado |
| outra máquina ou outro Windows | não testado |
| Linux e macOS | não testado |
| armazém `snapshots` fora do projeto, via `RP_CONFIG` | coberto por teste unitário de configuração, não ponta a ponta |

## 6. Dependências (fase 19)

**Declaradas:** `requests==2.34.2`, `pymupdf==1.28.2` (AGPL-3.0) e `pytest==9.1.1`.

**Transitivas sem versão:**
- o ambiente ativo usa urllib3 2.7.0, idna 3.19 e charset-normalizer 3.5.1;
- a instalação limpa da 05.7 obteve 2.8.0, 3.20 e 3.5.2;
- os dois ambientes passaram nos testes, mas a reprodução exata não é garantida.

**DEP-01 · MÉDIA · DÍVIDA:**
- **Correção:** arquivo de trava com as versões exatas do ambiente homologado (sem atualizar nada).
- **Hashes de pacote:** exigem baixar os pacotes, o que fica para quando o responsável autorizar.

**Python:** o README diz "3.11+" (exigência de `tomllib`), mas só 3.14.3 foi testado.

## 7. Arquitetura futura (fase 20)

A estratégia é incremental, sem reescrita. A classificação está no plano (`PLANO_CORRECOES_AUDITORIA.md`):
- **P0:** falsa integridade e estado intermediário (DB-01, MIG-01, COL-01);
- **P1:** antes da próxima carga (COL-02/03/04, HTTP-01, CLI-01, MIG-02, REC-01, DB-02a, DB-03, NORM-01/02, DER-01/02, POR-01, DET-01/02, ARM-01, DEP-01);
- **P2:** migração v5 de integridade (FK, chaves, imutabilidade de `regra` e `anomalia_tipo`, SHA do manifesto), retenção de execuções, separação de `consulta.py`/`paginas.py`, CI, saída de `pares` com disponibilidade, `coletas_json` relacional;
- **P3:** HTTP-04, NORM-03/04, COL-07, DER-03/04, MIG-03, PNL-01.
