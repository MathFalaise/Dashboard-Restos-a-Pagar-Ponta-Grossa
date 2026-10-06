# Reconciliação investigação × produção (Etapa 04.2)

Gerado por `docs/stages/04-pipeline/reconciliation/reconciliar_04_2.py`, sem acesso à internet.

- **Esperado:** pipeline de investigação (`docs/stages/03-data-model/validation`) sobre o bruto das Etapas 01/02.
- **Obtido:** importador + pipeline de produção (`app/rp`) sobre o mesmo bruto.
- Snapshots pareados por conteúdo: tipo, horário e SHA-256 de cada resposta.

## 1. Tabela a tabela

| Tabela | Linhas esperadas | Linhas obtidas | Igual? | Primeiras diferenças |
|---|--:|--:|---|---|
| `rp_registro` | 82988 | 82988 | **SIM** |  |
| `movimentacao_lancamento` | 2004 | 2004 | **SIM** |  |
| `rreo_valor` | 517 | 517 | **SIM** |  |
| `entidade_ref` | 10 | 10 | **SIM** |  |
| `exercicio_ref` | 11 | 11 | **SIM** |  |
| `rp_derivado` | 82988 | 82988 | **SIM** |  |
| `movimentacao_interpretada` | 2004 | 2004 | **SIM** |  |
| `anomalia` | 10837 | 10837 | **SIM** |  |
| `espelhamento_par` | 751 | 751 | **SIM** |  |
| `visao_valor` | 1020 | 1020 | **SIM** |  |
| `conciliacao_rreo` | 216 | 216 | **SIM** |  |
| `verificacao` | 34 | 34 | **NÃO** | [((('ANOM-CONT', 1), 'continuidade fechamento→abertura', '{"de": 2025, "entidade": 1, "para": 2026, "snapshots": [["rp_listagem", "2026-09-29T20:12:49-03:00", ["f1e15ac1743420d38a34f3df71a01fb6ec5794c84bb81006efdd81bc5014c600", "1c69ad4e0602f12ad192057d497c1dab7ce17ccfb53aaeec77cff5ba61f85523"]], [" |
| `verificacao (sem a escolha do snapshot)` | 34 | 34 | **SIM** |  |

Snapshots: 197 na investigação, 197 na produção, **197 pareados por conteúdo**.

## 2. Casos relevantes: esperado × obtido

| Caso | Esperado (investigação) | Obtido (produção) | Igual? |
|---|---|---|---|
| 11963/2016, corte 2026 (01/01–31/12): categoria, S1, cancel. processado | `[('processado', 0, 386452), ('processado', 0, 386452)]` | `[('processado', 0, 386452), ('processado', 0, 386452)]` | **SIM** |
| 5659/2025, corte 2026: S1, S3 | `[(86378534, 86378534), (86378534, 86378534), (86378534, 86378534), (86378534, 86378534), (86378534, 86378534)]` | `[(86378534, 86378534), (86378534, 86378534), (86378534, 86378534), (86378534, 86378534), (86378534, 86378534)]` | **SIM** |
| Pares 2025 por relação × lado com execução | `[('a_e_saldo_final_de_b', 'B', 9), ('igual', 'nenhum', 11)]` | `[('a_e_saldo_final_de_b', 'B', 9), ('igual', 'nenhum', 11)]` | **SIM** |
| Pares 2026 por lado com execução | `[('A', 356), ('nenhum', 375)]` | `[('A', 356), ('nenhum', 375)]` | **SIM** |
| Conciliação 4º bim/2026, entidade, RREO-COL v1: h, i | `[('h', -34547956), ('i', -23772825)]` | `[('h', -34547956), ('i', -23772825)]` | **SIM** |
| Conciliação 2025 consolidado, RREO-COL v2: colunas ≠ 0 | `[('L', 92570262), ('a', 182950), ('d', 182950), ('f', 658050), ('g', 91729262), ('j', -182950), ('k', 92570262)]` | `[('L', 92570262), ('a', 182950), ('d', 182950), ('f', 658050), ('g', 91729262), ('j', -182950), ('k', 92570262)]` | **SIM** |
| Visão analítica 2025, RREO-COL v2 × CONS-PAR v2: g, L | `[('L', 2034147166), ('g', 20518290253)]` | `[('L', 2034147166), ('g', 20518290253)]` | **SIM** |
| Anomalias por tipo (todas) | `[('COPIA-24', 10714), ('LIQ-NEG', 100), ('PAGOPROC-SEM-PROC', 14), ('PAR-INSCRICAO-DIVERGENTE', 9)]` | `[('COPIA-24', 10714), ('LIQ-NEG', 100), ('PAGOPROC-SEM-PROC', 14), ('PAR-INSCRICAO-DIVERGENTE', 9)]` | **SIM** |

## 3. Snapshots reais da 04.1 (banco ativo) × investigação

- Listagem real coletada em 2026-09-29T21:35:35-03:00: bytes idênticos a 2 snapshot(s) da investigação (2026-09-29T20:12:30-03:00, 2026-09-29T20:25:17-03:00).
  - `rp_registro` do snapshot real × snapshot de 2026-09-29T20:25:17-03:00: 4557 × 4557 linhas, **idênticas**
  - `rp_derivado` do snapshot real × snapshot de 2026-09-29T20:25:17-03:00: 4557 × 4557 linhas, **idênticas**
  - `rp_registro` do snapshot real × snapshot de 2026-09-29T20:12:30-03:00: 4557 × 4557 linhas, **idênticas**
  - `rp_derivado` do snapshot real × snapshot de 2026-09-29T20:12:30-03:00: 4557 × 4557 linhas, **idênticas**
- Conciliação do PDF real (4º bim/2026, entidade) × investigação: 24 × 24 linhas (2 regras × 12 colunas), **idênticas**.

## Resultado: **ESPERADO == OBTIDO**

