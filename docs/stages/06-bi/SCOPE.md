# Etapa 06 — Visão geral (BI): escopo

Pedido do responsável (07/10/2026): "uma espécie de BI com os dados, visual limpo, leitura fácil, textos só os
importantes, evolução no exercício e entre exercícios, gráficos de leitura usual (pizza, colunas verticais)".
O problema a resolver é a **transmissão do dado**: as telas atuais são exatas e auditáveis, mas densas.

## 1. Objetivo

Uma página nova, **Visão geral**, a página inicial da interface, que responde em poucos segundos, para qualquer leitor:

1. Quanto o Município deixou de Restos a Pagar para este exercício? Quanto já foi pago, cancelado e quanto ainda
   está em aberto?
2. Como esse saldo caiu ao longo do exercício, mês a mês?
3. Como os Restos a Pagar evoluíram de um exercício para o outro (2016 a 2026)?
4. De quem é e para onde vai o saldo em aberto (entidade, tipo de despesa, fonte do recurso, credor)?

As telas atuais continuam como estão: são a camada de detalhe e de auditoria. Cada gráfico da Visão geral leva a
elas ("ver detalhes").

## 2. Princípios (não negociáveis, herdados das etapas 04 e 05)

| Princípio | Como a Visão geral cumpre |
|---|---|
| Valor principal = API Elotech; nada recalculado na interface | Todos os números vêm de um método novo da camada painel; a interface só desenha e formata |
| Partição só se fecha ao centavo | Toda pizza só é desenhada se as fatias somarem exatamente o total (`fechamento`); senão, o gráfico não aparece e o motivo é dito |
| Pizza não mostra negativo | Se alguma fatia for negativa, a pizza dá lugar a colunas, com o motivo |
| Lacuna nunca é zero | Corte sem valor aparece como lacuna ("sem dado") nas colunas, como hoje |
| Percentuais exatos na leitura | Percentuais com 1 casa, arredondados pelo maior resto: a legenda soma exatamente 100,0% |
| Sem JavaScript, sem recurso externo, CSP estrita | Gráficos em SVG gerado no servidor (como o gráfico atual); dica ao passar o mouse por `<title>` do SVG |
| Nível público | Só agregados; nenhum nome ou documento de credor |
| Acessibilidade | Cada gráfico com título e descrição para leitor de tela e a tabela de valores exatos num bloco recolhido |
| Proveniência ao alcance | "Origem do dado" recolhida em cada bloco, igual às outras telas |

## 3. Conteúdo da página `/` (Visão geral)

Seleção no topo: exercício, corte (padrão: o mais recente com o Município completo) e escopo (Município ou uma
entidade). Os mesmos parâmetros das outras telas.

| Bloco | Pergunta | Gráfico | Dados (camada painel) |
|---|---|---|---|
| B1 Números-chave | Quanto? | 4 cartões grandes: inscrito na abertura, pago até o corte, cancelado até o corte, saldo em aberto; mais "% do inscrito já pago" | `indicadores` |
| B2 Destino do inscrito | O que aconteceu com o que foi inscrito? | Pizza (rosca): pago · cancelado · em aberto | identidade S1: inscrito = pago + cancelado + saldo, conferida no corte |
| B3 Situação do saldo | O que falta fazer com o saldo? | Pizza: a liquidar (S2) · liquidado a pagar (S3) | S1 = S2 + S3, conferida |
| B4 Evolução no exercício | Como o saldo caiu? | Colunas verticais por corte (mensal): saldo em aberto; segunda série: pago acumulado | `evolucao` |
| B5 Entre exercícios | Está crescendo ou diminuindo? | Colunas verticais por exercício: inscrito na abertura e saldo no fechamento | `serie_entre_exercicios` |
| B6 Por entidade | De quem é o saldo? | Pizza por entidade (nomes do catálogo da API) | `entidades_do_corte` |
| B7 Processado x não processado | Que tipo de dívida? | Pizza por categoria | `composicao` (categoria) |
| B8 Fonte do recurso | Com que dinheiro será pago? | Pizza: 6 maiores fontes + "demais" | `composicao` (fonte de recurso, descrição da API) |
| B9 Credor | Para quem? | Pizza: pessoa jurídica · pessoa física · não identificado | `composicao` (tipo de credor) |
| B10 Área de governo | Em que área? | Pizza: 8 maiores funções + "demais", com o nome oficial | `composicao` (função) + Portaria MOG nº 42/1999 |

