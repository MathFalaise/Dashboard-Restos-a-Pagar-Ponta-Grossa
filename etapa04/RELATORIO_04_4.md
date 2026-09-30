# Relatório da Subetapa 04.4 — carga histórica, 2024, conciliação com o RREO e comparador de snapshots

Data: 30/09/2026.

Detalhe por lote (portões, hashes, perfil, anomalias): `etapa04/lotes/LOTE_{A,R,C,D,E,F,M,T}.md` e `.json`.
Matrizes e análises (todas somente leitura): `lotes/conciliacao_2024_2026.md`, `lotes/consistencia_rreo.md`, `lotes/hipotese_canc_2020_2026.md`, `lotes/rreo_layout_antigo.md`.

**Resumo:**
- 8 lotes, todos com **todos os portões OK**. Nenhum lote parou.
- Os 7 backups (~743 MB) estão intactos e protegidos por `PRESERVAR.txt`.
- Nenhuma regra foi promovida, alterada ou criada. Nenhum snapshot foi sobrescrito.

---

## 1. O que foi coletado

**222 snapshots novos** (260 respostas HTTP, 96.762.200 bytes originais), distribuídos assim:
- 184 listagens de RP;
- 15 PDFs de RREO;
- 10 listagens de publicações;
- 5 catálogos de exercícios;
- 1 catálogo de entidades;
- 7 movimentações.

| Lote | Conteúdo | Snapshots | Registros | Bytes brutos | Hash atual | Hash "como estava em 29/09" |
|---|---|--:|--:|--:|---|---|
| A | 2024, entidades 1 e 15 + RREO 2024 6º bim | 5 | 6.004 | 4.585.086 | 246cfa5a53d96586 | b8a0b2ed2328bf09 |
| R | cortes que faltavam para os 21 RREOs armazenados (2024, 2025, 2026) | 74 | 24.239 | 17.854.559 | 188e4cc24bb19b71 | b8a0b2ed2328bf09 |
| C | 2022–2023 + catálogos das entidades 3/6/9/10/11 + RREO | 32 | 10.074 | 8.983.381 | 065fa3114443071a | b8a0b2ed2328bf09 |
| D | 2020–2021 + RREO | 26 | 12.327 | 9.191.385 | 134c029ba12e31b4 | b8a0b2ed2328bf09 |
| E | 2018–2019 + RREO | 23 | 13.630 | 9.763.006 | 0b866acf4bdc75b7 | b8a0b2ed2328bf09 |
| F | 2016–2017 + RREO (+ RREO 2019) | 27 | 16.456 | 11.926.168 | 88f1de281da27c25 | b8a0b2ed2328bf09 |
| T | recoleta temporal de 28 cortes | 28 | 46.960 | 34.368.074 | b9db914845573482 | b8a0b2ed2328bf09 |
| M | movimentação de 7 registros localizados | 7 | (333 lançamentos) | 90.541 | 2f6b4e295ce79593 | b8a0b2ed2328bf09 |

**Ajustes de plano, com justificativa:**
- **Lote B absorvido pelo R.** O R foi definido como "todo corte que falta para conciliar os RREOs armazenados". Depois do Lote A, o RREO consolidado de 2024 estava no banco, então os 8 cortes de 2024 das demais entidades entraram no R, com os mesmos portões.
- Os catálogos das entidades 3/6/9/10/11 passaram para o Lote C.
- **Lote M** (movimentação) foi criado para localizar registros.
- O **Lote F** recoletou o RREO de 2019 que o filtro do coletor tinha pulado (§15).
- **Regra fixada antes dos Lotes C–F:** combinação entidade×exercício fora do catálogo oficial é consultada e relatada, mas não entra no G1. Todas devolveram 0 registros:
  - entidade 15 em 2016–2018;
  - entidade 10 em 2023, 2025 e 2026;
  - entidades 3/6/9/11 em 2026.

## 2. Exercícios

