# Privacidade do repositório público: inventário e plano

Pedido de correção de 09/10/2026, item 8. **Nada foi removido do histórico nem enviado ao GitHub.** Este documento
registra o que está publicado hoje e propõe um plano em etapas. As etapas que mudam o que o GitHub serve (parar de
publicar, reescrever o histórico, mudar a visibilidade) dependem de autorização explícita do responsável. Até lá,
**a privacidade não está resolvida**: adicionar arquivos ao `.gitignore` não retira o que já está no histórico.

## 1. Situação verificada em 09/10/2026

| Item | Fato |
|---|---|
| Repositório | `MathFalaise/Dashboard-Restos-a-Pagar-Ponta-Grossa`, **público**, 0 forks, 0 estrelas, 77 commits, tags `etapa-04-final` e `etapa-05-final` |
| Pacote Git | 38,8 MiB |
| `.gitignore` | já ignora `data/snapshots/` e `data/backups/*.sqlite`, mas os arquivos versionados **antes** da regra continuam rastreados |

### Dados pessoais versionados (árvore atual)

| Caminho | Arquivos | Conteúdo pessoal |
|---|---|---|
| `data/snapshots/` | 841 (466 manifestos + 375 objetos zlib) | respostas brutas da API: nome do credor e CPF de pessoa física **mascarado pela própria API** (`****NNN****`). No banco: 996 documentos mascarados distintos e 5.715 nomes distintos em registros de pessoa física |
| `data/stage02-raw/` | 239 | bruto da Etapa 02 (mesma natureza) |
| `data/stage01-samples/` | 23 | amostras da Etapa 01; um CSV com 1.025 ocorrências de CPF mascarado |
| `data/backups/` | 4 SQLite (0,7 a 4,6 MB) | cópias do banco com credores (577 ocorrências de CPF mascarado em cada um dos dois maiores) |

### Histórico

Os mesmos conteúdos existem em caminhos antigos, anteriores à reorganização de 06/10/2026: `snapshots/coletas`,
`snapshots/objetos`, `etapa01/amostras_brutas`, `etapa02/dados_brutos` e `backups/`.

### Fora de `data/`

- Nenhum dos 5.715 nomes de pessoa física aparece em código, testes ou documentação versionados (busca exata em
  todos os arquivos de texto de `app/`, `docs/` e `README.md`).
- Os testes usam nomes inventados ("FULANA DE TAL").
- Dois relatórios citavam um fragmento real de CPF mascarado. Foi trocado por um exemplo sintético num commit
  normal (não reescreve o histórico).

### Informação desnecessária fora de `data/` (revisão da fase F)

- **Nome de usuário local:** o caminho local da máquina de trabalho, com o nome de usuário do Windows, aparece em 24
  arquivos de documentação e de evidência da etapa 04, por exemplo `PLAN.md`, `REPORT_04_1.md` e o campo `backup` de
  `batches/LOTE_*.json`.
- **Natureza:** não é dado de credor.
- **Por que não foi editado:** são registros de evidência de etapas homologadas. Pode ser trocado num commit normal
  (só para o futuro) ou também no histórico, com `git filter-repo --replace-text` junto da Etapa 3. A decisão é do
  responsável.
- **Arquivos criados por esta correção:** não contêm caminho local (as saídas de `docs/audits/rreo/` gravam só o nome
  do arquivo do banco).

### Natureza

São dados que o próprio Portal da Transparência publica. Mesmo assim, o repositório não precisa deles para os
testes sintéticos. O painel, no nível público, já omite a identificação de pessoa física (`rp/painel/publico.py`).

## 2. O que já funciona sem o bruto no repositório

- 169 testes usam dados reais e são marcados `dados_reais` pelo `conftest`. Os outros 470 são sintéticos (contagem
  de 09/10/2026).
- Prova executada: o código desta branch, exportado **sem a pasta `data/`**, roda `pytest -m "not dados_reais"`. O
  resultado está na seção 5.
- O CI (`.github/workflows/testes.yml`) só roda os passos com dados reais se `data/snapshots` e `data/stage02-raw`
  existirem. Sem eles, os passos são pulados, não falham.
