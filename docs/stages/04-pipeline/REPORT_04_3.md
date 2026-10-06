# Etapa 04.3 — Carga controlada (relatório)

Feita em 30/09/2026 (madrugada).

**Escopo:**
- **Feito:**
  - importação das Etapas 01/02 para o armazém real;
  - coleta controlada de 2025 fechado e 2026 atual;
  - RREOs faltantes;
  - processamento e conciliação;
  - exclusão segura de execuções.
- **Não feito:** interface, dashboard, indicadores, carga histórica 2016–2024, promoção de regra.

## 1. Resumo

| Item | Resultado |
|---|---|
| Esquema do banco | migrado de v2 para **v3** automaticamente, **com backup antes** (registrado em `esquema_versao`) |
| Importação das Etapas 01/02 | **197 snapshots**, 0 problemas; importar de novo não duplica nada (testado) |
| Coleta controlada | **40 requisições**, 37 snapshots, todos `completa` |
| Armazém real | 244 snapshots, 227 objetos, 7,4 MB; banco 54 MB (local, fora do OneDrive) |
| "Como estava em 29/09 23:59" × Etapa 03 | **igual** em todos os registros, visões e conciliações |
| Retratos de 29/09 × coleta de 30/09 (mesmo corte) | **11 de 11 cortes com bytes idênticos**; retratos preservados separadamente |
| Hash estável | "atual" `b565669b…` e "como estava" `b8a0b2ed…` idênticos entre duas normalizações e depois do VACUUM |
| Testes | **61/61** em produção + 26/26 da Etapa 03 (investigação) |
| Integridade (`verificar`) | nenhum problema, em todas as etapas |

## 2. As duas exigências da revisão

### 2.1 Exclusão segura de execuções inteiras

Comandos:
- `python -m rp execucoes` lista as execuções;
- `python -m rp apagar-execucao --tipo derivacao|normalizacao --id N --confirmar N [--simular]` apaga uma.

| Proteção | Como |
|---|---|
| Só execução inteira | apaga todas as linhas daquela execução nas tabelas da camada 1 ou 2 e o registro dela; nunca linhas avulsas; nunca a camada 0 |
| Identificação clara | tipo + id explícitos; `--confirmar` tem de repetir o id; id inexistente é recusado |
| Dependência | normalização com derivações dependentes é recusada ("apague-as antes") |
| Execução em uso | a mais recente é recusada sem `--permitir-mais-recente` |
| Simulação | `--simular` mostra quantas linhas de cada tabela sairiam |
| Backup | antes de apagar (backup operacional, seção 4.3) |
| Verificação depois | nenhuma linha restante com aquele id; hash da camada 0 igual ao de antes; `verificar` do armazém × banco |

**Na prática, no banco real** (log em `resultados/04_3_exclusao_execucoes.txt`):
- 4 recusas: confirmação errada, normalização com dependente, execução mais recente e id inexistente. Nada foi apagado.
- Depois foram apagadas as execuções desatualizadas: as da 04.2 (anteriores à importação) e as duplicadas. Foram 4 derivações e 3 normalizações, cada uma com camada 0 intacta e integridade ok.
- **Ficaram:** normalização 4, derivação 5 ("atual") e derivação 6 ("como estava em 29/09").

### 2.2 Retratos antigos e coletas novas do mesmo corte são independentes

- **Cada coleta é um snapshot próprio.** Tem `snapshot_uid`, manifesto imutável e horário. Nada é substituído, fundido ou "atualizado".
  - Os bytes iguais são armazenados uma vez (objeto por conteúdo), mas o **retrato** continua existindo.
  - Teste: o manifesto do retrato antigo fica byte a byte igual depois da coleta nova.
- **Nova capacidade:** a derivação passou a ter **data de vigência** (esquema v3).
  - Com `processar --em DATA`, só entram snapshots coletados até DATA; a data fica registrada na execução.
  - Assim convivem, no mesmo banco, "o que o portal mostrava em 29/09" (derivação 6) e "o que mostra hoje" (derivação 5).
- **Retratos do mesmo corte:** para comparar bytes e registros, use `python -m rp comparar-snapshots --entidade E --exercicio A --data-final D`.

**Resultado real:**

