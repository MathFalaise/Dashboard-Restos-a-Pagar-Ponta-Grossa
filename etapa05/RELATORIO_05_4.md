# Relatório da Subetapa 05.4 — composição do saldo

Data: 01/10/2026. Ramo `subetapa-05.4`, criado de `subetapa-05.3` (`6ab3dab`), sobre a base homologada `etapa-04-final` (`a6bd27c`).

- **Contrato:** `etapa05/CONTRATO_ANALITICO.md` (M-05 a M-08; seções 2, 3 e 4.2).
- **Plano:** `etapa05/PLANO_ETAPA05.md`, seção 05.4 e problema R3.

**Resumo:**
- **Composição do corte:** `Painel.composicao` decompõe a inscrição e o saldo de um corte, para o Município ou uma entidade, em oito dimensões:
  - categoria (CAT v1);
  - faixa (FAIXA v1);
  - tipo de credor;
  - fonte de recurso, órgão, função, programa e elemento de despesa.
- **Fechamento por dimensão:** cada dimensão fecha **sozinha** com o total do corte, por medida (registros, inscrição e saldo S1): soma dos grupos − total = 0, sem tolerância nem ajuste. Dimensão que não fecha **não é exibida**, mesmo que as outras fechem, e o motivo aparece com o valor da diferença.
- **Faixa (R3):** fecha em **valores** (soma de proc por faixa do processado + soma de aproc por faixa do não processado = inscrição total). A contagem de registros por faixa é por parte e não é somada. O texto é "composição dos registros da API segundo a regra FAIXA v1", sem referência às colunas do RREO.
- **Grupos:**
  - os fixos (as 4 categorias, as 4 faixas, os 3 tipos de credor) aparecem sempre, com 0 quando vazios;
  - nas dimensões orçamentárias, o grupo "sem classificação" (campo ausente no registro da API) aparece sempre, por último.
- **Do grupo à lista:** cada grupo leva à lista de empenhos cujo total é o próprio grupo. Para isso, a lista ganhou os filtros de faixa, órgão, função, programa, elemento e "sem classificação".
- **Tela `/composicao` ("Composição do saldo"):** total do corte, a dimensão escolhida e a tabela de fechamento de todas as dimensões. O Resumo tem link para ela.
- **Resultado real:** nos 181 recortes com valor (22 cortes × Município e 10 entidades, menos 61 sem valor), as 8 dimensões fecham em todos, e são iguais ao recálculo do JSON bruto.
- **Testes:** **324/324** de produção (307 + 17 novos) e **26/26** da investigação. `verificar` sem problemas; `portoes` apto. Bruto, armazém, derivações e os 5.575 valores homologados da 04.6 idênticos. Responsividade verificada nos quatro tamanhos.

---

## 1. O que mudou

| Arquivo | Mudança |
|---|---|
| `app/rp/painel/consulta.py` | `fechamento(total, componentes)`: a implementação da camada painel da seção 4.2 do contrato (inteiros só; sem tolerância).<br>`_por_grupo`: consulta única de agrupamento, usada por `por_dimensao`, pelas categorias de `indicadores` e pela composição. As duas primeiras devolvem exatamente o que devolviam antes.<br>`_por_faixa`, `composicao`, `_dimensao`, `_rotulo_do_grupo`.<br>Constantes `COMPOSICOES`, `DIMENSOES_ORCAMENTARIAS`, `FAIXAS`, `ROTULO_CATEGORIA`, `ROTULO_COMPOSICAO`, `MEDIDAS_DA_COMPOSICAO`, `TEXTO_FAIXA`, `SEM_CLASSIFICACAO`.<br>`_filtros_empenho` e `empenhos`: filtros `faixa`, `orgao`, `funcao`, `programa`, `elemento` e `sem_classificacao` |
| `app/rp/interface/paginas.py` | página `composicao`; item "Composição do saldo" no menu; link no Resumo; bloco recolhível "Mais filtros: faixa e classificação orçamentária" na lista de empenhos (aberto quando algum desses filtros está em uso); `NOME_CATEGORIA` passa a vir da camada painel |
| `app/rp/interface/aplicacao.py` | rota `/composicao` |
| `app/rp/interface/estilo.css` | largura mínima da coluna de grupo, link da lista sem quebra, navegação entre dimensões e bloco de filtros extras |
| `app/tests/recalculo_bruto.py` | `categoria`, `tipo_credor` e `composicao` recalculados do bruto pelas definições documentadas; `Bruto.composicao` |
| `app/tests/test_composicao_05_4.py` (novo) | 17 testes |
| `app/README.md` | linha da 05.4 e a tela nova |

