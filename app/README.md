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
- **05.4:** composição do saldo (`/composicao`): inscrição e saldo do corte por categoria, faixa (FAIXA v1, só em valores), tipo de credor, fonte de recurso, órgão, função, programa e elemento, com o grupo "sem classificação"; cada dimensão só aparece se fechar com o total do corte, e cada grupo leva à lista de empenhos correspondente (filtros novos de faixa e classificação orçamentária).
- **05.5:** investigação de variações (`/variacao`): para dois cortes do mesmo exercício, a variação do saldo S1 ou dos pagamentos explicada empenho por empenho (classes, maiores aumentos e reduções, lista completa paginada), com fechamento ao centavo; e o empenho em todos os cortes do exercício (`/empenho/cortes`).
- **05.6:** qualidade dos dados (`/qualidade`): anomalias da derivação por tipo, com as ocorrências e a ligação ao registro quando há chave de empenho; verificações de conjunto interpretadas pela descrição (catálogo do contrato); e as diferenças com o RREO contadas pelas cinco situações (sem diferença, explicada, parcialmente explicada, hipótese, não determinada).
- **05.7:** homologação e encerramento da Etapa 05 (`../etapa05/RELATORIO_ETAPA05_FINAL.md`): regressão completa, valores homologados da 04.6 inalterados, 100.201 valores das telas novas conferidos com a camada painel, acessibilidade básica, interface sem rede e instalação limpa; tag `etapa-05-final` (commit `b38e884`).
- **Pós-05:** encerramento formal e consolidação técnica (`../etapa05/CONSOLIDACAO_POS_05.md`): a seleção de exercício e corte nunca troca o que foi pedido. Corte não processado aparece como indisponível, com a situação do dado e os cortes processados do exercício. Inclui o mapa da dívida técnica, o procedimento da D1, a proposta de CI e as auditorias de dados e licenças.
- **Revisão crítica (05/10/2026):** resposta item a item em `../auditoria/REVISAO_CRITICA_RESPOSTA.md`. Retrato com chave de empenho repetida nunca é o vigente; a coleta pede a ordem e confere o eco; catálogos com contrato mínimo; prazo total absoluto por requisição; contrato da API documentado (`../auditoria/CONTRATO_API_ELOTECH.md`) e comando `diagnosticar-api`; impressão do esquema; marcador de testes `dados_reais`; CI e pacote instalável.

**Fontes** (detalhe em `../etapa04/ARQUITETURA_FONTES.md`):
- API do Portal da Transparência de Ponta Grossa (Elotech/Oxy Transparência) → fonte primária dos dados operacionais de RP;
- RREO Anexo VII → publicação oficial independente, usada só para reconciliação e auditoria. Uma divergência nunca altera o valor da API.

## Onde fica cada coisa (`config.toml`)

- **Banco ativo e logs:** `~/RestosAPagar_local/` (pasta do usuário, em qualquer sistema), fora do OneDrive. Outra pasta: variável de ambiente `RP_DADOS_LOCAIS` (caminho relativo = a partir de `app/`). O banco fica em `<pasta>/banco/restos_a_pagar.sqlite` e os logs em `<pasta>/logs/` (um arquivo por dia; os de mais de 90 dias saem sozinhos).
- **Outro arquivo de configuração:** variável `RP_CONFIG` ou `python -m rp --config ARQUIVO ...`.
- **Snapshots brutos** (`../snapshots`) e **backups** (`../backups`): no projeto. São arquivos gravados uma única vez. Só os 466 snapshots da base homologada estão no Git: desde 06/10/2026 (decisão D2) `snapshots/` está no `.gitignore` e um snapshot novo só é versionado com `git add -f`. Guarde a pasta inteira (por exemplo, no OneDrive): o banco só é reconstruível com ela.
- Se o banco se perder: `python -m rp reconstruir --destino NOVO.sqlite` refaz tudo a partir de `snapshots/` (depois, `python -m rp processar` recria normalização e derivação com os mesmos hashes).
- Backup com mais de 100 MB (limite por arquivo do GitHub) fica só na cópia local, listado pelo nome no `.gitignore` e nunca apagado. Hoje: `backups/20260930-145737_antes-migracao-v3-v4.sqlite` (120,5 MB). O repositório não depende dele: o armazém `snapshots/` basta para reconstruir o banco.

