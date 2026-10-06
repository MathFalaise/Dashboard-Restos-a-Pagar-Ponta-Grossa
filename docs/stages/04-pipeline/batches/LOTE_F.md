# Lote F — 2016–2017 (+ RREO 2019, que o filtro sensível a maiúsculas pulou no Lote E)

Início 2026-09-30T01:14:14 · fim 2026-09-30T01:18:45 · requisições 33 · **CONCLUÍDO**

- **Exercícios:** [2016, 2017]  ·  **Entidades:** [1, 3, 4, 5, 6, 8, 9, 10, 11, 15]
- **Snapshots:** 27 (Counter({'rp_listagem': 20, 'rreo_pdf': 4, 'publicacoes': 3}))
- **Registros normalizados do lote:** 16456
- **Tamanho bruto:** 11.926.168 bytes (1.217.926 comprimidos)
- **Hashes de resultado:** atual `88f1de281da27c25` · como estava em 29/09 `b8a0b2ed2328bf09`

## Portões

| Portão | Resultado | Detalhe |
|---|---|---|
| G1 coleta completa | OK | {'completa': 25, 'fora_do_catalogo (não exigido)': 2} |
| G2 integridade armazém×banco (após coleta) | OK | [] |
| G3 fidelidade (registros = bruto; sem chave desconhecida; chaves-base presentes) | OK | {'esperado': 16456, 'obtido': 16456, 'com_chaves_extras': 0, 'chaves_base_faltando': []} |
| G4 continuidade fechamento→abertura | OK | 100 pares entidade×ano, 0 falhas |
| G5 regressão temporal ('como estava em 29/09' inalterado) | OK | {'referencia': 'b8a0b2ed2328bf09', 'obtido': 'b8a0b2ed2328bf09'} |
| G6 sem efeito colateral em cortes não tocados pelo lote | OK | {'alteradas_fora_do_lote': 0, 'sumidas': 0} |
| G7 testes (produção + investigação) | OK | 76 passed in 86.00s (0:01:26) | 26 passed in 14.66s |
| G2b integridade armazém×banco (após processamento) | OK |  |
| G8 sem anomalia estrutural | OK | {} |
| G2c integridade após limpeza | OK |  |

Testes: produção `76 passed in 86.00s (0:01:26)`; investigação `26 passed in 14.66s`.

## Anomalias do lote

{'LIQ-NEG': 280, 'PAGOPROC-SEM-PROC': 3}

## Perfil por exercício (comparar com 2025/2026: programática de 28 dígitos, fontes de 3–4 dígitos)

- 2016: {'registros': 7774, 'programatica_27_dig': 179, 'sem_programatica_detalhada': 1770, 'fonte_4_dig': 3381, 'fonte_3_dig': 3377, 'programatica_28_dig': 7595, 'fonte_1_dig': 812, 'fonte_2_dig': 204}
- 2017: {'registros': 8682, 'programatica_27_dig': 179, 'sem_programatica_detalhada': 1522, 'fonte_4_dig': 3761, 'fonte_3_dig': 3827, 'programatica_28_dig': 8503, 'fonte_1_dig': 787, 'fonte_2_dig': 307}

## Consultas fora do catálogo oficial de exercícios (relatadas, não exigidas no G1)

- entidade 15, 2016: status completa, registros 0
- entidade 15, 2017: status completa, registros 0

## Conciliação com o RREO (colunas com diferença ≠ 0)

