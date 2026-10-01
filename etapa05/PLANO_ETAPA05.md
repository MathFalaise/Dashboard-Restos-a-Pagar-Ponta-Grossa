# Plano da Etapa 05 — da base homologada a um dashboard analítico

Data: 01/10/2026. Ramo `subetapa-05-planejamento`, criado da tag `etapa-04-final` (`a6bd27c`).

**Situação: proposta para revisão e aprovação.** Nada da Etapa 05 foi implementado. Este plano não altera código, banco, snapshots, regras, fórmulas nem interface.

Ordem de prioridade que orienta o plano:

**dados corretos → proveniência → validação → utilidade → apresentação.**

---

## 1. Objetivo da Etapa 05

Fazer o dashboard responder perguntas analíticas que hoje ele não responde, sem perder nenhuma das garantias homologadas na Etapa 04.

As perguntas centrais são:
- como os Restos a Pagar evoluem dentro de um exercício e ao longo dos exercícios;
- do que o saldo é composto;
- quais empenhos explicam uma variação.

Tudo isso com dados que já foram coletados, regras que já são operacionais e a mesma cadeia de proveniência até o objeto bruto.

**A Etapa 05 não é:** uma etapa de novas coletas, nem de automação, nem de publicação externa, nem de novas regras contábeis (seção 8).

## 2. Estado de partida

| Item | Valor |
|---|---|
| Ponto de restauração | tag `etapa-04-final` → `a6bd27c` (publicada no GitHub) |
| Integração no `main` | PRs #1 (04.5), #2 (04.6) e #3 (04.7) **abertos e não mesclados**; o `origin/main` está em `adc7510` |
| Testes | 257/257 de produção e 26/26 da investigação |
| Verificação e portões | `verificar` sem problemas; `portoes` apto |
| Banco | 466 snapshots; normalização 13 (228.873 registros); derivações 23 (atual, `2f6b4e29…`) e 24 (29/09, `b8a0b2ed…`) |
| Data dos dados | todos os cortes vigentes foram coletados entre 29/09/2026 20h11 e 30/09/2026 01h22 |

Fontes: `etapa04/RELATORIO_ETAPA04_FINAL.md` e as medições somente leitura feitas para este plano (seção 5.4).

## 3. O que a Etapa 04 entregou

- **Pipeline:** API Elotech → coletor → snapshot imutável → normalização → derivação → painel → interface. A trilha separada do RREO (snapshot → extração → reconciliação) nunca substitui o valor da API.
- **Camada de consulta:** `app/rp/painel`, somente leitura. Todo valor sai com natureza (`da_fonte`, `publicado`, `derivado`, `analitico`, `diferenca`), regra e sua situação de governança, rótulo de retrato e proveniência até o objeto bruto.
- **Interface:** `app/rp/interface`, WSGI da biblioteca padrão, sem JavaScript, CSP `default-src 'none'`. Homologada com bruto = painel = tela e com as 7 situações do dado (zero só quando é zero de verdade).
- **Operação:** reconstrução a partir de `snapshots/`, procedimento de atualização documentado, `python -m rp portoes` e instalação limpa comprovada (Windows, Python 3.14.3).

## 4. O que a Etapa 05 pretende resolver

Perguntas que o usuário precisa responder e que **hoje a interface não responde**, avaliadas contra os dados existentes:

| # | Pergunta | Responde hoje? | Dados disponíveis | Conclusão |
|---|---|---|---|---|
| P1 | Como o saldo, os pagamentos e os cancelamentos evoluem **dentro** do exercício? | não (só um corte por vez) | 2025: 6 cortes bimestrais; 2026: 7 cortes, com Município completo em 4; `Painel.evolucao` já existe | **respondível com os dados atuais** |
| P2 | Como os RP evoluem **ao longo dos exercícios** (2016–2026)? | não | um corte de fechamento (31/12) por exercício em 2016–2024; 2025 completo; 2026 aberto | **respondível**, sempre rotulado como estado atual da base |
| P3 | Quanto do saldo é processado ou não processado, inscrito no ano anterior ou antes, e por categoria? | não | CAT v1 e FAIXA v1 (operacionais) já derivados por registro; `indicadores.categorias` já calculado e não exibido | **respondível** |
| P4 | Como o saldo se distribui por fonte de recurso, função, programa, órgão e elemento? | não (só filtros pontuais) | `Painel.por_dimensao` existe; 16 registros sem classificação em 2025-12-31 | **respondível**, com "sem classificação" explícito |
| P5 | Como as entidades se comparam ao longo do tempo? | só num corte (tela Entidades) | as mesmas séries por entidade | **respondível**, com aviso dos pares 24xxxxx (seção 12) |
| P6 | Quais empenhos explicam a variação entre dois cortes do mesmo exercício? | não | os mesmos registros (chave entidade/ano/empenho) em cortes diferentes; nenhuma chave duplicada em 2016–2026 (04.4) | **respondível**, exige consulta nova e validação forte |
| P7 | Como a inscrição de A+1 se relaciona com o saldo final de A? | só por conferência com o RREO (coerência) | verificação "continuidade fechamento→abertura" da derivação (100 pares, 0 falhas) + FAIXA v1 | **respondível como verificação**, não como indicador |
| P8 | Como um empenho evoluiu? | parcial: detalhe num corte; movimentação só de 147 empenhos | o registro do empenho em cada corte em que aparece | **respondível** (valores por corte); a movimentação completa exigiria coleta nova (fora) |
| P9 | Quais diferenças com o RREO continuam, e em que situação? | parcial: por documento | `conciliacao_rreo` + `explicacoes` | **respondível** como resumo |
| P10 | O que mudou entre dois retratos do mesmo corte? | sim (comparador) | os 28 cortes com mais de um retrato têm **bytes idênticos** | **já existe; não há caso real** até haver coleta nova |
| P11 | Quais credores concentram o saldo? | não | identificação do credor só no nível interno; a 04.5 vedou ranking e tela pública de fornecedores | **depende de decisão de governança** (fora, seção 8) |
| P12 | Quais anomalias de dado existem? | não | a tabela `anomalia` da derivação (LIQ-NEG 2.096; PAGOPROC-SEM-PROC 99; COPIA-24 17.434; PAR-INSCRICAO-DIVERGENTE 55) não chega à camada painel | **respondível** como transparência de qualidade |

