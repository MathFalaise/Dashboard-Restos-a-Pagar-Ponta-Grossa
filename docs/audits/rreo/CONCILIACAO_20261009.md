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

- **Coletar a entidade 7 no banco ativo,** com backup e homologação. Exige ajustar a visão do Município, que hoje
  só soma o catálogo do portal.
- **Promover ou não as regras experimentais da seção 3** para a visão publicada.
- **Concluir a coleta da movimentação dos 3.695 empenhos mistos** (cerca de 2 h) para fechar a classificação c × i.
- **Pedir ao Município, via e-SIC, a data de registro** (não a data do documento) dos lançamentos listados na seção
  4. Só ela prova o registro posterior empenho a empenho.

Evidência de trabalho, fora do repositório porque contém nomes de pessoas físicas da API: listagens da entidade 7
(64 cortes) e movimentação de cerca de 880 empenhos, com URL, data e SHA-256 em manifestos na pasta de rascunho da
sessão. Para entrar no armazém, devem ser recoletadas pelo coletor do projeto.
