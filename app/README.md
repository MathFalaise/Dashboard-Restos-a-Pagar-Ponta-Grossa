# app — coletor de Restos a Pagar (Ponta Grossa)

Código de **produção**:
- **04.1:** coletor e camada bruta.
- **04.2:** processamento, com a normalização (camada 1) e a derivação (camada 2) de todas as regras lado a lado.
- **Revisão corretiva 01–04.4:** camada de consulta somente leitura para o futuro dashboard (`rp/painel`), governança e parâmetros das regras, evidência externa e registro do método de extração do RREO (esquema v4).
- **04.5:** interface pública somente leitura (`rp/interface`), sobre a camada `rp/painel`: `python -m rp interface`.
- **04.6:** homologação da interface: situação de cada dado, busca por empenho, resultado vazio sem R$ 0,00, análise experimental rotulada, configuração portátil, portões de uma carga nova (`python -m rp portoes`) e procedimento de instalação e atualização.
- **04.7:** encerramento técnico da Etapa 04, sem mudança de código: plano atualizado (`../etapa04/PLANO_ETAPA04.md`), relatório consolidado (`../etapa04/RELATORIO_ETAPA04_FINAL.md`) e ponto de restauração (tag `etapa-04-final`).
- **05.1:** contrato analítico da Etapa 05 (`../etapa05/CONTRATO_ANALITICO.md`) e ferramenta de recálculo independente a partir do JSON bruto (`tests/recalculo_bruto.py`), sem mudança no código de produção.
- **05.2:** evolução dentro do exercício: tela `/evolucao` com todos os cortes do exercício (corte sem dado aparece como lacuna, com o motivo), diferença entre cortes vizinhos e gráfico SVG gerado no servidor; `Painel.evolucao` passou a listar todos os cortes para qualquer escopo (R1).
- **05.3:** série entre exercícios (`/historico`): cada exercício no corte representativo (31/12, ou o último corte com o Município completo), com o retrato "estado atual da base" em todo ponto; fechamento de A × abertura de A+1 pela FAIXA v1 e a verificação de continuidade da derivação.

**Fontes** (detalhe em `../etapa04/ARQUITETURA_FONTES.md`):
- API do Portal da Transparência de Ponta Grossa (Elotech/Oxy Transparência) → fonte primária dos dados operacionais de RP;
- RREO Anexo VII → publicação oficial independente, usada só para reconciliação e auditoria. Uma divergência nunca altera o valor da API.

## Onde fica cada coisa (`config.toml`)

- **Banco ativo e logs:** `~/RestosAPagar_local/` (pasta do usuário, em qualquer sistema), fora do OneDrive. Outra pasta: variável de ambiente `RP_DADOS_LOCAIS` (caminho relativo = a partir de `app/`). O banco fica em `<pasta>/banco/restos_a_pagar.sqlite` e os logs em `<pasta>/logs/`.
- **Outro arquivo de configuração:** variável `RP_CONFIG` ou `python -m rp --config ARQUIVO ...`.
- **Snapshots brutos** (`../snapshots`) e **backups** (`../backups`): no projeto. São arquivos gravados uma única vez.
- Se o banco se perder: `python -m rp reconstruir --destino NOVO.sqlite` refaz tudo a partir de `snapshots/` (depois, `python -m rp processar` recria normalização e derivação com os mesmos hashes).
- Backup com mais de 100 MB (limite por arquivo do GitHub) fica só na cópia local, listado pelo nome no `.gitignore` e nunca apagado. Hoje: `backups/20260930-145737_antes-migracao-v3-v4.sqlite` (120,5 MB). O repositório não depende dele: o armazém `snapshots/` basta para reconstruir o banco.

## Instalação em outra máquina

Testado num ambiente Python novo, sem pacotes, a partir de uma cópia do repositório fora do OneDrive (relatório da 04.6, seção 15). Nenhum caminho da máquina de desenvolvimento é necessário.

1. Python 3.11 ou mais novo (desenvolvido e testado só em 3.14.3). Dentro de `app/`, crie o ambiente e instale as dependências fixadas (`requirements.txt` = execução; `requirements-dev.txt` = execução + `pytest`; a interface sozinha usa só a biblioteca padrão; em Linux/macOS o executável é `.venv/bin/python`):

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python -m pip install -r requirements-dev.txt
```

2. Reconstrua o banco a partir do armazém `../snapshots` no caminho do banco ativo, `<pasta local>/banco/restos_a_pagar.sqlite` (o comando nunca sobrescreve um arquivo existente):

```bash
python -m rp reconstruir --destino ~/RestosAPagar_local/banco/restos_a_pagar.sqlite
```

3. Processe (normalização + derivação, cerca de 20 s) e, para a reconciliação "como estava em" 29/09/2026, a derivação dessa data:

```bash
python -m rp processar
```

```bash
python -m rp processar --normalizacao 1 --em 2026-09-29T23:59:59-03:00
```

4. Confira: `python -m rp verificar` (sem problemas), `python -m rp portoes` (apto) e `python -m pytest tests`. Os hashes de resultado devem ser os do projeto (`2f6b4e29…` e `b8a0b2ed…`).

5. Abra a interface com `python -m rp interface` e acesse `http://127.0.0.1:8050/`.

