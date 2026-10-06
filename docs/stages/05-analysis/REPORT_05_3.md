# Relatório da Subetapa 05.3 — série histórica entre exercícios

Data: 01/10/2026. Ramo `subetapa-05.3`, criado de `subetapa-05.2` (`fa3f1c7`), sobre a base homologada `etapa-04-final` (`a6bd27c`).

- **Contrato:** `docs/stages/05-analysis/ANALYTICAL_CONTRACT.md` (M-03, M-04, E-02; seções 1.6, 2.1, 2.5).
- **Plano:** `docs/stages/05-analysis/PLAN.md`, seção 05.3 e problemas R2, R7 e R8.

**Resumo:**
- **Série entre exercícios:** `Painel.serie_entre_exercicios` cobre de 2016 a 2026, para o Município e cada entidade.
  - Cada exercício aparece no **corte representativo**, o mesmo para todos os escopos (R8): 31/12 de 2016 a 2025 e 31/08 para 2026, rotulado "exercício em aberto".
  - Todo ponto com valor traz o retrato "Estado atual da base para o exercício de A, corte …, coletado em …".
- **Fechamento × abertura (P7):** compara o saldo S1 do fechamento de A com a abertura de A+1 nas faixas 'a' e 'f' da FAIXA v1, sinal abertura − S1 (R2). No Município, a comparação só é feita quando as entidades que entram ou saem do catálogo não têm registros (R7).
  - **Resultado real:** diferença **0** em todas as 10 transições, para o Município e cada entidade. As entradas e saídas de entidades aparecem listadas: 15 entra em 2019; 10 sai em 2023; 3, 6, 9 e 11 saem em 2026, todas sem registros.
  - **Continuidade:** a verificação ANOM-CONT v1 da derivação é exibida ao lado, no regime de derivação (só leitura). Tem 0 falhas.
- **Situação nova:** `exercicio_sem_cobertura` para exercício sem nenhuma coleta (contrato, seção 2.1). Exercício sem nenhum corte com o Município completo fica como lacuna para todos os escopos.
- **Tela `/historico` ("Série entre exercícios"):** gráfico, tabela com o retrato em cada linha e tabela de fechamento × abertura com a continuidade.
- **Validação:** série e fechamento iguais ao recálculo do JSON bruto em todos os exercícios e escopos. Fechamento igual ao que a coerência entre publicações já exibe para o consolidado e a entidade 1. Continuidade igual à tabela da derivação. Tela igual ao painel.
- **Testes:** **307/307** de produção (294 + 13 novos) e **26/26** da investigação. `verificar` sem problemas; `portoes` apto. Bruto, armazém, derivações e os 5.575 valores homologados da 04.6 idênticos. Responsividade verificada nos quatro tamanhos.

---

## 1. O que mudou

| Arquivo | Mudança |
|---|---|
| `app/rp/painel/consulta.py` | situação `exercicio_sem_cobertura` em `SITUACOES_DO_PONTO`.<br>`_s1_e_a_mais_f`: definição única de S1 e (a)+(f), que antes estava só dentro de `_api_do_corte`; a coerência passa a usá-la, sem mudança de valor.<br>`_sem_cobertura`, `corte_representativo`, `serie_entre_exercicios`, `_ponto_do_exercicio`, `_fechamento_abertura` (R7) e `_continuidade` (leitura da tabela `verificacao`). Pontos sem valor têm todos os indicadores com `valor_c = None`, no mesmo formato da série da 05.2 |
| `app/rp/interface/paginas.py` | página `historico`; item "Série entre exercícios" no menu; forma curta da situação (`_situacao_curta`) também na tela da 05.2; classes `serie` e `historico` nas tabelas |
| `app/rp/interface/aplicacao.py` | rota `/historico` |
| `app/rp/interface/grafico.py` | a lacuna ocupa cerca de 90% da faixa do ponto, para o rótulo caber com 11 pontos |
| `app/rp/interface/estilo.css` | largura mínima das colunas de texto das duas tabelas de série |
| `app/tests/recalculo_bruto.py` | `sem_cobertura`, `corte_representativo` e `a_mais_f` recalculados do bruto |
| `app/tests/test_historico_05_3.py` (novo) | 13 testes |
| `app/README.md` | linha da 05.3 e a tela nova |

**Sem mudança:** derivação, regras, esquema, snapshots, banco, configuração, plano e contrato. A interface não calcula: valores, diferenças e contagens vêm prontos da camada painel.

## 2. Testes novos (`test_historico_05_3.py`)

