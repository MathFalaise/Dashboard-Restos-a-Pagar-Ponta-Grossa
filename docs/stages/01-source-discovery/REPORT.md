# Restos a Pagar de Ponta Grossa — Relatório da Etapa 01 (Investigação da fonte)

Investigação feita em 29/09/2026, entre 19h40 e 19h56 (horário de Brasília).
Ferramentas: navegador (com leitura do tráfego de rede da página), `curl` sem cookies e
leitura do código JavaScript público do portal. Foram cerca de 90 requisições, com pausa
de 1 s entre elas nos laços. Nenhum volume grande foi baixado; a maior resposta foi o CSV
completo de 213 KB.

Convenção deste relatório:

- **CONFIRMADO** — observado diretamente em resposta da fonte.
- **HIPÓTESE / NECESSITA DE VALIDAÇÃO** — dedução ainda não provada.
- **NÃO CONFIRMADO** — não foi possível verificar.

---

## 1. FONTE OFICIAL

**URL:** https://servicos.pontagrossa.pr.gov.br/portaltransparencia/
(a raiz redireciona para `/portaltransparencia/1/`, onde `1` é a entidade Prefeitura).

**Descrição:**
- É o Portal da Transparência da Prefeitura Municipal de Ponta Grossa. A página oficial da
  Prefeitura, https://www.pontagrossa.pr.gov.br/transparencia-pg/, aponta para ele com o
  texto "Portal da Transparência do Município". **CONFIRMADO**
- A plataforma é o **Oxy Transparência**, da Elotech Gestão Pública, versão **3.128.0**,
  com build de 22/09/2026. **CONFIRMADO** em `GET /portaltransparencia-api/actuator/info`.
- O portal é uma aplicação React de página única (SPA). O HTML não contém dados: tudo vem
  de uma API REST em `https://servicos.pontagrossa.pr.gov.br/portaltransparencia-api/`.
- O portal é organizado por **entidade × exercício**. Existem 10 entidades:

| id | Entidade | CNPJ |
|---|---|---|
| 1 | Prefeitura Municipal de Ponta Grossa | 76.175.884/0001-87 |
| 3 | Fundação Educacional de Ponta Grossa | 78.252.392/0001-73 |
| 4 | Instituto de Pesq. e Planejamento Urbano (IPLAN) | 03.570.696/0001-80 |
| 5 | Fundação de Assistência Social | 07.865.433/0001-59 |
| 6 | Autarquia Municipal de Trânsito e Transporte | 05.073.426/0001-99 |
| 8 | Agência de Inovação e Desenvolvimento | 03.406.339/0001-80 |
| 9 | Fundação Municipal de Cultura | 17.443.793/0001-16 |
| 10 | Fundação Municipal de Turismo | 17.443.826/0001-28 |
| 11 | Fundação Municipal de Esportes | 17.456.143/0001-05 |
| 15 | Fundação Municipal de Saúde | 32.370.759/0001-52 |

**Páginas relacionadas encontradas:**

| Página | URL |
|---|---|
| Execução (Despesa) | `/portaltransparencia/1/despesa/orgao`, `/funcao`, `/programa`, `/projeto`, `/elemento` |
| Despesas Empenhadas | `/portaltransparencia/1/empenhos/cf` — "Consulta dados dos empenhos do exercício" |
| Despesas Liquidadas | `/portaltransparencia/1/liquidacoes/todos` |
| Despesas Pagas | `/portaltransparencia/1/liquidacoes/pagas` |
| Fornecedores a Pagar | `/portaltransparencia/1/fornecedores` |
| Publicações contábeis (PDF) | menu "Contabilidade e Finanças" → `/portaltransparencia/1/publicacoes/{grupo}` |
| Dados Abertos | `/portaltransparencia/1/dados-abertos` |
| Swagger (API documentada) | https://servicos.pontagrossa.pr.gov.br/portaltransparencia-api/swagger-ui/index.html |

---

## 2. LOCALIZAÇÃO DOS RESTOS A PAGAR

**URL:** https://servicos.pontagrossa.pr.gov.br/portaltransparencia/1/restos-a-pagar

**Caminho dentro do portal:** **não há caminho pelo menu.**
- O menu de 2026 da entidade 1 não tem nenhum item "Restos a Pagar". Também não há nos
  menus de 2025 e 2021 (entidade 1) nem no de 2026 da entidade 15. **CONFIRMADO**
- A tela existe como rota no código do portal. Achei a rota `/restos-a-pagar` no
  JavaScript público e ela funciona quando acessada pelo endereço direto. Título da tela:
  **"Consulta em Restos a Pagar"**, com as abas **"Processados"** e **"Não Processados"**.
  **CONFIRMADO**

**Outras telas não correspondem a Restos a Pagar:**
- "Despesas Empenhadas" (`/empenhos/cf`) consulta os empenhos **do exercício**. Não tem
  filtro de restos a pagar na interface.
- "Despesas Liquidadas", "Despesas Pagas" e "Fornecedores a Pagar" são telas de
  liquidação e pagamento. O código traz um marcador "Somente Empenhos de Restos"
  (`isPendentes`) numa tela de liquidações. **NÃO TESTADO**
- Esta investigação não usa essas telas como fonte de Restos a Pagar.