- `config.toml` (`[caminhos]`), `RP_CONFIG` e `RP_DADOS_LOCAIS` apontam o armazém e os backups para qualquer pasta
  privada. O banco ativo já fica fora do repositório (`~/RestosAPagar_local`).

## 3. Plano proposto (nada executado)

### Etapa 1: armazenamento privado do bruto integral (reversível)
1. Copiar `data/snapshots`, `data/stage01-samples`, `data/stage02-raw` e `data/backups` para um local privado: um
   repositório privado separado, ou um disco com cópia externa.
2. Conferir a cópia: `python -m rp verificar`, `python -m rp raiz --gravar` e as listas `*.SHA256.txt`. Guardar a
   raiz fora dos dois locais.
3. Apontar `[caminhos].snapshots` e `backups` do `config.toml` local para a cópia privada e rodar
   `python -m rp homologar` contra ela.

### Etapa 2: parar de publicar, sem reescrever o histórico (exige autorização; é um push)
```bash
git rm -r --cached data/snapshots data/stage01-samples data/stage02-raw data/backups
```
- Acrescentar `data/stage01-samples/` e `data/stage02-raw/` ao `.gitignore`.
- Commit, PR e merge.
- **Consequência:** novas versões deixam de conter o bruto, mas **tudo continua acessível no histórico público**.
  O CI passa a rodar só os testes sintéticos; os testes com dados reais ficam no ambiente privado.

### Etapa 3: retirar do histórico público (irreversível para quem já clonou; exige autorização explícita)
Feito num clone espelho novo, nunca na pasta de trabalho:
```bash
git clone --mirror https://github.com/MathFalaise/Dashboard-Restos-a-Pagar-Ponta-Grossa.git rp-espelho.git
```
```bash
git -C rp-espelho.git filter-repo --invert-paths --path data/snapshots --path data/stage01-samples --path data/stage02-raw --path data/backups --path snapshots --path etapa01/amostras_brutas --path etapa02/dados_brutos --path backups
```
Depois, conferência (nenhum blob do bruto restante) e `git push --mirror --force`.

Consequências, que precisam ser aceitas antes:
- **Commits e PRs:** todos os 77 SHAs de commit mudam. Links para commits em PRs, issues e documentos quebram.
- **Tags:** `etapa-04-final` e `etapa-05-final` passam a apontar para commits novos. Isso conflita com a regra do
  projeto de não mover tags e exige autorização específica para essas duas.
- **Cache do GitHub:** as referências `refs/pull/1..19/head` mantêm os commits antigos no servidor. O GitHub continua
  servindo esses objetos até que o GitHub Support os remova (pedido de remoção de dados sensíveis, com a lista de
  PRs).
- **Clones:** clones existentes não podem fazer pull nem merge; precisam ser recriados. Forks hoje: 0.
- **Cópias externas:** cópias já baixadas por terceiros não são alcançadas por nenhuma medida.

### Etapa 4: conferir o resultado
- Pela API do GitHub, os blobs antigos (por SHA) não devem ser mais servidos.
- Um clone novo não deve ter nenhum caminho de bruto no `git log --all --name-only`.

### Alternativa mais simples
Tornar o repositório privado. Isso muda a visibilidade (só com autorização) e resolve o acesso futuro, mas não
alcança cópias já feitas. **Não recomendado:** pseudonimizar o bruto versionado, porque alteraria dados brutos
homologados.

## 4. Pendências

- **Decisão do responsável:** etapas 2, 3 e 4 (ou a alternativa) e autorização específica para recriar as duas tags.
- **Local privado da Etapa 1:** a escolha é do responsável.
- **Até a decisão:** o histórico público continua com os dados descritos na seção 1.

## 5. Prova: testes sem o bruto

O código do commit `b547bb6` foi exportado com `git archive HEAD`, sem a pasta `data/`, e testado sem nenhum dado
real:
```bash
python -m pytest tests -q -p no:cacheprovider -m "not dados_reais"
```
Resultado: `469 passed, 1 skipped, 169 deselected in 132.76s`. O teste pulado (`test_decisoes_revisao.py:96`, "sem
git/repositorio") precisa da pasta `.git`, que a exportação não tem; não depende de dados.
