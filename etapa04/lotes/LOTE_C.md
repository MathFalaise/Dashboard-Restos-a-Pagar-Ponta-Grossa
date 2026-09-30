# Lote C — 2022–2023

Início 2026-09-30T00:59:06 · fim 2026-09-30T01:03:20 · requisições 35 · **CONCLUÍDO**

- **Exercícios:** [2022, 2023]  ·  **Entidades:** [1, 3, 4, 5, 6, 8, 9, 10, 11, 15]
- **Snapshots:** 32 (Counter({'rp_listagem': 20, 'exercicios': 5, 'rreo_pdf': 4, 'publicacoes': 2, 'entidades': 1}))
- **Registros normalizados do lote:** 10074
- **Tamanho bruto:** 8.983.381 bytes (1.340.945 comprimidos)
- **Hashes de resultado:** atual `065fa3114443071a` · como estava em 29/09 `b8a0b2ed2328bf09`

## Portões

| Portão | Resultado | Detalhe |
|---|---|---|
| G1 coleta completa | OK | {'completa': 31, 'fora_do_catalogo (não exigido)': 1} |
| G2 integridade armazém×banco (após coleta) | OK | [] |
| G3 fidelidade (registros = bruto; sem chave desconhecida; chaves-base presentes) | OK | {'esperado': 10074, 'obtido': 10074, 'com_chaves_extras': 0, 'chaves_base_faltando': []} |
| G4 continuidade fechamento→abertura | OK | 40 pares entidade×ano, 0 falhas |
| G5 regressão temporal ('como estava em 29/09' inalterado) | OK | {'referencia': 'b8a0b2ed2328bf09', 'obtido': 'b8a0b2ed2328bf09'} |
| G6 sem efeito colateral em cortes não tocados pelo lote | OK | {'alteradas_fora_do_lote': 0, 'sumidas': 0} |
| G7 testes (produção + investigação) | OK | 75 passed in 86.98s (0:01:26) | 26 passed in 18.08s |
| G2b integridade armazém×banco (após processamento) | OK |  |
| G8 sem anomalia estrutural | OK | {} |
| G2c integridade após limpeza | OK |  |

Testes: produção `75 passed in 86.98s (0:01:26)`; investigação `26 passed in 18.08s`.

## Anomalias do lote

{'LIQ-NEG': 76, 'PAGOPROC-SEM-PROC': 17}

## Perfil por exercício (comparar com 2025/2026: programática de 28 dígitos, fontes de 3–4 dígitos)

- 2022: {'registros': 4375, 'programatica_28_dig': 4375, 'sem_programatica_detalhada': 18, 'fonte_4_dig': 1892, 'fonte_3_dig': 2093, 'fonte_2_dig': 180, 'fonte_1_dig': 210}
- 2023: {'registros': 5699, 'programatica_28_dig': 5699, 'sem_programatica_detalhada': 18, 'fonte_3_dig': 2638, 'fonte_4_dig': 2592, 'fonte_2_dig': 184, 'fonte_1_dig': 285}

## Consultas fora do catálogo oficial de exercícios (relatadas, não exigidas no G1)

- entidade 10, 2023: status completa, registros 0

## Conciliação com o RREO (colunas com diferença ≠ 0)

