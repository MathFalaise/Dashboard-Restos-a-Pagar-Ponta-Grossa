# Relatório da Subetapa 05.2 — evolução dentro do exercício

Data: 01/10/2026. Ramo `subetapa-05.2`, criado de `subetapa-05.1` (`8d22313`), sobre a base homologada `etapa-04-final` (`a6bd27c`). Contrato: `etapa05/CONTRATO_ANALITICO.md` (M-01 e M-02, seções 2 e 7). Plano: `etapa05/PLANO_ETAPA05.md`, seção 05.2.

**Resumo:**
- **Série completa:** `Painel.evolucao` lista **todos** os cortes processados do exercício para qualquer escopo (correção do R1).
  - Cada ponto tem situação, valores, retrato, rótulo do corte posterior à coleta (R4) e proveniência.
  - A diferença para o corte vizinho anterior (posterior − anterior) só existe quando os dois têm valor.
- **Tela `/evolucao`:** gráfico SVG gerado no servidor (lacuna desenhada como lacuna), tabela de valores exatos e tabela de diferenças.
- **Validação:** série do painel = série recalculada do JSON bruto (`recalculo_bruto.py`), ao centavo, em todos os pontos de 2025 e 2026, para o Município e as 10 entidades; tela = painel.
- **Testes:** **294/294** de produção (277 + 15 da 05.2 + 2 do atalho da raiz) e **26/26** da investigação. `verificar` sem problemas; `portoes` apto. Bruto, armazém, derivações e os 5.575 valores homologados da 04.6 idênticos.
- **Responsividade:** verificada em celular, tablet, notebook e desktop, sem nenhum estouro (seção 5). Dois ajustes de apresentação foram feitos durante a verificação.

---

## 1. O que mudou

| Arquivo | Mudança |
|---|---|
| `app/rp/painel/consulta.py` | `SITUACOES_DO_PONTO`: estende `SITUACOES_DO_DADO` com `municipio_indisponivel`, sem taxonomia paralela.<br>Constantes `TEM_VALOR`, `INDICADORES_DA_SERIE` e `ROTULO_POSTERIOR_A_COLETA`.<br>Função única `diferenca(anterior, posterior)` (sinal do contrato; `None` se algum lado falta).<br>`evolucao` reescrita: universo completo, situação do ponto, rótulos, diferença com proveniência dos dois lados e contagem das cópias 24xxxxx do exercício quando o escopo envolve as entidades 1 ou 15.<br>`metodologia` passa a listar `municipio_indisponivel` |
| `app/rp/interface/grafico.py` (novo) | gráfico de barras em SVG: sem `style`, `<style>` nem `<script>`; só geometria e classes; lacuna tracejada com "sem dado"; zero verdadeiro como linha "0"; cada barra é link interno para o corte; `<title>` e `<desc>` para leitor de tela |
| `app/rp/interface/paginas.py` | página `evolucao` (gráfico, tabela de valores, tabela de diferenças, aviso dos pares); item "Evolução no exercício" no menu; link a partir do Resumo; `_formulario` aceita formulário sem corte |
| `app/rp/interface/aplicacao.py` | rota `/evolucao` |
| `app/rp/interface/estilo.css` | classes do gráfico (cores das variáveis existentes; contraste igual ao homologado na 04.6) |
| `app/tests/test_serie_05_2.py` (novo) | 15 testes |
| `app/tests/test_contrato_05_1.py` | duas asserções que registravam o R1 como ainda aberto ("o painel atual omite o corte; correção na 05.2") passaram a exigir o comportamento corrigido |
| `app/README.md` | linha da 05.2 e a tela nova |
| `etapa05/RELATORIO_05_2.md`, `etapa05/resultados/05_2_*` | este relatório e as evidências |

**Sem mudança:** derivação, regras, esquema, snapshots, banco e configuração. A interface não faz conta: valores e diferenças vêm prontos da camada painel. O gráfico só converte valor em pixels (teste `test_grafico_nao_faz_aritmetica_de_valores_monetarios`).

## 2. Comportamento no dado real

| Escopo | Cortes | Situação |
|---|---|---|
| Município, 2025 | 6 | todos com valor; 5 diferenças |
| Município, 2026 | 7 | 31/01, 31/03 e 31/12 = "Município indisponível" ("corte não coletado para a(s) entidade(s) [4, 5, 8, 15]"); diferenças só em 30/06 e 31/08; as demais com o motivo |
| Entidades 4, 5, 8 e 15, 2026 | 7 (antes: 4) | 31/01, 31/03 e 31/12 = "corte não coletado" (R1 corrigido) |
| Entidade 1, 2026 | 7 | todos com valor; 31/12 rotulado "corte posterior à coleta" (R4) |
| Pares 24xxxxx | — | aviso com 731 cópias em 2026 e 20 em 2025 quando o escopo é o Município ou as entidades 1 e 15 |

**Critério de parada (inscrição variando dentro do exercício):** não acionado. A inscrição é igual em todos os cortes com valor de 2025 e 2026, em todos os escopos (`test_inscricao_estavel_dentro_do_exercicio`).

