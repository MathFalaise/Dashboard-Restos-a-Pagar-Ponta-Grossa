# Restos a Pagar de Ponta Grossa — Relatório da Etapa 02 (Validação contábil e conciliação)

Investigação feita em 29/09/2026, entre 20h00 e 20h40 (horário de Brasília).

**Base de evidência:**
- ~225 requisições à API do portal, com pausa entre elas:
  - 69 páginas da listagem de RP;
  - 140 movimentações de empenho;
  - 11 PDFs do RREO Anexo VII e 2 listagens de publicações.
- Consultas ao Tesouro Nacional (MDF 15ª edição) e ao Planalto (Lei 4.320/64 e Decreto 93.872/86).
- Todo o dado bruto está em `dados_brutos/`, com SHA-256 em `dados_brutos_SHA256.txt`. As saídas das análises estão em `resultados/` e os scripts de investigação em `investigacao/` (não é código de produção).

**Classificação usada:**
- **CONFIRMADO** — evidência suficiente na fonte oficial (RREO) ou em documentação oficial, com resultado exato.
- **FORTE EVIDÊNCIA** — consistente em muitos casos, mas com alguma limitação.
- **HIPÓTESE** — plausível, sem comprovação.
- **NÃO DETERMINADO** — evidência insuficiente.

**Abreviações:**
- "Aba P" = registros com `proc > 0`; "Aba N" = registros com `aproc > 0`.
- "Só-P" = `proc > 0` e `aproc = 0`.
- "Período" = intervalo [`dataInicial`, `dataFinal`].

---

## 1. RESUMO

### 1.1 O que foi confirmado

1. **O Anexo VII do RREO se reconstrói a partir da API, coluna a coluna, ao centavo.**
   - Condição: consulta com `dataInicial = 01/01` do exercício, e dados que não tenham sido alterados depois da emissão do RREO.
   - Em 2026:
     - 2º bimestre: 8 de 9 colunas conferem ao centavo; (h) difere em R$ 644,16;
     - 3º e 4º bimestres: 7 de 9 conferem.
   - No consolidado do 2º bimestre de 2026, a soma das 10 entidades confere em 8 de 9 colunas.
2. **As duas abas são definidas pelo valor de abertura:**
   - Processados = `proc > 0`;
   - Não Processados = `aproc > 0`;
   - "nas duas abas" = as duas condições ao mesmo tempo.
   - Vale para 100% dos registros (4.557 em 2026 e 3.990 em 2025). O mesmo empenho traz valores idênticos nas três consultas (Processados, NaoProcessados e sem tipo).
3. **`proc` e `aproc` são saldos imediatamente antes de `dataInicial`:**
   - `proc`: liquidado e não pago;
   - `aproc`: empenhado e não liquidado.
   - Com `dataInicial = 01/01`, são exatamente o inscrito em RP Processados e em RP Não Processados.
4. **Os campos de fluxo** (`pagoProc`, `pagoAProc`, `canceladoAProc`, `liquidado`, `retencao`, `*Estornado`) **são movimentos com data dentro do período.** Somam entre períodos em 100% dos registros; a exceção é `pagoAProcEstornado`, explicada na seção 8.
5. **Existe um modelo de reconstrução** que, a partir da movimentação de cada empenho, reproduz todos os campos da listagem.
   - Acertou 139 de 140 empenhos, em 7 períodos e 10 campos: 120 aleatórios com 8.400 comparações e zero divergências, mais 19 de 20 casos escolhidos.
   - A única exceção (2410946/2025) é um registro "espelho", descrito no item 8.
6. **O saldo pendente é calculável com fórmula comprovada.** Ver seção 9.
7. **Pagamentos já vêm líquidos de estornos.** Os campos `*Estornado` são informativos e não devem ser subtraídos de novo.
8. **Não existe cancelamento em `canceladoProc`**: é sempre 0 em todos os registros observados. Todo cancelamento aparece em `canceladoAProc`. RP processado é cancelado em dois passos: estorno da liquidação (`liquidado` negativo), depois cancelamento.
9. **Os dados mudam depois de publicados.** Lançamentos com data retroativa e registros inseridos depois alteram exercícios fechados e bimestres já publicados. A API mostra o estado atual; cada RREO é um retrato do dia da emissão.
10. **Os RP de 2025 da Fundação Municipal de Saúde aparecem duplicados na Prefeitura**, por conteúdo:
    - 711 de 711 empenhos da entidade 15 têm uma cópia na entidade 1, com o número 2.400.000 + número original, mesmo credor, mesma data e mesmos valores;
    - a execução de 2026 ocorre só na cópia;
    - somar entidades conta essas inscrições duas vezes, e **o RREO consolidado publicado faz exatamente isso**.
    - A natureza do fato (transferência ou duplicidade) **não foi determinada**.

### 1.2 Correções à Etapa 01

- A lista de RREO de 2026 vai **até o 4º bimestre**, e não até o 2º. O script da Etapa 01 quebrou num arquivo cujo tamanho vinha nulo.
- A "aparente divergência" do empenho 11963/2016 está explicada (seção 4): não há saldo pendente.
- O valor que a aba Processados mostra como "Valor Cancelado" (`canceladoProc`) **nunca** é o cancelamento do RP processado.
- O campo `tamanhoArquivo` da listagem de publicações não corresponde ao tamanho do arquivo baixado. Por exemplo, a listagem informa 1.332.265 bytes e o arquivo tem 18.472.

### 1.3 Resultado sobre os indicadores (item 14 da especificação)

| Indicador | Resposta | Motivo |
|---|---|---|
| Valor inscrito | **SIM** | `proc`/`aproc` com `dataInicial = 01/01` reproduzem (a), (b), (f), (g) do RREO ao centavo. Ressalva: reflete a base **atual**, que pode diferir de um RREO já publicado (item 1.1.9). |
| Valor pago | **PARCIALMENTE** | Processados: SIM (coluna (c) exata). Não processados: coluna (i) exata em 2025 e no 2º bim/2026, mas 0,14% a 0,28% menor que o RREO no 3º e 4º bim/2026, sem causa determinada. |
| Valor cancelado | **SIM** | (d) e (j) exatos em 2026. A separação processado × não processado é por registro (seção 6). Ressalva: caso "duas abas com cancelamento da parte processada" não observado. |
| Saldo | **SIM** | Saldo total, a liquidar e liquidado a pagar: fórmulas S1–S3 comprovadas em todos os registros. Saldo "estilo RREO" (e/k): SIM para (e); (k) herda a lacuna de (i). |
| Evolução anual | **PARCIALMENTE** | A continuidade 2025→2026 está provada (saldo final = inscrição seguinte, 1.247/1.247 registros). Mas a série muda retroativamente e há a duplicidade da entidade 15. Uma série "como publicada" exige guardar retratos datados. Só 2025 e 2026 foram conciliados. |
| Processados | **SIM** | Inscrito, pago, cancelado e saldo conferem com o RREO. |
| Não Processados | **PARCIALMENTE** | Inscrito e cancelado: SIM. Liquidado e pago: lacuna não explicada em dois bimestres de 2026. |

---

## 2. SEMÂNTICA DOS CAMPOS

### 2.1 Tabela de campos

Notação: `movimentos(data < di)` = lançamentos da movimentação do empenho com data anterior a `dataInicial`. `período` = data dentro de [`dataInicial`, `dataFinal`], com as duas pontas inclusivas.