## 5. Inventário do que já existe

### 5.1 Dados (camada `rp/painel` × interface)

| Capacidade | Classificação | Observação |
|---|---|---|
| Indicadores do corte (13) | **EXIBIDO** | homologados bruto = painel = tela |
| Estornos de pagamento | EXISTE NA CAMADA, NÃO EXIBIDO | informativo, já descontado dos pagamentos |
| Categorias no indicador (`indicadores.categorias`) | EXISTE NA CAMADA, NÃO EXIBIDO | CAT v1 operacional |
| Reconciliação por indicador (`reconciliacao_rreo`) | EXISTE NA CAMADA, NÃO EXIBIDO | a tela mostra só a conferência S1 × L |
| Empenhos (lista, filtros, totais, detalhe) | **EXIBIDO** | |
| Entidades do corte | **EXIBIDO** | 7 situações do dado |
| Catálogo histórico (períodos oficiais por entidade) | EXISTE PARCIALMENTE | `Painel.entidades`; a tela só usa os nomes |
| Evolução no exercício (`evolucao`) | EXISTE NA CAMADA, NÃO EXIBIDO | 0,1–0,3 s por série no banco real |
| Dimensões (`por_dimensao`, 12) | EXISTE NA CAMADA, NÃO EXIBIDO | a interface usa só para listar fontes de recurso |
| Fornecedores, nível público (por tipo de credor) | EXISTE NA CAMADA, NÃO EXIBIDO | só pessoa jurídica, pessoa física e não identificado |
| Fornecedores identificados (nível interno) | NÃO RECOMENDADO (público) | governança de dados pessoais |
| Pares espelhados (PAR-24 v1) | **EXIBIDO** | área técnica |
| Visão analítica CONS-PAR v1/v2 | **EXPERIMENTAL** | não exibida, por decisão |
| Retratos e comparação de retratos | **EXIBIDO** | nenhum caso real de mudança (P10) |
| Reconciliação com o RREO | **EXIBIDO** | RREO-COL v1 NÃO RECOMENDADO; v2 EXPERIMENTAL; ambas rotuladas como análise |
| Coerência entre publicações | **EXIBIDO** | |
| Regras e governança | **EXIBIDO** | metodologia |
| Evidências externas | EXISTE NA CAMADA, NÃO EXIBIDO | 0 registros |
| Fontes, metodologia, dicionário | **EXIBIDO** | |
| Movimentação de empenho | EXISTE PARCIALMENTE | só 147 empenhos (145 da entidade 1) |
| Anomalias da derivação | NÃO EXISTE (na camada) | só na tabela `anomalia` |
| Verificações da derivação (continuidade, pareamento, conciliação) | NÃO EXISTE (na camada) | só na tabela `verificacao` |
| Comparação entre cortes ou exercícios | NÃO EXISTE | |
| Concentração por credor | NÃO EXISTE | bloqueada por governança |

### 5.2 Funcionalidades da interface

| Funcionalidade | Classificação | Observação |
|---|---|---|
| Filtros (exercício, corte, entidade, como estava em, categoria, fonte de recurso, programação, tipo de credor, CNPJ de PJ) | **EXIBIDO** | |
| Filtro por órgão, função, programa ou elemento | NÃO EXISTE | |
| Busca por ano e número do empenho | **EXIBIDO** | |
| Busca por nome de credor | NÃO RECOMENDADO | dados pessoais |
| Paginação | **EXIBIDO** | 50 por página |
| Comparação temporal | EXISTE PARCIALMENTE | retratos do mesmo corte e "como estava em"; entre cortes, não |
| Detalhamento do empenho | **EXIBIDO** | |
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
| Atualização da base | EXISTE PARCIALMENTE | procedimento documentado na 04.6; **nunca executado de ponta a ponta** |
| Processamento | **EXISTE** | `processar`, `--em` |
| Portões | **EXISTE** | `portoes`; o portão de testes é manual |
| Backups | **EXISTE** | antes de migração e de exclusão; sem retenção global |
| Reconstrução | **EXISTE** | comprovada em ambiente limpo |
| Instalação | **EXISTE** | só Windows com Python 3.14.3 comprovados |
| Configuração | **EXISTE** | portátil (`~`, `RP_DADOS_LOCAIS`) |
| Testes | EXISTE PARCIALMENTE | 257 + 26, executados à mão; sem CI |
| CI, lint, verificação de tipos | NÃO EXISTE | |
| Agendamento e alertas | NÃO EXISTE | |
| Servidor de produção, HTTPS, autenticação | NÃO EXISTE | |

