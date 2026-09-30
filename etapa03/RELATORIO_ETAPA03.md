# Restos a Pagar de Ponta Grossa — Relatório da Etapa 03 (Arquitetura e modelagem de dados)

Etapa feita em 29/09/2026, segundo `etapa03/PROMPT_ETAPA03.md`: a versão aprovada, com as regras 5 e 6.

**Onde está cada entregável:**

| Entregável | Local |
|---|---|
| Esquema proposto (DDL) | `modelo/schema.sql` |
| Validação do modelo (**não é produção**) | `validacao/`: código, 26 testes e `LEIAME.md` |
| Resultados da carga de validação | `resultados/` (01 construção, 02 números do modelo, 03 testes) |

**Nenhuma requisição nova foi feita ao portal nesta etapa.** O banco de validação foi montado só com os dados brutos já baixados nas Etapas 01 e 02, e é descartável (recriado do zero em menos de 10 s).

---

## 1. RESUMO

1. **Arquitetura em três camadas**, com dependência só para baixo:
   - **0. BRUTO** (imutável): bytes exatos de cada resposta, hash, metadados, versão do coletor.
   - **1. NORMALIZADO** (reprocessável): tipagem fiel, sem interpretação e sem descartar registro.
   - **2. DERIVADO** (reprocessável): toda interpretação, sempre com a versão da regra que a produziu.
2. **Um snapshot é uma coleta:** (entidade, exercício, `dataInicial`, `dataFinal`, `tipoPesquisa`) + data/hora da coleta. O mesmo corte coletado de novo é outro snapshot, nunca uma sobrescrita. A pergunta "o que o portal dizia em D?" é uma consulta.
3. **A carga de validação reproduziu a Etapa 02 inteira pelo modelo:**
   - 82.988 registros, sem perder nenhum;
   - conciliação com o RREO idêntica ao relatório da Etapa 02;
   - continuidade 2025→2026 sem falhas (5.878 empenhos);
   - identidades de estoque em 3.403/3.403;
   - casos 11963/2016 e 5659/2025 com os valores esperados;
   - reprocessamento com hash idêntico.
   - **26/26 testes passaram.**
4. **Achados desta etapa** (seções 7 e 8), guardados como regras **versionadas e experimentais**, lado a lado com as anteriores. Nada foi promovido a verdade.
   - **Espelhamento.** Em 2025, nos 9 pares com inscrição divergente, **a inscrição da cópia é igual ao saldo final do original** (9 de 9, ao centavo). Isso gerou a regra **CONS-PAR v2**.
   - **Pagamento no RREO.** O RREO classifica o pagamento pela **categoria do registro**, e não pelo campo em que ele está. Isso gerou a regra **RREO-COL v2**. Ela explica exatamente duas diferenças que a Etapa 02 deixou em aberto: (c) −462,00 em 2025 e (i) −2.554,25 no consolidado de 2025.
   - **Com as duas versões 2, o RREO consolidado de 2025 é reconstruído ao centavo** em (b), (c), (e), (g), (h), (i), (k) e **L = 20.341.471,66**.
   - Resta só uma reclassificação de soma zero de 1.829,50 entre processado e não processado.
5. **Tecnologia proposta:** SQLite (seção 4.3). **A decisão é do usuário.**

**Cobertura dos 14 itens pedidos:**

| Item | Seção |
|---|---|
| 1 snapshots | 5.1 |
| 2 empenhos | 4.2 |
| 3 chave composta | 4.2 |
| 4 movimentações | 4.2, 5.4 |
| 5 entidades | 4.2, 7.3 |
| 6 exercícios | 4.2, 5.2 |
| 7 fórmulas | 6 |
| 8 anomalias | 7.1 |
| 9 espelhamentos | 7.2 |
| 10 RREO | 8 |
| 11 hashes e versionamento | 5.3, 6.2 |
| 12 imutabilidade | 5.3 |
| 13 esquema | 4 |
| 14 testes | 9 |

---

## 2. DECISÕES INCORPORADAS

