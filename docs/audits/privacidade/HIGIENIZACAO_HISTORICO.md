# Higienização do histórico público

Auditoria corretiva de 13/10/2026, fase P0.

**Situação: preparada e validada, NÃO publicada.** Ainda não houve envio forçado ao GitHub. O histórico público
continua, até lá, com os dados descritos na seção 1. A publicação depende de autorização explícita do responsável
(seção 5).

## 1. Inventário do histórico público

**Fonte:** um clone espelho do GitHub (`git clone --mirror`), com todas as refs: ramos, tags e as `refs/pull/*`
que o GitHub mantém. Foram examinados 89 commits, 2.006 blobs e 3.352 pares (blob, caminho).

**Como se procurou dado pessoal:** cada blob foi lido; objetos zlib e SQLite foram descomprimidos ou abertos. Em
cada blob foram procurados:
- os 5.712 nomes de pessoa física do banco;
- CPF mascarado (`****NNN****`);
- CPF completo.

| Caminho no histórico (antigo e atual) | Blobs | Com dado pessoal | Com nome de pessoa física | Natureza |
|---|---:|---:|---:|---|
| `snapshots/objetos` = `data/snapshots/objetos` | 375 | 146 | 38 | respostas brutas da API (zlib) |
| `snapshots/coletas` = `data/snapshots/coletas` | 466 | 0 | 0 | manifestos (URL, hash, horários) |
| `etapa02/dados_brutos` = `data/stage02-raw` | 226 | 51 | 20 | bruto da Etapa 02 |
| `etapa01/amostras_brutas` = `data/stage01-samples` | 23 | 10 | 0 | amostras da Etapa 01 |
| `backups` = `data/backups` | 3 | 2 | 2 | cópias SQLite do banco |
| demais caminhos (código, documentação, testes, resultados agregados) | 1.004 | 0 | 0 | — |

**Fora das pastas brutas**, a varredura achou só:
- valores sintéticos dos testes (`****123****`, `***456***`, `123.456.789-01`, com dígito verificador inválido);
- um fragmento real de CPF mascarado (3 dígitos), citado em versões antigas de 4 relatórios. As versões atuais já
  usam um exemplo sintético.

## 2. Preservação antes de qualquer remoção

- **Cópia conferida:** o bruto integral, os manifestos, as amostras e os backups foram para o armazenamento privado
  (`ARMAZENAMENTO_PRIVADO.md`), conferidos por SHA-256.
- **Cobertura do histórico:** dos blobs brutos do histórico, 1.092 de 1.094 existem byte a byte na cópia privada.
  Os 2 restantes são as listas `*.SHA256.txt` em versões antigas, que são públicas e continuam.
- **Reprodução:** `python -m rp homologar` contra o armazém privado reproduziu o banco ativo camada a camada.
- **Cópia cifrada independente:** AES-256, restaurada e conferida, fora deste computador.

## 3. Parar a publicação (feito, commit `bcc4fcb`)

- **Índice do Git:** 1.107 arquivos brutos saíram (`git rm --cached`).
- **`.gitignore`:** cobre todas as pastas brutas, antigas e novas, e qualquer arquivo `.sqlite`, `.zlib` ou de
  backup.
- **Guarda:** `app/tests/test_privacidade_repositorio.py` falha se um bruto, um banco ou um CPF real voltar a ser
  versionado.
- **CI:** roda só os testes sintéticos.
- **Pastas brutas no OneDrive:** foram movidas para fora dele (quarentena local), depois de conferidas byte a byte.

## 4. A reescrita, ensaiada e validada

**Script:** `higienizar_historico.sh`. Trabalha num clone espelho isolado, fora do OneDrive e fora da pasta de
trabalho, com `git-filter-repo` 2.47.0:
- remove do histórico as pastas `data/snapshots`, `data/stage01-samples`, `data/stage02-raw`, `data/backups`,
  `snapshots`, `etapa01/amostras_brutas`, `etapa02/dados_brutos` e `backups`;
- troca o fragmento real de CPF por `****NNN****`.

**Resultado do ensaio de 14/10/2026** (refs do GitHub + o ramo `auditoria-corretiva-20261013`):

| Verificação | Resultado |
|---|---|
| Caminho bruto em algum commit de alguma ref | nenhum |
| Blobs com nome de pessoa física, CPF mascarado real, zlib ou SQLite | **0 de 1.021** |
| Tamanho do pacote | 38,78 MiB → 2,32 MiB |
| Árvore de `main`, `cons-par-carga-2026`, `contrato-e-ausencias` e do ramo da auditoria | idêntica, blob a blob, à original sem as pastas brutas |
| Testes sintéticos no checkout higienizado (sem nenhum dado) | 522 passed |
| Reescrita determinística | os SHAs novos repetem os do primeiro ensaio (13/10) |
| Execução final (14/10, ponta do ramo da auditoria) | 99 commits, 1.029 blobs, nenhum com dado pessoal; árvore idêntica; suítes completas no checkout higienizado: 691 + 26 passed |

