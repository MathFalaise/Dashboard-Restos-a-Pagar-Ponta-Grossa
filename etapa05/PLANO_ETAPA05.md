# Plano da Etapa 05 — da base homologada a um dashboard analítico

Data: 01/10/2026. Ramo `subetapa-05-planejamento`, criado da tag `etapa-04-final` (`a6bd27c`).

**Situação: proposta revisada, para aprovação.** Nada da Etapa 05 foi implementado. Este plano não altera código, banco, snapshots, regras, fórmulas nem interface.

- **Versão 1:** commit `01dc272`.
- **Versão 2:** esta. Incorpora a revisão pedida pelo responsável e os problemas encontrados ao conferir o plano contra o código da tag; o registro das correções está na seção 18.

Ordem de prioridade que orienta o plano:

**dados corretos → proveniência → validação → utilidade → apresentação.**

---

## 1. Objetivo da Etapa 05

Fazer o dashboard responder perguntas analíticas que hoje ele não responde, sem perder nenhuma das garantias homologadas na Etapa 04.

As perguntas centrais são:
- como os Restos a Pagar evoluem dentro de um exercício e ao longo dos exercícios;
- do que o saldo é composto;
- quais empenhos explicam uma variação;
- o que o projeto sabe e não sabe sobre a qualidade dos dados e as diferenças com o RREO.

Tudo isso com dados que já foram coletados, regras que já são operacionais e a mesma cadeia de proveniência até o objeto bruto.

**A Etapa 05 não é:** uma etapa de novas coletas, nem de automação, nem de publicação externa, nem de novas regras contábeis (seção 8).

## 2. Estado de partida

| Item | Valor |
|---|---|
| Ponto de restauração | tag `etapa-04-final` → `a6bd27c` (publicada no GitHub) |
| Integração no `main` | PRs #1 (04.5), #2 (04.6) e #3 (04.7) abertos e não mesclados; PR #4 (versão 1 deste plano) aberto; `origin/main` em `adc7510` |
| Testes | 257/257 de produção e 26/26 da investigação |
| Verificação e portões | `verificar` sem problemas; `portoes` apto |
| Banco | 466 snapshots; normalização 13 (228.873 registros); derivações 23 (atual, `2f6b4e29…`) e 24 (29/09, `b8a0b2ed…`) |
| Data dos dados | todos os cortes vigentes foram coletados entre 29/09/2026 20h11 e 30/09/2026 01h22 |

Fontes: `etapa04/RELATORIO_ETAPA04_FINAL.md`, o código da tag e as medições somente leitura feitas para este plano (seção 5.4).

## 3. O que a Etapa 04 entregou

- **Pipeline:** API Elotech → coletor → snapshot imutável → normalização → derivação → painel → interface. A trilha separada do RREO (snapshot → extração → reconciliação) nunca substitui o valor da API.
- **Camada de consulta:** `app/rp/painel`, somente leitura. Todo valor sai com natureza (`da_fonte`, `publicado`, `derivado`, `analitico`, `diferenca`), regra e sua situação de governança, rótulo de retrato e proveniência até o objeto bruto.
- **Situação do dado:** `consulta.SITUACOES_DO_DADO`, com 7 situações:
  - `com_dados`, `sem_rp` (o único zero verdadeiro);
  - `inexistente`, `sem_coleta`, `nao_processado`, `incompleto` (sem valor);
  - `divergente` (com o RREO).
- **Interface:** `app/rp/interface`, WSGI da biblioteca padrão, sem JavaScript, CSP `default-src 'none'`.
  - Homologada com bruto = painel = tela.
  - Um teste proíbe soma ou subtração de valores em centavos na interface (`test_interface_nao_soma_nem_subtrai_valores_monetarios`).
- **Operação:** reconstrução a partir de `snapshots/`, procedimento de atualização documentado, `python -m rp portoes` e instalação limpa comprovada (Windows, Python 3.14.3).

## 4. O que a Etapa 05 pretende resolver

Perguntas que o usuário precisa responder e que **hoje a interface não responde**, avaliadas contra os dados e o código existentes:

| # | Pergunta | Responde hoje? | Dados e código disponíveis | Conclusão |
|---|---|---|---|---|
| P1 | Como saldo, pagamentos e cancelamentos evoluem **dentro** do exercício? | não | 2025: 6 cortes; 2026: 7 cortes, com Município disponível em 4. `Painel.evolucao` existe, mas omite os cortes em que uma entidade não foi coletada (seção 18, R1) | respondível com os dados atuais, **depois de corrigir a enumeração de cortes da série** |
| P2 | Como os RP evoluem **ao longo dos exercícios** (2016–2026)? | não | um corte de fechamento (31/12) por exercício em 2016–2024; 2025 completo; 2026 aberto | respondível, sempre como estado atual da base |
| P3 | Quanto da inscrição e do saldo é de cada categoria e faixa? | não | CAT v1 e FAIXA v1 (operacionais) por registro; `indicadores.categorias` já calculado e não exibido | respondível |
| P4 | Como o saldo se distribui por fonte de recurso, função, programa, órgão e elemento? | não | `Painel.por_dimensao`; 16 registros sem classificação orçamentária em 2025-12-31 | respondível, com "sem classificação" explícito |
| P5 | Como as entidades se comparam ao longo do tempo? | só num corte (tela Entidades) | as mesmas séries de P1 e P2 por entidade | respondível, com aviso dos pares 24xxxxx (seção 12) |
| P6 | Quais empenhos explicam a variação entre dois cortes do mesmo exercício? | não | mesmos registros (chave entidade/ano/empenho) em cortes diferentes; CHAVE-DUP = 0 na derivação atual | respondível com consulta nova (seção 9, 05.5) |
| P7 | O saldo que fecha A é o que abre A+1 na API? | em parte: a tela de coerência mostra "API hoje: S1 de A" ao lado de "API hoje: (a)+(f) de A+1", só para os escopos com RREO | S1 v1 e FAIXA v1 (operacionais); verificação ANOM-CONT v1 por entidade e ano (100 itens, 0 falhas) | respondível para todo escopo como diferença e verificação, **não** como "saldo final de A × inscrição de A+1" (seção 18, R2) |
| P8 | Como um empenho evoluiu através dos cortes? | parcial: detalhe num corte; movimentação de só 147 empenhos | o registro do empenho em cada corte em que aparece | respondível (valores por corte); a movimentação completa exigiria coleta nova |
| P9 | Quais diferenças com o RREO continuam, e em que situação? | parcial: por documento | `conciliacao_rreo`, `explicacoes.py`, coerência | respondível como resumo, separando "sem diferença" das situações de explicação |
| P10 | O que mudou entre dois retratos do mesmo corte? | sim (comparador) | os 28 cortes com mais de um retrato têm bytes idênticos | já existe; não há caso real até haver coleta nova |
| P11 | Quais credores concentram o saldo? | não | identificação só no nível interno; a 04.5 vedou ranking e tela pública de fornecedores | fora: decisão de governança (seção 8) |
| P12 | Quais anomalias e verificações a derivação registrou? | não | tabelas `anomalia` e `verificacao` da derivação, fora da camada de consulta | respondível, cada uma segundo sua natureza (seção 9, 05.6) |

## 5. Inventário do que já existe

### 5.1 Dados (camada `rp/painel` × interface)