**Fonte oficial complementar, para conferência de totais:**
- O **RREO – Anexo VII, "Demonstrativo dos Restos a Pagar por Poder e Órgão"**, fica em
  "Contabilidade e Finanças" → "Lei de Responsabilidade Fiscal (LRF-Execução Orçamentária)"
  (`/portaltransparencia/1/publicacoes/1`).
- É publicado em **PDF**, por bimestre, em versão da entidade e **consolidada**.
- 2025: 6 bimestres. 2026: 1º bimestre (normal e consolidado) e 2º bimestre (normal).
  **CONFIRMADO** via `GET /portaltransparencia-api/api/publicacoes/1?entidade=1&exercicio=2025|2026`.
- Não baixei nem li os PDFs.

---

## 3. MÉTODO DE ACESSO

**Método encontrado:** **Endpoint** usado pelo portal, não documentado, que devolve JSON
paginado. Há também **Exportação** (CSV e outros formatos). Não é necessário raspar HTML.

### A. API oficial (documentada)

Existe uma documentação OpenAPI 3.0.1:
- Especificação: `https://servicos.pontagrossa.pr.gov.br/portaltransparencia-api/v3/api-docs`
- Interface: `.../swagger-ui/index.html`
- Título "Web Services", contato Elotech. **CONFIRMADO**

Ela documenta **7 endpoints**, todos GET:
- `/empenhos/lista`
- `/api/servidores`
- `/api/receitas`
- `/api/liquidacoes/pagas`
- `/api/liquidacoes/pagar`
- `/api/licitacoes`
- `/api/dividas-ativas`

**Nenhum deles é de Restos a Pagar.** O `/empenhos/lista` documenta o parâmetro
`restosAPagar` ("Filtra apenas empenhos de restos a pagar"). No teste, **o parâmetro não
teve efeito**:
- com `restosAPagar=true`, `false`, omitido ou combinado com `anoempenho=2025`, o total foi
  sempre 23.619;
- o primeiro registro foi sempre `23619/2026`, ou seja, todos os empenhos de 2026.

**CONFIRMADO:** o filtro documentado não funcionou como descrito.

### B. Endpoint utilizado pelo portal (não documentado no Swagger)

```
GET https://servicos.pontagrossa.pr.gov.br/portaltransparencia-api/empenhos/restos-a-pagar
```

Trata-se do endpoint que a tela "Consulta em Restos a Pagar" usa. **Não é uma API pública
documentada.** Chamadas reais capturadas no navegador ao abrir a tela:

```
.../empenhos/restos-a-pagar?entidade=1&exercicio=2026&tipoPesquisa=Processados&dataInicial=2026-01-01&dataFinal=2026-12-31
.../empenhos/restos-a-pagar?entidade=1&exercicio=2026&tipoPesquisa=NaoProcessados&dataInicial=2026-01-01&dataFinal=2026-12-31
```

**Parâmetros de consulta** (lidos do código da tela e testados quando indicado):

| Parâmetro | Obrigatório | Valores | Status |
|---|---|---|---|
| `entidade` | — | id da entidade (1, 15…) | testado |
| `exercicio` | — | ano | testado |
| `dataInicial` | **SIM** | `AAAA-MM-DD` | sem ele: HTTP 500 "No value supplied for the SQL parameter 'dataInicial'" |
| `dataFinal` | provável | `AAAA-MM-DD` | isoladamente **NÃO TESTADO** |
| `tipoPesquisa` | não | `Processados`, `NaoProcessados` ou omitido | testado (os três casos) |
| `page` | não | 0, 1, 2… (começa em 0) | testado |
| `size` | não | padrão 20; **máximo 2000** | pedi 2500 e o servidor devolveu `size=2000` |
| `sort` | não | `campo,asc\|desc` | `sort=proc,desc` funcionou |
| `empenho` | não | número | testado |
| `anoempenho` | não | ano do empenho original | testado |
| `nome` | não | trecho do nome do fornecedor | testado (`nome=CAIXA`) |
| `cnpjCpf` | não | só dígitos | **NÃO TESTADO** |
| `programatica.orgao` | não | código | testado (`09` → 998 registros) |
| `programatica.unidade`, `.funcao`, `.subFuncao`, `.programa`, `.projeto`, `.elemento`, `.desdobramento`, `.subDesdobramento` | não | código | **NÃO TESTADOS** (presentes no código) |
| `fonteRecurso` | não | código | **NÃO TESTADO** |

**Resposta:**
- HTTP 200, `Content-Type: application/json`.
- Formato "Page" do Spring: `content[]`, `pageable{sort, offset, pageNumber, pageSize, paged, unpaged}`,
  `last`, `totalPages`, `totalElements`, `size`, `number`, `sort`, `first`,
  `numberOfElements`, `empty`.
- Desempenho medido: 2000 registros em cerca de 5,2 s e 1,48 MB.

**Endpoints de detalhe por empenho** (usados em "Mais Detalhes"):
- `GET /empenhos/detalhe?search=id.entidade==1&entidade=1&exercicio={anoempenho}&empenho={n}`
  — dados cadastrais e a programática com descrições.
- `GET /empenhos/detalhe/movimentacao?entidade=1&exercicio={anoempenho}&empenho={n}`
  — histórico de lançamentos: empenho, liquidação, pagamento, estorno, cancelamento.