| Decisão (PROMPT_ETAPA03) | Como o modelo implementa | Onde se prova |
|---|---|---|
| 1. Três visões do Município | `visao_valor.visao` ∈ {`publicado`, `analitico`, `entidade`}. Toda linha aponta a regra de agregação; a analítica aponta também a regra de consolidação | `test_visoes_publicado_e_analiticas` |
| 1. Consolidação por componente | A regra tira do total só a **inscrição** de um lado do par, por componente (a/b/f/g, S1–S3). Fluxos (c, d, h, i, j) dos dois lados permanecem | mesmo teste: fluxos idênticos entre publicado e analíticas |
| 2. Snapshots, sem sobrescrever | Toda coleta é linha nova em `coleta`; `coletas_vigentes(em=D)` escolhe o snapshot vigente em D; `diferencas()` compara dois snapshots | `test_mesmo_corte_em_datas_diferentes`, `test_SINTETICO_alteracao_retroativa...` |
| 3. e-SIC em paralelo | Tabela `evidencia_externa` (imutável). A resposta entra como evidência e pode motivar **nova versão** de regra, sem mudar a estrutura | estrutura criada; sem dado ainda |
| 4. Bruto nunca substituído | Camada 0 com gatilhos que abortam UPDATE/DELETE. Camadas 1 e 2 têm execução versionada; reprocessar cria execução nova | `test_camada_bruta_imutavel`, `test_reprocessamento_deterministico` |
| 5. Nenhum lado do par é descartável | `espelhamento_par` liga os dois registros de origem, com entidade A/B, exercício, inscrição de cada lado, execução de cada lado, lado com execução e **relação entre as inscrições**. Consolidação só em `visao_valor`, com regra `experimental` | `test_espelhamento_*`, `test_regras_de_consolidacao_sao_experimentais` |
| 6. Nenhum registro bruto excluído por duplicidade | A chave das camadas 1 e 2 é a **posição de origem** (resposta, índice), nunca a chave de negócio. Duplicata vira anomalia `CHAVE-DUP` | `test_paginacao_completa_e_nenhum_registro_perdido`, `test_nenhum_registro_espelhado_foi_removido` |

---

## 3. MODELO CONCEITUAL

```text
                        ┌──────────────────────── CAMADA 0 — BRUTO (imutável) ─────────────────────────┐
  coletor_versao ──1:N──► coleta (= snapshot) ──1:N──► resposta_bruta (bytes + sha256)      evidencia_externa
  (nome, versão,          tipo · endpoint · parâmetros · corte                                (e-SIC, normas)
   hash do código)        coletada_em · origem do carimbo · status
                        └───────────────────────────────┬──────────────────────────────────────────────┘
                                                        │ normalizacao_execucao (versão do normalizador)
                        ┌──────────────────── CAMADA 1 — NORMALIZADO (reprocessável) ──────────────────┐
                          rp_registro            1 linha por item de content[]; chave = (resposta, índice)
                          movimentacao_lancamento rótulos exatamente como a API envia (_rotulo)
                          rreo_valor             transcrição do PDF por linha/coluna (versão do extrator)
                          entidade_ref · exercicio_ref   catálogos, por snapshot
                        └───────────────────────────────┬──────────────────────────────────────────────┘
                                                        │ derivacao_execucao (versão + regras usadas + hash)
                        ┌──────────────────── CAMADA 2 — DERIVADO (reprocessável) ─────────────────────┐
  regra (código, versão,  rp_derivado            categoria, faixa RREO, S1, S2, S3, cancelamento por categoria
   uso, status, fonte) ◄─ movimentacao_interpretada  referência de liquidação (rótulos trocados resolvidos)
  anomalia_tipo       ◄─ anomalia               catálogo + ocorrências (nunca corrigem nada)
                          espelhamento_par       par A↔B, inscrição e execução de cada lado, relação
                          visao_valor            publicado · analítico · entidade × regra de agregação × consolidação
                          conciliacao_rreo       diferença API − RREO por coluna e regra (registro, não correção)
                          verificacao            resultado de cada verificação de integridade
                        └──────────────────────────────────────────────────────────────────────────────┘
```

**Dependências:**
- A camada 2 só lê a 1, e a 1 só lê a 0.
- Nada escreve para baixo.
- Mudança de regra = nova linha em `regra` + nova `derivacao_execucao`. As anteriores ficam para comparação.

---

## 4. ESQUEMA DO BANCO

O DDL completo está em `modelo/schema.sql`: 20 tabelas, 1 visão, 9 gatilhos e 4 índices.

### 4.1 Tabelas

