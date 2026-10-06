# Relatório da Subetapa 04.6 — homologação do dashboard sobre a fonte Elotech

Data: 30/09/2026. Ramo `subetapa-04.6`, criado a partir de `subetapa-04.5` (`6461ef2`). O PR #1 (04.5 → `main`) continua aberto e não mesclado; por isso a 04.6 parte do ramo da 04.5, e não do `main`.

**Resumo:**
- **Valores validados em três níveis:** cada valor principal da interface foi conferido contra a camada `painel` e contra um recálculo independente, feito direto do JSON bruto da API guardado no armazém. Os três coincidem, centavo a centavo, nos cortes testados.
- **Valores e bruto intactos:** nenhum valor mudou em relação ao estado de partida. São 5.575 valores exibidos nas telas e todos os valores da camada painel. Bruto, armazém e derivações estão idênticos; as únicas diferenças são 27 textos de motivo, agora mais precisos.
- **Correções feitas:**
  - situação de cada dado explícita (7 situações; "não coletado" e "não processado" não se confundem mais);
  - filtro sem resultado mostra "Nenhum resultado encontrado", nunca R$ 0,00;
  - busca por empenho;
  - regra experimental rotulada ANÁLISE EXPERIMENTAL;
  - a interface deixou de somar dois campos por conta própria;
  - título com o tipo de retrato;
  - metodologia completa;
  - configuração sem caminho da máquina de desenvolvimento.
- **Portões de carga nova:** comando `python -m rp portoes`, somente leitura, e procedimento documentado COLETAR → VALIDAR → PROCESSAR → TESTAR → VERIFICAR → DISPONIBILIZAR.
- **Instalação em ambiente limpo:** a cópia limpa fica fora do OneDrive e usa um ambiente Python novo com só as dependências declaradas.
  - O banco reconstruído a partir de `data/snapshots/` reproduz os mesmos hashes: `2f6b4e29…` e `b8a0b2ed…`.
  - A interface respondeu com toda conexão externa bloqueada; nenhuma tentativa de rede foi registrada.
- **Testes:** **257/257** de produção (207 anteriores + 50 novos) e **26/26** da investigação, no repositório e no ambiente limpo. `verificar` sem problemas.

---

## 1. Estado inicial

Registrado antes de qualquer alteração (`resultados/04_6_estado_antes.json`, script `resultados/04_6_estado.py`, que não tem caminho fixo):

| Item | Valor |
|---|---|
| Git | `subetapa-04.5` em `6461ef2`, árvore limpa; `origin/main` em `adc7510`; PR #1 aberto |
| Suítes | 207/207 de produção (148 s) e 26/26 da investigação (`resultados/04_6_baseline_testes_*.txt`) |
| `python -m rp verificar` | sem problemas |
| `PRAGMA integrity_check` | `ok` |
| Camada bruta | `hash_camada0` = `733670693c01d0153b3f5bbd5761569d93a347fb080d888515af9d00e9478e00`; 466 coletas, 536 respostas, 375 objetos, 9 versões de coletor |
| Derivações válidas | 23 (atual) = `2f6b4e295ce79593…`; 24 (29/09/2026) = `b8a0b2ed2328bf09…`; 21 e 22 iguais a elas |
| Armazém | 466 manifestos e 375 objetos, com SHA-256 de cada arquivo |
| Esquema | v2, v3, v4 |
| Painel e telas | 22 cortes; valores de todo corte × escopo (Município e cada entidade), entidades, pares, reconciliação e coerência; 5.575 valores `<data>` das telas |

O baseline passou; as alterações começaram depois dele.

## 2. Auditoria da 04.5

**Arquivos da 04.5** (diff `b4c7f8a..ad0d958`):
- criados: `app/rp/interface/` (`aplicacao.py`, `paginas.py`, `formato.py`, `estilo.css`, `__init__.py`), `tests/test_interface.py` e `tests/test_interface_casos_reais.py`;
- modificados: `rp/painel/consulta.py`, `fontes.py` e `publico.py`, `rp/cli.py`, `tests/conftest.py`, `test_correcoes.py` e `test_casos_reais.py`, `README.md` e `ARQUITETURA_FONTES.md`;
- mais o relatório e as evidências da 04.5.