## Instalação em outra máquina

Testado num ambiente Python novo, sem pacotes, a partir de uma cópia do repositório fora do OneDrive (relatório da 04.6, seção 15). Nenhum caminho da máquina de desenvolvimento é necessário.

1. Python: **comprovado só no Windows 11 com Python 3.14.3**, onde o projeto foi desenvolvido e homologado. O código declara 3.11 ou mais novo, e o CI (`../.github/workflows/testes.yml`) roda os testes sintéticos em Linux e Windows com 3.11, 3.12, 3.13 e 3.14. Enquanto o CI não tiver rodado no GitHub, as outras combinações são só a intenção (até 05/10/2026 o importador nem carregava no 3.11). Dentro de `app/`, crie o ambiente e instale as dependências fixadas (`requirements.txt` = execução; `requirements-dev.txt` = execução + `pytest`; a interface sozinha usa só a biblioteca padrão; em Linux/macOS o executável é `.venv/bin/python`):

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python -m pip install -r requirements-dev.txt
```

No Windows, use uma pasta de caminho curto para a cópia do projeto: com o ambiente numa pasta muito profunda, o caminho de uma biblioteca nativa passa de 260 caracteres e não carrega. A instalação limpa da 05.7 viu isso com o `charset_normalizer`, dependência do `requests`: o `requests` emite `RequestsDependencyWarning` e fica sem detecção de codificação de texto.

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

4. Confira: `python -m rp verificar` (sem problemas), `python -m rp portoes` (apto) e `python -m pytest tests`. Os hashes de resultado devem ser os do projeto (`2f6b4e29…` e `b8a0b2ed…`). Para provar que o banco novo é equivalente a outro (ex.: o de outra máquina), camada a camada: `python -m rp comparar-bancos --banco NOVO.sqlite --outro OUTRO.sqlite` (código de saída 0 = equivalentes).

Para reproduzir exatamente o ambiente homologado, inclusive as dependências transitivas, instale `requirements-lock.txt` em vez de `requirements-dev.txt` (Python 3.14, Windows ou Linux de 64 bits). A trava tem o SHA-256 de cada arquivo: o pip recusa qualquer pacote que não seja exatamente o conferido. Atualizar uma versão exige gerar os hashes de novo (`pip download` do pacote para `win_amd64` e `manylinux` x86_64, Python 3.14, conferindo com os publicados no PyPI). O CI roda o `pip-audit` sobre a trava: versão travada com vulnerabilidade conhecida reprova.

Opcional: `python -m pip install -e .` (dentro de `app/`, sempre em modo editável) instala o comando `rp`, que funciona de qualquer pasta: `rp verificar` = `python -m rp verificar`. Instalado como cópia, o pacote não acharia `config.toml` nem o armazém.

5. Abra a interface com `python -m rp interface` e acesse `http://127.0.0.1:8050/`.

## Atualização dos dados

Sempre COLETAR → VALIDAR → PROCESSAR → TESTAR → VERIFICAR → DISPONIBILIZAR. Nunca coletar por cima do banco e publicar: a coleta nova vira um snapshot a mais, e o retrato anterior continua no armazém e no banco.

1. **Referência do bruto**, antes de coletar (o arquivo nunca é sobrescrito): `python -m rp portoes --gravar-referencia ../etapa04/resultados/referencia_AAAAMMDD.json`
2. **Backup:** `python -m rp backup --motivo antes-carga-AAAAMMDD`
3. **Coletar:** `coletar-catalogos`, `coletar-listagem` de cada entidade e corte, `coletar-rreo` (e `coletar-movimentacao` quando necessário). Coleta que termina `incompleta` ou `falhou` fica registrada, mas não vira retrato válido.
4. **Validar:** `python -m rp verificar`, e `comparar-snapshots` / `comparar` para ver o que mudou em relação ao retrato anterior.
5. **Processar:** `python -m rp processar` (e `--em` para as datas históricas que se queira reconciliar).
6. **Testar:** `python -m pytest tests` e, em `../etapa03/validacao`, os 26 testes da investigação.
7. **Verificar os portões:** `python -m rp portoes --referencia ../etapa04/resultados/referencia_AAAAMMDD.json`. Só com `"apto_sem_ressalvas": true` (apto e nenhum portão sem verificação, exceto os testes, conferidos à mão) e os testes passando a carga é disponibilizada. `"apto"` considera só os portões verificáveis; a lista do que não foi verificado sai em `"nao_verificados"`.
8. **Disponibilizar:** reiniciar `python -m rp interface`. A interface lê a derivação atual mais recente; nenhum snapshot é substituído.