### 5.4 Medições feitas para este plano (somente leitura, banco ativo)

| Tema | Medição |
|---|---|
| Cortes | 22 cortes processados: 2016–2024 só 31/12; 2025 com 6 bimestres; 2026 com 7 cortes, dos quais 31/01, 31/03 e 31/12 só da entidade 1 (Município indisponível) |
| Janela de coleta | os cortes vigentes foram coletados entre 29/09/2026 20h11 e 30/09/2026 01h22. A comparação entre cortes é uma fotografia coerente da base nessa janela. |
| Retratos | 28 cortes com mais de um retrato, todos com bytes idênticos ao anterior |
| Inscrição entre cortes do mesmo exercício | igual em todos os cortes de 2025 (Município, entidades 1 e 15) e de 2026 (entidade 1 e Município): mesma inscrição e mesmo número de registros. A premissa da 05.2 vale hoje |
| Dimensões (2025-12-31, Município) | entidade 5 grupos; ano do empenho 13; categoria 3; fonte de recurso 150; programação 688; órgão 28; unidade 112; função 20; subfunção 43; programa 69; projeto 351; elemento 49; 16 registros sem classificação orçamentária |
| Credores por tipo (2025-12-31) | PJ: 3.947 registros; PF: 1.931 registros |
| RREO extraído | 2017 e 2020–2024 (6º bimestre, entidade e consolidado); 2025 com 6 bimestres; 2026 com 4. Não lidos: 2016 (entidade), 2018 e 2019 (layout desconhecido) |
| Anomalias (derivação 23) | COPIA-24 17.434; LIQ-NEG 2.096; PAGOPROC-SEM-PROC 99; PAR-INSCRICAO-DIVERGENTE 55 |
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
- B1: diferença entre cortes consecutivos, como natureza "diferença" (P1).
- B2: série histórica por exercício (P2).
- B3: composição por categoria e faixa (P3).
- B4: composição por dimensão (P4).
- B5: comparação entre entidades (P5).

**C. Investigação**
- C1: empenhos que explicam a variação entre dois cortes do mesmo exercício (P6).
- C2: relação entre o fechamento de A e a abertura de A+1, como verificação (P7).
- C3: histórico de um empenho através dos cortes (P8).
- C4: painel de qualidade dos dados, com anomalias e verificações (P12).
- C5: resumo das diferenças com o RREO por situação (P9).

**D. Dados**
- D1: primeira atualização real da base pelo procedimento documentado.
- D2: cortes bimestrais de 2016–2024.
- D3: movimentação de mais empenhos.
- D4: RREO de outras entidades e bimestres, e layouts de 2016, 2018 e 2019.

**E. Automação**
- E1: coleta agendada.
- E2: processamento automático.
- E3: portões automáticos.
- E4: alertas.

**F. Engenharia**
- F1: CI rodando as suítes.
- F2: lint e tipos.
- F3: dependências com hash.
- F4: testes dos scripts de lote.
- F5: unificação das implementações de regra (investigação × produção).
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
| **B1/A1 evolução no exercício** | Dados prontos e já calculados pelo painel (`evolucao`). As regras são operacionais. O recálculo independente a partir do bruto já existe nos testes da 04.6. Risco quase nulo: só exibe consulta existente mais uma subtração. **Primeira a entrar.** |
| **B2/A2 série entre exercícios** | Dados prontos (cortes de 31/12). Valor alto. O risco é de **interpretação** (estado atual × época), resolvido por rótulo, não por cálculo. Entra logo depois da B1, reaproveitando a mesma forma de série. |
| **B3/B4/A3/A5 composição** | Regras operacionais (CAT, FAIXA) e somas de campos da API. `por_dimensao` existe. Validação simples: as partes somam o total. Exige o tratamento explícito de "sem classificação". |
| **C1/C3 investigação de variação** | Valor alto, mas é a única oportunidade que pede consulta realmente nova (casamento de registros entre cortes). Entra depois das séries, porque responde "por quê" a uma variação que o usuário primeiro precisa ver. Validação exige que a soma das contribuições feche exatamente com a variação total. |
| **C2/C4/C5 qualidade e verificações** | Dados prontos na derivação, mas fora da camada de consulta. Valor de auditoria. Baixo risco: leitura de tabelas existentes, sem regra nova. |
| **B5 comparação entre entidades** | Sai das mesmas séries por entidade (B1, B2). Exige aviso das cópias 24xxxxx (as entidades 1 e 15 têm registros espelhados). Não precisa de subetapa própria. |
| A4 gráficos | Só depois que a série e a tabela existirem e estiverem homologadas. O gráfico é apresentação de um dado já validado, nunca o contrário. |
| D, E, F | Fora da Etapa 05 (seção 8), exceto testes novos de cada subetapa. D1 é uma decisão do responsável (seção 10). |

