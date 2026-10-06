# Prova real: banco ativo × fonte (05/10/2026)

Fonte primária: Portal da Transparência de Ponta Grossa (`https://servicos.pontagrossa.pr.gov.br/portaltransparencia/1/`), que lê os dados da API `portaltransparencia-api` (Elotech/Oxy, versão 3.128.0 no rodapé).

O banco ativo (`~/RestosAPagar_local/banco/restos_a_pagar.sqlite`: derivação atual 23, hash `2f6b4e29…`) foi **só lido**. A recoleta foi gravada num armazém e num banco temporários em `C:\rpaud\prova`, fora do projeto.

## Resultado em uma linha

O banco reproduz **exatamente** o que a fonte publicava quando foi coletado: 0 erro de gravação, transcrição ou cálculo em 130.893 registros. Hoje a fonte só difere do banco em **4 cortes de 2026 da Prefeitura**, porque recebeu lançamentos depois da coleta de 29–30/09, alguns com data retroativa, e em **nomes de credor de 16 registros**. Nenhum registro falta e nenhum sobrou.

## Como foi feito

| Nível | Pergunta | Como |
|---|---|---|
| N1 | A tela do portal é a mesma coisa que o banco? | 180 empenhos lidos na **tela** do portal no navegador (3 consultas), confrontados empenho a empenho com o banco |
| N2 | A fonte hoje é igual ao que foi gravado? | Recoleta completa pela própria API, com o coletor do projeto, de tudo o que o banco tem: 193 cortes, 147 movimentações, 11 catálogos e 35 PDFs do RREO (495 requisições, pausa de 1,5 s, segunda leitura das listagens com várias páginas) |
| N3 | O banco gravou fielmente o bruto? | Cada registro do snapshot que o painel usa × a linha de `rp_registro`, campo a campo, com o mapeamento refeito de forma independente (`comparar_fonte.py`) |
| N4 | O que a tela do painel mostra bate com o bruto? | Os 14 indicadores de cada corte × o recálculo independente (`app/tests/recalculo_bruto.py`), sobre o bruto gravado e sobre o bruto de hoje |

## Resultados

### N1 — Tela do portal × banco: 180 de 180 iguais

| Consulta no portal | Empenhos | Iguais (inscrito, liquidado, cancelado, pago) |
|---|---|---|
| Prefeitura, 2026 (Processados e Não Processados) | 100 | 100 |
| Prefeitura, 2025 | 40 | 40 |
| Fundação Municipal de Saúde, 2026 (banco: corte 31/08) | 40 | 40 |

A página `/restos-a-pagar` do portal consulta `empenhos/restos-a-pagar` da mesma API, separada em `tipoPesquisa=Processados` e `NaoProcessados`, com o período de 01/01 a 31/12. Na tela, "Valor Pago" é o pagamento bruto (`pagoProc`/`pagoAProc`), o mesmo campo que o banco guarda.

### N3 — Bruto gravado × banco: 0 diferença

130.893 registros, todos os campos (21 de identificação e classificação, 10 monetários): **nenhuma diferença**, nenhum registro sem linha no banco e nenhuma linha a mais.

### N4 — Painel × recálculo independente: 0 diferença

Os 14 indicadores dos 193 cortes (registros, inscrição, pagamentos, estornos, liquidações, cancelamentos, retenções, saldos S1/S2/S3) são iguais ao recálculo feito direto do JSON gravado.

### N2 — API hoje × banco

| | Banco (coleta de 29–30/09) | API hoje (05/10) |
|---|---|---|
| Cortes | 193 | 193, todos com coleta completa |
| Registros | 130.893 | 130.893 |
| Registros que faltam / que surgiram | — | 0 / 0 |
| Cortes idênticos | — | 184 |
| Registros com algum campo diferente | — | 94, em 9 cortes |
| Catálogos (entidades e exercícios) | 11 | 11 idênticos |
| PDFs do RREO Anexo VII | 35 | 35 com os mesmos bytes |
| Movimentações | 147 | 144 idênticas; 3 com lançamentos novos |

**Os 2016–2025 estão iguais à fonte.** Nos exercícios fechados só mudou o nome de credor de 2 registros (2017 e 2020). O número do documento não mudou: é cadastro atualizado, sem efeito em valor.

