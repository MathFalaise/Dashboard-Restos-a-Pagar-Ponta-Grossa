# Relatório da Subetapa 05.5 — investigação de variações

Data: 01/10/2026. Ramo `subetapa-05.5`, criado de `subetapa-05.4` (`feca7b7`), sobre a base homologada `etapa-04-final` (`a6bd27c`).

- **Contrato:** `etapa05/CONTRATO_ANALITICO.md` (M-09 a M-12; seções 2, 3 e 4.2).
- **Plano:** `etapa05/PLANO_ETAPA05.md`, seção 05.5 e problema R6.

**Resumo:**
- **Variação entre dois cortes do mesmo exercício** (`Painel.variacao`): para o saldo S1 ou os pagamentos, a variação total (indicador homologado do posterior − do anterior) é explicada pela contribuição de cada empenho.
  - **Escolha do par:** o usuário escolhe qualquer par de cortes do exercício, vizinhos ou não, com o anterior antes do posterior.
  - **Contribuição:** o sinal é sempre posterior − anterior, separado em três classes:
    - nos dois cortes;
    - presente só no corte posterior;
    - ausente no corte posterior.
  - **Par indisponível:** o par fica indisponível, com o motivo, quando:
    - um lado não tem valor no escopo;
    - o Município soma conjuntos de entidades diferentes (R6);
    - a mesma chave aparece mais de uma vez num snapshot. Nesse caso a tela lista as chaves e nenhuma ocorrência é escolhida.
- **Fechamento obrigatório:** a lista completa, os grupos do resumo (10 maiores aumentos, outros aumentos, 10 maiores reduções, outras reduções, sem variação) e as classes fecham **ao centavo** com a variação total. Se não fechassem, o par seria bloqueado; isso não ocorreu.
- **Lista completa paginada:**
  - traz todas as chaves com contribuição ≠ 0, do maior aumento à maior redução, com empate desfeito por entidade, ano e número;
  - cada página mostra o subtotal e o acumulado; a última fecha com a variação total.
- **Empenho em todos os cortes** (`Painel.historico_empenho`, M-12):
  - mostra os valores do registro em cada corte do exercício;
  - corte sem valor para a entidade aparece com a situação; corte em que a chave não aparece, como "empenho ausente deste corte";
  - chave repetida mostra todas as ocorrências.
- **Telas:**
  - `/variacao` ("Variação entre cortes");
  - `/empenho/cortes`, com link a partir do detalhe do empenho;
  - cada intervalo da tabela de diferenças da Evolução passa a levar à investigação dele.
- **Validação:** todos os pares de cortes vizinhos de 2025 e 2026, mais o par que salta a lacuna do Município (28/02 → 30/04/2026): 12 pares × Município e 10 entidades × 2 métricas = 264 combinações.
  - Em todas, a disponibilidade é igual à do recálculo do JSON bruto.
  - Nas 144 com valor, cada contribuição, os grupos e as classes são iguais ao bruto.
  - Em todas as 144, a variação é igual à diferença dos indicadores homologados.
- **Testes:** **338/338** de produção (324 + 14 novos) e **26/26** da investigação. `verificar` sem problemas; `portoes` apto. Bruto, armazém, derivações e os 5.575 valores homologados da 04.6 idênticos. Responsividade verificada.

---

## 1. O que mudou

| Arquivo | Mudança |
|---|---|
| `app/rp/painel/consulta.py` | `EXPR_PAGAMENTOS`: expressão única dos pagamentos, usada no indicador "pagamentos", no agrupamento e na variação (o plano pedia que virasse constante, como `EXPR_CANCELAMENTOS`; sem mudança de valor).<br>`METRICAS_DA_VARIACAO` (só S1 e pagamentos), `CLASSES_DA_CHAVE`, `TOP_DA_VARIACAO` (10), `CAMPOS_DO_HISTORICO`.<br>`variacao`, `_valores_por_chave`, `_universo_do_exercicio`, `historico_empenho`.<br>`_pares_no_corte` (contagem das cópias 24xxxxx do corte, agora usada pela composição e pela variação) |
| `app/rp/interface/paginas.py` | páginas `variacao` e `empenho_cortes`; item "Variação entre cortes" no menu; link do detalhe do empenho para o empenho em todos os cortes; link de cada intervalo da tabela de diferenças da Evolução para a variação |
| `app/rp/interface/aplicacao.py` | rotas `/variacao` e `/empenho/cortes` |
| `app/rp/interface/estilo.css` | larguras mínimas das colunas de situação e de classe nas tabelas novas |
| `app/tests/recalculo_bruto.py` | `Bruto.empenho_nos_cortes` (M-12); `Bruto.contribuicoes` já existia (05.1) |
| `app/tests/test_variacao_05_5.py` (novo) | 14 testes |
| `app/README.md` | linha da 05.5 e as telas novas |