| Camada | Tabela | Chave | Para quê |
|---|---|---|---|
| 0 | `coletor_versao` | id; único (nome, versão) | quem coletou, com hash do código |
| 0 | `coleta` | id | o snapshot: tipo, endpoint, parâmetros canônicos (JSON) e promovidos a coluna, `coletada_em`, `origem_carimbo`, `status` |
| 0 | `resposta_bruta` | id; único (coleta, ordem) | bytes exatos, URL, status HTTP, cabeçalhos, `sha256`, tamanho |
| 0 | `evidencia_externa` | id | e-SIC, normas, notas (arquivo + hash) |
| 1 | `normalizacao_execucao` | id | versão do normalizador |
| 1 | `rp_registro` | (normalização, resposta, índice) | 37 colunas; dinheiro em centavos; `chaves_ausentes`/`chaves_extras` |
| 1 | `movimentacao_lancamento` | (normalização, resposta, índice) | lançamento com os 4 campos de liquidação/pagamento **como rotulados pela API** |
| 1 | `rreo_valor` | (normalização, coleta, linha, coluna) | transcrição do Anexo VII, com versão do extrator |
| 1 | `entidade_ref`, `exercicio_ref` | por coleta | catálogos por snapshot |
| 2 | `regra` | id; único (código, versão) | catálogo; **não se edita** (gatilho) |
| 2 | `derivacao_execucao` | id | versão do derivador, regras usadas, `hash_resultado` |
| 2 | `rp_derivado` | (derivação, resposta, índice) | 1:1 com `rp_registro` |
| 2 | `movimentacao_interpretada` | (derivação, resposta, índice) | liquidação de referência + efeito com sinal |
| 2 | `anomalia_tipo`, `anomalia` | — | catálogo e ocorrências |
| 2 | `espelhamento_par` | — | par A↔B com as posições de origem dos dois registros e a relação entre as inscrições |
| 2 | `visao_valor` | id; único (derivação, visão, regra de agregação, regra de consolidação, entidade, exercício, corte, componente) | valores agregados por visão e por versão de regra |
| 2 | `conciliacao_rreo` | (derivação, RREO, regra de agregação, snapshots da API, coluna) | diferença por coluna |
| 2 | `verificacao` | — | verificados × falhas de cada checagem |

### 4.2 Itens de modelagem pedidos

- **Empenho**
  - Não existe tabela "empenho" com estado atual.
  - O empenho é a **chave composta** (`entidade`, `anoempenho`, `empenho`), que aparece em cada snapshot. O estado dele numa data é o do snapshot vigente naquela data.
  - Motivo: a base muda retroativamente (Etapa 02 §1.1.9), e um "cadastro atual" seria sobrescrito.
- **Chave composta:** (`entidade`, `anoempenho`, `empenho`). O número se repete entre entidades (Etapa 02 §2.1), então `empenho` sozinho não identifica nada.
- **Movimentações**
  - São snapshots do tipo `movimentacao`, um por empenho e por data.
  - A normalização guarda os rótulos crus. A regra `MOV-REF` v1 (camada 2) resolve os rótulos trocados nos lançamentos 40/41.
  - Coleta **sob demanda** (seção 5.4).
- **Entidades**
  - Catálogo por snapshot (`entidade_ref`), não fixo: o conjunto pode mudar.
  - "Tem RP" não é atributo: é consequência de haver registros no snapshot.
  - As visões do Município só são calculadas quando **todas** as entidades do catálogo têm snapshot no **mesmo corte**. Sem isso, o total seria parcial sem aviso.
- **Exercícios**
  - Catálogo por snapshot (`exercicio_ref`: aberto/fechado).
  - O corte de uma listagem guarda `exercicio`, `data_inicial` e `data_final`.
  - Regra de uso (Etapa 02 §8): visões e conciliação só consomem snapshots **sem tipo** e com `data_inicial` = 01/01 do exercício. Combinações `exercicio` × datas de anos diferentes não são geradas pelo coletor.

### 4.3 Tecnologia proposta — decisão do usuário

| Opção | A favor | Contra |
|---|---|---|
| **SQLite** (proposta) | Arquivo único, sem servidor, na biblioteca padrão do Python. Gatilhos garantem a imutabilidade. Aguenta GBs com folga. Backup = copiar o arquivo. É o que a validação usou (98 MB, < 10 s) | Um escritor por vez (suficiente para coleta agendada). A imutabilidade vale para quem usa o banco, não para quem apaga o arquivo; mitigação: hashes + cópia de segurança. Analítica pesada é mais lenta que em banco colunar |
| PostgreSQL | Permissões reais (`REVOKE UPDATE, DELETE` na camada 0), concorrência, pronto para web/multiusuário | Servidor para instalar, manter e fazer backup; exagero no volume atual |
| DuckDB (+ Parquet) | Muito rápido para agregações e dashboards | Sem gatilhos; imutabilidade teria de ser por convenção. Melhor como camada de leitura/analítica no futuro, lendo do banco principal |

- **Recomendação:** SQLite agora, com SQL portável (tipos simples, sem recursos exóticos) para migrar a PostgreSQL se o projeto virar serviço multiusuário.
- **Atenção prática:** a pasta do projeto está no **OneDrive**. Banco SQLite sendo escrito dentro de pasta sincronizada pode se corromper em conflito de sincronização. O banco de produção deve ficar numa pasta local **não sincronizada**, com cópia periódica para a nuvem.