Textos: um título em forma de pergunta e uma linha de leitura por gráfico ("R$ 78,7 mi ainda em aberto, 38% do
inscrito"). Valores grandes abreviados (R$ 78,7 mi) nos gráficos e cartões; o valor exato aparece na dica e na
tabela recolhida.

## 4. Implementação

1. **Camada painel** (`rp/painel/consulta/visao.py`, mixin novo): `Painel.visao_geral(exercicio, data_final,
   entidade, em)` monta os blocos a partir dos métodos existentes e acrescenta só:
   - as partições B2/B3 com `fechamento` (se não fechar, o bloco vem indisponível com o motivo);
   - percentuais por maior resto (inteiros em décimos de ponto percentual, soma = 1000);
   - o agrupamento "demais" (soma dos grupos fora do topo, conferida com `fechamento` contra o total).
2. **Gráficos** (`rp/interface/grafico.py`): `pizza` (rosca SVG, fatias por arco, legenda com valor e %) e
   `colunas` (verticais, uma ou duas séries, lacuna tracejada), no padrão do gráfico de barras atual.
3. **Tela** (`rp/interface/paginas/tela_visao.py`) na rota `/`, primeiro item do menu; o resumo completo do corte
   passa para `/resumo` (menu "Resumo do corte"), e os links que levavam ao resumo apontam para lá.
4. **Estilo**: paleta de 8 cores distinguíveis por daltônicos, no tema escuro atual; layout em grade de cartões,
   2 colunas no computador e 1 no celular.

## 5. Provas (critério de pronto)

- Cada valor desenhado está num `<data value>` igual ao da camada painel (ferramenta 05.7 estendida a `/`).
- B2, B3 e as pizzas de composição recalculadas de forma independente a partir do JSON bruto (`recalculo_bruto`),
  ao centavo, em todos os cortes.
- Percentuais: soma 100,0% em toda pizza; nenhum valor negativo desenhado em pizza.
- Testes novos para a camada (`visao_geral`) e para os gráficos (geometria, lacuna, zero, negativo).
- Acessibilidade (ferramenta 05.7) sem problemas, incluindo `/` e `/resumo`.
- As outras telas não mudam (só o item novo no menu): conferido pelo rastreamento das 2.500 páginas, com o menu
  normalizado.
- 509 testes atuais + os novos passam; `verificar` e portões aptos (nada no banco muda).

## 6. Decisões do responsável (07/10/2026)

- A Visão geral **vira a página inicial** (`/`); o resumo atual muda para `/resumo`. Os testes homologados que pediam
  o resumo em `/` passam a pedi-lo em `/resumo` (mesmas asserções), e as listas de rotas dos testes gerais (sem rede,
  somente leitura, desempenho, nada experimental na tela) incluem a `/`.
- Área de governo com os **nomes oficiais** da Portaria MOG nº 42, de 14/04/1999 (anexo de funções e subfunções),
  conferidos em 07/10/2026 na reprodução do anexo pela SEF/SC; fonte de referência fora da API, citada na tela e em
  `rp/painel/classificacao.py`. Código fora da tabela mantém o código (nunca um nome adivinhado).

## 7. Fora do escopo

Interatividade com JavaScript, exportação (PDF/Excel), dados novos (coleta), mudanças nas telas existentes além do
menu, nomes de órgão (a API só traz o código).