**Sem mudança:** derivação, regras, esquema, snapshots, banco, configuração, plano e contrato. A interface não calcula: variação, contribuições, grupos, classes, fechamentos e somas de página vêm prontos da camada painel.

## 2. Comportamento no dado real (Município)

| Par | Métrica | Variação | Empenhos com variação | Grupos |
|---|---|---|---|---|
| 31/10 → 31/12/2025 | S1 | −R$ 9.995.201,17 | 422 (de 5.878) | só reduções: 10 maiores −R$ 6.399.845,28; outras 412 −R$ 3.595.355,89 |
| 31/10 → 31/12/2025 | pagamentos | +R$ 3.929.640,01 | 101 | só aumentos |
| 28/02 → 30/04/2026 (salta 31/03) | S1 | −R$ 40.100.737,26 | 981 (de 5.760) | só reduções |
| 30/06 → 31/08/2026 | S1 | −R$ 11.371.591,79 | 447 | 1 aumento de R$ 5,33 (o mesmo empenho tem pagamento −R$ 5,33: estorno de pagamento) |

- **Chave de um lado só:** em nenhum par real há chave presente só num corte. É coerente com a medição do plano (inscrição e registros iguais em todos os cortes do exercício). As classes "presente só no corte posterior" e "ausente no corte posterior" estão cobertas por testes sintéticos.
- **Chave repetida:** nenhuma, em nenhum snapshot (CHAVE-DUP = 0). O critério de parada não foi acionado.
- **Pares sem valor:** 120 das 264 combinações, todas com o motivo:
  - 110 em 2026:
    - 70 das entidades fora do catálogo de 2026 (3, 6, 9, 10 e 11), em todos os 7 pares;
    - 40 do Município e das entidades 4, 5, 8 e 15, nos 4 pares que envolvem 31/01, 31/03 ou 31/12, cortes que não têm essas entidades;
  - 10 em 2025: a entidade 10, fora do catálogo do exercício (5 pares × 2 métricas).
- **Cópias 24xxxxx:** o aviso aparece quando o escopo envolve as entidades 1 e 15 (20 em 2025; 731 em 2026). Uma cópia incluída depois apareceria como "presente só no corte posterior".
- **Casos do plano:**
  - 5659/2025 (entidade 1) aparece nos 7 cortes de 2026, e o de 31/12/2026 é rotulado "corte posterior à coleta";
  - 2401751/2023 aparece nos 6 cortes de 2025;
  - 1751/2023 (entidade 15) mostra 31/01, 31/03 e 31/12/2026 como "corte não coletado".

  Todos batem com o bruto.

## 3. Testes novos (`test_variacao_05_5.py`)

| Teste | O que garante |
|---|---|
| `test_SINTETICO_contribuicoes_classes_grupos_e_fechamento` | contribuições e classes de chave só no posterior, só no anterior, nos dois e sem variação; empate resolvido pela chave; reduções do TOP em ordem crescente; fechamento de lista, grupos e classes; métrica de pagamentos |
| `test_SINTETICO_paginas_com_subtotal_e_acumulado` | subtotal e acumulado por página; a última fecha com a variação |
| `test_SINTETICO_igual_ao_recalculo_do_bruto` | 3 escopos × 2 métricas × 3 pares (inclusive com lado indisponível) |
| `test_SINTETICO_par_indisponivel_e_zero_verdadeiro` | lado sem valor; entidade sem RP (variação 0); tudo sem variação; corte não processado; par invertido ou igual recusado; métrica fora do contrato recusada |
| `test_SINTETICO_chave_repetida_bloqueia_o_par` | lista das chaves repetidas; histórico mostra as duas ocorrências; o bruto também bloqueia |
| `test_SINTETICO_municipio_com_entidades_diferentes_bloqueia_o_par` | R6 no Município; a entidade continua disponível |
| `test_SINTETICO_historico_do_empenho_e_bruto` | presente, ausente e lacuna; igual ao bruto |
| `test_SINTETICO_tela_da_variacao_e_do_empenho` | tela = painel; "ausente do corte posterior" em vez de R$ 0,00; indisponível sem números; par invertido com aviso; métrica inválida = 400; links novos |
| `test_todos_os_pares_adjacentes_e_o_que_salta_lacuna_iguais_ao_bruto` | as 264 combinações reais; 144 disponíveis; variação = diferença dos indicadores homologados; proveniência dos dois lados em cada contribuição |
| `test_salto_de_lacuna_e_pares_com_lacuna_no_municipio` | 28/02 → 30/04/2026 disponível; pares com 31/01, 31/03 e 31/12 indisponíveis no Município |
| `test_pagina_a_pagina_ate_a_variacao_total` | 20 páginas de 50: o acumulado chega à variação |
| `test_casos_reais_5659_2025_e_2401751_2023` | histórico = bruto; contribuição de 5659/2025 = bruto |
| `test_tela_igual_ao_painel_reais` | primeira e última página; acumulado da última = variação |
| `test_desempenho_com_o_corte_inteiro` | menos de 3 s (medido: 0,1–0,3 s) |

