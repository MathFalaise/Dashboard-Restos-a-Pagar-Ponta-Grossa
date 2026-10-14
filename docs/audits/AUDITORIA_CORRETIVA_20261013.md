# Auditoria corretiva integral: banco de dados, Restos a Pagar e confiabilidade contábil

Executada em 13 e 14/10/2026, no ramo `auditoria-corretiva-20261013`, criado a partir do PR #21
(`cons-par-carga-2026`, `9e11d1c`). O PR #21 não foi mesclado. Este relatório separa o que foi **feito e
comprovado** do que foi **preparado** e do que **depende de ação externa**.

## 1. Estado inicial e final

| Item | Inicial (13/10, 22:08) | Final (14/10) |
|---|---|---|
| Git | `main` `8166c5b`; PR #21 aberto (`9e11d1c`); ramos locais sem push `promocao-regras-rreo` e `rreo-cobertura-siconfi`; 1.107 arquivos brutos versionados | ramo `auditoria-corretiva-20261013` com 12 commits locais; nenhum bruto versionado; nada enviado ao GitHub |
| Histórico público | 89 commits; 1.094 blobs brutos; 146 + 51 + 10 + 2 blobs com dado pessoal | inalterado até a autorização; espelho higienizado validado (seção 3) |
| Banco ativo | `~/RestosAPagar_local/banco`, 1.435.840.512 bytes, esquema v8; normalização 17, derivações 35/36 (`7e7983f9`/`4002ccc2`) | 346.234.880 bytes; normalização 18 (`rp-normalizador/3`), derivações 37/38 (`bcd01a41`/`4002ccc2`) |
| Armazém do bruto | `data/snapshots` dentro do OneDrive | `~/RestosAPagar_local/armazem`, fora do OneDrive; cópia cifrada fora do computador |
| Backups | 2,9 GB em `data/backups`, no OneDrive | `~/RestosAPagar_local/backups`, 4,1 GB comprimidos e conferidos; cópias do OneDrive em quarentena local |

**Ponto de restauração inicial:** `ponto_restauracao_20261013.sqlite`, SHA-256 `9c1935cd…b1e3`, `integrity_check`
ok. Fica na pasta privada da auditoria.

## 2. Problemas, causa, correção e onde está

