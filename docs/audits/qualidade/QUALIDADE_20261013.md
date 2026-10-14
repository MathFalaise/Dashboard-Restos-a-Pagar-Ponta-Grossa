# Relatório de qualidade por dimensão

Gerado por `docs/audits/qualidade/medir_qualidade.py` sobre a normalização 18. Cada dimensão tem o seu numerador, denominador e critério; **nenhum percentual global** é calculado. A meta de 99,9% só é dada como atingida na dimensão em que a medição a confirma.

| Dimensão | Numerador | Denominador | Taxa | Meta 99,9% | Universo | Critério |
|---|---:|---:|---:|---|---|---|
| 1. Fidelidade da ingestão (registros) | 604142 | 604142 | 100,0000% | atingida | 604142 registros da normalização 18 (listagens completas) | registro igual ao item bruto em todos os campos conferidos |
| 1. Fidelidade da ingestão (campos) | 10874556 | 10874556 | 100,0000% | atingida | 10 campos monetários + 8 de identificação por registro | valor do campo igual ao do bruto (centavos exatos) |
| 2. Reprodutibilidade do cálculo | 9347 | 9347 | 100,0000% | atingida | indicadores publicados de todos os cortes processados (Município e cada entidade) | valor do painel igual ao recálculo independente a partir do bruto |
| 3. Concordância documental: elotech_x_pdf | 773 | 1356 | 57,0059% | não atingida | células comparáveis (elotech_x_pdf) | valores iguais ao centavo |
| 3. Concordância documental: elotech_x_siconfi | 269 | 768 | 35,0260% | não atingida | células comparáveis (elotech_x_siconfi) | valores iguais ao centavo |
| 3. Concordância documental: painel_x_siconfi | 161 | 320 | 50,3125% | não atingida | células comparáveis (painel_x_siconfi) | valores iguais ao centavo |
| 3. Concordância documental: oficial_x_oficial | 229 | 696 | 32,9023% | não atingida | células comparáveis (oficial_x_oficial) | valores iguais ao centavo |
| 4. Cobertura: RREO transcritos | 112 | 114 | 98,2456% | não atingida | documentos do Anexo VII listados pelo portal (114) | coletado e transcrito pelo extrator de produção |
| 4. Cobertura: RREO conferidos por leitura independente | 112 | 112 | 100,0000% | atingida | documentos transcritos | todas as células iguais na segunda leitura (xpdf) |
| 7. Integridade da proveniência (cortes publicados) | 65 | 65 | 100,0000% | atingida | cortes publicados do Município (605 snapshots distintos) | todo snapshot do corte: manifesto com o SHA-256 registrado e todo objeto bruto com o SHA-256 do nome |

## 5. Resíduos sem causa determinada

Por comparação e exercício (valor absoluto da parte sem causa comprovada; detalhe por coluna em `docs/audits/rreo/MATRIZ_CONCORDANCIA.md`):

| Comparação | Exercício | Células | Valor |
|---|---|---:|---:|
| elotech_x_pdf | 2016 | 33 | 10.382.790,74 |
| elotech_x_pdf | 2017 | 7 | 2.941.903,80 |
| elotech_x_pdf | 2018 | 34 | 62.969.718,79 |
| elotech_x_pdf | 2019 | 20 | 40.671.686,87 |
| elotech_x_pdf | 2020 | 7 | 353.096,89 |
| elotech_x_pdf | 2021 | 1 | 14.023,07 |
| elotech_x_pdf | 2022 | 30 | 912.178,60 |
| elotech_x_pdf | 2023 | 55 | 925.551,02 |
| elotech_x_pdf | 2024 | 6 | 23.170,16 |
| elotech_x_pdf | 2026 | 26 | 18.282.749,93 |
| elotech_x_siconfi | 2016 | 47 | 54.967.975,28 |
| elotech_x_siconfi | 2017 | 26 | 25.068.783,73 |
| elotech_x_siconfi | 2018 | 36 | 63.108.756,55 |
| elotech_x_siconfi | 2019 | 15 | 1.498.108,39 |
| elotech_x_siconfi | 2020 | 12 | 5.289.808,29 |
| elotech_x_siconfi | 2022 | 15 | 1.830.355,46 |
| elotech_x_siconfi | 2023 | 24 | 580.634,45 |
| elotech_x_siconfi | 2024 | 26 | 4.817.348,10 |
| elotech_x_siconfi | 2025 | 2 | 523.594,75 |
| elotech_x_siconfi | 2026 | 20 | 10.906.499,78 |
| oficial_x_oficial | 2017 | 43 | 38.328.009,28 |
| oficial_x_oficial | 2018 | 3 | 208.556,64 |
| oficial_x_oficial | 2019 | 47 | 156.905.471,11 |
| oficial_x_oficial | 2020 | 34 | 8.908.646,09 |
| oficial_x_oficial | 2021 | 5 | 15.060,89 |
| oficial_x_oficial | 2022 | 14 | 1.248.391,64 |
| oficial_x_oficial | 2023 | 37 | 1.464.954,86 |
| oficial_x_oficial | 2024 | 52 | 9.236.575,68 |
| oficial_x_oficial | 2025 | 21 | 40.963.535,98 |
| oficial_x_oficial | 2026 | 23 | 26.900.095,10 |
| painel_x_siconfi | 2016 | 24 | 40.231.104,15 |
| painel_x_siconfi | 2017 | 14 | 24.177.431,24 |
| painel_x_siconfi | 2018 | 19 | 42.639.252,66 |
| painel_x_siconfi | 2019 | 12 | 31.549.854,00 |
| painel_x_siconfi | 2020 | 5 | 3.478.266,23 |
| painel_x_siconfi | 2021 | 3 | 26.388,56 |
| painel_x_siconfi | 2022 | 7 | 447.536,92 |
| painel_x_siconfi | 2023 | 12 | 295.131,71 |
| painel_x_siconfi | 2024 | 10 | 2.756.833,01 |
| painel_x_siconfi | 2025 | 2 | 2.114.171,24 |
| painel_x_siconfi | 2026 | 9 | 6.102.064,83 |

## 6. Atualidade

- Última coleta de listagem: 2026-10-10T13:26:25-03:00 (3 dia(s) antes desta medição).
- Retratos armazenados ainda não processados (não publicados): 0.
- Cortes com alteração entre retratos: 11; alertas retrospectivos: 10.

## Casos fora dos denominadores

- 2. Reprodutibilidade do cálculo: Município indisponível no painel (nunca zero): 2026|2026-01-31, 2026|2026-03-31, 2026|2026-12-31
- 4. Cobertura: RREO transcritos: recusado_layout: 2
- 4. Cobertura: RREO transcritos: coletado_sem_extracao: 0
- 4. Cobertura: RREO transcritos: nao_coletado: 0