| Exercício | Corte | Escopo | RREO-COL | Coluna | RREO | API | Diferença |
|---|---|---|---|---|--:|--:|--:|
| 2022 | 2022-12-31 | consolidado | v1 | (L) | 23.750.403,75 | 24.549.431,91 | 799.028,16 |
| 2022 | 2022-12-31 | consolidado | v1 | (d) | 175.184,54 | 15.279,82 | -159.904,72 |
| 2022 | 2022-12-31 | consolidado | v1 | (e) | 1.731.969,58 | 1.891.874,30 | 159.904,72 |
| 2022 | 2022-12-31 | consolidado | v1 | (i) | 77.334.080,58 | 76.694.637,91 | -639.442,67 |
| 2022 | 2022-12-31 | consolidado | v1 | (j) | 33.277.689,74 | 33.278.008,97 | 319,23 |
| 2022 | 2022-12-31 | consolidado | v1 | (k) | 22.018.434,17 | 22.657.557,61 | 639.123,44 |
| 2022 | 2022-12-31 | consolidado | v2 | (L) | 23.750.403,75 | 23.909.989,24 | 159.585,49 |
| 2022 | 2022-12-31 | consolidado | v2 | (d) | 175.184,54 | 15.279,82 | -159.904,72 |
| 2022 | 2022-12-31 | consolidado | v2 | (e) | 1.731.969,58 | 1.891.874,30 | 159.904,72 |
| 2022 | 2022-12-31 | consolidado | v2 | (j) | 33.277.689,74 | 33.278.008,97 | 319,23 |
| 2022 | 2022-12-31 | consolidado | v2 | (k) | 22.018.434,17 | 22.018.114,94 | -319,23 |
| 2022 | 2022-12-31 | entidade | v1 | (L) | 20.003.072,05 | 20.163.082,14 | 160.010,09 |
| 2022 | 2022-12-31 | entidade | v1 | (d) | 170.353,92 | 10.449,20 | -159.904,72 |
| 2022 | 2022-12-31 | entidade | v1 | (e) | 1.673.892,58 | 1.833.797,30 | 159.904,72 |
| 2022 | 2022-12-31 | entidade | v1 | (i) | 59.457.720,83 | 59.457.296,23 | -424,60 |
| 2022 | 2022-12-31 | entidade | v1 | (j) | 6.011.720,92 | 6.012.040,15 | 319,23 |
| 2022 | 2022-12-31 | entidade | v1 | (k) | 18.329.179,47 | 18.329.284,84 | 105,37 |
| 2022 | 2022-12-31 | entidade | v2 | (L) | 20.003.072,05 | 20.162.657,54 | 159.585,49 |
| 2022 | 2022-12-31 | entidade | v2 | (d) | 170.353,92 | 10.449,20 | -159.904,72 |
| 2022 | 2022-12-31 | entidade | v2 | (e) | 1.673.892,58 | 1.833.797,30 | 159.904,72 |
| 2022 | 2022-12-31 | entidade | v2 | (j) | 6.011.720,92 | 6.012.040,15 | 319,23 |
| 2022 | 2022-12-31 | entidade | v2 | (k) | 18.329.179,47 | 18.328.860,24 | -319,23 |
| 2023 | 2023-12-31 | consolidado | v1 | (L) | 21.197.857,45 | 21.259.531,33 | 61.673,88 |
| 2023 | 2023-12-31 | consolidado | v1 | (c) | 5.241.173,83 | 5.238.060,50 | -3.113,33 |
| 2023 | 2023-12-31 | consolidado | v1 | (d) | 56.598,74 | 45.937,67 | -10.661,07 |
| 2023 | 2023-12-31 | consolidado | v1 | (e) | 2.340.203,25 | 2.353.977,65 | 13.774,40 |
| 2023 | 2023-12-31 | consolidado | v1 | (f) | 22.047.449,65 | 22.044.498,17 | -2.951,48 |
| 2023 | 2023-12-31 | consolidado | v1 | (h) | 130.634.479,92 | 130.635.909,36 | 1.429,44 |
| 2023 | 2023-12-31 | consolidado | v1 | (i) | 129.184.714,50 | 129.169.286,43 | -15.428,07 |
| 2023 | 2023-12-31 | consolidado | v1 | (j) | 20.682.813,42 | 20.647.390,53 | -35.422,89 |
| 2023 | 2023-12-31 | consolidado | v1 | (k) | 18.857.654,20 | 18.905.553,68 | 47.899,48 |
| 2023 | 2023-12-31 | consolidado | v2 | (L) | 21.197.857,45 | 21.239.560,49 | 41.703,04 |
| 2023 | 2023-12-31 | consolidado | v2 | (c) | 5.241.173,83 | 5.238.610,50 | -2.563,33 |
| 2023 | 2023-12-31 | consolidado | v2 | (d) | 56.598,74 | 45.937,67 | -10.661,07 |
| 2023 | 2023-12-31 | consolidado | v2 | (e) | 2.340.203,25 | 2.353.427,65 | 13.224,40 |
| 2023 | 2023-12-31 | consolidado | v2 | (f) | 22.047.449,65 | 22.044.498,17 | -2.951,48 |
| 2023 | 2023-12-31 | consolidado | v2 | (h) | 130.634.479,92 | 130.635.909,36 | 1.429,44 |
| 2023 | 2023-12-31 | consolidado | v2 | (i) | 129.184.714,50 | 129.188.707,27 | 3.992,77 |
| 2023 | 2023-12-31 | consolidado | v2 | (j) | 20.682.813,42 | 20.647.390,53 | -35.422,89 |
| 2023 | 2023-12-31 | consolidado | v2 | (k) | 18.857.654,20 | 18.886.132,84 | 28.478,64 |
| 2023 | 2023-12-31 | entidade | v1 | (L) | 20.417.319,97 | 20.482.151,37 | 64.831,40 |
| 2023 | 2023-12-31 | entidade | v1 | (c) | 4.360.639,69 | 4.357.526,36 | -3.113,33 |
| 2023 | 2023-12-31 | entidade | v1 | (d) | 51.666,91 | 45.770,60 | -5.896,31 |
| 2023 | 2023-12-31 | entidade | v1 | (e) | 2.278.655,89 | 2.287.665,53 | 9.009,64 |
| 2023 | 2023-12-31 | entidade | v1 | (f) | 18.359.090,35 | 18.356.138,87 | -2.951,48 |
| 2023 | 2023-12-31 | entidade | v1 | (i) | 107.201.176,45 | 107.184.363,94 | -16.812,51 |
| 2023 | 2023-12-31 | entidade | v1 | (j) | 12.415.416,33 | 12.373.455,60 | -41.960,73 |
| 2023 | 2023-12-31 | entidade | v1 | (k) | 18.138.664,08 | 18.194.485,84 | 55.821,76 |
| 2023 | 2023-12-31 | entidade | v2 | (L) | 20.417.319,97 | 20.462.225,53 | 44.905,56 |
| 2023 | 2023-12-31 | entidade | v2 | (c) | 4.360.639,69 | 4.358.076,36 | -2.563,33 |
| 2023 | 2023-12-31 | entidade | v2 | (d) | 51.666,91 | 45.770,60 | -5.896,31 |
| 2023 | 2023-12-31 | entidade | v2 | (e) | 2.278.655,89 | 2.287.115,53 | 8.459,64 |
| 2023 | 2023-12-31 | entidade | v2 | (f) | 18.359.090,35 | 18.356.138,87 | -2.951,48 |
| 2023 | 2023-12-31 | entidade | v2 | (i) | 107.201.176,45 | 107.203.739,78 | 2.563,33 |
| 2023 | 2023-12-31 | entidade | v2 | (j) | 12.415.416,33 | 12.373.455,60 | -41.960,73 |
| 2023 | 2023-12-31 | entidade | v2 | (k) | 18.138.664,08 | 18.175.110,00 | 36.445,92 |

Conciliações com TODAS as colunas iguais: nenhuma

## Notas do lote

- Portões OK. Entidade 10 em 2023 está fora do catálogo oficial (o catálogo dela vai até 2022). A consulta devolveu 0 registros e foi relatada, conforme a regra fixada antes do lote.
- 2022 (v2): só (d) −159.904,72, com (e) compensando, e (j)/(k) ±319,23.
- 2023 (v2): (f) −2.951,48 é 2011/21040. O estorno da liquidação é de 11/01/2024; o RREO de 2023 foi emitido em 29/01/2024, depois do estorno, e já trata o registro como não processado (ver Lote M).
- Formato igual ao de 2025/2026: programática de 28 dígitos; nenhuma chave desconhecida.