| # | Problema | Causa comprovada | Correção | Commit / arquivo |
|---|---|---|---|---|
| 1 | Dados de credores publicados | O bruto e as cópias SQLite foram versionados até 06/10; o `.gitignore` não retira o que já está no Git | Armazenamento privado conferido; 1.107 arquivos fora do índice; guarda de testes; CI só sintético; histórico higienizado preparado | `bcc4fcb`; `docs/audits/privacidade/` |
| 2 | Bruto, banco e backups no OneDrive | A configuração apontava o armazém e os backups para `data/` | `config.toml` aponta para o armazenamento privado; o programa recusa pastas sincronizadas; cópias movidas para fora do OneDrive depois de conferidas | `bcc4fcb`, `2c7cdf9`; `ARMAZENAMENTO_PRIVADO.md` |
| 3 | "Município" misturava escopos | A fonte Elotech cobre o Executivo; o consolidado oficial tem também o Legislativo | O painel passa a se rotular "Poder Executivo, fonte Elotech"; série oficial do Siconfi separada, comparada só com a linha do Executivo; a Câmara (R$ 696,91 em 2025, único RP do Legislativo em 64 declarações) aparece como declarada, nunca somada | `2cc264f` (`rp/siconfi.py`, página `/oficial`) |
| 4 | Entidade 7 com regra universal até 2020 | Os demonstrativos oficiais tratam a ARAS de forma diferente em cada bimestre | ESCOPO-MUN v2: escopo por bimestre, provado ao centavo (a+b+f+g) com método fixado antes de olhar os totais; ressalva onde não há prova ou há contradição | `bdbaf44`, `626ab50`, decisão 40; `docs/audits/escopo/` |
| 5 | Pares 1↔15 não consolidados ficavam em silêncio | O painel só avisava a consolidação feita | CONS-PAR v4 inalterada; ressalva explícita para par contado nos dois lados e para consolidação com campo de conferência nulo; 8 cenários testados | `626ab50` |
| 6 | "Como estava em" usava as regras de hoje sem dizer | Não havia governança datada | Duas modalidades: metodologia atual ou vigente na data (decisões até a data; recusada antes da primeira); todo retrato mostra a metodologia | `626ab50` |
| 7 | VALOR-OBRIG v1 sem decisão; CONS-PAR v2 experimental indefinidamente | Promoções nunca registradas | Decisões 39 (VALOR-OBRIG v1 operacional), 41 (ESCOPO-MUN v1 supersedida pela v2), 42 (CONS-PAR v2 supersedida pela v4); `--supersedida-por` registra a sucessora | `6b0b740` |
| 8 | Sem visão de alterações retrospectivas | Só existia a comparação de dois retratos escolhidos | `rp atualizacao`: atualidade e alterações por corte e por empenho, com alerta retrospectivo e as datas separadas | `6b0b740` |
| 9 | Sem matriz SICONFI × RREO × Elotech × painel | — | Matriz célula a célula com classes verificáveis e resíduos | `cbe6956`, atualizada em `2c7cdf9` |
| 10 | 18 RREOs recusados pelo extrator | Layout de 2016 e impressões do Siconfi (2018–2020) | Regras de layout versionadas (`rp-normalizador/3`); 16 lidos, validados célula a célula pela segunda leitura; prova de que só acrescentam | `a359202` |
| 11 | "99,9%" sem medição | Nenhuma métrica por dimensão | Relatório de qualidade em 7 dimensões, nunca somadas | `2c7cdf9` |
| 12 | Banco crescendo sem limite | Toda carga guardava normalizações e derivações completas | `rp manutencao` com política reproduzível; backups estruturais comprimidos | `2c7cdf9` |
| 13 | Homologação misturava dimensões | — | Bloco `dimensoes` (técnica, cobertura, pendências); "sem ressalvas" exige cobertura completa | `2c7cdf9` |
| 14 | Perguntas ao Município espalhadas | — | Minuta e-SIC v4 (blocos A–F) e procedimento de registro da resposta | `2c7cdf9`; `docs/foi-requests/` |

### Mudanças de valor publicado (com regra nova, evidência e decisão)

**ESCOPO-MUN v2** muda 14 cortes do Município: 2018 (2º–6º bim), 2019 (1º–4º bim) e 2020 (2º–6º bim). Cada um cai
R$ 180.334,82 na inscrição e no saldo. Nesses cortes o saldo publicado passa a ser igual, ao centavo, à linha do
Poder Executivo da declaração ao Siconfi. Detalhe em `docs/audits/governanca/IMPACTO_DECISOES_20261013.md`, com os
retratos antes e depois dos 68 cortes.

**Nenhuma outra mudança altera valor publicado:**
- **Normalizador v3:** só acrescenta transcrições de RREO, comprovado.
- **Avisos e ressalvas:** não mudam números.

## 3. Privacidade: higienização e referências públicas

- **Feito:** armazenamento privado conferido; publicação de novo bruto interrompida (guarda + `.gitignore`).
- **Preparado e validado, não publicado:** reescrita do histórico (`docs/audits/privacidade/HIGIENIZACAO_HISTORICO.md`).
  - **Varredura:** 0 de 1.021 blobs com dado pessoal.
  - **Árvores:** idênticas às originais, sem as pastas brutas.
  - **Testes no checkout higienizado:** 522 sintéticos passaram.
  - **Reprodutibilidade:** reescrita determinística, com mapa de refs.
- **Pendente:**
  - envio forçado, que **exige autorização explícita**;
  - pedido ao suporte do GitHub para as `refs/pull/1..20` e caches (texto pronto);
  - novo clone da pasta de trabalho, cujo `.git` no OneDrive ainda tem os blobs antigos.

**A higienização não está concluída e não é declarada concluída.**

## 4. Reconstrução independente do banco

