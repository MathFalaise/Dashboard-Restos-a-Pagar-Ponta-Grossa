# Lote M — Movimentação dos registros localizados nas conciliações (datas dos lançamentos)

Início 2026-09-30T01:27:43 · fim 2026-09-30T01:31:18 · requisições 7 · **CONCLUÍDO**

- **Exercícios:** []  ·  **Entidades:** []
- **Snapshots:** 7 (Counter({'movimentacao': 7}))
- **Registros normalizados do lote:** 0
- **Tamanho bruto:** 90.541 bytes (8.148 comprimidos)
- **Hashes de resultado:** atual `2f6b4e295ce79593` · como estava em 29/09 `b8a0b2ed2328bf09`

## Portões

| Portão | Resultado | Detalhe |
|---|---|---|
| G1 coleta completa | OK | {'completa': 7} |
| G2 integridade armazém×banco (após coleta) | OK | [] |
| G3 fidelidade (registros = bruto; sem chave desconhecida; chaves-base presentes) | OK | {'esperado': 0, 'obtido': 0, 'com_chaves_extras': 0, 'chaves_base_faltando': []} |
| G4 continuidade fechamento→abertura | OK | 100 pares entidade×ano, 0 falhas |
| G5 regressão temporal ('como estava em 29/09' inalterado) | OK | {'referencia': 'b8a0b2ed2328bf09', 'obtido': 'b8a0b2ed2328bf09'} |
| G6 sem efeito colateral em cortes não tocados pelo lote | OK | {'alteradas_fora_do_lote': 0, 'sumidas': 0} |
| G7 testes (produção + investigação) | OK | 76 passed in 88.34s (0:01:28) | 26 passed in 18.45s |
| G2b integridade armazém×banco (após processamento) | OK |  |
| G8 sem anomalia estrutural | OK | {} |
| G2c integridade após limpeza | OK |  |

Testes: produção `76 passed in 88.34s (0:01:28)`; investigação `26 passed in 18.45s`.

## Anomalias do lote

{}

## Perfil por exercício (comparar com 2025/2026: programática de 28 dígitos, fontes de 3–4 dígitos)


PDFs de RREO sem valores extraídos (layout): 3; problemas da normalização: ['LayoutDesconhecido: período não encontrado no RREO (coleta 403)', "LayoutDesconhecido: colunas não encontradas no RREO: {'h', 'j', 'k', 'e', 'd', '", 'LayoutDesconhecido: período não encontrado no RREO (coleta 431)']

## Notas do lote

7 movimentações (333 lançamentos), todas completas. O que elas mostram está no relatório 04.4, §8–9:

- 2023/9459: cancelamento e estorno de liquidação datados de 31/12/2024, ausentes do RREO emitido em 30/01/2025.
- 2011/21040: estorno de liquidação em 11/01/2024.
- 2401751/2023: um único lançamento (empenho de 8.410,00 em 08/03/2023, mesma data do original de 30.000,00).
