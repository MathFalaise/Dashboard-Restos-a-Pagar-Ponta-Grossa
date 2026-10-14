# Conciliação API × RREO, célula a célula (09/10/2026)

Pedido do responsável: fazer **todos** os indicadores de Restos a Pagar do Município baterem com as provas reais
(RREO e Siconfi). Este documento registra até onde isso foi possível, com a evidência de cada item, e o que é
**impossível por construção**. É uma análise somente leitura: nenhuma regra homologada, valor validado ou dado
bruto foi alterado. As regras novas usadas aqui são **propostas experimentais**, não promovidas.

## 1. Resultado em números (104 RREOs gerados pelo sistema Elotech, entidade 1 e consolidado, 2016–2026)

| Etapa | Células iguais ao centavo | Documentos idênticos (12 colunas) |
|---|---|---|
| Regra de produção atual (RREO-COL v1, escopo do catálogo, cópias incluídas) | 533 de 1.248 (42,7%) | 7 |
| + regras propostas (seção 3) | 742 (59,5%) | 22 |
| + itens de conciliação comprovados (seção 4) | **862 (69,1%)** | **33** |

Por exercício, documentos que fecham em todas as colunas:
- **2021:** 14 de 15.
- **2025:** 10 de 12. Os 2 restantes são o RREO do 3º bimestre, que está com defeito (item D1).
- **2020:** 4 de 13.
- **2022:** 4 de 12.
- **Demais anos:** os resíduos estão classificados na seção 5.

**Siconfi, saldo total L:** depois das regras de escopo, bate **ao centavo** em 35 das 64 declarações. Isso inclui
todas as de 2021, quase todas de 2019, 2024 e 2025, e o 1º bimestre de 2026. No 1º bimestre de 2026 batem também
as 12 colunas, contando cada par 1↔15 uma vez só e com o retrato da API mais antigo.

## 2. Por que 100% é impossível (prova)

A API é contínua: o saldo final de cada ano é igual à abertura do ano seguinte, ao centavo, em todos os anos de
2016 a 2025. **Os próprios RREOs não são.** O RREO do 1º bimestre de X+1 abre com valor diferente do que o RREO do
6º bimestre de X fechou:

| Ano X | Fechamento (RREO 6º bim/X) | Abertura (RREO 1º bim/X+1) | Diferença |
|---|---|---|---|
| 2020 (consolidado) | 18.662.407,15 | 18.482.072,33 | −180.334,82 |
| 2022 | 20.003.072,05 | 20.162.657,54 | +159.585,49 |
| 2023 | 20.417.319,97 | 20.465.177,01 | +47.857,04 |
| 2024 | 17.848.930,28 | 18.523.356,29 | +674.426,01 |
| 2025 | 19.374.826,42 | 20.300.529,04 | +925.702,62 |

Nenhum conjunto de dados consistente pode igualar ao mesmo tempo o fechamento e a abertura quando os dois
documentos oficiais se contradizem.

O mesmo vale entre o PDF do portal e o Siconfi, que divergem entre si no mesmo período. Exemplos:
- 2020: R$ 180.334,82 em f;
- 2021: classificação de pagamentos e cancelamentos;
- 2026: R$ 31.813.905,47 dos pares.

O Siconfi também muda as inscrições de um bimestre para outro dentro do mesmo ano (2016, 2017, 2018, 2022, 2025).
**Em todos os casos medidos, a API coincide com o documento mais recente.**

## 3. Regras propostas (experimentais, não promovidas)

| Código proposto | O que faz | Evidência |
|---|---|---|
| Pagamento por categoria (= RREO-COL v2, já existente) | Pagamento de registro só processado vai para c; de registro só não processado, para i | Com ela, os RREOs de 2020–2022 fecham em c e i |
| Cancelamento em registro misto | Primeiro cancela o RP não processado ainda a liquidar (j); o excedente é processado (d) | A API traz um único campo de cancelamento (`canceladoProc` = 0 sempre); 2020 passa a fechar em d e j |
| Escopo: entidade 7 | Inclui a **Agência Reguladora de Águas e Saneamento Básico** (entidade 7) no consolidado até 2020 | Fora do catálogo do portal (`/api/entidades/lista`), mas a API de RP responde. Quatro empenhos parados desde 2018 somam R$ 180.334,82: 2011/163 (9.869,02), 2014/174 (3.390,00), 2016/41 (3.900,00) e 2016/166 (163.175,80). Em 2017 explicam exatamente b 84.524,52, f 13.259,02 e g 178.633,74. O RREO consolidado os inclui em 2017, no 3º bimestre de 2019 e em 2020, e deixa de incluir a partir de 2021. Sondagem das entidades 0 e 2–39 em 2016, 2020 e 2024: nenhuma outra existe |
| Cópias 24xxxxx antes de 2026 | Exclui as cópias (lado A dos pares 1↔15) dos exercícios até 2025 | As cópias foram criadas em 2026 com efeito retroativo. Em 2024 (1 cópia, 8.410,00) e em 2025 (20 cópias, 925.702,62), a diferença API × RREO é exatamente igual a elas. A abertura de 2026 do RREO pula exatamente 925.702,62 |