**Como a aplicação funciona:**
- **Tecnologia:** WSGI da biblioteca padrão (`wsgiref`), HTML gerado no servidor, sem JavaScript. CSP `default-src 'none'`; só GET e HEAD.
- **Início:** `python -m rp interface`, em `127.0.0.1:8050`.
- **Acesso ao banco:** uma conexão `Painel.abrir` por requisição, com URI `mode=ro` + `PRAGMA query_only`. A interface só chama métodos de `rp.painel.Painel`.
- **Indicadores exibidos:** 13, em 4 grupos: inscrição total, processada e não processada; saldo S1, S2 e S3; pagamentos, pago processado e pago não processado, liquidações, cancelamentos e retenções; e número de registros. Calculados, mas não exibidos: estornos de pagamento, evolução, dimensões e fornecedores. Não existem: gráficos e série temporal na tela.
- **Filtros:**
  - exercício, corte, entidade e "como estava em";
  - na lista de empenhos: categoria, fonte de recurso, início da programação, tipo de credor, CNPJ de pessoa jurídica e ordem.
- **Páginas:** resumo, entidades, empenhos, detalhe do empenho, retratos, comparação de retratos, reconciliação (índice e documento), coerência entre publicações, pares espelhados e metodologia.
- **Proveniência:** bloco "Origem do dado" (snapshot, derivação com hash, normalização, resposta HTTP, objeto bruto) e um selo "Fonte · Natureza · Regra" em cada valor.
- **Reconciliação:**
  - no resumo, a conferência compara o saldo S1 com a coluna L;
  - por documento, a tela compara as colunas a–L pelas regras RREO-COL v1 e v2, com PDF, extração e explicação;
  - a coerência compara a coluna L de um exercício com (a)+(f) do seguinte.
- **Escolha do snapshot:** o vigente é o mais recente completo do corte, entre os já processados (`coleta.id <= ultima_coleta_id`).
- **"Como estava em":** limita a escolha a `coletada_em <= data`; a reconciliação histórica exige uma derivação com a mesma vigência.
- **Testes da 04.5:** 22 em `test_interface.py` e 11 em `test_interface_casos_reais.py`.

## 3. Problemas encontrados

| # | Seção da especificação | Problema |
|---|---|---|
| P1 | 17 | Filtro sem registro mostrava os totais do conjunto como **R$ 0,00** (a camada `painel` somava um conjunto vazio como zero) |
| P2 | 9, 10 | "Corte não coletado" e "coletado, mas não processado" eram uma situação só ("corte não coletado ou não processado"); coleta só incompleta também caía nela |
| P3 | 4 | Fórmula duplicada: a coluna "Cancelado" da lista era `cancelado_aproc_c + cancelado_proc_c` somado **na interface** |
| P4 | 17 | Não havia busca por empenho (ano e número) na lista |
| P5 | 20 | Regras experimentais ou não recomendadas apareciam só como "valor analítico (não oficial)", sem o rótulo explícito ANÁLISE EXPERIMENTAL; no detalhe do empenho, o CANC v1 ficava na mesma tabela dos derivados operacionais |
| P6 | 8 | O título das páginas não dizia se o retrato era o estado atual ou "como estava em"; o bloco de retrato não listava os snapshots usados |
| P7 | 19 | Coluna do RREO mostrada só pela letra (a…L); diferença "não determinada" em vermelho, cor de erro |
| P8 | 21 | Metodologia sem seções de snapshots, processamento, retrato atual × histórico e limitações |
| P9 | 22 | `config.toml` com `dados_locais = "C:/Users/maped/RestosAPagar_local"`: outra máquina não roda sem editar o arquivo versionado |
| P10 | 24 | `pytest` usado nos testes, mas não declarado; `requirements.txt` sem explicar para que serve cada pacote |
| P11 | 27 | Nenhuma verificação objetiva antes de disponibilizar uma carga nova |
| P12 | 16 | Sem estilo de foco para teclado; páginas de erro sem `viewport` |
| P13 | 18 | Natureza dos derivados na lista de empenhos era sempre "derivado", inclusive CANC v1 (não recomendada) |

Sem problema:
- valores dos indicadores (seção 6 deste relatório);
- proveniência dos indicadores;
- leitura só com `mode=ro`;
- funcionamento sem internet;
- minimização de dados pessoais;
- desempenho.

## 4. Correções

