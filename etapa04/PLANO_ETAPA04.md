# Etapa 04 — Coletor e pipeline (plano aprovado em 29/09/2026)

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
