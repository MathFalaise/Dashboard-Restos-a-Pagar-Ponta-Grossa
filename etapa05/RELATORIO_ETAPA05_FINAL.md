# Relatório final da Etapa 05 — da base homologada a um dashboard analítico

Data: 02/10/2026. Subetapa 05.7 (homologação e encerramento), ramo `subetapa-05.7`, criado de `subetapa-05.6` (`3e60c57`). Base homologada de partida: `etapa-04-final` (`a6bd27c`).

- **Plano:** `etapa05/PLANO_ETAPA05.md` (versão final `988a7cc`, com as decisões da seção 10).
- **Contrato:** `etapa05/CONTRATO_ANALITICO.md` (05.1).
- **Relatórios por subetapa:** `etapa05/RELATORIO_05_1.md` a `RELATORIO_05_6.md`.

**Resumo:** a Etapa 05 respondeu às perguntas do plano com seis telas novas, todas apoiadas na camada painel. A interface não calcula, e nenhum dado, regra ou derivação mudou.

| Tela | Pergunta |
|---|---|
| Evolução no exercício | P1 |
| Série entre exercícios | P2, P5, P7 |
| Composição do saldo | P3, P4 |
| Variação entre cortes | P6 |
| Empenho nos cortes | P8 |
| Qualidade dos dados | P9, P12 |

- **Base:** snapshots, normalização, derivação, `hash_resultado` (`2f6b4e29…`, `b8a0b2ed…`) e `hash_camada0` são os da `etapa-04-final`, e os 5.575 valores de tela homologados na 04.6 continuam idênticos.
- **Telas novas:** 100.201 valores conferidos, todos iguais à camada painel.
- **Testes:** **348** de produção (257 na `etapa-04-final`) e **26** da investigação, passando no ambiente ativo e numa instalação limpa.
- **Os 14 critérios de encerramento** do plano (seção 17) estão cumpridos (seção 4). A tag `etapa-05-final` foi criada **localmente**, sem envio ao GitHub.

---

## 1. Evolução 05.1 → 05.7

| Subetapa | Commit(s) | Entrega |
|---|---|---|
| Plano | `01dc272`, `89d6092`, `988a7cc` | plano v1, v2 e revisão final com as decisões da seção 10 |
| 05.1 | `8d22313` | contrato analítico (M-01 a M-12, E-01 a E-03), validação independente a partir do JSON bruto (`tests/recalculo_bruto.py`); sem código de produção |
| 05.2 | `eac9b4d`, `075b9f7`, `fa3f1c7` | evolução no exercício (`/evolucao`), com todos os cortes (R1), lacunas, diferenças entre vizinhos e gráfico SVG gerado no servidor; atalho `rp.py` na raiz |
| 05.3 | `6ab3dab` | série entre exercícios (`/historico`) no corte representativo (R8), com o retrato em todo ponto; fechamento × abertura pela FAIXA v1 (R2, R7); continuidade da derivação |
| 05.4 | `feca7b7` | composição do saldo (`/composicao`) em 8 dimensões, com fechamento por dimensão (a que não fecha não é exibida), faixa só em valores (R3), "sem classificação" e ligação de cada grupo à lista de empenhos |
| 05.5 | `017b2b2` | investigação de variações (`/variacao`): contribuição de cada empenho para a variação de S1 ou de pagamentos entre dois cortes, com fechamento ao centavo; empenho em todos os cortes (`/empenho/cortes`) |
| 05.6 | `3e60c57` | qualidade dos dados (`/qualidade`): anomalias por tipo e ocorrências, verificações interpretadas pela descrição (R5), as cinco situações das diferenças com o RREO |
| 05.7 | este commit | homologação final: regressão, estado, telas novas conferidas, acessibilidade, sem rede, instalação limpa, este relatório e a tag |

## 2. Arquitetura preservada

