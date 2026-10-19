# Nota técnica: por que os Restos a Pagar inscritos em 2025 subiram 53,2%

Data: 15/10/2026. Escopo: Poder Executivo de Ponta Grossa (entidades do Portal da Transparência; a Câmara Municipal
fica fora). Somente leitura: nada foi alterado no banco, nas regras ou nos valores homologados.

Números reproduzíveis com:

```bash
python docs/audits/rreo/nota_rp_2025.py --banco ~/RestosAPagar_local/banco/restos_a_pagar.sqlite --saida-json docs/audits/rreo/NOTA_RP_2025.json
```

## Resposta curta

- **O aumento é concentrado, não generalizado.** Dos R$ 89,0 milhões a mais em RP novos:
  - 71,5% são obras de transporte financiadas pelo FINISA IV (operação de crédito com a Caixa);
  - 25,1% são despesa de pessoal empenhada em dezembro de 2024.
- **Eleições:** os dados mostram coincidência com o último ano do mandato, não uma causa eleitoral.
  - Mostram também caixa insuficiente em fontes vinculadas em 31/12/2024, ponto que o art. 42 da LRF manda examinar.
  - Quem julga o cumprimento é o TCE-PR; o parecer dele não foi consultado.

## 1. Fontes

| | Fonte | Onde está |
|---|---|---|
| F1 | Listagem de Restos a Pagar da API do Portal (Elotech), retratos de 31/12 de cada exercício, com SHA-256 conferido | banco ativo, normalização 18 (fora do repositório: a listagem traz nomes de pessoas físicas) |
| F2 | Declarações do RREO Anexo 07 ao Siconfi, leitura de 13/10/2026 | `docs/audits/rreo/siconfi/raw/coleta_20261013-223143/` |
| F3 | RGF Anexo 5 (Disponibilidade de Caixa e Restos a Pagar), 3º quadrimestre de 2020, 2023 e 2024, Poder Executivo, API do Siconfi | `docs/audits/rreo/rgf/raw_20261015/` (manifesto com URL e SHA-256) |
| F4 | Lei Municipal 14.545, de 20/12/2022: autoriza até R$ 200 milhões no programa FINISA | [base de leis da Câmara](https://www.legislador.com.br/LegisladorWEB.ASP?WCI=LeiTexto&ID=9&inEspecieLei=1&nrLei=14545&aaLei=2022) |
| F5 | Lei Complementar 101/2000 (LRF), art. 42 | texto legal |
| F6 | Resultado das eleições municipais de 2024 | [O Povo, 29/10/2024](https://www.opovo.com.br/noticias/politica/2024/10/29/eleicoes-2024-727-mulheres-foram-eleitas-prefeitas-sendo-2-em-capitais.html); [Poder360](https://www.poder360.com.br/poder-eleicoes/ponta-grossa-tera-2o-turno-entre-mabel-canto-e-elizabeth-schmidt/) |
| F7 | Série de inscrições desde 2016 | `docs/audits/rreo/RP_2024_2026.md`, seção 4 |

## 2. O aumento, conferido em três fontes

| | Exercício 2024 | Exercício 2025 | Variação |
|---|---:|---:|---:|
| RP inscritos em 01/01 (F1) | 162.898.581,67 | 249.625.355,11 | +86.726.773,44 (+53,2%) |
| Declaração ao Siconfi, 1º bimestre (F2) | 162.898.581,67 | 249.625.355,11 | iguais ao centavo |
| De anos anteriores (colunas a+f) | 21.239.560,49 | 18.966.578,99 | −2.272.981,50 |
| Novos, inscritos em 31/12 do ano anterior (colunas b+g) | 141.659.021,18 | 230.658.776,12 | +88.999.754,94 |

**Conferência com o RGF de 31/12/2024 (F3):**
- **RP não processados do exercício:** R$ 205.182.902,53, igual ao centavo à API.
- **Processados:** R$ 25.476.570,50 no RGF e R$ 25.475.873,59 na API. A diferença, de R$ 696,91, tem o mesmo valor do
  único RP da Câmara Municipal (`RP_2024_2026.md`, D3).

O aumento todo vem dos RP inscritos em 31/12/2024, isto é, das despesas do último ano do mandato 2021–2024.

## 3. O que compõe o aumento dos RP novos

| Componente | Empenhos de 2023 (inscritos em 2024) | Empenhos de 2024 (inscritos em 2025) | Variação | Parte do aumento |
|---|---:|---:|---:|---:|
| FINISA IV, fonte 632 (operação de crédito) | 0,00 | 63.609.959,06 | +63.609.959,06 | 71,5% |
| Pessoal e encargos (natureza 31) | 9.741.501,59 | 32.056.975,05 | +22.315.473,46 | 25,1% |
| Demais despesas | 131.917.519,59 | 134.991.842,01 | +3.074.322,42 | 3,5% |
| Total | 141.659.021,18 | 230.658.776,12 | +88.999.754,94 | 100% |

**FINISA IV (F1, F3, F4):**
- **Obras:** obras de transporte (função 26), quase todas na natureza 449051, "obras e instalações".
- **Três maiores empenhos:** emitidos em 10/07/2024, somando R$ 39.552.449,04:
  - 11696/2024: R$ 13.364.188,84;
  - 11698/2024: R$ 13.286.955,60;
  - 11697/2024: R$ 12.901.304,60.
- **Situação em 31/12/2024:** 98% dos R$ 63,6 milhões estavam não processados (obra ainda não medida).
- **Em 2025:** pagos R$ 55.009.270,60; cancelados R$ 8.578.232,42.
- **Conferência com o RGF:** os RP não processados da linha "Recursos de Operações de Crédito" (R$ 64.973.420,29) são
  iguais ao centavo à soma das fontes 632 (FINISA IV) e 629 (Finisa); os processados (R$ 1.177.508,58) são iguais aos
  da fonte 632.
- **Autorização:** a Lei 14.545/2022 autoriza até R$ 200 milhões no programa FINISA, para pavimentação e
  infraestrutura. Não foi confirmado que esse é o contrato registrado como "FINISA IV".

**Pessoal (F1):**
- **Maior parcela:** 10 empenhos de vencimentos da Prefeitura, emitidos entre 12 e 27/12/2024, na fonte 101
  (Fundeb), com R$ 11.864.709,88 inscritos, dos quais R$ 11.858.085,93 já liquidados (processados).
- **Pagamento:** nada foi pago até 31/08/2025; os R$ 11.858.085,93 foram pagos entre 31/08 e 31/10/2025, de 8 a 10
  meses depois.
- **Natureza:** os dados não mostram que tipo de pagamento de pessoal é esse.

**Sem esses dois fatores (conta ilustrativa, não uma nova série):**
- sem o FINISA IV, a inscrição subiria 14,2%;
- sem também a folha de dezembro do Fundeb, subiria 6,9%.

## 4. Relação com as eleições

**Fatos:**
- 2024 foi o último ano do mandato 2021–2024.
- A eleição teve 1º turno em 06/10/2024 e 2º turno em 27/10/2024; a prefeita, candidata à reeleição, foi reeleita
  com 53,72% dos votos válidos (F6).
- **Art. 42 da LRF (F5):** nos últimos dois quadrimestres do mandato (01/05 a 31/12/2024), o titular do Poder não pode
  contrair despesa que não possa ser paga dentro do mandato, nem deixar parcelas para o exercício seguinte sem caixa
  suficiente. O entendimento predominante dos tribunais de contas é que a regra vale também em caso de reeleição.

**O que aponta para o calendário eleitoral:**
- 90,3% dos RP novos de 2025 (R$ 208.188.329,28) foram empenhados entre maio e dezembro de 2024 (F1).
- As três grandes obras do FINISA foram empenhadas em 10/07/2024, três meses antes da eleição.
- O RGF de 31/12/2024 (F3) mostra caixa negativo depois dos RP em fontes vinculadas:

| Fonte (RGF Anexo 5, 3º quadrimestre de 2024) | Caixa bruto | RP não processados do exercício | Caixa líquido depois dos RP |
|---|---:|---:|---:|
| Operações de crédito | 6.040.833,53 | 64.973.420,29 | −60.753.293,70 |
| Demais vinculações legais | 60.611.075,06 | 79.790.528,63 | −29.170.526,41 |
| Transferências do FUNDEB | 2.831.741,78 | 2.139.205,97 (mais 16.491.078,04 já liquidados) | −16.252.519,48 |
| Educação (total vinculado) | 11.538.027,99 | 5.341.265,16 | −11.425.833,97 |
| Convênios | 9.582.309,39 | 12.930.661,04 | −6.599.785,91 |
| Recursos não vinculados | 133.222.983,00 | 90.142.176,84 | +30.004.850,99 |
| Total do Executivo | 285.562.787,39 | 205.182.902,53 | +26.088.931,76 |

**O que não aponta para efeito eleitoral:**
- **Empenhar no fim do ano é rotina.** A parcela dos RP novos empenhada de maio a dezembro foi de 90,5% em 2021 e 94,5%
  em 2022, anos sem eleição; nos anos eleitorais anteriores, 81,5% em 2016 e 84,0% em 2020 (F1).
- **Eleições anteriores sem salto:** a inscrição subiu 4,7% em 2017 e 2,6% em 2021, depois dos anos eleitorais. A outra
  alta acima de 50% (+51,2%) foi em 2019, depois de um ano sem eleição (F7).
- **Programa anterior ao ano eleitoral:** o salto se concentra num investimento financiado, autorizado em dezembro de
  2022 (F4). Nesse tipo de empréstimo, o banco libera o dinheiro conforme a obra é medida; por isso o caixa da fonte
  costuma ficar negativo no fim do ano.
- **2020 também teve caixa negativo:** no fim do mandato anterior, o total depois dos RP foi −R$ 9.680.304,36 (F3).

## 5. Conclusão

1. **O aumento existe e está comprovado:** +53,2%, igual ao centavo na API, no Siconfi e no RGF.
2. **A causa contábil é concentrada:**
   - obras do FINISA IV, R$ 63,6 milhões, financiadas por empréstimo e ainda não medidas em 31/12/2024;
   - pessoal de dezembro de 2024, R$ 22,3 milhões, dos quais R$ 11,9 milhões de folha do Fundeb paga só em setembro e
     outubro de 2025.
3. **Sobre as eleições:** os dados não provam motivação eleitoral, e o padrão de fim de ano não difere do de outros
   anos. A despesa, porém, foi feita no último ano do mandato e está sujeita ao art. 42. O RGF mostra caixa
   insuficiente em fontes vinculadas, sobretudo operações de crédito (−R$ 60,8 milhões) e Fundeb (−R$ 16,3 milhões). Se
   isso descumpre o art. 42 depende de análise que só o TCE-PR faz, porque considera os repasses do financiamento já
   contratados.

## 6. Limites

- O parecer prévio do TCE-PR sobre as contas de 2024 não foi consultado.
- A API não traz caixa; o caixa vem do RGF, que é do Poder Executivo.
- A natureza dos pagamentos de pessoal do Fundeb de dezembro de 2024 não é conhecida.
- A ligação entre a Lei 14.545/2022 e o contrato "FINISA IV" não foi confirmada.