| Capacidade | Classificação | Observação |
|---|---|---|
| Indicadores do corte (13) | **EXIBIDO** | homologados bruto = painel = tela |
| Estornos de pagamento | EXISTE NA CAMADA, NÃO EXIBIDO | informativo; já descontado dos pagamentos |
| Categorias no indicador (`indicadores.categorias`) | EXISTE NA CAMADA, NÃO EXIBIDO | CAT v1 operacional |
| Reconciliação por indicador (`reconciliacao_rreo`) | EXISTE NA CAMADA, NÃO EXIBIDO | a tela mostra só a conferência S1 × L |
| Empenhos (lista, filtros, totais, detalhe) | **EXIBIDO** | o detalhe mostra todas as ocorrências quando a chave se repete |
| Entidades do corte | **EXIBIDO** | 7 situações do dado |
| Catálogo histórico (períodos oficiais por entidade) | EXISTE PARCIALMENTE | `Painel.entidades`; a tela só usa os nomes |
| Evolução no exercício (`evolucao`) | EXISTE NA CAMADA, NÃO EXIBIDO | para uma entidade, só lista os cortes em que ela tem snapshot (seção 18, R1) |
| Dimensões (`por_dimensao`, 12) | EXISTE NA CAMADA, NÃO EXIBIDO | o agrupamento inclui o grupo nulo; a interface usa só para listar fontes de recurso |
| Fornecedores, nível público (por tipo de credor) | EXISTE NA CAMADA, NÃO EXIBIDO | só pessoa jurídica, pessoa física e não identificado |
| Fornecedores identificados (nível interno) | NÃO RECOMENDADO (público) | governança de dados pessoais |
| Pares espelhados (PAR-24 v1) | **EXIBIDO** | área técnica |
| Visão analítica CONS-PAR v1/v2 | **EXPERIMENTAL** | não exibida, por decisão |
| Retratos e comparação de retratos | **EXIBIDO** | nenhum caso real de mudança |
| Reconciliação com o RREO | **EXIBIDO** | RREO-COL v1 NÃO RECOMENDADO e v2 EXPERIMENTAL, rotuladas como análise |
| Coerência entre publicações | **EXIBIDO** | inclui "API hoje: S1 de A" e "API hoje: (a)+(f) de A+1" só para os escopos com RREO |
| Situação das diferenças | EXIBIDO por linha | "sem diferença" é atribuída pela camada painel quando `diferenca_c == 0`; as demais saem de `explicacoes.resumo` (explicada, parcialmente explicada, hipótese, não determinada). Não há resumo por situação |
| Regras e governança | **EXIBIDO** | metodologia |
| Evidências externas | EXISTE NA CAMADA, NÃO EXIBIDO | 0 registros |
| Fontes, metodologia, dicionário | **EXIBIDO** | |
| Movimentação de empenho | EXISTE PARCIALMENTE | 147 empenhos (145 da entidade 1) |
| Anomalias da derivação (`anomalia`) | NÃO EXISTE na camada | uma linha por ocorrência, com chave de empenho opcional no esquema; hoje todas têm chave |
| Verificações da derivação (`verificacao`) | NÃO EXISTE na camada | agregadas por escopo (entidade × ano, documento do RREO etc.), sem lista de empenhos |
| Comparação entre cortes | NÃO EXISTE | |
| Concentração por credor | NÃO EXISTE | bloqueada por governança |

### 5.2 Funcionalidades da interface

| Funcionalidade | Classificação | Observação |
|---|---|---|
| Filtros (exercício, corte, entidade, como estava em, categoria, fonte de recurso, programação, tipo de credor, CNPJ de PJ) | **EXIBIDO** | |
| Filtro por órgão, função, programa ou elemento | NÃO EXISTE | |
| Busca por ano e número do empenho | **EXIBIDO** | |
| Busca por nome de credor | NÃO RECOMENDADO | dados pessoais |
| Paginação | **EXIBIDO** | 50 por página (`LIMIT`/`OFFSET`) |
| Comparação temporal | EXISTE PARCIALMENTE | retratos do mesmo corte e "como estava em"; entre cortes, não |
| Detalhamento | **EXIBIDO** | |
| Proveniência | **EXIBIDO** | até o objeto bruto |
| Reconciliação | **EXIBIDO** | |
| Navegação entre entidades | EXISTE PARCIALMENTE | seletor e tela de entidades; sem histórico por entidade |
| Navegação entre exercícios | EXISTE PARCIALMENTE | seletor; sem JavaScript, trocar o exercício exige uma consulta |
| Histórico | EXISTE PARCIALMENTE | "como estava em" e retratos |
| Metodologia | **EXIBIDO** | |
| Gráficos | NÃO EXISTE | |

### 5.3 Infraestrutura

| Capacidade | Classificação | Observação |
|---|---|---|
| Atualização da base | EXISTE PARCIALMENTE | procedimento documentado na 04.6, nunca executado de ponta a ponta |
| Processamento | **EXISTE** | `processar`, `--em` |
| Portões | **EXISTE** | `portoes`; o portão de testes é manual |
| Backups | **EXISTE** | antes de migração e de exclusão; sem retenção global |
| Reconstrução | **EXISTE** | comprovada em ambiente limpo |
| Instalação | **EXISTE** | só Windows com Python 3.14.3 comprovados |
| Configuração | **EXISTE** | portátil |
| Testes | EXISTE PARCIALMENTE | 257 + 26, executados à mão; sem CI |
| CI, lint, verificação de tipos | NÃO EXISTE | |
| Agendamento e alertas | NÃO EXISTE | |
| Servidor de produção, HTTPS, autenticação | NÃO EXISTE | |

### 5.4 Medições feitas para este plano (somente leitura, banco ativo)

| Tema | Medição |
|---|---|
| Cortes | 22 cortes processados: 2016–2024 só 31/12; 2025 com 6 bimestres; 2026 com 7 cortes, dos quais 31/01, 31/03 e 31/12 só da entidade 1 (Município indisponível: "corte não coletado para a(s) entidade(s) [4, 5, 8, 15]") |
| Série de uma entidade | `evolucao(2026, 15)` e `evolucao(2026, 5)` listam 4 cortes; 31/01, 31/03 e 31/12 não aparecem, nem como indisponíveis |
| Janela de coleta | todos os cortes vigentes coletados entre 29/09/2026 20h11 e 30/09/2026 01h22 |
| Corte posterior à coleta | 31/12/2026 (só entidade 1), coletado em 29–30/09/2026: valores até a data da coleta |
| Retratos | 28 cortes com mais de um retrato, todos com bytes idênticos ao anterior |
| Inscrição entre cortes do mesmo exercício | igual em todos os cortes de 2025 (Município, entidades 1 e 15) e de 2026 (entidade 1 e Município): mesma inscrição e mesmo número de registros |
| Dimensões (2025-12-31, Município) | entidade 5 grupos; ano do empenho 13; categoria 3; fonte de recurso 150; programação 688; órgão 28; unidade 112; função 20; subfunção 43; programa 69; projeto 351; elemento 49; 16 registros sem classificação orçamentária |
| Credores por tipo (2025-12-31) | PJ: 3.947 registros; PF: 1.931 registros |
| RREO extraído | 2017 e 2020–2024 (6º bimestre, entidade e consolidado); 2025 com 6 bimestres; 2026 com 4. Não lidos: 2016 (entidade), 2018 e 2019 |
| Anomalias (derivação 23) | COPIA-24 17.434; LIQ-NEG 2.096; PAGOPROC-SEM-PROC 99; PAR-INSCRICAO-DIVERGENTE 55. Todas com entidade, ano e empenho preenchidos. Tipos possíveis: 12 em `anomalia_tipo` |
| Verificações (derivação 23) | ANOM-CONT v1 "continuidade fechamento→abertura": 100 itens, 64.792 verificados, 0 falhas. PAR-24 v1 "pareamento de cópias 24xxxxx": 19 itens, 3.045 verificados, 0 falhas. CONC-RREO v1 "conciliação RREO × API (colunas com diferença)": 66 itens, 792 verificados, 466 "falhas" (= colunas com diferença, não erro). CONC-RREO v1 "RREO sem valores extraídos": 3 itens, 3 "falhas" (= PDFs não lidos) |
| Movimentação | 148 coletas de 147 empenhos; 2.352 lançamentos de 10/11/2011 a 29/09/2026 |
| Evidências externas | 0 |