```text
API Elotech → coleta → snapshot imutável → normalização → derivação (camada 2)
      ↓
CAMADA PAINEL (rp/painel): consultas somente leitura; toda métrica nova, com natureza, regra, retrato, situação e proveniência
      ↓
INTERFACE (rp/interface): só apresenta; teste da 04.6 proíbe aritmética em centavos e sum()
```

- **Métricas novas:** só na camada painel, sobre a camada 2 existente. Expressão repetida virou constante única (`EXPR_PAGAMENTOS` na 05.5, ao lado de `EXPR_CANCELAMENTOS`).
- **Consulta de agrupamento:** uma só (`_por_grupo`, 05.4).
- **Regra de diferença:** uma só (`diferenca`, 05.2).
- **Fechamento:** um só (`fechamento`, 05.4), sem tolerância.
- **Anomalias e verificações:** só lidas da derivação (regime "derivação"); nenhuma regra reimplementada.
- **Interface:** sem JavaScript, CSP `default-src 'none'; style-src 'self'`, sem recurso externo. Gráficos em SVG gerado no servidor (decisão da 05.1), com tabela de valores exatos sempre presente.

## 3. Validação final (executada na 05.7)

| Verificação | Resultado | Evidência |
|---|---|---|
| Suíte de produção (ambiente ativo) | **348 passed** | `resultados/05_7_testes_producao.txt` |
| Investigação (ambiente ativo) | **26 passed** | `resultados/05_7_testes_investigacao.txt` |
| `verificar` | sem problemas | `resultados/05_7_verificar.txt` |
| `portoes` | apto | `resultados/05_7_portoes.json` |
| Estado × `etapa-04-final` (homologação 04.6) | bruto, armazém e derivações idênticos; 0 diferenças nos valores da camada painel e nos 5.575 valores de tela | `resultados/05_7_comparacao_com_homologacao_04_6.json` |
| Estado × fim da 05.6 | idem | `resultados/05_7_comparacao_antes_depois.json` |
| Valores das telas novas × camada painel | 1.815 páginas (todas as telas da Etapa 05, em todos os escopos e cortes, e todos os pares da variação), **100.201 valores**: 0 ausentes, 0 diferentes, 0 sem conferência; todas com status 200 | `resultados/05_7_telas_novas.json` (`05_7_telas_novas.py`) |
| Acessibilidade básica e ausência de recurso externo | 38 páginas (todas as telas e as de erro), 0 problemas | `resultados/05_7_acessibilidade.json` (`05_7_acessibilidade.py`) |
| Sem rede (toda conexão de saída bloqueada) | 25 visitas com o status esperado; **0** tentativas de conexão de saída | `resultados/05_7_percurso_sem_rede.json`, `05_7_sem_rede_registro.jsonl` (vazio) |
| Responsividade | por tela em celular, tablet, notebook e painel do app nas subetapas; varredura final em 375 px sem estouro | `resultados/05_2_` a `05_7_responsividade.json` |
| Instalação limpa | cópia fora do OneDrive, ambiente Python novo; mesmos hashes; `verificar` e `portoes` ok; acessibilidade 0 problemas; 348 + 26 testes, sem nenhum aviso | `resultados/05_7_instalacao_limpa.txt` |

**O que a conferência das telas novas cobre** (`05_7_telas_novas.py`): para cada página, monta o valor esperado de cada `<data id value>` a partir da camada painel e confere três coisas:
- todo id esperado está na tela;
- todo valor exibido é igual ao esperado;
- todo id exibido foi conferido.

As páginas cobertas são:
- evolução: 2025 e 2026 × 11 escopos;
- série: 11 escopos;
- composição: as 8 dimensões em cada um dos 181 recortes com valor, e os 61 sem valor;
- variação: os 264 pares × escopos × métricas;
- empenho nos cortes: os 4 casos do plano;
- qualidade: a página geral e a de cada tipo de anomalia.

A igualdade da camada painel com o JSON bruto foi verificada nas subetapas pelos testes de recálculo independente.

## 4. Critério de encerramento (plano, seção 17)