- 2016–2024 carregados pela primeira vez (corte 31/12, `dataInicial` = 01/01, sem `tipoPesquisa`).
- 2025: cortes bimestrais completados (28/02, 30/04, 30/06, 31/08, 31/10) para as 10 entidades.
- 2026: 28/02 e 30/06 completados para as 10 entidades.

## 3. Entidades

- As 5 da carga (1, 4, 5, 8, 15) e as 5 que completam o Município no catálogo de entidades (3, 6, 9, 10, 11). Sem todas as 10 não existe visão do Município (`derivar._visoes`).
- Catálogos oficiais de exercícios:
  - 1, 4, 5, 8: 2016–2026;
  - 15: 2019–2026;
  - 3, 6, 9, 11: 2016–2025;
  - 10: 2016–2022.

## 4. Snapshots

- **466 no banco = 244 anteriores + 222 da 04.4.**
- Os 244 anteriores foram conferidos contra o backup de 30/09 00:23: todos presentes; nenhum id faltando entre 1 e 466.
- Os 13 gatilhos de imutabilidade estão ativos.
- Armazém: 841 arquivos, 12,7 MB.
- Integridade armazém × banco: sem problemas depois de cada lote (G2, G2b, G2c).
- Hash da camada 0 ao final: `3fe902f65a54cfb4`.

## 5. Registros

A normalização 12 tem 228.873 registros de RP. Registros por exercício (retrato vigente, corte 31/12, 10 entidades):

| 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* |
|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 7.774 | 8.682 | 6.821 | 6.809 | 7.913 | 4.414 | 4.375 | 5.699 | 6.427 | 5.878 | 4.557 |

\* 2026 só da entidade 1.

**Diferenças de formato em relação a 2025/2026:**
- 2016–2020 têm 166–179 registros com programática de 27 dígitos (os demais têm 28).
- Mais registros sem as chaves opcionais de classificação (675–1.770 por ano, contra 48 em 2025).
- Nenhuma chave desconhecida, nenhuma chave-base ausente (G3), nenhuma anomalia estrutural: CHAVE-DUP, ANOEMP-FUTURO, DESCONTINUIDADE, COPIA-SEM-PAR, PAR-EXECUCAO-DOIS-LADOS e CANCPROC-NZ = 0 em 2016–2026.
- Continuidade fechamento→abertura: 100 pares entidade×ano, 0 falhas.

## 6. Testes

- Em **cada um dos 8 lotes**: produção 75 → **76 passed**; investigação **26 passed**.
- Os 61 testes de produção anteriores continuam no portão.
- A 04.4 acrescentou 15 testes em `app/tests/test_comparador.py`:
  - **dado real (3):** snapshots idênticos; cortes diferentes recusados; a comparação não altera o banco (`total_changes` e hash da camada 0);
  - **SINTÉTICOS (8, marcados no código):** registro novo; removido; 500.000,00 → 300.000,00 (−200.000,00); mudança não monetária; vários campos + classificação; lado espelhado; momentos diferentes sem alterar os originais; recoleta com os mesmos parâmetros;
  - **outros (4):** recoleta recusa corte fora da regra; filtro de bimestre; filtro com rótulo em caixa alta (novo, §15); retenção nunca apaga backup preservado.

## 7. Resultados de 2024

Detalhe no Lote A. O RREO de 2024 (entidade 1, emitido 30/01/2025) **não** é reproduzido: ΔL = +682.836,01 em v2 (+746.315,10 em v1). Decomposição, sem forçar nada:

- **+674.426,01: diferença entre as duas publicações oficiais.** O RREO 2024 fecha em 17.848.930,28. A abertura de "exercícios anteriores" do RREO 2025 é 18.523.356,29. A API reproduz a abertura de 2025, não o fechamento de 2024.
- **+8.410,00: a cópia 2401751/2023**, ausente do RREO. Ver §13.
- **+511.782,00 de cancelamento: 2023/9459.** Estorno de liquidação e cancelamento datados de **31/12/2024**, ausentes do RREO emitido um mês depois.
- **2.951,48: 2011/21040.** Estorno de liquidação de 11/01/2024. O RREO de 2022 (emitido antes) o trata como processado; os de 2023 e 2024 (emitidos depois) como não processado, e somam o valor em (a) e em (f).
- 1.829,50 em (a), o mesmo valor que aparece em 2025. Nenhum registro tem esse valor: NÃO DETERMINADO.