---

## 5. SNAPSHOTS, HASHES E IMUTABILIDADE

### 5.1 Snapshot

- **Identidade:** `tipo` + parâmetros + `coletada_em`. Para listagens: `entidade`, `exercicio`, `data_inicial`, `data_final`, `tipo_pesquisa`.
- **`origem_carimbo`** diz quão confiável é o horário: `relogio_coletor`, `manifesto`, `cabecalho_http` ou `mtime_arquivo` (**aproximado**). Os dados importados da Etapa 02 usam as três últimas.
- **`status`:**
  - `completa` só quando a última página diz `last=true` e Σ `numberOfElements` = `totalElements`;
  - snapshot incompleto é guardado, mas nunca é "vigente".
- **Escrita atômica:** `registrar_coleta` grava a coleta e todas as respostas numa transação. Não existe "completar depois", porque a camada é imutável.
- **"Como estava em D":** o snapshot vigente de um corte em D é o mais recente com `coletada_em ≤ D`. Validado com os dados reais (recoleta 13 min depois; bytes idênticos) e com um caso sintético de alteração retroativa (seção 9).

### 5.2 Política de coleta (decisão já tomada, com o que o modelo exige)

| Exercício | Frequência | Corte | Observação |
|---|---|---|---|
| Corrente | mensal (ou bimestral) | `dataInicial` = 01/01, `dataFinal` = fim do mês | fluxos acumulados; o fluxo de um intervalo é a diferença entre dois snapshots (aditividade confirmada na Etapa 02) |
| Fechados | trimestral | 01/01–31/12 | captura as alterações retroativas; bytes iguais = nada mudou |
| **Todas as entidades no mesmo corte** | — | — | exigência do modelo para as visões do Município e para conciliar o RREO consolidado |
| RREO | a cada publicação | — | via listagem `/api/publicacoes/1`; cada PDF é um snapshot `rreo_pdf` |

### 5.3 Hashes, versionamento e imutabilidade

- **Hashes:**
  - `sha256` de cada resposta (bytes exatos);
  - `sha256_codigo` do coletor;
  - `hash_resultado` de cada derivação;
  - `sha256` de cada evidência externa.
- **Versões:** coletor, normalizador (`normalizador-1`), extrator do RREO (`rreo-coordenadas-1`), derivador (`derivador-1`), cada regra (código + versão).
- **Imutável e nunca apagado:**
  - `coletor_versao`, `coleta`, `resposta_bruta`, `evidencia_externa` (gatilhos abortam UPDATE/DELETE);
  - `regra` não se edita (gatilho).
- **Reprocessável:** normalizações e derivações. Pode-se apagar uma **execução inteira** e refazê-la; nunca se edita uma linha dentro dela.
- **Armazenamento (recomendação para a Etapa 04, medida nesta etapa):**
  - A mesma consulta repetida sem mudança na base devolveu **bytes idênticos** (3/3 páginas, mesmo SHA-256).
  - JSON comprime a **9%** com zlib (60,8 MB → 5,3 MB).
  - Proposta: guardar o corpo comprimido, com o hash do conteúdo **descomprimido**, e reaproveitar bytes idênticos entre snapshots (armazenamento por conteúdo). O snapshot continua existindo e apontando para os bytes. Isso não é deduplicação de registros; não viola a regra 6.

### 5.4 Movimentações: coleta sob demanda

- Uma requisição por empenho: cerca de 4.500 por exercício só na entidade 1.
- Uso: auditoria de um valor, amostras de validação e pares espelhados com execução. Não é coleta em massa.
- O modelo aceita qualquer quantidade, porque cada movimentação é um snapshot.

---

## 6. FÓRMULAS E VERSIONAMENTO DE REGRAS

### 6.1 Catálogo (`validacao/rpval/regras.py`, gravado na tabela `regra`)