Uma tentativa de classificar pelos lançamentos da movimentação também foi testada. Ela separa os pagamentos pelo
exercício da liquidação paga.
- **O que validou:** reproduz os campos da API em 7.670 de 7.670 registro×corte.
- **O que não resolveu:** não fecha os casos de pagamento c × i restantes. O relatório do sistema não segue só o
  exercício da liquidação, por exemplo no estorno seguido de nova liquidação.
- **Situação:** fica registrada, não proposta.

## 4. Itens de conciliação comprovados (empenho a empenho)

| Código | Documentos | Efeito (API − RREO) | Evidência |
|---|---|---|---|
| A1 ART-7561 | 1º bim/2024 a 1º bim/2026 | a e d +1.829,50; f e j −1.829,50 (e, k e L não mudam) | Empenho 2011/7561. Movimentação de 29/12/2023: "Cancel: 2" e "Cancel: 3" de 1.829,50 e um único estorno de cancelamento. No RREO defeituoso do 3º bim/2025 os únicos cancelamentos impressos são d −1.829,50 e j +1.829,50. Some a partir do 2º bim/2026 |
| A2 ART-21040 | 6º bim/2023 e todo 2024 | 2023: f −2.951,48. 2024: d +2.951,48, f −2.951,48, h +2.951,48, j −2.951,48 | Empenho 2011/21040, estorno da liquidação 2/2011 e cancelamento em 11/01/2024. O RREO conta o valor estornado também como não processado, em dobro no saldo. O 1º bim/2025 abre sem ele |
| A3 2022 | 5º e 6º bim/2022 | d −151.752,22 | O relatório de 2022 contou como **cancelamento** três estornos de liquidação de 24/10/2022 sem cancelamento: 2019/7079 (142.274,26), 2019/16 (6.715,23) e 2019/8401 (2.762,73). O RREO de 2023 os reabre como não processados (abertura = API). Os cancelamentos reais são de 2023/2024 |
| M1 3586 | 6º bim/2023 e 1º bim/2024 | d −165,00 e +165,00 | Empenho 2014/3586: cancelamento datado de 09/01/2024 contado no RREO de 2023 e ausente do 1º bim/2024 |
| M2 estornos de cancelamento 2023 | 6º bim/2023 | j −47.692,04 | Cancelamentos de 2019/16774 (17.692,04) e 2022/23726 (30.000,00) estornados no 6º bim/2023. Na API o acumulado cai entre os cortes de 31/10 e 31/12; o RREO (29/01/2024) ainda os conta |
| M3 fechamento de 2024 | 6º bim/2024 | d +511.782,00; c −49.768,80; i −1.139.390,69 (L +677.377,49 exato) | 2023/9459: estorno e cancelamento de 511.782,00. Pagamentos estornados de 2023/20463, 21018 e 23301 (1.189.159,49). Todos datados no 6º bim/2024 e ausentes do RREO de 30/01/2025. O 1º bim/2025 abre como a API |
| M4 exclusão sem rastro | 3º e 5º bim/2022 | c −4.074,49 e d −4.074,49 | Empenho 2021/16636: o RREO mostrou um pagamento e depois um cancelamento que **não existem na movimentação**, foram excluídos do sistema. Os RREOs seguintes estão de acordo com a API |
| M5 transitórios de 2024 | 1º bim/2024 | c +25.593,00 | Pagamentos de 2023/4989 (6.916,00), 2023/20196 (17.817,00) e 2023/22008 (860,00), de liquidações de dezembro/2023. Ficaram fora do RREO de março e entraram no de maio |
| D1 RREO defeituoso | 3º bim/2025 (entidade e consolidado) | d e j inteiros | O cancelamento acumulado **cai** de 3.374.389,18 (2º bim) para 1.829,50 (3º bim), o que é impossível. A declaração ao Siconfi do mesmo período tem j = 12.039.633,26, coerente com a API |
| D2 RREO prematuro | 5º bim/2016 | colunas de fluxo | Emitido em 20/09/2016, antes do fim do período (set–out) |
| D3 coluna h de 2016–2017 | RREOs gerados entre ago e dez/2018 | h menor que a soma das liquidações | No próprio PDF i > h (6º bim/2016, 5º e 6º bim/2017), o que a definição do MDF não permite. Não afeta e, k nem L |
| S1 documentos superados | 1º bim/2026 (inscrições); 3º bim/2019 Elotech | b, g e outras | Inscrições de 31/12/2025 refeitas no RREO do 2º bim/2026 (= API). O 3º bim/2019 foi substituído pela declaração ao Siconfi (= API, 0 diferenças). Os RREOs de 2018 e 2019 publicados no portal são impressões do Siconfi (sem rodapé Elotech) |
| 2026 | 2º a 4º bim/2026 | j +1.270.679,25 / +1.251.860,27; h e i | Cancelamentos e estornos com data retroativa, observados entre os nossos retratos de 29/09 e 06/10 (`DIVERGENCIA_2026.md`). Com o primeiro retrato, o 2º bim fecha (só h 644,16) |

