# Relatório final da Etapa 04 — pipeline de produção de Restos a Pagar

Data: 01/10/2026. Subetapa 04.7 (encerramento técnico). Ramo `subetapa-04.7`, criado do commit homologado da 04.6 (`25adab7`).

Este documento consolida a Etapa 04 e aponta para os relatórios de cada subetapa, que continuam sendo o registro histórico detalhado e não foram alterados. Números só aparecem aqui quando já constam das evidências oficiais (relatórios e `resultados/`) ou foram medidos na própria 04.7 (seção 5).

---

## 1. Objetivo da Etapa 04

As Etapas 01 a 03 descobriram como o Portal da Transparência de Ponta Grossa expõe os Restos a Pagar (API do sistema Elotech/Oxy Transparência), o que significa cada campo e como os registros se relacionam com o RREO Anexo VII. A Etapa 03 validou um modelo de dados com código de investigação.

A Etapa 04 transformou essas descobertas num **pipeline de produção**:
1. coleta auditável, com snapshots brutos imutáveis;
2. normalização e derivação versionadas, com hash de resultado reproduzível;
3. carga histórica de 2016 a 2026;
4. camada de consulta e interface somente leitura;
5. homologação dos valores contra o bruto.

O princípio do plano continua valendo: **se o banco for perdido, ele é reconstruído a partir dos snapshots brutos.**

## 2. Evolução 04.1 → 04.7

As subetapas 04.5, 04.6 e 04.7 foram acrescentadas depois do plano de 29/09/2026 (ver `PLANO_ETAPA04.md`, seção "Estrutura real da Etapa 04").

| Subetapa | Objetivo | Resultado | Portão | Situação |
|---|---|---|---|---|
| 04.1 | Coletor e armazenamento bruto | coletor, armazém de snapshots, camada 0, reconstrução, backup e CLI; coleta real mínima | 18/18 testes do coletor; 26/26 da Etapa 03; coleta conferida byte a byte com a Etapa 02 | aprovada |
| 04.2 | Processamento | normalização e derivação de produção com `hash_resultado` estável | nenhum registro perdido ou inventado (82.988 = 82.988); 26 testes reproduzidos sobre a produção | aprovada |
| 04.3 | Carga controlada | importação das Etapas 01/02; 2025 fechado e 2026; RREOs; exclusão segura de execuções | 61/61 de produção; 26/26; conciliação com o RREO igual à da Etapa 03 | aprovada |
| 04.4 | Expansão da carga | 2016–2026, 8 lotes, 466 snapshots no banco, comparador de snapshots | todos os portões de cada lote OK; 76/76 e 26/26 em cada lote | aprovada |
| — | Revisão de código (fora do fluxo) | segurança, 5 defeitos corrigidos, otimização (processamento de 43,2 s para 11,1 s) | hashes de resultado idênticos; 138/138 e 26/26 | concluída |
| — | Revisão corretiva 01–04.4 (fora do fluxo) | API Elotech como fonte primária; camada de consulta `rp/painel`; governança das regras; esquema v4 | hashes de resultado idênticos; nenhuma evidência apagada | aprovada |
| 04.5 | Interface pública somente leitura | aplicação WSGI da biblioteca padrão, sem JavaScript, sobre a camada de consulta | 207/207 e 26/26; bruto, armazém e hashes idênticos | aprovada; PR #1 aberto, não mesclado |
| 04.6 | Homologação da interface e dos dados | bruto = painel = tela; 7 situações do dado; portabilidade; instalação limpa; `python -m rp portoes` | 257/257 e 26/26 (também em ambiente limpo); `verificar` limpo; `portoes` apto; 0 valores diferentes pré × pós | concluída; PR #2 aberto, não mesclado |
| 04.7 | Encerramento técnico da Etapa 04 | plano atualizado, este relatório, ponto de restauração | documentação final + regressão completa + integridade dos dados + estado Git estável + tag `etapa-04-final` (seção 5) | esta subetapa |

Relatórios: `RELATORIO_04_1.md` a `RELATORIO_04_6.md`, `REVISAO_CODIGO_20260930.md`, `CORRECOES_ETAPAS_01_A_04_4.md`, `ARQUITETURA_FONTES.md` e detalhe dos lotes em `lotes/`.

## 3. Arquitetura consolidada

Fonte primária dos dados operacionais de Restos a Pagar:

```text
ELOTECH (API do Portal da Transparência de Ponta Grossa)
  ↓
COLETOR (python -m rp coletar-*)
  ↓
SNAPSHOTS IMUTÁVEIS (snapshots/: objetos + manifestos, SHA-256; camada 0 no SQLite com gatilhos)
  ↓
NORMALIZAÇÃO (camada 1, valores em centavos, sem interpretação)
  ↓
DERIVAÇÃO (camada 2, regras versionadas, hash_resultado)
  ↓
PAINEL (rp/painel: consulta somente leitura, com natureza, regra, retrato e proveniência)
  ↓
INTERFACE SOMENTE LEITURA (rp/interface: python -m rp interface)
```

Trilha do RREO (publicação oficial independente):

```text
RREO Anexo VII (PDF publicado pelo Município)
  ↓
SNAPSHOT (o PDF guardado como objeto bruto)
  ↓
EXTRAÇÃO (extrator versionado; método registrado em rreo_extracao)
  ↓
RECONCILIAÇÃO (conciliacao_rreo, na derivação)
  ↓
PAINEL / INTERFACE (só conferência e reconciliação, sempre rotulado)
```

**O RREO nunca substitui um valor originado da API Elotech.** Uma divergência aparece como diferença, com a situação da explicação. A 04.6 provou isso em cópias do banco: apagar ou alterar o RREO não muda nenhum indicador da API (`RELATORIO_04_6.md`, seção 8).

Fora do fluxo de dados:
- `python -m rp portoes` verifica, só lendo, se uma carga nova pode ser disponibilizada.
- `python -m rp verificar` confere armazém × banco.

## 4. Estado dos dados

Estado homologado na 04.6 (`resultados/04_6_estado_depois.json`) e conferido igual no início da 04.7 (`resultados/04_7_estado_antes.json`):

| Item | Valor |
|---|---|
| Snapshots (coletas) | 466 no banco; 466 manifestos no armazém |
| Respostas HTTP brutas | 536 |
| Objetos brutos | 375 no banco e 375 arquivos no armazém |
| Versões do coletor | 9 |
| Evidências externas registradas | 0 |
| Esquema | v2, v3, v4 |
| `PRAGMA integrity_check` | `ok` |
| `hash_camada0` | `733670693c01d0153b3f5bbd5761569d93a347fb080d888515af9d00e9478e00` |
| Hash das tabelas do bruto | `coleta` `d1f4f6ea…`, `resposta_bruta` `10261e4d…`, `objeto_bruto` `b7daff63…`, `coletor_versao` `16cdb0d6…` |
| Normalizações | 12 e 13; a 13 leu as coletas até a 466 e tem 228.873 registros de RP |
| Derivações | 21 e 23 (atuais) = `2f6b4e295ce795934f7051fba31d9d3c1b5bc42c8858d4622a3e89ec88e3f2a5`; 22 e 24 ("como estava em" 29/09/2026 23:59:59) = `b8a0b2ed2328bf093f3f44d4a51dd70f0063d2c9c827b981520a8f921f142a68` |
| Regras | 15 versões de regra; 22 decisões de governança |
| Cortes processados | 22 (exercício × data final); total do Município indisponível em 31/01/2026, 31/03/2026 e 31/12/2026, porque só a entidade 1 foi coletada nesses cortes |
| Valores exibidos nas telas | 5.575 elementos `<data>` medidos pelo script de estado |

Sobre o `hash_camada0`:
- até a 04.4 e na revisão de código, o valor era `3fe902f65a54cfb4`;
- a migração para o esquema v4, na revisão corretiva, acrescentou uma linha em `esquema_versao`, que entra nesse hash, e o valor passou a `733670693c01d015…`;
- as tabelas do bruto, uma a uma, não mudaram (`CORRECOES_ETAPAS_01_A_04_4.md`, seção sobre o v4).

A reconstrução a partir de `data/snapshots/` num ambiente limpo reproduziu os dois hashes de resultado (`RELATORIO_04_6.md`, seção 15).

## 5. Validação final (executada na 04.7)

Executada em 01/10/2026 no ramo `subetapa-04.7`, depois de todas as alterações desta subetapa (só documentação), sobre o banco ativo.