| Código | Versão | Uso | Status | Definição resumida |
|---|---|---|---|---|
| CAT | 1 | estável | CONFIRMADO | categoria por `proc`/`aproc` > 0 (válida com 01/01) |
| FAIXA | 1 | estável | CONFIRMADO | (a)/(b), (f)/(g) por `anoempenho` vs exercício − 1 |
| S1, S2, S3 | 1 | estável | CONFIRMADO | saldo total, a liquidar, liquidado a pagar |
| CANC | 1 | estável | FORTE EVIDÊNCIA | cancelamento processado (só-P) × não processado (`aproc` > 0) |
| RREO-COL | 1 | estável | FORTE EVIDÊNCIA | colunas a–L; pagamento pelo **campo** (Etapa 02 §3.2) |
| **RREO-COL** | **2** | **experimental** | **FORTE EVIDÊNCIA** | pagamento pela **categoria do registro**: `pagoAProc` de só-P entra em (c); `pagoProc` de só-N entra em (i). Consequência algébrica: L = ΣS1 |
| MOV-REF | 1 | estável | FORTE EVIDÊNCIA | rótulos trocados nos lançamentos 40/41 |
| PAR-24 | 1 | estável | FORTE EVIDÊNCIA | par: entidade 1 (≥ 2.400.000) ↔ entidade 15 (número − 2.400.000), mesmo CNPJ e data |
| **CONS-PAR** | **1** | **experimental** | **HIPÓTESE** | inscrições iguais → inscrição de B sai; fluxos dos dois lados ficam |
| **CONS-PAR** | **2** | **experimental** | **HIPÓTESE** | inscrição de A = inscrição ou saldo final de B → inscrição de A sai; fluxos ficam |
| CONC-RREO | 1 | estável | CONFIRMADO | diferença por coluna, nunca correção |
| ANOM-REG, ANOM-CONT | 1 | estável | CONFIRMADO | anomalias por registro e de continuidade |

**Nada fora de F1–F3 e S1–S4 foi calculado.**
- CAT, FAIXA, CANC e RREO-COL são a forma das fórmulas F1–F3/S4 da Etapa 02.
- RREO-COL v2 só muda **a coluna** em que um pagamento é somado, não o valor. Não há indicador, taxa nem ranking.

### 6.2 Versionamento

- Toda linha da camada 2 pertence a uma `derivacao_execucao`, que registra as regras usadas.
- Toda linha de `visao_valor` e de `conciliacao_rreo` aponta a **regra de agregação**; a visão analítica aponta também a **regra de consolidação**.
- Versões diferentes convivem na mesma derivação. Hoje há 2 × 2 combinações: RREO-COL v1/v2 × CONS-PAR v1/v2.
- **Determinismo:** a mesma normalização + as mesmas regras dão o mesmo `hash_resultado`. Testado: duas derivações, hashes idênticos.
- **Qual versão é o "padrão" de apresentação é decisão do usuário** (seção 11). Hoje nenhuma experimental é padrão.

---

## 7. ANOMALIAS E ESPELHAMENTOS

### 7.1 Anomalias (catálogo `anomalia_tipo`; nenhuma corrige dado)

| Código | Regra de detecção | Na carga de validação |
|---|---|---|
| LIQ-NEG | `liquidado` < 0 | 100 ocorrências em 18 snapshots (5 no corte 2026 01/01–31/12) |
| PAGOPROC-SEM-PROC | `pagoProc` ≠ 0 e `proc` = 0 | 14 em 7 snapshots (no corte 2026: só 2410946/2025) |
| CANCPROC-NZ | `canceladoProc` ≠ 0 | 0 (vigia se o campo passar a ser usado) |
| COPIA-24 | entidade 1 e empenho ≥ 2.400.000 | 10.714 em 23 snapshots (731 no corte 2026) |
| ANOEMP-FUTURO | `anoempenho` ≥ exercício | 0 |
| SEM-SALDO-ABERTURA | `proc` = `aproc` = 0 no universo | 0 |
| CHAVE-DUP | chave de negócio repetida no mesmo snapshot | 0 |
| COPIA-SEM-PAR | cópia sem par na entidade 15 no mesmo corte | 0 |
| PAR-INSCRICAO-DIVERGENTE | par com `proc`/`aproc` diferentes | 9 (2025) |
| PAR-EXECUCAO-DOIS-LADOS | par com fluxo nos dois lados | 0 |
| DESCONTINUIDADE / SALDO-SEM-CONTINUIDADE | abertura de A+1 ≠ fechamento de A | 0 em 5.878 empenhos |

### 7.2 Espelhamentos

Pareamento `PAR-24` v1:

| Corte | Pares | Relação entre inscrições | Lado com execução |
|---|--:|---|---|
| 2025 (01/01–31/12) | 9 | **inscrição A = saldo final de B** | B (original) |
| 2025 (01/01–31/12) | 11 | igual | nenhum |
| 2026 (01/01–30/04) | 356 | igual | A (cópia) |
| 2026 (01/01–30/04) | 375 | igual | nenhum |

Nenhum par tem execução nos dois lados. Nenhuma cópia ficou sem par.

**Achado.** Nos 9 pares divergentes de 2025, inscrição A = inscrição B − (pago + cancelado de B em 2025), em **9 de 9**. Exemplo: 2401751 ↔ 1751: 10.390,00 − 1.980,00 = 8.410,00.
- A cópia de 2025 é o **saldo remanescente** do original depois da execução de 2025.
- Somar as inscrições dos dois lados conta o remanescente duas vezes.

