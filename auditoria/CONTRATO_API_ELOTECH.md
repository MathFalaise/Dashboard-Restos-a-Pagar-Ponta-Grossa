# Contrato da API Elotech usado pelo coletor

**Contrato EMPÍRICO do projeto, não documentação do fornecedor.** O endpoint de Restos a Pagar
(`/empenhos/restos-a-pagar`) não consta da especificação OpenAPI publicada pelo portal
(`etapa01/amostras_brutas/openapi_v3_api-docs.json`, "Web Services", 7 endpoints, nenhum de RP). É o
endpoint que a própria tela "Consulta em Restos a Pagar" usa. Tudo abaixo é comportamento **observado e
conferido** pelo projeto, com a data e a evidência; nada aqui é garantia da Elotech.

Versão deste contrato no código: `rp/contrato.py`, `VERSAO = "rp-api-contrato/1"`. Ela muda quando muda o que
o coletor exige da API. Revisão crítica de 05/10/2026, itens 16, 17, 19, 49 e 50.

## 1. Fonte e versão observada

| Item | Valor | Evidência |
|---|---|---|
| Base | `https://servicos.pontagrossa.pr.gov.br/portaltransparencia-api` | `app/config.toml` |
| Plataforma | Oxy Transparência (Elotech Gestão Pública), versão **3.128.0**, build `2026-09-22T19:26:34Z` | `GET /actuator/info`: Etapa 01 (sem cópia no bruto) e `diagnosticar-api` de 05/10/2026 (`auditoria/diagnostico_api_20261005.json`) |
| Servidor | `Server: nginx`; também `ETag`, `Date` e `X-debug: API LOCATION, geral LOCATION`. Nenhum cabeçalho traz versão | cabeçalhos das 312 respostas gravadas pelo coletor |
| Autenticação | nenhuma; sem CAPTCHA | Etapa 01 §4 |

A versão do portal só é lida pelo `diagnosticar-api`, e só como informação: `/actuator/info` não é endpoint do
coletor e pode ser desligado sem afetar a coleta.

## 2. Endpoints usados (todos GET, sem redirecionamento)

| Uso | Caminho | Parâmetros | Resposta |
|---|---|---|---|
| Listagem de RP de um corte | `/empenhos/restos-a-pagar` | `entidade`, `exercicio`, `dataInicial`, `dataFinal`, `size=2000`, `page`, `sort=anoempenho,asc` e `sort=empenho,asc` | página Spring |
| Movimentação de um empenho | `/empenhos/detalhe/movimentacao` | `entidade`, `exercicio` (= ano do empenho), `empenho`, `size=500`, `page` | página Spring |
| Catálogo de entidades | `/api/entidades/lista` | — | lista de objetos |
| Catálogo de exercícios | `/api/exercicios/entidade/{entidade}` | — | lista de objetos |
| Publicações LRF (grupo 1) | `/api/publicacoes/1` | `entidade`, `exercicio` | lista de grupos |
| PDF do RREO | `/api/files/arquivo/{idArquivo}` | — | PDF |
| Versão do portal (só diagnóstico) | `/actuator/info` | — | JSON `build.version`, `build.time` |

Regras de produção sobre os parâmetros da listagem (Etapa 02 §8 e §11), conferidas pelo coletor:

- `dataInicial` é sempre 01/01 do exercício. Sem ela o servidor responde **HTTP 500** ("No value supplied for
  the SQL parameter 'dataInicial'", Etapa 01).
- `dataFinal` fica no mesmo ano do exercício.
- `tipoPesquisa` (`Processados`/`NaoProcessados`) **nunca** é usado em produção.

## 3. Página Spring (listagem e movimentação)

Campos do topo, presentes em **todas** as 322 páginas gravadas (314 de listagem, 8 de movimentação):
`content`, `empty`, `first`, `last`, `number`, `numberOfElements`, `pageable`, `size`, `sort`,
`totalElements`, `totalPages`.

| Regra observada | Evidência | Conferida em |
|---|---|---|
| `page` começa em 0; `number` ecoa a página pedida | 322/322 páginas gravadas | `coletor.conferir_pagina` |
| `numberOfElements` = tamanho de `content` | 322/322 | idem |
| `first` = (página 0); `empty` = (`content` vazio) | 322/322 | idem (desde 05/10/2026) |
| Resultado vazio: `totalPages=0`, `last=true`, `first=true`, `empty=true` | 88 listagens vazias gravadas | idem (`totalPages` coerente) |
| `size` máximo 2000: pedido maior volta com `size=2000` | Etapa 01 (2500 → 2000); sondagem da auditoria (5000 → 2000) | `size` ecoado nunca maior que o pedido; menor é aceito se coerente (`test_API06_*`) |
| Mesma consulta repetida devolve os mesmos bytes de `content` | `auditoria/sondagem_api.json` | segunda leitura de todas as páginas |
| Páginas de 100 e de 2000 trazem o mesmo conjunto, na mesma ordem | `auditoria/sondagem_api.json` | — |
| `sort` é aceito, ecoado (`sort[]` com `property`, `direction`, `ascending`, `descending`...) e obedecido; `desc` inverte | `auditoria/sondagem_ordenacao.json` (05/10/2026) | eco conferido página a página |
| Com `sort=anoempenho,asc&sort=empenho,asc`, o `content` é **idêntico byte a byte** ao da ordem implícita | idem: entidade 5 (1 página, 360 registros) e entidade 1 de 2025 (2 páginas, 3.990 registros) | — |

## 4. Registro da listagem de RP

Estrutura plana (nenhum objeto aninhado). No snapshot mais recente da entidade 1 (4.557 registros):

- **Em todos os registros** (24 campos): `anoempenho`, `aproc`, `canceladoAProc`, `canceladoProc`, `cnpj`,
  `cnpjNome`, `dataEmissao`, `descricaoFonte`, `desdobraDesp`, `empenho`, `empenhoExercicio`, `entidade`,
  `fonteRecurso`, `fornecedor`, `liquidado`, `nome`, `pagoAProc`, `pagoAProcEstornado`, `pagoProc`,
  `pagoProcEstornado`, `proc`, `programatica`, `retencao`, `subDesdobramento`.
- **Só em parte dos registros** (7 campos): `elemento`, `funcao`, `orgao`, `programa`, `projeto`, `subFuncao`,
  `unidade`.
- Tipos: os 10 campos monetários, `entidade`, `anoempenho`, `empenho`, `fonteRecurso` e `fornecedor` são números;
  os demais, texto.

Na normalização 13 do banco ativo (228.873 registros), 6.851 registros não trazem alguma chave, e **nenhum** deixa
de trazer campo monetário. O significado de cada campo está no dicionário do painel (`python -m rp painel
dicionario`) e na Etapa 02.

**Identidade de um registro** (item 15), três níveis que convivem:

| Nível | Definição | Onde |
|---|---|---|
| Física | snapshot, resposta (ordem da página) e índice em `content` | `rp_registro (resposta_id, indice)` |
| Lógica | `(entidade, anoempenho, empenho)` | `contrato.chave_negocio` |
| Conteúdo | SHA-256 do registro em JSON canônico | `contrato.impressao_registro` |

A chave lógica **não pode repetir** num retrato. Repetida, a coleta fica `incompleta` (§6) e um retrato antigo
ou importado com repetição nunca vira o vigente do corte.

## 5. Catálogos (contrato mínimo)

JSON válido não basta: um objeto de erro com HTTP 200 também é JSON (item 6). O mínimo é o que a normalização
precisa:

| Catálogo | Contrato mínimo (`rp/contrato.py`) |
|---|---|
| Entidades | lista não vazia de objetos com `id` inteiro |
| Exercícios | lista de objetos com `id.exercicio` e `id.entidade.id` inteiros; `id.entidade.id` = a entidade pedida |
| Publicações | lista de grupos (objetos); `list`, se presente, é lista |

## 6. Coleta paginada: o que é garantido e o que não é

A API não oferece cursor, transação nem exportação consistente utilizável (a exportação CSV leva cerca de 6
minutos para 1.663 linhas e traz só 7 colunas: Etapa 01 §3.C). Então uma coleta de várias páginas é um
**retrato montado por consultas sucessivas**, não uma fotografia atômica da base (item 18). O manifesto grava
`coletada_em` (início) e `coleta_finalizada_em` (fim).

O coletor só marca `completa` se, em todas as páginas:

1. HTTP 200 e página Spring dentro do contrato do §3;
2. `totalElements` inteiro e igual em todas as páginas, soma das páginas igual a ele e `totalPages` coerente;
3. eco da ordem pedida igual ao pedido;
4. `(anoempenho, empenho)` nunca diminui e cresce na troca de página;
5. nenhum registro idêntico reaparece e nenhuma chave lógica repete no retrato inteiro, dentro ou entre páginas;
6. na listagem, todo registro é da entidade pedida;
7. com mais de uma página, a **segunda leitura** de todas devolve o mesmo `content` e o mesmo total.

**Limite que nenhuma dessas travas remove** (item 19): cada página reflete a base no instante em que foi lida.
Uma alteração que não desloca registros entre páginas (por exemplo, um valor que muda num registro de uma página
ainda não lida) entra no retrato sem ser detectada, e o retrato mistura instantes dentro da janela entre
`coletada_em` e `coleta_finalizada_em`. Retrato de uma página só é atômico. As travas 2, 4, 5 e 7 detectam o
deslocamento entre páginas (inclusão ou exclusão antes do ponto de leitura), que é o que perde ou repete
registro.

## 7. Erros conhecidos

| Situação | Comportamento | Tratamento |
|---|---|---|
| Sem `dataInicial` | HTTP 500 | o coletor sempre envia |
| Entidade ou exercício inexistente | HTTP 200 com 0 registros: não distingue "sem RP" de "não existe" | observação no snapshot quando fora do catálogo vigente (COL-05) |
| `size` acima de 2000 | cortado para 2000, sem erro | `size` ecoado conferido |
| 429 e 5xx | — | nova tentativa com espera crescente e `Retry-After` (segundos ou data HTTP, teto de 300 s); esgotadas, coleta `falhou` |
| Redirecionamento | — | não é seguido (`test_API14_*`) |

## 8. Como uma mudança da API aparece

- **Antes de coletar:** `python -m rp diagnosticar-api` consulta os catálogos e uma página pequena da
  listagem, confere o contrato acima e compara a estrutura com a dos snapshots gravados. Não grava nada. Saída 0
  (nada mudou), 1 (a API mudou), 2 (não deu para consultar).
- **Em cada snapshot novo:** o manifesto grava `contrato_api` = versão do contrato, `forma` (caminho → tipos de
  toda a resposta) e `forma_sha256`. Campo novo, campo removido ou tipo diferente muda a impressão (item 50).
- **Na coleta:** o que fere o §3, o §5 ou o §6 deixa o snapshot `incompleta` ou `falhou`, com o motivo. Ele é
  preservado e nunca vira o retrato vigente.

A comparação de estrutura do diagnóstico ignora o eco da ordem pedida (`$.sort[]`, `$.pageable.sort[]`). Os
snapshots coletados antes de 05/10/2026 não pediam ordem e têm esse eco vazio. Na primeira rodada real essa era a
única diferença, e ela não é mudança da API.

## 9. Histórico

| Data | O que foi observado |
|---|---|
| 29/09/2026 | Etapa 01: endpoint descoberto pela tela do portal; parâmetros, limite de 2000 e erro 500 sem `dataInicial`; versão 3.128.0 |
| 30/09/2026 | Coleta de produção concluída. Banco ativo: 466 snapshots (247 listagens), nenhum com chave repetida ou registro de outra entidade (conferido em 05/10/2026) |
| 05/10/2026 | Sondagem da ordenação (`sondagem_ordenacao.json`, 7 requisições) e primeiro `diagnosticar-api` (resultado `ok`, `diagnostico_api_20261005.json`) |