**Camada `painel` (`rp/painel/consulta.py`)** — só acréscimos. Nenhuma fórmula contábil mudou.
- `SITUACOES_DO_DADO` define 7 situações. Cada entidade de um corte passa a ter `situacao_do_dado` e `retrato_mais_novo_nao_processado`:

  | Situação | Tem valor? |
  |---|---|
  | dado existente | sim |
  | entidade existente sem RP | sim (é o único zero) |
  | entidade inexistente no exercício | não |
  | corte não coletado | não |
  | corte coletado, mas não processado | não |
  | dado indisponível (só coleta incompleta ou com falha) | não |
  | diferença em relação ao RREO | valor mostrado com a diferença |

  O motivo de indisponibilidade lista as entidades por situação (P2).
- `empenhos()`:
  - conjunto vazio devolve `sem_resultado`, a mensagem e totais `None` (P1);
  - novos filtros `anoempenho` e `empenho` (P4);
  - a natureza de cada derivado segue a governança da regra (P13).
- `EXPR_CANCELAMENTOS` é a expressão única do cancelamento, usada no indicador, no agrupamento e na nova coluna `cancelamentos_c` de cada registro (P3).
- Retrato com a lista de snapshots usados (P6). Conferência S1 × L com a situação "divergente" quando há diferença.
- `metodologia()` devolve as datas "como estava em" com derivação própria e as situações do dado.

**Interface (`rp/interface`):**
- **Títulos:** com "(estado atual da base)" ou "(como a base estava em DD/MM/AAAA)". O bloco de retrato mostra o tipo e os snapshots usados (P6).
- **Situação do dado:** em "Entidades abrangidas" e na tela de entidades, com aviso de retrato mais novo ainda não processado. Escopo com zero de verdade traz o aviso "Zero de verdade…" (P2).
- **Empenhos:** campos de busca por ano e número (P4). Conjunto vazio mostra "Nenhum resultado encontrado", a contagem 0 e os snapshots consultados, sem nenhum valor monetário (P1). A coluna "Cancelado" vem da camada `painel` (P3).
- **Detalhe:** seção própria "ANÁLISE EXPERIMENTAL (não oficial)" para regra não operacional (hoje, CANC v1) (P5).
- **Reconciliação:**
  - rótulo de cada coluna do Anexo VII, transcrito da Etapa 02;
  - selo "ANÁLISE EXPERIMENTAL" (RREO-COL v2) ou "ANÁLISE — REGRA NÃO RECOMENDADA" (RREO-COL v1);
  - cabeçalho "API Elotech projetada na coluna (análise)";
  - "não determinada" em roxo, a cor de diferença (P5, P7).
- **Metodologia:** fonte principal, fonte de reconciliação, hierarquia, snapshots, processamento e derivação, retrato atual e histórico, datas "como estava em", situação dos dados, naturezas, regras, limitações, dados pessoais e dicionário (P8).
- **CSS:** foco visível (contorno azul; amarelo no menu), `viewport` nas páginas de erro e ajustes para telas até 640 px (P12).

**Configuração e dependências:**
- `config.toml`: `dados_locais = "~/RestosAPagar_local"`. Nesta máquina, `~` resolve para a mesma pasta de antes.
- `rp/config.py`: expande `~` e aceita a variável `RP_DADOS_LOCAIS`. `reconstruir`, `Painel.abrir` e `portoes` expandem `~` mesmo quando o shell não o faz, como no PowerShell (P9).
- `requirements.txt` comentado. `requirements-dev.txt` novo, com `-r requirements.txt` e `pytest==9.1.1`. Nenhuma versão mudou (P10).

**Portões (`rp/portoes.py`, `python -m rp portoes`)** — seção 16 deste relatório (P11).

**Ajustes em testes anteriores** (a regra da seção 17 contrariava o que eles supunham):
- `test_interface.py::test_10_filtros_nao_alteram_dados` somava o saldo das 4 categorias, inclusive uma vazia, que antes aparecia como R$ 0,00.
  - Agora, para categoria vazia, o teste exige "Nenhum resultado encontrado" e soma zero para ela.
  - A intenção do teste continua a mesma: as categorias repartem o total sem alterar valores.
- Nenhum outro teste anterior foi alterado.
- Um atalho "Pular para o conteúdo" (`href="#conteudo"`) foi retirado em vez de afrouxar o teste de segurança que exige links internos começando por "/". O foco visível foi mantido.