**Visões do Município** (agregação RREO-COL v2; valores em R$):

| Corte | Componente | Publicado | Analítico CONS-PAR v1 | Analítico CONS-PAR v2 | RREO consolidado publicado |
|---|---|--:|--:|--:|--:|
| 2025 | (g) | 206.100.195,15 | 205.667.777,25 | **205.182.902,53** | **205.182.902,53** |
| 2025 | (a)+(f) | 18.974.988,99 | 18.974.988,99 | **18.966.578,99** | **18.966.578,99** |
| 2025 | (k) | 19.867.032,52 | 19.434.614,62 | **18.941.329,90** | **18.941.329,90** |
| 2025 | L | 21.267.174,28 | 20.834.756,38 | **20.341.471,66** | **20.341.471,66** |
| 2026, até 30/04 | (b) | 38.824.329,69 | 27.478.501,54 | 27.478.501,54 | 38.824.329,69 |
| 2026, até 30/04 | (g) | 145.250.370,54 | 125.707.995,84 | 125.707.995,84 | 145.250.370,54 |
| 2026, até 30/04 | L | 104.135.295,67 | 72.321.390,20 | 72.321.390,20 | 104.135.295,67 |

- Os fluxos (c, d, h, i, j) são idênticos nas três visões, como a regra de consolidação exige.
- **2026:** a visão publicada coincide com o RREO consolidado. As analíticas ficam **31,8 milhões** abaixo: é a inscrição dos 731 pares contada uma vez só.
- **2025:** a analítica CONS-PAR v2 reproduz **(g), (a)+(f), (k) e L** do RREO consolidado emitido em 30/01/2026, ao centavo. É indício forte de que as 20 cópias foram criadas **depois** da emissão e de que a leitura "cópia = remanescente" é coerente.
- **Status:** CONS-PAR v1 e v2 continuam **HIPÓTESE / experimental**. O banco guarda as duas, e nenhuma foi promovida (critérios na seção 10).

### 7.3 Entidades e o espelhamento

O pareamento é específico entre a entidade 1 e a entidade 15, com o número + 2.400.000, e é uma regra versionada. Se aparecer outro padrão, com outra entidade ou outro deslocamento, vira uma nova versão de `PAR-*`. O esquema não muda.

---

## 8. RREO E CONCILIAÇÃO

- **Como é guardado:**
  - o PDF é um snapshot `rreo_pdf`, com `id_arquivo`, rótulo da publicação, nome do arquivo e data HTTP;
  - os números vão para `rreo_valor`, com a versão do extrator (transcrição por coordenadas);
  - período (`data_final`) e emissão são lidos do próprio PDF; o escopo vem do rótulo da publicação ("… - Consolidado").
- **Conciliação** (para cada versão da regra de agregação):
  - escopo "entidade" → visão da entidade 1 no mesmo corte;
  - escopo "consolidado" → visão publicada (todas as entidades no mesmo corte).
  - Diferença por coluna em `conciliacao_rreo`, sem nenhuma correção.
  - Se não há snapshot correspondente, isso é **registrado** em `verificacao`; não se compara com outro corte.

**Achado: RREO-COL v2.** Três diferenças da Etapa 02 têm a mesma causa: um pagamento gravado no campo do "outro" tipo, e o RREO o classifica pela **categoria do registro**.

| Caso | Registro(s) | Campo na API | Onde o RREO põe | Diferença v1 → v2 |
|---|---|---|---|---|
| 2025, (c), Prefeitura | 15863/2023 (só processado) | `pagoAProc` 462,00 | (c) pagos processados | −462,00 → **0** |
| 2025, (i), consolidado | 8 registros da entidade 15 (só não processado) | `pagoProc` 2.554,25 | (i) pagos não processados | −2.554,25 → **0** |
| 2026, (i), 4º bim | 2410946/2025 (só não processado) | `pagoProc` 49,50 | (i) | −237.728,25 → −237.678,75 |

Consequência algébrica: com v2, L = Σ S1 em qualquer visão. Isso foi testado em todas.

**Resultado da carga** (`resultados/02`), diferença API − RREO:

| Referência | RREO-COL v1 | RREO-COL v2 |
|---|---|---|
| 2025, entidade e consolidado | a +1.829,50; c −462,00; d +1.829,50; f +6.580,50; g +917.292,62; j −1.829,50; (consolidado: i −2.554,25) | a +1.829,50; d +1.829,50; f +6.580,50; g +917.292,62; j −1.829,50 |
| 2026, 2º bim (entidade e consolidado) | só h +644,16 | só h +644,16 |
| 2026, 3º bim, entidade | h −216.913,24; i −109.112,43 | idem |
| 2026, 4º bim, entidade | h −345.479,56; i −237.728,25 | h −345.479,56; i −237.678,75 |