**Sequência que aumenta a utilidade sem pôr em risco a confiabilidade:**
1. contrato e validação;
2. evolução no exercício;
3. série entre exercícios;
4. composição;
5. investigação de variações;
6. qualidade dos dados;
7. homologação.

Cada passo só exibe ou combina valores que o passo anterior já validou.

## 8. Fora da Etapa 05

| Item | Motivo |
|---|---|
| Novas coletas (D1–D4), salvo decisão expressa do responsável | dependem da API não documentada; geram snapshots; a D1 é avaliada como decisão à parte (seção 10) |
| Automação (E1–E4) | o procedimento manual nunca foi executado de ponta a ponta; analisado como trilha futura na seção 16.2 |
| Servidor de produção, HTTPS, autenticação, publicação externa | infraestrutura; precisa de homologação no ambiente de destino |
| Concentração e ranking por credor identificado (P11) | governança de dados pessoais; a 04.5 vedou ranking e tela pública de fornecedores |
| Consolidação dos pares 24xxxxx (CONS-PAR) ou qualquer "correção" da dupla contagem | natureza das cópias **não determinada**; depende do e-SIC; regra experimental |
| Promoção de regra experimental ou não recomendada (RREO-COL v1/v2, CANC v1, CONS-PAR) | sem critério nem evidência nova |
| Explicar automaticamente diferenças "não determinadas" com o RREO | proibido transformar diferença não explicada em regra |
| Divisão de cancelamentos em processado e não processado como indicador | CANC v1 não recomendada |
| Nova versão de qualquer regra da derivação | mudaria o `hash_resultado`; a Etapa 05 só consome a camada 2 existente |
| Extrator de RREO para os layouts de 2016, 2018 e 2019 | pesquisa de layout; trilha RREO própria |
| CI, lint, tipos, hash de dependências, empacotamento (F1–F3, F7) | engenharia; etapa própria ou antes da publicação externa |
| Unificação das implementações de regra (F5) | arriscaria os hashes; precisa de etapa dedicada |

## 9. Subetapas propostas

Cada subetapa termina com homologação e **parada para aprovação**. Nenhuma altera snapshot, normalização, derivação, regra ou valor já exibido. Os critérios comuns de homologação estão na seção 11; abaixo vai só o que é próprio de cada uma.

### 9.0 Princípios para gráficos (valem para 05.2 a 05.5)

- **Pergunta antes do gráfico:** um gráfico só entra se responde a uma pergunta da seção 4 (P1–P5). Nada decorativo.
- **Tabela sempre:** todo gráfico vem com a tabela de valores exatos (`<data value>` em centavos). A tabela é a fonte da verdade e a alternativa acessível.
- **Unidade, período e escopo explícitos:** R$ (centavos na máquina); exercício e corte de cada ponto; Município ou entidade.
- **Ausência não é zero:** dado indisponível (corte não coletado ou Município incompleto) vira lacuna rotulada, nunca ponto zero. Zero de verdade (entidade existente sem RP) é desenhado como zero e rotulado como tal.
- **Proveniência:** cada ponto liga para a tela do corte, com retrato, snapshots e derivação. O gráfico não tem cálculo próprio.
- **Do ponto ao registro:** de um ponto ou barra, o usuário chega à lista de empenhos daquele corte e escopo, e à investigação da variação (05.5).
- **Técnica:**
  - Restrições atuais: sem JavaScript, CSP `default-src 'none'`, sem CDN, sem dependência nova de execução.
  - Candidato compatível: SVG gerado no servidor, só com atributos de apresentação (sem `style` embutido, que a CSP bloqueia).
  - Nenhuma biblioteca é escolhida neste plano. A decisão fica para a 05.1, com justificativa.

### 05.1 — Contrato analítico e base de validação

- **Objetivo:** fixar, antes de qualquer tela, a definição de cada série, diferença e composição da Etapa 05, e a técnica de apresentação.
- **Problema que resolve:** evita que a interface invente cálculo e que um indicador entre "porque faz sentido".
- **Dados:** nenhum dado novo.
- **Componentes afetados:**
  - documento `etapa05/CONTRATO_ANALITICO.md`;
  - testes;
  - nenhum código de produção, salvo utilitários de teste.
- **Conteúdo:**
  - para cada métrica nova, as 9 respostas da seção 9.1;
  - qual corte representa cada exercício na série (31/12; em 2026, o último corte com Município disponível, rotulado "exercício em aberto");
  - textos obrigatórios de retrato;
  - decisão sobre a técnica de gráfico, com justificativa.
  - nos testes: generalizar o recálculo independente a partir do JSON bruto (`test_homologacao_real.py`) para séries de cortes e para diferenças;
  - nos testes: fixar os valores esperados da linha de base.
