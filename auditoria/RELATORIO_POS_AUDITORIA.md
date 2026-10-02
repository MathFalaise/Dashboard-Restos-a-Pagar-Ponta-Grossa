# Relatório pós-auditoria técnica

Data: 02/10/2026. Ramo `auditoria-tecnica`, criado de `main` (`333ab3d`).

Documentos de base: `AUDITORIA_TECNICA_COMPLETA.md` (achados) e `PLANO_CORRECOES_AUDITORIA.md` (grupos G1 a G8 e adiados). Evidências em `auditoria/resultados/` e nos JSON de `auditoria/`.

**Resumo:**
- **Implementado:** 27 achados corrigidos ou cobertos, em 8 grupos, cada um com teste que **falha no código anterior** e passa no novo.
- **Dados:** nenhum dado bruto, snapshot, regra, fórmula, hash ou valor homologado mudou. O banco ativo **não foi alterado** (`hash_camada0` `733670693c01d015`, esquema v4, mesmas execuções).
- **Correções que mudaram resultado:** nenhuma.

## 1. Comparação antes × depois

| Verificação | Antes (linha de base) | Depois |
|---|---|---|
| Testes de produção | 353 passed (174 s) | **397 passed** (252 s, com 2 leituras do armazém real a mais) |
| Testes da investigação | 26 passed | 26 passed |
| `verificar` (banco ativo) | sem problemas | sem problemas (agora também campo a campo e órfãos) |
| `portoes` (banco ativo) | apto (7 portões, 2 sem verificação, não destacados) | apto, `apto_sem_ressalvas=false`, `nao_verificados=[camada_bruta_preservada, testes]`; 11 portões, os 4 novos aprovados |
| `PRAGMA integrity_check` / `foreign_key_check` | ok / 0 | ok / 0 |
| `hash_resultado` (reconstrução do armazém com o código novo) | `2f6b4e29…` / `b8a0b2ed…` | **iguais** |
| Estado × homologação 04.6 | 0 diferenças (5.575 valores) | **0 diferenças** |
| Estado × pré-auditoria | — | **0 diferenças**: bruto, armazém, derivações, camada painel e tela |
| Telas da Etapa 05 × camada painel | 100.201 valores, 0 problemas (05.7) | 100.201 valores, 0 problemas |
| Duas reconstruções independentes | **diferiam** em `rreo_extracao` (texto com `set`) | **equivalentes em tudo** (`comparar-bancos`) |
| Coletor na API real (armazém temporário) | — | entidade 1: 3 páginas + segunda leitura idêntica, completa; entidade 5: 1 página; entidade 51 inexistente: completa com observação |
| Interface (19 chamadas, mediana) | ≤ 0,30 s | ≤ 0,35 s (variação de medição; nenhuma consulta mudou) |
| `processar` (normalização + derivação) | 10,8 s | 11,0 s |
| `verificar` / `portoes` | 0,9 s / ~2 s | 1,1 s / 6,5 s (recálculo dos hashes e órfãos) |

## 2. Problemas encontrados e corrigidos

| Grupo | IDs | Natureza | Correção | Teste (falha no código anterior) |
|---|---|---|---|---|
| G1 migrações | MIG-01 | BUG | migração = uma transação explícita (BEGIN/COMMIT/ROLLBACK) | `test_auditoria.py` (3) |
| G1 | MIG-02 | BUG | banco novo montado em temporário e publicado no fim; arquivo sem versão de esquema recusado sem alteração | idem |
| G2 HTTP | HTTP-01 | BUG | só `FalhaTransitoria`, `TimeoutError` e `ConnectionError` repetem; TLS e URL inválida → `ErroDeRede` sem repetição; erro de programação propaga | `test_auditoria_api.py` |
| G2 | HTTP-02 | RISCO | `Retry-After` em data HTTP | idem |
| G3 paginação | COL-01 | RISCO (alto) | proíbe registro idêntico entre páginas; exige ordem (anoempenho, empenho) crescente na troca de página; segunda leitura das coletas de várias páginas, com hashes no manifesto (`segunda_leitura`), fora da normalização | idem (casos 1–8 da fase 15) |
| G3 | COL-02, COL-03, COL-04 | RISCO / BUG | `number`, `numberOfElements`, `size` e `totalPages` conferidos; `totalElements` obrigatório; sem requisição fora do intervalo | idem |
| G3 | COL-05 | RISCO | observação para entidade ou exercício fora do catálogo vigente | idem |
| G4 vigência | CLI-01 | BUG | `rp.instante()` único (CLI, derivação, painel); a derivação recusa forma não canônica | `test_auditoria_processamento.py` |
| G4 | DET-01 | BUG | mensagem com `sorted` | idem (subprocessos com `PYTHONHASHSEED` 1–4) |
| G5 | NORM-02 | RISCO | valor diferente na mesma célula do RREO → `LayoutDesconhecido` registrado | idem |
| G5 | DER-01 | BUG latente | movimentação só de snapshot completo | idem |
| G5 | DB-03 | RISCO | `semear` confere o catálogo banco × código e recusa divergência (`CatalogoDivergente`) | idem |
| G6 portões | DB-01 | RISCO (alto) | portão `hash_resultado_confere`: recalcula o hash da última derivação de cada vigência | `test_auditoria_integridade.py` |
| G6 | DB-02a | RISCO | portão `integridade_relacional`: `foreign_key_check` + 8 relações sem FK, inclusive os uids de `coletas_json` | idem |
| G6 | NORM-01 | RISCO | portão `campos_monetarios_ausentes` (o comportamento homologado, ausência = 0, continua) | idem |
| G6 | DER-02 | RISCO | portão `lancamento_desconhecido` | idem |
| G6 | POR-01 | RISCO | `nao_verificados` e `apto_sem_ressalvas`; `apto` e código de saída mantidos | idem |
| G6 | REC-01 | RISCO | `verificar` compara cada coleta com o manifesto campo a campo | idem |
| G6 | ARM-01 | RISCO | `verificar` relata objeto sem manifesto e temporário abandonado (nunca apaga) | idem |
| G7 | DET-02 | RISCO | `rp/equivalencia.py` + `rp comparar-bancos`: impressões estáveis da camada 0, da normalização (por tabela) e das derivações; `hash_camada0` antigo mantido | `test_auditoria_equivalencia.py` |
| G8 | DEP-01 | DÍVIDA | `app/requirements-lock.txt` com as versões exatas do ambiente homologado (nenhuma atualização) | — |
| G8 | REP-01 | DÍVIDA | `backups/*.sqlite` no `.gitignore` (os 4 versionados continuam) | — |