| # | Critério | Situação | Onde é verificado |
|---|---|---|---|
| 1 | **P1/P2:** séries com todo o universo de pontos; diferenças só entre vizinhos com valor; ponto com valor igual entre bruto, painel e tela; ponto sem valor com a situação, nunca R$ 0,00 nem ausente; retrato verificado em todo ponto histórico | cumprido | `test_serie_05_2.py`, `test_historico_05_3.py`; 05.7: telas = painel |
| 2 | **P3/P4:** cada composição exibida fecha sozinha com o total do corte; dimensão que não fecha não é exibida; faixa como "composição dos registros da API segundo a regra FAIXA v1" | cumprido: 8 dimensões fecham nos 181 recortes; bloqueio coberto por teste sintético | `test_composicao_05_4.py` |
| 3 | **P6:** contribuições fecham a variação, por grupos e por classe, com sinal; chave duplicada ou escopo incompatível bloqueados com motivo | cumprido: 144 combinações disponíveis, todas iguais ao bruto | `test_variacao_05_5.py` |
| 4 | **P7:** fechamento × abertura = S1(A) × (a)+(f)(A+1) pela FAIXA v1 no corte representativo, como diferença e verificação; R7 no Município | cumprido: diferença 0 nas 10 transições | `test_historico_05_3.py` |
| 5 | **P9:** "sem diferença" separado das quatro situações de explicação; contagens iguais às da reconciliação | cumprido | `test_qualidade_05_6.py` |
| 6 | **P12:** anomalias e verificações validadas segundo a natureza; drill-down só com chave; verificações como conjunto | cumprido | `test_qualidade_05_6.py` |
| 7 | toda métrica nova no contrato com as 14 respostas e validada por recálculo independente | cumprido (M-01 a M-12) | `CONTRATO_ANALITICO.md`; testes `*_bruto*` de cada subetapa |
| 8 | nenhum indicador com regra experimental ou não recomendada; nenhuma consolidação dos pares 24xxxxx; nenhuma "hipótese" ou "não determinada" como explicada | cumprido | `_regras_publicaveis`; aviso dos pares em toda tela que os envolve; situações separadas (05.6) |
| 9 | interface sem cálculo contábil (teste da 04.6) | cumprido | `test_homologacao.py::test_interface_nao_soma_nem_subtrai_valores_monetarios` |
| 10 | suítes passando, `verificar` limpo, `portoes` apto | cumprido | seção 3 |
| 11 | snapshots, normalização, derivação, `hash_resultado` e `hash_camada0` iguais aos da `etapa-04-final`; valores da 04.6 inalterados | cumprido | `05_7_comparacao_com_homologacao_04_6.json` |
| 12 | telas novas verificadas em celular, tablet, notebook e desktop, com acessibilidade básica e sem rede; instalação limpa repetida | cumprido | seção 3 |
| 13 | relatório final com as limitações abertas; tag `etapa-05-final` | cumprido: este relatório; tag criada localmente (seção 7) | — |
| 14 | nada da seção 8 implementado sem decisão expressa | cumprido: sem D1, sem coleta, sem automação, sem CI, sem ranking por credor, sem consolidação dos pares | — |

**Pré-requisito da 05.7 (plano):** relatórios de 05.1 a 05.6 aprovados.
- A 05.1 e o plano foram aprovados.
- A 05.2 e a 05.3 seguiram o fluxo de aprovação.
- As subetapas 05.4 a 05.7 foram executadas em sequência, a pedido do responsável, em 01–02/10/2026. Cada uma tem relatório próprio e os seus critérios cumpridos, mas **a aprovação formal dos relatórios 05.4 a 05.6 e deste relatório fica com o responsável**.

## 5. Decisões e limitações abertas

**D1 (primeira atualização real da base): não executada.**
- O plano (seção 10) a deixou fora do caminho crítico, a decidir antes da 05.7.
- Não houve decisão de executá-la, e a Etapa 05 foi homologada sobre a base da 04.6 (coletas de 29–30/09/2026).
- Se for feita, entra como subetapa própria, pelo procedimento do `app/README.md`. As comparações de estado devem ser refeitas, tratando a mudança de valores como efeito da coleta.