## 5. Arquitetura final

Sem mudança de arquitetura.

```
ELOTECH → COLETA → SNAPSHOT IMUTÁVEL → NORMALIZAÇÃO → DERIVAÇÃO → PAINEL → INTERFACE
RREO    → SNAPSHOT → EXTRAÇÃO → RECONCILIAÇÃO (derivação) → PAINEL → INTERFACE (só conferência)
                                     portoes (somente leitura) ──┘  verifica antes de disponibilizar
```

- A interface só importa `rp.painel`. Teste feito em subprocesso: importar `rp.interface` não carrega `rp.http`, `rp.coletor`, `rp.normalizar`, `rp.derivar`, `rp.importar`, `rp.snapshots`, `rp.execucoes`, `rp.evidencias`, `requests` nem `pymupdf`.
- A interface não tem `SELECT` nem soma ou subtração de campos em centavos (teste por AST).

## 6. Validação dos indicadores

Para cada indicador exibido no resumo, `test_homologacao_real.py` identifica e confere a origem:
- a consulta: `SOMAS` em `consulta.py`;
- a fonte: API Elotech;
- os snapshots: `retrato.snapshots`, conferidos contra uma escolha independente (a coleta completa mais recente do corte);
- a derivação: id e hash;
- a regra: S1, S2 e S3 v1 nos saldos.

O mesmo valor é recalculado **direto do JSON bruto** no armazém: manifesto → objetos → `content[]`, com Decimal → centavos e as fórmulas documentadas na Etapa 02, sem normalização nem derivação. Esse recálculo é comparado com a camada `painel` e com o `<data value>` da página.

**Cortes testados:**
- Município: 2024-12-31, 2025-12-31, 2026-08-31, 2016-12-31 e 2026-04-30;
- entidades: 1 e 15 em 2026-08-31; 5 em 2025-06-30.

Resultado: **bruto = painel = tela** nos 13 indicadores exibidos, em todos os cortes.

O total do Município soma só as entidades cujo catálogo oficial de exercícios contém o exercício. Isso foi conferido a partir do catálogo bruto.

## 7. Validação do Elotech como fonte primária

- **Casos de regressão:** o detalhe de 5659/2025, 11963/2016, 2401751/2023 e o par 1751/2023, e da entidade 5 / 1485/2025 bate campo a campo com o item da API no snapshot mostrado. O S1 também foi recalculado do bruto.
- **Testes anteriores mantidos:** pares 1 × 15 (2025: 20; 2026: 731), divergências (h) e (i) de 2026, R$ 674.426,01 e entidade fora do catálogo.
- **Valores fixados do estado de partida:**

  | Corte | Registros | Inscrição | Saldo S1 | Diferença S1 − L do RREO | Situação da diferença |
  |---|---|---|---|---|---|
  | 2024-12-31 | 6.427 | R$ 162.906.991,67 | R$ 18.974.988,99 | R$ 678.171,65 | parcialmente explicada |
  | 2025-12-31 | 5.878 | R$ 250.551.057,73 | R$ 21.267.174,28 | R$ 925.702,62 | explicada |
  | 2026-08-31 | 5.760 | R$ 205.341.874,51 | R$ 80.844.090,29 | R$ 237.678,75 | não determinada |

- **Hashes:** o banco temporário do teste, montado só do armazém, dá os mesmos hashes do banco ativo: `2f6b4e29…` e `b8a0b2ed…`.

## 8. Validação do RREO como reconciliação

Todos os testes abaixo usam **cópias** temporárias do banco montado do armazém:
- **RREO removido** (`conciliacao_rreo`, `rreo_valor` e `rreo_extracao` apagados): os indicadores ficam idênticos. A tela abre com "sem RREO transcrito", sem valores de conferência.
- **RREO alterado** (+ R$ 12.345,67 em todo valor publicado):
  - os indicadores da API ficam idênticos;
  - a conferência mostra a API igual, o RREO + 12.345,67 e a diferença menor nesse mesmo valor, com situação "divergente";
  - nenhuma coluna da reconciliação "fecha" à força.
- **RREO zerado:** os indicadores continuam iguais à soma da API, e o valor da API nunca é trocado pelo do RREO.