- Em 2025, o que sobra em v2 são as 20 cópias, que CONS-PAR v2 resolve (seção 7.2), mais **1.829,50 reclassificado** entre (a)/(f) e (d)/(j). Esse valor tem soma zero; (a)+(f) e (d)+(j) fecham.
- Os consolidados do 3º e 4º bim/2026 ficaram sem conciliação por falta de coleta de todas as entidades nesses cortes. É uma lacuna **de dados**, não do modelo.
- **Limite do extrator:** depende do layout Elotech de uma página. Se o layout mudar, a transcrição falha de forma explícita (assert de colunas), e a correção é uma nova versão do extrator.

---

## 9. TESTES DE INTEGRIDADE

`python -m pytest tests` → **26 passed** (log em `resultados/03_testes_integridade.txt`). O banco da carga registra ainda **34 verificações** em `verificacao`.

| Grupo | Teste | O que prova |
|---|---|---|
| Bruto | `test_camada_bruta_imutavel` | UPDATE/DELETE na camada 0 abortam |
| | `test_hash_de_cada_resposta_confere` | 224/224 corpos batem com o SHA-256 |
| | `test_regra_nao_se_edita` | regra só muda por versão nova |
| Normalização | `test_paginacao_completa_e_nenhum_registro_perdido` | por snapshot, Σ `content` = `totalElements` = linhas normalizadas (regra 6) |
| | `test_chaves_base_sempre_presentes` | só as 7 chaves de programática podem faltar; 0 chaves desconhecidas |
| | `test_centavos_recusa_mais_de_duas_casas` | dinheiro nunca é arredondado em silêncio |
| | `test_movimentacao_guarda_rotulos_como_vieram` | a normalização não interpreta |
| Derivação | `test_mov_ref_resolve_rotulos_trocados` | 5659/2025: todos os pagamentos → liquidação 1/2025 |
| | `test_caso_11963_2016` | processado, cancelamento de processado 3.864,52, saldo 0 |
| | `test_caso_5659_2025` | S1 = 863.785,34; `proc` = 3.001.373,39 com início em 01/02 |
| | `test_empenhos_nas_duas_abas_...` | abas = subconjuntos do snapshot sem tipo, valores idênticos; 197 "ambos" |
| | `test_identidade_de_estoque_entre_periodos` | 3.403/3.403 + os que saíram tinham saldo 0 |
| | `test_continuidade_entre_exercicios_sem_falhas` | 5.878 empenhos, 0 falhas |
| | `test_anomalias_do_corte_2026` | 5 LIQ-NEG, 731 COPIA-24, 1 PAGOPROC-SEM-PROC (2410946/2025) |
| Espelhamento | `test_espelhamento_2026_execucao_so_na_copia` | 731 pares, inscrição igual, execução só em A |
| | `test_espelhamento_2025_...saldo_remanescente` | 9 "A = saldo final de B" com execução em B + 11 iguais |
| | `test_nenhum_registro_espelhado_foi_removido` | os dois lados de cada par seguem no derivado |
| | `test_visoes_publicado_e_analiticas` | publicado = RREO; fluxos iguais nas 3 visões; v1 = v2 em 2026; v2 < v1 em 2025 |
| | `test_regras_de_consolidacao_sao_experimentais` | CONS-PAR v1/v2 = experimental / HIPÓTESE |
| RREO | `test_conciliacao_reproduz_etapa02` | com RREO-COL v1, diferenças idênticas às da Etapa 02 |
| | `test_rreo_col_v2_fecha_c_e_i_de_2025_...` | v2 zera (c) de 2025 e (i) do consolidado de 2025; (i) 4º bim/2026 muda 49,50 |
| | `test_rreo_col_v2_torna_L_igual_a_S1_...` | L = S1 em todas as visões com v2 |
| | `test_rreo_sem_snapshot_correspondente_...` | sem corte correspondente → registro, não invenção |
| Tempo | `test_mesmo_corte_em_datas_diferentes` | 2 snapshots do mesmo corte; "como estava em" escolhe certo; diferença = vazio |
| | `test_SINTETICO_alteracao_retroativa_...` | **dados inventados**: dois retratos com valor diferente convivem; a diferença é detectada |
| Reprocessamento | `test_reprocessamento_deterministico` | duas derivações, mesmo hash |

---

## 10. LIMITAÇÕES E PONTOS EM ABERTO