**Entidades 1 e 15 em 2024:** um só par espelhado, relação "outra", execução só em B. Nenhuma CONS-PAR o consolida.

## 8. Conciliações com o RREO

Os 21 PDFs armazenados de 2024–2026 têm agora corte completo da API, mais 2017, 2020, 2021, 2022 e 2023 (extraídos) e 2018/2019 (leitura de investigação).

**Conciliações exatas ou quase:**
- **2021, entidade 1: 12/12 colunas iguais**, em v1 e em v2.
- 2021 consolidado (v2): L igual; só (d)/(j) ±757,56.
- 2020 entidade (v2): L igual; só (d)/(j) ±249.027,59.
- 2018 consolidado (v2): L +3.052,00.
- 2026 2º bim: só (h) +644,16.
- 2025 6º bim com RREO-COL v2 + CONS-PAR v2: L igual; só a troca de 1.829,50.

Nenhum outro PDF fecha nas 12 colunas.

**Coerência entre as próprias publicações** — o L de A contra o (a)+(f) de A+1 (`consistencia_rreo.md`):

| | 17→18 | 18→19 | 19→20 | 20→21 | 21→22 | 22→23 | 23→24 | 24→25 | 25→26 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| entidade 1 | — | — | — | **0,00** | **0,00** | 162.536,97 | 47.857,04 | 674.426,01 | 925.702,62 |
| consolidado | −84.812,82 | 3.101,49 | 274.434,78 | −180.334,82 | **0,00** | 162.536,97 | 44.654,52 | 669.761,65 | 925.702,62 |

**Achado principal:**
- A API reproduz o RREO onde as publicações são coerentes entre si (2020→2022).
- Quase sempre ela reproduz a abertura publicada no ano **seguinte**. As exceções são 2.951,48 (21040), 8.410,00 (cópia), 49,49 (2019) e 180.334,82 (2020, consolidado).
- A API mostra o estado **atual** da base contábil. Cada RREO é um retrato do momento em que foi emitido.

## 9. Diferenças: classificação

| Classe | Casos | Status |
|---|---|---|
| **T — lançamento com data retroativa, feito depois da emissão** | 2024 6º bim (674.426,01; 2023/9459 localizado); 2025 3º bim, j +4.184.895,81 (ent. 1) e +11.964.345,35 (consolidado), que o 4º bim já inclui; 2026 1º bim, b +11.158.739,30 e g −3.290.752,98, que o 2º bim já inclui; saltos entre publicações de 2017–2024 | FORTE EVIDÊNCIA no agregado; registros localizados só em parte |
| **C — cópias 24xxxxx ausentes do RREO** | 2024: 8.410,00; 2025: 925.702,62 em todos os 6 bimestres; presentes a partir do RREO de 2026 (Δ 25→26 = 925.702,62) | CONFIRMADO pelo valor |
| **R — reclassificação por estado na emissão** | 2011/21040 (2.951,48 nas aberturas de 2023/2024) | FORTE EVIDÊNCIA (1 registro, 3 RREOs coerentes) |
| R | 1.829,50 (2024–2026 1º bim); 3.972,66 (2024) | NÃO DETERMINADO |
| **P — regra de pagamento** | c −462,00 / i −2.554,25 (2025); c/i em 2017, 2018, 2019, 2020, 2021 | v2 elimina ou reduz em todos os anos |
| **CANC — divisão do cancelamento de registro "ambos"** | fecha (j) ao centavo em 2018–2021 e (d) em 2020–2021; piora (j) em 2022 e 2023 | HIPÓTESE com evidência mista (§14) |
| E — entidade 5, 1485/2025 | c +3.692,25 (2026, consolidado) | HIPÓTESE (1 caso) |
| Não explicadas | h/i 2026 3º/4º bim (−345.479,56 / −237.678,75); 2017 h +1.065.159,06; 2020 f −180.334,82 (outra entidade, PDF sem detalhe por órgão) | NÃO DETERMINADO |