| Verificação | Resultado | Evidência |
|---|---|---|
| `python -m pytest tests` (produção) | **257 passed**, 0 falhas | `resultados/04_7_testes_producao.txt` |
| 26 testes da investigação (`docs/stages/03-data-model/validation`) | **26 passed** | `resultados/04_7_testes_investigacao.txt` |
| `python -m rp verificar` | `{"problemas": []}`, código 0 | `resultados/04_7_verificar.txt` |
| `python -m rp portoes` | **apto** (código 0): integridade, snapshots válidos, coleta completa, normalização 13 com as 466 coletas, derivação 23 cobrindo 228.873 de 228.873 registros, proveniência sem órfãos | `resultados/04_7_portoes.json` |
| `PRAGMA integrity_check` | `ok` | `resultados/04_7_estado_depois.json` |
| `hash_camada0` | `733670693c01d0153b3f5bbd5761569d93a347fb080d888515af9d00e9478e00`, igual ao homologado | idem |
| Derivações 21–24 | `hash_resultado` e hashes de visão e conciliação iguais aos homologados | idem |
| Armazém | 466 manifestos e 375 objetos, SHA-256 de cada arquivo igual ao homologado | idem |
| Camada painel e telas | 0 valores diferentes; 0 textos diferentes; 5.575 valores de tela iguais | `resultados/04_7_comparacao_com_homologacao_04_6.json` (04.6 homologado × fim da 04.7) e `resultados/04_7_comparacao_antes_depois.json` (início × fim da 04.7) |
| Código, testes, configuração, snapshots, dados das etapas e relatórios históricos | nenhuma alteração desde `25adab7` (`git diff 25adab7` vazio nesses caminhos) | Git |

O portão `camada_bruta_preservada` do `portoes` fica "não verificável" sem uma referência gravada antes de uma carga nova. A 04.7 não fez carga; a preservação do bruto foi provada pela comparação de estado acima.

O estado do início da 04.7 foi capturado com o mesmo script (`resultados/04_6_estado.py`) e era idêntico, item a item, ao estado final. O arquivo foi descartado por ser duplicata; a comparação está em `04_7_comparacao_antes_depois.json`.

## 6. Segurança e integridade

Proteções homologadas (detalhe em `REVISAO_CODIGO_20260930.md` seção 3, `RELATORIO_04_5.md` e `RELATORIO_04_6.md` seção 11):

- **Camada bruta:**
  - gatilhos impedem UPDATE e DELETE em `coleta`, `resposta_bruta`, `objeto_bruto`, `coletor_versao` e `esquema_versao`;
  - os manifestos são publicados de forma exclusiva e nunca sobrescritos;
  - o hash do objeto é validado antes de virar caminho, e a descompressão tem teto;
  - `verificar` confere SHA-256 de objetos e manifestos.
- **Coleta:**
  - API só em `https`;
  - corpo com teto de 64 MiB e prazo total;
  - redirecionamento não seguido;
  - `Retry-After` limitado;
  - paginação com limite.
- **Processamento:**
  - mudança de regra exige versão nova;
  - parâmetros de regra em tabela imutável;
  - governança com histórico;
  - nenhuma regra experimental compõe indicador;
  - a derivação mais recente de cada vigência é protegida contra exclusão.
- **Banco:**
  - backup antes de mudança estrutural;
  - backup nunca sobrescreve outro;
  - banco ativo recusado dentro do OneDrive;
  - os 7 backups locais de ~743 MB estão preservados por `PRESERVAR.txt`.
- **Interface:**
  - banco aberto só para leitura (URI `mode=ro` + `PRAGMA query_only`): 11 tipos de escrita recusados, e o arquivo fica intacto depois de visitar todas as telas;
  - só GET e HEAD; sem JavaScript; CSP `default-src 'none'`;
  - não chama a API e funciona sem internet;
  - não carrega os módulos de coleta, processamento nem gravação de snapshot;
  - não faz aritmética de valores monetários.
- **Dados pessoais na interface:**
  - listas e totais sem identificação do credor;
  - nome de pessoa física e CPF omitidos;
  - filtro de credor só por CNPJ de pessoa jurídica;
  - não há dado bancário nos dados coletados.

Essas proteções valem para o código e o banco. Os limites delas estão na seção 8 (por exemplo, itens 45 a 49 da revisão de código).

## 7. Portabilidade

Comprovado na 04.6 (`RELATORIO_04_6.md` seções 14 e 15; `resultados/04_6_instalacao_limpa.txt`):

- **Ambiente limpo:** cópia dos arquivos versionados numa pasta fora do OneDrive e um ambiente Python novo, sem pacotes.
- **Sistema e Python:** **Windows** (Windows 11), **Python 3.14.3**.
- **Dependências:** instaladas só as declaradas (`requirements.txt`: `requests==2.34.2` e `pymupdf==1.28.2`; `requirements-dev.txt` acrescenta `pytest==9.1.1`). A interface e a camada painel usam só a biblioteca padrão.
- **Reconstrução:** `reconstruir` a partir de `data/snapshots/` registrou 466 snapshots; `processar` deu os hashes `2f6b4e29…` e `b8a0b2ed…`; `verificar` ficou limpo e `portoes`, apto; 257/257 e 26/26 no ambiente limpo.
- **Configuração:** nenhum caminho da máquina de desenvolvimento é necessário (`~/RestosAPagar_local` ou `RP_DADOS_LOCAIS`).

