# Folder map (06/10/2026)

On 06/10/2026 the repository folders were reorganized and renamed in English. Every move was a `git mv`, so file
history is preserved (`git log --follow <new path>`). No file content changed in the move, except the code paths
that point to the new folders.

## Old references that stay on purpose

Some old paths are **data**, not navigation, and are never rewritten:

- **Snapshot manifests** (`data/snapshots/coletas/...`) record collectors such as `etapa02-investigacao/coletar.py`
  and their code hash. Manifests are immutable, and the database checks them field by field.
- **Rule catalog and governance** (`app/rp/regras.py`, `app/rp/governanca.py`): the `fonte` of each rule and
  decision (e.g. `etapa04/RELATORIO_04_4.md`) is stored in the database. Changing it would be rejected as a catalog
  divergence.
- **Evidence files** (`*.json`, `*.log`) keep the path that was valid when they were written.

The explanation sources shown in the quality screen and the methodology page (`app/rp/painel/explicacoes.py`,
`fontes.py`) are code only, not stored data, so they were updated to the new paths.
- **Frozen scripts** `docs/stages/02-accounting-validation/investigation/coletar.py` and `casos.py` have their
  SHA-256 recorded in 181 manifests. They are not edited, so their internal paths still describe the old layout
  (`etapa02/dados_brutos`).

To follow any of these references, use the table below.

## Old → new

| Old | New |
|---|---|
| `snapshots` | `data/snapshots` |
| `backups` | `data/backups` |
| `etapa01/amostras_brutas` | `data/stage01-samples` |
| `etapa01/amostras_brutas_SHA256.txt` | `data/stage01-samples.SHA256.txt` |
| `etapa02/dados_brutos` | `data/stage02-raw` |
| `etapa02/dados_brutos_SHA256.txt` | `data/stage02-raw.SHA256.txt` |
| `etapa01/RELATORIO_ETAPA01.md` | `docs/stages/01-source-discovery/REPORT.md` |
| `etapa02/RELATORIO_ETAPA02.md` | `docs/stages/02-accounting-validation/REPORT.md` |
| `etapa02/investigacao` | `docs/stages/02-accounting-validation/investigation` |
| `etapa02/resultados` | `docs/stages/02-accounting-validation/results` |
| `etapa03/PROMPT_ETAPA03.md` | `docs/stages/03-data-model/PROMPT.md` |
| `etapa03/RELATORIO_ETAPA03.md` | `docs/stages/03-data-model/REPORT.md` |
| `etapa03/modelo` | `docs/stages/03-data-model/model` |
| `etapa03/resultados` | `docs/stages/03-data-model/results` |
| `etapa03/validacao` | `docs/stages/03-data-model/validation` |
| `etapa04/ARQUITETURA_FONTES.md` | `docs/stages/04-pipeline/SOURCE_ARCHITECTURE.md` |
| `etapa04/CORRECOES_ETAPAS_01_A_04_4.md` | `docs/stages/04-pipeline/CORRECTIONS_STAGES_01_TO_04_4.md` |
| `etapa04/PLANO_ETAPA04.md` | `docs/stages/04-pipeline/PLAN.md` |
| `etapa04/RELATORIO_04_1.md` | `docs/stages/04-pipeline/REPORT_04_1.md` |
| `etapa04/RELATORIO_04_2.md` | `docs/stages/04-pipeline/REPORT_04_2.md` |
| `etapa04/RELATORIO_04_3.md` | `docs/stages/04-pipeline/REPORT_04_3.md` |
| `etapa04/RELATORIO_04_4.md` | `docs/stages/04-pipeline/REPORT_04_4.md` |
| `etapa04/RELATORIO_04_5.md` | `docs/stages/04-pipeline/REPORT_04_5.md` |
| `etapa04/RELATORIO_04_6.md` | `docs/stages/04-pipeline/REPORT_04_6.md` |
| `etapa04/RELATORIO_ETAPA04_FINAL.md` | `docs/stages/04-pipeline/FINAL_REPORT.md` |
| `etapa04/REVISAO_CODIGO_20260930.md` | `docs/stages/04-pipeline/CODE_REVIEW_20260930.md` |
| `etapa04/lotes` | `docs/stages/04-pipeline/batches` |
| `etapa04/reconciliacao` | `docs/stages/04-pipeline/reconciliation` |
| `etapa04/resultados` | `docs/stages/04-pipeline/results` |
| `etapa05/CONSOLIDACAO_POS_05.md` | `docs/stages/05-analysis/POST_05_CONSOLIDATION.md` |
| `etapa05/CONTRATO_ANALITICO.md` | `docs/stages/05-analysis/ANALYTICAL_CONTRACT.md` |
| `etapa05/PLANO_ETAPA05.md` | `docs/stages/05-analysis/PLAN.md` |
| `etapa05/RELATORIO_05_1.md` | `docs/stages/05-analysis/REPORT_05_1.md` |
| `etapa05/RELATORIO_05_2.md` | `docs/stages/05-analysis/REPORT_05_2.md` |
| `etapa05/RELATORIO_05_3.md` | `docs/stages/05-analysis/REPORT_05_3.md` |
| `etapa05/RELATORIO_05_4.md` | `docs/stages/05-analysis/REPORT_05_4.md` |
| `etapa05/RELATORIO_05_5.md` | `docs/stages/05-analysis/REPORT_05_5.md` |
| `etapa05/RELATORIO_05_6.md` | `docs/stages/05-analysis/REPORT_05_6.md` |
| `etapa05/RELATORIO_D1.md` | `docs/stages/05-analysis/REPORT_D1.md` |
| `etapa05/RELATORIO_ETAPA05_FINAL.md` | `docs/stages/05-analysis/FINAL_REPORT.md` |
| `etapa05/resultados` | `docs/stages/05-analysis/results` |
| `auditoria/AUDITORIA_TECNICA_COMPLETA.md` | `docs/audits/TECHNICAL_AUDIT.md` |
| `auditoria/CONTRATO_API_ELOTECH.md` | `docs/audits/ELOTECH_API_CONTRACT.md` |
| `auditoria/PLANO_CORRECOES_AUDITORIA.md` | `docs/audits/AUDIT_FIX_PLAN.md` |
| `auditoria/RELATORIO_POS_AUDITORIA.md` | `docs/audits/POST_AUDIT_REPORT.md` |
| `auditoria/REVISAO_CRITICA_RESPOSTA.md` | `docs/audits/CRITICAL_REVIEW_RESPONSE.md` |
| `auditoria/prova_real/RELATORIO_PROVA_REAL.md` | `docs/audits/source-check/REPORT.md` |
| `auditoria/prova_real` | `docs/audits/source-check` |
| `auditoria/resultados` | `docs/audits/results` |
| `auditoria` | `docs/audits` |
| `esic/PEDIDO_ESIC_rascunho.md` | `docs/foi-requests/FOI_REQUEST_DRAFT.md` |

Inside `data/snapshots/`, the store layout (`coletas/`, `objetos/`) is unchanged: the database records each
manifest path relative to the store root.