## 9. Proveniência

- **Dado da fonte:** o detalhe mostra endpoint, snapshot, resposta HTTP e SHA-256 do objeto bruto. O teste lê o objeto no armazém, confere o SHA-256 do conteúdo e confirma que a resposta pertence ao snapshot.
- **Valor derivado:** cada um dos 13 cartões de **todos** os cortes processados tem fonte, natureza, cálculo ou regra, snapshots (cada um com manifesto existente no armazém), derivação com hash de 64 dígitos e normalização. Corte indisponível não mostra nenhum cartão.
- **Valor publicado:** o documento do RREO mostra o snapshot do PDF, o SHA-256 (objeto no armazém, começando por `%PDF-`), o extrator `rp-rreo-coordenadas/1`, o PyMuPDF 1.28.2 e a data de emissão.
- **Diferença:** a conferência e a reconciliação mostram os dois lados, com os snapshots da API e o do PDF.

## 10. Snapshots

- **Bruto e armazém:** idênticos antes e depois (comparação arquivo a arquivo e por tabela). Nenhum snapshot foi criado no banco ativo.
- **Derivações:** nenhuma nova no banco ativo; as derivações existentes ficaram idênticas.
- **Retratos antigos:** continuam acessíveis na tela de retratos.
- **Retrato mais novo não processado:** passa a ser sinalizado por entidade.

## 11. Segurança

- **Somente leitura:**
  - pela conexão da interface, SELECT é permitido;
  - INSERT, UPDATE, DELETE, CREATE TABLE, DROP, ALTER, CREATE INDEX, `PRAGMA user_version`, VACUUM e CREATE TEMP TABLE são recusados;
  - depois de visitar todas as rotas, o arquivo do banco tem o mesmo SHA-256 e o mesmo `mtime`, sem `-wal` nem `-journal`.
- **Isolamento:** a interface nunca coleta, processa, deriva ou grava snapshot; os módulos que fazem isso nem são carregados.
- **Dados pessoais:**
  - no detalhe de credores pessoa física reais, o nome e o CPF (inteiro ou mascarado, `****374****`) não aparecem;
  - não há campo bancário;
  - as listas continuam sem identificação do credor.
- **Cabeçalhos:** CSP, `nosniff`, `no-referrer` e `DENY` mantidos. Parâmetros inválidos (incluindo os novos campos de busca) dão 400.

## 12. Desempenho

Banco ativo (`resultados/04_6_desempenho_banco_ativo.json`, 3 execuções):

| Operação | Tempo |
|---|---|
| Abertura | 56–174 ms |
| Troca de exercício | 59–86 ms |
| Filtro de entidade | 39–46 ms |
| Como estava em | 17–52 ms |
| Entidades | 43–49 ms |
| Lista de empenhos | 65–73 ms |
| Filtros combinados | 57–201 ms |
| Busca | 156–201 ms |
| Navegação (página 40) | 175–310 ms |
| Detalhe | 10–30 ms |
| Retratos | 57–113 ms |
| Reconciliação (índice) | 383–659 ms |
| Reconciliação (documento) | 7 ms |
| Pares | 59–81 ms |
| Metodologia | 2 ms |

- No ambiente limpo, pelo HTTP, a tela mais lenta levou 293 ms.
- As listas são paginadas (50 registros), e os totais saem de `SUM` no SQLite.
- Nenhuma consulta passou de 1 s, então **nenhum índice foi criado**, sem otimização especulativa.
- O teste automatizado exige menos de 3 s por operação.

## 13. Responsividade

Verificada no navegador embutido, com o servidor do ambiente limpo:

| Tamanho | Telas |
|---|---|
| Celular (375 px) | resumo, empenhos, detalhe, reconciliação, entidades, metodologia |
| Tablet (768 px) | empenhos, reconciliação |
| Notebook (1280 px) | resumo 2024, detalhe |
| Desktop (painel) | entidades 2016 |

Resultado: nenhuma página mais larga que a tela, nenhum botão, campo ou lista fora da tela e nenhuma fonte menor que 11 px. As tabelas largas rolam dentro do próprio quadro. No celular, os filtros ficam em coluna, com largura total. O selo "ANÁLISE — REGRA NÃO RECOMENDADA" passava da célula no celular e passou a quebrar linha.