## 6. Oportunidades identificadas (por categoria)

**A. Apresentação**
- A1: séries no exercício (P1).
- A2: séries entre exercícios (P2).
- A3: tabelas de composição (P3, P4).
- A4: gráficos que respondam a P1–P5 (seção 9.0).
- A5: filtros por dimensão orçamentária na lista de empenhos.
- A6: navegação do ponto da série para os registros.

**B. Análise**
- B1: diferença entre cortes consecutivos (P1).
- B2: série por exercício (P2).
- B3: composição por categoria e faixa (P3).
- B4: composição por dimensão (P4).
- B5: comparação entre entidades (P5).
- B6: diferença "S1 de A × (a)+(f) de A+1" na API para todo escopo (P7).

**C. Investigação**
- C1: contribuição de cada empenho para a variação entre dois cortes (P6).
- C2: histórico de um empenho através dos cortes (P8).
- C3: anomalias e verificações da derivação (P12).
- C4: resumo das diferenças com o RREO por situação (P9).

**D. Dados**
- D1: primeira atualização real pelo procedimento documentado.
- D2: cortes bimestrais de 2016–2024.
- D3: movimentação de mais empenhos.
- D4: RREO de outras entidades e bimestres; layouts de 2016, 2018 e 2019.

**E. Automação**
- E1: coleta agendada.
- E2: processamento automático.
- E3: portões automáticos.
- E4: alertas.

**F. Engenharia**
- F1: CI.
- F2: lint e tipos.
- F3: dependências com hash.
- F4: testes dos scripts de lote.
- F5: unificação das implementações de regra.
- F6: retenção de logs e backups.
- F7: empacotamento.

## 7. Priorização

Critérios aplicados a cada oportunidade:
- valor para o usuário;
- disponibilidade dos dados;
- confiabilidade dos dados;
- complexidade;
- risco de alterar resultados homologados;
- dependências;
- facilidade de validação independente.

| Oportunidade | Por que entra, ou por que não, agora |
|---|---|
| **B1/A1 evolução no exercício** | Dados prontos; `evolucao` existe e só precisa enumerar todos os cortes do exercício (R1). Regras operacionais. O recálculo a partir do bruto já existe nos testes da 04.6. Risco baixo. **Primeira a entrar.** |
| **B2/B6/A2 série entre exercícios** | Dados prontos (cortes de 31/12). A comparação fechamento × abertura já tem definição no código (coerência). O risco é de interpretação (estado atual × época), resolvido por rótulo e teste de texto. |
| **B3/B4/A3/A5 composição** | Regras operacionais (CAT, FAIXA) e somas de campos da API; `por_dimensao` existe. Validação: fechamento por dimensão. |
| **C1/C2 investigação de variação** | Valor alto. Exige a consulta realmente nova (casamento de registros entre cortes). Entra depois das séries, porque explica uma variação que o usuário primeiro precisa ver. A validação é a mais exigente (seção 9, 05.5). |
| **C3/C4 qualidade e diferenças** | Dados prontos na derivação e em `explicacoes.py`. Baixo risco, desde que cada estrutura seja apresentada segundo sua natureza (seção 9, 05.6). |
| **B5 comparação entre entidades** | Sai das séries de 05.2 e 05.3, com aviso dos pares 24xxxxx. Não precisa de subetapa própria. |
| A4 gráficos | Só depois que a tabela correspondente estiver homologada. |
| D, E, F | Fora da Etapa 05 (seção 8). D1 é decisão separada, fora do caminho crítico (seção 10). |

**Sequência:** 05.1 contrato → 05.2 evolução no exercício → 05.3 série entre exercícios → 05.4 composição → 05.5 investigação → 05.6 qualidade e diferenças → 05.7 homologação. A conferência contra o código não revelou dependência técnica que mude essa ordem.

## 8. Fora da Etapa 05

| Item | Motivo |
|---|---|
| Novas coletas (D1–D4), salvo decisão expressa do responsável | dependem da API não documentada e geram snapshots. D1 é decisão separada e **não** é dependência de 05.1–05.6 |
| Automação (E1–E4) | o procedimento manual nunca foi executado de ponta a ponta (análise na seção 16.2) |
| Servidor de produção, HTTPS, autenticação, publicação externa | infraestrutura; homologação no ambiente de destino |
| Concentração e ranking por credor identificado (P11) | governança de dados pessoais; vedado pela especificação da 04.5 |
| Somar "entidade 1 + entidade 15" como total corrigido, ou promover CONS-PAR | natureza das cópias 24xxxxx **não determinada**; depende do e-SIC; regra experimental |
| Promoção de regra experimental ou não recomendada (RREO-COL v1/v2, CANC v1, CONS-PAR) | sem critério nem evidência nova |
| Tratar como explicada uma diferença hoje "hipótese" ou "não determinada" | proibido transformar diferença não explicada em regra |
| Divisão de cancelamentos em processado e não processado como indicador | CANC v1 não recomendada |
| Nova versão de qualquer regra da derivação, ou nova tabela derivada | mudaria o `hash_resultado`; a Etapa 05 só lê a camada 2 existente |
| Segunda implementação das regras de derivação para "recalcular" anomalias e verificações | aumentaria o risco de divergência entre implementações (revisão de código, item 25) |
| Extrator de RREO para os layouts de 2016, 2018 e 2019 | trilha RREO própria |
| CI, lint, tipos, hash de dependências, empacotamento, unificação de regras (F1–F3, F5, F7) | engenharia; etapa própria ou antes da publicação externa |

## 9. Subetapas propostas

Cada subetapa termina com homologação (seção 11) e **parada para aprovação**. Nenhuma altera snapshot, normalização, derivação, regra ou valor já exibido. Toda métrica nova fica na camada painel; a interface só apresenta (seção 9.3).

### 9.0 Princípios para gráficos (valem para 05.2 a 05.5)

- **Pergunta antes do gráfico:** um gráfico só entra se responde a uma pergunta da seção 4 (P1–P6). Nada decorativo.
- **Tabela sempre:** todo gráfico vem com a tabela de valores exatos (`<data value>` em centavos). A tabela é a fonte da verdade e a alternativa acessível.
- **Unidade, período e escopo explícitos.**
- **Ausência não é zero:** ponto indisponível vira lacuna rotulada com a situação (seção 9.2), nunca zero e nunca ausência silenciosa. Zero verdadeiro (`sem_rp`) é desenhado como zero e rotulado.
- **Proveniência:** cada ponto liga para a tela do corte, com retrato, snapshots e derivação. O gráfico não calcula nada.
- **Do ponto ao registro:** de um ponto, o usuário chega à lista de empenhos daquele corte e escopo, e à investigação da variação (05.5).
- **Técnica:**
  - Nenhuma biblioteca é escolhida neste plano e nenhum gráfico é implementado agora.
  - Restrições a respeitar: sem JavaScript, CSP `default-src 'none'` e `style-src 'self'`, sem CDN, sem dependência nova de execução sem justificativa aprovada.
  - A decisão fica para a 05.1.

### 9.1 Contrato de toda métrica numérica nova (registrado na 05.1)

Nenhuma métrica entra sem as 14 respostas:

1. **Fonte:** API Elotech; RREO só na reconciliação.
2. **Regra:** fórmula e versão.
3. **Classe da regra:** contábil e operacional, analítica ou experimental. Só operacional compõe indicador.
4. **Localização da implementação:** método da camada painel; a interface nunca calcula.
5. **Recálculo independente:** pode ser recalculada a partir do JSON bruto? Se não puder, a métrica não entra.
6. **Método de validação:** bruto = painel = tela, ao centavo, nos pontos disponíveis.
7. **Risco de mascarar a fonte:** por exemplo, uma diferença que esconde mudança retroativa, ou uma soma que esconde a dupla contagem dos pares.
8. **Proveniência exibida:** derivação, normalização e snapshots de cada operando.
9. **Casos extremos:**
   - corte indisponível;
   - zero verdadeiro;
   - entidade fora do catálogo;
   - registro só de um lado;
   - pares 24xxxxx;
   - valores negativos (LIQ-NEG);
   - "sem classificação";
   - chave duplicada.
10. **Fechamento esperado**, quando aplicável. Por exemplo: soma dos grupos = total do corte; soma das contribuições = variação total.
11. **Definição de sinal**, quando for diferença: sempre **posterior − anterior**; nunca valor absoluto.
12. **Unidade e domínio:** centavos inteiros (R$ só na exibição); pode ser negativo, e qual é o intervalo esperado.
13. **Tratamento de indisponibilidade:** que situação do dado (seção 9.2) impede o cálculo, e como isso aparece.
14. **Tratamento de ausência de registro:** o que acontece quando a chave ou o grupo não existe num dos lados.

**Anomalias e verificações não são métricas novas.** Já são produzidas pela derivação homologada e seguem o regime da seção 9.4.

### 9.2 Regra de disponibilidade das séries (vale para 05.2, 05.3 e 05.5)

Cada ponto de série (exercício × corte × escopo) tem uma situação, sempre exibida:

| Situação | Origem no código | Ponto da série |
|---|---|---|
| dado disponível | `com_dados` em toda entidade que entra no total | valor; conferido bruto = painel = tela |
| zero verdadeiro | `sem_rp` (a entidade existia e a API devolveu 0 registros) | **R$ 0,00**, rotulado "sem RP neste corte" |
| entidade fora do catálogo | `inexistente` | sem valor: "a entidade não existia no exercício" |
| corte não coletado | `sem_coleta` | sem valor: lacuna rotulada |
| corte coletado, mas não processado | `nao_processado` | sem valor: lacuna rotulada |
| dado indisponível | `incompleto` (só coleta incompleta ou com falha) | sem valor: lacuna rotulada |
| Município indisponível | alguma entidade do catálogo do exercício sem snapshot processado (`motivo_indisponivel` de `_corte`) | sem valor, com o motivo por entidade |
| exercício sem cobertura (só 05.3) | nenhum corte do exercício no banco | sem valor: "exercício sem coleta" |
| corte posterior à coleta | `retrato.corte_posterior_a_coleta` | valor, rotulado "valores até a data da coleta" |

**Regra:**
- Para todo corte e escopo em que o dado estiver **disponível**, o valor da série coincide entre o JSON bruto, a camada `painel` e a interface, ao centavo.
- Ponto **indisponível** aparece explicitamente como lacuna, com a situação. Ele **nunca** vira R$ 0,00 e **nunca** desaparece da série.

**Universo de pontos de uma série:**
- Todos os cortes processados do exercício, para **qualquer** escopo (Município ou entidade). Hoje `evolucao` para uma entidade só lista os cortes em que ela tem snapshot (R1).
- Na série entre exercícios (05.3): todos os exercícios de 2016 a 2026.

### 9.3 Arquitetura que a Etapa 05 preserva

```text
REGRA / CONSULTA (camada painel, sobre a camada 2 existente)
      ↓
PAINEL (valor + natureza + regra + retrato + situação + proveniência)
      ↓
INTERFACE (só apresenta; teste proíbe aritmética em centavos)
```

Nunca `BANCO → INTERFACE → CÁLCULO IMPROVISADO`. Expressão repetida em mais de um lugar vira constante única na camada painel, como `EXPR_CANCELAMENTOS` na 04.6.

### 9.4 Validação independente: dois regimes

| O que se valida | Cadeia de validação | Por quê |
|---|---|---|
| **Métrica numérica nova** (séries, diferenças, composição, contribuições) | JSON bruto → recálculo independente → painel → interface, ao centavo | é a garantia homologada na 04.6; sem recálculo possível, a métrica não entra |
| **Anomalias e verificações já produzidas pela derivação** | derivação homologada (tabelas `anomalia`, `verificacao`, `hash_resultado`) → painel → interface, mais a cadeia de proveniência (regra, derivação, snapshot, quando houver) | já fazem parte do `hash_resultado` homologado. Uma segunda implementação integral das regras para "recalculá-las" criaria duas implementações que podem divergir (revisão de código, item 25) |

Nos dois regimes, a interface mostra exatamente o que a camada painel devolve.

### 05.1 — Contrato analítico e base de validação

- **Objetivo:** fixar, antes de qualquer tela:
  - o contrato (seção 9.1) de cada métrica da Etapa 05;
  - a regra de disponibilidade (seção 9.2);
  - a técnica de apresentação.
- **Problema que resolve:** evita cálculo na interface, métrica sem validação e ponto indisponível tratado como zero.
- **Dados:** nenhum dado novo.
- **Componentes afetados:** `etapa05/CONTRATO_ANALITICO.md` e utilitários de teste; nenhum código de produção.
- **Conteúdo:**
  - as 14 respostas de cada métrica de 05.2–05.5;
  - o corte que representa cada exercício (31/12; em 2026, o último corte com Município disponível, rotulado "exercício em aberto");
  - textos obrigatórios de retrato;
  - pendências R1 e R4 da seção 18;
  - técnica de gráfico, com justificativa.
  - nos testes: generalizar o recálculo a partir do JSON bruto (`test_homologacao_real.py`: `registros_brutos`, `recalcular`) para séries, diferenças e contribuições;
  - nos testes: casos sintéticos de cada situação da seção 9.2.
- **Dependências:** aprovação deste plano.
- **Risco:** baixo.
- **Testes:**
  - o recálculo reproduz `Painel.indicadores` em todos os pontos disponíveis dos 22 cortes;
  - as suítes existentes continuam passando.
- **Critério de aceitação:** contrato aprovado; validação cobrindo todo ponto disponível; nenhum valor exibido muda.
- **Critério de parada:** métrica sem recálculo independente possível sai do escopo.

### 05.2 — Evolução dentro do exercício

- **Objetivo:** série dos cortes de um exercício, para Município ou entidade (inscrição, pagamentos, liquidações, cancelamentos, saldo S1), e a diferença entre cortes consecutivos.
- **Problema que resolve:** P1.
- **Dados:** `Painel.indicadores` por corte; 2025 (6 cortes) e 2026 (7 cortes).
- **Componentes afetados:**
  - camada painel: série com o universo completo de cortes (R1), situação de cada ponto (seção 9.2), diferença entre consecutivos com natureza `diferenca`, sinal posterior − anterior e proveniência dos dois lados;
  - interface: tela ou seção.
- **Diferença entre cortes:** só existe quando **os dois** pontos estão disponíveis. Ponto vizinho indisponível = diferença indisponível, nunca calculada contra zero.
- **Dependências:** 05.1.
- **Risco:** baixo.
- **Testes:**
  - todo ponto disponível com bruto = painel = tela;
  - 2026: Município em 31/01, 31/03 e 31/12 presente como lacuna "corte não coletado para as entidades [4, 5, 8, 15]";
  - entidade 15 em 31/01, 31/03 e 31/12 de 2026 presente como lacuna, e não ausente;
  - nenhuma diferença calculada contra lacuna;
  - 31/12/2026 rotulado "posterior à coleta";
  - proveniência de cada ponto;
  - responsividade.