## 4. Validação

| Verificação | Resultado | Evidência |
|---|---|---|
| Suíte de produção | **338 passed** | `resultados/05_5_testes_producao.txt` |
| Investigação | **26 passed** | `resultados/05_5_testes_investigacao.txt` |
| `verificar` | sem problemas | `resultados/05_5_verificar.txt` |
| `portoes` | apto | `resultados/05_5_portoes.json` |
| Bruto, armazém, derivações | idênticos | `resultados/05_5_comparacao_*.json` |
| Valores homologados (inclui o indicador "pagamentos", que passou a usar `EXPR_PAGAMENTOS`) | 0 diferenças na camada painel e nos 5.575 valores de tela | idem |
| Responsividade | celular, tablet, notebook e painel do app sem estouro | `resultados/05_5_responsividade.json` |

## 5. Revisão do que foi feito

Revisão item a item contra o plano (seção 05.5) e o contrato (M-09 a M-12), com o código final relido:

| Item | Situação |
|---|---|
| Par do mesmo exercício, escolhido explicitamente, anterior < posterior | ok; entre exercícios não há investigação (é o fechamento × abertura da 05.3) |
| Pré-condições (dois lados com valor; mesmo conjunto de entidades no Município) | ok, com motivo |
| Chave repetida bloqueia o par e lista as chaves | ok |
| Só S1 e pagamentos, pela expressão do indicador | ok (`EXPR_PAGAMENTOS` criada) |
| Datas de coleta dos dois lados na tela | ok ("Os dois cortes") |
| Contribuição e classes, sinal posterior − anterior, nunca valor absoluto | ok |
| Lista completa só com contribuição ≠ 0, ordem e desempate do contrato | ok |
| Subtotal e acumulado por página; a última fecha | ok |
| Resumo TOP N, outros, sem variação; fechamento de grupos e de classes | ok |
| Registro de um lado só nunca vira zero sem rótulo | ok ("ausente do corte anterior/posterior") |
| Proveniência dos dois lados, até o objeto bruto | ok |
| Histórico do empenho com situação e ausência | ok |

**Problemas encontrados e corrigidos durante a revisão:**
1. **Ordem de definição:** `METRICAS_DA_VARIACAO` usava `EXPR_PAGAMENTOS` antes de ela ser definida (erro na importação, pego no primeiro teste). O bloco foi movido para depois da constante.
2. **"Sem valor" no corte que tem valor:** quando só um lado do par não tinha valor, ou o par era bloqueado por R6 ou chave repetida, o total do outro corte não era calculado, e a tela mostrava "sem valor". Agora o total de cada corte com valor é sempre calculado; um teste confere.
3. **Snapshots parciais:** num corte sem valor para o escopo (Município incompleto), a tela listava os snapshots das entidades que existiam. Agora a lista fica vazia nesse caso.
4. **Linhas altas:** três ajustes de apresentação vieram da verificação de responsividade (seção 6).

## 6. Ajustes feitos durante a verificação de responsividade

- **"Os dois cortes":** os 10 identificadores de snapshot do Município ficavam empilhados na célula, com linhas de 675 px em 375 px. Agora ficam num bloco recolhível com a contagem, e a linha tem 89 px.
- **Empenho nos cortes:** a coluna de situação ganhou largura mínima (a linha de 187 px caiu para 70 px).
- **Lista de contribuições:** a coluna de classe ganhou largura mínima.

## 7. O que não foi implementado

- 05.6 (qualidade dos dados) e 05.7.
- Variação entre exercícios diferentes, fora do plano: a passagem de um exercício ao seguinte é o fechamento × abertura da 05.3.
- Outras métricas de contribuição: o contrato limita a S1 e pagamentos.
- D1, coletas, automação e qualquer mudança em derivação, regras ou dados.
