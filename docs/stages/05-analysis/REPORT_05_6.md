# Relatório da Subetapa 05.6 — qualidade dos dados e situação das diferenças

Data: 02/10/2026. Ramo `subetapa-05.6`, criado de `subetapa-05.5` (`017b2b2`), sobre a base homologada `etapa-04-final` (`a6bd27c`).

- **Contrato:** `docs/stages/05-analysis/ANALYTICAL_CONTRACT.md`, seção 6 (E-01 anomalias, E-02 verificações, E-03 situação das diferenças) e seção 4.1 (regime "derivação").
- **Plano:** `docs/stages/05-analysis/PLAN.md`, seção 05.6 e problema R5.

**Resumo:**
- **Tela `/qualidade` ("Qualidade dos dados"):** expõe, cada uma segundo a sua natureza, as anomalias e as verificações já gravadas pela derivação e a situação das diferenças com o RREO. Nenhuma regra nova; nada é recalculado. A camada painel só lê as tabelas `anomalia`, `anomalia_tipo`, `verificacao` e a reconciliação já exibida.
- **Anomalias** (`Painel.qualidade`, `Painel.anomalias`):
  - por tipo: código, descrição, status de evidência, regra, ocorrências, quantas estão nos snapshots vigentes, snapshots e exercícios;
  - a lista de ocorrências traz o detalhe gravado;
  - a ligação ao registro só existe com entidade, ano e número do empenho, e é exata só no snapshot vigente do corte;
  - ocorrência sem chave fica só na contagem por tipo.
- **Verificações:** de conjunto, nunca listadas como empenhos. A situação é interpretada pela **descrição literal e pela regra**, pelo catálogo do contrato (R5):
  - "sem falha" ou "com falhas";
  - "colunas com diferença: n de m";
  - "PDFs não lidos: n".

  Descrição fora do catálogo aparece com os números brutos e "significado não catalogado". Item com falha leva às anomalias da mesma regra **no seu escopo**.
- **Diferenças com o RREO:** as cinco situações (sem diferença, explicada, parcialmente explicada, hipótese, não determinada) aparecem separadas, por coluna × documento × regra de agregação (RREO-COL v1 e v2), e também na coerência entre publicações. "Sem diferença" nunca é contada como explicada. A diferença entre a contagem da verificação CONC-RREO (por snapshot do PDF) e a da reconciliação (por documento) é explicada na tela, e as contas conferem.
- **Testes:** **348/348** de produção (338 + 10 novos) e **26/26** da investigação. `verificar` sem problemas; `portoes` apto. Bruto, armazém, derivações e os 5.575 valores homologados da 04.6 idênticos. Responsividade verificada.

---

## 1. O que mudou

| Arquivo | Mudança |
|---|---|
| `app/rp/painel/consulta.py` | `qualidade`, `_verificacoes`, `_escopo_das_anomalias`, `_situacao_da_verificacao`, `_situacao_das_diferencas`, `anomalias` (paginada, com filtros de escopo).<br>Constantes `SITUACOES_DAS_DIFERENCAS`, `NAO_CATALOGADA` e `INTERPRETACOES_DE_VERIFICACAO` (o catálogo E-02 do contrato).<br>`coerencia_entre_publicacoes`: cada comparação ganha `mais_recente`, a marca que a tela de reconciliação já usava para escolher a linha exibida. A escolha saiu da interface para a camada painel, com a mesma regra e o mesmo resultado (12 linhas) |
| `app/rp/interface/paginas.py` | página `qualidade`; item "Qualidade dos dados" no menu; `_coerencia` passa a usar a marca `mais_recente` |
| `app/rp/interface/aplicacao.py` | rota `/qualidade` |
| `app/rp/interface/estilo.css` | larguras mínimas das colunas de texto das tabelas novas |
| `app/tests/test_qualidade_05_6.py` (novo) | 10 testes |
| `app/README.md` | linha da 05.6 e a tela nova |

**Sem mudança:** derivação, regras, esquema, snapshots, banco, configuração, plano, contrato e `explicacoes.py`. Nenhuma regra é reimplementada (regime "derivação").

## 2. O que a tela mostra no dado real (derivação 23)

**Anomalias** (19.684 ocorrências, todas com chave de empenho):

| Tipo | Regra | Ocorrências | Nos snapshots vigentes | Snapshots | Exercícios |
|---|---|---|---|---|---|
| COPIA-24 | ANOM-REG v1 | 17.434 | 7.648 | 40 | 2024–2026 |
| LIQ-NEG | ANOM-REG v1 | 2.096 | 1.976 | 68 | 2016–2026 |
| PAGOPROC-SEM-PROC | ANOM-REG v1 | 99 | 76 | 31 | 9 exercícios |
| PAR-INSCRICAO-DIVERGENTE | PAR-24 v1 | 55 | 55 | 7 | 2024–2025 |