| Campo | Significado determinado | Confiança | Evidência |
|---|---|---|---|
| `proc` | Saldo **liquidado e não pago** do empenho antes de `dataInicial` = liquidações − estornos de liquidação − pagamentos + estornos de pagamento − retenções + estornos de retenção, todos com data < `dataInicial`. Com `dataInicial = 01/01` = **RP Processados inscritos**, incluindo RPNP liquidados em anos anteriores e ainda não pagos, como manda o MDF 15ª ed. | **CONFIRMADO** com 01/01; **FORTE EVIDÊNCIA** para outra data | (a)+(b) do RREO exatas no 2º, 3º e 4º bim/2026; continuidade 2025→2026 em 1.247/1.247; modelo em 139/140 empenhos; identidade de estoque em 3.403/3.403 |
| `aproc` | Saldo **empenhado e não liquidado** antes de `dataInicial` = empenho − anulações/cancelamentos + estornos − liquidações líquidas, com data < `dataInicial`. Com 01/01 = **RP Não Processados inscritos**. | **CONFIRMADO** com 01/01; **FORTE EVIDÊNCIA** para outra data | (f)+(g) exatas no 2º, 3º e 4º bim/2026; `aproc[01/02] = aproc − liquidado − canceladoAProc` de janeiro em 3.403/3.403 |
| `canceladoProc` | **Sempre 0.** Nenhum registro, entidade, exercício ou período observado tem valor diferente de zero. O significado pretendido não pode ser determinado. | **NÃO DETERMINADO** (o fato "é sempre 0" está confirmado nos dados baixados) | Somas em `resultados/03` e `04` |
| `canceladoAProc` | Cancelamentos do empenho **no período**, de qualquer parcela, processada ou não, líquidos de estorno de cancelamento. | **FORTE EVIDÊNCIA** | (d) = soma nos só-P e (j) = soma na aba N, ambos exatos no 2º–4º bim/2026; casos C0, C, I1; modelo 139/140. Estorno de cancelamento no período **não observado**: essa parte é HIPÓTESE |
| `pagoProc` | Pagamentos − estornos de pagamento **no período**, referentes a **liquidações de exercício anterior** ao consultado. Já é líquido de estornos. | **CONFIRMADO** para o total (coluna (c)); **FORTE EVIDÊNCIA** para a regra de separação | (c) exata no 2º–4º bim/2026; D1 (235.205,82 − 156.803,88 = 78.401,94); 1 exceção (I2) |
| `pagoAProc` | Pagamentos − estornos de pagamento **no período** referentes a **liquidações do próprio exercício**, **mais retenções** (− estornos de retenção) dessas liquidações. | **FORTE EVIDÊNCIA** | (i) exata em 2025 (3º, 5º e 6º bim) e no 2º bim/2026; lacuna de 0,14–0,28% no 3º/4º bim/2026; casos G, G2, G3, H2, I3 (ex.: G: 99.754,55 pago + 4.825,69 retido = 104.580,24) |
| `pagoProcEstornado` | Soma **bruta** dos estornos de pagamento no período, sobre liquidações de exercício anterior. **Informativo**: já foi descontado de `pagoProc`. | **FORTE EVIDÊNCIA** | D1: 73.587,00 + 4.814,94 + 73.587,00 + 4.814,94 = 156.803,88; modelo 139/140; identidades de saldo fecham **sem** este campo (3.403/3.403) |
| `pagoAProcEstornado` | Idem, sobre liquidações do exercício. Informativo. **Não é aditivo entre períodos** (seção 8). | **FORTE EVIDÊNCIA** | D1: 254.462,96; G3: 14.454,45; 11 registros não aditivos explicados pelo universo |
| `liquidado` | Liquidações − estornos de liquidação **no período**, de qualquer liquidação do empenho. **Negativo** quando há estorno de liquidação de parcela já liquidada: o valor volta a "a liquidar". | **FORTE EVIDÊNCIA** | (h) exata em 2025 (3 bimestres); +644,16 no 2º bim/2026; lacuna no 3º/4º bim/2026; casos C0, C, D2 com valor negativo |
| `retencao` | Retenções − estornos de retenção **no período** (lançamentos 50/51). **Já está contida em `pagoAProc`** quando a liquidação é do exercício. | **FORTE EVIDÊNCIA** | D1, G, G2, G3, H2, I3; modelo 139/140. Retenção sobre liquidação de exercício anterior **não observada**: nesse caso o tratamento é HIPÓTESE |

Campos de identificação:

| Campo | Significado | Confiança | Evidência |
|---|---|---|---|
| `anoempenho` | Exercício de emissão do empenho. Sempre < `exercicio` consultado. | **CONFIRMADO** | 0 registros com `anoempenho ≥ exercicio`; (b)/(g) = `anoempenho = exercício − 1` e (a)/(f) = `anoempenho < exercício − 1`, exatos |
| `empenho` | Número do empenho **dentro da entidade e do ano**. A chave única é (`entidade`, `anoempenho`, `empenho`). | **CONFIRMADO** | 45 números iguais entre as entidades 1 e 15 em 2026, todos com credores diferentes |
| empenho ≥ 2.400.000 | Na entidade 1, cópia de um empenho da entidade 15 (número original + 2.400.000). | **CONFIRMADO** (espelhamento, 711/711 por conteúdo); natureza **NÃO DETERMINADA** | Seção 3.5 |

### 2.2 Matriz de confiabilidade