- Também existem `/detalhe/pagamentos`, `/anulacoes`, `/liquidacoes`, `/itens`,
  `/retencoes`, `/liquidacoesdocumentos`, `/anexos`, `/em-liquidacao` e `/links`.
- Todos responderam 200 no navegador. Por curl, testei `detalhe`, `movimentacao` e
  `pagamentos`.

### C. Exportação

```
GET .../portaltransparencia-api/empenhos/restos-a-pagar/report?<mesmos filtros>&exportType=<tipo>
```

- Os botões da tela oferecem `html` (Imprimir), `xls`, `pdf`, `txt`, `csv`, `rtf` e `doc`.
  **CONFIRMADO no código.**
- **Só o CSV foi testado:**
  - HTTP 200, `Content-Type: text/csv`,
    `Content-Disposition: attachment; filename="Listagem de Restos a Pagar.csv"`.
  - **Exporta todos os registros do filtro, não só a página.** Enviei `size=20` e o
    arquivo veio com "1663 registros", o mesmo que `totalElements`.
  - **Muito lento: cerca de 6 minutos** para 1.663 linhas (213 KB).
  - Traz **só 7 colunas**: `Empenho;Data;Fonte de Recursos;Fornecedor;Valor Inscrito;Valor Cancelado;Valor Pago;`.
    O JSON tem 24 a 31 campos.
  - Formato: UTF-8 (sem BOM), fim de linha CRLF, separador `;`, `;` sobrando no fim da
    linha, decimal com vírgula e milhar com ponto (`13.454,4`), datas `dd/mm/aaaa`.
    Antes do cabeçalho vêm 3 linhas de título ("Listagem de Restos a Pagar",
    "Gerado em: …", linha vazia).
  - O CPF de pessoa física aparece mascarado: `****123****` (exemplo sintético).
- XLS, PDF, TXT, RTF, DOC e HTML **NÃO TESTADOS**. Interrompi os testes seguintes para não
  gerar mais carga no servidor.
- **Dados Abertos** ("Conjunto de Dados") tem 6 conjuntos: Pessoal, Licitações,
  Contratos, Convênios, Receitas e Despesas. **Nenhum é de Restos a Pagar.**

### D. HTML

Desnecessário: o HTML é só o esqueleto da aplicação e os dados vêm em JSON.

---

## 4. CAPTCHA E MECANISMOS DE PROTEÇÃO

**CAPTCHA encontrado?** **NÃO**

**Onde aparece?** Em nenhum ponto do fluxo testado:
- página inicial;
- tela de Restos a Pagar;
- tela de detalhe do empenho;
- Dados Abertos;
- chamadas diretas à API;
- exportação CSV.

**Qual mecanismo?** Nenhum observado:
- Não há login, token, chave de API nem cookie de sessão. `curl` sem nenhum cookie
  funciona.
- Não há cabeçalhos de limite de requisições (`X-RateLimit-*`, `Retry-After`).
- Não houve bloqueio em cerca de 90 requisições espaçadas de ≥ 1 s.
- **Não testei rajadas, de propósito.** O limite real de requisições é **NÃO CONFIRMADO**.
- Alguns endpoints auxiliares exigem os **cabeçalhos HTTP** `entidade` e `exercicio`. É
  parâmetro, não autenticação. Exemplo: `/api/ultimas-atualizacoes/by-table` devolveu 500
  sem o cabeçalho e 200 com `entidade: 1`. O `/empenhos/restos-a-pagar` **não** precisa
  desses cabeçalhos.
- O e-SIC pede CPF/CNPJ, mas não tem relação com os dados de despesa.

**A consulta pode continuar após intervenção manual?** **NÃO FOI POSSÍVEL TESTAR**, porque
não houve CAPTCHA. Não se aplica.

**Qual parte do processo continua automatizável?** O fluxo inteiro: listar exercícios,
consultar, paginar, detalhar e exportar.

---

## 5. EXERCÍCIOS DISPONÍVEIS

**Confirmados pelo portal (entidade 1):** **2016, 2017, 2018, 2019, 2020, 2021, 2022,
2023, 2024, 2025, 2026**.
- Fonte: `GET /portaltransparencia-api/api/exercicios/entidade/1`.
- 2026 aparece como `aberto=true, fechado=false`; de 2016 a 2025, `fechado=true`.

O endpoint de Restos a Pagar devolveu dados em todos esses anos. Contagem de **linhas**
(não de valores) em 29/09/2026, com período de 01/01 a 31/12 do próprio exercício:

| Exercício | Processados | Não Processados |
|---|---:|---:|
| 2016 | 2.679 | 4.361 |
| 2017 | 2.569 | 5.433 |
| 2018 | 1.720 | 4.382 |
| 2019 | 1.937 | 4.136 |
| 2020 | 1.484 | 3.703 |
| 2021 | 744 | 2.054 |
| 2022 | 856 | 2.326 |
| 2023 | 1.076 | 3.239 |
| 2024 | 1.465 | 3.379 |
| 2025 | 699 | 3.364 |
| 2026 (em andamento) | 1.663 | 3.091 |

Anos **fora** da lista oficial:
- `exercicio=2015` devolveu 2.414 registros Processados e `exercicio=2010` devolveu 401.
- O portal **não oferece** esses anos. Disponibilidade e confiabilidade:
  **NÃO CONFIRMADO**.