**Sem mudança:** derivação, regras, esquema, snapshots, banco, configuração, plano e contrato. A interface não calcula: grupos, totais e fechamentos vêm prontos da camada painel.

## 2. Comportamento no dado real (Município, 31/12/2025)

Total do corte: 5.878 registros, inscrição R$ 250.551.057,73, saldo S1 R$ 21.267.174,28.

| Dimensão | Grupos | Observação |
|---|---|---|
| Categoria | 4 | processado 690, não processado 5.072, ambos 116, sem saldo de abertura **0** (aparece com zero) |
| Faixa | 4 | registros com parte em a 477, b 329, f 774, g 4.414. A soma das contagens (5.994) é maior que 5.878 porque os 116 registros "ambos" entram em duas faixas (R3). Os **valores** somam a inscrição exata |
| Tipo de credor | 3 | pessoa jurídica 3.947, pessoa física 1.931, não identificado **0** |
| Fonte de recurso | 151 | 150 códigos + "sem classificação" com 0 registros |
| Órgão / função / programa / elemento | 28 / 20 / 69 / 49 | cada uma com "sem classificação" de **16 registros**, a medição do plano (seção 5.4) |

- **Fechamento:** 0 em todas as medidas das 8 dimensões, em todos os 181 recortes com valor.
- **Recortes sem valor:** 61, todos mostrados como indisponíveis, com a situação, e nenhum com grupos zerados:
  - 46 entidade fora do catálogo;
  - 12 corte não coletado;
  - 3 Município indisponível.
- **Pares 24xxxxx:** o aviso aparece quando o escopo envolve as entidades 1 e 15: 20 cópias em 31/12/2025 e 731 em 31/08/2026. Os dois lados continuam em todos os grupos.
- **Fonte de recurso:** no dado real, cada código tem uma única descrição. Se um código aparecer com duas descrições, os dois grupos continuam na composição, mas sem link de lista, porque a lista filtra por código e juntaria os dois. Esse caso é coberto por teste sintético.

## 3. Testes novos (`test_composicao_05_4.py`)

| Teste | O que garante |
|---|---|
| `test_SINTETICO_fechamento_grupos_fixos_e_sem_classificacao` | valores por grupo de todas as dimensões; grupos fixos na ordem e com 0 quando vazios; "sem classificação" presente e por último; faixa só com a medida de valor |
| `test_SINTETICO_igual_ao_recalculo_do_bruto` | painel = bruto no Município e nas entidades |
| `test_SINTETICO_zero_verdadeiro_e_indisponivel` | entidade sem RP: composição com zeros; Município indisponível e entidade sem coleta: indisponível, sem grupos |
| `test_SINTETICO_dimensao_que_nao_fecha_nao_e_exibida` | proc negativo não tem faixa: a faixa não fecha (diferença 1.000), sai da tela e da camada sem grupos; as outras 7 continuam exibidas; o bruto também não fecha |
| `test_SINTETICO_cada_grupo_leva_a_lista_com_o_proprio_total` | todo grupo de toda dimensão, nos três escopos |
| `test_SINTETICO_fonte_com_duas_descricoes_fica_sem_lista` | código com duas descrições: dois grupos, sem lista, com o motivo |
| `test_SINTETICO_filtros_novos_validados` | filtros novos parametrizados; valores fora da lista recusados |
| `test_SINTETICO_fechamento_do_painel_sem_tolerancia` | `fechamento` recusa bool, float e None |
| `test_SINTETICO_tela_valores_links_e_texto_da_faixa` | tela = painel; todo link leva a lista não vazia; CSP; sem `style`; texto da faixa sem "coluna", "RREO" nem "(a)"; indisponível sem R$; faixa inválida = 400 |
| `test_toda_dimensao_fecha_e_e_igual_ao_bruto_em_todo_corte_disponivel` | os 22 cortes × 11 escopos: situação igual à do bruto; nos recortes com valor, as 8 dimensões fecham e cada grupo é igual ao recalculado do bruto, sem grupo do bruto faltando |
| `test_sem_classificacao_presente_com_contagem` | 16 registros sem classificação orçamentária em 31/12/2025; fonte com 0 |
| `test_mesma_consulta_de_categorias_e_por_dimensao` | composição = `indicadores.categorias` e = `por_dimensao` |
| `test_cada_grupo_real_leva_a_lista_com_o_proprio_total` (3 casos) | todos os grupos reais de Município 31/12/2025, entidade 1 e entidade 15 em 31/08/2026 |
| `test_tela_igual_ao_painel_e_links_reais` | tela = painel em todas as dimensões; links seguidos até a lista com o mesmo total; aviso dos pares |
| `test_desempenho_da_composicao` | menos de 3 s por tela (medido: 0,1–0,2 s) |

