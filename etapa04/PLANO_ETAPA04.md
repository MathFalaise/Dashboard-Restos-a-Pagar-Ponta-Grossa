# Etapa 04 — Coletor e pipeline (plano aprovado em 29/09/2026)

> **Atualização de 01/10/2026 (Subetapa 04.7).** O texto abaixo, até a tabela "Subetapas" inclusive, é o plano original aprovado em 29/09/2026 e foi mantido sem alteração. A estrutura que a Etapa 04 efetivamente teve (04.1 a 04.7), com as subetapas acrescentadas depois, está na seção "Estrutura real da Etapa 04", no fim deste arquivo.

## Decisões

| Item | Decisão |
|---|---|
| Banco | SQLite |
| Banco ativo | local, **fora do OneDrive**: `C:\Users\maped\RestosAPagar_local\banco\` |
| Backup | automático antes de mudança estrutural + cópia periódica; snapshots brutos preservados fora do banco |
| Princípio | **se o banco for perdido, ele é reconstruído a partir dos snapshots brutos** |
| Carga inicial | 2016–2026 |
| Entidades | 1, 4, 5, 8 e 15. O coletor aceita qualquer entidade; a primeira execução é controlada |
| 2024 adicional | sim, entidades 1 e 15, como validação controlada das regras experimentais |
| Movimentação | sob demanda |
| RREO-COL v1 (API) e v2 (RREO) | as duas calculadas e identificadas |
| Regras experimentais | **nenhuma promovida a padrão durante a Etapa 04** |
| e-SIC | enviado em paralelo pelo usuário (rascunho em `esic/`) |
| Interface e indicadores | ainda não |

## Onde fica cada coisa

| Caminho | Conteúdo | Sincronizado? |
|---|---|---|
| `app/` (projeto) | código de produção, testes, `config.toml` | sim (OneDrive) |
| `snapshots/` (projeto) | bruto imutável: objetos comprimidos + manifestos | sim: arquivos gravados uma vez, e a sincronização serve de cópia fora da máquina |
| `backups/` (projeto) | cópias do SQLite, gravadas uma vez | sim |
| `C:\Users\maped\RestosAPagar_local\banco\` | SQLite **ativo** | **não** |
| `C:\Users\maped\RestosAPagar_local\logs\` | logs de execução | não |

## Subetapas (cada uma termina com validação e PARADA para aprovação)

| Subetapa | Conteúdo | Portão de qualidade |
|---|---|---|
| **04.1** | coletor mínimo: HTTP, armazém de snapshots, camada 0 no SQLite, reconstrução, backup, CLI; coleta real mínima | testes do coletor + 26 testes da Etapa 03 + coleta real conferida byte a byte com a Etapa 02 |
| 04.2 | processamento: normalização e derivação de produção sobre o esquema do app | 26 testes reproduzidos **sobre o pipeline de produção** |
| 04.3 | carga controlada: importar Etapas 01/02 + coleta de um conjunto pequeno (ex.: entidade 1, 2025–2026) | conciliação com o RREO igual à da Etapa 03 |
| 04.4 | expansão: 2016–2026, entidades 1/4/5/8/15, e 2024 das entidades 1 e 15 | portões anteriores + verificações a cada lote |

## Estrutura real da Etapa 04 (atualizada em 01/10/2026)

O plano de 29/09/2026 previa quatro subetapas (04.1 a 04.4) e a decisão "Interface e indicadores: ainda não". Durante a execução, o responsável acrescentou três subetapas e pediu duas revisões fora do fluxo. **As subetapas 04.5, 04.6 e 04.7 não existiam no plano original.**

| Subetapa | Conteúdo | Portão de qualidade | Origem | Relatório |
|---|---|---|---|---|
| 04.1 | Coletor e armazenamento bruto: HTTP, armazém de snapshots, camada 0 no SQLite, reconstrução, backup, CLI; coleta real mínima | testes do coletor + 26 testes da Etapa 03 + coleta real conferida byte a byte com a Etapa 02 | plano original | `RELATORIO_04_1.md` |
| 04.2 | Processamento: normalização e derivação de produção | 26 testes reproduzidos sobre o pipeline de produção | plano original | `RELATORIO_04_2.md` |
| 04.3 | Carga controlada: importação das Etapas 01/02 + coleta controlada de 2025–2026 | conciliação com o RREO igual à da Etapa 03 | plano original | `RELATORIO_04_3.md` |
| 04.4 | Expansão da carga: 2016–2026, entidades 1/4/5/8/15, 2024 das entidades 1 e 15 | portões anteriores + verificações a cada lote | plano original | `RELATORIO_04_4.md` |
| — | Revisão de código: segurança, correções, otimização, anotações | hashes de resultado idênticos; testes; banco real intocado | fora do fluxo, 30/09/2026 | `REVISAO_CODIGO_20260930.md` |
| — | Revisão corretiva 01–04.4: API Elotech como fonte primária, camada de consulta somente leitura, governança das regras, esquema v4 | hashes de resultado idênticos; testes; nenhuma evidência apagada | fora do fluxo, 30/09/2026 | `CORRECOES_ETAPAS_01_A_04_4.md`, `ARQUITETURA_FONTES.md` |
| 04.5 | Interface pública somente leitura sobre a camada de consulta | testes da interface (sem rede, somente leitura) + suítes completas + bruto, armazém e hashes idênticos | **acrescentada em 30/09/2026** | `RELATORIO_04_5.md` |
| 04.6 | Homologação da interface e dos dados: validação independente dos valores (bruto = painel = tela), portabilidade, instalação limpa, portões de carga | suítes completas + `verificar` + `portoes` apto + comparação pré × pós sem diferença de valor + instalação em ambiente limpo | **acrescentada em 30/09/2026** | `RELATORIO_04_6.md` |
| 04.7 | Encerramento técnico da Etapa 04: plano atualizado, relatório final, ponto de restauração | documentação final + regressão completa + integridade dos dados + estado Git estável + ponto de restauração (tag `etapa-04-final`) | **acrescentada em 01/10/2026** | `RELATORIO_ETAPA04_FINAL.md` |

Decisões do plano original que mudaram depois (o registro está nos relatórios indicados):
- **Interface e indicadores:** "ainda não" no plano. A camada de consulta veio na revisão corretiva; a interface somente leitura, na 04.5.
- **Caminho do banco ativo:** o plano fixava `C:\Users\maped\RestosAPagar_local\banco\`. Desde a 04.6 o padrão é `~/RestosAPagar_local` (nesta máquina, a mesma pasta), configurável por `RP_DADOS_LOCAIS`. Continua fora do OneDrive.
- **Fonte primária:** o plano não hierarquizava as fontes. A revisão corretiva declarou a API Elotech fonte primária e o RREO só fonte de reconciliação.
- **Regras experimentais:** continua valendo "nenhuma promovida a padrão durante a Etapa 04". RREO-COL v1 e CANC v1 passaram a "não recomendada" por decisão de governança, sem editar a tabela de regras.

O consolidado da etapa está em `RELATORIO_ETAPA04_FINAL.md`.