Nenhuma regra foi criada para "fechar" essas diferenças.

## 10. Mudanças temporais

- **Recoleta (Lote T):** 28 cortes coletados em 29/09 (20:11–20:34) foram recoletados em 30/09 (01:19–01:22) com parâmetros idênticos. **Todos idênticos byte a byte.**
  - O intervalo foi de só ~5 h, de madrugada; o teste de vários dias ainda não foi feito.
  - Todos os retratos anteriores foram preservados. Cada recoleta aponta o snapshot de origem.
- **Evidência de mudança real na base**, vista pelas publicações (§8) e por lançamentos datados (Lote M):
  - lançamentos com data no passado aparecem depois da emissão;
  - cópias criadas depois aparecem **retroativamente** nos cortes históricos: 2401751 aparece com 8.410,00 já em 2024, valor que o original só atingiu em out/2025.
  - Uma consulta histórica feita hoje não é o que se via na época.
- **Teste espaçado** (sem agendamento; rodar manualmente daqui a alguns dias):
  ```bash
  python executar_lote.py T 2026-10-07T00:00:00-03:00
  ```
  O comando recoleta todo corte coletado antes da data e grava `LOTE_T_<carimbo>.md`, sem sobrescrever relatório de lote.

## 11. Comparador de snapshots

Implementação: `app/rp/comparador.py`, somente leitura.
- Recusa comparar cortes diferentes.
- Relata: novos, removidos, comuns, alterados; campo a campo; grupos (inscrição processada e não processada, pagamentos, estornos, cancelamentos, liquidações, retenções); classificação e saldos derivados; espelhamento.

Uso na linha de comando:
```bash
python -m rp comparar --a <uid> --b <uid>
```

Resultados em dado real:
- 28 comparações do Lote T, todas sem diferença.
- Nenhum corte do banco tem dois retratos diferentes.

**Limitação:** comparação com mudança **real** ainda não foi exercitada. Essa parte está coberta só pelos 8 testes sintéticos (§6). A garantia de não alteração é testada em dado real.

## 12. Impacto financeiro

- **Entre snapshots (Lote T):** 0,00 em todos os grupos e em S1, nos 28 cortes.
- **Entre publicações oficiais** (o que mudou na base depois de cada emissão, segundo o próprio Município), por exemplo:
  - entidade 1: saldo de RP de 2023 e anteriores, de 17.848.930,28 (RREO 2024) para 18.523.356,29 (RREO 2025) = **+674.426,01**;
  - consolidado, 2025→2026: de 20.341.471,66 para 21.267.174,28 = **+925.702,62** (as 20 cópias);
  - consolidado, 2020→2021: de 18.662.407,15 para 18.482.072,33 = **−180.334,82**.
- A causa só é afirmada onde há registro e data; o restante está marcado como não determinado.

## 13. Pares espelhados

| Corte | Pares | Relação (A = entidade 1, cópia; B = entidade 15) | Execução |
|---|--:|---|---|
| 2024-12-31 | 1 | outra | B |
| 2025, 28/02 → 31/12 | 20 | "A = saldo final de B" sobe de 2 para 9; 11 iguais; "outra" cai de 7 para 0 | B ou nenhuma |
| 2026, 28/02 → 31/08 | 731 | todos iguais | nenhuma → A (356 em abril, 530 em junho, 562 em agosto); nunca B |

- As 731 cópias são 1 de anoempenho 2023, 19 de 2024 e 711 de 2025. Nenhuma aparece em corte anterior a 2024.
- **Caso rastreado (2401751 × 15/1751):** a cópia vale 8.410,00 = saldo de B a partir de 31/10/2025, e aparece com esse valor em todos os cortes desde 2024.
- Os dois lados continuam explícitos. Nenhum foi presumido descartável.
- A natureza das cópias (duplicidade ou transferência de responsabilidade) continua **NÃO DETERMINADA**: é pergunta para o e-SIC.