| Prova | Resultado |
|---|---|
| `homologar` contra o armazém privado (13/10) | reprodução camada a camada igual ao ativo; hashes `7e7983f9`/`4002ccc2`; raiz de 10/10 conferida |
| Normalizador v3: só acréscimo (`prova_acrescimo_layouts.py`) | +504 valores de RREO de 16 PDFs; resto idêntico; derivação 37 reconstruída sem eles = `7e7983f9`; 38 = `4002ccc2` |
| Âncoras homologadas na base de 30/09 | todas reproduzidas (`2f6b4e29`/`b8a0b2ed`, `adc55b19`/`96777ec6`, `15e91995`/`4002ccc2`); novo resultado completo `4e0a066f` |
| Homologação final (14/10) | reprodução camada a camada igual ao ativo (`bcd01a41`/`4002ccc2`); raiz de 14/10 conferida |

## 5. Concordância SICONFI × RREO × Elotech (resumo)

Detalhe por exercício, período, coluna e classe em `docs/audits/rreo/MATRIZ_CONCORDANCIA.md`. Os resíduos são somas
de valores absolutos de células sem causa provada. Colunas se sobrepõem (L contém e e k), então o resíduo não é um
valor monetário único.

| Comparação | Células | Concordam | Explicadas por evidência | Sem causa |
|---|---:|---:|---:|---:|
| PDF do portal × Siconfi (Executivo) | 696 | 229 | 188 | 279 |
| Elotech (RREO-COL v3) × PDF | 1.356 | 773 | 364 | 219 |
| Elotech (escopo publicado) × Siconfi | 768 | 269 | 276 | 223 |
| Painel publicado × Siconfi, por grupo | 320 | 161 | 42 | 117 |

**O que a matriz mostra:**
- **Documentos oficiais em contradição:** o PDF do portal e a declaração ao Siconfi se contradizem em 279 células
  sem causa provada; o resto tem causa provada ou é troca de soma zero.
- **Contradições com causa comprovada:**
  - 2020, 2º–6º bimestres: a entidade 7;
  - 2026: os pares somados no PDF;
  - 2019: impressões com uma linha de Legislativo que a declaração atual não tem.
- **Onde a fonte Elotech e o painel reproduzem o Siconfi ao centavo:** 2021, 2024 e 2025. Em 2026 a inscrição
  bate ao centavo; nos pagamentos restam alterações retrospectivas.
- **Resíduos grandes:** concentram-se em 2016–2019. Nesses anos as declarações divergem da fonte Elotech sem causa
  determinada (ex.: 2018, 1º bimestre: Siconfi R$ 63,2 milhões × Elotech R$ 43,1 milhões). Estão no e-SIC, bloco D.

## 6. Cobertura documental

| Exercício | Esperados | Transcritos | Recusados | Não coletados |
|---|---:|---:|---:|---:|
| 2016–2026 | 114 | 112 | 2 | 0 |

- **Conferência independente:** 112 de 112 iguais à segunda leitura (xpdf), 0 divergentes.
- **Recusados:**
  - 2019, 1º bimestre (`b218b702`): período ilegível, e a segunda leitura também não lê as linhas;
  - 2020, 3º bimestre consolidado (`c39d70b9`): linha com 11 números.
- **Consequência:** esses dois documentos não entram em nenhuma conferência.
- **Siconfi:** 64 períodos declarados (2016 a 2026, 4º bimestre); 2026, 5º e 6º, ainda sem declaração.
- **Detalhe:** `docs/audits/rreo/COBERTURA_E_CONFERENCIA.md` e `VALIDACAO_LAYOUTS.md`.

## 7. Regras e governança (situação atual)

| Regra | Situação | Compõe o indicador | Observação |
|---|---|---|---|
| CAT, FAIXA, S1, S2, S3 v1 | operacional | sim | — |
| CANC v2, RREO-COL v3, MOV-REF v2, COPIA-ORIGEM v1, CONS-PAR v4 | operacional | sim | com ressalva registrada |
| ESCOPO-MUN v2 | operacional (decisão 40, evidência externa 2) | sim | ressalva: períodos sem prova e contraditórios; ARAS no e-SIC |
| VALOR-OBRIG v1 | operacional (decisão 39) | não (conformidade) | 0 valores recusados |
| PAR-24, CONC-RREO, ANOM-REG, ANOM-CONT v1 | operacional | não | — |
| ESCOPO-MUN v1 | supersedida pela v2 (decisão 41) | não | segue na derivação: escopo dos PDFs do portal |
| CONS-PAR v1 e v2, RREO-COL v2, MOV-REF v1 | supersedidas | não | v2 → v4 (decisão 42) |
| CANC v1, RREO-COL v1 | não recomendadas | não | — |