| Exercício | Corte | Escopo | RREO-COL | Coluna | RREO | API | Diferença |
|---|---|---|---|---|--:|--:|--:|
| 2017 | 2017-12-31 | consolidado | v1 | (L) | 17.486.545,07 | 17.456.300,37 | -30.244,70 |
| 2017 | 2017-12-31 | consolidado | v1 | (b) | 17.399.999,02 | 17.315.474,50 | -84.524,52 |
| 2017 | 2017-12-31 | consolidado | v1 | (c) | 18.774.174,77 | 18.516.320,05 | -257.854,72 |
| 2017 | 2017-12-31 | consolidado | v1 | (d) | 1.075.018,99 | 868.846,28 | -206.172,71 |
| 2017 | 2017-12-31 | consolidado | v1 | (e) | 3.770.887,55 | 4.150.390,46 | 379.502,91 |
| 2017 | 2017-12-31 | consolidado | v1 | (f) | 27.496.690,64 | 27.483.431,62 | -13.259,02 |
| 2017 | 2017-12-31 | consolidado | v1 | (g) | 41.838.243,29 | 41.659.609,55 | -178.633,74 |
| 2017 | 2017-12-31 | consolidado | v1 | (h) | 33.907.429,07 | 35.072.303,38 | 1.164.874,31 |
| 2017 | 2017-12-31 | consolidado | v1 | (i) | 34.493.393,47 | 34.600.597,61 | 107.204,14 |
| 2017 | 2017-12-31 | consolidado | v1 | (j) | 21.125.882,94 | 21.236.533,65 | 110.650,71 |
| 2017 | 2017-12-31 | consolidado | v1 | (k) | 13.715.657,52 | 13.305.909,91 | -409.747,61 |
| 2017 | 2017-12-31 | consolidado | v2 | (L) | 17.486.545,07 | 17.401.732,25 | -84.812,82 |
| 2017 | 2017-12-31 | consolidado | v2 | (b) | 17.399.999,02 | 17.315.474,50 | -84.524,52 |
| 2017 | 2017-12-31 | consolidado | v2 | (c) | 18.774.174,77 | 18.570.888,17 | -203.286,60 |
| 2017 | 2017-12-31 | consolidado | v2 | (d) | 1.075.018,99 | 868.846,28 | -206.172,71 |
| 2017 | 2017-12-31 | consolidado | v2 | (e) | 3.770.887,55 | 4.095.822,34 | 324.934,79 |
| 2017 | 2017-12-31 | consolidado | v2 | (f) | 27.496.690,64 | 27.483.431,62 | -13.259,02 |
| 2017 | 2017-12-31 | consolidado | v2 | (g) | 41.838.243,29 | 41.659.609,55 | -178.633,74 |
| 2017 | 2017-12-31 | consolidado | v2 | (h) | 33.907.429,07 | 35.072.303,38 | 1.164.874,31 |
| 2017 | 2017-12-31 | consolidado | v2 | (i) | 34.493.393,47 | 34.600.597,61 | 107.204,14 |
| 2017 | 2017-12-31 | consolidado | v2 | (j) | 21.125.882,94 | 21.236.533,65 | 110.650,71 |
| 2017 | 2017-12-31 | consolidado | v2 | (k) | 13.715.657,52 | 13.305.909,91 | -409.747,61 |
| 2017 | 2017-12-31 | entidade | v1 | (L) | 16.440.984,91 | 16.592.264,91 | 151.280,00 |
| 2017 | 2017-12-31 | entidade | v1 | (c) | 17.797.868,83 | 17.620.108,30 | -177.760,53 |
| 2017 | 2017-12-31 | entidade | v1 | (d) | 1.072.813,63 | 866.640,92 | -206.172,71 |
| 2017 | 2017-12-31 | entidade | v1 | (e) | 3.760.154,24 | 4.144.087,48 | 383.933,24 |
| 2017 | 2017-12-31 | entidade | v1 | (h) | 29.946.119,29 | 31.011.278,35 | 1.065.159,06 |
| 2017 | 2017-12-31 | entidade | v1 | (i) | 30.424.654,19 | 30.546.656,72 | 122.002,53 |
| 2017 | 2017-12-31 | entidade | v1 | (j) | 19.774.075,71 | 19.884.726,42 | 110.650,71 |
| 2017 | 2017-12-31 | entidade | v1 | (k) | 12.680.830,67 | 12.448.177,43 | -232.653,24 |
| 2017 | 2017-12-31 | entidade | v2 | (L) | 16.440.984,91 | 16.536.506,91 | 95.522,00 |
| 2017 | 2017-12-31 | entidade | v2 | (c) | 17.797.868,83 | 17.675.866,30 | -122.002,53 |
| 2017 | 2017-12-31 | entidade | v2 | (d) | 1.072.813,63 | 866.640,92 | -206.172,71 |
| 2017 | 2017-12-31 | entidade | v2 | (e) | 3.760.154,24 | 4.088.329,48 | 328.175,24 |
| 2017 | 2017-12-31 | entidade | v2 | (h) | 29.946.119,29 | 31.011.278,35 | 1.065.159,06 |
| 2017 | 2017-12-31 | entidade | v2 | (i) | 30.424.654,19 | 30.546.656,72 | 122.002,53 |
| 2017 | 2017-12-31 | entidade | v2 | (j) | 19.774.075,71 | 19.884.726,42 | 110.650,71 |
| 2017 | 2017-12-31 | entidade | v2 | (k) | 12.680.830,67 | 12.448.177,43 | -232.653,24 |

Conciliações com TODAS as colunas iguais: nenhuma

PDFs de RREO sem valores extraídos (layout): 3; problemas da normalização: ['LayoutDesconhecido: período não encontrado no RREO (coleta 403)', "LayoutDesconhecido: colunas não encontradas no RREO: {'k', 'i', 'f', 'h', 'L', '", 'LayoutDesconhecido: período não encontrado no RREO (coleta 431)']

## Notas do lote

- Portões OK. Entidade 15 em 2016 e 2017 está fora do catálogo: 0 registros, relatado.
- 2017 (extraído, v2): as inscrições (a)(b)(f)(g) da entidade 1 fecham. Sob v2, os pagamentos totais (c)+(i) fecham e L difere só pelo cancelamento líquido (95.522,00). Há troca c/i de 122.002,53, h +1.065.159,06 e (d)/(j) −206.172,71/+110.650,71.
- Os PDFs de 2016 e 2017 têm `dataArquivo` 17/12/2018: foram publicados, ou republicados, dois anos depois.
- 2016: o extrator não acha as colunas. A leitura de investigação foi **recusada** porque as identidades e/k/L não fecham; nada foi ajustado.
- 2019 (lido na investigação): consolidado, L (v2) +94.099,96.
