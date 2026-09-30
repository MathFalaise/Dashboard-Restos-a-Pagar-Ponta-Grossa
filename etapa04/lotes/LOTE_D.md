# Lote D — 2020–2021

Início 2026-09-30T01:03:52 · fim 2026-09-30T01:07:57 · requisições 29 · **CONCLUÍDO**

- **Exercícios:** [2020, 2021]  ·  **Entidades:** [1, 3, 4, 5, 6, 8, 9, 10, 11, 15]
- **Snapshots:** 26 (Counter({'rp_listagem': 20, 'rreo_pdf': 4, 'publicacoes': 2}))
- **Registros normalizados do lote:** 12327
- **Tamanho bruto:** 9.191.385 bytes (845.585 comprimidos)
- **Hashes de resultado:** atual `134c029ba12e31b4` · como estava em 29/09 `b8a0b2ed2328bf09`

## Portões

| Portão | Resultado | Detalhe |
|---|---|---|
| G1 coleta completa | OK | {'completa': 26} |
| G2 integridade armazém×banco (após coleta) | OK | [] |
| G3 fidelidade (registros = bruto; sem chave desconhecida; chaves-base presentes) | OK | {'esperado': 12327, 'obtido': 12327, 'com_chaves_extras': 0, 'chaves_base_faltando': []} |
| G4 continuidade fechamento→abertura | OK | 60 pares entidade×ano, 0 falhas |
| G5 regressão temporal ('como estava em 29/09' inalterado) | OK | {'referencia': 'b8a0b2ed2328bf09', 'obtido': 'b8a0b2ed2328bf09'} |
| G6 sem efeito colateral em cortes não tocados pelo lote | OK | {'alteradas_fora_do_lote': 0, 'sumidas': 0} |
| G7 testes (produção + investigação) | OK | 75 passed in 85.03s (0:01:25) | 26 passed in 17.95s |
| G2b integridade armazém×banco (após processamento) | OK |  |
| G8 sem anomalia estrutural | OK | {} |
| G2c integridade após limpeza | OK |  |

Testes: produção `75 passed in 85.03s (0:01:25)`; investigação `26 passed in 17.95s`.

## Anomalias do lote

{'LIQ-NEG': 732, 'PAGOPROC-SEM-PROC': 3}

## Perfil por exercício (comparar com 2025/2026: programática de 28 dígitos, fontes de 3–4 dígitos)

- 2020: {'registros': 7913, 'programatica_27_dig': 166, 'sem_programatica_detalhada': 675, 'fonte_4_dig': 3744, 'fonte_3_dig': 3197, 'programatica_28_dig': 7747, 'fonte_1_dig': 582, 'fonte_2_dig': 390}
- 2021: {'registros': 4414, 'programatica_28_dig': 4414, 'sem_programatica_detalhada': 18, 'fonte_4_dig': 1929, 'fonte_3_dig': 1774, 'fonte_2_dig': 322, 'fonte_1_dig': 389}

## Conciliação com o RREO (colunas com diferença ≠ 0)