| Corte | Retratos | Bytes |
|---|---|---|
| 2025 (01/01–31/12), 10 entidades | 29/09 20h12–20h34 (Etapa 02) × 30/09 00h18 (04.3) | **idênticos** nas 10 |
| Entidade 1, 2026 (01/01–31/08) | 29/09 20h12 × 20h25 × 21h35 × 30/09 00h18 | **idênticos** nos 4 |

**Ressalva honesta:** o intervalo entre os retratos foi de ~4 horas, à noite. Ainda não se observou uma alteração retroativa real entre retratos. O comportamento com base alterada está coberto pelo teste sintético (dois retratos com valor diferente convivem, e a diferença é detectada). O teste real exige recoletas com dias de intervalo, na 04.4.

### 2.3 PDFs do RREO: snapshot → extração versionada → valores → conciliação

- Cada PDF é um snapshot `rreo_pdf`. Os valores vão para `rreo_valor`, com a **versão do extrator**, dentro de uma normalização.
- **Uma normalização nova nunca altera a anterior.** Testado: as 517 linhas extraídas continuam idênticas depois de outra normalização.
- **Layout desconhecido não derruba mais o processamento** (antes, abortava a normalização inteira):
  - o problema fica gravado na execução (`normalizacao_execucao.observacao`);
  - os demais dados são normalizados;
  - a derivação registra a verificação "RREO sem valores extraídos". Testado com um PDF sintético.

## 3. Operações no armazém real (em ordem)

1. **Abertura do banco** → migração v2 → v3, com backup `20260930-001726_antes-migracao-v2-v3.sqlite`.
2. **Importação** das Etapas 01/02: backup antes; 197 snapshots (41 listagens + 1 recoleta + 140 movimentações + 2 publicações + 11 PDFs + 2 catálogos); 0 problemas.
3. **Coleta controlada**, 40 requisições, todas `completa`:
   - catálogos: entidades + exercícios de 1, 15, 4, 5, 8 (6 requisições);
   - listagens de **2025 fechado (01/01–31/12)** e **2026 até 31/08** para as **10 entidades** (23 requisições). Ver a decisão na seção 6;
   - RREO: listagens de 2025 e 2026 + **9 PDFs do Anexo VII que faltavam** (8 de 2025, 1 de 2026).
4. **Processamento:**
   - derivação "atual" (5) e "como estava em 29/09 23:59" (6) sobre a mesma normalização (4);
   - repetido para conferir o hash (seção 1).
5. **Exclusão** das execuções desatualizadas (seção 2.1) e **compactação** (VACUUM: 111 MB → 56 MB; hashes recalculados iguais).

## 4. Portões

### 4.1 Testes

| Conjunto | Resultado |
|---|---|
| Coletor | 18/18 |
| 26 testes da Etapa 03 sobre produção | 26/26 |
| Processamento (04.2) | 7/7 |
| **Novos da 04.3:** migração com backup; exclusão (recusas e sucesso); retenção de backups; compactação; retratos antigos × novos; RREO com layout desconhecido; extração anterior preservada; importação idempotente | 10/10 |
| **Total `app/tests`** | **61/61** |
| 26 testes originais da Etapa 03 (investigação) | 26/26 |

### 4.2 Conciliação com o RREO no armazém real (`resultados/04_3_reconciliacao.md`)

**A) "Como estava em 29/09" × investigação da Etapa 03: igual.**

| Comparação | Linhas | Igual? |
|---|--:|---|
| registros normalizados / derivados (snapshots da investigação) | 82.988 / 82.988 | SIM |
| movimentações normalizadas / interpretadas | 2.004 / 2.004 | SIM |
| anomalias | 10.837 | SIM |
| pares espelhados | 751 | SIM |
| valores de todas as visões (entidade, publicada, analíticas; RREO-COL v1/v2 × CONS-PAR v1/v2) | 1.020 | SIM |
| conciliação RREO × API (por PDF, regra e coluna) | 216 | SIM |

**B) "Atual" × "como estava em 29/09":**
- 0 diferenças nos 1.020 valores dos cortes comuns.
- As novidades vêm só dos cortes de 31/08/2026 de todas as entidades: as visões de Município e a conciliação consolidada do 4º bimestre.

### 4.3 Problema encontrado e corrigido nesta subetapa: backups de exclusão