- **Dependências:** aprovação deste plano.
- **Risco:** baixo.
- **Testes:**
  - o recálculo independente reproduz `Painel.evolucao` e `Painel.indicadores` em todos os 22 cortes;
  - as suítes existentes continuam passando.
- **Critério de aceitação:** contrato aprovado pelo responsável; a ferramenta de validação cobre todos os cortes; nenhum valor exibido muda.
- **Critério de parada:** se alguma métrica proposta não puder ser recalculada independentemente do painel, ela sai do escopo.

### 05.2 — Evolução dentro do exercício

- **Objetivo:** mostrar, para Município ou entidade, a série dos cortes de um exercício (inscrição, pagamentos, liquidações, cancelamentos, saldo S1) e a diferença entre cortes consecutivos.
- **Problema que resolve:** P1.
- **Dados:** `Painel.evolucao`, em 2025 (6 cortes) e 2026 (7 cortes; Município em 4).
- **Componentes afetados:**
  - camada painel: diferença entre cortes, natureza `diferenca`, com os snapshots dos dois cortes;
  - interface: tela ou seção nova;
  - opcionalmente, o gráfico.
- **Dependências:** 05.1.
- **Risco:** baixo.
  - Cuidado 1: corte com Município indisponível vira lacuna e não entra em diferença.
  - Cuidado 2: a inscrição deve ser igual em todos os cortes do exercício. Se não for (mudança retroativa), isso é mostrado como diferença, nunca escondido.
- **Testes:**
  - recálculo do bruto de cada ponto e de cada diferença;
  - lacunas em 2026 (31/01, 31/03, 31/12) sem zero;
  - proveniência de cada ponto;
  - responsividade da série.
- **Critério de aceitação:** série = painel = bruto em todos os cortes de 2025 e 2026, para o Município e cada entidade; nenhum ponto inexistente vira zero.
- **Critério de parada:** se a inscrição variar entre cortes do mesmo exercício sem explicação, parar e documentar antes de exibir a série.

### 05.3 — Série histórica entre exercícios (2016–2026)

- **Objetivo:** série por exercício (inscrição na abertura, pagamentos, cancelamentos, saldo no fechamento), para Município e entidade, mais a verificação "saldo final de A × inscrição de A+1".
- **Problema que resolve:** P2, P5 e P7.
- **Dados:**
  - cortes de 31/12 de 2016–2025;
  - 2026 como exercício em aberto (último corte do Município: hoje 31/08);
  - verificação de continuidade da derivação (tabela `verificacao`, 0 falhas).
- **Componentes afetados:**
  - camada painel: série por exercício composta de `indicadores`, e leitura das verificações;
  - interface: tela ou seção.
- **Dependências:** 05.2 (mesma forma de série).
- **Risco:** médio, de **interpretação**. Todo ano passado é "estado atual da base para o exercício, coletado em 30/09/2026", não o que se publicava na época. Entidade fora do catálogo de um exercício não é zero (entidade 15 antes de 2019; entidade 10 depois de 2022).
- **Testes:**
  - recálculo do bruto por exercício;
  - continuidade = verificação da derivação;
  - rótulos de retrato em todos os pontos;
  - entidades fora do catálogo como lacuna.
- **Critério de aceitação:** série = painel = bruto em 2016–2026; nenhum texto sugere "como era na época".
- **Critério de parada:** qualquer falha de continuidade nova, ou divergência entre a série e os indicadores homologados.

### 05.4 — Composição do saldo

- **Objetivo:** decompor o saldo e a inscrição de um corte por:
  - categoria (CAT v1);
  - faixa (FAIXA v1: inscritos no exercício anterior × em exercícios anteriores);
  - tipo de credor;
  - dimensões orçamentárias (fonte de recurso, função, programa, órgão, elemento).

  Cada parte leva à lista de empenhos correspondente.
- **Problema que resolve:** P3 e P4.
- **Dados:** `rp_derivado` (CAT, FAIXA) e `Painel.por_dimensao`.
- **Componentes afetados:**
  - camada painel: composição por faixa, filtros por dimensão em `_filtros_empenho`;
  - interface: tabelas de composição e novos filtros.
- **Dependências:** 05.1.
- **Risco:** baixo a médio. A composição por faixa usa as mesmas letras das colunas do RREO; deve ser rotulada "composição dos registros da API pela regra FAIXA v1", nunca "colunas do RREO".
- **Testes:**
  - soma das partes = total, ao centavo, em todo corte;
  - grupo "sem classificação" presente e com contagem;
  - cada parte leva a uma lista cujo total é a própria parte;
  - recálculo do bruto.
- **Critério de aceitação:** fechamento exato das partes em todos os cortes; drill-down coerente.
- **Critério de parada:** se alguma dimensão não fechar com o total, ela não é exibida até a causa ser explicada.

