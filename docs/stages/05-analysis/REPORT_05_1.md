# Relatório da Subetapa 05.1 — contrato analítico e base de validação

Data: 01/10/2026. Ramo `subetapa-05.1`, criado de `subetapa-05-planejamento` (`988a7cc`, plano aprovado), sobre a base homologada `etapa-04-final` (`a6bd27c`).

**Resumo:**
- **Contrato:** `docs/stages/05-analysis/ANALYTICAL_CONTRACT.md` fixa:
  - a disponibilidade dos dados (taxonomia única e precedência);
  - proveniência, validação em dois regimes, fechamento e sinal;
  - as 14 respostas de cada métrica de 05.2–05.5 (M-01 a M-12);
  - o regime de derivação das estruturas da 05.6 (E-01 a E-03), com o catálogo das 4 verificações reais;
  - a técnica de gráfico.
- **Validação independente:** `app/tests/recalculo_bruto.py` recalcula a partir do JSON bruto, sem usar a camada painel, a normalização nem a derivação. Reproduz `Painel.indicadores` ao centavo nos **181 pontos com valor** dos 22 cortes reais (Município e 10 entidades), e devolve valores nulos nos **61 pontos sem valor**, como o painel.
- **Testes:** 20 novos em `app/tests/test_contrato_05_1.py`. Suítes: **277/277** de produção (257 anteriores + 20) e **26/26** da investigação.
- **Código de produção:** nenhum alterado (plano, seção 05.1). Bruto, armazém, derivações e os 5.575 valores de tela homologados na 04.6 estão idênticos.

---

## 1. Estado inicial

