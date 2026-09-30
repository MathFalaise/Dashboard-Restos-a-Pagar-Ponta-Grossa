# Etapa 04.2 — Processamento (relatório)

Feita em 29/09/2026. **Escopo: exclusivamente processamento.**

- **Feito:** normalização, derivação, versionamento, processamento dos snapshots existentes, testes, reconciliação e documentação.
- **Não feito:** interface, dashboard, indicadores, agendamento, coleta em massa, promoção de regra, decisão sobre espelhamento ou sobre v1/v2.
- **Nenhuma requisição ao portal** nesta subetapa.

## 1. O que foi entregue

| Item | Local |
|---|---|
| Normalização de produção (camada 1) | `app/rp/normalizar.py` |
| Derivação de produção (camada 2), com hash estável | `app/rp/derivar.py` |
| Catálogo de regras (mesmos códigos e versões da Etapa 03) | `app/rp/regras.py` |
| Consultas "como estava em" | `app/rp/consultas.py` |
| Gravação única de snapshot (coletor e importador usam a mesma) | `app/rp/snapshots.py` |
| Importador das Etapas 01/02 (**nesta subetapa só em armazéns temporários**) | `app/rp/importar.py` |
| Comando `python -m rp processar` | `app/rp/cli.py` |
| 26 testes da Etapa 03 **sobre o código de produção** | `app/tests/test_etapa03_em_producao.py` |
| Portões da 04.2 | `app/tests/test_processamento.py` |
| Reconciliação investigação × produção | `etapa04/reconciliacao/reconciliar_04_2.py` → `resultados/04_2_reconciliacao.md` |

**Sobre o importador.** Os 26 testes precisam dos dados brutos das Etapas 01/02. Por isso o importador foi escrito agora, mas **só roda dentro de armazéns temporários** (testes e reconciliação). O armazém real continua com os 10 snapshots da 04.1. A importação real fica para a 04.3, como planejado.

**Versão do coletor:** 0.2.0. O coletor passou a gravar pelo mesmo caminho do importador. As regras de coleta não mudaram, e os 18 testes do coletor continuam passando.

## 2. Portões exigidos e resultado

### 2.1 Bruto → normalizado

| Exigência | Como foi provada | Resultado |
|---|---|---|
| Nenhum registro perdido | Por snapshot: Σ `content` = `totalElements` = linhas normalizadas | 82.988 = 82.988 |
| Nenhum registro inventado | Cada linha normalizada corresponde a exatamente um item do bruto, pela posição (resposta, índice) | 82.988 = 82.988 |
| Valores em centavos preservados | Os 10 campos monetários de **cada** registro: centavos = valor bruto × 100, exato (Decimal) | 829.880 comparações, 0 diferenças |
| Demais campos | Os 21 campos restantes de cada registro iguais ao bruto; chaves ausentes registradas | 0 diferenças |
| Posição/origem preservada | (resposta, índice) de cada linha = posição no bruto | conferido |
| Snapshots imutáveis | Hash de todas as tabelas da camada 0 + todos os arquivos do armazém, antes e depois de processar | idênticos |
| Snapshot com falha não processado | Resposta HTML → contada como `ignoradas_sem_pagina`, sem linhas e sem visões | conferido |
| Duplicata não descartada | Mesma chave duas vezes → 2 linhas normalizadas + 2 derivadas + anomalia `CHAVE-DUP` | conferido |

### 2.2 Normalizado → derivado

F1–F3, S1–S4, categorias, anomalias, pares espelhados e as visões publicada, analítica e por entidade foram validados de duas formas:
- pelos 26 testes da Etapa 03 executados sobre a produção;
- pela reconciliação linha a linha (seção 3).

### 2.3 Todas as regras lado a lado, sem promoção

- Cada derivação calcula todas as combinações: **RREO-COL v1 e v2**, cada uma com as visões por entidade e publicada, e com as analíticas **CONS-PAR v1 e v2**.
- As regras experimentais continuam `uso = experimental`. Nenhuma virou padrão.
- `derivacao_execucao.regras_json` lista todas as regras do catálogo. Testado.

### 2.4 Reprodutibilidade

| Teste | Resultado |
|---|---|
| Mesma normalização derivada duas vezes | mesmo `hash_resultado` |
| Nova normalização + nova derivação | mesmo hash |
| **Banco reconstruído só com os manifestos do armazém** (ids internos diferentes) + processamento | **mesmo hash** |
| Relógio trocado (`agora` = 2099) | mesmo hash |
| **Banco ativo real**, processado duas vezes | `03d4848a6366…` nas duas execuções |

Como o hash não depende de ids internos:
- ele é calculado sobre identificadores estáveis: `snapshot_uid`, ordem da resposta e índice do registro;
- as regras entram como código + versão;
- os campos JSON guardam `snapshot_uid`, não id.

O que o resultado não usa:
- **data/hora:** a única é o carimbo da execução, que não entra no hash;
- **ordem aleatória:** toda consulta tem `ORDER BY`;
- **estado externo:** não há leitura de rede nem de arquivo fora do banco.

O resultado depende só do conjunto de snapshots e do catálogo de regras.

### 2.5 Os 26 testes sobre o código de produção

`app/tests/test_etapa03_em_producao.py` tem as mesmas asserções e os mesmos números da Etapa 03. **Nada é importado de `etapa03/`.** O caminho inteiro é de produção: importador → armazém → banco v2 → normalização → derivação.