## 5. O que sobra (206 células)

Classificação automática dos resíduos depois dos itens. "Explicado" aqui significa ter evidência documental, não
ter o empenho identificado:

| Categoria | Células | Leitura |
|---|---|---|
| Incluído em RREO posterior | 53 | O fluxo aparece num RREO seguinte do mesmo ano e a diferença some. Corresponde a lançamento registrado depois da emissão com data anterior, ou excluído depois. A prova é o documento seguinte; o empenho nem sempre é identificável |
| Classificação c × i e d × j | 50 | Mesmo valor com sinal trocado entre colunas, sem efeito no saldo. São pagamentos de registros mistos que o relatório põe em c e a API em i. Maiores: 2017 (≈ 122 mil), 2020 consolidado (13.097,05), 2024 (5.421,75). Precisa da movimentação de todos os mistos (coleta interrompida em ~870 de 3.695) |
| Inscrição corrigida em outro RREO | 9 | Inscrições do 1º bim/2026 e do 2019 Siconfi refeitas depois |
| Sem explicação ainda | 94 | Concentrados em: 2017 (h e o cancelamento de 95.522,00 do empenho 2014/11805, reaberto depois); 2016 (pagamentos de jan–ago registrados depois de 20/09/2016); 2018–2019 (impressões do Siconfi, outra regra); 2023 (pagamentos de jan–mai, 9.900,80 a 84.228,85); 2026 (alterações antes do primeiro retrato, 29/09) |

## 6. Conclusões que a evidência sustenta

1. **A API é a fonte coerente.** Ela é contínua entre anos, coincide com o documento oficial mais recente em todos
   os casos testados e é reproduzida pela movimentação empenho a empenho.
2. **As diferenças restantes são do lado dos documentos:**
   - lançamentos registrados ou excluídos depois da emissão;
   - artefatos contábeis de empenhos específicos;
   - documentos defeituosos ou superados;
   - escopo (entidade 7, cópias de 2026).
3. **"Bater 100%" com todos os RREOs é matematicamente impossível,** porque eles se contradizem (seção 2).
   Alcançável, e já feito para 2021 e 2025: igualdade ao centavo onde o documento é consistente, e conciliação
   documentada no resto.

## 7. Decisões e próximos passos (do responsável)

> Executado na mesma noite, a pedido do responsável: coleta da entidade 7 e da movimentação, e promoção das regras
> (seção 8).

- **Coletar a entidade 7 no banco ativo,** com backup e homologação. Exige ajustar a visão do Município, que hoje
  só soma o catálogo do portal.
- **Promover ou não as regras experimentais da seção 3** para a visão publicada.
- **Concluir a coleta da movimentação dos 3.695 empenhos mistos** (cerca de 2 h) para fechar a classificação c × i.
- **Pedir ao Município, via e-SIC, a data de registro** (não a data do documento) dos lançamentos listados na seção
  4. Só ela prova o registro posterior empenho a empenho.