- **Tipos sem ocorrência:** 8 (CHAVE-DUP, SALDO-SEM-CONTINUIDADE, DESCONTINUIDADE, COPIA-SEM-PAR e outros) aparecem listados como "sem ocorrência na derivação atual".
- **Contagem por snapshot:** a derivação grava as anomalias por registro (ANOM-REG) em **todo** snapshot processado, inclusive retratos anteriores do mesmo corte e coletas por tipo de pesquisa. Por isso o mesmo empenho conta uma vez por retrato. A tela diz isso e mostra, ao lado, quantas ocorrências estão nos snapshots vigentes.

**Verificações:**

| Descrição | Regra | Itens | Verificados | "Falhas" | Situação exibida |
|---|---|---|---|---|---|
| continuidade fechamento→abertura | ANOM-CONT v1 | 100 | 64.792 | 0 | sem falha |
| pareamento de cópias 24xxxxx | PAR-24 v1 | 19 | 3.045 | 0 | sem falha |
| conciliação RREO × API (colunas com diferença) | CONC-RREO v1 | 66 | 792 | 466 | colunas com diferença: 466 de 792 |
| RREO sem valores extraídos (ver problemas da normalização) | CONC-RREO v1 | 3 | 3 | 3 | PDFs não lidos: 3 |

**Diferenças com o RREO por situação:**

| Situação | RREO-COL v1 | RREO-COL v2 | Coerência (exibida) | Coerência (todas) |
|---|---|---|---|---|
| sem diferença | 142 | 168 | 3 | 3 |
| explicada | 32 | 58 | 2 | 8 |
| parcialmente explicada | 127 | 40 | 1 | 6 |
| hipótese | 17 | 27 | 5 | 10 |
| não determinada | 66 | 91 | 1 | 1 |
| total | 384 | 384 | 12 | 28 |

- **Conferência com a verificação CONC-RREO:** a verificação conta 792 colunas, 466 com diferença, porque conta por snapshot do PDF. A reconciliação conta por documento: 768 colunas (32 documentos × 12 colunas × 2 regras), 458 com diferença. A diferença é um PDF coletado duas vezes (24 colunas, 8 com diferença): 792 − 24 = 768 e 466 − 8 = 458.
- **Coerência:** a tela de reconciliação mostra 12 comparações, a publicação mais recente de A+1 para cada escopo e exercício. A qualidade mostra essas 12 e também as 28 comparações com todas as publicações.

## 3. Testes novos (`test_qualidade_05_6.py`)

| Teste | O que garante |
|---|---|
| `test_SINTETICO_anomalias_por_tipo_e_sem_ocorrencia` | contagens por tipo, nos vigentes, com chave e por snapshot (o mesmo corte coletado duas vezes); tipos sem ocorrência |
| `test_SINTETICO_ligacao_so_com_chave_e_exata_so_no_vigente` | anomalia sem chave fora da lista e contada em `sem_chave`; vigente leva ao registro (o valor do detalhe é o da anomalia); retrato anterior leva aos retratos; tipo desconhecido recusado |
| `test_SINTETICO_verificacao_fora_do_catalogo_nao_e_interpretada` | descrição desconhecida, e descrição conhecida gravada por outra regra: "significado não catalogado", números brutos preservados |
| `test_SINTETICO_ligacao_da_verificacao_por_regra_e_escopo` | item com falha leva às anomalias da mesma regra no exercício e na entidade do escopo |
| `test_SINTETICO_tela_da_qualidade` | tela = painel; uma ligação ao registro e uma aos retratos; verificação sem link de empenho; aviso de ocorrência sem chave; tipo sem ocorrência; 400 para tipo desconhecido |
| `test_anomalias_iguais_a_derivacao` | contagens = tabela `anomalia`; vigentes = `derivar.coletas_vigentes`; tipos sem ocorrência = catálogo − presentes |
| `test_verificacoes_iguais_a_derivacao_e_interpretadas` | itens, verificados e falhas = tabela `verificacao`; as quatro situações; continuidade ligada às suas anomalias |
| `test_cinco_situacoes_iguais_a_reconciliacao` | por regra = linhas da reconciliação; "sem diferença" = diferença zero; nenhuma diferença zero como explicada; coerência exibida = 12; conferência 466 / 8 / 458 |
| `test_drill_down_real_leva_ao_registro` | LIQ-NEG e PAGOPROC-SEM-PROC: o registro ligado tem o mesmo snapshot e o mesmo valor da anomalia |
| `test_tela_igual_ao_painel_reais` | valores da tela = painel; menos de 3 s; a coerência da reconciliação continua com 12 linhas; nenhum campo de identificação do credor no detalhe das anomalias |