- A lista de exercícios das **outras entidades** não foi consultada: **NÃO CONFIRMADO**.

---

## 6. CAMPOS ENCONTRADOS

### 6.1 Registro de `/empenhos/restos-a-pagar` (JSON)

A coluna "Rótulo na tela" é o que a própria interface do portal mostra. É a única
"definição" que a fonte oferece.

| Campo | Tipo aparente | Exemplo | Observação |
|---|---|---|---|
| `entidade` | inteiro | `1` | id da entidade |
| `empenho` | inteiro | `5659` | número do empenho |
| `anoempenho` | inteiro | `2025` | ano do empenho original; a tela usa como "exercício" no link de detalhe |
| `empenhoExercicio` | texto | `"5659/2025"` | rótulo "Empenho"; número/ano |
| `cnpjNome` | texto | `"00.360.305/0001-04 - CAIXA ECONOMICA FEDERAL"` | documento + nome |
| `dataEmissao` | texto (data ISO) | `"2025-04-28"` | rótulo "Data" |
| `programatica` | texto (dígitos) | `"2001808244004817034567830000"` | **27 dígitos** na amostra de 2016, **28** nas de 2021 e 2026; sem separadores |
| `fonteRecurso` | inteiro | `3062` | código com 3 ou 4 dígitos (`103`, `1000`, `3062`, `3494`) |
| `descricaoFonte` | texto | `"3062-Prolar/Lotes"` | rótulo "Fonte de Recursos"; às vezes com espaço duplo |
| `fornecedor` | inteiro | `2775` | código interno do credor |
| `nome` | texto | `"00.360.305/0001-04 - CAIXA ECONOMICA FEDERAL"` | rótulo "Fornecedor"; **não é só o nome**: vem com o documento na frente |
| `cnpj` | texto | `"00.360.305/0001-04"` ou `"****123****"` (exemplo sintético) | CNPJ formatado; CPF de pessoa física **mascarado** |
| `proc` | número | `3141530.4` | rótulo "Valor Inscrito", aba Processados |
| `aproc` | número | `2874.26` | rótulo "Valor Inscrito", aba Não Processados |
| `canceladoProc` | número | `0` | rótulo "Valor Cancelado", aba Processados |
| `pagoProc` | número | `2277745.06` | rótulo "Valor Pago", aba Processados |
| `pagoProcEstornado` | número | `0` | **sem rótulo na tela**; significado NÃO CONFIRMADO |
| `canceladoAProc` | número | `3864.52` | rótulo "Valor Cancelado", aba Não Processados |
| `pagoAProc` | número | `1175.76` | rótulo "Valor Pago", aba Não Processados |
| `pagoAProcEstornado` | número | `0` | **sem rótulo na tela**; significado NÃO CONFIRMADO |
| `retencao` | número | `0` | **sem rótulo na tela**; significado NÃO CONFIRMADO |
| `liquidado` | número | `1175.76`, `-3864.52` | rótulo "Valor Liquidado", aba Não Processados; **aparece negativo** |
| `orgao` | texto | `"20"` | **às vezes ausente** (a chave não vem) |
| `unidade` | texto | `"20018"` | às vezes ausente |
| `funcao` | texto | `"08"` | às vezes ausente |
| `subFuncao` | texto | `"244"` | às vezes ausente |
| `programa` | texto | `"0048"` | às vezes ausente |
| `projeto` | texto | `"1703"` | às vezes ausente |
| `elemento` | texto | `"4567830000"` | às vezes ausente |
| `desdobraDesp` | texto | `"99"` | sempre presente nas amostras |
| `subDesdobramento` | texto | `"00"` | sempre presente nas amostras |

Não existe campo de **saldo**, de **situação** nem de **data de inscrição**.

### 6.2 Envelope de paginação

| Campo | Tipo | Exemplo |
|---|---|---|
| `content` | lista | registros acima |
| `totalElements` | inteiro | `1663` |
| `totalPages` | inteiro | `84` |
| `size` | inteiro | `20` |
| `number` | inteiro | `0` |
| `numberOfElements` | inteiro | `20` |
| `first` / `last` / `empty` | booleano | `true` / `false` / `false` |
| `pageable` | objeto | `{"sort":[],"offset":0,"pageNumber":0,"pageSize":20,"paged":true,"unpaged":false}` |
| `sort` | lista | `[]` |

### 6.3 Exportação CSV (aba Processados)

As colunas são `Empenho; Data; Fonte de Recursos; Fornecedor; Valor Inscrito; Valor Cancelado; Valor Pago`.
As colunas do CSV da aba Não Processados **NÃO FORAM TESTADAS**.

---

## 7. AMOSTRA DOS DADOS

Registros **copiados byte a byte** das respostas. Escolhi credores pessoa jurídica para não
expor nomes de pessoas físicas neste texto.

Processados, com o campo de órgão presente (`exercicio=2026`, período 2026-01-01 a 2026-12-31):