Evidência de trabalho, fora do repositório porque contém nomes de pessoas físicas da API: listagens da entidade 7
(64 cortes) e movimentação de cerca de 880 empenhos, com URL, data e SHA-256 em manifestos na pasta de rascunho da
sessão. Para entrar no armazém, devem ser recoletadas pelo coletor do projeto.

## 8. Promoção das quatro regras (09/10/2026, a pedido do responsável)

Pedido: "promova as quatro regras além da coleta das movimentações". Executado no banco ativo, com a mesma disciplina
das correções anteriores.

### 8.1 Proteção e coleta
- **Backup:** `data/backups/20261009-191501_antes-promocao-regras-20261009.sqlite`. Restauração comprovada: cópia
  aberta com `PRAGMA integrity_check` = ok e as mesmas contagens do banco ativo em 8 tabelas.
- **Referências fora do banco:** `referencia_antes_promocao_20261009.json` e `raiz_antes_promocao_20261009.json`
  em `~/RestosAPagar_local/referencias/`.
- **Entidade 7:** 68 cortes (todos os que o banco tem para as demais entidades), pelo coletor do projeto (contrato
  estrito, segunda leitura): 68 `completa`.
- **Movimentação:** 3.812 empenhos com coleta `completa` (antes 148): os 3.695 de classificação mista e os 11
  citados como evidência. Nenhum retrato duplicado. Durante a coleta, dois processos chegaram a rodar ao mesmo tempo
  por alguns minutos; o segundo foi encerrado e `python -m rp verificar` não acusou problema.

### 8.2 Regras (versões novas; nada homologado foi editado)

| Regra | O que faz | Situação |
|---|---|---|
| CANC v2 | Cancelamento de registro com aproc > 0: primeiro o não processado ainda a liquidar (j), o excedente é processado (d) | operacional, compõe o indicador |
| RREO-COL v3 | Pagamento pela categoria (como a v2) + cancelamentos pela CANC v2; calculada no escopo das duas regras abaixo | operacional, compõe o indicador |
| ESCOPO-MUN v1 | Entidade 7 no Município até 2020, a partir do momento em que a base a conhece (faltar um corte dela = Município indisponível, nunca zero) | operacional, compõe o indicador |
| COPIA-ORIGEM v1 | Cópias 24xxxxx fora dos indicadores antes de 2026 (continuam no bruto, na normalização, no pareamento e nas anomalias) | operacional, compõe o indicador |
| MOV-REF v2 | Como a v1, mais o lançamento 33 "Em Liquidação": registro de etapa, efeito zero (achado da coleta: 2 lançamentos; os saldos não mudam neles) | operacional com ressalva (sem conferência externa) |
| RREO-COL v2 | — | supersedida pela v3 |
| MOV-REF v1 | — | supersedida pela v2 |
| RREO-COL v1, CANC v1 | — | continuam não recomendadas e calculadas lado a lado, como histórico |

- **Decisões:** registradas em `regra_situacao` com `decidir-regra`, cada uma com:
  - teste de regressão: `tests/test_promocao_20261009.py`;
  - evidência independente: declarações do Siconfi, evidência externa nº 1 (zip com manifesto, SHA-256
    `4c500a8e…`), exceto na MOV-REF v2;
  - ressalva de cada regra, que aparece na metodologia.
- **A homologação pegou um tipo novo:** a primeira homologação depois da coleta foi **reprovada** pela trava
  `lancamento_desconhecido`, porque a movimentação nova trouxe o tipo 33 ("Em Liquidação"), que a MOV-REF v1 não
  conhecia. O tipo foi analisado (os saldos não mudam no lançamento) e virou a MOV-REF v2. Nenhum valor foi
  ajustado.
- **Derivação (`rp-derivador/3`):**
  - **v1 e v2:** ficam exatamente como eram. A única correção de comportamento é que uma entidade fora do catálogo
    não esconde mais a visão do Município (só não é somada).
  - **v3:** usa o escopo promovido. Duas verificações novas: `cópias 24xxxxx fora do indicador (COPIA-ORIGEM v1)` e
    `entidade fora do catálogo no Município (ESCOPO-MUN v1)`.
- **Painel:**
  - **Somas dos indicadores:** com as regras operacionais, todas excluem as cópias anteriores a 2026 e somam a
    entidade 7 até 2020.
  - **Entidade fora do catálogo nos outros exercícios:** aparece como `fora_do_escopo`, sem ser somada.
  - **Ficha de um empenho:** continua mostrando a cópia, com o aviso de que ela está fora do indicador.
  - **Explicações:** o catálogo de explicações de diferenças recebeu os itens comprovados da seção 4.