- **Critério de aceitação:** coincidência ao centavo em todo ponto disponível de 2025 e 2026, para o Município e cada entidade; todo ponto indisponível presente e rotulado; nenhum R$ 0,00 fora de `sem_rp`.
- **Critério de parada:** se a inscrição variar entre cortes do mesmo exercício sem explicação, parar e documentar antes de exibir a série (hoje não varia; seção 5.4).

### 05.3 — Série histórica entre exercícios (2016–2026)

- **Objetivo:** série por exercício, para Município e entidade:
  - inscrição na abertura;
  - pagamentos e cancelamentos do exercício;
  - saldo S1 no fechamento;
  - a diferença "S1 de A × (a)+(f) de A+1".
- **Problema que resolve:** P2, P5 e P7.
- **Dados:**
  - cortes de 31/12 de 2016–2025;
  - 2026 como exercício em aberto;
  - FAIXA v1 e S1 v1;
  - verificação ANOM-CONT v1.
- **Componentes afetados:**
  - camada painel: série composta de `indicadores` por exercício, com a situação de cada ponto (seção 9.2, incluindo "exercício sem cobertura");
  - camada painel: a diferença fechamento × abertura **pelas mesmas definições do código** (`_api_do_corte`: S1 de A e (a)+(f) de A+1 pela FAIXA v1), agora para todo escopo e não só os com RREO;
  - leitura da verificação ANOM-CONT;
  - interface.
- **Fechamento × abertura** (R2): nunca "saldo final de A × inscrição de A+1".
  - A inscrição de A+1 inclui os empenhos do próprio ano A (faixas b/g da FAIXA v1), que não estavam no saldo de RP de A.
  - A comparação definida é S1(A) contra (a)+(f)(A+1), com natureza `diferenca` e sinal (a)+(f)(A+1) − S1(A).
  - Diferença ≠ 0 mostra que o fechamento de A e a abertura de A+1 não coincidem na base atual. Ela aparece como diferença, nunca como erro, e a causa é investigada, não presumida.
- **Distinguir na série:**
  - exercício sem cobertura;
  - entidade fora do catálogo (entidade 15 antes de 2019; entidade 10 depois de 2022; entidades 3, 6, 9 e 11 em 2026);
  - escopo existente sem RP (`sem_rp`);
  - corte indisponível.
- **Requisito histórico obrigatório:** todo ponto carrega o retrato "estado atual da base para o corte de {exercício}, coletado em {data da coleta}". Nenhum texto pode sugerir "situação conhecida em {exercício}".
- **Dependências:** 05.2 (forma de série e diferença).
- **Risco:** médio, de interpretação.
- **Testes:**
  - todo ponto disponível com bruto = painel = tela;
  - teste do **texto do retrato** em todos os pontos;
  - ausência de frases como "Restos a Pagar de 2020" ou "situação em 2020" sem o retrato;
  - entidades fora do catálogo como lacuna;
  - fechamento × abertura igual ao já exibido na coerência para os escopos com RREO;
  - ANOM-CONT igual à tabela `verificacao`.
- **Critério de aceitação:** coincidência ao centavo em todo ponto disponível; lacunas rotuladas; texto do retrato verificado em todo ponto.
- **Critério de parada:** divergência entre a série e os indicadores homologados, ou falha nova de continuidade.

### 05.4 — Composição do saldo

- **Objetivo:** decompor a inscrição e o saldo de um corte por dimensão, cada parte levando à lista de empenhos correspondente. Dimensões:
  - categoria (CAT v1);
  - faixa (FAIXA v1);
  - tipo de credor;
  - fonte de recurso, órgão, função, programa e elemento.
- **Problema que resolve:** P3 e P4.
- **Dados:** `rp_derivado` (CAT, FAIXA) e `Painel.por_dimensao`, que agrupa também o valor nulo.
- **Componentes afetados:**
  - camada painel: composição por faixa e verificação de fechamento por dimensão;
  - filtros por dimensão em `_filtros_empenho`;
  - interface.
- **Fechamento por dimensão.** Cada dimensão fecha **sozinha**: grupo 1 + grupo 2 + … + "sem classificação" = total do corte, ao centavo, para cada medida exibida (inscrição, saldo).
  - Dimensão que não fecha **não é exibida** até a causa ser explicada, mesmo que as outras fechem.
  - Publicar "fonte fecha, órgão fecha, função não fecha" mostrando a função é vedado.
- **Faixa (R3):**
  - A FAIXA v1 classifica separadamente a parte processada (a/b) e a não processada (f/g) de cada registro. Um registro com as duas partes entra em dois grupos.
  - O fechamento da faixa é de **valores**: Σ proc por faixa_processado + Σ aproc por faixa_nao_processado = inscrição total. **Não** é de contagem de registros.
  - A linguagem é sempre "composição dos registros da API segundo a regra FAIXA v1", nunca "coluna (a)", "coluna (f)" ou qualquer referência às colunas do RREO.
- **Dependências:** 05.1.
- **Risco:** baixo a médio.
- **Testes:**
  - fechamento de cada dimensão em todo corte disponível;
  - grupo "sem classificação" presente com contagem;
  - cada parte leva a uma lista cujo total é a própria parte;
  - recálculo do bruto;
  - teste de texto: nenhuma menção às colunas do RREO na composição por faixa.
- **Critério de aceitação:** todas as dimensões exibidas fecham individualmente em todos os cortes disponíveis.
- **Critério de parada:** dimensão que não fecha fica fora da tela, com a causa registrada no relatório.

### 05.5 — Investigação de variações

- **Objetivo:**
  1. Para dois cortes do **mesmo exercício** e mesmo escopo, explicar a variação de cada métrica pelas contribuições de cada empenho.
  2. Mostrar o histórico de um empenho através dos cortes.
- **Problema que resolve:** P6 e P8.
- **Dados:** `rp_registro` e `rp_derivado` dos snapshots vigentes dos dois cortes.
- **Componentes afetados:** camada painel (consulta nova, paginada, somente leitura) e interface.
- **Dependências:** 05.1 e 05.2.
- **Risco:** médio; é a consulta mais sensível da etapa.

**Pré-condições do par de cortes:**
- os dois cortes estão disponíveis no escopo;
- no Município, o mesmo conjunto de entidades entra no total nos dois cortes;
- se uma pré-condição falhar, a investigação daquele par fica indisponível, com o motivo.

**Chave e duplicidade:**
- A chave é `(entidade, anoempenho, empenho)`.
- Se a mesma chave aparecer mais de uma vez em qualquer dos dois snapshots, a investigação **daquele par de cortes é bloqueada**, com a lista das chaves repetidas. Nenhuma ocorrência é escolhida automaticamente.
- A derivação já registra esse caso como anomalia CHAVE-DUP; hoje há 0.

**Métricas comparadas** (só estas duas; nenhuma regra contábil nova):

| Métrica | Valor por chave no corte anterior e no posterior | Fórmula da variação | Natureza | Proveniência | Validação |
|---|---|---|---|---|---|
| Variação de saldo S1 | `rp_derivado.s1_saldo_total_c` (S1 v1 = proc + aproc − pagoProc − pagoAProc − canceladoAProc) | S1(posterior) − S1(anterior) | `diferenca` | os dois snapshots, as derivações e o registro de cada lado (resposta HTTP, posição, objeto bruto) | recálculo do S1 a partir do JSON bruto de cada lado |
| Variação de pagamentos | `rp_registro.pago_proc_c + rp_registro.pago_aproc_c`, a mesma expressão do indicador "pagamentos" (a 05.1 a torna constante única, como `EXPR_CANCELAMENTOS`) | pagamentos(posterior) − pagamentos(anterior) | `diferenca` | idem | recálculo de pagoProc + pagoAProc a partir do JSON bruto |