**Limitações dos dados e das fontes** (continuam as da Etapa 04, `RELATORIO_ETAPA04_FINAL.md`, seção 8):
- natureza das cópias 24xxxxx não determinada (pedido e-SIC em rascunho, a enviar pelo responsável);
- RREOs de 2016 (entidade), 2018 e 2019 não lidos pelo extrator;
- diferenças com o RREO "não determinadas": 66 (RREO-COL v1) e 91 (v2) colunas;
- base retroativa: cortes antigos refletem o estado atual da base, não o da época;
- corte 31/12/2026 da entidade 1 posterior à coleta.

**Limitações e observações da Etapa 05:**
- **Anomalias por snapshot:** a derivação grava as anomalias por registro em todo snapshot processado, inclusive retratos anteriores e coletas por tipo de pesquisa. A tela mostra a contagem da derivação e quantas estão nos vigentes, e a ligação ao registro só é exata no vigente.
- **Verificação fora do catálogo:** a derivação pode gravar "RREO sem snapshot da API no mesmo corte" (hoje 0 itens), que não está no catálogo E-02. Se aparecer, sai como "significado não catalogado" até uma revisão do contrato.
- **Variação de um lado só:** nenhum par real tem chave presente só num corte, porque os registros são iguais dentro do exercício. Essas classes estão cobertas por testes sintéticos.
- **Gráficos:** só na evolução e na série (05.2, 05.3). A composição, a variação e a qualidade ficaram só com tabelas, por decisão registrada nas subetapas: com 150 fontes ou 69 programas, um gráfico não seria legível em 375 px.
- **Cabeçalho no celular:** com 12 itens no menu, o topo ocupa 229 px de altura em 375 px, sem estouro. Sugestão: menu recolhível sem JavaScript.
- **Resumo:** a tabela "Conferência com o RREO" (04.6) tem uma linha de 148 px em 375 px, sem estouro.
- **Ambiente:** só Windows com Python 3.14.3 comprovados; sem CI; testes executados à mão.
- **Instalação no Windows em pasta profunda:** a primeira instalação limpa da 05.7, numa pasta temporária muito profunda, teve 1 aviso. O caminho de uma biblioteca nativa do `charset_normalizer`, dependência do `requests`, passava de 260 caracteres. Com caminho curto, o aviso desaparece. O `app/README.md` passou a recomendar pasta de caminho curto, e o diagnóstico está em `05_7_instalacao_limpa.txt`.

## 6. Pendências para o futuro

- **Aprovação:** dos relatórios 05.4, 05.5, 05.6 e deste.
- **Pull requests:**
  - os PRs #1 a #8 continuam abertos (ordem de mesclagem #1 → #8);
  - os ramos `subetapa-05.5`, `subetapa-05.6` e `subetapa-05.7` estão só na cópia local, sem envio nem PR;
  - a tag `etapa-05-final` também é local.
- **D1:** decidir se e quando fazer a primeira atualização real da base (seção 5).
- **e-SIC:** enviar o pedido (pelo responsável) e, com a resposta, seguir a seção 16.3 do plano.
- **Antes de qualquer publicação externa:** os itens da seção 16.4 do plano (servidor de produção, HTTPS, controle de acesso, dados pessoais no repositório, licença do PyMuPDF).
- **Servidor da interface na porta 8050:** o processo iniciado em 01/10 às 19h30 ainda roda o código anterior à 05.4. Para ver as telas novas, é preciso reiniciá-lo (`python -m rp interface`).

## 7. Ponto de restauração

- **Tag local:** `etapa-05-final`, anotada, aponta para o commit da 05.7. Nada foi enviado ao GitHub.
- **Envio:** só a pedido, com `git push origin subetapa-05.5 subetapa-05.6 subetapa-05.7 etapa-05-final`, depois dos PRs anteriores.
- **Tag anterior:** `etapa-04-final` não foi alterada.