**Não comprovado:**
- outro sistema operacional (Linux, macOS);
- outra versão do Python. O mínimo declarado, 3.11 (por causa do `tomllib`), nunca foi testado; o ramo POSIX da publicação exclusiva de manifesto nunca rodou (revisão de código, item 31).

## 8. Limitações conhecidas

### 8.1 Da revisão de código (`REVISAO_CODIGO_20260930.md`, seção 7)

Já tratados, com evidência:

| Item | Tratamento |
|---|---|
| 14 | comando `registrar-evidencia` (C9); a tabela continua vazia |
| 17, 18 | RREO-COL v1 e CANC v1 "não recomendadas" (C5, C6) |
| 21 | `regra_parametro` (C8) |
| 22, 23 | em parte: entidade fora do catálogo do exercício não é zero (C12); o catálogo de entidades continua o atual |
| 24 | desatualizado: o projeto está no Git/GitHub |
| 33 | em parte: `pytest` em `requirements-dev.txt` (04.6); as dependências continuam sem hash |
| 36 | `rreo_extracao` (C10) |
| 41 | configuração portátil (04.6) |
| 44 | camada de consulta e interface (C11, 04.5, 04.6) |
| 45 | em parte: camada pública (C15); o bruto continua com os dados como a API devolve |

C9 a C15 são as seções de `CORRECOES_ETAPAS_01_A_04_4.md`.

Continuam abertos (sem mudança desde a revisão):

**Fonte de dados:**
- 1: API sem documentação nem contrato.
- 2: semântica inferida; `canceladoProc` sempre 0.
- 3: a base muda retroativamente; corte histórico = estado atual da base.
- 4: paginação sem ordenação fixa.
- 5: 145 snapshots importados com horário aproximado.
- 6, 7: RREO só da entidade 1 e consolidado; 2016–2024 só o 6º bimestre.
- 8, 9: PDFs de 2016, 2018 e 2019 não lidos pelo extrator de produção.
- 10, 11: o consolidado não detalha por órgão; só o RREO de 2021 da entidade 1 fecha nas 12 colunas.
- 12: diferenças sem causa determinada, entre elas R$ 674.426,01 (2024) e (h)/(i) de 2026.
- 13: natureza das 731 cópias 24xxxxx não determinada; o e-SIC continua em rascunho.
- 15: teste temporal curto.
- 16: comparador sem caso real de mudança, segundo a revisão; não reavaliado depois.

**Regras:**
- 19, 20: CONS-PAR v1/v2 não validáveis; continuam experimentais e fora da interface.

**Arquitetura e engenharia:**
- 25: duas implementações das regras (investigação e produção).
- 26 a 29: renormalização total; backups grandes; crescimento sem limite.
- 30: os testes dependem dos brutos reais das Etapas 01/02.
- 31: só Windows e Python 3.14.
- 32: sem CI, lint ou tipos.
- 34: scripts de lote sem testes, usando funções internas.
- 35: datas como texto ISO com deslocamento fixo.
- 37: a identidade do coletor muda com comentário.
- 38: limites de segurança fixos no código.
- 39: `KeyError` tratado como erro de uso.
- 40: visão `snapshot_rp` sem uso.
- 42: logs sem retenção.
- 43: sem execução automática nem alerta.

**Segurança e dados pessoais:**
- 45, 46: dados pessoais em texto claro no bruto, nos backups e no armazém. O armazém e os brutos ficam no OneDrive e no repositório **público** do GitHub, por decisão do responsável.
- 47: a integridade depende de quem tem escrita na pasta.
- 48: a proteção reconhece só o OneDrive como pasta sincronizada.
- 49, 50: PDF interpretado pelo MuPDF no mesmo processo; PyMuPDF sob AGPL-3.0.
- 51: textos com acento fazem parte do hash.
- 52: o código de investigação não passou pela revisão de segurança.

### 8.2 Da 04.5 e da 04.6

