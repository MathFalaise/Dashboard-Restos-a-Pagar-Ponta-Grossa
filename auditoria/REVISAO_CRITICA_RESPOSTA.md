# Resposta à revisão crítica de 05/10/2026

Resposta item a item aos 51 pontos da revisão crítica do coletor, da normalização, da derivação, do banco, da
camada de consulta e da publicação do bruto. Branch `auditoria-tecnica` (PR #13), sobre o commit `461c6a2`.

Regra seguida, a da própria revisão: **nenhum dado foi apagado para corrigir duplicidade**. O que mudou foi a
elegibilidade: um retrato com ambiguidade não resolvida nunca chega a um indicador, e o sistema prova isso num
portão.

## 1. Resultado em uma página

- **Nenhum número publicado mudou.** Reconstruí o banco a partir do armazém real duas vezes, uma com o código
  da base (`461c6a2`) e outra com o código novo, e processei as duas. `comparar-bancos` dá **equivalentes em
  tudo**: camada bruta, as seis tabelas da normalização, as duas derivações (atual e "como estava em" 29/09/2026)
  e o hash semântico. Os hashes homologados se repetem: `2f6b4e29…` e `b8a0b2ed…`. Nos dados reais não há chave
  repetida, então a regra nova de elegibilidade não tira nenhum retrato de uso.
- No banco reconstruído pelo código novo: `verificar` sem problemas, portões aptos (inclusive os dois novos),
  482 testes de produção e os 26 da investigação passando.
- **O banco ativo não foi alterado:** só foi aberto para leitura. Ele difere de qualquer reconstrução numa linha
  de `rreo_extracao`, a mensagem de erro de um PDF de layout desconhecido. É a correção DET-01 da auditoria
  anterior, já registrada em `auditoria/resultados/equivalencia_ativo_x_reconstruido.json`, e some quando o banco
  ativo for reprocessado.
- **Testes:** de 397 para 482. São 85 novos em quatro arquivos `test_revisao_*.py`, e cada teste cita o item que
  cobre. Quatro testes antigos mudaram (seção 4) e nenhum foi apagado.
- **Fatos conferidos nos dados reais**, todos só com leitura:

| Fato | Resultado |
|---|---|
| chave (entidade, anoempenho, empenho) repetida nas 247 listagens / 466 snapshots | 0 |
| registro de outra entidade numa listagem | 0 |
| páginas com `first`, `number`, `numberOfElements` ou `empty` incoerentes | 0 de 322 |
| registros com campo monetário ausente | 0 de 228.873 (6.851 têm outra chave ausente) |
| PDFs do RREO com mais de 1 página | 0 de 36 (33 transcritos, 3 com layout desconhecido) |
| carimbos do MANIFESTO da Etapa 02 sem fuso | 66 de 66 |
| `sort` aceito, ecoado e obedecido pela API | sim, e com a ordem pedida o content é idêntico byte a byte ao da ordem implícita (`sondagem_ordenacao.json`, 7 requisições) |
| `diagnosticar-api` contra o portal | `ok`; portal Oxy Transparência 3.128.0, build de 22/09/2026 (`diagnostico_api_20261005.json`, 4 requisições) |

## 2. Prioridades P0 da revisão

| P0 | Situação |
|---|---|
| duplicidade pode entrar no cálculo | **corrigido** (itens 1, 13 e 14) |
| paginação não prova unicidade/cobertura | **corrigido** (itens 2, 4 e 35) |
| ordenação da API não é controlada | **corrigido** (item 3) |
| API pode mudar durante a paginação | **detectado o que é detectável; limite documentado** (itens 18 e 19) |
| duplicata é anotação, não bloqueio | **corrigido**: portão (item 14) |
| repositório público com bruto e dados pessoais | **depende de decisão sua** (itens 31 a 33). Nada foi feito no repositório remoto |

## 3. Item a item

Legenda: **CORRIGIDO** nesta revisão · **JÁ ESTAVA** corrigido na auditoria técnica anterior (grupos G1–G8) ·
**MITIGADO** (o risco está bloqueado, a forma sugerida não foi adotada) · **EXPLICADO** · **ADIADO** ·
**DECISÃO SUA**.

### Coleta e API (etapa A)

| # | Ponto | Situação | O que foi feito / por quê | Prova |
|---|---|---|---|---|
| 2 | paginação não prova registros únicos | JÁ ESTAVA + CORRIGIDO | Antes já se conferiam `number`, `numberOfElements`, `size`, `totalPages`, registro idêntico entre páginas, ordem crescente e segunda leitura. Agora também: chave de negócio única no retrato inteiro (dentro e entre páginas), `first`, `empty` e registro da entidade pedida | `test_REV02_*`, `test_REV35_*`, `test_API03`–`API08` |
| 3 | sort não controlado | CORRIGIDO | A listagem pede `sort=anoempenho,asc&sort=empenho,asc` e confere o eco em cada página; servidor que ignora a ordem não produz retrato `completa`. Sondagem controlada antes de mudar: a API aceita, ecoa e obedece (`desc` inverte). Exceção deliberada: `recoletar` repete exatamente os parâmetros do snapshot de origem, e um snapshot anterior a 05/10/2026 não tinha `sort`. A unicidade da chave, a ordem crescente e a segunda leitura valem do mesmo jeito | `test_REV03_*`; `sondagem_ordenacao.json` |
| 4 | totalElements não prova integridade | JÁ ESTAVA + CORRIGIDO | Prova de cobertura completa: total informado = soma recebida = chaves únicas = posições; `totalPages` coerente; toda página 0..n−1 lida e com `number` conferido | idem item 2 |
| 5 | confia demais na página Spring | JÁ ESTAVA + CORRIGIDO | `conferir_pagina` (COL-02/03) passou a conferir também `first` e `empty`, presentes e coerentes nas 322 páginas reais | `test_REV35_*` |
| 6 | catálogo `completa` com JSON errado | CORRIGIDO | Contrato mínimo de entidades, exercícios e publicações (`rp/contrato.py`); fora dele o snapshot fica `falhou` com o motivo, e as publicações fora do contrato não baixam PDF | `test_REV06_*` |
| 7 | `except Exception` no HTTP | JÁ ESTAVA + CORRIGIDO | No HTTP já só repetia falha transitória. Agora a normalização do RREO também separa erro de layout (registrado) de erro de programa (derruba o processamento) | `test_API15`, `test_HTTP01_*`, `test_REV07_*` |
| 8 | timeout total não é total | CORRIGIDO | Três prazos: conexão (30 s), silêncio entre pedaços e prazo total **absoluto** (3 × leitura), com a leitura numa thread e o socket derrubado no vencimento. Antes, com prazo de 1,5 s, um servidor que pingava bytes prendia 9,8 s | `test_REV08_*`, com servidor HTTP local de verdade |
| 9 | Retry-After incompleto | JÁ ESTAVA | Aceita segundos e data HTTP, com teto de 300 s. Sem jitter de propósito: um cliente sequencial só, e o jitter tiraria o determinismo dos testes (documentado em `http.py`) | `test_API09_*` |
| 16 | endpoint sem contrato oficial | CORRIGIDO | `auditoria/CONTRATO_API_ELOTECH.md`: contrato **empírico**, com endpoint, parâmetros, estrutura observada, campos obrigatórios e opcionais, limite de página, ordenação, erros conhecidos, versão do portal e datas | — |
| 17 | sem versão do contrato da API | CORRIGIDO EM PARTE | O manifesto de cada snapshot novo grava `contrato_api` (versão `rp-api-contrato/1`, forma e SHA-256 da forma); a data do servidor já ia nos cabeçalhos (`Date`). A versão do portal sai no `diagnosticar-api` (`/actuator/info`), mas não é gravada por snapshot: seria uma requisição a mais por coleta, num endpoint fora do contrato. O hash do OpenAPI não entra: o endpoint de RP não está nele | `test_REV18_*` |
| 18 | `coletada_em` não é um instante | CORRIGIDO | Manifesto com `coleta_finalizada_em`; o início já era `coletada_em`. A limitação está escrita no contrato (§6) | `test_REV18_*` |
| 19 | não dá para saber se a base mudou entre páginas | EXPLICADO | Das alternativas da revisão: a ordenação determinística foi aplicada; cursor/keyset não existe na API; a exportação integral é inviável (CSV de 6 min e 7 colunas); a checagem cruzada já existia (segunda leitura). O que sobra está escrito no contrato §6: cada página reflete a base no instante em que foi lida. A garantia não foi inventada | — |
| 20 | identidade do importador por caminho | CORRIGIDO | O mesmo `snapshot_uid` com outros bytes ou parâmetros é `ConflitoDeImportacao`, nunca "já existe, então ignora" | `test_REV20_*` |
| 21 | fuso no importador | CORRIGIDO | Sem fuso: Brasília. Com fuso: convertido, não sobrescrito. Os 66 carimbos reais são sem fuso, então nenhum snapshot importado muda | `test_REV21_*` |
| 49 | sem monitoramento de mudança da API | CORRIGIDO | `python -m rp diagnosticar-api` confere catálogos e uma página pequena da listagem contra o contrato e compara a estrutura com a dos snapshots gravados, sem gravar nada. Saída 0 / 1 (mudou) / 2 (não consultou). Primeira rodada real: `ok` | `test_REV49_*` (26) |
| 50 | sem impressão do contrato da resposta | CORRIGIDO | `contrato.forma` (caminho → tipos, sem valores) e o SHA-256 dela. Campo novo, removido ou com outro tipo muda a impressão. Na comparação com uma amostra, "removido" só conta para campo presente em todo registro gravado (campo raro não gera alarme) | `test_REV50_*`, `test_REV49_*` |

### Duplicidade e elegibilidade (etapas B e C)

| # | Ponto | Situação | O que foi feito / por quê | Prova |
|---|---|---|---|---|
| 1 | duplicidade entra no dinheiro | CORRIGIDO | Retrato com a mesma chave (entidade, anoempenho, empenho) mais de uma vez **nunca é o vigente** do corte. Vale o retrato válido anterior (aviso no painel e verificação na derivação) ou o dado fica "ambíguo", indisponível. A regra é única (`rp/vigencia.py`) e vale para derivação, consultas e painel; o oráculo bruto aplica a mesma regra lendo o JSON, sem a anomalia gravada. A CHAVE-DUP agora diz se a cópia é exata ou conflitante e onde está. Nada é apagado. **Diferença em relação à revisão:** cópia exata também bloqueia (ver decisão D1) | `test_REV01_*` |
| 13 | dict escolhe uma duplicata em silêncio | CORRIGIDO | Continuidade e pareamento montam o mapa por chave com `_por_chave`, que recusa repetição em vez de ficar com a última cópia. É a segunda barreira: pelo item 1, retrato ambíguo nem chega lá | `test_REV13_*` |
| 14 | CHAVE-DUP deveria ser portão | CORRIGIDO | Portão `retrato_sem_chave_repetida`: reprova com qualquer repetição e informa quantas chaves e de que natureza (exata, conflitante) | `test_REV14_*` |
| 15 | falta identidade formal | CORRIGIDO EM PARTE | As três identidades existem: física (resposta + índice), lógica (`contrato.chave_negocio`) e de conteúdo (`contrato.impressao_registro`, SHA-256 do JSON canônico). São usadas na unicidade e na classificação. A de conteúdo não é gravada por registro: exigiria mudar o esquema da camada 1 (junto com a decisão D4) | `test_REV15_*` |
| 23 | 24xxxxx não é duplicidade | EXPLICADO | Já são mecanismos separados: CHAVE-DUP (a mesma chave no mesmo retrato) e COPIA-24/PAR-24 (cópias entre as entidades 1 e 15). A regra nova só usa CHAVE-DUP. A natureza das cópias 24xxxxx continua NÃO DETERMINADA (pergunta do e-SIC) | — |
| 35 | faltam testes de paginação | CORRIGIDO | Os seis casos: (1) A B / B C → `test_REV02_chave_repetida_entre_paginas_*`; (2) `number` errado e (3) `numberOfElements` errado → `test_REV35_*`; (4) `size` menor que o pedido → aceito se coerente, maior → recusado (`test_API06_*`); (5) conflitante e (6) exata sem dupla contagem → `test_REV02_*` e `test_REV01_*` | — |

### Normalização, banco e portões (etapa D)

| # | Ponto | Situação | O que foi feito / por quê | Prova |
|---|---|---|---|---|
| 10 | ausência monetária vira zero | MITIGADO | Desde a auditoria anterior (NORM-01), o portão `campos_monetarios_ausentes` impede disponibilizar carga com campo monetário ausente. Nos dados reais são 0 de 228.873. Trocar o 0 por NULL é decisão (D3) | portão |
| 11 | `INSERT OR IGNORE` no RREO | CORRIGIDO | Sem OR IGNORE: a mesma célula com o mesmo valor vira uma linha só, explicitamente; valor diferente vira `LayoutDesconhecido`; qualquer outro conflito é erro | `test_REV11_*` |
| 12 | RREO só na primeira página | CORRIGIDO | Exige 1 página (o layout conhecido; os 36 PDFs reais têm 1). Com mais de uma, é `LayoutDesconhecido`, nunca transcrição parcial | `test_REV12_*` |
| 25 | hash mistura resultado e diagnóstico | CORRIGIDO | `hash_semantico` (valores e relações, sem anomalia nem verificação) aparece em `comparar-bancos`. Não é gravado e o `hash_resultado` homologado não muda | `test_REV25_*` |
| 26 | faltam FKs na camada derivada | MITIGADO | O portão `integridade_relacional` (auditoria anterior) roda `foreign_key_check` e procura órfãos nas relações sem FK: derivado → registro, anomalia → coleta, par → registros, conciliação → PDF. FK de verdade exige migrar o esquema (D4) | portão |
| 27 | JSON usado para relações | MITIGADO | Os snapshots citados em `coletas_json` são conferidos pelo mesmo portão. Tabelas de ligação entram com D4 | portão |
| 28 | versão do esquema sem impressão | CORRIGIDO | Impressão digital do esquema por versão (tabelas, colunas, restrições, índices, gatilhos; comentário e espaço não contam). Ao abrir, diferença vai para o log; o portão `esquema_confere` reprova. O banco ativo confere | `test_REV28_*` |
| 29 | `integrity_check` sozinho não basta | JÁ ESTAVA + CORRIGIDO | `foreign_key_check` já era portão. Agora os portões separados são: integridade SQLite, integridade relacional, esquema, hash, proveniência e chave repetida | — |
| 30 | backup sem prova de restauração | CORRIGIDO | backup → restaurar em outro arquivo → `integrity_check` → `foreign_key_check` → reprocessar → mesmo hash e mesma equivalência semântica | `test_REV30_*` |
| 44 | `repr(row)` em hash de integridade | CORRIGIDO | A referência dos portões passa a JSON canônico (`rp-referencia/2`), e a referência antiga continua sendo conferida como foi gravada. O `hash_camada0` (repr) fica porque é valor homologado; a prova entre bancos já usa JSON (`equivalencia.py`) | `test_REV44_*` |
| 46 | não é só OneDrive | CORRIGIDO | O banco ativo é recusado em OneDrive, Dropbox, Google Drive, iCloud, Box, Nextcloud, caminho UNC, unidade de rede mapeada e sistema de arquivos de rede no Linux | `test_REV46_*` |

### Testes, CI, empacotamento e documentação

| # | Ponto | Situação | O que foi feito / por quê | Prova |
|---|---|---|---|---|
| 34 | testes dependem de dados reais | CORRIGIDO | O marcador `dados_reais` é posto sozinho pelo `conftest.py` em todo teste que usa as fixtures `real` ou `producao`: 161 testes, contra 321 sintéticos. `-m "not dados_reais"` roda sem o bruto | — |
| 36 | falta CI | CORRIGIDO (falta rodar) | `.github/workflows/testes.yml` com três jobs. **Sintéticos:** Linux e Windows × Python 3.11–3.14, com conferência de sintaxe. **Dados reais:** ambiente homologado, mais os 26 da Etapa 03, pulado se o bruto sair do repositório. **Pacote:** instalação editável e comando `rp`. Só roda quando for enviado ao GitHub. Lint ficou fora: o projeto não tem linter configurado e ligar um agora reprovaria código que nunca passou por ele | — |
| 37 | README promete portabilidade | CORRIGIDO | O README diz o que está comprovado: Windows com Python 3.14.3. Ao conferir, achei um bloqueio real: `rp/importar.py` usava barra invertida dentro de f-string, o que só vale a partir do 3.12, e no 3.11 o importador nem carregava. Corrigido sem mudar a URL gravada. O CI prova o resto | — |
| 38 | instalação pouco empacotada | CORRIGIDO | `app/pyproject.toml` com o comando `rp` (`rp.cli:main`). Instalação **editável** (`pip install -e .`): o pacote acha `config.toml` e o armazém a partir de `app/`. Conferido sem instalar (ponto de entrada, pacotes, arquivos de dados, versões); a instalação é provada pelo job `pacote` | — |
| 51 | corte ≠ conhecimento ≠ coleta | JÁ ESTAVA | Todo valor leva o rótulo "Estado atual da base para o exercício de A, corte DD/MM/AAAA, coletado em …" ou "Como a base estava em …". Agora o manifesto também tem o fim da coleta. A data de conhecimento do Município não vem da API (a data do lançamento não prova a do registro, 04.4 §15) | — |

### Regras, armazenamento e operação

| # | Ponto | Situação | Comentário |
|---|---|---|---|
| 22 | catálogo histórico de entidades | EXPLICADO | O catálogo já é temporal pelos snapshots: "como estava em" usa o vigente até a data. A API só informa o presente, então entidade extinta antes da primeira coleta não aparece, e o painel diz isso na tela |
| 24 | regras com evidência limitada | DECISÃO SUA (D7) | A governança já separa situação (operacional, experimental, não recomendada) e evidência. Faltam critérios objetivos de promoção, e isso é decisão de negócio, não de código |
| 31 | Git como armazenamento do bruto | DECISÃO SUA (D2) | Hoje: pacote do repositório com 37,6 MiB, `snapshots/` com 15 MB, `etapa02/` com 87 MB |
| 32 | repositório público com dados pessoais | DECISÃO SUA (D2) | É o P0 que não depende de código. O CI e os testes já estão preparados para o bruto sair do Git |
| 33 | remover do Git não apaga o histórico | DECISÃO SUA (D2) | Reescrever o histórico é irreversível, exige push forçado e não alcança cópias já feitas |
| 39 | dependências sem hash | DECISÃO SUA (D5) | Gerar o lock com hashes exige baixar os pacotes; isso já estava anotado como pendente de autorização em `requirements-lock.txt` |
| 40 | investigação duplica a lógica de produção | EXPLICADO | `etapa03/validacao` é evidência congelada ("não é código de produção") e nunca roda em produção. A duplicação é proposital: uma reimplementação independente serve de oráculo, como `recalculo_bruto.py`. `test_etapa03_em_producao.py` repete as mesmas asserções com o código de produção |
| 41 | processamento incremental | ADIADO | A própria revisão pede para não fazer antes da integridade. Hoje são cerca de 20 s |
| 42 | índices por EXPLAIN QUERY PLAN | ADIADO | O desempenho do painel foi medido na auditoria anterior (`benchmark_painel.py`). Índice novo, só com EXPLAIN e com medição |
| 43 | índices nas tabelas derivadas | ADIADO | Junto com o item 42 |
| 45 | imutabilidade contra administrador | EXPLICADO | O modelo detecta alteração acidental, não fraude de quem tem escrita no armazém. Para prova forte: manifesto assinado, hash publicado fora e armazenamento com bloqueio de objeto (decisão futura) |
| 47 | sem política de retenção | DECISÃO SUA (D6) | Já existe: snapshots nunca são apagados; backups operacionais mantêm os 3 mais recentes mais os listados em `PRESERVAR.txt` |
| 48 | logs sem retenção | DECISÃO SUA (D6) | É simples de implementar depois de escolhido o prazo |

## 4. Testes antigos que mudaram (nenhum foi apagado)

| Teste | Por quê |
|---|---|
| `test_seguranca.py::test_servidor_que_ignora_page_nao_prende_o_coletor` | Usava dois registros idênticos na mesma página; a regra nova recusaria antes e o teste deixaria de testar o que diz. Os dados passaram a ser registros distintos, e a intenção ficou igual |
| `test_auditoria_equivalencia.py::test_DET02_*` | Era **instável** antes desta revisão. Exigia `hash_camada0` diferente entre o banco e o reconstruído, mas isso só acontecia se a reconstrução caísse em outro segundo do relógio ou se os uids aleatórios saíssem em outra ordem; falhou uma vez na suíte cheia. O relógio da reconstrução agora é fixo |
| `test_variacao_05_5.py::test_SINTETICO_chave_repetida_bloqueia_o_par` | Regra nova (item 1): o retrato ambíguo deixou de ser um lado do par. O corte aparece como "ambíguo" (R1: nunca omitido) e o par continua bloqueado |
| `test_contrato_05_1.py::test_SINTETICO_chave_duplicada_bloqueia_o_par` | A mesma regra, no oráculo bruto |

## 5. Decisões que são suas

| | Decisão | Opções | O que recomendo |
|---|---|---|---|
| D1 | Cópia **exata** da mesma chave num retrato | (a) bloquear o retrato, como está implementado; (b) contar uma vez, como sugeriu a revisão | **(a).** Numa coleta em que a soma das páginas bate com `totalElements`, uma cópia a mais significa um registro a menos: contar uma vez esconderia a falta |
| D2 | Bruto e dados pessoais no repositório público | (a) tornar o repositório privado (reversível, imediato); (b) tirar o bruto do Git daqui para frente, mantendo manifestos e hashes e guardando o bruto em armazenamento privado; (c) reescrever o histórico (irreversível) | (a) agora; (b) e (c) como projeto próprio, se a decisão for publicar o código |
| D3 | Campo monetário ausente | (a) manter 0 com o portão; (b) NULL; (c) registro inválido, retrato inelegível | (c), no mesmo espírito da CHAVE-DUP. Hoje não afeta nenhum dado |
| D4 | FKs e tabelas de ligação na camada derivada | migração v5 do esquema, com backup antes e sem mudar dado | quando for mexer no esquema por outro motivo |
| D5 | Hashes das dependências | autorizar o download dos pacotes para gerar o lock com hashes | sim, junto com o primeiro CI |
| D6 | Retenção de logs e backups | prazos (a revisão sugere 30 dias operacionais e 90 de auditoria) | — |
| D7 | Critérios de promoção de regra | experimental → evidência → regressão → reconciliação independente → operacional | — |
| D8 | Reprocessar o banco ativo | `python -m rp processar` cria uma normalização e uma derivação novas; os hashes ficam os mesmos e só a mensagem DET-01 muda | rodar na próxima carga, depois do backup |

## 6. Como conferir

Dentro de `app/`:

```bash
python -m pytest tests
```

```bash
python -m pytest tests -m "not dados_reais"
```

```bash
python -m rp diagnosticar-api --entidade 1
```

Reconstrução numa pasta temporária, sem tocar o banco ativo (com `RP_DADOS_LOCAIS` apontando para ela): `reconstruir`, `processar`,
`processar --normalizacao 1 --em 2026-09-29T23:59:59-03:00`, `verificar`, `portoes` e
`comparar-bancos --outro <outra reconstrução>`.