### 8.3 Prova de que nada homologado mudou
- **Base homologada de 30/09:** sem as linhas das regras novas, a derivação reproduz exatamente os hashes homologados
  `2f6b4e29…` e `b8a0b2ed…`. O hash completo novo é `adc55b19…` / `96777ec6…`, registrado no teste.
- **Banco ativo:** a derivação atual nova (30, `a839c708…`) contra a anterior (26, `ed386665…`), por identificadores
  estáveis:

| Tabela | Derivação 26 (anterior) | Derivação 30 (nova) | Linhas que sumiram ou mudaram | Linhas novas |
|---|---|---|---|---|
| rp_derivado | 561.357 | 561.671 | 0 | 314 |
| movimentacao_interpretada | 2.352 | 65.847 | 0 | 63.495 |
| anomalia | 28.069 | 28.069 | 0 | 0 |
| espelhamento_par | 3.781 | 3.781 | 0 | 0 |
| visao_valor | 25.440 | 41.220 | 0 | 15.780 |
| conciliacao_rreo | 2.328 | 3.492 | 0 | 1.164 |
| verificacao | 377 | 526 | 0 | 149 |

- **Vigência "como estava em 29/09":** sem as regras novas, `b8a0b2ed2328bf093f3f44d4a51dd70f0063d2c9c827b981520a8f921f142a68` (= homologado `b8a0b2ed…`). Completo:
  `96777ec6a17da54b09812422695b14a9bb0dc89b4d3563a3712f9964ccc699a4`.

### 8.4 Impacto na conciliação com o RREO (documentos transcritos pelo extrator de produção)

| Regra | Entidade 1: colunas iguais | Documentos idênticos | Consolidado: colunas iguais | Documentos idênticos |
|---|---|---|---|---|
| RREO-COL v1 (não recomendada) | 282 de 588 (48,0%) | 7 de 49 | 216 de 576 (37,5%) | 0 de 48 |
| RREO-COL v2 (agora supersedida) | 314 de 588 (53,4%) | 11 de 49 | 264 de 576 (45,8%) | 8 de 48 |
| **RREO-COL v3 (promovida)** | 356 de 588 (60,5%) | 12 de 49 | 343 de 576 (59,5%) | 10 de 48 |

São 97 documentos lidos pelo extrator (49 entidade, 48 consolidado). Com os 18 recusados lidos à parte (seção 1), a v3
reproduz 69,1% das células depois dos itens comprovados da seção 4.

### 8.5 Impacto no indicador publicado (saldo de RP do painel × coluna L do RREO, 31/12)

| Exercício | Escopo | Saldo do painel (S1) | Coluna L do RREO | Diferença | Situação |
|---|---|---|---|---|---|
| 2016 | Município | 33.716.772,93 | — | — | sem RREO transcrito pelo extrator |
| 2016 | entidade 1 | 31.982.018,98 | — | — | sem RREO transcrito pelo extrator |
| 2017 | Município | 17.582.067,07 | 17.486.545,07 | 95.522,00 | explicada |
| 2017 | entidade 1 | 16.536.506,91 | 16.440.984,91 | 95.522,00 | explicada |
| 2018 | Município | 19.157.923,69 | — | — | sem RREO transcrito pelo extrator |
| 2018 | entidade 1 | 18.324.474,11 | — | — | sem RREO transcrito pelo extrator |
| 2019 | Município | 21.675.760,37 | — | — | sem RREO transcrito pelo extrator |
| 2019 | entidade 1 | 20.401.311,24 | — | — | sem RREO transcrito pelo extrator |
| 2020 | Município | 18.662.407,15 | 18.662.407,15 | 0,00 | sem diferença |
| 2020 | entidade 1 | 13.617.360,50 | 13.617.360,50 | 0,00 | sem diferença |
| 2021 | Município | 45.226.754,81 | 45.226.754,81 | 0,00 | sem diferença |
| 2021 | entidade 1 | 17.912.305,36 | 17.912.305,36 | 0,00 | sem diferença |
| 2022 | Município | 23.909.989,24 | 23.750.403,75 | 159.585,49 | parcialmente explicada |
| 2022 | entidade 1 | 20.162.657,54 | 20.003.072,05 | 159.585,49 | parcialmente explicada |
| 2023 | Município | 21.239.560,49 | 21.197.857,45 | 41.703,04 | explicada |
| 2023 | entidade 1 | 20.462.225,53 | 20.417.319,97 | 44.905,56 | explicada |
| 2024 | Município | 18.966.578,99 | 18.296.817,34 | 669.761,65 | parcialmente explicada |
| 2024 | entidade 1 | 18.523.356,29 | 17.848.930,28 | 674.426,01 | explicada |
| 2025 | Município | 20.341.471,66 | 20.341.471,66 | 0,00 | sem diferença |
| 2025 | entidade 1 | 19.374.826,42 | 19.374.826,42 | 0,00 | sem diferença |