Portões verificados por `portoes` (somente leitura):
- integridade do SQLite;
- armazém × banco (`verificar`);
- snapshot mais recente de cada corte completo;
- normalização em dia (nenhum snapshot sem processar);
- derivação atual sobre a normalização mais recente, cobrindo todo registro;
- proveniência (todo registro → resposta HTTP → objeto bruto);
- linhas do bruto anteriores à carga idênticas às da referência;
- o `hash_resultado` gravado de cada vigência é o recalculado do conteúdo atual das tabelas derivadas (nada foi alterado depois da derivação);
- integridade relacional: `PRAGMA foreign_key_check` e as relações que o esquema não protege com FOREIGN KEY (derivado → registro da mesma normalização, anomalia → coleta, par → registros, conciliação → PDF, snapshots citados em `coletas_json`);
- nenhum registro com campo monetário ausente (a normalização grava a ausência como 0; a carga precisa de decisão);
- nenhum tipo de lançamento de movimentação sem efeito conhecido;
- nenhum retrato com a mesma chave (entidade, anoempenho, empenho) mais de uma vez, com a natureza da repetição (exata ou conflitante);
- o esquema do banco é o da versão gravada (impressão digital de tabelas, colunas, restrições, índices e gatilhos).

Os testes são conferidos por quem disponibiliza. Se um portão falhar, o retrato novo não é disponibilizado como válido (código de saída 1).

## Proteções