Os pagamentos de um corte são acumulados de 01/01 até a data final. A variação entre cortes do mesmo exercício é, portanto, o pagamento líquido do intervalo, **desde que** os dois cortes reflitam a mesma base. Por isso a tela mostra as datas de coleta dos dois lados (hoje, a mesma janela de 29–30/09).

Outra métrica de contribuição só entra com justificativa e contrato completo na 05.1.

**Contribuição por chave** (sinal sempre posterior − anterior; nunca valor absoluto):

| Situação da chave | Contribuição | Classe exibida |
|---|---|---|
| existe nos dois cortes | valor_posterior − valor_anterior | "nos dois cortes" |
| existe só no corte posterior | valor_posterior | "presente só no corte posterior" (ex.: registro inserido depois) |
| existe só no corte anterior | 0 − valor_anterior | "ausente no corte posterior" |
| repetida em algum lado | — (par bloqueado) | — |

**Variação total:**

```text
variação = valor_do_corte_posterior − valor_do_corte_anterior
```

O total é calculado pela mesma soma do indicador homologado em cada corte.

**Fechamento e apresentação:**
- **Lista completa paginada:** é a opção coerente com a arquitetura atual, que já pagina com `LIMIT`/`OFFSET`. A lista contém **todas** as chaves com contribuição ≠ 0.
- **Resumo com grupos:** a tela de resumo mostra:
  - TOP N aumentos (contribuição > 0, em ordem decrescente);
  - "outros aumentos" (soma e quantidade);
  - TOP N reduções (contribuição < 0, em ordem crescente, a mais negativa primeiro);
  - "outras reduções" (soma e quantidade);
  - "sem variação" (contribuição = 0, só a quantidade).
- **Fechamento obrigatório, ao centavo:**

  ```text
  Σ TOP aumentos + Σ outros aumentos + Σ TOP reduções + Σ outras reduções + 0 (sem variação)
  = variação total
  ```

  E também por classe: Σ "nos dois cortes" + Σ "só no posterior" + Σ "só no anterior" = variação total.
- **Desempate da ordenação:** igualdade de contribuição se resolve por (entidade, anoempenho, empenho), para ser determinística.
- **Sinal:** contribuições positivas e negativas nunca se compensam em silêncio nem são mostradas em valor absoluto.
- **Registro presente só de um lado:** sempre em sua classe, nunca tratado como zero do outro lado sem rótulo.

**Histórico de um empenho:** valores do registro da chave em cada corte em que aparece, com a situação do ponto (seção 9.2) nos cortes em que não aparece.

**Testes:**
- fechamento ao centavo (grupos e classes) em todos os pares de cortes consecutivos disponíveis de 2025 e 2026, nas duas métricas;
- recálculo do bruto de cada contribuição;
- sintéticos:
  - chave só no posterior;
  - chave só no anterior;
  - chave duplicada (par bloqueado);
  - contribuição zero;
  - empates;
  - Município com conjunto de entidades diferente (par bloqueado);
- casos reais: 5659/2025 e 2401751/2023;
- desempenho com o corte inteiro.

**Critério de aceitação:** fechamento exato em todos os pares disponíveis; toda contribuição com proveniência dos dois lados.

**Critério de parada:** chave duplicada real, ou fechamento que falhe. Parar e investigar antes de exibir.

### 05.6 — Qualidade dos dados e situação das diferenças

- **Objetivo:** expor, cada uma segundo sua natureza, as anomalias e verificações já gravadas pela derivação, e um resumo das diferenças com o RREO por situação.
- **Problema que resolve:** P9 e P12.
- **Dados:** `anomalia` + `anomalia_tipo`; `verificacao` + `regra`; `conciliacao_rreo`; `explicacoes.py`; coerência.
- **Componentes afetados:** camada painel (leituras novas, sem regra nova) e interface (tela "Qualidade dos dados").
- **Dependências:** 05.1.
- **Risco:** baixo; o cuidado é de natureza e de linguagem.

**Anomalias** (`anomalia`: uma linha por ocorrência; colunas `derivacao_id`, `regra_id`, `tipo`, `coleta_id`, `entidade`, `anoempenho`, `empenho`, `detalhe_json`):
- por tipo: código, descrição e status de evidência (`anomalia_tipo`), regra, quantidade e escopo (coletas e exercícios envolvidos);
- registros relacionados, com o detalhe de `detalhe_json`;
- **quando a anomalia estiver associada a entidade, ano e número do empenho, a interface permite o drill-down até o registro correspondente**;
- anomalias sem chave de empenho aparecem só no nível agregado. O esquema permite chave nula; hoje todas têm chave;
- anomalia não é erro: o texto segue a descrição do tipo (ex.: LIQ-NEG = estorno de liquidação).

**Verificações** (`verificacao`: agregada; colunas `derivacao_id`, `regra_id`, `descricao`, `escopo_json`, `verificados`, `falhas`):
- campos exibidos: regra, descrição, escopo (de `escopo_json`), quantidade verificada, quantidade de "falhas", snapshots envolvidos quando `escopo_json` os traz (a continuidade traz);
- **situação da verificação**, interpretada **por descrição**, porque o significado de "falhas" muda (R5):
  - "continuidade fechamento→abertura" e "pareamento de cópias 24xxxxx": falha = item que não cumpriu a verificação; 0 = "sem falha";
  - "conciliação RREO × API (colunas com diferença)": "falhas" = **colunas com diferença**, informativo, remetendo à reconciliação e às situações abaixo;
  - "RREO sem valores extraídos": "falhas" = PDFs não lidos pelo extrator;
- a verificação é de conjunto. **Não** se apresenta cada falha como um empenho. Quando a mesma regra registra anomalias por empenho (ex.: SALDO-SEM-CONTINUIDADE e DESCONTINUIDADE para a continuidade), a ligação é feita por regra e escopo, para a lista de anomalias.

**Diferenças com o RREO**, cinco situações separadas:

| Situação | Critério (código) |
|---|---|
| SEM DIFERENÇA | `diferenca_c == 0` (atribuída pela camada painel; **não** é explicação) |
| EXPLICADA | `explicacoes.resumo` = "explicada" |
| PARCIALMENTE EXPLICADA | `explicacoes.resumo` = "parcialmente explicada" |
| HIPÓTESE | `explicacoes.resumo` = "hipótese" |
| NÃO DETERMINADA | `explicacoes.resumo` = "não determinada", inclusive diferença sem nenhuma entrada |

A contagem é feita por coluna × documento × regra de agregação (RREO-COL v1 e v2 separadas), e também para a coerência entre publicações. A tela nunca classifica diferença zero como "explicada", nem soma "sem diferença" com "explicada".

**Testes:**
- contagens de anomalias e verificações iguais às da derivação (regime da seção 9.4: derivação → painel → interface);
- drill-down só para anomalia com chave completa;
- anomalia sintética sem chave aparecendo só no agregado;
- verificação nunca listada como empenhos;
- as 5 situações contadas separadamente e iguais às da reconciliação já exibida;
- nenhum `diferenca_c == 0` contado como explicada.

**Critério de aceitação:** números iguais aos da derivação e da reconciliação; cada estrutura apresentada segundo sua natureza; nenhuma regra nova.

**Critério de parada:** se a exibição exigir reinterpretar uma anomalia ou verificação, documentar e não exibir a interpretação.

### 05.7 — Homologação e encerramento da Etapa 05

- **O que entra:**
  - regressão completa;
  - estado antes × depois: os 5.575 valores homologados da 04.6 inalterados, mais os novos valores conferidos;
  - instalação limpa;
  - responsividade e acessibilidade das telas novas;
  - relatório final;
  - tag `etapa-05-final`.
- **Decisão antes da 05.7:** se a primeira atualização real da base (D1) será feita (seção 10).
- **Critério de aceitação:** seção 17.

