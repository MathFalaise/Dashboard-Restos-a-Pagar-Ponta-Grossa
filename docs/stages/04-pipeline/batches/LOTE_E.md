# Lote E — 2018–2019

Início 2026-09-30T01:09:00 · fim 2026-09-30T01:13:02 · requisições 27 · **CONCLUÍDO**

- **Exercícios:** [2018, 2019]  ·  **Entidades:** [1, 3, 4, 5, 6, 8, 9, 10, 11, 15]
- **Snapshots:** 23 (Counter({'rp_listagem': 20, 'publicacoes': 2, 'rreo_pdf': 1}))
- **Registros normalizados do lote:** 13630
- **Tamanho bruto:** 9.763.006 bytes (874.190 comprimidos)
- **Hashes de resultado:** atual `0b866acf4bdc75b7` · como estava em 29/09 `b8a0b2ed2328bf09`

## Portões

| Portão | Resultado | Detalhe |
|---|---|---|
| G1 coleta completa | OK | {'completa': 22, 'fora_do_catalogo (não exigido)': 1} |
| G2 integridade armazém×banco (após coleta) | OK | [] |
| G3 fidelidade (registros = bruto; sem chave desconhecida; chaves-base presentes) | OK | {'esperado': 13630, 'obtido': 13630, 'com_chaves_extras': 0, 'chaves_base_faltando': []} |
| G4 continuidade fechamento→abertura | OK | 80 pares entidade×ano, 0 falhas |
| G5 regressão temporal ('como estava em 29/09' inalterado) | OK | {'referencia': 'b8a0b2ed2328bf09', 'obtido': 'b8a0b2ed2328bf09'} |
| G6 sem efeito colateral em cortes não tocados pelo lote | OK | {'alteradas_fora_do_lote': 0, 'sumidas': 0} |
| G7 testes (produção + investigação) | OK | 75 passed in 83.28s (0:01:23) | 26 passed in 18.23s |
| G2b integridade armazém×banco (após processamento) | OK |  |
| G8 sem anomalia estrutural | OK | {} |
| G2c integridade após limpeza | OK |  |

Testes: produção `75 passed in 83.28s (0:01:23)`; investigação `26 passed in 18.23s`.

## Anomalias do lote

{'LIQ-NEG': 571, 'PAGOPROC-SEM-PROC': 1}

## Perfil por exercício (comparar com 2025/2026: programática de 28 dígitos, fontes de 3–4 dígitos)

- 2018: {'registros': 6821, 'programatica_27_dig': 167, 'sem_programatica_detalhada': 1274, 'fonte_4_dig': 3328, 'fonte_3_dig': 2601, 'programatica_28_dig': 6654, 'fonte_1_dig': 672, 'fonte_2_dig': 220}
- 2019: {'registros': 6809, 'programatica_27_dig': 167, 'sem_programatica_detalhada': 987, 'fonte_4_dig': 3675, 'fonte_3_dig': 2342, 'programatica_28_dig': 6642, 'fonte_1_dig': 522, 'fonte_2_dig': 270}

## Consultas fora do catálogo oficial de exercícios (relatadas, não exigidas no G1)

- entidade 15, 2018: status completa, registros 0

PDFs de RREO sem valores extraídos (layout): 1; problemas da normalização: ['LayoutDesconhecido: período não encontrado no RREO (coleta 403)']

## Notas do lote

- Portões OK. Entidade 15 em 2018 está fora do catálogo (o dela começa em 2019): 0 registros, relatado.
- **Limitação encontrada:** em 2019 o portal rotula o PDF como "6º BIMESTRE", em caixa alta, e o filtro de bimestre do coletor diferenciava maiúsculas. O PDF foi pulado sem erro.
  - Correção no coletor: expressão regular sem diferença de caixa e de espaço, com teste novo (`test_rreo_filtra_bimestres_rotulo_em_maiusculas`).
  - O PDF foi coletado no Lote F.
- O PDF de 2018 (arquivo 34898) tem outro layout ("JANEIRO Á DEZEMBRO 2018", sem ponto no ano) e o extrator `rp-rreo-coordenadas/1` não o reconhece. Isso ficou registrado na normalização; o extrator não foi alterado.
  - Leitura de investigação em `rreo_layout_antigo.md`: consolidado, L (v2) com diferença de só 3.052,00.
