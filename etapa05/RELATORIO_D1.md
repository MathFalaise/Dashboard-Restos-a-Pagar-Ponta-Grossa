# D1: primeira atualização real da base (06/10/2026)

Carga nova dos cortes de 2026 até 30/09/2026, pelo procedimento da D1 (`CONSOLIDACAO_POS_05.md`, seção 8, opções (a) e (b) juntas). Ramo `carga-d1-2026-09-30`, a partir de `3c16291` (main). Nenhuma tag foi movida.

## O que foi coletado

| Item | Quantidade |
|---|---|
| Catálogos (entidades e exercícios das 10 entidades) | 11 coletas |
| Nova coleta dos cortes de 2026 já existentes (31/01, 28/02, 31/03, 30/04, 30/06, 31/08) | 42 coletas: um segundo retrato de cada corte, e o anterior fica preservado |
| Corte novo de 30/09/2026, para as 10 entidades | 10 coletas |
| Requisições das listagens | 87, com pausa de 1,5 s |

- Todas as 63 coletas terminaram `completa`. As listagens com mais de uma página tiveram segunda leitura idêntica, e todas pediram a ordem (anoempenho, empenho).
- As entidades 3, 6, 9, 10 e 11 estão fora do catálogo de 2026: a API devolveu lista vazia, com observação no manifesto, e o painel as mostra como "entidade inexistente no exercício", como antes.
- **Ficaram de fora:**
  - o corte de 31/12/2026, que só existe para a Prefeitura e vai além de 30/09;
  - o RREO, porque o banco já tem os bimestres 1 a 4 de 2026 e o 5º só sai depois de 31/10;
  - as movimentações.

Um primeiro disparo da coleta falhou antes de qualquer requisição de listagem: a lista de cortes tinha fim de linha `\r`, e o coletor recusou a data. Só os 11 catálogos foram gravados nessa vez. Achado: uma data inválida em `coletar-listagem` sai como erro não tratado (código 1), e não como recusa de parâmetro (código 4). Não afeta dados.

## Procedimento e resultado

| Passo | Resultado |
|---|---|
| 2. Estado antes, `verificar`, `portoes` | `d1_estado_antes.json`; verificar sem problemas; portões aptos |
| 3. Referência do bruto e backup | `etapa04/resultados/referencia_20261006.json` (536 respostas); `backups/20261006-102052_antes-carga-20261006.sqlite` |
| 4. Coleta | acima |
| 5. Validar | `verificar` sem problemas; comparação pelo bruto de cada retrato novo com o anterior (abaixo) |
| 6. Processar | normalização 14, derivação atual 25, `hash_resultado` **`b6f80d879ee89d5f17c42de25c6ff3c030b5c7d238a1235035b6b18f23e1802f`** |
| 7. Testes | **482 de produção e 26 da investigação, todos passando** (`d1_testes_producao.txt`, `d1_testes_investigacao.txt`) |
| 8. Portões com a referência | **apto**; os 13 portões verificáveis aprovados, inclusive `camada_bruta_preservada` (as 466 coletas e as respostas anteriores à carga continuam idênticas) |
| 9. Estado depois e comparação | `d1_estado_depois.json`, `d1_comparacao.json` |

O `hash_resultado` da derivação atual mudou, como a D1 prevê, porque a derivação passa a usar os retratos novos. As derivações anteriores (21 a 24), com os hashes homologados `2f6b4e29…` (atual em 30/09) e `b8a0b2ed…` ("como estava em" 29/09), continuam no banco intactas.

## O que mudou na fonte, retrato novo × anterior

36 dos 42 cortes recoletados estão idênticos, registro a registro. Os 6 que mudaram são todos da Prefeitura, e o número de registros é o mesmo, 4.557:

| Corte | Registros alterados | Campos |
|---|---|---|
| 31/01, 28/02, 31/03 | 2 | nome do credor (cadastro, sem valor) |
| 30/04 | 10 | cancelamento de não processado (8) e nome (2) |
| 30/06 | 10 | cancelamento (8), liquidação, pagamento e retenção (2) e nome (2) |
| 31/08 | 12 | cancelamento (8), pagamento (6), liquidação e retenção (4) e nome (2) |

São as mesmas diferenças que a prova real de 05/10 encontrou (`auditoria/prova_real/RELATORIO_PROVA_REAL.md`). A principal é um cancelamento de R$ 1.270.679,25 em 8 empenhos de 2025, lançado depois de 30/09 com data até 30/04/2026.

## Efeito no painel (Município, entidades somadas)

| Corte | Saldo total antes | Saldo total depois | Diferença |
|---|---:|---:|---:|
| 30/04/2026 | 104.135.295,67 | 102.864.616,42 | −1.270.679,25 |
| 30/06/2026 | 92.215.682,08 | 91.019.166,83 | −1.196.515,25 |
| 31/08/2026 | 80.844.090,29 | 79.906.319,12 | −937.771,17 |
| **30/09/2026 (novo)** | — | **78.652.156,06** | — |

Corte novo de 30/09/2026 (Município):
- inscrição R$ 205.341.874,51;
- pagamentos R$ 117.086.594,95;
- cancelamentos R$ 9.603.123,50;
- saldo R$ 78.652.156,06, sendo R$ 61.856.125,90 a liquidar e R$ 16.796.030,16 liquidados a pagar.

A comparação de estados (5.575 valores de tela) confirma:
- **nenhum valor de 2016 a 2025 mudou**, e nenhuma página perdeu identificadores;
- 164 valores do painel e 155 de tela mudaram, todos nos cortes de 30/04, 30/06 e 31/08/2026;
- 300 textos são do corte novo de 30/09.

**Conciliação com o RREO:** nos cortes de 30/04, 30/06 e 31/08/2026, 1 a 3 colunas a mais passaram a ter diferença, e 20 linhas foram de "sem diferença" para "não determinada". É efeito esperado: os RREOs desses bimestres foram publicados antes dos lançamentos retroativos que a API agora mostra. A divergência nunca altera o valor da API.

**Anomalias:** de 19.684 para 24.828. As anomalias são registradas por retrato, e cada retrato novo de um corte repete as suas (por exemplo, `COPIA-24`, 731 por retrato de 2026). As que contam como vigentes estão na tela de qualidade.

## Mudança nos testes

Os testes de casos reais montavam um banco temporário com o armazém inteiro e exigiam o hash homologado. Com snapshots novos no armazém, esse hash muda e os testes falhariam sem erro de fato. A montagem (`app/tests/conftest.py`, fixture `real`) passou a registrar só os **466 snapshots da base homologada**, os coletados até 30/09/2026 01:27:56 (`BASE_HOMOLOGADA_ATE`).

`test_armazem_real_intacto_e_integro` passou a exigir duas coisas: os 466 registrados e íntegros, e, como única diferença no `verificar`, os manifestos posteriores à base. Nenhum valor esperado mudou, e nenhum teste foi apagado. A carga nova é validada pelos portões, como manda o procedimento.

## Pendências

- A interface não estava rodando: ao abrir `python -m rp interface`, ela já lê a derivação 25.
- Os snapshots novos estão em `snapshots/` (armazém do projeto), mas não foram commitados. O repositório é público e o bruto tem dados de credores: a decisão de privacidade ainda está pendente.