**Acessibilidade:**
- um `h1` por página, sem salto de nível de título;
- todo campo dentro de `<label>`, `lang="pt-BR"`, nenhuma imagem;
- foco visível;
- contraste de todas as combinações de cor ≥ 4,87:1 (texto 15,8; texto secundário 6,1; links 6,7; selo de análise 4,87; menu 11,2).

## 14. Portabilidade

- Nenhum código, configuração, CSS ou dependência contém caminho de usuário (teste automatizado).
- Banco e logs: `~/RestosAPagar_local` ou `RP_DADOS_LOCAIS`. Configuração: `RP_CONFIG` ou `--config`. Snapshots e backups: relativos a `app/`. A folha de estilo é lida ao lado do código.
- Os scripts de evidência antigos (`resultados/revisao_corretiva_estado.py` e `04_5_*`) têm caminhos desta máquina. São registros históricos e não foram alterados. Os da 04.6 recebem caminhos por argumento ou pela configuração.

## 15. Instalação

Teste real em ambiente limpo (`resultados/04_6_instalacao_limpa.txt`):

1. **Cópia limpa:** arquivos versionados e novos (`git ls-files -co --exclude-standard`), sem `.git`, sem `__pycache__` e sem o backup de 120,5 MB, numa pasta temporária fora do OneDrive (115 MB).
2. **Ambiente novo:** `python -m venv` sem pacotes, e depois `pip install -r requirements-dev.txt`. Foram instalados só `requests`, `pymupdf`, `pytest` e as dependências deles.
3. **Pasta local:** `RP_DADOS_LOCAIS` apontando para uma pasta temporária.
4. **Reconstrução:** `reconstruir` registrou 466 snapshots, sem problemas (4 s).
5. **Processamento:** `processar` levou 16 s e deu o hash `2f6b4e29…`; `processar --em 2026-09-29T23:59:59-03:00` deu `b8a0b2ed…`.
6. **Conferência:** `verificar` sem problemas e `portoes` apto.
7. **Interface:** subiu com toda conexão de saída bloqueada e passou pelas 22 visitas, com 0 tentativas de rede.
8. **Testes:** 257/257 e 26/26 no ambiente limpo.

Os passos estão em `app/README.md`, seção "Instalação em outra máquina". O PyPI foi usado só para instalar as dependências declaradas.

## 16. Atualização de dados

- **Procedimento documentado** (`app/README.md`, seção "Atualização dos dados"): referência do bruto → backup → coletar → validar → processar → testar → portões → disponibilizar. Nunca "coletar → sobrescrever banco → publicar": a coleta nova é um snapshot a mais, e o retrato anterior continua.
- **`python -m rp portoes`** (somente leitura; código 0 apto, 1 não apto) verifica:
  - integridade do SQLite;
  - armazém × banco;
  - snapshot mais recente de cada corte completo;
  - normalização em dia;
  - derivação atual sobre a normalização mais recente, cobrindo todo registro;
  - proveniência sem órfãos;
  - bruto anterior idêntico à referência gravada com `--gravar-referencia` (o arquivo nunca é sobrescrito).
- **Testes:** o portão de testes é declarado e fica com quem disponibiliza.
- **Verificações da derivação:** entram como informação, porque incluem as diferenças já conhecidas com o RREO.
- **Banco ativo hoje:** apto.

## 17. Testes

Novos (50):
- **`test_homologacao_real.py` (40, sobre o armazém real):**
  - indicadores bruto = painel = tela em 8 cortes;
  - catálogo do Município;
  - valores fixados de 2024, 2025 e 2026;
  - hashes;
  - 5 casos reais contra o JSON;
  - 3 testes de não contaminação pelo RREO;
  - 4 de proveniência;
  - retrato em todos os cortes;
  - 7 combinações de filtro contra o bruto;
  - 5 filtros sem resultado;
  - detalhe e dados pessoais;
  - reconciliação;
  - regras experimentais;
  - desempenho.
- **`test_homologacao.py` (10, sintéticos e de código):**
  - as 7 situações do dado, na camada `painel` e na tela;
  - existente sem RP × inexistente × sem coleta;
  - banco somente leitura, com 11 tipos de escrita;
  - módulos não carregados;
  - nenhuma aritmética de centavos na interface;
  - busca e parâmetros inválidos;
  - configuração versionada;
  - `RP_DADOS_LOCAIS`;
  - portões.