- **2016, 2018 e 2019 ("sem RREO transcrito pelo extrator"):** os PDFs desses anos são recusados pelo extrator. Os de
  2018 e 2019 são impressões das declarações do Siconfi.
- **Nuance da entidade 7 em 2018 e 2019:** essas declarações **não** incluem a entidade 7, que o relatório do
  sistema inclui em 2017, no 3º bim/2019 e em 2020. A regra ESCOPO-MUN v1 segue o relatório do sistema, então nesses
  dois anos o Município do painel fica R$ 180.334,82 acima do Siconfi. Uma versão que siga o Siconfi seria uma v2,
  decisão do responsável.
- **Diferenças que restam:** estão explicadas no próprio painel pelo catálogo de explicações (seção 4).
  - **2022:** R$ 7.833,27 sem causa identificada.
  - **2024, Município:** R$ 4.664,36 de outras entidades não atribuídos a empenhos.

### 8.6 Testes e homologação
- **Testes novos:** `tests/test_promocao_20261009.py`, 11 testes. Eles servem de teste de regressão de cada decisão:
  CANC v2, RREO-COL v3, COPIA-ORIGEM v1, ESCOPO-MUN v1 (incluindo a base que não conhece a entidade), MOV-REF v2 e a
  entrada das versões novas no catálogo como experimentais.
- **Testes existentes ajustados:** só onde a promoção muda o que é conferido, com o valor anterior anotado ao lado:
  - **v3 nas contagens:** 24 → 36 comparações por documento (12 colunas × v1/v2/v3), linhas e contagens da qualidade
    e da conciliação, e 2 × 2 → 2 × 3 "RREO sem snapshot";
  - **contrato analítico E-02:** com as duas descrições novas de verificação;
  - **governança:** a CANC v2 existe desde 09/10/2026;
  - **explicações:** os casos de 2024 (674.426,01) passaram de "parcialmente explicada" a "explicada";
  - **hash da base homologada:** o teste continua exigindo `2f6b4e29…` e `b8a0b2ed…` (sem as regras novas) e
    registra os hashes completos novos;
  - **fixture `real`:** passa a sincronizar só as evidências registradas até a data da base homologada, como já
    fazia com os retratos (a evidência do Siconfi é posterior).
- **Suítes:** produção, 650 passed; investigação (Etapa 03), 26 passed.
- **`python -m rp homologar`:** **`aprovada_com_ressalvas`**, 21 de 21 verificações, relatório em
  `~/RestosAPagar_local/referencias/homologacao_pos_promocao_20261009_b.json`.
  - **Pendências contábeis:** divergência com o RREO (v3: 465 colunas em 75 documentos, contra 666 em 90 da v1 e 586
    em 78 da v2), 18 RREOs recusados pelo extrator, pares 1↔15 e VALOR-OBRIG v1 sem decisão.
  - **Primeira tentativa:** foi `reprovada` por dois motivos, ambos tratados: o tipo 33 (MOV-REF v2) e o teste do
    armazém, que contava a primeira evidência externa como se fosse da base homologada.

### 8.7 Para o responsável
- **Reiniciar a interface** (`python -m rp interface`): ela abre a derivação nova (30) com as regras promovidas.
- **Guardar fora deste computador:**
  - a pasta `~/RestosAPagar_local/referencias/`;
  - o backup `data/backups/20261009-191501_antes-promocao-regras-20261009.sqlite`, que já está no OneDrive.
- **Em aberto:**
  - **Decisão da ESCOPO-MUN em 2018 e 2019:** seguir o relatório do sistema (como está) ou o Siconfi.
  - **Perguntas ao e-SIC:**
    - extinção e saldos da entidade 7;
    - natureza das cópias;
    - data de registro dos lançamentos posteriores.