## 14. Regras experimentais

Nenhuma foi promovida, alterada ou criada.

| Regra | Evidência da 04.4 | Confiança |
|---|---|---|
| RREO-COL v1 (estável) | L ≠ ΣS1 (em 2024 excede em 63.479,09); deixa diferenças c/i em 2017–2025 | **diminuiu** |
| RREO-COL v2 (experimental) | L = ΣS1 = abertura oficial seguinte; elimina ou reduz c/i em todos os anos com RREO | **aumentou** |
| CONS-PAR v1 | nunca fecha 2025; em 2026 quebra (o RREO conta os dois lados) | **diminuiu** como explicação do RREO |
| CONS-PAR v2 | fecha 2025 só em 31/12; nos cortes intermediários sobram 274–369 mil (a relação é avaliada no corte); em 2026 quebra | **diminuiu**. A hipótese temporal (cópias inseridas depois) explica o mesmo de forma mais simples |
| PAR-24 | todas as cópias pareadas, 2024–2026 | inalterada (alta) |

As CONS-PAR continuam como visão analítica; o RREO não serve para validá-las.

**Candidatas registradas e NÃO criadas** (cada uma exigiria versão nova, por decisão sua):
- CANC v2: o excedente de cancelamento sobre o aproc vai para (d). A evidência é mista (§9).
- CONS-PAR v3: "saldo final de B" como saldo no fechamento do exercício.
- Leitura "RREO classifica pelo estado na emissão": só documentação, não regra.

## 15. Limitações

- **Coletor:** o filtro de bimestre diferenciava maiúsculas ("6º BIMESTRE" em 2019) e pulou o PDF sem erro. Corrigido entre os Lotes E e F, com teste. É correção de defeito, não de regra; a identidade do coletor muda com o hash do código.
- **Extrator de RREO** (`rp-rreo-coordenadas/1`): não lê 2016, 2018 e 2019. Isso fica registrado na normalização.
  - 2018 e 2019 foram lidos por um script de **investigação** que confere as identidades e/k/L.
  - 2016 foi **recusado** por essa conferência.
  - Um extrator novo seria versão nova, para decidir depois.
- Os consolidados antigos não detalham por órgão, então não dá para atribuir a diferença a uma entidade (2020).
- A data de um lançamento na movimentação não prova quando ele foi registrado. "Lançado depois da emissão" é inferência pela ausência no RREO.
- Teste temporal de só ~5 h; comparador sem caso real de mudança (§11).
- Pendentes de e-SIC: natureza das cópias, datas de registro, critério de classificação do RREO.
- Espaço local: banco 120,5 MB; 7 backups preservados (743 MB); 3 da retenção (690 MB); tudo fora do OneDrive.

## 16. Recomendações (para sua decisão; a 04.5 não foi iniciada)

1. **Backups:** as cinco condições da seção 12 da especificação estão atendidas no sentido de "validado e explicado":
   - carga histórica: portões OK;
   - 2024: analisado;
   - RREOs: conciliados ou explicados — **não** iguais;
   - comparador: testado;
   - integridade: confirmada.

   A exclusão dos 7 backups continua sendo decisão sua. Para liberar, é só tirar os nomes de `PRESERVAR.txt`.
2. Acrescentar ao e-SIC:
   - (a) se lançamentos com data retroativa são feitos depois do fechamento, e até quando;
   - (b) quando e por que foram criados os empenhos 24xxxxx da entidade 1;
   - (c) como o RREO classifica RP com liquidação estornada.
3. Rodar o teste temporal espaçado (§10) antes de qualquer decisão que dependa da estabilidade da série histórica.
4. Decidir se as candidatas CANC v2 e CONS-PAR v3 entram como versões experimentais, e se RREO-COL v2 passa a padrão.
5. Tratar toda série anterior à data da coleta como "estado atual da base, com data no passado", não como "o que se sabia na época".

SUBETAPA 04.4 CONCLUÍDA — AGUARDANDO APROVAÇÃO PARA A 04.5.