| Regra / interpretação | Status | Evidência |
|---|---|---|
| Aba Processados = registros com `proc > 0` | CONFIRMADO | 1.663/1.663 (2026), 699/699 (2025) |
| Aba Não Processados = registros com `aproc > 0` | CONFIRMADO | 3.091/3.091 (2026), 3.364/3.364 (2025) |
| "Nas duas abas" = `proc > 0` e `aproc > 0`: empenho com parte liquidada a pagar e parte a liquidar na abertura | CONFIRMADO | 197/197 (2026), 73/73 (2025); casos H1 e H2 |
| Consulta sem `tipoPesquisa` = uma linha por empenho, união das abas, mesmos valores | CONFIRMADO | 4.557 = 1.466 + 2.894 + 197; 0 campos diferentes |
| `proc` (01/01) = RP Processados inscritos (a+b) | CONFIRMADO | RREO exato (2º, 3º e 4º bim/2026) |
| `aproc` (01/01) = RP Não Processados inscritos (f+g) | CONFIRMADO | RREO exato (2º, 3º e 4º bim/2026) |
| `proc`/`aproc` são saldos antes de `dataInicial` e **não dependem de `dataFinal`** | CONFIRMADO | 0 variações em 4.557 registros × 5 valores de `dataFinal` |
| RPNP liquidado e não pago no ano passa a `proc` no ano seguinte (MDF 15ª ed.) | CONFIRMADO | continuidade 2025→2026: 1.247/1.247; caso B1 |
| Fluxos = soma de movimentos com data no período (pontas inclusivas) | CONFIRMADO | aditividade em 4.557/4.557 para 8 campos; pagamento de 31/08 incluído (B0) |
| Universo da consulta = empenhos com saldo `proc + aproc > 0` antes de `dataInicial` | FORTE EVIDÊNCIA | 1.154/1.154 que saíram em 01/02 tinham saldo 0; o universo com 01/01 não muda com `dataFinal` |
| Movimentos de empenho **fora do universo** (saldo 0 em `dataInicial`) **são omitidos** | CONFIRMADO (caso) / FORTE EVIDÊNCIA (regra) | 20738/2025 e 20744/2025; 11 registros não aditivos |
| `pagoProc`/`pagoAProc` são líquidos de estornos | CONFIRMADO | D1 exato; identidades fecham sem `*Estornado` |
| Separação `pagoProc` × `pagoAProc` pelo exercício da liquidação (anterior × do ano) | FORTE EVIDÊNCIA | 139/140; aditividade de `pagoProc` independe de `dataInicial` |
| `pagoAProc` inclui retenções das liquidações do exercício | FORTE EVIDÊNCIA | 6 casos exatos; (i) do RREO exata onde não há lacuna |
| (c) do RREO = soma de `pagoProc` na aba P | CONFIRMADO | exato no 2º, 3º e 4º bim/2026 |
| (d) do RREO = soma de `canceladoAProc` nos só-P | FORTE EVIDÊNCIA | exato no 2º, 3º e 4º bim/2026; o caso "duas abas" nunca ocorreu |
| (j) do RREO = soma de `canceladoAProc` na aba N | CONFIRMADO | exato no 2º, 3º e 4º bim/2026 |
| (h) do RREO = soma de `liquidado` na aba N | FORTE EVIDÊNCIA | exato em 2025; lacuna de até 0,40% no 3º/4º bim/2026 |
| (i) do RREO = soma de `pagoAProc` na aba N | FORTE EVIDÊNCIA | exato em 2025 e no 2º bim/2026; lacuna de até 0,28% no 3º/4º bim/2026 |
| RREO consolidado = soma das 10 entidades | CONFIRMADO | 2º bim/2026: 8/9 exatas (h: +644,16) |
| RREO de um bimestre é reproduzível depois | HIPÓTESE (em geral NÃO) | 1º bim/2026 e 2025 divergem por alterações posteriores (seção 3.4) |
| `canceladoProc` tem algum uso | NÃO DETERMINADO | sempre 0 |
| Lacuna de (h)/(i) no 3º/4º bim/2026 | NÃO DETERMINADO | seção 10 |
| Espelhamento entidade 15 → entidade 1 é transferência legítima ou duplicidade | NÃO DETERMINADO | seção 3.5 |
| Movimentação: rótulos de pagamento trocados (em 40/41 a liquidação está em `exercicioPagamento`/`noPagamento`) | FORTE EVIDÊNCIA | cruzamento com `/detalhe/pagamentos` (5659/2025); o modelo depende disso e acertou 139/140 |

---

## 3. RECONCILIAÇÃO COM O RREO

### 3.1 O que o RREO apresenta (PDF do portal)

- O documento é "RREO – Anexo VII (LRF, art. 53, inciso V) – Demonstrativo dos Restos a Pagar por Poder e Órgão – Orçamentos Fiscal e da Seguridade Social".
- Tem uma versão da entidade (Prefeitura, "Poder Executivo") e uma consolidada, geradas pelo sistema Elotech.
- Linhas:
  - RP exceto intraorçamentários (I), só com "Poder Executivo";
  - RP intraorçamentários (II), sempre zero;
  - Total (III).
- Colunas:

| Bloco | Coluna | Rótulo |
|---|---|---|
| Processados | (a) | Inscritos em exercícios anteriores |
| | (b) | Inscritos em 31/dez do exercício anterior |
| | (c) | Pagos |
| | (d) | Cancelados |
| | (e) | Saldo = (a+b) − (c+d) |
| Não Processados | (f) | Inscritos em exercícios anteriores |
| | (g) | Inscritos em 31/dez do exercício anterior |
| | (h) | Liquidados |
| | (i) | Pagos |
| | (j) | Cancelados |
| | (k) | Saldo = (f+g) − (i+j) |
| Total | (L) | Saldo total = e + k |

- As fórmulas internas do PDF fecham ao centavo (conferido em todos os PDFs).

### 3.2 Correspondência RREO × API

| RREO | API | Relação | Evidência |
|---|---|---|---|
| (a) | Σ `proc`, registros com `proc > 0` e `anoempenho < exercício − 1`, com `dataInicial = 01/01` | direta | exato no 2º, 3º e 4º bim/2026 |
| (b) | Σ `proc`, `proc > 0` e `anoempenho = exercício − 1` | direta | exato em 2025 (3 bimestres) e no 2º–4º bim/2026 |
| (c) | Σ `pagoProc` nos registros com `proc > 0`, período 01/01 → fim do bimestre | direta | exato no 2º, 3º e 4º bim/2026 |
| (d) | Σ `canceladoAProc` nos registros com `proc > 0` e `aproc = 0` | **indireta**: o RREO chama de "Processados cancelados" o que a API guarda em `canceladoAProc` | exato no 2º, 3º e 4º bim/2026 (4º: 78.570,99) |
| (e) | (a)+(b) − (c)−(d) | derivada | exato no 3º e 4º bim/2026 |
| (f) | Σ `aproc`, `aproc > 0` e `anoempenho < exercício − 1` | direta | exato no 2º, 3º e 4º bim/2026 |
| (g) | Σ `aproc`, `aproc > 0` e `anoempenho = exercício − 1` | direta | exato no 2º, 3º e 4º bim/2026 |
| (h) | Σ `liquidado` nos registros com `aproc > 0` | direta, com lacuna | exato em 2025; +644,16 no 2º bim/2026; −216.913,24 no 3º; −345.479,56 no 4º |
| (i) | Σ `pagoAProc` nos registros com `aproc > 0` (inclui retenções) | direta, com lacuna | exato em 2025 e no 2º bim/2026; −109.112,43 no 3º; −237.728,25 no 4º |
| (j) | Σ `canceladoAProc` nos registros com `aproc > 0` | direta | exato no 2º, 3º e 4º bim/2026 |
| (k), (L) | derivadas | — | (k) herda a lacuna de (i) |

**Não há correspondência** para `canceladoProc` (sempre 0), `pagoProcEstornado`, `pagoAProcEstornado` e `retencao`. O RREO não tem essas colunas; a retenção está embutida em (i).

### 3.3 Resultado por bimestre (entidade 1, diferença API − RREO)

| Referência | (a) | (b) | (c) | (d) | (f) | (g) | (h) | (i) | (j) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 2025 3º bim (emit. 29/07/2025) | 1.829,50 | 0 | −462,00 | 35.529,49 | 6.580,50 | 917.292,62 | **0** | **0** | 4.184.895,81 |
| 2025 5º bim (emit. 27/11/2025) | 1.829,50 | 0 | −462,00 | 1.829,50 | 6.580,50 | 917.292,62 | **0** | **0** | −1.829,50 |
| 2025 6º bim (emit. 30/01/2026) | 1.829,50 | 0 | −462,00 | 1.829,50 | 6.580,50 | 917.292,62 | **0** | **0** | −1.829,50 |
| 2026 1º bim (emit. 27/03/2026) | 1.829,50 | 11.158.739,30 | −262.716,27 | 1.829,50 | −1.829,50 | −3.290.752,98 | −3.224.757,44 | −4.236.912,01 | −1.829,50 |
| 2026 2º bim (emit. 29/05/2026) | **0** | **0** | **0** | **0** | **0** | **0** | 644,16 | **0** | **0** |
| 2026 3º bim (emit. 29/07/2026) | **0** | **0** | **0** | **0** | **0** | **0** | −216.913,24 | −109.112,43 | **0** |
| 2026 4º bim (emit. 29/09/2026) | **0** | **0** | **0** | **0** | **0** | **0** | −345.479,56 | −237.728,25 | **0** |