### Mapa das refs (antes → depois)

Os commits mudam de SHA. O conteúdo é o mesmo, sem as pastas brutas.

| Ref | Antes | Depois |
|---|---|---|
| `refs/heads/cons-par-carga-2026` | `9e11d1c3803b` | `f9b3b518c200` |
| `refs/heads/contrato-e-ausencias` | `da5e25f4d998` | `63c5bb16199f` |
| `refs/heads/main` | `8166c5b1cf2a` | `24b993afe708` |
| `refs/tags/etapa-04-final` | `ed6f35bf45e8` | `ecb28430c0e1` |
| `refs/tags/etapa-05-final` | `892940f83efe` | `5a571d9baa89` |
| `refs/pull/1..21/head`, `refs/pull/21/merge` | 22 refs | reescritas no espelho, mas o GitHub **não aceita** envio para elas (seção 6) |

**Tags:** os nomes ficam e passam a apontar para o commit equivalente reescrito:
- `etapa-04-final` (commit `a6bd27c1` → `b9039803`);
- `etapa-05-final` (`b38e8841` → `2972be50`).

O mapa completo de commits fica em `mapa_de_commits.txt`, na pasta privada da reescrita.

## 5. Publicar (depende de autorização explícita)

Na hora do envio, rodar de novo o script sobre a ponta final (pasta nova) e conferir que a árvore e os SHAs das refs do GitHub são os da seção 4.

A partir do espelho higienizado, só ramos e tags, nunca `--mirror`:
```bash
git -C ESPELHO push --force origin refs/heads/main:refs/heads/main refs/heads/cons-par-carga-2026:refs/heads/cons-par-carga-2026 refs/heads/contrato-e-ausencias:refs/heads/contrato-e-ausencias refs/heads/auditoria-corretiva-20261013:refs/heads/auditoria-corretiva-20261013
```
```bash
git -C ESPELHO push --force origin refs/tags/etapa-04-final refs/tags/etapa-05-final
```

**Consequências que precisam ser aceitas antes:**
- **SHAs:** todos os commits mudam. Links para commits antigos em PRs e documentos deixam de resolver pelo SHA
  novo. Os PRs fechados continuam com o histórico antigo (seção 6).
- **PR #21:** aberto, passa a mostrar os commits reescritos, porque o ramo é atualizado.
- **Clones existentes:** precisam ser recriados, inclusive a pasta de trabalho local. O `.git` dela, dentro do
  OneDrive, ainda guarda os blobs brutos, e só fica limpo depois do novo clone.
- **Forks:** hoje 0. Cópias já baixadas por terceiros não são alcançadas por nenhuma medida.

## 6. O que o envio forçado NÃO resolve

- **`refs/pull/1/head` a `refs/pull/20/head`:** PRs já fechados. O GitHub mantém essas refs e os objetos antigos
  continuam acessíveis por elas e pelo SHA. **Só o suporte do GitHub remove.**
- **Caches e visualizações por SHA:** continuam até a remoção pelo suporte.

Pedido ao suporte do GitHub (formulário "Remove sensitive data", depois do envio forçado):

> Repository: MathFalaise/Dashboard-Restos-a-Pagar-Ponta-Grossa (public). We rewrote the history with git-filter-repo
> to remove raw data files containing personal data of individuals (names and partially masked CPF numbers of
> creditors) under the paths data/snapshots, data/stage01-samples, data/stage02-raw, data/backups, snapshots,
> etapa01/amostras_brutas, etapa02/dados_brutos and backups. All branches and tags were force-pushed. Please remove the
> cached views and dereference the old commits kept by the pull request refs refs/pull/1/head to refs/pull/20/head
> (and refs/pull/21/merge), and run garbage collection, so that the old objects are no longer reachable. Old commit
> SHAs (examples): 8166c5b1cf2a380ca617f702fb351d345c8adc21 (main), 9e11d1c3803b21bebdf0c30dfea86f13a1f10dcd (PR 21),
> ed6f35bf45e8cff3cac172378038ec0c389fa6ea and 892940f83efe8332013725708d2a0451068b79e7 (tags).

## 7. Conferir depois do envio

1. Um clone novo do GitHub, sem `--mirror`, não pode ter nenhum caminho bruto em `git log --all --name-only`.
2. `git ls-remote origin`: ramos e tags com os SHAs novos da tabela da seção 4.
3. Os SHAs antigos de exemplo não podem ser servidos pela API do GitHub, por exemplo
   `gh api repos/MathFalaise/Dashboard-Restos-a-Pagar-Ponta-Grossa/commits/8166c5b1`. **Só depois da resposta do
   suporte** isso vale para os commits só alcançáveis pelas `refs/pull/*`.
4. A higienização só será declarada concluída quando o item 3 for confirmado. Até lá, cada ref residual fica listada
   como pendência.