- Servidor `wsgiref` local, de um pedido por vez, sem autenticação, sem HTTPS e sem limite de acesso.
- A reconciliação "como estava em" só existe para datas com derivação própria (hoje, 29/09/2026).
- O total do Município não existe nos cortes em que só a entidade 1 foi coletada (31/01, 31/03 e 31/12/2026). A tela diz isso e não mostra zero.
- Sem gráficos. Evolução, dimensões e fornecedores existem na camada de consulta, mas não são exibidos.
- Sem JavaScript: trocar o exercício exige uma consulta para atualizar a lista de cortes.
- O teste "sem internet" bloqueia a rede dentro do processo, sem desligar a rede do sistema.
- Instalação comprovada só no Windows com Python 3.14.3 (seção 7).

### 8.3 Registros históricos que ficaram desatualizados

Não foram reescritos, porque são históricos. A leitura correta fica aqui:

- **`RELATORIO_04_5.md`, linha de abertura:** diz que o ponto de restauração `b4c7f8a` está "no `main`". Está no `main` **local**; o `main` remoto (`origin/main`) continua em `adc7510`. O `b4c7f8a` chega ao remoto pelos ramos `subetapa-04.5`, `subetapa-04.6` e `subetapa-04.7`.
- **`RELATORIO_04_6.md`, seção 20:** diz "nenhum PR foi criado". Depois do relatório, a pedido do responsável, foi aberto o PR #2 (`subetapa-04.6` → `main`, em 01/10/2026), ainda aberto.

## 9. Pendências para o futuro

### Antes de qualquer publicação externa

- Servidor WSGI de produção, em vez do `wsgiref`.
- HTTPS.
- Controle de acesso e limite de requisições.
- Homologação no ambiente de destino (sistema operacional, versão do Python, caminhos e permissões), já que só Windows + Python 3.14.3 foi comprovado.
- Política de logs e de retenção (itens 42 e 28 da revisão).
- Decisão sobre os dados pessoais no bruto e nos backups versionados (itens 45 e 46) e sobre a licença AGPL do PyMuPDF (item 50) no modelo de publicação escolhido.

### Etapa 05 (evolução funcional e analítica, com planejamento próprio)

- Gráficos e séries de evolução; exibição das dimensões e dos totais por tipo de credor que já existem na camada de consulta.
- Novos indicadores, filtros e comparações.
- Automação de coleta, agendamento e alertas (item 43).
- Ampliação do RREO (outras entidades, outros bimestres, layouts de 2016, 2018 e 2019).
- Incorporação da resposta do e-SIC como evidência externa e eventual decisão sobre as cópias 24xxxxx e as diferenças não determinadas.
- Melhorias de engenharia: CI, lint, hash das dependências, testes dos scripts de lote, unificação das implementações de regra.

### Fora de etapa

- Envio do pedido e-SIC (rascunho v2 em `docs/foi-requests/`), feito pelo responsável, porque exige CPF.
- Integração dos ramos no `main`, depois da revisão humana (seção 10).

## 10. Critério de encerramento

A Etapa 04 está encerrada quando todas as condições abaixo forem verdadeiras ao mesmo tempo, no commit final da 04.7:

1. As subetapas 04.1 a 04.7 estão documentadas, cada uma com o seu relatório, e o plano mostra a estrutura real (`PLANO_ETAPA04.md`).
2. Os relatórios históricos estão preservados, sem alteração.
3. `python -m pytest tests` passa integralmente, e os 26 testes da investigação da Etapa 03 passam.
4. `python -m rp verificar` não acusa problema, e `python -m rp portoes` retorna `apto`.
5. Bruto, armazém e derivações são idênticos ao estado homologado da 04.6, e os valores da camada painel e das telas não mudaram.
6. A árvore de trabalho está limpa, sem temporários, cópias de banco ou caches no commit.
7. O histórico Git está preservado (sem rebase, merge ou force-push), e a tag `etapa-04-final` aponta para o commit final da 04.7.
8. Nenhuma funcionalidade da Etapa 05 foi implementada.
9. As limitações abertas estão documentadas (seção 8).

**Integração recomendada, depois da revisão humana:**
1. Mesclar o PR #1 (`subetapa-04.5`).
2. Mesclar o PR #2 (`subetapa-04.6`), que então passa a conter só `25adab7`.
3. Abrir o PR de `subetapa-04.7` para `main`, que então conterá só o commit da 04.7.

Abrir agora o PR da 04.7 contra `main` faria esse PR carregar de novo os commits dos #1 e #2. O `main` local (`b4c7f8a`, um commit à frente de `origin/main`) pode ser atualizado depois da integração do #1, sem reescrever nada.

---

**A Etapa 04 foi encerrada.** A Etapa 05 deve começar a partir deste ponto estável (tag `etapa-04-final`) e ter planejamento próprio antes de qualquer implementação.
