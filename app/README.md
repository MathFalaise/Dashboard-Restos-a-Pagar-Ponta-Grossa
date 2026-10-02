# app — coletor de Restos a Pagar (Ponta Grossa)

Código de **produção**:
- **04.1:** coletor e camada bruta.
- **04.2:** processamento, com a normalização (camada 1) e a derivação (camada 2) de todas as regras lado a lado.
- **Revisão corretiva 01–04.4:** camada de consulta somente leitura para o futuro dashboard (`rp/painel`), governança e parâmetros das regras, evidência externa e registro do método de extração do RREO (esquema v4).
- **04.5:** interface pública somente leitura (`rp/interface`), sobre a camada `rp/painel`: `python -m rp interface`.

**Fontes** (detalhe em `../etapa04/ARQUITETURA_FONTES.md`):
- API do Portal da Transparência de Ponta Grossa (Elotech/Oxy Transparência) → fonte primária dos dados operacionais de RP;
- RREO Anexo VII → publicação oficial independente, usada só para reconciliação e auditoria. Uma divergência nunca altera o valor da API.

## Onde fica cada coisa (`config.toml`)

- **Banco ativo e logs:** `C:\Users\maped\RestosAPagar_local\`, fora do OneDrive.
- **Snapshots brutos** (`../snapshots`) e **backups** (`../backups`): no projeto. São arquivos gravados uma única vez.
- Se o banco se perder: `python -m rp reconstruir --destino NOVO.sqlite` refaz tudo a partir de `snapshots/` (depois, `python -m rp processar` recria normalização e derivação com os mesmos hashes).
- Backup com mais de 100 MB (limite por arquivo do GitHub) fica só na cópia local, listado pelo nome no `.gitignore` e nunca apagado. Hoje: `backups/20260930-145737_antes-migracao-v3-v4.sqlite` (120,5 MB). O repositório não depende dele: o armazém `snapshots/` basta para reconstruir o banco.

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

## Comandos (rodar dentro de `app/`)

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
- **Telas:** Resumo (indicadores do corte, entidades abrangidas, retratos e conferência com o RREO), Entidades, Empenhos (filtros e paginação), detalhe de um empenho (valores, classificação, par espelhado, movimentação e origem do dado), Retratos e comparação de retratos, Reconciliação com o RREO (e coerência entre publicações), Metodologia e fontes, e a área técnica de pares espelhados.
- **Fonte e natureza:** todo valor mostra fonte (API Elotech ou RREO Anexo VII), natureza (`da_fonte`, `publicado`, `derivado`, `analitico`, `diferenca`) e regra; a origem (snapshot, derivação, resposta HTTP, hash do objeto bruto) fica num bloco "Origem do dado".
- **Retrato:** toda tela de valores diz exercício, corte e data da coleta ("Estado atual da base para o exercício de 2024, corte 31/12/2024, coletado em 30/09/2026"). O campo "Como estava em" mostra o retrato vigente numa data.
- **Dados pessoais:** listas e totais sem nome, código ou documento do credor (só o tipo); detalhe com nome de pessoa jurídica sem documento; nome de pessoa física omitido; filtro de credor só por CNPJ completo de pessoa jurídica. Não há modo interno na interface.
- **Regras:** só regra operacional compõe indicador. Visões analíticas (CONS-PAR) não aparecem; regras experimentais ou não recomendadas aparecem rotuladas na reconciliação, na metodologia e como "valor analítico (não oficial)" no detalhe.

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

Testes (nenhum acessa a internet; os da interface bloqueiam qualquer conexão para fora e sobem um servidor HTTP em 127.0.0.1; `test_casos_reais.py` e `test_interface_casos_reais.py` montam um banco temporário a partir do armazém real `../snapshots`, só com leitura):

```bash
python -m pytest tests
```

Dependências: Python 3.11+ (desenvolvido e testado em 3.14), `requests` e `pymupdf` (este só para transcrever o PDF do RREO), nas versões fixadas em `requirements.txt`: a transcrição do RREO depende das coordenadas de texto que o PyMuPDF devolve.