**Defeito do próprio código novo, achado nos testes e corrigido antes do commit:**
- **Problema:** com uma linha derivada órfã, recalcular o hash levantava `KeyError` e derrubava o `portoes`, em vez de reprová-lo.
- **Correção:** o portão trata `KeyError` e `TypeError` como "não confere", com o motivo.
- **Cobertura:** `test_DB02_…`.

**Testes antigos alterados (nenhum apagado):**

| Teste | Mudança | Motivo | Intenção |
|---|---|---|---|
| `test_coletor.py::test_repete_em_503_e_completa` | 4 → 7 chamadas | segunda leitura | preservada |
| `test_coletor.py::test_pausa_minima_entre_requisicoes` | 2 → 5 pausas | idem | preservada |
| `test_seguranca.py::test_servidor_que_ignora_page_nao_prende_o_coletor` | recusa na 2ª chamada (pelo `number`), não na 3ª; ganhou um caso sem `number`, que mantém a trava antiga pela soma | detecção mais cedo | preservada |

## 3. Problemas não corrigidos (e por quê)

| ID | Motivo | Classe |
|---|---|---|
| DB-02b, DB-04, DB-05: migração v5 com FKs nas tabelas derivadas, chaves em `anomalia`/`verificacao`/`espelhamento_par`, gatilhos de `regra` (DELETE) e `anomalia_tipo` | muda `esquema_versao` e, portanto, o `hash_camada0` homologado; exige reconstruir tabelas de 600 mil linhas no banco ativo. A proteção equivalente por leitura já está no portão `integridade_relacional` | P2, com decisão |
| REC-02: SHA do manifesto no banco | migração de esquema | P2 |
| NORM-01: ausência monetária como NULL | **REGRA HOMOLOGADA A REVISAR**: muda esquema e derivação; o portão impede a carga até a decisão | P2 |
| inscrição negativa fora das faixas (a)/(b)/(f)/(g) | **REGRA HOMOLOGADA A REVISAR**; 0 casos hoje | P2 |
| PNL-02: `pares` da camada painel sem disponibilidade | muda a saída que a homologação compara (a interface já trata) | P2 |
| DB-06: `coletas_json` relacional | migração; o portão já confere os uids | P2 |
| DB-07: retenção de execuções | política operacional do responsável | P2 |
| CI | proposta da consolidação pós-05 aguarda decisão | P2 |
| hashes de pacote na trava | exige baixar pacotes (autorização) | P2 |
| bruto fora do Git | decisão de privacidade (repositório público) | decisão |
| COL-06, COL-07, HTTP-04, NORM-03, NORM-04, DER-03, DER-04, MIG-03, PNL-01 | baixo risco, ou mudariam o hash homologado (DER-04) | P3 |

## 4. Alterações por área

**Banco** (`rp/banco.py`):
- migração e criação atômicas;
- `versao_esquema` tolerante a arquivo sem tabela;
- `verificar` campo a campo;
- **esquema inalterado** (v4).