| Teste | O que garante |
|---|---|
| `test_SINTETICO_universo_corte_representativo_e_lacunas` | exercício sem cobertura no meio da série; 31/12 sem o Município completo → corte anterior rotulado "em aberto", o mesmo para todo escopo; exercício sem nenhum corte do Município → lacuna para todos os escopos; entidade inexistente sem valor |
| `test_SINTETICO_fechamento_e_abertura_com_sinal_e_faixa` | abertura sem a faixa g (empenhos do ano A); sinal abertura − S1; diferença −500 no Município e 0 na entidade 1; proveniência dos dois lados |
| `test_SINTETICO_R7_entidade_que_sai_com_registros_bloqueia_o_municipio` / `..._sem_registros_e_listada` | R7 |
| `test_SINTETICO_continuidade_e_lida_da_derivacao` | continuidade igual à tabela da derivação, inclusive com falhas |
| `test_SINTETICO_tela_retrato_lacunas_e_grafico` | texto do retrato por linha; lacunas sem "R$"; SVG conforme; nenhuma frase do tipo "situação em AAAA" ou "Restos a Pagar de AAAA" |
| `test_corte_representativo_real_igual_para_todos_os_escopos` | R8 no dado real, para os 11 escopos |
| `test_serie_e_fechamento_iguais_ao_recalculo_do_bruto` | painel = bruto em situação, valores, S1, abertura e diferença, para todos os exercícios e escopos |
| `test_fechamento_igual_a_coerencia_ja_homologada` | mesma definição da coerência (consolidado e entidade 1, 2020–2025) |
| `test_R7_nas_transicoes_reais` | 15 entra em 2019; 10 sai em 2023; 3, 6, 9 e 11 saem em 2026; diferença 0 |
| `test_continuidade_igual_a_tabela_da_derivacao` | por entidade e somada no Município; 0 falhas |
| `test_tela_igual_ao_painel_com_retrato_em_todo_ponto` | valores, fechamentos, lacunas e retrato da tela = painel |
| `test_desempenho_da_serie_entre_exercicios` | menos de 3 s |

## 3. Validação

| Verificação | Resultado | Evidência |
|---|---|---|
| Suíte de produção | **307 passed** | `resultados/05_3_testes_producao.txt` |
| Investigação | **26 passed** | `resultados/05_3_testes_investigacao.txt` |
| `verificar` | sem problemas | `resultados/05_3_verificar.txt` |
| `portoes` | apto | `resultados/05_3_portoes.json` |
| Bruto, armazém, derivações | idênticos | `resultados/05_3_comparacao_*.json` |
| Valores homologados (inclui a coerência entre publicações, que passou a usar `_s1_e_a_mais_f`) | 0 diferenças na camada painel e nos 5.575 valores de tela | idem |
| Responsividade | celular, tablet, notebook e desktop sem estouro; gráfico com 11 barras sem rótulos sobrepostos; "sem dado" dentro da lacuna; linhas de no máximo 89 px em 375 px | `resultados/05_3_responsividade.json` |

## 4. Ajustes feitos durante a verificação

Os três ajustes são só de apresentação, sem efeito em valores:
- **Lacuna do gráfico:** passou a ocupar cerca de 90% da faixa do ponto. Com 11 exercícios em 375 px, o rótulo (23 px) passava da lacuna (18 px).
- **Forma curta da situação:** passou a cortar também o parêntese ("entidade inexistente no exercício"), nas duas telas de série. O texto completo continua como dica, e o motivo, na célula de valores.
- **Colunas de texto:** ganharam largura mínima (Retrato 17em, Situação 11em). Em 375 px, linhas de até 194 px caíram para 89 px; a tabela continua rolando dentro do quadro.

## 5. Observações

- **Corte da continuidade:** a verificação ANOM-CONT usa como abertura o snapshot de A+1 de maior data final, que pode não ser o corte representativo (para 2026, a continuidade da entidade 1 usa 31/12/2026). Isso está indicado na tela e no contrato. A exibição só lê o que a derivação gravou.
- **Escopo sem RREO:** a comparação fechamento × abertura antes existia só na coerência. Agora existe para qualquer escopo, com a mesma definição.
- **Exercício sem cobertura:** não há nenhum no dado real (2016–2026 completos); o caso é coberto por teste sintético.

## 6. O que não foi implementado

- 05.4 (composição), 05.5 (investigação de variações), 05.6 (qualidade dos dados), 05.7.
- Diferença entre exercícios vizinhos (opcional no contrato, M-03 item 11). A pergunta P7 é respondida pelo fechamento × abertura.
- D1, coletas, automação e qualquer mudança em derivação, regras ou dados.