Consolidado:
- 2º bim/2026: a soma das 10 entidades confere em 8 de 9 colunas ((h): +644,16).
- 6º bim/2025: as mesmas lacunas da entidade 1, mais (i) −2.554,25 de outra entidade (não isolado).
- Só as entidades 1, 4, 5, 8 e 15 têm RP em 2025/2026. As entidades 3, 6, 9, 10 e 11 devolveram 0 registros.

### 3.4 Diferenças explicadas

1. **2025, (a)+(f)+(g) = 925.702,62**
   - São 20 registros com numeração ≥ 2.400.000 (anoempenho 2023/2024), inseridos na entidade 1 **depois** dos RREOs de 2025.
   - Esses registros têm `aproc` = 917.292,62 (anoempenho 2024), igual à lacuna de (g), e 8.410,00 de anos anteriores, igual a (a)+(f) = 1.829,50 + 6.580,50.
   - A troca de 1.829,50 entre (a) e (f), e entre (d) e (j), é uma reclassificação de soma zero entre processado e não processado.
   - Não identifiquei o registro dessa reclassificação: **NÃO DETERMINADO**.
   - Status: **CONFIRMADO** (soma exata por segmento).
2. **2025 3º bim, (j) e (d)**
   - O RREO publicado em julho/2025 mostrava só 1.829,50 de cancelamentos de RPNP no semestre.
   - A API mostra hoje 4.186.725,31 com data no semestre.
   - Conclusão: os cancelamentos foram **lançados depois com data retroativa**.
   - Status: FORTE EVIDÊNCIA; o horário de lançamento não é visível na fonte.
3. **2026 1º bim, quase todas as colunas**
   - O fechamento de 2025 foi refeito depois de 27/03/2026.
   - (a)+(f) é idêntico nos dois momentos (20.300.529,04), mas (b)+(g) cresceu 7.867.986,32.
   - Coincide com a inserção, na entidade 1, das 711 cópias da entidade 15 (seção 3.5), cujos efeitos não isolei integralmente.
   - Status: FORTE EVIDÊNCIA para "base alterada depois da emissão"; NÃO DETERMINADO o detalhamento exato.
4. **2025 (c) −462,00**: pequena alteração posterior. **NÃO DETERMINADO** qual registro.

### 3.5 Espelhamento da Fundação Municipal de Saúde (entidade 15) na Prefeitura (entidade 1)

- Os 711 RP de anoempenho 2025 da entidade 15 têm, na entidade 1, um registro com o número `2.400.000 + número original` e a mesma assinatura. Exemplo: 21/2025 na entidade 15 ↔ 2400021/2025 na entidade 1.
  - A assinatura comparada é CNPJ/CPF, data de emissão, `proc` e `aproc`.
  - Resultado: **711 de 711**. A programática tem o mesmo prefixo, órgão 24.
  - Em 2025 há 20 cópias equivalentes, de anoempenho 2023/2024.
- **A execução de 2026 está só na cópia da entidade 1.**
  - Na cópia, de janeiro a abril: `pagoProc` 10.193.610,01, `pagoAProc` 6.331.257,71, `liquidado` 6.633.013,32.
  - Na entidade 15, todos os fluxos são zero.
- Consequências:
  - A **entidade 1 inclui hoje RP da Saúde**, que no RREO de 1º bim/2026 ainda não estavam lá.
  - **Somar entidades conta a inscrição duas vezes:** cerca de 30,9 milhões em 2026, ou 11.345.828,15 em (b) e 19.542.374,70 em (g).
  - O **RREO consolidado publicado** confere com essa soma, portanto também conta duas vezes.
  - Os originais da entidade 15 ficam com saldo integral, sem execução, e **inflam o saldo consolidado**.
- **O que não se pode afirmar:** se é uma transferência formal de RP entre entidades, que deveria ter baixa na origem, ou um erro. **NÃO DETERMINADO** — só a Prefeitura pode responder (e-SIC ou consulta ao órgão contábil).

### 3.6 Diferença não explicada

- (h) e (i) no 3º e 4º bimestres de 2026: a API fica abaixo do RREO em 0,14–0,40%.
- Testes que **não** explicaram a lacuna:
  - uma nova coleta 13 minutos depois (sem alteração);
  - procurar um registro isolado com o valor exato;
  - registros restabelecidos depois de 01/01 (nenhum encontrado);
  - fluxos das cópias 24xxxxx.
- Do incremento de julho–agosto, R$ 49,50 são explicados pelo registro 2410946/2025, pago como processado na API e provavelmente como não processado no RREO. O resto é **NÃO DETERMINADO**.
- **Hipóteses:**
  - (1) lançamentos com data retroativa depois da emissão;
  - (2) regra própria do RREO para algum tipo de movimento não presente nos 140 empenhos examinados.

### 3.7 Norma × implementação

| Tema | O QUE A NORMA DIZ | COMO O PORTAL IMPLEMENTA O DADO |
|---|---|---|
| Definição | Lei 4.320/64, art. 36: RP são "despesas empenhadas mas não pagas até o dia 31 de dezembro distinguindo-se as processadas das não processadas". Decreto 93.872/86, art. 67 §1º: processadas = liquidadas; não processadas = não liquidadas | `proc` = liquidado não pago; `aproc` = empenhado não liquidado, medidos antes de `dataInicial`. Com 01/01 coincidem com a norma |
| RPNP liquidado no ano | MDF 15ª ed. (03.07.05.01): permanece nas colunas de não processados no ano de referência; no exercício seguinte o saldo liquidado a pagar vai para Processados – Inscritos – Em Exercícios Anteriores | Idêntico com `dataInicial = 01/01`: `aproc` não muda no ano e a liquidação vai para `liquidado`. No ano seguinte o saldo entra em `proc` (1.247/1.247). **Com `dataInicial` ≠ 01/01 a API já mostra o liquidado do ano dentro de `proc`**, o que não é o critério do RREO |
| Título do bloco | O MDF 9ª ed. usava "Processados e Não Processados Liquidados em Exercícios Anteriores"; o MDF 15ª ed. diz que "não há mais a discriminação" | O PDF do portal usa "RESTOS A PAGAR PROCESSADOS", coerente com a 15ª ed. |
| Cancelamento de RP processado | MDF 15ª ed.: RP processados "em geral, não podem ser cancelados", salvo motivo previsto na legislação | O município cancela, sempre em dois passos: estorno da liquidação e depois cancelamento do empenho. A API registra em `liquidado` (−) e `canceladoAProc`; o RREO mostra em (d) |
| Pagos | MDF: "já foram pagos, durante o exercício de referência" | Líquido de estornos; em não processados inclui retenções. O tratamento de retenção **na norma não foi verificado** nesta etapa |
| Saldo (e), (k) | "Inscritos menos os Cancelados e menos os Pagos"; (e) = RPP pendentes de pagamento; (k) = RPNP pendentes de pagamento | Reproduzível pela API (seção 9, fórmula S4) |