## Atualização dos dados

Sempre COLETAR → VALIDAR → PROCESSAR → TESTAR → VERIFICAR → DISPONIBILIZAR. Nunca coletar por cima do banco e publicar: a coleta nova vira um snapshot a mais, e o retrato anterior continua no armazém e no banco.

1. **Referência do bruto**, antes de coletar (o arquivo nunca é sobrescrito): `python -m rp portoes --gravar-referencia ../etapa04/resultados/referencia_AAAAMMDD.json`
2. **Backup:** `python -m rp backup --motivo antes-carga-AAAAMMDD`
3. **Coletar:** `coletar-catalogos`, `coletar-listagem` de cada entidade e corte, `coletar-rreo` (e `coletar-movimentacao` quando necessário). Coleta que termina `incompleta` ou `falhou` fica registrada, mas não vira retrato válido.
4. **Validar:** `python -m rp verificar`, e `comparar-snapshots` / `comparar` para ver o que mudou em relação ao retrato anterior.
5. **Processar:** `python -m rp processar` (e `--em` para as datas históricas que se queira reconciliar).
6. **Testar:** `python -m pytest tests` e, em `../etapa03/validacao`, os 26 testes da investigação.
7. **Verificar os portões:** `python -m rp portoes --referencia ../etapa04/resultados/referencia_AAAAMMDD.json`. Só com `"apto": true` e os testes passando a carga é disponibilizada.
8. **Disponibilizar:** reiniciar `python -m rp interface`. A interface lê a derivação atual mais recente; nenhum snapshot é substituído.

Portões verificados por `portoes` (somente leitura):
- integridade do SQLite;
- armazém × banco (`verificar`);
- snapshot mais recente de cada corte completo;
- normalização em dia (nenhum snapshot sem processar);
- derivação atual sobre a normalização mais recente, cobrindo todo registro;
- proveniência (todo registro → resposta HTTP → objeto bruto);
- linhas do bruto anteriores à carga idênticas às da referência.

Os testes são conferidos por quem disponibiliza. Se um portão falhar, o retrato novo não é disponibilizado como válido (código de saída 1).

## Proteções

- O banco ativo não abre dentro de uma pasta do OneDrive (erro `BancoEmPastaSincronizada`).
- `config.toml` é validado: a API só em `https`, sem credencial na URL; números fora de faixa e `user_agent` com quebra de linha são recusados.
- HTTP: redirecionamento não é seguido (um 3xx fica registrado como falha); o corpo de cada resposta tem teto (`limite_resposta_bytes`, 64 MiB) e prazo total de leitura (3 × `timeout_segundos`); `Retry-After` do servidor é limitado a 300 s.
- A paginação para quando a soma das páginas passa de `totalElements` ou chega a 10.000 páginas (servidor que ignore `page` não prende o coletor).
- Hash de objeto é validado antes de virar caminho de arquivo; descompressão tem teto; manifesto nunca é sobrescrito, nem por duas gravações simultâneas.
- Backup nunca sobrescreve outro backup (sufixo `-2`, `-3`... no mesmo segundo); o `--motivo` não escolhe pasta.
- `comparar --saida` recusa arquivo existente. Erro de uso sai como uma linha JSON `{"erro": ...}` com código 4 (detalhe no log). Códigos de saída: 0 ok; 1 `verificar` achou problema; 2 coleta incompleta ou com falha; 3 exclusão recusada; 4 comando recusado.
- Saída redirecionada para arquivo em cp1252 não derruba o programa: caractere que a codificação não representa (ex.: "→") sai como `→`.
- `apagar-execucao` protege a derivação mais recente de cada vigência (a atual e a de cada data "como estava em").

## Comandos (rodar dentro de `app/` ou na raiz do projeto)

Na raiz do projeto, o atalho `rp.py` encaminha `python -m rp ...` para o pacote em `app/rp`, com a mesma configuração. Em qualquer outra pasta, o Python não acha o pacote (`No module named rp`).