**API e coletor** (`rp/http.py`, `rp/coletor.py`, `rp/snapshots.py`):
- classificação de erros e `Retry-After` em data;
- contrato da página;
- detecção de duplicação, deslocamento e ordem;
- segunda leitura;
- observação de catálogo;
- campo `segunda_leitura` no manifesto. É aditivo: manifestos antigos continuam válidos, e o banco e a normalização ignoram o campo.

**Normalização e derivação** (`rp/normalizar.py`, `rp/derivar.py`, `rp/regras.py`, `rp/__init__.py`, `rp/cli.py`, `rp/painel/consulta.py`):
- conflito de célula do RREO registrado;
- mensagem determinística;
- vigência canônica;
- movimentação só de snapshot completo;
- catálogo conferido.

**Verificação** (`rp/portoes.py`, `rp/armazem.py`, `rp/equivalencia.py`):
- 4 portões novos;
- campos `nao_verificados` e `apto_sem_ressalvas`;
- órfãos e temporários no armazém;
- comando `comparar-bancos`.

**Desempenho:**
- nenhuma consulta da camada painel mudou;
- os portões ficaram 4 s mais lentos (recálculo de hash e órfãos);
- a coleta de cortes com várias páginas dobra as leituras dessas páginas (entidade 1: 3 → 6 requisições por corte).

**Segurança:**
- o erro de TLS deixa de ser repetido como "rede";
- erro de programação não é mais mascarado.

**Testes:** 5 arquivos novos (`test_auditoria.py`, `test_auditoria_api.py`, `test_auditoria_processamento.py`, `test_auditoria_integridade.py`, `test_auditoria_equivalencia.py`), com 44 testes ao todo (353 + 44 = 397).

**Documentação:** `app/README.md`:
- proteções novas;
- portões novos;
- `comparar-bancos`;
- arquivo de trava.

## 5. Impacto

| Área | Efeito |
|---|---|
| Dados brutos, snapshots, armazém | nenhum |
| Regras, fórmulas, parâmetros, governança | nenhum (o catálogo gravado é conferido, não alterado) |
| `hash_resultado` | nenhum (reproduzido por reconstrução) |
| `hash_camada0` | nenhum (banco ativo intacto) |
| Normalização | só o texto de erro de PDF não lido passa a ser ordenado (`['L', 'c', …]` em vez de ordem variável). Muda em normalizações **novas**; a gravada no banco ativo não foi tocada |
| Interface e camada painel | nenhum valor (0 diferenças em 5.575 + 100.201 valores) |
| Próxima carga | a coleta pode sair `incompleta` onde antes sairia `completa`, se a base mudar durante a paginação ou se a API mudar de contrato. Esse é o efeito desejado; a observação diz o motivo |

## 6. Respostas às duas perguntas da auditoria

**1. Se um valor for contestado daqui a dois anos, dá para demonstrar a origem e reproduzi-lo?** Sim, com as ressalvas abaixo. A cadeia é:
- valor da tela → camada painel → derivação (regra, versão, parâmetros no banco, agora conferidos com o código) → registro normalizado (posição de origem) → resposta HTTP (URL, cabeçalhos, hora) → bytes no armazém (SHA-256) → manifesto;
- `comparar-bancos` prova que um banco reconstruído do armazém é o mesmo, camada a camada;
- `hash_resultado_confere` prova que as tabelas derivadas não mudaram depois da derivação.

**Ressalvas:**
- o manifesto não tem autenticação própria; a prova de que não foi editado é o histórico do Git (REC-02);
- o código que produziu o resultado é identificado pela versão do derivador, sem hash do código. A versão do coletor tem hash do código (P2: gravar `hash_do_codigo` na derivação).

**2. Se a API mudar amanhã, o sistema percebe e impede a carga?** Agora, em boa parte, sim:
- mudança de paginação, ordem, `size`, `number`, total ou formato da página → coleta `incompleta`, com o motivo;
- tipo de lançamento novo, campo monetário que deixa de vir ou campo extra → portões reprovam (os extras ficam registrados em `chaves_extras`);
- entidade ou exercício inexistentes → observação.

**Não percebe:**
- mudança de **semântica** de um campo que mantém nome e tipo (ex.: `pagoProc` passar a incluir estornos). Só a reconciliação com o RREO e as anomalias podem indicar isso, e não com certeza;
- é uma limitação da fonte, sem documentação nem contrato.

## 7. Estado Git

**Ramo:** `auditoria-tecnica`, com 7 commits sobre `main` (`333ab3d`):
1. auditoria e plano;
2. G1;
3. G2/G3;
4. G4/G5;
5. G6;
6. G7;
7. G8, este relatório e as evidências.

**Pendências de envio e de decisão:**
- nada foi enviado ao GitHub; não há PR;
- as tags `etapa-04-final` e `etapa-05-final` não foram tocadas;
- o banco ativo não foi migrado nem reprocessado. O próximo `processar` gera uma normalização com as mensagens ordenadas e a derivação com o mesmo hash. Isso fica para o responsável decidir.