Fontes normativas (texto guardado em `dados_brutos/normas/`):
- [Lei 4.320/64](https://www.planalto.gov.br/ccivil_03/leis/l4320.htm), arts. 36 e 63;
- [Decreto 93.872/86](https://www.planalto.gov.br/ccivil_03/decreto/d93872.htm), arts. 67 e 68;
- [MDF 15ª edição, STN](https://thot-arquivos.tesouro.gov.br/publicacao-anexo/26033), item 03.07, págs. 295–302 do PDF;
- [MDF 9ª edição, Anexo 7](https://conteudo.tesouro.gov.br/manuais/index.php?option=com_content&view=article&id=1262:03-07-05-01-tabela-7-demonstrativo-dos-restos-a-pagar-por-poder-e-orgao&catid=636&Itemid=675), só para comparação histórica.

---

## 4. CASOS INDIVIDUAIS

Exercício consultado: 2026, entidade 1.
- Seleção determinística: primeiro empenho, em ordem de chave, que atende à condição.
- Cronologias completas em `resultados/07_casos_cronologia.txt`.
- Comparação com o modelo nos 7 períodos em `resultados/05`.
- Valores da API no período 01/01–31/12/2026, com as fórmulas da seção 9 aplicadas:

| Caso | Empenho | proc | aproc | pagoProc | pagoAProc | cancel.AProc | liquidado | retencao | *Estornado | S1 saldo | S2 a liquidar | S3 liq. a pagar | Saldo pela movimentação | Modelo × API (7 períodos) |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|---|
| A proc. sem pagamento | 2398/2012 | 754,32 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 754,32 | 0 | 754,32 | 754,32 | OK |
| B proc. pago (Etapa 01) | 5659/2025 | 3.141.530,40 | 0 | 2.277.745,06 | 0 | 0 | 0 | 0 | 0 | 863.785,34 | 0 | 863.785,34 | 863.785,34 | OK |
| B1 proc. pago integralmente | 22455/2022 | 8.147,23 | 0 | 8.147,23 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | OK |
| B2 proc. pago em parte | 5658/2025 | 1.258.490,49 | 0 | 810.085,45 | 0 | 0 | 0 | 0 | 0 | 448.405,04 | 0 | 448.405,04 | 448.405,04 | OK |
| C proc. cancelado (Etapa 01) | 11963/2016 | 3.864,52 | 0 | 0 | 0 | 3.864,52 | −3.864,52 | 0 | 0 | 0 | 0 | 0 | 0 | OK |
| C proc. cancelado | 15577/2023 | 74.425,32 | 0 | 0 | 0 | 74.425,32 | −74.425,32 | 0 | 0 | 0 | 0 | 0 | 0 | OK |
| D1 pagamento estornado (complexo) | 1874/2025 | 163.888,32 | 348.199,16 | 163.888,32 | 178.165,77 | 0 | 262.263,85 | 8.551,96 | 411.266,84 | 170.033,39 | 85.935,31 | 84.098,08 | 170.033,39 | OK |
| D2 estorno de liquidação sem cancelamento | 15193/2025 | 24.166,60 | 0 | 0 | 0 | 0 | −24.166,60 | 0 | 0 | 24.166,60 | 24.166,60 | 0 | 24.166,60 | OK |
| E não proc. sem liquidação | 14285/2017 | 0 | 7.879,90 | 0 | 0 | 0 | 0 | 0 | 0 | 7.879,90 | 7.879,90 | 0 | 7.879,90 | OK |
| F não proc. liquidado em parte | 7724/2017 | 0 | 2.874,26 | 0 | 1.175,76 | 0 | 1.175,76 | 0 | 0 | 1.698,50 | 1.698,50 | 0 | 1.698,50 | OK |
| G não proc. liquidado e pago | 23729/2022 | 0 | 104.580,24 | 0 | 104.580,24 | 0 | 104.580,24 | 4.825,69 | 0 | 0 | 0 | 0 | 0 | OK |
| G2 não proc. só retenção "paga" | 12057/2024 | 0 | 514.673,37 | 0 | 39.730,44 | 0 | 292.157,17 | 39.730,44 | 0 | 474.942,93 | 222.516,20 | 252.426,73 | 474.942,93 | OK |
| G3 não proc. com estorno de pagamento | 17442/2024 | 0 | 50.000,00 | 0 | 14.224,98 | 0 | 28.679,43 | 1.376,58 | 14.454,45 | 35.775,02 | 21.320,57 | 14.454,45 | 35.775,02 | OK |
| H1 duas abas | 933/2021 | 540,00 | 10,00 | 0 | 0 | 0 | 0 | 0 | 0 | 550,00 | 10,00 | 540,00 | 550,00 | OK |
| H2 duas abas, dois tipos de pagamento | 23186/2023 | 72.890,38 | 559.880,98 | 72.890,38 | 559.880,98 | 0 | 559.880,98 | 15.113,22 | 0 | 0 | 0 | 0 | 0 | OK |
| I1 cancelamento parcial + liquidações | 11921/2024 | 200,23 | 23.069,17 | 200,23 | 1.360,99 | 13.960,31 | 1.860,06 | 0 | 0 | 7.747,87 | 7.248,80 | 499,07 | 7.747,87 | OK |
| I2 cópia 24xxxxx | 2410946/2025 | 0 | 49,50 | **49,50** | **0** | 0 | 49,50 | 0 | 49,50 | 0 | 0 | 0 | 0 | **diverge** (pago como processado) |
| I3 retenção | 5176/2023 | 0 | 198.278,74 | 0 | 198.278,74 | 0 | 198.278,74 | 13.751,63 | 0 | 0 | 0 | 0 | 0 | OK |
| I4 fora do universo em 01/02 | 20738/2025 | 0 | 4.500,00 | 0 | 4.500,00 | 0 | 4.500,00 | 0 | 9.000,00 | 0 | 0 | 0 | 0 | OK |
| I4 idem | 20744/2025 | 0 | 4.500,00 | 0 | 4.500,00 | 0 | 4.500,00 | 0 | 4.500,00 | 0 | 0 | 0 | 0 | OK |

S1 bate com o saldo reconstruído da movimentação em **20 de 20** casos.

### 4.1 Caso obrigatório — 11963/2016 (entidade 1)

1. **O que aconteceu contabilmente.**
   - Empenho de 25.000,00 (28/06/2016), liquidado integralmente (16/11/2016) e pago em 21.135,48 (17/11/2016).
   - Sobraram 3.864,52 liquidados e não pagos: um **RP processado** desde 2017.
   - Em 27/05/2026, **estorno da liquidação** de 3.864,52: o valor deixa de ser liquidado.
   - Em 28/05/2026, **cancelamento do empenho** de 3.864,52.
2. **Na movimentação:** "31 Estorno Liquidação 3.864,52 (Ref. a Liq: 1/2016)" e "21 Cancelamento Empenho 3.864,52"; o saldo a pagar vai a 0.
3. **Na listagem:**
   - `proc` = 3.864,52 em todo período que começa em 01/01; é o inscrito.
   - A partir de um período que inclua maio: `liquidado` = −3.864,52 (o estorno) e `canceladoAProc` = 3.864,52 (o cancelamento).
   - Em janeiro–março os fluxos são 0, porque os movimentos são de maio. O modelo reproduz os 7 períodos.
4. **Por que `canceladoProc` fica em 0:**
   - `canceladoProc` é 0 em **todos** os registros da base, então o sistema não usa esse campo (FORTE EVIDÊNCIA).
   - O cancelamento acontece **depois** do estorno da liquidação: no momento do cancelamento, o valor já é "a liquidar" (não processado). Por isso cai em `canceladoAProc`.
   - O RREO trata como cancelamento de **processado** (coluna (d)), porque o registro só está na aba P.
5. **Saldo pendente:** **não há**. S1 = 3.864,52 + 0 − 0 − 0 − 3.864,52 = 0, igual ao saldo reconstruído da movimentação.
6. **Como o sistema futuro deve representar:**
   - RP processado inscrito em 01/01/2026: 3.864,52;
   - cancelado no exercício: 3.864,52, classificado como cancelamento de **processado**, como no RREO (d);
   - saldo: 0.
   - Opcionalmente, registrar o evento "estorno de liquidação" (`liquidado` negativo) como marca de que o processado foi reclassificado antes do cancelamento.
   - Nunca exibir "Cancelado 0" para esse RP, como faz a aba Processados do portal.

### 4.2 Caso obrigatório — 5659/2025 (entidade 1)

- **Saldo anterior:**
  - empenho de 3.871.740,70 liquidado em 28/04/2025;
  - pagamentos em 2025 de 447.573,22 + 228.819,88 + 53.817,20;
  - saldo a pagar em 31/12/2025: **3.141.530,40**.
- **Pagamentos de 2026**, todos sobre a liquidação 1/2025:

| Data | Valor |
|---|--:|
| 19/01 | 140.157,01 |
| 19/02 | 188.166,60 |
| 06/03 | 441.378,44 |
| 19/03 | 260.180,98 |
| 24/04 | 211.397,04 |
| 04/05 | 245.081,19 |
| 11/06 | 306.641,86 |
| 06/07 | 267.924,46 |
| 30/07 | 130.090,49 |
| 31/08 | 86.726,99 |
| **Total** | **2.277.745,06** |

- **Comportamento por período:**

| Período | `proc` | `pagoProc` |
|---|--:|--:|
| 01/01–31/01 | 3.141.530,40 | 140.157,01 |
| 01/02–31/03 | **3.001.373,39** | 889.726,02 |
| 01/01–31/03 | 3.141.530,40 | 1.029.883,03 |
| 01/01–30/06 | 3.141.530,40 | 1.793.003,12 |
| 01/01–31/08 | 3.141.530,40 | 2.277.745,06 |
| 01/01–31/12 | 3.141.530,40 | 2.277.745,06 |

- **O que `proc` representa:** o saldo liquidado e não pago **imediatamente antes de `dataInicial`**.
  - Com 01/02: 3.141.530,40 − 140.157,01 (pagamento de janeiro) = 3.001.373,39.
- **Teste em outros empenhos:**
  - a interpretação vale nos 140 empenhos examinados (139 exatos; o 140º diverge em outro campo);
  - a identidade de estoque vale em 3.403/3.403 registros.
  - **Ressalva:** com `dataInicial` ≠ 01/01, `proc` inclui também RPNP liquidados no próprio ano e ainda não pagos, pois a identidade é `proc[01/02] = proc − pagoProc + liquidado − pagoAProc` de janeiro. Assim "saldo existente no início" é verdade, mas **não é mais "RP processado inscrito"**.

---

## 5. TRATAMENTO DE ESTORNOS

| Estorno | Como aparece | Tratamento correto | Confiança |
|---|---|---|---|
| Estorno de pagamento (41) | Já descontado de `pagoProc`/`pagoAProc`. O valor bruto aparece em `pagoProcEstornado`/`pagoAProcEstornado`, pela mesma regra de exercício da liquidação | Usar `pagoProc`/`pagoAProc` como estão. **Não subtrair** os campos `*Estornado`: seria descontar duas vezes. Use-os só como indicador de volume de estornos | FORTE EVIDÊNCIA (D1, G3, B1, I4; identidades sem esses campos em 3.403/3.403) |
| Estorno de liquidação (31) | `liquidado` negativo no período; o valor volta ao "a liquidar" | Para o saldo total não muda nada (S1 não usa `liquidado`). Para a composição, S2/S3 mostram a mudança de natureza (D2: 24.166,60 passa de "liquidado a pagar" para "a liquidar") | FORTE EVIDÊNCIA (C0, C, D2, D1) |
| Estorno de retenção (51) | Descontado de `retencao` e de `pagoAProc` | Nada a fazer | HIPÓTESE para 2026 (só observado em 2025, fora do período testado) |
| Estorno de cancelamento (22) | Pelo modelo, reduz `canceladoAProc` | — | HIPÓTESE (só observado em 2016, no mesmo dia do cancelamento) |

Os campos `*Estornado` **não são aditivos entre períodos**: um estorno pode ocorrer num período em que o empenho está fora do universo (seção 8).

---

## 6. TRATAMENTO DE CANCELAMENTOS

1. `canceladoProc` = 0 sempre. **Não usar.**
2. Todo cancelamento está em `canceladoAProc`: líquido de estornos de cancelamento (HIPÓTESE) e com data no período.
3. **Cancelamento de RP processado** acontece como estorno de liquidação seguido de cancelamento (C0, C). Nos dados:
   - `liquidado` negativo e `canceladoAProc` positivo no mesmo registro;
   - em 2025, 13/13 registros só-P com cancelamento tinham `liquidado = −canceladoAProc`.
   - Pode haver estorno **sem** cancelamento (D2). Em jan–ago/2026, os só-P somam `liquidado` = −102.737,59 e `canceladoAProc` = 78.570,99; a diferença, 24.166,60, é exatamente o caso D2.
4. **Classificação processado × não processado de um cancelamento** (é o que o RREO faz, com FORTE EVIDÊNCIA):
   - registro só-P → cancelamento de processado (d);
   - registro com `aproc > 0` → cancelamento de não processado (j).
   - **Não determinado:** um registro "nas duas abas" que cancele a parte processada. Não houve nenhum caso em 2026 (0/197), e o RREO provavelmente o poria em (j).
5. **Norma × prática:** o MDF diz que RP processado "em geral" não pode ser cancelado; Ponta Grossa cancela. O sistema deve mostrar isso como fato, sem julgamento.

---

## 7. PROCESSADOS × NÃO PROCESSADOS

- A classificação vem **da abertura do período**: saldo liquidado e não pago → `proc`; saldo não liquidado → `aproc`.
  - Com `dataInicial = 01/01` coincide com a inscrição e com o MDF 15ª ed. (CONFIRMADO pelo RREO).
- **Empenho nas duas abas:** existência **simultânea** de uma parcela liquidada a pagar e de uma parcela a liquidar no início do período.
  - Não é mudança de situação nem outra estrutura.
  - Exemplos: H1 (933/2021: 540,00 liquidado a pagar + 10,00 a liquidar); H2 (23186/2023: 72.890,38 da liquidação 2/2025 + 559.880,98 não liquidados; em 2026 a primeira parcela é paga como processado e a segunda é liquidada e paga como não processado).
  - Status: **CONFIRMADO** para a regra; os exemplos confirmam a interpretação.
- **Consequência para somas:** as abas trazem o **mesmo registro com todos os campos**. Somar os totais das duas abas conta duas vezes os 197 empenhos comuns. Exemplo: em jan–ago/2026, a aba P soma `aproc` = 13.097.523,90, e isso pertence a registros que também estão na aba N.
  - Regra para a Etapa 03: usar **uma linha por empenho** (consulta sem `tipoPesquisa`) e calcular cada categoria pelo campo correspondente.
- **Durante o ano**, o RPNP liquidado **continua** não processado (em `aproc`/`liquidado`/`pagoAProc`) e só vira processado no ano seguinte (CONFIRMADO: MDF + continuidade 1.247/1.247).
- **Pagamento:** a separação `pagoProc` × `pagoAProc` é pelo exercício da liquidação paga (anterior × do ano).

---

## 8. EFEITO DO PERÍODO

Testes com uma variável de cada vez (2026, entidade 1, consulta sem tipo; `resultados/04`):

| Teste | Período | Registros |
|---|---|--:|
| A | 01/01–31/12 | 4.557 |
| B | 01/01–31/01 | 4.557 |
| C | 01/02–31/03 | 3.403 |
| D | 01/01–31/03 | 4.557 |
| E | 01/01–30/06 | 4.557 |
| F | 01/01–31/08 | 4.557 |
| X | 01/02–31/12 | 3.403 |

| Pergunta | Resposta | Confiança |
|---|---|---|
| Estoque/saldo inicial | `proc`, `aproc` = saldo antes de `dataInicial`. Não mudam com `dataFinal` (0 variações) | CONFIRMADO |
| Pagamento no período | `pagoProc` + `pagoAProc` (líquidos; `pagoAProc` com retenções). Aditivos: D = B + C em 4.557/4.557 | CONFIRMADO |
| Cancelamento no período | `canceladoAProc`; aditivo em 4.557/4.557 | CONFIRMADO |
| Liquidação no período | `liquidado`, líquido de estornos e podendo ser negativo; aditivo em 4.557/4.557 | CONFIRMADO |
| Retenção no período | `retencao`; aditiva em 4.557/4.557 | CONFIRMADO |
| Limites de data | Inclusivos nas duas pontas (pagamento de 31/08 entra em 01/01–31/08) | CONFIRMADO (B0) |
| Universo | Só empenhos com `proc + aproc > 0` antes de `dataInicial`. 1.154 saíram ao mover o início para 01/02; todos tinham saldo 0 no fim de janeiro | FORTE EVIDÊNCIA |
| Movimento de empenho fora do universo | **Omitido.** 20738/2025 foi pago em 30/01, teve estornos e novo pagamento em fevereiro, e desaparece de 01/02–31/03 com seus 9.000,00 de `pagoAProcEstornado`. Por isso `pagoAProcEstornado` não é aditivo (11 registros) | CONFIRMADO (casos); o efeito sobre campos líquidos é possível em tese, sem ocorrência observada |
| Relação exercício × ano do empenho | `exercicio` = exercício de referência; `anoempenho` = ano de emissão, sempre < `exercicio`. (b)/(g) = `anoempenho = exercicio − 1`; (a)/(f) = anteriores | CONFIRMADO |
| `exercicio` e datas de anos diferentes | Resultado incoerente (Etapa 01) | NÃO DETERMINADO — **não usar** |

**Conclusões:**
1. Para dados compatíveis com o RREO, use **sempre `dataInicial = 01/01` do exercício**. A evolução intra-anual se obtém variando **só `dataFinal`**, com fluxos acumulados.
2. Mudar `dataInicial` troca o universo e a semântica de `proc` e deve ser evitado.

---

## 9. FÓRMULAS POSSÍVEIS

Só fórmulas comprovadas. Todas por registro (chave `entidade + anoempenho + empenho`), numa consulta com `dataInicial = 01/01/AAAA` e `dataFinal = D`; os saldos são em D.

| # | Fórmula | Significado | Evidência | Status |
|---|---|---|---|---|
| **S1** | `saldo_total(D) = proc + aproc − pagoProc − pagoAProc − canceladoAProc` | RP ainda pendente em D (processado + não processado) | identidade 3.403/3.403; 1.154/1.154 zerados; continuidade 1.247/1.247; 20/20 casos iguais ao saldo da movimentação | **CONFIRMADO** |
| **S2** | `a_liquidar(D) = aproc − liquidado − canceladoAProc` | parcela ainda não liquidada | identidade 3.403/3.403; continuidade (`aproc` do ano seguinte) 1.247/1.247 | **CONFIRMADO** |
| **S3** | `liquidado_a_pagar(D) = proc − pagoProc + liquidado − pagoAProc` | parcela liquidada e não paga (inclui RPNP liquidado no ano) | S1 − S2; continuidade (`proc` do ano seguinte) 1.247/1.247 | **CONFIRMADO** |
| **S4** | por categoria de inscrição, como no RREO: **Saldo RPP (e)** = Σ `proc` [proc>0] − Σ `pagoProc` [proc>0] − Σ `canceladoAProc` [só-P]; **Saldo RPNP (k)** = Σ `aproc` [aproc>0] − Σ `pagoAProc` [aproc>0] − Σ `canceladoAProc` [aproc>0] | pendente por categoria de inscrição | (e) exato no 3º e 4º bim/2026; (k) exato no 2º bim/2026 e com a lacuna de (i) no 3º/4º | **FORTE EVIDÊNCIA** |
| **F1** | Inscrito RPP = Σ `proc` [01/01]; RPNP = Σ `aproc` [01/01]; separação (a)/(b) e (f)/(g) por `anoempenho` | inscrição | RREO exato | **CONFIRMADO** |
| **F2** | Pago no ano até D = Σ `pagoProc` + Σ `pagoAProc` (sem subtrair `*Estornado`) | pagamentos líquidos, com retenção em não processados | RREO (c) exato; (i) exato com ressalva | **FORTE EVIDÊNCIA** |
| **F3** | Cancelado no ano até D = Σ `canceladoAProc`; processado = só-P; não processado = `aproc > 0` | cancelamentos | RREO (d) e (j) exatos | **FORTE EVIDÊNCIA** |

**Não comprovadas, e por isso não recomendadas:**
- qualquer fórmula com `canceladoProc`;
- subtrair `*Estornado`;
- somar `retencao` ao pago (já está incluído);
- somar as duas abas;
- saldo com `dataInicial` ≠ 01/01 comparado com o RREO.

Diferença entre S1 e S4: S1 soma todos os registros; S4 ignora `pagoProc` de registros sem `proc` (o caso I2, R$ 49,50 em 2026). O total de S4 pode diferir de S1 nesse valor residual.

---

## 10. INCERTEZAS

1. **Lacuna de (h) e (i) no 3º e 4º bimestres de 2026** (−216.913,24 / −109.112,43 e −345.479,56 / −237.728,25). Causa NÃO DETERMINADA.
2. **Espelhamento entidade 15 → entidade 1:** transferência formal ou duplicidade? Os originais da entidade 15 deveriam ter baixa? O RREO consolidado está inflado? NÃO DETERMINADO. Só a Prefeitura pode esclarecer.
3. **Classificação de pagamento em cópias 24xxxxx:** 2410946/2025 foi pago como processado na API. Não sei se é regra das cópias ou caso isolado (1 de 140 examinados).
4. **Reclassificação de 1.829,50 em 2025** entre (a)/(f) e (d)/(j), e **−462,00 em (c)**: registros NÃO DETERMINADOS.
5. **`canceladoProc`:** finalidade desconhecida (sempre 0).
6. **Regras não exercitadas nos dados:**
   - estorno de cancelamento no período;
   - retenção sobre liquidação de exercício anterior;
   - cancelamento da parte processada de empenho "nas duas abas".
   São HIPÓTESES.
7. **Abrangência da validação:**
   - modelo por empenho validado só na entidade 1 e só no exercício 2026;
   - entidades 4, 5, 8 e 15 validadas apenas pela soma consolidada do 2º bim/2026;
   - exercícios 2016–2024 não foram conciliados.
8. **Volatilidade:**
   - a base recebe lançamentos com data retroativa e inserções posteriores;
   - a fonte não expõe data/hora de lançamento, então não dá para saber quando um valor mudou.
9. **`exercicio` e datas de anos diferentes:** comportamento incoerente, não investigado a fundo.
10. **Rótulos trocados na movimentação** (liquidação em `exercicioPagamento`/`noPagamento` nos lançamentos 40/41): confirmado por cruzamento em um empenho e sustentado pelo acerto do modelo. Não há documentação.
11. **Estágio "em liquidação"** (endpoint `/detalhe/em-liquidacao`): não examinado.
12. **Coincidência não explicada:** a soma das lacunas de 2025 (925.702,62) é igual ao (f) da entidade 15 em 2026. Os 20 registros da entidade 15 são originais (existiam lá em 2025). A relação provável são as 20 cópias 24xxxxx da entidade 1 em 2025, mas a correspondência registro a registro com a entidade 15 **não foi verificada**.

---

## 11. ESPECIFICAÇÃO PARA A ETAPA 03

Só regras e estruturas sustentadas por esta etapa. Os itens marcados **[decisão sua]** dependem de escolha do usuário.

### 11.1 Coleta

1. Endpoint `GET /portaltransparencia-api/empenhos/restos-a-pagar`, **sem `tipoPesquisa`** (uma linha por empenho), com:
   - `entidade = E`;
   - `exercicio = A`;
   - `dataInicial = A-01-01`;
   - `dataFinal = D`, com D ≤ 31/12/A;
   - `size = 2000`, paginando até `last`.
2. **Nunca** usar `exercicio` de um ano com datas de outro. **Nunca** usar `dataInicial` ≠ 01/01 para números "de RREO".
3. **Evolução intra-anual:** várias coletas do mesmo exercício com `dataFinal` = fim de cada mês ou bimestre (fluxos acumulados; a diferença entre duas coletas dá o fluxo do intervalo).
4. **Entidades com RP em 2025/2026:** 1, 4, 5, 8, 15. As outras (3, 6, 9, 10, 11) devolveram 0; manter a coleta, que é barata.
   - [decisão sua] se o "Município" é a soma das entidades (como o RREO consolidado) ou a soma **sem as duplicidades** da seção 3.5.
5. Guardar cada resposta **bruta e com data/hora**, como **retrato**. A base muda, então um exercício pode ter vários retratos.
   - [decisão sua] frequência de recoleta dos exercícios fechados.

### 11.2 Estrutura mínima de dados

- **Chave:** (`entidade`, `anoempenho`, `empenho`).
- **Dimensão da consulta:** `exercicio`, `dataInicial`, `dataFinal`, `coletado_em`.
- **Campos brutos preservados:** todos, inclusive `canceladoProc` (sempre 0) e `*Estornado`, para auditoria.
- **Campos derivados:**
  - `categoria_inscricao`: processado / não processado / ambos, pela regra `proc > 0` / `aproc > 0`;
  - S1, S2 e S3;
  - `faixa_rreo`: (a)/(b) ou (f)/(g), por `anoempenho` vs `exercicio − 1`;
  - `cancelamento_processado` = `canceladoAProc` se só-P, senão 0;
  - `cancelamento_nao_processado` = `canceladoAProc` se `aproc > 0`;
  - `copia_espelho` = entidade 1 e `empenho ≥ 2.400.000`, com o par na entidade 15 (`empenho − 2.400.000`) quando existir, verificado por CNPJ, data, `proc` e `aproc`.

### 11.3 Regras de cálculo permitidas

- **Inscrito:** F1.
- **Pago:** F2, sem subtrair `*Estornado`.
- **Cancelado:** F3.
- **Liquidado de RPNP no ano:** Σ `liquidado` [`aproc > 0`], com ressalva (seção 3.6).
- **Saldos:** S1, S2, S3 por registro; S4 para comparar com o RREO.

### 11.4 Validações obrigatórias a cada coleta

1. Soma de `numberOfElements` = `totalElements`.
2. Conjunto de chaves esperado; `canceladoProc` = 0 (alertar se deixar de ser).
3. **Continuidade entre exercícios:** para os empenhos presentes em A e A+1, `proc`(A+1) = S3 final de A e `aproc`(A+1) = S2 final de A. Alertar em qualquer divergência.
4. **Conciliação com o RREO publicado** do mesmo bimestre (colunas a–j, sabendo que o RREO é um retrato). Registrar as diferenças sem "corrigir" nada.
5. Marcar anomalias:
   - `liquidado < 0`;
   - `pagoProc ≠ 0` com `proc = 0`;
   - cópias 24xxxxx.

### 11.5 Proibido na Etapa 03 (por falta de base)

- Usar `canceladoProc`, ou os rótulos da tela do portal, como definição.
- Apresentar a soma das abas como total.
- Tratar a série histórica como imutável.
- Tratar o consolidado como "sem duplicidade" antes do esclarecimento da seção 3.5.

### 11.6 Movimentação por empenho

- `/empenhos/detalhe/movimentacao` serve só para **auditoria pontual** (uma requisição por empenho). Não deve ser coleta em massa.
- O modelo de reconstrução (seção 2 e `investigacao/reconstruir.py`, como especificação e não como código a reaproveitar) pode ser usado para explicar um valor específico.

---

### Anexo — onde está cada evidência

| Evidência | Arquivo |
|---|---|
| Conciliação por coluna (3 referências) | `resultados/01_conciliacao_rreo_ent1.txt` |
| Diferença por bimestre | `resultados/02_conciliacao_por_bimestre.txt` |
| Regra das abas e somas por segmento | `resultados/03_segmentos_abas.txt` |
| Testes de período | `resultados/04_testes_de_periodo.txt` |
| Modelo × API, casos selecionados | `resultados/05_modelo_casos_selecionados.txt` |
| Modelo × API, amostra aleatória | `resultados/06_modelo_amostra_aleatoria.txt` |
| Cronologias dos casos | `resultados/07_casos_cronologia.txt` |
| Páginas brutas da API + manifesto | `dados_brutos/api/` (`MANIFESTO.jsonl`) |
| Movimentações brutas (140) | `dados_brutos/movimentacao/` |
| RREO Anexo VII (11 PDFs) | `dados_brutos/rreo/` |
| Textos normativos | `dados_brutos/normas/` |
| Hashes | `dados_brutos_SHA256.txt` |

---

## ADENDO (29/09/2026, após a revisão da Etapa 02)

Uma verificação feita nos dados já baixados, sem novas requisições, corrige e amplia a seção 3.5.

1. **Em 2026, o espelhamento é de 731 registros, e não de 711.**
   - A entidade 1 tem 731 cópias (número ≥ 2.400.000): 711 de anoempenho 2025, 19 de 2024 e 1 de 2023.
   - As **731** têm par idêntico na entidade 15 (mesmos CNPJ/CPF, data de emissão, `proc` e `aproc`). Ou seja, todo o RP da entidade 15 em 2026 está espelhado na entidade 1.
   - Fluxos de janeiro a agosto de 2026:
     - nas cópias da entidade 1: `pagoProc` 11.252.733,57, `pagoAProc` 11.520.529,15, `liquidado` 11.835.589,40;
     - nos originais da entidade 15: **zero**.
2. **Em 2025, o lado que tem execução é o outro.**
   - As 20 cópias da entidade 1 não tiveram nenhum fluxo.
   - Das 20, 11 têm par idêntico na entidade 15. Esses 11 originais tiveram 75.000,00 cancelados em 2025.
   - Os outros 9 não casaram pela assinatura com os valores de 01/01/2025. **NÃO DETERMINADO** por quê.
3. **Consequência para a modelagem.** O lado do par que carrega a execução **muda de um exercício para outro**. Nenhuma regra fixa do tipo "sempre excluir a cópia" ou "sempre excluir o original" preserva a execução nos dois anos. A regra de deduplicação é **NÃO DETERMINADA**.
   - Hipótese a testar: contar a inscrição do par uma única vez e somar os fluxos dos dois lados. Nos dados observados, os fluxos aparecem em apenas um lado por exercício.