Criar pastas e banco:

```bash
python -m rp iniciar
```

Catálogo de entidades e exercícios:

```bash
python -m rp coletar-catalogos
```

Listagem de restos a pagar de uma entidade até uma data (sempre a partir de 01/01, sem tipo):

```bash
python -m rp coletar-listagem --entidade 1 --exercicio 2026 --data-final 2026-08-31
```

Publicações do RREO e PDFs do Anexo VII ainda não baixados:

```bash
python -m rp coletar-rreo --exercicio 2026
```

Só os PDFs de alguns bimestres (o rótulo pode vir como "6º Bimestre" ou "6º BIMESTRE"):

```bash
python -m rp coletar-rreo --exercicio 2024 --bimestres 6
```

Nova coleta de um corte já coletado, com EXATAMENTE os parâmetros de um snapshot anterior (que não é tocado):

```bash
python -m rp recoletar --snapshot <snapshot_uid>
```

Comparar dois snapshots do mesmo corte (somente leitura): registros novos, removidos e alterados, campo a campo, e o impacto financeiro:

```bash
python -m rp comparar --a <uid_anterior> --b <uid_posterior> --saida comparacao.json
```

Movimentação de um empenho (sob demanda):

```bash
python -m rp coletar-movimentacao --entidade 1 --anoempenho 2025 --empenho 5659
```

Normalizar e derivar todos os snapshots do banco. Cria novas execuções e imprime o `hash_resultado`; o mesmo bruto com as mesmas regras dá sempre o mesmo hash:

```bash
python -m rp processar
```

Derivação "como estava em" uma data: considera só os snapshots coletados até ela:

```bash
python -m rp processar --em 2026-09-29T23:59:59-03:00
```

Derivar de novo sobre uma normalização existente:

```bash
python -m rp processar --normalizacao 4
```

Listar execuções de processamento:

```bash
python -m rp execucoes
```

Ver o que seria apagado:

```bash
python -m rp apagar-execucao --tipo derivacao --id 3 --simular
```

Apagar UMA execução inteira (confirmação repetindo o id; faz backup operacional antes e verifica a integridade depois). A pasta `backups_operacionais/` mantém os 3 mais recentes; um arquivo listado em `backups_operacionais/PRESERVAR.txt` (um nome por linha) nunca é apagado pela retenção:

```bash
python -m rp apagar-execucao --tipo derivacao --id 3 --confirmar 3
```

Devolver ao disco o espaço de execuções apagadas (VACUUM):

```bash
python -m rp compactar
```

Importar o bruto das Etapas 01/02 como snapshots históricos (idempotente):

```bash
python -m rp importar-etapas-anteriores
```

Retratos do mesmo corte, comparando bytes e registros:

```bash
python -m rp comparar-snapshots --entidade 1 --exercicio 2025 --data-final 2025-12-31
```

Integridade do armazém × banco:

```bash
python -m rp verificar
```

Registrar no banco manifestos que ainda não estão lá:

```bash
python -m rp sincronizar
```

Cópia do banco para `backups/`:

```bash
python -m rp backup --motivo manual
```

Contagens:

```bash
python -m rp situacao
```

Registrar documento externo (e-SIC, norma, nota técnica): guarda o arquivo com SHA-256, grava manifesto imutável em `snapshots/evidencias/` e a linha em `evidencia_externa`:

```bash
python -m rp registrar-evidencia --tipo e-SIC --descricao "Resposta sobre as cópias 24xxxxx" --arquivo resposta.pdf --origem "e-SIC, protocolo n." --data 2026-10-15
```

## Interface pública (somente leitura)

```bash
python -m rp interface
```

Abre em `http://127.0.0.1:8050/` (use `--porta` para outra porta e `--banco` para outro arquivo). Só esta máquina acessa, a menos que se passe `--host`; com outro host, a interface avisa que fica acessível pela rede sem autenticação.