## 4. Validação

| Verificação | Resultado | Evidência |
|---|---|---|
| Suíte de produção | **348 passed** | `resultados/05_6_testes_producao.txt` |
| Investigação | **26 passed** | `resultados/05_6_testes_investigacao.txt` |
| `verificar` | sem problemas | `resultados/05_6_verificar.txt` |
| `portoes` | apto | `resultados/05_6_portoes.json` |
| Bruto, armazém, derivações | idênticos | `resultados/05_6_comparacao_*.json` |
| Valores homologados (inclui a coerência, que ganhou a marca `mais_recente`) | 0 diferenças na camada painel e nos 5.575 valores de tela | idem |
| Responsividade | celular, tablet e notebook sem estouro | `resultados/05_6_responsividade.json` |

## 5. Revisão do que foi feito

Revisão item a item contra o plano (seção 05.6) e o contrato (E-01 a E-03), com o código final relido:

| Item | Situação |
|---|---|
| Anomalias por tipo: código, descrição, evidência, regra, quantidade, escopo (coletas e exercícios) | ok |
| Registros relacionados com o detalhe de `detalhe_json` | ok (lista paginada) |
| Drill-down só com entidade, ano e número do empenho | ok, e exato só no snapshot vigente |
| Anomalia sem chave só no agregado | ok (após correção, item 1 abaixo) |
| Texto: anomalia não é erro; usa a descrição do tipo | ok |
| Verificações: regra, descrição, escopo, verificados, falhas, snapshots | ok |
| Situação interpretada por descrição (R5); fora do catálogo = "significado não catalogado", sem analogia | ok (exige também a regra do catálogo) |
| Verificação nunca listada como empenhos; ligação às anomalias por regra e escopo | ok (após correção, item 2) |
| Cinco situações separadas, por coluna × documento × regra, e na coerência | ok |
| Diferença zero nunca contada como explicada; "sem diferença" nunca somada a "explicada" | ok (colunas separadas; o total é o número de comparações) |
| Nenhuma regra nova; nenhuma reinterpretação | ok |

**Problemas encontrados e corrigidos durante a revisão:**
1. **Anomalia sem chave na lista:** na primeira versão, a ocorrência sem chave aparecia na lista de ocorrências, sem ligação. O contrato (E-01) diz que ela fica só no agregado. Agora a lista traz só as ocorrências com chave e informa quantas ficaram de fora.
2. **Ligação da verificação só por regra:** o plano pede a ligação por regra **e escopo**. Agora cada item com falha leva às anomalias da mesma regra no seu escopo, pelo mesmo critério com que a derivação as grava:
   - continuidade: snapshot de abertura de A+1 da entidade;
   - pareamento: snapshot da entidade-cópia no corte.

   Hoje nenhum item tem falha; o caso é coberto por teste sintético.
3. **Drill-down não exato:** a derivação grava anomalias também em retratos anteriores e em coletas que não são cortes. Ligar todas ao detalhe do empenho mostraria outro retrato (o vigente). Agora:
   - só a ocorrência do snapshot vigente leva ao registro;
   - a de retrato anterior leva aos retratos do corte;
   - a de coleta que não é corte não tem ligação.
4. **Duas contagens da conciliação:** a verificação dá 466 colunas com diferença e a reconciliação, 458. Em vez de mostrar números que não batem, a tela mostra a conferência com o PDF repetido, e um teste a confere.
5. **Escolha duplicada da coerência exibida:** a escolha estava na interface e seria repetida na camada painel. Virou uma marca única (`mais_recente`) na camada painel.
6. **Linhas altas no celular:** quatro ajustes de apresentação (seção 6).
7. **Forma:** um `__import__("json")` improvisado virou um `import json` normal.

## 6. Ajustes feitos durante a verificação de responsividade

- **Anomalias por tipo:** o código do tipo (ex.: PAR-INSCRICAO-DIVERGENTE) quebrava letra a letra numa coluna de 43 px, com linhas de até 226 px. Agora não quebra, e as colunas de texto têm largura mínima (até 89 px).
- **Itens das verificações:** coluna de escopo com largura mínima (o pareamento tinha linhas de 168 px; agora 51 px).
- **Significado das falhas:** largura mínima (de 128 px para 109 px).
- **Ocorrências:** colunas de retrato e de detalhe com largura mínima (de 128 px para 70 px).

## 7. O que não foi implementado

- 05.7 (homologação e encerramento da Etapa 05).
- Interpretação de verificação fora do catálogo do contrato. A derivação pode gravar "RREO sem snapshot da API no mesmo corte" (hoje com 0 itens); se aparecer, sai como "significado não catalogado" até uma revisão do contrato.
- D1, coletas, automação e qualquer mudança em derivação, regras ou dados.