| Item | Valor |
|---|---|
| Ramo de origem | `subetapa-05-planejamento` em `988a7cc` (plano revisado e aprovado; PR #4 aberto) |
| Base homologada | tag `etapa-04-final` → `a6bd27c` (intacta) |
| PRs #1–#4 | abertos, não mesclados. Pela decisão da seção 10 do plano, o ramo da 05.1 parte do ramo de planejamento |
| Estado de partida | capturado antes de qualquer arquivo novo; idêntico ao homologado na 04.6 (0 diferenças) |

## 2. O que foi implementado

| Arquivo | Finalidade |
|---|---|
| `docs/stages/05-analysis/ANALYTICAL_CONTRACT.md` (novo) | contrato de toda a Etapa 05 |
| `app/tests/recalculo_bruto.py` (novo) | ferramenta de recálculo independente (regime "bruto"):<br>• situação do dado, com a precedência do contrato;<br>• pontos de série e universo de cortes;<br>• diferença posterior − anterior;<br>• contribuições por empenho (S1 e pagamentos, com classes, grupos e ordem);<br>• fechamento ao centavo |
| `app/tests/test_contrato_05_1.py` (novo) | 20 testes da 05.1 |
| `docs/stages/05-analysis/REPORT_05_1.md` (novo) | este relatório |
| `docs/stages/05-analysis/results/05_1_*` (novos) | testes, `verificar`, `portoes` e comparações de estado |
| `app/README.md` | uma linha sobre a 05.1 |

### 2.1 Contratos estabelecidos

| Contrato | Seção do contrato | Estado |
|---|---|---|
| Taxonomia de disponibilidade: 6 situações existentes + `municipio_indisponivel` + `exercicio_sem_cobertura` (extensão de `SITUACOES_DO_DADO`, sem taxonomia paralela) | 2.1 | fixado; os dois códigos novos **a implementar** na 05.2 e na 05.3 |
| Precedência entre situações (entidade e Município) | 2.2 | fixada (decisão da 05.1; justificativa no contrato) |
| Representação de um ponto (valor `None` sem dado; nunca 0) | 2.3 | fixada; implementação na 05.2 |
| Universo de pontos de uma série (R1) | 2.4 | fixado; testado como representável no dado real |
| Corte representativo do exercício (R8) | 2.5 | fixado; implementação na 05.3 |
| Diferença só entre adjacentes (R9) | 2.6 | fixada; testada na ferramenta |
| Proveniência (formato existente `_prov_curta` / `_proveniencia`; dois lados nas diferenças) | 3 | fixada |
| Validação em dois regimes (bruto × derivação) | 4.1 | fixada |
| Fechamento: Σ componentes − total = 0, sem tolerância | 4.2 | fixado; testado |
| Métricas M-01 a M-12, cada uma com 14 respostas | 5 | fixadas; o teste confere as 14 respostas de cada uma |
| Anomalias, verificações e situação das diferenças (E-01 a E-03) | 6 | fixadas; o catálogo cobre as 4 descrições reais |
| Técnica de gráfico: SVG gerado no servidor, sem dependência nova | 7 | decidida; **nenhum gráfico implementado** |

### 2.2 Testes novos (`test_contrato_05_1.py`)

| Grupo | Testes |
|---|---|
| Disponibilidade (sintético) | cada situação de entidade igual no painel e na regra independente; Município indisponível nunca vira zero; exercício sem cobertura (e precedência `inexistente`); Município com zero verdadeiro |
| Série (sintético) | todos os cortes do exercício representados; lacuna com situação; diferença nunca contra lacuna |
| Contribuições e fechamento (sintético) | contribuição por situação da chave; fechamento por grupos, classes e linhas; ordem com desempate; chave duplicada bloqueia; par com lado sem valor; fechamento aprova só com diferença 0 e rejeita não inteiros |
| Independência | a ferramenta não importa `rp.*` e não contém regras de anomalia ou verificação |
| Documento | 14 respostas em cada métrica; taxonomia, regimes, gráfico, R1 e R4 presentes |
| Armazém real | recálculo = painel em todo ponto dos 22 cortes (181 com valor, 61 sem); universo da série e R1; R4; diferenças adjacentes; contribuições fecham e batem com os indicadores (2025 Município, 2026 entidade 1, par que salta a lacuna de 31/03/2026); catálogo das verificações reais |

## 3. Validação

| Verificação | Resultado | Evidência |
|---|---|---|
| Suíte de produção | **277 passed** | `resultados/05_1_testes_producao.txt` |
| Investigação da Etapa 03 | **26 passed** | `resultados/05_1_testes_investigacao.txt` |
| Homologação da Etapa 04 (`test_homologacao.py`, `test_homologacao_real.py`, `test_interface*`) | dentro da suíte de produção, sem nenhuma alteração nesses arquivos | idem |
| `python -m rp verificar` | sem problemas | `resultados/05_1_verificar.txt` |
| `python -m rp portoes` | apto | `resultados/05_1_portoes.json` |
| `PRAGMA integrity_check` | `ok` | comparação de estado |
| `hash_camada0` | `733670693c01d015…`, igual ao homologado | idem |
| Derivações 21–24 | `2f6b4e29…` e `b8a0b2ed…`, com os mesmos hashes de visão e conciliação | idem |
| Armazém | 466 manifestos e 375 objetos idênticos | idem |
| Valores homologados | 0 diferenças na camada painel e nos 5.575 valores de tela, antes × depois e 04.6 × depois | `resultados/05_1_comparacao_antes_depois.json`, `resultados/05_1_comparacao_com_homologacao_04_6.json` |
| Código de produção, regras, esquema | sem alteração (`git diff` vazio em `app/rp/`, `app/config.toml`, requisitos, testes existentes) | Git |

Os estados de partida e de chegada foram capturados com `docs/stages/04-pipeline/results/04_6_estado.py`. Os arquivos completos de estado ficaram fora do repositório (são idênticos ao homologado); as comparações foram guardadas.

## 4. O que não foi implementado

- 05.2 (série no exercício), 05.3 (série entre exercícios), 05.4 (composição), 05.5 (investigação de variações), 05.6 (qualidade e diferenças) e 05.7 (homologação da etapa).
- Os códigos `municipio_indisponivel` e `exercicio_sem_cobertura` na camada painel. Existem só no contrato e na ferramenta de validação.
- Qualquer gráfico, tela, filtro ou consulta nova.
- D1 (primeira atualização real), novas coletas, nova derivação, automação, CI, infraestrutura de produção, autenticação.
- Concentração ou ranking por credor.

## 5. Pendências

| # | Pendência | Onde se resolve |
|---|---|---|
| R1 | `Painel.evolucao(exercicio, entidade)` omite os cortes em que a entidade não tem snapshot. Em 2026, as entidades 5 e 15 aparecem em 4 cortes e 31/01, 31/03 e 31/12 somem. A 05.1 testou que todo ponto é **representável** (`cortes()` + `entidades_do_corte()`) e que a ferramenta lista os 7 cortes; o painel continua com o R1 | 05.2 (correção funcional e homologação) |
| R4 | 31/12/2026 da entidade 1 é posterior à coleta. O painel já marca `corte_posterior_a_coleta`; falta o rótulo na série | 05.2 |
| — | Cortes só coletados, sem processamento, não entram no universo da série (contrato, seção 2.4). Em base disponibilizada isso não ocorre (portão `normalizacao`) | registrado no contrato; sem ação |
| — | O par de cortes do Município com conjuntos de entidades diferentes (R6) não ocorre dentro de um mesmo exercício quando os dois pontos têm valor: a disponibilidade já exige todas as entidades do catálogo. A verificação continua no contrato como defesa | sem ação |

Nenhuma ambiguidade do plano impediu a 05.1. A precedência entre situações (contrato, seção 2.2) foi fixada aqui, porque o plano atribui à 05.1 "fixar a regra de disponibilidade", e está justificada no contrato.

## 6. Dependências para 05.2 em diante

- **Ferramenta de validação:**
  - 05.2 usa `Bruto.serie`;
  - 05.3 usa `Bruto.ponto` no corte representativo (a escolha do corte vem com a 05.3);
  - 05.4 precisa de agrupamentos do bruto por categoria, faixa, tipo de credor e dimensão: a acrescentar na 05.4, seguindo o mesmo regime;
  - 05.5 usa `Bruto.contribuicoes`.
- **Taxonomia:** os códigos novos entram na camada painel na 05.2 (`municipio_indisponivel`) e na 05.3 (`exercicio_sem_cobertura`), estendendo `SITUACOES_DO_DADO`.
- **Pagamentos:** a expressão de pagamentos (`pago_proc_c + pago_aproc_c`) vira constante única na camada painel na 05.5 (contrato, M-09).
- **Primeiro gráfico (05.2):** traz o teste de conformidade do SVG previsto no contrato (seção 7).
- **Integração:** recomenda-se mesclar os PRs #1 → #4 antes do PR da 05.1 (plano, seção 10; não bloqueante).