- O banco ativo não abre em pasta sincronizada nem de rede (erro `BancoEmPastaSincronizada`): OneDrive, Dropbox, Google Drive, iCloud, Box, Nextcloud, caminho UNC ou unidade de rede mapeada. SQLite ativo precisa de disco local.
- Ao abrir, o esquema do banco é conferido com a impressão digital da versão; diferença vai para o log (e reprova o portão `esquema_confere`).
- `config.toml` é validado: a API só em `https`, sem credencial na URL; números fora de faixa e `user_agent` com quebra de linha são recusados.
- HTTP: redirecionamento não é seguido (um 3xx fica registrado como falha); o corpo de cada resposta tem teto (`limite_resposta_bytes`, 64 MiB); `Retry-After` do servidor é limitado a 300 s. Três prazos: conexão (`timeout_conexao_segundos`, 30 s), silêncio entre dois pedaços da resposta (`timeout_segundos`) e prazo total ABSOLUTO da requisição (3 × `timeout_segundos`), que vale mesmo contra um servidor que manda um byte por vez.
- A paginação para quando a soma das páginas passa de `totalElements` ou chega a 10.000 páginas (servidor que ignore `page` não prende o coletor).
- Soma = total não basta para dizer que a coleta está completa (auditoria técnica e revisão crítica, `../auditoria/`). A coleta de listagem PEDE a ordem (anoempenho, empenho) e só é `completa` se, além disso: cada página traz `number`, `numberOfElements`, `size`, `totalPages`, `first` e `empty` coerentes e ecoa a ordem pedida; nenhum registro idêntico reaparece em página seguinte; a ordem cresce na troca de página; nenhuma chave (entidade, anoempenho, empenho) se repete no retrato, dentro ou entre páginas; todo registro é da entidade pedida; e, com mais de uma página, uma segunda leitura de todas elas vem igual (os hashes vão para o manifesto, em `segunda_leitura`). Entidade ou exercício fora do catálogo vigente fica na observação: a API responde 200 vazio para entidade inexistente. O contrato observado da API está em `../auditoria/CONTRATO_API_ELOTECH.md`.
- Catálogo (entidades, exercícios, publicações) só é `completa` se cumprir um contrato mínimo: JSON válido não basta, porque um objeto de erro com HTTP 200 também é JSON.
- O manifesto de cada snapshot novo grava quando a coleta terminou (`coleta_finalizada_em`) e a estrutura da resposta (`contrato_api`: caminhos, tipos e o SHA-256 deles).
- Retrato com a mesma chave de empenho mais de uma vez (anomalia CHAVE-DUP), exata ou conflitante, nunca é o vigente do corte: derivação, painel e consultas usam o retrato válido anterior (com aviso) ou mostram o dado como indisponível. Nada é apagado: as ocorrências ficam no banco e na tela de qualidade. O portão `retrato_sem_chave_repetida` traz o comando de recoleta de cada retrato; recolete **mais tarde** (a segunda leitura da coleta já releu as páginas na hora), sem recoleta automática.
- `importar-etapas-anteriores`: o mesmo snapshot com outro conteúdo (bytes ou parâmetros) é conflito, nunca "já existe, então ignora"; carimbo com fuso é convertido para Brasília, não sobrescrito.
- HTTP: só falha transitória (tempo esgotado, conexão) é repetida; erro de TLS e URL inválida falham na hora; erro de programação no transporte não é tratado como rede.
- Migração de esquema é uma transação única (falha no meio não deixa o esquema pela metade); banco novo é montado num temporário e publicado no fim.
- O catálogo de regras gravado no banco precisa ser o do código: editar uma regra, parâmetro ou decisão já gravados é recusado (crie versão nova).
- Esquema v5 (decisão D4, 06/10/2026): gatilhos `ri_*` recusam na gravação a linha derivada sem a origem na mesma normalização (derivado, movimentação interpretada, par espelhado), a anomalia de coleta inexistente, o snapshot inexistente citado em `coletas_json`, a regra inexistente na derivação e apagar a camada 1 de uma normalização que ainda tem derivações. Nenhuma tabela foi recriada nem linha alterada; o portão `integridade_relacional` continua lendo, como segunda defesa.
- Promoção de regra a operacional (decisão D7, desde 06/10/2026), em dois trilhos: regra que **não** compõe indicador publicado exige evidência documentada e teste de regressão existente; regra que compõe exige também conferência independente registrada (evidência externa) ou, sem ela em 30 dias (prazo do e-SIC), uma ressalva escrita, que a metodologia mostra como "operacional com ressalva". O banco recusa por gatilho a promoção fora desses critérios. Promoção nova só por `decidir-regra`, nunca por evento versionado.
- `verificar` confere cada coleta com o seu manifesto campo a campo e relata objeto sem manifesto e arquivo temporário abandonado (nunca apaga).
- Hash de objeto é validado antes de virar caminho de arquivo; descompressão tem teto; manifesto nunca é sobrescrito, nem por duas gravações simultâneas.
- Backup nunca sobrescreve outro backup (sufixo `-2`, `-3`... no mesmo segundo); o `--motivo` não escolhe pasta.
- `comparar --saida` recusa arquivo existente. Erro de uso sai como uma linha JSON `{"erro": ...}` com código 4 (detalhe no log). Códigos de saída: 0 ok; 1 `verificar` achou problema (também: `portoes` não apto, `comparar-bancos` diferentes, `diagnosticar-api` viu a API mudar); 2 coleta incompleta ou com falha (também: `diagnosticar-api` não conseguiu consultar); 3 exclusão recusada; 4 comando recusado.
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

Apagar UMA execução inteira (confirmação repetindo o id; faz backup operacional antes e verifica a integridade depois). A pasta `backups_operacionais/` mantém os 3 mais recentes como estão e **comprime** os mais antigos (`<nome>.gz`, conferido byte a byte antes de remover o original; nada é apagado). Um arquivo listado em `backups_operacionais/PRESERVAR.txt` (um nome por linha) não entra na retenção:

```bash
python -m rp apagar-execucao --tipo derivacao --id 3 --confirmar 3
```

Comprimir os backups operacionais antigos que já existem, inclusive os preservados (sem `--confirmar`, só lista; os 3 mais recentes ficam como estão). Para voltar a um backup: `python -m gzip -d <nome>.sqlite.gz`:

```bash
python -m rp comprimir-backups --confirmar
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

Conferir se a API ainda responde como o coletor espera, antes de uma coleta. Consulta os catálogos e uma página pequena da listagem e compara a estrutura com a dos snapshots gravados; não grava nada (banco aberto só para leitura). Saída 0 = nada mudou, 1 = a API mudou, 2 = não deu para consultar:

```bash
python -m rp diagnosticar-api --entidade 1
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

Contagens e espaço ocupado por pasta (banco, armazém, backups, backups operacionais, logs):

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
- **Telas:** Resumo (indicadores do corte, entidades abrangidas, retratos e conferência com o RREO), Evolução no exercício (todos os cortes, lacunas, diferenças e gráfico), Série entre exercícios (2016–2026, fechamento × abertura), Composição do saldo (por dimensão, com fechamento), Variação entre cortes (contribuição de cada empenho), Entidades, Empenhos (filtros, inclusive faixa e classificação orçamentária, busca por ano e número do empenho e paginação), detalhe de um empenho (valores, classificação, par espelhado, movimentação e origem do dado), o empenho em todos os cortes do exercício, Retratos e comparação de retratos, Reconciliação com o RREO (e coerência entre publicações), Qualidade dos dados (anomalias, verificações e situação das diferenças), Metodologia e fontes, e a área técnica de pares espelhados.
- **Fonte e natureza:** todo valor mostra fonte (API Elotech ou RREO Anexo VII), natureza (`da_fonte`, `publicado`, `derivado`, `analitico`, `diferenca`) e regra; a origem (snapshot, derivação, resposta HTTP, hash do objeto bruto) fica num bloco "Origem do dado".
- **Retrato:** toda tela de valores diz exercício, corte, data da coleta, tipo de retrato (atual ou "como estava em") e snapshots usados ("Estado atual da base para o exercício de 2024, corte 31/12/2024, coletado em 30/09/2026"). O campo "Como estava em" mostra o retrato vigente numa data.
- **Situação do dado:** dado existente; entidade existente sem RP (o único zero); entidade inexistente no exercício; corte não coletado; corte coletado, mas ainda não processado; dado indisponível (só coleta incompleta ou com falha); dado indisponível porque o retrato do corte repete uma chave de empenho (CHAVE-DUP); diferença em relação ao RREO. Só as duas primeiras têm valor. Filtro sem registro mostra "Nenhum resultado encontrado", nunca R$ 0,00.
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

Registrar uma decisão de governança (acrescenta ao histórico, nunca edita). Promover a operacional exige `--teste` e, se a regra compõe o indicador publicado (`--compoe-indicador`), `--evidencia` (id da evidência externa) ou `--ressalva`:

```bash
python -m rp decidir-regra --codigo RREO-COL --versao 2 --situacao operacional --status "FORTE EVIDÊNCIA" --compoe-indicador --motivo "..." --fonte "etapa04/RELATORIO_04_4.md secao 14" --teste "tests/test_x.py::test_y" --evidencia 3
```

Testes (nenhum acessa a internet; os da interface bloqueiam qualquer conexão para fora e sobem um servidor HTTP em 127.0.0.1; `test_casos_reais.py`, `test_interface_casos_reais.py` e `test_homologacao_real.py` montam um banco temporário a partir do armazém real `../snapshots`, só com leitura; `test_homologacao_real.py` recalcula os indicadores direto do JSON bruto da API):

```bash
python -m pytest tests
```

Os testes que usam dados reais (fixtures `real` e `producao`: armazém `../snapshots` e bruto das Etapas 01/02, com dados de credores) recebem sozinhos o marcador `dados_reais`. Só os sintéticos, num ambiente sem o bruto:

```bash
python -m pytest tests -m "not dados_reais"
```

Dependências: Python 3.11+ declarado (comprovado só em 3.14.3 no Windows; ver Instalação), `requests` e `pymupdf` (este só para transcrever o PDF do RREO), nas versões fixadas em `requirements.txt`: a transcrição do RREO depende das coordenadas de texto que o PyMuPDF devolve. Para os testes, `pytest` (`requirements-dev.txt`). A interface e a camada painel não importam nenhum pacote de terceiros.