### 05.5 — Investigação de variações

- **Objetivo:**
  1. Para dois cortes do mesmo exercício (Município ou entidade), listar os empenhos que mais contribuem para a variação de saldo e de pagamentos.
  2. Mostrar o histórico de um empenho através dos cortes em que ele aparece.
- **Problema que resolve:** P6 e P8.
- **Dados:** `rp_registro` e `rp_derivado` dos snapshots vigentes dos dois cortes, casados pela chave (entidade, ano, empenho).
- **Componentes afetados:** camada painel (consulta nova, paginada e somente leitura) e interface (tela de variação; seção "histórico nos cortes" no detalhe).
- **Dependências:** 05.2 (de onde o usuário parte) e 05.1.
- **Risco:** médio, porque é a primeira consulta que casa registros de snapshots diferentes. Registros presentes só num dos cortes (por exemplo, cópias 24xxxxx inseridas depois) entram como classes explícitas, "novo no corte posterior" e "ausente no corte posterior", e não como zero.
- **Testes:**
  - Σ contribuições = variação total, ao centavo, em todos os pares de cortes consecutivos de 2025 e 2026;
  - recálculo independente do bruto;
  - casos com chave presente só de um lado;
  - casos reais (5659/2025, 2401751/2023);
  - desempenho com o corte inteiro.
- **Critério de aceitação:** fechamento exato; nenhuma contribuição sem proveniência dos dois snapshots.
- **Critério de parada:** se aparecer chave duplicada num snapshot, ou se o fechamento falhar, parar e investigar antes de exibir.

### 05.6 — Qualidade dos dados e situação das diferenças

- **Objetivo:**
  1. Expor na camada de consulta e na interface as anomalias e as verificações que a derivação já grava: continuidade, pareamento e colunas conciliadas.
  2. Um resumo das diferenças com o RREO por situação (sem diferença, explicada, parcialmente explicada, não determinada).
- **Problema que resolve:** P9 e P12, além da transparência sobre o que o projeto ainda não sabe.
- **Dados:** tabelas `anomalia`, `anomalia_tipo`, `verificacao`, `conciliacao_rreo`; `explicacoes.py`.
- **Componentes afetados:** camada painel (leituras novas) e interface (tela "Qualidade dos dados").
- **Dependências:** 05.1.
- **Risco:** baixo. O cuidado é de linguagem: anomalia não é erro, e diferença não determinada não é falha do Município.
- **Testes:**
  - contagens iguais às das tabelas da derivação;
  - cada anomalia leva ao empenho;
  - nenhuma diferença "não determinada" aparece como explicada.
- **Critério de aceitação:** números iguais aos da derivação; linguagem neutra; nenhuma regra nova.
- **Critério de parada:** se a exibição exigir reinterpretar uma anomalia, documentar e não exibir a interpretação.

### 05.7 — Homologação e encerramento da Etapa 05

- **Objetivo:** homologar o conjunto.
- **O que entra:**
  - regressão completa;
  - estado antes × depois: os 5.575 valores homologados da 04.6 inalterados, mais os novos valores conferidos;
  - instalação limpa;
  - responsividade e acessibilidade das telas novas;
  - relatório final;
  - tag `etapa-05-final`.
- **Critério de aceitação:** seção 17.

O agrupamento é deliberado. Comparação entre entidades (B5) não tem subetapa própria: sai das séries de 05.2 e 05.3. Gráficos não têm subetapa própria: cada um entra na subetapa da pergunta que responde, depois da tabela homologada.

### 9.1 Regras para qualquer indicador ou métrica nova

Nenhuma métrica entra sem estas respostas, registradas no contrato analítico (05.1):

1. **Fonte:** API Elotech; RREO só na reconciliação.
2. **Regra:** fórmula e versão.
3. **Classe da regra:** contábil e operacional, analítica ou experimental. Só operacional compõe indicador.
4. **Já existe?** Em que método do painel.
5. **Recálculo independente:** pode ser recalculada a partir do JSON bruto? Se não puder, não entra.
6. **Validação:** como, e com que tolerância. Sempre zero: centavos inteiros.
7. **Risco de mascarar a fonte:** a métrica pode esconder um problema da fonte? Por exemplo, uma diferença que esconde mudança retroativa, ou uma soma que esconde a dupla contagem dos pares.
8. **Proveniência exibida:** derivação, normalização e snapshots de cada operando.
9. **Casos extremos:**
   - corte indisponível;
   - zero verdadeiro;
   - entidade fora do catálogo;
   - registro só de um lado;
   - pares 24xxxxx;
   - valores negativos (LIQ-NEG);
   - "sem classificação".

**Métricas previstas** (todas de regra já operacional, ou subtração de valores já validados):