## 4. Validação

| Verificação | Resultado | Evidência |
|---|---|---|
| Suíte de produção | **324 passed** | `resultados/05_4_testes_producao.txt` |
| Investigação | **26 passed** | `resultados/05_4_testes_investigacao.txt` |
| `verificar` | sem problemas | `resultados/05_4_verificar.txt` |
| `portoes` | apto | `resultados/05_4_portoes.json` |
| Bruto, armazém, derivações | idênticos | `resultados/05_4_comparacao_*.json` |
| Valores homologados (inclui as categorias do indicador e `por_dimensao`, que passaram a usar `_por_grupo`) | 0 diferenças na camada painel e nos 5.575 valores de tela | idem |
| Responsividade | celular, tablet, notebook e desktop sem estouro; tabelas largas rolam no próprio quadro | `resultados/05_4_responsividade.json` |

## 5. Ajustes feitos durante a verificação

Só de apresentação, sem efeito em valores:
- **Link da lista:** "ver N empenhos" quebrava em duas linhas em 375 px e dobrava a altura de quase todas as linhas da composição. Agora não quebra; as linhas de grupo têm 31 px.
- **Dica da faixa:** a indicação de qual total da lista corresponde à faixa ("Processado (inscrito)" ou "Não processado (inscrito)") estava em cada linha e levava a 109 px. Foi para a nota da seção (linhas de até 70 px).
- **Coluna de grupo:** largura mínima de 16em, para as descrições longas das fontes de recurso.
- **Navegação entre dimensões:** texto de 14 px e entrelinha maior, para área de toque adequada no celular.
- **Indisponível:** situação e motivo em frases separadas.

## 6. Observações

- **Sem gráfico:** a composição é respondida pela tabela (fonte da verdade). Um gráfico com 150 fontes ou 69 programas não seria legível em 375 px, e o plano exige que gráfico só entre se responder melhor à pergunta (seção 9.0).
- **Faixa só em valores:** a FAIXA v1 classifica só a parte positiva de cada registro. Um proc ou aproc negativo ficaria sem faixa e a faixa deixaria de fechar. Hoje não há nenhum valor negativo de proc ou aproc (medido), e o teste sintético cobre o bloqueio.
- **Saldo por faixa:** não existe, porque a faixa divide um registro em duas partes e o S1 é do registro inteiro. A faixa mostra só o valor inscrito.
- **Servidor da interface:** havia outro processo da interface aberto na porta 8050 (iniciado às 19h30, com o código anterior). Ele não foi encerrado; a verificação usou a porta 8051. Para ver a tela nova na 8050, é preciso reiniciar aquele processo.

## 7. O que não foi implementado

- 05.5 (investigação de variações), 05.6 (qualidade dos dados), 05.7.
- Concentração ou ranking por credor (fora do escopo): o tipo de credor é o único agrupamento de credor, sem nome nem documento.
- D1, coletas, automação e qualquer mudança em derivação, regras ou dados.
