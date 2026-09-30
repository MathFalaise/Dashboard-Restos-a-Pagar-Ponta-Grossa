# Etapa 04.1 — Coletor mínimo (relatório)

Feita em 29/09/2026, conforme `etapa04/PLANO_ETAPA04.md`. Esta subetapa cobre **só a coleta e a camada bruta**. Normalização e derivação ficam para a 04.2.

## 1. O que foi entregue

| Item | Local |
|---|---|
| Código de produção | `app/rp/`: `config`, `http`, `armazem`, `banco`, `coletor`, `cli` |
| Esquema de produção v2 | `app/rp/esquema.sql` |
| Configuração | `app/config.toml` |
| Testes do coletor (sem rede) | `app/tests/` (18) |
| Instruções | `app/README.md` |
| Banco ativo | `C:\Users\maped\RestosAPagar_local\banco\restos_a_pagar.sqlite` (**fora do OneDrive**) |
| Logs | `C:\Users\maped\RestosAPagar_local\logs\` |
| Snapshots brutos | `snapshots/` no projeto (objetos comprimidos + manifestos, gravados uma vez) |
| Backups | `backups/` no projeto |
| Rascunho do e-SIC | `esic/PEDIDO_ESIC_rascunho.md`, para o usuário enviar (o envio exige CPF) |

O código foi **reescrito** a partir das especificações das Etapas 02 e 03. Nada foi importado de `etapa02/investigacao` nem de `etapa03/validacao`.

## 2. Decisões aplicadas

- **SQLite.** O banco ativo fica em pasta local fora do OneDrive.
- **Snapshots e backups** ficam no projeto. São gravados uma única vez (arquivo temporário + renomear), e a sincronização do OneDrive vira cópia fora da máquina.
- **Princípio "o banco é reconstruível do bruto" implementado e testado:**
  - `python -m rp reconstruir --destino NOVO.sqlite` refaz o banco só com `snapshots/`;
  - nunca sobrescreve um banco existente.
- **Backup:**
  - automático antes de qualquer mudança de versão do esquema;
  - comando `backup` para cópias periódicas, feito com a API de backup do SQLite (cópia consistente).
- **Nenhuma regra experimental foi tocada.** Esta subetapa não interpreta dado.

## 3. Mudanças no esquema: v1 (Etapa 03) → v2 (produção)

Só na camada 0, e só as exigidas pelas decisões da Etapa 04. As camadas 1 e 2 estão idênticas.

| Mudança | Motivo |
|---|---|
| `objeto_bruto` (sha256 do original, tamanho, dados zlib) no lugar de `resposta_bruta.corpo` | Recomendação da Etapa 03 §5.3: comprimir e guardar bytes iguais uma vez só. O snapshot continua existindo por inteiro; não é deduplicação de registros |
| `coleta.snapshot_uid` e `coleta.manifesto` | Cada snapshot tem um manifesto imutável em disco; o banco é reconstruível a partir deles |
| `esquema_versao` | Registro de versões; mudança estrutural exige backup antes (testado) |
| Gatilhos de imutabilidade para `objeto_bruto` e `esquema_versao` | Mesma regra da camada 0 |

## 4. O que o coletor garante

| Regra | Origem |
|---|---|
| Listagem sempre **sem `tipoPesquisa`**, `dataInicial` = 01/01, `size` = 2000 | Etapa 02 §8 e §11 |
| `dataFinal` fora do ano do exercício é **recusada antes de qualquer requisição** | Etapa 02 §8 |
| Paginação até `last`; `totalElements` conferido página a página; soma = total | Etapa 01 §3; Etapa 03 §5.1 |
| A base mudou durante a paginação → snapshot `incompleta` (guardado, nunca vigente) | Etapa 03 §5.1 |
| Pausa mínima de 1,5 s entre requisições | cortesia com o portal |
| Repete em 5xx, 429 e erro de rede, com espera crescente (respeita `Retry-After`); nunca repete 4xx | — |
| Falha também vira snapshot (`falhou`), com as respostas recebidas e o motivo | rastreabilidade |
| Ordem de gravação: objetos → manifesto → banco. Queda no meio é recuperável por `sincronizar` | princípio do bruto |
| Versão do coletor = `0.1.0` + hash dos fontes: qualquer mudança de código gera outra versão registrada | Etapa 03 §5.3 |
| RREO: só baixa PDFs do "Anexo VII – Restos a Pagar" ainda não coletados com sucesso | — |

## 5. Validação

### 5.1 Testes automatizados

| Conjunto | Resultado | Arquivo |
|---|---|---|
| Coletor (`app/tests`, sem rede) | **18/18** | `resultados/04_1_testes_coletor.txt` |
| **Portão:** 26 testes da Etapa 03 | **26/26** | `resultados/04_1_portao_26_testes_etapa03.txt` |

Os 18 testes cobrem:
- paginação completa e parâmetros enviados;
- total que muda durante a paginação → `incompleta`;
- `dataFinal` fora do exercício recusada sem requisição;
- repetição em 503 com espera; nenhuma repetição em 4xx;
- erro de rede esgotando as tentativas;
- pausa entre requisições;
- mesmo conteúdo = 1 objeto e 2 snapshots;
- imutabilidade da camada 0;
- manifesto nunca sobrescrito;
- objeto corrompido detectado;
- reconstrução completa do banco;
- manifesto fora do banco detectado e sincronizado;
- backup íntegro;
- backup automático antes de recusar banco em versão antiga;
- RREO baixando só o Anexo VII e sem repetir;
- PDF inválido virando falha;
- versão do coletor com hash do código.

### 5.2 Coleta real mínima: 12 requisições, 10 snapshots, todos `completa`

Log em `resultados/04_1_log_coleta_real.log`. Comparação com os bytes baixados nas Etapas 01 e 02 (SHA-256):

| Snapshot | Respostas | Igual a |
|---|--:|---|
| Listagem entidade 1, 2026, até 31/08 | 3 | **as duas coletas da Etapa 02** (20h12 e 20h25) |
| PDF RREO 2026, 4º bim, entidade (id 2560662) | 1 | download da Etapa 02 |
| Movimentação 5659/2025 | 1 | Etapa 02 |
| Publicações LRF 2026 | 1 | Etapa 02 |
| Entidades | 1 | Etapa 01 |
| Exercícios da entidade 1 | 1 | Etapa 01 |
| Exercícios das entidades 15, 4, 5, 8 | 4 | (novo; sem referência anterior) |

**6 de 6 comparações com bytes idênticos.** O coletor de produção reproduz exatamente o que as investigações baixaram.

### 5.3 Integridade, reconstrução e backup com os dados reais

- `python -m rp verificar`: **nenhum problema** (armazém × banco, hashes, tamanhos).
- **Reconstrução:** banco novo feito só a partir de `snapshots/` = banco ativo. Mesmos snapshots, mesmas respostas, mesmos objetos, comparados linha a linha. O banco de teste foi apagado depois.
- **Backup real** gravado em `backups/20260929-213626_validacao-04-1.sqlite`.
- **Tamanhos:** armazém 612 KB (12 objetos + 10 manifestos); banco ativo 748 KB.

## 6. Limitações e pendências

1. **Dados das Etapas 01/02 ainda não foram importados** para o armazém. Isso está previsto na 04.3 (carga controlada), com carimbo aproximado identificado.
2. **Não exercitado com o portal real:** HTTP 429/`Retry-After`, 5xx e queda de rede. Só foram testados com o portal falso.
3. **Coletas longas** (anos antigos com 3–4 páginas de 2.000 registros, várias entidades seguidas) ainda não foram feitas. Ficam para as subetapas 04.3/04.4, em lotes.
4. **Snapshots dentro do OneDrive:**
   - os arquivos são gravados uma única vez, mas a sincronização pode segurar um arquivo recém-criado por alguns instantes;
   - o coletor só escreve arquivo novo e nunca reabre um existente para escrita;
   - com o modo "arquivos sob demanda" do OneDrive, ler um objeto antigo pode forçar o download dele. Isso não altera nada, só demora.
5. **Não há agendamento automático** nesta subetapa. As coletas são por comando. O agendamento entra quando a carga estiver validada (04.4).
6. **Sem movimentação em massa:** o coletor só a traz sob demanda, como decidido.

## 7. Próxima subetapa proposta: 04.2 — processamento

- Normalização e derivação de produção (`app/rp/`) sobre o esquema v2, lendo os bytes de `objeto_bruto`, com o catálogo de regras da Etapa 03 **completo, inclusive as versões experimentais, sem promover nenhuma**.
- **Portão:**
  - os 26 testes da Etapa 03 **reproduzidos sobre o pipeline de produção**, com os mesmos números;
  - os 18 testes do coletor;
  - o pipeline aplicado aos snapshots reais desta subetapa tem de dar os mesmos valores que o pipeline da Etapa 03 dá para os mesmos bytes.
- Sem coleta nova além do mínimo, sem interface, sem indicadores.