- **Fluxo:** API Elotech → coletor → snapshot imutável → normalização → derivação → `rp/painel` → `rp/interface`. A interface nunca chama a API da Elotech: funciona com a internet desligada e com o portal fora do ar. A coleta continua sendo outro processo.
- **Somente leitura:** cada requisição abre o banco em modo só leitura (URI `mode=ro` + `PRAGMA query_only`); só GET e HEAD; nada de JavaScript, CDN, fonte externa ou imagem externa; cabeçalhos de segurança com CSP restritiva.
- **Telas:** Resumo (indicadores do corte, entidades abrangidas, retratos e conferência com o RREO), Evolução no exercício (todos os cortes, lacunas, diferenças e gráfico), Série entre exercícios (2016–2026, fechamento × abertura), Entidades, Empenhos (filtros, busca por ano e número do empenho e paginação), detalhe de um empenho (valores, classificação, par espelhado, movimentação e origem do dado), Retratos e comparação de retratos, Reconciliação com o RREO (e coerência entre publicações), Metodologia e fontes, e a área técnica de pares espelhados.
- **Fonte e natureza:** todo valor mostra fonte (API Elotech ou RREO Anexo VII), natureza (`da_fonte`, `publicado`, `derivado`, `analitico`, `diferenca`) e regra; a origem (snapshot, derivação, resposta HTTP, hash do objeto bruto) fica num bloco "Origem do dado".
- **Retrato:** toda tela de valores diz exercício, corte, data da coleta, tipo de retrato (atual ou "como estava em") e snapshots usados ("Estado atual da base para o exercício de 2024, corte 31/12/2024, coletado em 30/09/2026"). O campo "Como estava em" mostra o retrato vigente numa data.
- **Situação do dado:** dado existente; entidade existente sem RP (o único zero); entidade inexistente no exercício; corte não coletado; corte coletado, mas ainda não processado; dado indisponível (só coleta incompleta ou com falha); diferença em relação ao RREO. Só as duas primeiras têm valor. Filtro sem registro mostra "Nenhum resultado encontrado", nunca R$ 0,00.
- **Dados pessoais:** listas e totais sem nome, código ou documento do credor (só o tipo); detalhe com nome de pessoa jurídica sem documento; nome de pessoa física omitido; filtro de credor só por CNPJ completo de pessoa jurídica. Não há modo interno na interface.
- **Regras:** só regra operacional compõe indicador. Visões analíticas (CONS-PAR) não aparecem. Regras experimentais ou não recomendadas aparecem só rotuladas como ANÁLISE EXPERIMENTAL (ou análise de regra não recomendada): na reconciliação, na metodologia e numa seção própria do detalhe.

## Camada de consulta do dashboard (somente leitura)

`rp.painel.Painel` abre o banco em modo só leitura e nunca chama a API. Todo valor sai com natureza (`da_fonte`, `publicado`, `derivado`, `analitico`, `diferenca`), regras e situação delas, fonte, rótulo de retrato ("Estado atual da base..." ou "Como a base estava em...") e proveniência até o objeto bruto. O nível `publico` (padrão) não traz identificação de credor em listagens; `--nivel interno` só quando pedido.

Consultas (saída JSON): `contexto`, `cortes`, `entidades`, `indicadores`, `evolucao`, `dimensao`, `empenhos`, `empenho`, `fornecedores`, `pares`, `retratos`, `comparar-retratos`, `reconciliacao`, `coerencia`, `analitica`, `regras`, `evidencias`, `fontes`, `metodologia`, `dicionario`.

Indicadores do Município num corte:

```bash
python -m rp painel indicadores --exercicio 2024 --data-final 2024-12-31
```

Como a base estava numa data (a reconciliação dessa data exige `processar --em` com a mesma data):

```bash
python -m rp painel indicadores --exercicio 2025 --data-final 2025-12-31 --entidade 1 --em 2026-09-29
```

Detalhe de um empenho (padrão: o último corte processado do exercício):

```bash
python -m rp painel empenho --entidade 1 --anoempenho 2025 --empenho 5659 --exercicio 2026
```

Área de reconciliação com o RREO (só as diferenças):

```bash
python -m rp painel reconciliacao --exercicio 2026 --escopo entidade --somente-diferencas
```

Coerência entre publicações (L de A × (a)+(f) de A+1), com a API ao lado:

```bash
python -m rp painel coerencia
```

Situação de governança de cada regra (histórico de decisões e parâmetros):

```bash
python -m rp painel regras
```

Testes (nenhum acessa a internet; os da interface bloqueiam qualquer conexão para fora e sobem um servidor HTTP em 127.0.0.1; `test_casos_reais.py`, `test_interface_casos_reais.py` e `test_homologacao_real.py` montam um banco temporário a partir do armazém real `../snapshots`, só com leitura; `test_homologacao_real.py` recalcula os indicadores direto do JSON bruto da API):

```bash
python -m pytest tests
```

Dependências: Python 3.11+ (desenvolvido e testado em 3.14.3), `requests` e `pymupdf` (este só para transcrever o PDF do RREO), nas versões fixadas em `requirements.txt`: a transcrição do RREO depende das coordenadas de texto que o PyMuPDF devolve. Para os testes, `pytest` (`requirements-dev.txt`). A interface e a camada painel não importam nenhum pacote de terceiros.