| Métrica | Fonte e regra | Classe | Existe hoje? |
|---|---|---|---|
| Diferença entre cortes | API; subtração de somas (S1 e campos) | `diferenca` | não |
| Série por exercício | API; `indicadores` por corte de fechamento | `derivado` | em parte (`evolucao` é só no exercício) |
| Composição por categoria e faixa | API; CAT v1, FAIXA v1 | `derivado` | em parte |
| Composição por dimensão | API; soma por campo | `derivado` | sim (`por_dimensao`) |
| Contribuição por empenho | API; diferença por chave | `diferenca` | não |
| Continuidade fechamento → abertura | derivação (ANOM-CONT v1, operacional, não compõe indicador) | verificação, não indicador | na derivação, fora da camada |

## 10. Dependências e decisões do responsável

| Decisão | Opções | Recomendação |
|---|---|---|
| Integração da Etapa 04 no `main` (PRs #1 → #2 → #3) | antes ou durante a Etapa 05 | **antes**, para que os PRs da Etapa 05 mostrem só o próprio trabalho |
| Aprovação deste plano e da ordem das subetapas | — | condição para iniciar a 05.1 |
| D1: primeira atualização real da base (procedimento manual da 04.6) | fazer como subetapa extra da Etapa 05, adiar ou deixar fora | não é necessária para 05.1–05.6. Exercita o procedimento e daria os primeiros casos reais de mudança entre retratos. Recomendação: decidir antes da 05.7 |
| Técnica de gráfico | decidida na 05.1 | sem dependência nova de execução, salvo justificativa aprovada |
| Concentração por credor | manter fora ou abrir decisão de governança | manter fora |

## 11. Critérios de homologação (toda subetapa)

```text
IMPLEMENTAÇÃO
    ↓
TESTE UNITÁRIO (sintético, situações que o dado real não tem)
    ↓
TESTE REAL (armazém real, fixture `real`)
    ↓
VALIDAÇÃO INDEPENDENTE (recálculo a partir do JSON bruto: bruto = painel = tela)
    ↓
VERIFICAÇÃO DE PROVENIÊNCIA (todo valor novo → derivação → snapshot → objeto bruto)
    ↓
VERIFICAÇÃO DA INTERFACE (celular, tablet, notebook, desktop; acessibilidade básica; sem rede)
    ↓
HOMOLOGAÇÃO (suítes completas + verificar + portoes + estado antes × depois)
```

- **Testes junto com o código:** os testes de cada camada são escritos junto com ela, não no fim da subetapa.
- **Toda subetapa termina com:**
  - suítes de produção e da investigação passando;
  - `verificar` limpo e `portoes` apto;
  - comparação de estado (`etapa04/resultados/04_6_estado.py` e `04_6_comparar_estados.py`) sem nenhuma diferença nos valores homologados;
  - relatório próprio em `etapa05/`;
  - commit exclusivo;
  - parada para aprovação.

## 12. Riscos

| Risco | Efeito | Mitigação |
|---|---|---|
| Ler série histórica como "o que se sabia na época" | conclusão errada sobre gestões passadas | rótulo de retrato obrigatório em todo ponto; texto da metodologia |
| Dupla contagem dos pares 24xxxxx nas séries de 2025–2026 | soma das entidades 1 e 15 parece maior | aviso explícito em toda série e comparação entre entidades; nenhuma consolidação (CONS-PAR experimental) |
| Diferença entre cortes coletados em momentos diferentes | mistura movimento do período com mudança retroativa | hoje todos os cortes são da mesma janela (29–30/09); depois de uma coleta nova, a diferença mostra as datas de coleta dos dois lados |
| Gráfico esconder lacuna ou zero | "ausência = zero" volta pela apresentação | princípios da seção 9.0; testes de lacuna |
| Lógica contábil migrar para a interface | perda da garantia homologada | teste da 04.6 que proíbe aritmética em centavos na interface continua valendo; métricas só na camada painel |
| Consulta nova pesada (casamento de cortes) | lentidão | paginação; medição antes e depois; índice só se uma medida pedir |
| Dependência da API não documentada | — | a Etapa 05 não coleta (salvo D1); trabalha sobre os snapshots |
| Escopo crescer | etapa não fecha | seção 8; critério de parada em cada subetapa |

## 13. Estratégia de preservação dos dados

- A Etapa 05 **só lê**: camada painel e interface continuam somente leitura (`mode=ro` + `query_only`).
- Nenhuma subetapa altera snapshots, normalização, derivação, regras ou parâmetros. O `hash_resultado` (`2f6b4e29…`, `b8a0b2ed…`) e o `hash_camada0` (`733670693c01d015…`) devem continuar iguais ao fim de cada subetapa.
- Métrica nova é consulta da camada painel sobre a camada 2 existente. Se uma métrica exigir mudança na derivação, ela sai da Etapa 05 e vira proposta própria, com versão nova de regra e novo hash documentado.
- Os 5.575 valores de tela homologados na 04.6 são conferidos sem mudança ao fim de cada subetapa.

## 14. Estratégia de proveniência

- Todo valor novo sai da camada painel com natureza, regras e sua situação, retrato e proveniência (`_prov_curta` / `_proveniencia`).
- Diferença e contribuição carregam a proveniência dos **dois** lados: snapshots, derivação e normalização.
- Ponto de série e linha de composição levam à tela do corte e à lista de registros, onde cada registro chega ao objeto bruto (cadeia homologada na 04.6).
- Teste obrigatório por subetapa: nenhum valor novo sem proveniência navegável até um snapshot que exista no armazém.

## 15. Estratégia de regressão

- **Suítes:** as suítes atuais (257 + 26) rodam a cada subetapa e precisam continuar passando sem ajuste. Ajuste de teste existente só com justificativa no relatório, como na 04.6.
- **Testes reais novos:** cada subetapa acrescenta testes reais com recálculo do bruto e casos fixados (valores da linha de base de 2024, 2025 e 2026 já fixados na 04.6).
- **Estado:** comparação antes × depois por subetapa, com os scripts da 04.6.
- **Instalação limpa:** repetida na 05.7.

## 16. Possíveis evoluções futuras

### 16.1 Trilha RREO
- **Cobertura atual:**
  - entidade 1 e consolidado;
  - 6º bimestre em 2017 e 2020–2024;
  - todos os bimestres de 2025;
  - 4 bimestres de 2026.
- **Lacunas:** 2016 (entidade), 2018 e 2019 sem extração (layout); demais entidades sem RREO individual; 2016–2024 só o 6º bimestre.
- **Evolução possível:** extratores versionados novos para os layouts antigos e coleta de mais bimestres, sempre como fonte de reconciliação.
- **Regra fixa:** diferença não explicada nunca vira regra automática, e regra experimental não é promovida sem critério documentado.

### 16.2 Automação (análise; não implementar antes do procedimento manual ser executado ao menos uma vez)

| Tema | Situação | O que exigiria |
|---|---|---|
| Periodicidade | os cortes bimestrais acompanham o RREO | definir calendário (ex.: depois de cada bimestre) |
| Dependências externas | API não documentada, sem contrato | tolerância a mudança de formato; parar e alertar, nunca adaptar sozinho |
| Falhas da API | coleta incompleta fica registrada e não vira retrato válido | repetição limitada; portão `coleta_completa` |
| Idempotência | cada coleta é um snapshot novo; objetos idênticos não se duplicam (endereçados por conteúdo) | aceitar retratos repetidos; comparar com o anterior |
| Snapshots | append-only | retenção nunca apaga snapshot |
| Portões | `portoes` existe; o de testes é manual | rodar suítes e portões antes de disponibilizar |
| Alertas | inexistentes | canal a definir |
| Rollback | a interface lê a derivação atual mais recente | "não disponibilizar" = não processar ou manter a derivação anterior; apagar execução só pelo comando protegido |
| Logs e retenção | logs diários sem retenção; backups grandes | política de retenção (revisão de código, itens 27–29 e 42) |

### 16.3 e-SIC (quando houver resposta)

1. Registrar a resposta com `registrar-evidencia` (SHA-256, manifesto, `evidencia_externa`).
2. Rever as explicações (`explicacoes.py`) e as decisões de governança (`regra_situacao`) que a resposta afetar, citando a evidência.
3. Nunca reescrever valores passados. Se a resposta justificar uma regra (por exemplo, consolidação dos 24xxxxx), ela entra como **versão nova**, com nova derivação, novo hash e homologação própria.

**Temas que a resposta pode esclarecer:**
- natureza das cópias 24xxxxx e data de inclusão;
- colunas (h) e (i) de 2026;
- lançamentos retroativos;
- classificação de liquidação estornada;
- situação oficial da consulta de RP.

### 16.4 Engenharia e publicação
- CI com as suítes, lint e tipos.
- Dependências com hash.
- Testes dos scripts de lote.
- Unificação das implementações de regra.
- Empacotamento.
- Servidor WSGI de produção, HTTPS e controle de acesso.
- Homologação em outro sistema e em outra versão do Python.
- Decisão sobre dados pessoais no repositório público e sobre a licença AGPL do PyMuPDF.

## 17. Critério de encerramento da Etapa 05

A Etapa 05 estará encerrada quando:

1. As perguntas P1–P9 e P12 tiverem resposta na interface, cada uma com tabela de valores exatos, retrato e proveniência.
2. Toda métrica nova estiver no contrato analítico com as 9 respostas da seção 9.1, e estiver validada por recálculo independente do bruto.
3. Nenhum indicador usar regra experimental ou não recomendada, e nenhuma diferença não determinada aparecer como explicada.
4. A interface continuar sem cálculo contábil; o teste que proíbe aritmética em centavos na interface continuar passando.
5. As suítes de produção e da investigação passarem, `verificar` estiver limpo e `portoes` apto.
6. Snapshots, normalização, derivação, `hash_resultado` e `hash_camada0` estiverem iguais aos de `etapa-04-final`, e os valores homologados na 04.6 estiverem inalterados.
7. Telas novas estiverem verificadas em celular, tablet, notebook e desktop, com acessibilidade básica e funcionando sem rede.
8. A instalação limpa tiver sido repetida.
9. O relatório final da Etapa 05 estiver escrito, com as limitações abertas, e existir a tag `etapa-05-final`.
10. Nada da seção 8 tiver sido implementado sem decisão expressa do responsável.