O agrupamento é deliberado. Comparação entre entidades (B5) sai das séries de 05.2 e 05.3. Gráficos entram na subetapa da pergunta que respondem, depois da tabela homologada.

## 10. Dependências e decisões do responsável

| Decisão | Opções | Recomendação |
|---|---|---|
| Integração da Etapa 04 no `main` (PRs #1 → #2 → #3) | antes ou durante a Etapa 05 | **antes**, para que os PRs da Etapa 05 mostrem só o próprio trabalho |
| Aprovação deste plano (versão 2) e da ordem das subetapas | — | condição para iniciar a 05.1 |
| D1: primeira atualização real da base | fazer antes da 05.7, adiar ou deixar fora | **não é dependência de 05.1–05.6.** Exercitaria o procedimento da 04.6 e daria os primeiros casos reais de mudança entre retratos. Decidir antes da 05.7 |
| Técnica de gráfico | decidida na 05.1 | sem dependência nova de execução, salvo justificativa aprovada |
| Concentração por credor | manter fora ou abrir decisão de governança | manter fora |

## 11. Critérios de homologação (toda subetapa)

```text
IMPLEMENTAÇÃO
    ↓
TESTE UNITÁRIO (sintético: situações que o dado real não tem)
    ↓
TESTE REAL (armazém real, fixture `real`)
    ↓
VALIDAÇÃO INDEPENDENTE (seção 9.4: bruto → recálculo para métrica nova; derivação → painel para anomalia e verificação)
    ↓
VERIFICAÇÃO DE PROVENIÊNCIA (todo valor novo → derivação → snapshot → objeto bruto)
    ↓
VERIFICAÇÃO DA INTERFACE (celular, tablet, notebook, desktop; acessibilidade básica; sem rede; lacunas e textos de retrato)
    ↓
HOMOLOGAÇÃO (suítes completas + verificar + portoes + estado antes × depois)
```

- **Testes junto com o código:** os testes de cada camada são escritos junto com ela.
- **Toda subetapa termina com:**
  - suítes passando;
  - `verificar` limpo e `portoes` apto;
  - comparação de estado (`etapa04/resultados/04_6_estado.py` e `04_6_comparar_estados.py`) sem diferença nos valores homologados;
  - relatório próprio em `etapa05/`;
  - commit exclusivo;
  - parada para aprovação.

## 12. Riscos

| Risco | Efeito | Mitigação |
|---|---|---|
| Ler série histórica como "o que se sabia na época" | conclusão errada sobre gestões passadas | retrato obrigatório em todo ponto; teste do texto (05.3) |
| Ponto indisponível sumir ou virar zero | "ausência = zero" volta pela série | regra da seção 9.2; universo completo de pontos (R1); testes de lacuna |
| Dupla contagem dos pares 24xxxxx nas séries e comparações | soma das entidades 1 e 15 parece maior | os registros continuam como a API devolve; sinalização de espelhamento em toda série e comparação que envolva as entidades 1 e 15; **nenhuma** consolidação corretiva sem decisão de governança baseada em evidência |
| Fechamento × abertura lido como "saldo final × inscrição seguinte" | diferença falsa do tamanho das inscrições novas | definição S1(A) × (a)+(f)(A+1) pela FAIXA v1 (R2) |
| Diferença entre cortes coletados em momentos diferentes | mistura movimento do período com mudança retroativa | datas de coleta dos dois lados exibidas; hoje, mesma janela |
| Lista de contribuições "fechar" por omissão ou valor absoluto | variação explicada errada | fechamento por grupos e por classe, sinal preservado (05.5) |
| Verificação de conjunto apresentada como lista de empenhos, ou "sem diferença" contada como explicada | falsa precisão | regras da 05.6 |
| Lógica contábil migrar para a interface | perda da garantia homologada | teste da 04.6 continua valendo; métricas só na camada painel |
| Consulta nova pesada (casamento de cortes) | lentidão | paginação; medição antes e depois; índice só se uma medida pedir |
| Escopo crescer | etapa não fecha | seção 8; critério de parada em cada subetapa |

## 13. Estratégia de preservação dos dados

- A Etapa 05 **só lê**: camada painel e interface continuam somente leitura (`mode=ro` + `query_only`).
- Nenhuma subetapa altera snapshots, normalização, derivação, regras ou parâmetros. `hash_resultado` (`2f6b4e29…`, `b8a0b2ed…`) e `hash_camada0` (`733670693c01d015…`) devem continuar iguais ao fim de cada subetapa.
- Métrica nova é consulta da camada painel sobre a camada 2 existente. Se uma métrica exigir mudança na derivação, ela sai da Etapa 05.
- Os 5.575 valores de tela homologados na 04.6 são conferidos sem mudança ao fim de cada subetapa.

## 14. Estratégia de proveniência

- Todo valor novo sai da camada painel com natureza, regras e situação delas, retrato, situação do dado (seção 9.2) e proveniência (`_prov_curta` / `_proveniencia`).
- Diferença e contribuição carregam a proveniência dos **dois** lados: snapshots, derivação, normalização, e o registro de cada lado na 05.5.
- Anomalia e verificação carregam regra, derivação e, quando houver, coleta ou snapshots do escopo.
- Teste obrigatório por subetapa: nenhum valor novo sem proveniência navegável até um snapshot que exista no armazém, ou até a derivação, no caso das verificações agregadas.

## 15. Estratégia de regressão

- **Suítes:** as atuais (257 + 26) rodam a cada subetapa e precisam continuar passando sem ajuste. Ajuste de teste existente só com justificativa no relatório.
- **Testes reais novos:** cada subetapa acrescenta recálculo do bruto, testes de lacuna e de texto, e fechamentos.
- **Estado:** comparação antes × depois por subetapa, com os scripts da 04.6.
- **Instalação limpa:** repetida na 05.7.

## 16. Possíveis evoluções futuras

### 16.1 Trilha RREO
- **Cobertura atual:** entidade 1 e consolidado; 6º bimestre em 2017 e 2020–2024; todos os bimestres de 2025; 4 bimestres de 2026.
- **Lacunas:** 2016 (entidade), 2018 e 2019 sem extração; demais entidades sem RREO individual; 2016–2024 só o 6º bimestre.
- **Evolução possível:** extratores versionados para os layouts antigos e mais bimestres, sempre como fonte de reconciliação.
- **Regra fixa:** diferença não explicada nunca vira regra automática, e regra experimental não é promovida sem critério documentado.

### 16.2 Automação (análise; não implementar antes de o procedimento manual ser executado ao menos uma vez)

| Tema | Situação | O que exigiria |
|---|---|---|
| Periodicidade | os cortes bimestrais acompanham o RREO | calendário (ex.: depois de cada bimestre) |
| Dependências externas | API não documentada | parar e alertar quando o formato mudar; nunca adaptar sozinho |
| Falhas da API | coleta incompleta fica registrada e não vira retrato válido | repetição limitada; portão `coleta_completa` |
| Idempotência | cada coleta é um snapshot novo; objetos idênticos não se duplicam | comparar com o retrato anterior |
| Snapshots | append-only | retenção nunca apaga snapshot |
| Portões | `portoes` existe; testes manuais | suítes e portões antes de disponibilizar |
| Alertas | inexistentes | canal a definir |
| Rollback | a interface lê a derivação atual mais recente | "não disponibilizar" = manter a derivação anterior; apagar execução só pelo comando protegido |
| Logs e retenção | logs diários sem retenção; backups grandes | política de retenção (revisão de código, itens 27–29 e 42) |

### 16.3 e-SIC (quando houver resposta)

1. Registrar a resposta com `registrar-evidencia` (SHA-256, manifesto, `evidencia_externa`).
2. Rever as entradas de `explicacoes.py` e as decisões de governança (`regra_situacao`) que a resposta afetar, citando a evidência.
3. Nunca reescrever valores passados. Se a resposta justificar uma regra (ex.: consolidação dos 24xxxxx), ela entra como **versão nova**, com nova derivação, novo hash e homologação própria.

**Temas que a resposta pode esclarecer:**
- natureza e data de inclusão das cópias 24xxxxx;
- colunas (h) e (i) de 2026;
- lançamentos retroativos;
- liquidação estornada;
- situação oficial da consulta de RP.

### 16.4 Engenharia e publicação
- CI, lint e tipos.
- Dependências com hash.
- Testes dos scripts de lote.
- Unificação das implementações de regra.
- Empacotamento.
- Servidor WSGI de produção, HTTPS e controle de acesso.
- Homologação em outro sistema e em outra versão do Python.
- Decisão sobre dados pessoais no repositório público e sobre a licença AGPL do PyMuPDF.

## 17. Critério de encerramento da Etapa 05

A Etapa 05 estará encerrada quando, no commit final:

1. **P1/P2:** as séries existirem para Município e entidades. Cada ponto disponível coincide ao centavo entre JSON bruto, camada painel e interface. Cada ponto indisponível aparece com sua situação (seção 9.2), nunca como R$ 0,00 nem ausente. O texto do retrato de cada ponto histórico foi verificado por teste.
2. **P3/P4:** cada composição exibida fechar **individualmente** com o total do corte, por dimensão, ao centavo. Dimensão que não fecha não é exibida. A faixa é apresentada como "composição dos registros da API segundo a regra FAIXA v1".
3. **P6:** para todo par de cortes consecutivos disponível, as contribuições fecharem exatamente a variação, por grupos e por classe, com sinal preservado. Pares com chave duplicada ou escopo incompatível ficam bloqueados com motivo.
4. **P7:** a comparação fechamento × abertura usar S1(A) × (a)+(f)(A+1) pela FAIXA v1 e aparecer como diferença e verificação, não como erro.
5. **P9:** "sem diferença" separado de "explicada", "parcialmente explicada", "hipótese" e "não determinada", e as contagens iguais às da reconciliação.
6. **P12:** anomalias e verificações validadas segundo sua natureza (derivação → painel → interface). Drill-down só para anomalias com chave de empenho; verificações apresentadas como conjunto.
7. Toda métrica numérica nova estar no contrato com as 14 respostas e validada por recálculo independente.
8. Nenhum indicador usar regra experimental ou não recomendada; nenhuma consolidação dos pares 24xxxxx; nenhuma diferença "hipótese" ou "não determinada" apresentada como explicada.
9. A interface continuar sem cálculo contábil (teste da 04.6 passando).
10. As suítes passarem, `verificar` estar limpo e `portoes` apto.
11. Snapshots, normalização, derivação, `hash_resultado` e `hash_camada0` estarem iguais aos de `etapa-04-final`, e os valores homologados na 04.6 inalterados.
12. Telas novas verificadas em celular, tablet, notebook e desktop, com acessibilidade básica e sem rede; instalação limpa repetida.
13. Relatório final da Etapa 05 com as limitações abertas, e a tag `etapa-05-final` criada.
14. Nada da seção 8 implementado sem decisão expressa do responsável.

Nenhum critério acima exige regra nova, fonte nova ou mudança na derivação.

## 18. Registro das correções desta revisão (versão 2)

### 18.1 Correções pedidas pelo responsável

| Tema | Versão 1 | Versão 2 |
|---|---|---|
| Indisponibilidade nas séries | "série = painel = bruto em todos os cortes" | regra da seção 9.2: coincidência só nos pontos disponíveis; ponto indisponível presente e rotulado; nunca R$ 0,00 nem ausente |
| Matemática da variação (05.5) | "Σ contribuições = variação total" | definição de variação e de contribuição por situação da chave; chave duplicada bloqueia o par |
| Métricas comparadas (05.5) | não definidas | só variação de S1 e de pagamentos, com campo, fórmula, natureza, proveniência e validação |
| Fechamento das contribuições | não definido | lista completa paginada + resumo TOP N aumentos e reduções + "outros" + "sem variação"; fechamento por grupos e por classe; ordenação e sinal definidos; nunca valor absoluto |
| Anomalias × verificações (05.6) | misturadas | tratadas separadamente, conforme o esquema real |
| "Cada anomalia leva ao empenho" | critério de teste | drill-down só quando há chave completa; sem chave, só agregado |
| Validação independente | "se não puder ser recalculada do bruto, não entra" para tudo | dois regimes (seção 9.4): métrica nova pelo bruto; anomalia e verificação pela derivação homologada, sem segunda implementação |
| "Sem diferença" no RREO | listada como situação de explicação | categoria própria (`diferenca_c == 0`), separada das quatro situações de `explicacoes.resumo` |
| Fechamento da composição (05.4) | "soma das partes = total" | fechamento por dimensão; dimensão que não fecha não é exibida |
| Contrato da 05.1 | 9 itens | 14 itens (+ fechamento, sinal, unidade e domínio, indisponibilidade, ausência de registro) |
| Encerramento | genérico | um critério por pergunta (P1/P2, P3/P4, P6, P7, P9, P12), sem exigir regra ou fonte nova |

Mantidos sem mudança, conforme pedido:
- ordem das subetapas;
- a distinção FAIXA × RREO (agora com teste de texto);
- o requisito histórico da série (agora com teste de texto);
- os pares 24xxxxx fora da consolidação;
- D1 fora do caminho crítico;
- os princípios de gráfico, sem escolher biblioteca.

### 18.2 Problemas encontrados ao conferir o plano contra o código da tag

| # | Problema | Evidência | Classificação |
|---|---|---|---|
| R1 | `Painel.evolucao(ex, entidade)` só lista os cortes em que **aquela** entidade tem snapshot. Os demais cortes do exercício somem em silêncio, em vez de aparecerem como indisponíveis | `consulta.py`, `evolucao`: filtro `entidade is None or e == entidade`; `evolucao(2026, 15)` devolve 4 cortes e omite 31/01, 31/03 e 31/12 | **pendência para 05.1** (contrato do universo de pontos), corrigida na 05.2; sem efeito na Etapa 04, porque a interface não usa `evolucao` |
| R2 | A versão 1 propunha "saldo final de A × inscrição de A+1". A inscrição de A+1 inclui empenhos do próprio ano A (faixas b/g), então essa diferença não é zero por definição | definição da FAIXA v1 (`derivar.py`); o código já compara S1(A) com (a)+(f)(A+1) em `_api_do_corte`, usado pela coerência | **correção do plano** (05.3 e P7) |
| R3 | A composição por faixa fecha em **valores**, não em contagem de registros: um registro com proc e aproc entra em duas faixas | `derivar.py`: `faixa_processado` e `faixa_nao_processado` independentes | **correção do plano** (05.4) |
| R4 | O corte 31/12/2026 é posterior à coleta (valores até 29–30/09/2026) e aparece na série de 2026 da entidade 1 | `retrato.corte_posterior_a_coleta` | **pendência para 05.1** (rótulo do ponto) |
| R5 | "Falhas" em `verificacao` muda de significado conforme a verificação: na conciliação são colunas com diferença; em "RREO sem valores extraídos", PDFs não lidos | medição da seção 5.4 | **correção do plano** (05.6: situação interpretada por descrição) |
| R6 | No Município, comparar dois cortes exige o mesmo conjunto de entidades no total | `_corte`: entidades fora do catálogo ou sem snapshot não entram | **correção do plano** (pré-condição da 05.5) |

Nenhum desses problemas exige implementação agora, e nenhum muda a ordem das subetapas.