- A primeira versão fazia um backup **completo** do banco (111 MB) antes de cada exclusão, em `data/backups/`, dentro do OneDrive. Sete exclusões geraram **754 MB** sincronizando.
- **Correção:**
  - backups **operacionais** (antes de apagar uma execução, que é reprocessável a partir do bruto) vão para a pasta **local** `C:\Users\maped\RestosAPagar_local\backups_operacionais\`, mantendo só os **3 mais recentes** (testado);
  - backups de mudança estrutural, importação e manuais continuam em `data/backups/` e **nunca são apagados automaticamente** (testado);
  - os 7 arquivos criados foram **movidos** (não apagados) para a pasta local; `data/backups/` voltou a 11 MB;
  - novo comando `compactar` (VACUUM) para devolver ao disco o espaço de execuções apagadas.
- **Decisão sua:** os 7 backups operacionais (743 MB, locais) podem ser apagados, porque tudo o que protegem é reprocessável. A retenção automática de 3 vale para os próximos. Não apaguei nenhum.

## 5. Foco pedido: 2025/2026 × entidades 1 e 15 (derivação "atual")

### 5.1 Pares espelhados (entidade 1 = A, cópia; entidade 15 = B, original)

| Corte | Relação | Execução | Pares | Inscrito A | Inscrito B | Execução A | Execução B |
|---|---|---|--:|--:|--:|--:|--:|
| 2025 até 31/12 | A = saldo final de B | **B** | 9 | 493.284,72 | 1.103.073,27 | 0,00 | 1.021.899,82 |
| 2025 até 31/12 | igual | nenhum | 11 | 432.417,90 | 432.417,90 | 0,00 | 0,00 |
| 2026 até 30/04 | igual | **A** | 356 | 23.262.860,00 | 23.262.860,00 | 23.233.461,98 | 0,00 |
| 2026 até 30/04 | igual | nenhum | 375 | 8.551.045,47 | 8.551.045,47 | 0,00 | 0,00 |
| **2026 até 31/08** (novo) | igual | **A** | **562** | 28.143.226,03 | 28.143.226,03 | 34.608.852,12 | **0,00** |
| **2026 até 31/08** (novo) | igual | nenhum | 169 | 3.670.679,44 | 3.670.679,44 | 0,00 | 0,00 |

- O padrão se mantém no corte novo: em 2026, **toda** a execução está na cópia da entidade 1. A entidade 15 tem pagamento, liquidação e cancelamento **zero** no ano, e o saldo S1 dela (31.813.905,47) não se move entre 30/04 e 31/08.
- Nenhum par tem execução nos dois lados, e nenhuma cópia ficou sem par.

### 5.2 Visões por entidade (RREO-COL v1)

| Entidade | Corte | (a)+(b) | (f)+(g) | (c) | (h) | (i) | (j) | S1 |
|---|---|--:|--:|--:|--:|--:|--:|--:|
| 1 | 2025 até 31/12 | 27.657.040,00 | 175.951.244,01 | 26.203.276,11 | 136.380.158,67 | 136.288.900,26 | 20.761.380,47 | 20.300.529,04 |
| 15 | 2025 até 31/12 | 93.473,32 | 42.815.720,14 | 93.473,32 | 31.292.797,61 | 31.290.243,36 | 10.597.219,91 | 925.702,62 |
| 1 | 2026 até 31/08 | 28.877.504,33 | 137.112.078,77 | 25.557.330,59 | 85.253.628,49 | 83.655.417,66 | 8.015.744,44 | 48.682.469,92 |
| 15 | 2026 até 31/08 | 11.345.828,15 | 20.468.077,32 | 0,00 | 0,00 | 0,00 | 0,00 | 31.813.905,47 |

### 5.3 Município: publicado × analíticas × RREO consolidado (RREO-COL v2)

| Corte | | Publicado | Analítico v1 | Analítico v2 | RREO consolidado |
|---|---|--:|--:|--:|--:|
| 2025 até 31/12 | L | 21.267.174,28 | 20.834.756,38 | **20.341.471,66** | **20.341.471,66** |
| 2026 até 30/04 | L | 104.135.295,67 | 72.321.390,20 | 72.321.390,20 | 104.135.295,67 |
| **2026 até 31/08** (novo) | L | 80.844.090,29 | 49.030.184,82 | 49.030.184,82 | 80.606.411,54 |

A diferença entre a visão publicada e as analíticas em 2026 é sempre a inscrição dos 731 pares contada uma vez só: **31,8 milhões**.

### 5.4 Nova: conciliação do RREO consolidado do 4º bim/2026

Só é possível agora, com todas as entidades coletadas no corte de 31/08.

| Coluna | RREO | Dif. RREO-COL v1 | Dif. RREO-COL v2 |
|---|--:|--:|--:|
| (a), (b), (d), (f), (g), (j) | — | 0,00 | 0,00 |
| (c) | 25.648.732,39 | **+3.692,25** | **+3.692,25** |
| (h) | 92.521.797,18 | −345.479,56 | −345.479,56 |
| (i) | 90.788.014,24 | −241.438,48 | −241.371,00 |

- **(h):** −345.479,56 é exatamente a lacuna já conhecida da entidade 1 (Etapa 02). Continua **NÃO DETERMINADA**.
- **(c) +3.692,25: explicado ao centavo.**
  - Na entidade 5 (Fundação de Assistência Social), o empenho **1485/2025** tem `proc` = 6.080,77 e `pagoProc` = 9.773,02. O excesso, 9.773,02 − 6.080,77, é exatamente 3.692,25.
  - **Hipótese:** o RREO limita o "pago processado" ao inscrito processado e lança o excesso em "pago não processado" (i). Isso explicaria 3.692,25 dos 3.710,23 que sobram em (i) além da lacuna da entidade 1; restam 17,98 sem explicação.
  - **Status: HIPÓTESE** (1 caso). Nenhuma regra nova foi criada nem promovida. Se se confirmar em mais casos, vira candidata a RREO-COL v3.

## 6. Decisões tomadas nesta subetapa (para a sua revisão)

1. **Incluí as entidades 3, 6, 9, 10 e 11 nas listagens** (1 requisição por corte cada; nenhuma tem RP).
   - Motivo: pela regra aprovada na Etapa 03 (§4.2), as visões do Município e a conciliação do RREO **consolidado** só existem com **todas** as entidades do catálogo no mesmo corte.
   - Sem elas, a conciliação consolidada do 4º bimestre (seção 5.4) seria impossível.
   - Isso também confirma, a cada coleta, que continuam sem RP.
2. **"2026 atual" = corte até 31/08/2026**, último mês fechado.
   - Casa com o RREO do 4º bimestre, publicado em 29/09.
   - Um corte até 30/09 feito na madrugada de 30/09 seria um mês incompleto.
3. **Backups operacionais fora do OneDrive, com retenção** (seção 4.3).

## 7. Limitações e pendências

1. Alteração retroativa real entre retratos **ainda não observada** (intervalo de 4 horas). Precisa de recoletas espaçadas (04.4).
2. **PDFs do RREO de 2025 (1º, 2º e 4º bim) sem corte correspondente na API** (2025 até 28/02, 30/04 e 31/08). Ficam registrados como "RREO sem snapshot da API no mesmo corte". Coletar esses cortes é barato (10 requisições cada) e entra naturalmente na 04.4.
3. Lacunas em aberto:
   - (h)/(i) da entidade 1 no 3º e 4º bim/2026;
   - 17,98 em (i) consolidado;
   - hipótese do empenho 1485/2025 da entidade 5;
   - espelhamento entre entidades 15 e 1.
   Todas continuam registradas, nenhuma "corrigida".
4. **A versão do coletor mudou depois da coleta** (0.3.0 + hash), porque o código foi alterado para corrigir os backups. As coletas desta subetapa ficaram registradas com a versão exata que as fez; as próximas registrarão a nova.
5. **Movimentação:** só as 141 herdadas da Etapa 02 + 1 da 04.1. Coleta sob demanda, como decidido.

## 8. Próxima subetapa proposta: 04.4 — expansão

- **Carga histórica 2016–2024** das entidades 1, 4, 5, 8 e 15 (+ as vazias, pela regra do Município), em **lotes por exercício**, com processamento, testes, conciliação e integridade a cada lote.
- Cortes bimestrais de 2025 que faltam, para conciliar os PDFs que já estão no armazém. Recoleta dos cortes de 2025/2026 com alguns dias de intervalo, para observar alterações retroativas reais.
- **2024 das entidades 1 e 15** como validação das regras experimentais (CONS-PAR v2), sem promover nada.
- Política de agendamento (ainda sem executar automaticamente, se preferir).
- Continua sem interface, dashboard e indicadores.