1. **Regras experimentais: RREO-COL v2, CONS-PAR v1 e CONS-PAR v2.** Para promover alguma a padrão, é preciso:
   - (a) resposta do e-SIC sobre a natureza das cópias; e/ou
   - (b) repetir o padrão em outro exercício, por exemplo coletando 2024 das entidades 1 e 15 e conciliando com os RREOs de 2024; e
   - (c) no caso de RREO-COL v2, um caso a mais que não seja cópia 24xxxxx.
   Até lá, toda visão analítica e toda conciliação mostram qual regra usaram.
2. **CONS-PAR v2 só é verificável em corte que feche o exercício** (31/12) ou em que B não tenha execução. Num corte intermediário de um ano em que o original é executado, a relação "A = saldo final de B" não fecha, e o par fica não consolidado (conservador).
3. **Carimbos aproximados na carga de validação:** movimentações, recoleta, PDFs de publicações e catálogos da Etapa 01 usam `mtime_arquivo`. Na produção, o coletor carimba pelo próprio relógio.
4. **Visões do Município exigem todas as entidades no mesmo corte.** A política de coleta tem de coletar as 10 juntas.
5. **Ainda NÃO DETERMINADO:**
   - lacuna (h)/(i) do 3º/4º bim/2026;
   - reclassificação de 1.829,50 em 2025;
   - a natureza das cópias (transferência ou duplicidade).
   O modelo apenas registra.
6. **Pareamento limitado ao padrão conhecido** (entidade 1 ↔ 15, +2.400.000).
7. **Extrator de RREO dependente do layout.** Qualquer mudança exige nova versão.
8. **SQLite não tem permissões:** a imutabilidade vale dentro do banco. Hashes e cópia de segurança protegem contra alteração do arquivo.
9. **Derivação recalcula tudo** (< 10 s hoje). Com anos de snapshots pode ficar lenta; derivação incremental por snapshot é otimização para depois, sem mudar o modelo.
10. **Não validado com dados reais:**
    - evidência externa (tabela existe, sem dado);
    - estorno de cancelamento e retenção sobre liquidação de ano anterior (regras herdadas como HIPÓTESE da Etapa 02).

**Incertezas da Etapa 02 resolvidas nesta etapa** (com as regras experimentais):
- §10.4: −462,00 em (c) de 2025 → pagamento `pagoAProc` do registro só-processado 15863/2023.
- §10.12: coincidência 925.702,62 → as 20 cópias da entidade 15 inseridas depois dos RREOs de 2025 (CONS-PAR v2).
- §3.3: (i) −2.554,25 do consolidado de 2025 → `pagoProc` de 8 registros só-não-processados da entidade 15.
- §10.3: 2410946/2025 → mesmo mecanismo (RREO-COL v2).

---

## 11. ESPECIFICAÇÃO PARA A ETAPA 04

**Proposta:** implementar o **coletor definitivo e o pipeline** (bruto → normalizado → derivado) sobre este esquema. **Ainda sem interface, gráficos nem indicadores.**

1. **Coletor**
   - Única via de escrita da camada 0 com a semântica de `registrar_coleta`: atômica, paginação completa, `status`, pausa entre requisições, nova tentativa só em 5xx, carimbo do próprio relógio, versão com hash do código.
   - Tipos: listagem de RP (**sem tipo**, `dataInicial` = 01/01), publicações + PDFs do RREO, catálogos de entidades/exercícios, movimentação sob demanda.
   - Coleta **de todas as entidades no mesmo corte**.
2. **Agendamento:** exercício corrente mensal; fechados trimestral; RREO por publicação nova.
3. **Armazenamento:** corpo comprimido + hash do conteúdo original; bytes idênticos reaproveitados entre snapshots, sem apagar snapshot.
4. **Pipeline:** normalização e derivação versionadas, reprocessáveis a partir do bruto, com o catálogo de regras da seção 6 (sem regra nova sem evidência). Todas as versões de regra vigentes são calculadas lado a lado.
5. **Os 26 testes desta etapa viram portão de qualidade** do pipeline, junto com as verificações gravadas em `verificacao` a cada execução.
6. **Carga inicial:** importar os dados brutos das Etapas 01/02 como snapshots históricos, com carimbo aproximado identificado.

**Decisões do usuário antes da Etapa 04:**
- (a) tecnologia do banco (seção 4.3);
- (b) onde o banco vai morar (fora do OneDrive sincronizado, recomendado) e como será o backup;
- (c) quais exercícios entram na carga inicial (2016–2026? só 2024–2026?);
- (d) qual regra de agregação será a **padrão de apresentação** (RREO-COL v1, que segue o campo, ou v2, que reproduz o RREO), mantendo a outra calculada;
- (e) quando enviar o e-SIC e se a Etapa 04 deve coletar 2024 das entidades 1 e 15 para testar as regras experimentais em mais um ano.