| Exercício | Corte | Escopo | RREO-COL | Coluna | RREO | API | Diferença |
|---|---|---|---|---|--:|--:|--:|
| 2020 | 2020-12-31 | consolidado | v1 | (L) | 18.662.407,15 | 18.484.337,99 | -178.069,16 |
| 2020 | 2020-12-31 | consolidado | v1 | (c) | 15.976.269,30 | 15.963.172,25 | -13.097,05 |
| 2020 | 2020-12-31 | consolidado | v1 | (d) | 3.487.579,04 | 3.238.551,45 | -249.027,59 |
| 2020 | 2020-12-31 | consolidado | v1 | (e) | 5.070.758,23 | 5.332.882,87 | 262.124,64 |
| 2020 | 2020-12-31 | consolidado | v1 | (f) | 16.053.117,28 | 15.872.782,46 | -180.334,82 |
| 2020 | 2020-12-31 | consolidado | v1 | (i) | 72.598.227,94 | 72.609.059,33 | 10.831,39 |
| 2020 | 2020-12-31 | consolidado | v1 | (j) | 11.534.414,75 | 11.783.442,34 | 249.027,59 |
| 2020 | 2020-12-31 | consolidado | v1 | (k) | 13.591.648,92 | 13.151.455,12 | -440.193,80 |
| 2020 | 2020-12-31 | consolidado | v2 | (L) | 18.662.407,15 | 18.482.072,33 | -180.334,82 |
| 2020 | 2020-12-31 | consolidado | v2 | (c) | 15.976.269,30 | 15.963.172,25 | -13.097,05 |
| 2020 | 2020-12-31 | consolidado | v2 | (d) | 3.487.579,04 | 3.238.551,45 | -249.027,59 |
| 2020 | 2020-12-31 | consolidado | v2 | (e) | 5.070.758,23 | 5.332.882,87 | 262.124,64 |
| 2020 | 2020-12-31 | consolidado | v2 | (f) | 16.053.117,28 | 15.872.782,46 | -180.334,82 |
| 2020 | 2020-12-31 | consolidado | v2 | (i) | 72.598.227,94 | 72.611.324,99 | 13.097,05 |
| 2020 | 2020-12-31 | consolidado | v2 | (j) | 11.534.414,75 | 11.783.442,34 | 249.027,59 |
| 2020 | 2020-12-31 | consolidado | v2 | (k) | 13.591.648,92 | 13.149.189,46 | -442.459,46 |
| 2020 | 2020-12-31 | entidade | v1 | (L) | 13.617.360,50 | 13.619.626,16 | 2.265,66 |
| 2020 | 2020-12-31 | entidade | v1 | (d) | 3.042.034,35 | 2.793.006,76 | -249.027,59 |
| 2020 | 2020-12-31 | entidade | v1 | (e) | 3.964.851,65 | 4.213.879,24 | 249.027,59 |
| 2020 | 2020-12-31 | entidade | v1 | (i) | 44.719.135,44 | 44.716.869,78 | -2.265,66 |
| 2020 | 2020-12-31 | entidade | v1 | (j) | 9.191.087,22 | 9.440.114,81 | 249.027,59 |
| 2020 | 2020-12-31 | entidade | v1 | (k) | 9.652.508,85 | 9.405.746,92 | -246.761,93 |
| 2020 | 2020-12-31 | entidade | v2 | (d) | 3.042.034,35 | 2.793.006,76 | -249.027,59 |
| 2020 | 2020-12-31 | entidade | v2 | (e) | 3.964.851,65 | 4.213.879,24 | 249.027,59 |
| 2020 | 2020-12-31 | entidade | v2 | (j) | 9.191.087,22 | 9.440.114,81 | 249.027,59 |
| 2020 | 2020-12-31 | entidade | v2 | (k) | 9.652.508,85 | 9.403.481,26 | -249.027,59 |
| 2021 | 2021-12-31 | consolidado | v1 | (L) | 45.226.754,81 | 45.229.722,56 | 2.967,75 |
| 2021 | 2021-12-31 | consolidado | v1 | (d) | 894.686,96 | 893.929,40 | -757,56 |
| 2021 | 2021-12-31 | consolidado | v1 | (e) | 1.475.354,09 | 1.476.111,65 | 757,56 |
| 2021 | 2021-12-31 | consolidado | v1 | (i) | 50.878.789,73 | 50.875.821,98 | -2.967,75 |
| 2021 | 2021-12-31 | consolidado | v1 | (j) | 16.454.111,03 | 16.454.868,59 | 757,56 |
| 2021 | 2021-12-31 | consolidado | v1 | (k) | 43.751.400,72 | 43.753.610,91 | 2.210,19 |
| 2021 | 2021-12-31 | consolidado | v2 | (d) | 894.686,96 | 893.929,40 | -757,56 |
| 2021 | 2021-12-31 | consolidado | v2 | (e) | 1.475.354,09 | 1.476.111,65 | 757,56 |
| 2021 | 2021-12-31 | consolidado | v2 | (j) | 16.454.111,03 | 16.454.868,59 | 757,56 |
| 2021 | 2021-12-31 | consolidado | v2 | (k) | 43.751.400,72 | 43.750.643,16 | -757,56 |

Conciliações com TODAS as colunas iguais: [(2021, '2021-12-31', 'entidade', 1), (2021, '2021-12-31', 'entidade', 2)]

## Notas do lote

- **RREO 2021 da entidade 1: 12/12 colunas iguais**, em v1 e em v2 — a primeira conciliação exata da série.
- 2021 consolidado (v2): só (d)/(j) ±757,56. É o excedente de cancelamento sobre o aproc de 2019/1684 (entidade 6).
- 2020 entidade (v2): só (d)/(j) ±249.027,59, de 14 registros "ambos" (ver `hipotese_canc_2020_2026.md`).
- 2020 consolidado: (f) −180.334,82 de outra entidade. O PDF não detalha por órgão: NÃO DETERMINADO.
- Diferença de formato em relação a 2025/2026: 166 registros com programática de 27 dígitos; 675 sem as chaves opcionais de classificação (em 2025, 48). Nenhuma chave desconhecida.