**As diferenças de valor estão só nos cortes de 2026 da Prefeitura (entidade 1):**

| Corte | Indicador | Banco | API hoje | Diferença |
|---|---|---:|---:|---:|
| 30/04/2026 | Cancelamentos | 3.498.779,83 | 4.769.459,08 | +1.270.679,25 |
| | Saldo total (S1) | 70.974.405,61 | 69.703.726,36 | −1.270.679,25 |
| 30/06/2026 | Cancelamentos | 4.262.232,22 | 5.532.911,47 | +1.270.679,25 |
| | Pagamentos | 102.161.781,12 | 102.087.617,12 | −74.164,00 |
| | Saldo total (S1) | 59.565.569,76 | 58.369.054,51 | −1.196.515,25 |
| 31/08/2026 | Cancelamentos | 8.094.315,43 | 9.346.175,70 | +1.251.860,27 |
| | Pagamentos | 109.212.797,75 | 108.898.708,65 | −314.089,10 |
| | Saldo total (S1) | 48.682.469,92 | 47.744.698,75 | −937.771,17 |
| 31/12/2026 | Cancelamentos | 8.146.347,32 | 9.436.848,14 | +1.290.500,82 |
| | Pagamentos | 110.316.250,61 | 110.489.597,30 | +173.346,69 |
| | Saldo total (S1) | 47.526.985,17 | 46.063.137,66 | −1.463.847,51 |

A tabela completa de cada corte, com todos os indicadores, está em `comparacao_banco_x_api_20261005.json`.

**Explicação:**
- **Cancelamento retroativo:** 8 empenhos de 2025 passaram a ter cancelamento de não processado no corte de 30/04/2026, somando R$ 1.270.679,25. Em 29–30/09 esse cancelamento não existia na fonte. Como o corte de 30/04 só soma lançamentos até 30/04, o cancelamento foi lançado depois de 30/09 com data até 30/04. Esse é o fenômeno de alteração retroativa já registrado na Etapa 04.4. A data exata dos lançamentos não foi verificada, porque esses 8 empenhos não têm movimentação coletada.
- **Estornos e lançamentos novos:** pagamentos e liquidações caíram nos cortes de 30/06 e 31/08 (estornos com data passada) e subiram no corte de 31/12, que ainda está aberto. As 3 movimentações que mudaram mostram isso: pagamento de 01/10, liquidação e retenção de 30/09, e um par pagamento + estorno de 27/08 que apareceu depois.
- Nada disso é erro do banco. O banco é o retrato fiel da fonte em 29–30/09, e a fonte mudou depois.

### Os 31 cortes "sem valor"

31 cortes aparecem no painel como "entidade inexistente no exercício", sem valor. Para esses cortes a API devolve hoje lista vazia (0 registros), o que é coerente. Outros 42 cortes aparecem como "entidade existente sem RP": nesses, o zero é real, e a API também devolve 0.

## O que não foi verificado

- O valor de cada célula do RREO contra o texto do PDF. Os PDFs são os mesmos bytes que o portal publica hoje, e a transcrição já tem testes homologados.
- A data dos 8 cancelamentos retroativos, que exigiria coletar a movimentação desses empenhos (8 requisições).
- Empenhos fora das 147 movimentações já coletadas.

## O que isso significa para o painel

- O que o painel mostra de 2016 a 2025 continua igual à fonte hoje.
- Os cortes de 2026 mostram a fonte como estava em 30/09, e a interface já diz isso ("coletado em 30/09/2026"). Para refletir a fonte de hoje, é preciso uma carga nova, no procedimento do README (coletar → validar → processar → testar → portões). A recoleta desta prova está num armazém temporário e **não** foi incorporada ao projeto.

## Arquivos

- `recoletar_tudo.py`: recoleta, no armazém temporário, de tudo o que o banco tem.
- `comparar_fonte.py`: comparações N2, N3 e N4, movimentações, catálogos e PDFs.
- `comparar_tela.py` e `tela_portal/*.json`: empenhos lidos na tela do portal (só número e valores) × banco.
- `comparacao_banco_x_api_20261005.json`: resultado completo, sem nome, documento ou descrição de credor.
- `recoleta_progresso_20261005.jsonl`: cada coleta da recoleta, com snapshot, status e número de requisições.
