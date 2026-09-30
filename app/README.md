# app — coletor de Restos a Pagar (Ponta Grossa)

Código de **produção**:
- **04.1:** coletor e camada bruta.
- **04.2:** processamento, com a normalização (camada 1) e a derivação (camada 2) de todas as regras lado a lado.

## Onde fica cada coisa (`config.toml`)

- **Banco ativo e logs:** `C:\Users\maped\RestosAPagar_local\`, fora do OneDrive.
- **Snapshots brutos** (`../snapshots`) e **backups** (`../backups`): no projeto. São arquivos gravados uma única vez.
- Se o banco se perder: `python -m rp reconstruir --destino NOVO.sqlite` refaz tudo a partir de `snapshots/`.

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

Testes (nenhum acessa a internet; um deles sobe um servidor HTTP local em 127.0.0.1):

```bash
python -m pytest tests
```

Dependências: Python 3.11+ (desenvolvido e testado em 3.14), `requests` e `pymupdf` (este só para transcrever o PDF do RREO), nas versões fixadas em `requirements.txt`: a transcrição do RREO depende das coordenadas de texto que o PyMuPDF devolve.