```json
{"entidade":1,"empenho":5659,"anoempenho":2025,"empenhoExercicio":"5659/2025","cnpjNome":"00.360.305/0001-04 - CAIXA ECONOMICA FEDERAL","dataEmissao":"2025-04-28","programatica":"2001808244004817034567830000","fonteRecurso":3062,"descricaoFonte":"3062-Prolar/Lotes","fornecedor":2775,"nome":"00.360.305/0001-04 - CAIXA ECONOMICA FEDERAL","cnpj":"00.360.305/0001-04","proc":3141530.4,"aproc":0,"canceladoProc":0,"pagoProc":2277745.06,"pagoProcEstornado":0,"canceladoAProc":0,"pagoAProc":0,"pagoAProcEstornado":0,"retencao":0,"liquidado":0,"orgao":"20","unidade":"20018","funcao":"08","subFuncao":"244","programa":"0048","projeto":"1703","elemento":"4567830000","desdobraDesp":"99","subDesdobramento":"00"}
```

Processados, **sem** os campos de órgão/unidade/função/…:

```json
{"entidade":1,"empenho":2398,"anoempenho":2012,"empenhoExercicio":"2398/2012","cnpjNome":"81.646.457/0001-70 - CRECHE FREI FABIANO ZANATTA","dataEmissao":"2012-02-13","programatica":"0900212365008020943350430000","fonteRecurso":103,"descricaoFonte":"103-10% sobre Transferências Constitucionais  - Exercício Corrente","fornecedor":274,"nome":"81.646.457/0001-70 - CRECHE FREI FABIANO ZANATTA","cnpj":"81.646.457/0001-70","proc":754.32,"aproc":0,"canceladoProc":0,"pagoProc":0,"pagoProcEstornado":0,"canceladoAProc":0,"pagoAProc":0,"pagoAProcEstornado":0,"retencao":0,"liquidado":0,"desdobraDesp":"03","subDesdobramento":"99"}
```

Não Processados:

```json
{"entidade":1,"empenho":7724,"anoempenho":2017,"empenhoExercicio":"7724/2017","cnpjNome":"14.804.099/0001-99 - CONSELHO DE ARQUITETURA E URBANISMO DO PARANA - CAU/PR","dataEmissao":"2017-05-17","programatica":"0300104122001020123390390000","fonteRecurso":1000,"descricaoFonte":"1000-Recursos Ordinários (Livres)","fornecedor":20739,"nome":"14.804.099/0001-99 - CONSELHO DE ARQUITETURA E URBANISMO DO PARANA - CAU/PR","cnpj":"14.804.099/0001-99","proc":0,"aproc":2874.26,"canceladoProc":0,"pagoProc":0,"pagoProcEstornado":0,"canceladoAProc":0,"pagoAProc":1175.76,"pagoAProcEstornado":0,"retencao":0,"liquidado":1175.76,"orgao":"03","unidade":"03001","funcao":"04","subFuncao":"122","programa":"0010","projeto":"2012","elemento":"3390390000","desdobraDesp":"05","subDesdobramento":"00"}
```

CSV (primeiras linhas, exatamente como recebidas; o fim de linha é CRLF):

```
Listagem de Restos a Pagar
Gerado em: 29/09/2026 19:48 com 1663 registros.

Empenho;Data;Fonte de Recursos;Fornecedor;Valor Inscrito;Valor Cancelado;Valor Pago;
2398/2012;13/02/2012;103-10% sobre Transferências Constitucionais  - Exercício Corrente;81.646.457/0001-70 - CRECHE FREI FABIANO ZANATTA;754,32;0,0;0,0;
5136/2012;23/03/2012;104-25% sobre demais impostos vinculados a Educação;78.280.617/0001-03 - J DEGRAF VIAGENS E TURISMO LTDA;616,5;0,0;0,0;
```

Todas as amostras estão em `data/stage01-samples/`, sem nenhuma alteração. Os hashes
SHA-256 estão em `data/stage01-samples.SHA256.txt`. A lista de arquivos está no Anexo A.

---

## 8. ESTRUTURA DA FONTE

**Organização.**
- Cada linha corresponde a **um empenho** de exercício anterior (`entidade` + `anoempenho` +
  `empenho`), dentro do exercício consultado.
- Os valores de processado (`proc`, `canceladoProc`, `pagoProc`…) e de não processado
  (`aproc`, `canceladoAProc`, `pagoAProc`, `liquidado`…) vêm **na mesma linha**.
- `tipoPesquisa` escolhe o subconjunto.
  - Sem `tipoPesquisa`, 2026 devolve 4.557 linhas, contra 1.663 + 3.091 = 4.754 somando
    as duas abas.
  - Portanto, 197 empenhos aparecem nas duas abas. Exemplo: `1622/2025`, com `proc`
    35.685,70 **e** `aproc` 235.600,05.
  - Sem tipo, não houve linha duplicada: é uma linha por empenho. Contagem **CONFIRMADA**;
    interpretação como "empenho parcialmente liquidado na inscrição" é **HIPÓTESE**.

**Período (`dataInicial` / `dataFinal`) — o que o teste mostrou:**
- A tela sempre envia `exercicio=A`, `dataInicial=A-01-01` e `dataFinal=A-12-31`.
- **Os valores dependem do período.** Teste com o empenho 5659/2025 (exercício 2026):

| Período | `proc` ("Valor Inscrito") | `pagoProc` ("Valor Pago") |
|---|---:|---:|
| 01/01 – 31/01 | 3.141.530,40 | 140.157,01 |
| 01/01 – 31/03 | 3.141.530,40 | 1.029.883,03 |
| 01/02 – 31/03 | **3.001.373,39** | 889.726,02 |
| 01/01 – 31/12 | 3.141.530,40 | 2.277.745,06 |