| Conjunto | Resultado |
|---|---|
| 26 testes da Etapa 03 sobre **produção** | **26/26** |
| 7 portões específicos da 04.2 | **7/7** |
| 18 testes do coletor (04.1) | **18/18** |
| **Total em `app/tests`** | **51/51** |
| 26 testes originais da Etapa 03 sobre a investigação (inalterados) | 26/26 |

Logs em `resultados/04_2_testes_producao.txt` e `resultados/04_2_testes_investigacao_etapa03.txt`.

## 3. Reconciliação investigação × produção

```text
bruto Etapas 01/02 → pipeline de investigação (etapa03/validacao) → ESPERADO
bruto Etapas 01/02 → importador + pipeline de produção (app/rp)   → OBTIDO
```

- Os snapshots são pareados **pelo conteúdo** (tipo, horário e SHA-256 de cada resposta): 197 de 197 pareados.
- A comparação é **linha a linha** e ignora ids internos e nomes de versão.
- Relatório completo em `resultados/04_2_reconciliacao.md`.

| Tabela | Linhas | Esperado == obtido |
|---|--:|---|
| `rp_registro` | 82.988 | **SIM** |
| `movimentacao_lancamento` | 2.004 | **SIM** |
| `rreo_valor` | 517 | **SIM** |
| `entidade_ref` / `exercicio_ref` | 10 / 11 | **SIM** |
| `rp_derivado` | 82.988 | **SIM** |
| `movimentacao_interpretada` | 2.004 | **SIM** |
| `anomalia` | 10.837 | **SIM** |
| `espelhamento_par` | 751 | **SIM** |
| `visao_valor` | 1.020 | **SIM** |
| `conciliacao_rreo` | 216 | **SIM** |
| `verificacao`: verificados e falhas | 34 | **SIM** |
| `verificacao`: qual snapshot serviu de abertura na continuidade | 34 | **diferença documentada** (abaixo) |

**A única diferença, e por quê.**
- A verificação de continuidade (fechamento de 2025 → abertura de 2026) precisa de *um* snapshot que comece em 01/01/2026. Existem vários, e todos dão a mesma abertura, porque a abertura não depende de `dataFinal` (Etapa 02 §8, confirmado).
- A investigação usava "o último inserido no banco", critério que depende da ordem de carga.
- A produção usa **"o de maior `dataFinal`, depois o mais recente"**, critério estável.
- Os números verificados e as falhas são idênticos (5.878 empenhos, 0 falhas).

**Casos relevantes, esperado × obtido: 8 de 8 idênticos.**
- 11963/2016;
- 5659/2025;
- pares de 2025 por relação × lado;
- pares de 2026 por lado;
- conciliação do 4º bim/2026 (h −345.479,56; i −237.728,25);
- conciliação consolidada de 2025 com RREO-COL v2;
- visão analítica de 2025 com v2 × v2 (g = 205.182.902,53; L = 20.341.471,66);
- anomalias por tipo.

**Snapshots reais da 04.1** (banco ativo, processados com `python -m rp processar`):
- A listagem real (coletada às 21h35) tem os mesmos bytes das duas coletas da Etapa 02 do mesmo corte.
- Os registros normalizados e derivados são **idênticos** aos da investigação: 4.557 de 4.557, contra cada uma das duas.
- A conciliação do PDF real do 4º bim/2026 é **idêntica**: 24 de 24 linhas (2 regras × 12 colunas).

**Resultado: ESPERADO == OBTIDO.**

## 4. Estado do banco ativo

| Item | Valor |
|---|---|
| Local | `C:\Users\maped\RestosAPagar_local\banco\restos_a_pagar.sqlite` |
| Backup antes de processar | `backups/20260929-233213_antes-processamento-04-2.sqlite` |
| Camada 0 | 10 snapshots, 12 objetos (inalterados) |
| Execuções | normalização 1 e 2, derivação 1 e 2, com o mesmo hash |
| Integridade (`verificar`) | nenhum problema |

## 5. Limitações e pendências

1. **Execuções se acumulam.** Cada `processar` grava uma normalização e uma derivação novas. A política permite apagar execuções **inteiras** (nunca linhas), mas o comando de limpeza ainda não existe. Pode entrar na 04.3, se você quiser.
2. **Processamento completo a cada execução.** Leva cerca de 10 s com 83 mil registros. O processamento incremental é otimização para quando o volume crescer, sem mudar o modelo.
3. **Extrator do RREO** continua dependente do layout do PDF. Se o layout mudar, a transcrição falha de forma explícita (`LayoutDesconhecido`), nunca em silêncio.
4. **Critério de abertura da continuidade:** a diferença documentada na seção 3. É uma escolha de implementação, não de regra.
5. Continuam **sem decisão** (fora do escopo): espelhamento, v1 × v2, lacuna (h)/(i), e-SIC.

## 6. Próxima subetapa proposta: 04.3 — carga controlada

- Importar para o **armazém real** os dados brutos das Etapas 01/02 como snapshots históricos, com o importador testado nesta subetapa. Carimbo aproximado identificado.
- Coletar um conjunto **pequeno e definido** para validar coleta e processamento reais juntos. Sugestão:
  - todas as entidades (1, 4, 5, 8, 15) no corte de 2025 fechado e no corte atual de 2026;
  - PDFs do Anexo VII de 2025 e 2026 que faltam.
- **Portão:**
  - a conciliação com o RREO sobre o armazém real igual à da Etapa 03;
  - os 51 testes;
  - `verificar` sem problemas;
  - hash estável entre duas execuções.
- Ainda sem agendamento, sem coleta 2016–2024 e sem interface. Essas ficam para a 04.4.