## 3. Testes novos (`test_serie_05_2.py`)

| Teste | O que garante |
|---|---|
| `test_SINTETICO_serie_tem_todos_os_cortes_e_lacuna_nunca_vira_zero` | universo completo; lacuna com situação e valores nulos; nenhuma diferença contra lacuna nem pulando lacuna; Município indisponível com motivo |
| `test_SINTETICO_diferenca_posterior_menos_anterior_com_proveniencia_dos_dois_lados` | sinal, valores e proveniência dos dois lados |
| `test_SINTETICO_zero_verdadeiro_e_corte_posterior_a_coleta` | zero verdadeiro (`sem_rp`) com valor 0; rótulo R4 só em ponto com valor |
| `test_SINTETICO_tela_mostra_lacunas_e_o_grafico_e_conforme` | CSP mantida; linhas de lacuna sem "R$"; SVG sem `style`, `<style>` ou `<script>`; links internos; uma barra por corte; lacuna e zero desenhados de forma distinta |
| `test_grafico_nao_faz_aritmetica_de_valores_monetarios` | nenhuma soma ou subtração de centavos no gráfico |
| `test_serie_do_painel_igual_a_recalculada_do_bruto` (2025, 2026) | painel = bruto em situação, valores e diferenças, para o Município e cada entidade |
| `test_lacunas_reais_de_2026` | lacunas reais do Município e das entidades 5 e 15; R4 da entidade 1 |
| `test_inscricao_estavel_dentro_do_exercicio` | critério de parada |
| `test_tela_igual_ao_painel` (4 escopos) | uma linha e uma barra por corte; valores e diferenças da tela = painel; lacunas sem valor; aviso dos pares |
| `test_metodologia_e_navegacao` | metodologia lista a nova situação; menu e link do Resumo |
| `test_desempenho_da_tela_de_evolucao` | menos de 3 s |

## 4. Validação

| Verificação | Resultado | Evidência |
|---|---|---|
| Suíte de produção | **294 passed** (inclui os 2 testes do atalho `rp.py` da raiz, commit `075b9f7`) | `resultados/05_2_testes_producao.txt` |
| Investigação | **26 passed** | `resultados/05_2_testes_investigacao.txt` |
| `verificar` | sem problemas | `resultados/05_2_verificar.txt` |
| `portoes` | apto | `resultados/05_2_portoes.json` |
| Bruto, armazém, derivações | idênticos (`hash_camada0` `733670693c01d015…`; `2f6b4e29…`, `b8a0b2ed…`; 466 manifestos e 375 objetos) | `resultados/05_2_comparacao_*.json` |
| Valores homologados | 0 diferenças na camada painel e nos 5.575 valores de tela (antes × depois e 04.6 × depois) | idem |
| Política de segurança no navegador | as cores das barras vêm de `estilo.css` (a CSP aceitou o SVG estilizado por classes) e as lacunas aparecem tracejadas, verificado no navegador embutido | — |

## 5. Responsividade (verificada)

Medida no navegador embutido, com a interface local, só para leitura, sobre o banco ativo (`resultados/05_2_responsividade.json`):

| Tamanho | Telas | Resultado |
|---|---|---|
| Celular 375 × 812 | evolução 2026 (Município e entidade 15), evolução 2025, Resumo, Metodologia | nenhum estouro de largura; nenhum elemento ou controle fora da tela; nenhuma fonte < 11 px; um `h1` por página, sem salto de título; gráfico de 351 px, menor texto 14 px; "sem dado" dentro da lacuna |
| Tablet 768 × 1024 | evolução 2026, entidade 1 | sem estouro; gráfico de 713 px; rótulo R4 presente |
| Notebook 1280 × 720 | evolução 2026, Município | sem estouro; gráfico de 820 px (largura máxima) |
| Desktop (largura do painel) | evolução 2025, entidade 15 | sem estouro; gráfico de 661 px |

Ajustes feitos durante a verificação, só de apresentação, sem efeito em valores:
- **Rótulo "sem dado":** passou a ocupar duas linhas. Com 7 cortes em 375 px, ele passava da borda da lacuna.
- **Célula "Situação":** mostra a forma curta (por exemplo, "Município indisponível"), com o texto completo como dica. O motivo detalhado já aparece na célula de valores. Em 375 px, as linhas chegavam a cerca de 200 px de altura; agora vão até 37 px.

Pendências do contrato que continuam fora da 05.2: `exercicio_sem_cobertura` e o corte representativo (05.3).

## 6. O que não foi implementado

- 05.3 (série entre exercícios), 05.4 (composição), 05.5 (investigação de variações), 05.6 (qualidade dos dados) e 05.7.
- Gráficos de outros indicadores. O gráfico da 05.2 responde à pergunta P1 para o saldo S1; os demais indicadores estão na tabela.
- D1, coletas, automação, CI e qualquer mudança em derivação, regras ou dados.