- `pagoProc` soma os pagamentos **dentro do período**: 1.029.883,03 − 140.157,01 =
  889.726,02.
- `proc` é o **saldo no início do período**, não um valor fixo de inscrição:
  3.141.530,40 − 140.157,01 = 3.001.373,39.
- **Validação cruzada** com `/empenhos/detalhe/movimentacao`:
  - o saldo "a pagar" depois do último pagamento de 2025 (03/12/2025) é **3.141.530,40**;
  - a soma dos 10 pagamentos de 2026 é **2.277.745,06** — confere.
  - **CONFIRMADO para este empenho.** Generalização: **NECESSITA DE VALIDAÇÃO**.
- **Misturar `exercicio` e datas de anos diferentes dá resultado incoerente.**
  - `exercicio=2026` com datas de 2020 devolveu o mesmo total (1.484) e os mesmos valores,
    nos 2 registros comparados, que `exercicio=2020` com datas de 2020.
  - Mas `exercicio=2020` com datas de 2026 devolveu só 129 linhas, contra 1.663 de
    `exercicio=2026`.
  - Os dois parâmetros interferem, de um jeito que não entendi.

**Diferenças de estrutura entre exercícios** (amostras de 50 registros de 2016, 2021 e 2026,
por aba):
- **Mesmo endpoint, método, parâmetros e envelope** em todos os anos testados (2010, 2015 a
  2026).
- `programatica` tem **27 dígitos** na amostra de 2016 e **28** nas de 2021 e 2026, ou seja,
  a máscara mudou. O próprio portal descreve o modelo atual como "Port. Intermin. nº163
  (Unidade 5 díg.)", máscara `##.###.##.###.####.#.###.#.#.##.##.##.##.`.
- `orgao`, `unidade`, `funcao`, `subFuncao`, `programa`, `projeto` e `elemento`:

| Amostra | Registros com esses campos |
|---|---|
| 2016 (as duas abas) | nenhum dos 50 |
| Não Processados 2021 e 2026 | todos os 50 |
| Processados 2021 | 32 de 50 |
| Processados 2026 | 35 de 50 |

  Quando faltam, a chave é **omitida**; não vem como `null`.
- **Hipótese de decodificação** da `programatica` de 28 dígitos: `[0:2]` órgão, `[0:5]`
  unidade, `[5:7]` função, `[7:10]` subfunção, `[10:14]` programa, `[14:18]`
  projeto/atividade e `[18:28]` elemento.
  - Bateu em **194 de 194** registros que tinham os campos explícitos.
  - O formato de 27 dígitos **não foi verificado**.
  - Status: **HIPÓTESE forte, NECESSITA DE VALIDAÇÃO**.
- Códigos de fonte de recurso de formatos diferentes convivem: `101`, `103`, `1000`, `602`,
  `3062`, `3494`. Não investiguei se houve troca de classificação ao longo dos anos.
- Números vêm ora como inteiro (`0`), ora como decimal (`754.32`). É só a serialização
  JSON; o tipo lógico é o mesmo.
- A entidade 15 (Fundação Municipal de Saúde) tem a mesma estrutura: 506 registros Não
  Processados em 2026. A entidade 3 devolveu 0 registros em 2026. As demais entidades não
  foram testadas.

**Enriquecimento.** O `/empenhos/detalhe` traz o que a listagem de RP não traz: descrição
de órgão, unidade, função, programa e projeto, histórico, modalidade de licitação,
processo, endereço do credor. Exige **uma chamada por empenho**.

**Atualização.** A tela mostra "Última Atualização: 29/09/2026 16:16:08". O mesmo valor sai
em `GET /api/ultimas-atualizacoes/by-table?modulo=3&table=empenho&column=dataultimaatualizacao`
com o cabeçalho `entidade: 1`. O rodapé do portal avisa: "Informações sujeitas a alteração".

---

## 9. LIMITAÇÕES

1. **O endpoint de Restos a Pagar não é documentado** e fica fora do Swagger. Pode mudar sem
   aviso. O portal teve build em 22/09/2026, uma semana antes desta investigação.
2. **Não há item de menu** para a tela. Isso indica que ela pode não ser mantida como
   funcionalidade oficial do município (hipótese).
3. **A API documentada não serve:** o filtro `restosAPagar` de `/empenhos/lista` é ignorado.
4. `dataInicial` é obrigatório; sem ele o servidor devolve 500 e ainda mostra detalhe da
   consulta SQL interna. **O significado dos valores depende do período escolhido.**
5. **Os rótulos da tela não bastam para interpretar os valores.** No empenho 11963/2016
   (exercício 2026, Processados, `proc` = 3.864,52):
   - a movimentação mostra, em 27/05/2026, um **"Estorno Liquidação"** de 3.864,52 e, em
     28/05/2026, um **"Cancelamento Empenho"** de 3.864,52;
   - a API registra isso em `liquidado` = **−3.864,52** e `canceladoAProc` = 3.864,52;
   - `canceladoProc` e `pagoProc` ficam em 0.
   A aba "Processados" mostra **Cancelado 0 e Pago 0**. Quem lê só essa aba conclui que há
   saldo em aberto, e ele não existe.
6. **Campos ausentes** (e não nulos) em parte dos registros. `programatica` muda de tamanho
   entre períodos.
