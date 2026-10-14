# Armazenamento privado do bruto, do banco e das cópias

Auditoria corretiva de 13/10/2026, fases P0 e P2. O bruto da API, o bruto das Etapas 01/02 e as cópias do banco têm
registros de credores (nomes e CPF mascarado). Por isso:
- ficam **só** no armazenamento privado local, fora do repositório público e fora do OneDrive;
- a cópia fora do computador é **cifrada**.

## 1. Onde fica cada coisa

| Conteúdo | Caminho (`app/config.toml`, `[caminhos]`) | Sincronizado? |
|---|---|---|
| Banco ativo (SQLite) | `~/RestosAPagar_local/banco/restos_a_pagar.sqlite` (`dados_locais`) | não |
| Armazém do bruto (manifestos, objetos, evidências) | `~/RestosAPagar_local/armazem` (`snapshots`) | não |
| Bruto das Etapas 01/02 | `~/RestosAPagar_local/etapas_anteriores` (`etapas_anteriores`) | não |
| Backups estruturais (antes de migração, carga, promoção) | `~/RestosAPagar_local/backups` (`backups`) | não |
| Backups operacionais (antes de apagar uma execução) | `~/RestosAPagar_local/backups_operacionais` | não |
| Referências de integridade (raiz, referência, homologações) | `~/RestosAPagar_local/referencias` | não |
| Evidências de trabalho das sessões (releituras da API, PDFs, Siconfi) | `~/RestosAPagar_local/evidencias_sessoes` | não |
| Cópia cifrada independente | `OneDrive/RestosAPagar_copia_cifrada/` (fora do repositório) | sim, **cifrada** |
| Frase-senha da cópia cifrada | `~/RestosAPagar_local/segredos/chave_copia_cifrada.txt` | não |

**Recusa automática:**
- `banco.abrir` recusa abrir o banco ativo quando o armazém, os backups, o bruto das etapas ou os backups
  operacionais estão numa pasta sincronizada ou de rede.
- `banco.backup` recusa gravar uma cópia nessas pastas.
- O teste `tests/test_privacidade_repositorio.py` falha se o `config.toml` voltar a apontar o bruto para dentro do
  repositório.

## 2. A migração de 13/10/2026

1. **Ponto de restauração do banco ativo:**
   - cópia pela API de backup do SQLite;
   - `integrity_check` ok, `foreign_key_check` vazio;
   - SHA-256 `9c1935cd…b1e3`.
2. **Cópia conferida** (`rp.privado.copiar_conferido`):
   - nunca sobrescreve e confere o SHA-256 de cada arquivo copiado;
   - armazém: 9.445 arquivos;
   - bruto das Etapas 01/02: 23 + 239 arquivos;
   - backups: 11 bancos, 3,06 GB;
   - nenhum conflito.
3. **Cobertura do histórico público:** os 1.094 blobs brutos de todas as refs do GitHub, inclusive as `refs/pull/*`,
   foram procurados na cópia privada pelo hash de blob do Git. 1.092 existem byte a byte. Os 2 restantes são as
   listas `*.SHA256.txt` em versões antigas, que não têm dado pessoal e continuam públicas.
4. **Prova de que o armazém privado basta:** `python -m rp homologar` contra o armazém privado.
   - **Reprodução determinística:** banco novo construído só do armazém, normalizado e derivado, igual ao ativo camada
     a camada. Hashes `7e7983f9…` (atual) e `4002ccc2…` (29/09), os mesmos do banco ativo.
   - **Raiz externa** de 10/10/2026: confere.
   - **Suíte de investigação:** 26 passed.
   - **Suíte de produção:** 3 falhas que vinham do ambiente da execução, não do armazém. O texto do `config.toml`
     antigo era substituído pelos testes, e a variável `PYTHONIOENCODING` estava definida. As três passam depois da
     correção (seção 5).
5. **Cópia cifrada independente:**
   - **O que contém:** `armazem/`, `etapas_anteriores/` e `referencias/`, 9.720 arquivos, num `tar` cifrado com
     GnuPG simétrico AES-256: `rp_privado_20261013.tar.gpg`, 70,7 MB, SHA-256 `8b69fc71…107b`.
   - **Teste de restauração:** decifrar, extrair e comparar os 9.720 SHA-256 com a lista
     `rp_privado_20261013.SHA256.json`. Resultado: 0 divergentes, 0 extras.
   - **Onde fica:** a cópia foi para `OneDrive/RestosAPagar_copia_cifrada/`, fora do repositório. Lá o OneDrive a
     leva para fora do computador sem expor o conteúdo.

## 3. Restaurar

```bash
gpg -d rp_privado_20261013.tar.gpg | tar -xf - -C ~/RestosAPagar_local
```
```bash
python -m rp verificar
```
```bash
python -m rp reconstruir --destino ~/RestosAPagar_local/banco/reconstruido.sqlite
```
O banco se reconstrói só do armazém (`reconstruir` + `processar`). `homologar` prova que o resultado é igual ao
banco que estava em uso.

## 4. Política de backups e retenção

| Tipo | Quando | Retenção |
|---|---|---|
| Estrutural (`backups/`) | antes de migração, carga, importação, promoção, manutenção | nunca apagado automaticamente; os antigos são comprimidos (gzip conferido byte a byte) |
| Operacional (`backups_operacionais/`) | antes de apagar uma execução | os 3 mais recentes sem compressão; os outros, gzip conferido; `PRESERVAR.txt` protege da retenção |
| Cópia cifrada | depois de cada carga homologada | um arquivo por data, nunca sobrescrito |
| Execuções no banco ativo | `python -m rp manutencao` (seção 4.1) | a normalização atual e a derivação mais recente de cada vigência; as demais saem depois de backup conferido |

**Regra geral:** nenhum backup antigo é apagado antes de existir um substituto conferido. Comprimir não é apagar.

### 4.1 Manutenção do banco ativo
`python -m rp manutencao` mostra a prévia. Com `--confirmar`, faz nesta ordem:
1. backup estrutural, conferido por `integrity_check`, pela contagem de linhas de cada tabela e pelo SHA-256;
2. exclusão das execuções fora da retenção, uma a uma, pelo mesmo código de `apagar-execucao`;
3. `integrity_check`, `foreign_key_check` e `verificar`;
4. `VACUUM`.

A manutenção é recusada quando o backup não confere, quando a camada bruta muda ou quando alguma verificação falha.

## 5. Pendências que dependem do responsável

- **Frase-senha da cópia cifrada:** guardar fora deste computador, por exemplo num gerenciador de senhas. Sem ela, a
  cópia cifrada não restaura. Ela está só em `~/RestosAPagar_local/segredos/`.
- **Testes com dados reais:** rodam só neste ambiente privado. No CI público rodam só os testes sintéticos.