## 18. Resultados

| Portão | Resultado |
|---|---|
| Suíte de produção | **257/257** (`resultados/04_6_testes_producao.txt`) |
| Investigação | **26/26** (`resultados/04_6_testes_investigacao.txt`) |
| Ambiente limpo | 257/257 e 26/26 |
| `python -m rp verificar` | sem problemas |
| `python -m rp portoes` | apto |
| `PRAGMA integrity_check` | ok |
| Camada bruta | `hash_camada0` `733670693c01d015…`, igual ao inicial; tabelas do bruto idênticas |
| Armazém | 466 manifestos e 375 objetos idênticos |
| Derivações | 21–24 com o mesmo `hash_resultado` e os mesmos hashes de visão e conciliação |
| Comparação pré × pós (`resultados/04_6_comparacao_pre_pos.json`) | **0** valores diferentes na camada `painel`; **0** dos 5.575 valores de tela; 27 textos alterados, todos o motivo "corte não coletado ou não processado" → "corte não coletado" (era de fato não coletado; nenhum caso de "não processado" nos dados reais) |

Nenhum valor mudou, então não houve diferença a investigar.

## 19. Limitações

- **Servidor:** local, de um pedido por vez (`wsgiref`), sem autenticação e sem HTTPS. Uma publicação exige um servidor WSGI de produção e homologação própria.
- **Como estava em:** a reconciliação histórica existe só para datas com derivação própria (hoje, 29/09/2026).
- **Sem gráficos:** evolução, dimensões e fornecedores existem na camada `painel`, mas não são exibidos.
- **Python:** testado só em 3.14.3. O mínimo declarado (3.11, por causa do `tomllib`) não foi testado em outra versão.
- **Sistema operacional:** o ambiente limpo foi outro diretório e outro ambiente Python no mesmo Windows, não outro sistema.
- **Rede bloqueada por equivalente:** o teste sem rede substitui `socket.connect`/`getaddrinfo` no processo e aponta os proxies para um endereço morto. A rede do sistema não foi desligada, porque isso mexeria em configuração do sistema.
- **Diferenças com o RREO:** as já conhecidas continuam como estão: (h) e (i) de 2026 "não determinada", e as cópias 24xxxxx com natureza não determinada.

## 20. Pendências

- Aprovação da 04.6 e decisão sobre os PRs: o PR #1 (04.5) segue aberto; a 04.6 está num ramo próprio e **nenhum PR foi criado**.
- Envio do pedido e-SIC (rascunho v2), feito pelo responsável.
- Para uma publicação futura: servidor WSGI de produção, HTTPS, limite de acesso e homologação no ambiente de destino.
- Teste de instalação em outro sistema operacional e em Python 3.11–3.13, se for exigido.

---

**Arquivos da 04.6:**
- **Código:**
  - `app/rp/painel/consulta.py` e `fontes.py`;
  - `app/rp/interface/paginas.py`, `formato.py`, `aplicacao.py` e `estilo.css`;
  - `app/rp/config.py`, `app/rp/banco.py` (só `~` em `reconstruir`), `app/rp/cli.py` e `app/rp/portoes.py` (novo).
- **Configuração:** `app/config.toml`, `app/requirements.txt` e `app/requirements-dev.txt` (novo).
- **Testes:** `app/tests/test_homologacao.py` e `test_homologacao_real.py` (novos) e `test_interface.py` (1 ajuste).
- **Documentação:** `app/README.md`, `docs/stages/04-pipeline/SOURCE_ARCHITECTURE.md` e este relatório.
- **Evidências e scripts em `docs/stages/04-pipeline/results/`:**
  - estado e comparação: `04_6_estado.py`, `04_6_estado_antes.json`, `04_6_estado_depois.json`, `04_6_comparar_estados.py`, `04_6_comparacao_pre_pos.json`;
  - servidor sem rede e percurso: `04_6_servidor_sem_rede.py`, `04_6_percorrer_telas.py`, `04_6_percurso_sem_rede_ambiente_limpo.json`;
  - desempenho e instalação: `04_6_desempenho_banco_ativo.json`, `04_6_instalacao_limpa.txt`;
  - testes: `04_6_baseline_testes_*.txt`, `04_6_testes_*.txt`.