7. **Sem campo de saldo nem de situação.** Qualquer saldo terá de ser calculado, e a fórmula
   ainda não foi validada.
8. **Exportação lenta e pobre:** o CSV levou cerca de 6 min para 1.663 linhas, com 7
   colunas. Não serve como método principal.
9. **Limite de 2000 registros por página.** Para 2017 Não Processados (5.433) são 3 páginas.
10. **Limite de requisições desconhecido.** Não há cabeçalhos nem documentação, e não testei
    rajadas.
11. **Dados pessoais (LGPD):**
    - há nomes de pessoas físicas credoras, com CPF parcialmente mascarado;
    - os endpoints de detalhe/pagamento trazem **banco, agência e conta** do credor.
    - Os dados são públicos no portal, mas exigem cuidado em repositório e divulgação.
12. **Escopo "Município" é ambíguo.** São 10 entidades, cada uma consultada separadamente,
    e não existe consulta consolidada no endpoint.
13. **Anos fora da lista oficial** (2010, 2015) respondem, mas não têm respaldo do portal.
14. Os dados são um retrato do sistema contábil no momento da consulta ("sujeitas a
    alteração"). Consultas em datas diferentes podem divergir.
15. Na movimentação do empenho 5659/2025, o saldo corrente não é monotônico entre 11/06 e
    06/07/2026. Os lançamentos parecem ordenados por data, com números de liquidação fora de
    ordem. Serve de alerta para não confiar em saldo corrente sem recalcular.

---

## 10. PONTOS QUE AINDA PRECISAM DE VALIDAÇÃO

1. A **semântica contábil** de cada campo (`proc`, `aproc`, `canceladoProc`,
   `canceladoAProc`, `pagoProc`, `pagoAProc`, `liquidado`, `pagoProcEstornado`,
   `pagoAProcEstornado`, `retencao`). Até agora só vale para um empenho de cada tipo.
2. **Fórmula de saldo** de RP processado e não processado, inclusive nos casos de
   estorno/cancelamento que migram de coluna (exemplo 11963/2016).
3. Se `proc`/`aproc` com `dataInicial = 01/01` equivalem ao **valor inscrito** oficial.
   Confirmado num caso só.
4. **Conciliação** dos totais da API com o **RREO Anexo VII** (PDF) de pelo menos um
   exercício fechado (2025) e com o 1º/2º bimestre de 2026. Nada foi conciliado ainda.
5. Se o universo de linhas depende das datas, do `exercicio` ou dos dois (os testes
   cruzados deram resultados incoerentes).
6. Colunas do CSV da aba Não Processados. Formatos XLS, PDF, TXT, RTF, DOC e HTML.
7. Filtros `cnpjCpf`, `fonteRecurso` e os demais `programatica.*`.
8. `dataFinal` isoladamente obrigatório ou não.
9. Limite real de requisições e comportamento sob carga.
10. Exercícios disponíveis nas entidades 3 a 11 e 15, e quais delas têm Restos a Pagar.
11. Decodificação da `programatica` de **27 dígitos** e o motivo da ausência dos campos
    `orgao`…`elemento` em parte dos registros.
12. O que significam `anoempenho` e `empenho` com números como `2411034/2025` (empenhos de
    30/12/2025 com numeração na casa dos 2,4 milhões, formato diferente dos demais).
13. Se a tela `/restos-a-pagar` é considerada funcionalidade oficial pela Prefeitura, já que
    não está no menu.
14. Se os dados de 2010 e 2015 retornados pela API são válidos.

---

## 11. VIABILIDADE DE AUTOMAÇÃO

**Classificação: AUTOMÁTICA**

**É possível automatizar?** **SIM.** O endpoint devolve JSON estruturado e paginado por
GET simples:
- sem autenticação, sem sessão, sem cookie, sem CAPTCHA e sem mecanismo anti-bot observado;
- com parâmetros previsíveis (entidade, exercício, período, tipo, página);
- reproduzível: a mesma URL devolve o mesmo resultado, salvo atualização da base.

**Método:** endpoint estruturado usado pelo portal (não documentado). A exportação CSV fica
como alternativa secundária.

- **Autenticação:** nenhuma.
- **Intervenção humana:** nenhuma para coletar. Precisa de decisão humana para interpretar
  os campos contábeis (item 10).
- **Riscos:**
  - **Quebra:** o endpoint não é documentado e o portal é atualizado com frequência. Médio
    a alto.
  - **Semântica:** os rótulos não bastam e os valores dependem do período. Alto, se não for
    validado.
  - **Carga:** limite de requisições desconhecido. Recomenda-se ritmo moderado.
- **Dependência da estrutura visual:** nenhuma. Não há raspagem de HTML.
- **Possibilidade de reprodução:** alta, desde que se guarde a URL completa, a data/hora da
  coleta e a resposta bruta, porque a base muda.

---

## 12. RECOMENDAÇÃO TÉCNICA PARA A ETAPA 02

Com base só no que foi descoberto; nada disso foi implementado.

1. **Fonte principal:** `GET /portaltransparencia-api/empenhos/restos-a-pagar`, em JSON.
   - Reproduzir exatamente os parâmetros da tela: `exercicio=A`, `dataInicial=A-01-01`,
     `dataFinal=A-12-31`, `tipoPesquisa=Processados` e `NaoProcessados`.
   - Nunca misturar ano de `exercicio` com datas de outro ano.
2. **Camada bruta primeiro:**
   - gravar cada página exatamente como recebida, com URL, parâmetros, data/hora, status
     HTTP e SHA-256;
   - usar `size` até 2000, requisições sequenciais com pausa e nova tentativa só em 5xx;
   - checar `totalElements` contra a soma de `numberOfElements`.
3. **Checagem de esquema a cada coleta:** conjunto esperado de chaves, tamanho da
   `programatica`, tipos. Mudança deve alertar, nunca ser ajustada em silêncio.
4. **Validação contábil antes de qualquer indicador.** Conciliar os totais do exercício
   2025 (e 2026 até o 2º bimestre) com o **RREO Anexo VII** do portal. Usar a
   **movimentação por empenho** para esclarecer os casos de estorno e cancelamento. Só depois
   definir "inscrito", "pago", "cancelado" e "saldo".
5. **Decisões que são suas antes da Etapa 02:**
   - (a) quais entidades formam "o Município" — só a 1, todas as 10 ou a 1 + 15…;
   - (b) quais exercícios, sendo 2016–2026 os oficiais;
   - (c) se interessa a evolução mensal, já que `dataFinal` permite posições intermediárias;
   - (d) como tratar os dados de pessoas físicas.
6. **Não usar** o `/empenhos/lista?restosAPagar=true` (filtro ignorado). **Não usar** o CSV
   como fonte principal (lento, 7 colunas).
7. Enriquecimento pelo `/empenhos/detalhe` só se for necessário, porque exige uma chamada
   por empenho.

---

## Anexo A — Arquivos em `amostras_brutas/`

| Arquivo | Requisição (GET, base `https://servicos.pontagrossa.pr.gov.br/portaltransparencia-api`) |
|---|---|
| `restos-a-pagar_entidade1_exercicio{2016,2021,2026}_{Processados,NaoProcessados}_page0_size50.json` | `/empenhos/restos-a-pagar?entidade=1&exercicio=A&tipoPesquisa=T&dataInicial=A-01-01&dataFinal=A-12-31&page=0&size=50` |
| `restos-a-pagar_ent1_ex2026_SemTipo_page0_size20.json` | `/empenhos/restos-a-pagar?entidade=1&exercicio=2026&dataInicial=2026-01-01&dataFinal=2026-12-31&size=20` |
| `restos-a-pagar_ent1_ex2026_Processados_emp5659-2025_periodo_2026-01-01_a_2026-12-31.json` | idem, `tipoPesquisa=Processados&empenho=5659&anoempenho=2025` |
| `restos-a-pagar_ent1_ex2026_Processados_emp5659-2025_periodo_2026-02-01_a_2026-03-31.json` | idem, `dataInicial=2026-02-01&dataFinal=2026-03-31` |
| `restos-a-pagar_ent15_ex2026_NaoProcessados_page0_size20.json` | `/empenhos/restos-a-pagar?entidade=15&exercicio=2026&tipoPesquisa=NaoProcessados&dataInicial=2026-01-01&dataFinal=2026-12-31&size=20` |
| `restos-a-pagar_exercicio2015_teste.json` | `/empenhos/restos-a-pagar?entidade=1&exercicio=2015&tipoPesquisa=Processados&dataInicial=2015-01-01&dataFinal=2015-12-31&size=3` |
| `restos-a-pagar_erro500_sem_dataInicial.json` | `/empenhos/restos-a-pagar?entidade=1&exercicio=2026&tipoPesquisa=Processados&size=5` |
| `export_report_csv_ent1_ex2026_Processados_COMPLETO.csv` (+ `_headers.txt`) | `/empenhos/restos-a-pagar/report?entidade=1&exercicio=2026&tipoPesquisa=Processados&dataInicial=2026-01-01&dataFinal=2026-12-31&size=20&exportType=csv` |
| `empenho_detalhe_ent1_ex2025_emp5659.json` | `/empenhos/detalhe?search=id.entidade%3D%3D1&entidade=1&exercicio=2025&empenho=5659` |
| `empenho_detalhe_movimentacao_ent1_ex2025_emp5659.json` | `/empenhos/detalhe/movimentacao?entidade=1&exercicio=2025&empenho=5659` |
| `empenho_detalhe_movimentacao_ent1_ex2016_emp11963.json` | `/empenhos/detalhe/movimentacao?entidade=1&exercicio=2016&empenho=11963` |
| `empenho_detalhe_pagamentos_ent1_ex2025_emp5659.json` | `/empenhos/detalhe/pagamentos?search=id.entidade%3D%3D1&entidade=1&exercicio=2025&empenho=5659` |
| `openapi_v3_api-docs.json` | `/v3/api-docs` |
| `api_exercicios_entidade_1.json` | `/api/exercicios/entidade/1` |
| `api_entidades_lista.json` | `/api/entidades/lista` |
| `parametros_menu_1_2026.json` | `/parametros/menu/1/2026` |
| `api_publicacoes_1_ent1_ex2026.json` | `/api/publicacoes/1?entidade=1&exercicio=2026` |

Os arquivos contêm dados públicos do portal, inclusive nomes de pessoas físicas. **Não
devem ir para repositório público** sem a decisão do item 12.5(d).