Nenhuma regra ficou sem decisão.

## 8. Testes

| Execução | Resultado |
|---|---|
| Suíte de produção no commit P0 (`bcc4fcb`, dados reais do armazém privado) | 661 passed |
| Suíte de investigação no commit P0 | 26 passed |
| Suíte de produção no commit dos layouts (`a359202`) | 688 passed |
| Suíte de investigação no commit dos layouts | 26 passed |
| Testes sintéticos no checkout higienizado (sem nenhum dado) | 522 passed |
| Suítes completas no checkout higienizado final (dados reais do armazém privado) | produção 691 passed; investigação 26 passed |
| Homologação final (`homologacao_final_auditoria_20261014.json`, banco ativo depois da manutenção) | `aprovada_com_ressalvas`: 20 de 20 verificações ok; produção 691 passed; investigação 26 passed; dimensões: técnica aprovada, cobertura 112/114, 3 pendências contábeis (divergência com o RREO, 2 RREOs ilegíveis, natureza dos pares) |

**Testes novos:** privacidade do repositório (7), escopo da entidade 7, os 8 cenários dos pares, metodologia na data,
série oficial, Siconfi (ausente ≠ zero), alterações retrospectivas, sucessora de regra, retenção (2), dimensões da
homologação, regras de layout (6).

**Testes antigos ajustados** (o valor anterior fica no comentário), sem nenhum apagado:
- D2: nada mais é versionado;
- 10/10: o par não consolidado não é mais silencioso;
- âncoras da base homologada.

**Não executados no CI público:** os testes com dados reais (169 + 26), porque dependem do armazém privado. Rodam
na homologação local.

## 9. Espaço e retenção

| Item | Antes | Depois |
|---|---:|---:|
| Banco ativo | 1.737.969.664 B (1.435.840.512 no início da auditoria) | 346.234.880 B |
| Backups estruturais privados | 7,7 GB (cópias) | 4,1 GB (12 comprimidos com conferência, 2 recentes inteiros) |
| Pasta do repositório no OneDrive | 3,06 GB de backups + 158 MB de bruto | 0 (movidos para a quarentena local) |
| Pacote do Git | 38,8 MiB | 2,3 MiB depois da higienização (pendente de envio) |

A política está em `docs/audits/privacidade/ARMAZENAMENTO_PRIVADO.md`, seção 4.

## 10. Pendências externas

| Pendência | Impacto | Evidência | O que falta |
|---|---|---|---|
| Envio forçado do histórico higienizado | dados de credores continuam no histórico público | `HIGIENIZACAO_HISTORICO.md` | autorização explícita do responsável; depois, os comandos da seção 5 desse documento |
| Pedido ao suporte do GitHub | `refs/pull/1..20` e caches mantêm os objetos antigos | idem, seção 6 | enviar o formulário com o texto pronto |
| Novo clone da pasta de trabalho | o `.git` no OneDrive tem os blobs antigos | idem | recriar o clone depois do envio |
| Frase-senha da cópia cifrada | sem ela, a cópia fora do computador não restaura | `~/RestosAPagar_local/segredos/` | guardar num gerenciador de senhas |
| e-SIC (não enviado) | pares: R$ 31,8 milhões; entidade 7: R$ 180.334,82; 2026 retroativo; versões do Siconfi | `docs/foi-requests/ESIC_MINUTA_V4_20261013.md` | envio pelo solicitante (exige CPF); registrar a resposta pelo procedimento |
| 2 RREOs ilegíveis | sem conferência desses dois documentos | seção 6 | cópia legível do Município, ou conferência manual documentada |
| Revisão e mesclagem | — | PR a abrir depois do envio do histórico | revisão do responsável |

**Nenhuma resposta do Município foi presumida.** Nenhuma meta de 99,9% foi declarada fora das dimensões em que a
medição a confirma:
- fidelidade da ingestão: 100%;
- reprodutibilidade: 100%;
- conferência independente das transcrições: 100%;
- proveniência: 100%.

Ficaram abaixo da meta:
- cobertura documental: 98,2%;
- concordância entre documentos: 32,9% a 57,0%, porque os documentos oficiais se contradizem.
