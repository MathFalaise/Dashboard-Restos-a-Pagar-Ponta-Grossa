# Contrato analítico da Etapa 05 (Subetapa 05.1)

Data: 01/10/2026. Ramo `subetapa-05.1`, sobre o plano aprovado (`etapa05/PLANO_ETAPA05.md`, commit `988a7cc`), base `etapa-04-final` (`a6bd27c`).

Este documento é o contrato que as subetapas 05.2 a 05.6 implementam. Nenhuma métrica, série, composição ou tela da Etapa 05 pode ser implementada fora dele.
- Mudar o contrato exige revisão aprovada.
- Uma métrica que não couber nele sai do escopo, pelo critério de parada da 05.1.

A ferramenta de validação independente que o acompanha está em `app/tests/recalculo_bruto.py`, e os testes que fixam o contrato em `app/tests/test_contrato_05_1.py`.

**A 05.1 não muda código de produção** (plano, seção 05.1). Toda regra abaixo marcada "a implementar" pertence à subetapa indicada.

---

## 1. Princípios fixos

1. **Arquitetura:**
   - O cálculo novo fica na camada painel (`app/rp/painel`) e lê só a camada 2 existente.
   - A interface só apresenta; o teste da 04.6 que proíbe aritmética em centavos na interface continua valendo.
   - Expressão usada em mais de um lugar vira constante única na camada painel (como `EXPR_CANCELAMENTOS`).
2. **Somente leitura:** nenhuma métrica altera snapshot, normalização, derivação, regra, `hash_resultado` ou `hash_camada0`.
3. **Unidade:** centavos inteiros (`int`) em todo cálculo e comparação. R$ aparece só na exibição. Não há `float`, arredondamento nem tolerância.
4. **Ausência nunca é zero:** um valor só existe nas situações `com_dados` e `sem_rp` (seção 2). Nas demais, o valor é `None`, e o ponto aparece com a situação.
5. **Sinal:** toda diferença é **posterior − anterior** (ou a comparação definida na métrica). Nunca valor absoluto.
6. **Retrato histórico:** um corte de exercício passado é o **estado atual da base para aquele corte**, na data da coleta. Nunca "o que se sabia na época". Texto obrigatório: "Estado atual da base para o exercício de {A}, corte {DD/MM/AAAA}, coletado em {DD/MM/AAAA}" (o texto que `Painel._retrato` já gera).
7. **Pares 24xxxxx:** os registros continuam como a API devolve. Nenhuma métrica soma "entidade 1 + entidade 15" como total corrigido, nem usa CONS-PAR.
8. **Regras:** só regras `operacional` que compõem indicador entram em métrica `derivado`. Regra experimental ou não recomendada não entra em nenhuma métrica da Etapa 05.

## 2. Contrato de disponibilidade

### 2.1 Taxonomia única

A Etapa 05 **estende** a taxonomia existente (`consulta.SITUACOES_DO_DADO`, por entidade). Não cria outra.

| Código | Situação | Escopo | Já existe? | Tem valor? |
|---|---|---|---|---|
| `com_dados` | dado disponível | entidade e Município | sim (entidade) | sim |
| `sem_rp` | zero verdadeiro: a entidade existia e a API devolveu 0 registros | entidade e Município | sim (entidade) | sim: **0**, rotulado "sem RP neste corte" |
| `inexistente` | entidade fora do catálogo oficial do exercício | entidade | sim | não |
| `sem_coleta` | corte não coletado | entidade | sim | não |
| `nao_processado` | corte coletado, mas não processado | entidade | sim | não |
| `incompleto` | dado indisponível: só coleta incompleta ou com falha | entidade | sim | não |
| `municipio_indisponivel` | alguma entidade do catálogo do exercício sem snapshot processado no corte | Município | **a implementar (05.2)**; hoje é `indicadores(...).disponivel = False` + `motivo_indisponivel` | não |
| `exercicio_sem_cobertura` | nenhuma coleta de listagem do exercício no banco | entidade e Município | **a implementar (05.3)**; hoje aparece como indisponível genérico | não |

- **Corte posterior à coleta** (R4) não é situação. É um **rótulo adicional** de um ponto com valor (`retrato.corte_posterior_a_coleta`, já existente): "valores até a data da coleta".
- **Divergente** (`SITUACOES_DO_DADO["divergente"]`) qualifica a comparação com o RREO, não a disponibilidade de um ponto. Não entra nesta taxonomia.

### 2.2 Precedência (determinística)

Quando mais de uma situação se aplica, vale a primeira da lista.

| Escopo | Ordem |
|---|---|
| Entidade | `inexistente` → `exercicio_sem_cobertura` → `nao_processado` → `incompleto` → `sem_coleta` → `sem_rp` → `com_dados` |
| Município | `exercicio_sem_cobertura` → `municipio_indisponivel` → `sem_rp` (todas as entidades do total com 0 registros) → `com_dados` |

Justificativa:
- `inexistente` vem primeiro porque é um fato do catálogo oficial, independente de coleta.
- `exercicio_sem_cobertura` vem antes das situações do corte porque explica todas elas de uma vez.
- `nao_processado` → `incompleto` → `sem_coleta` é a ordem que `Painel._estado_sem_snapshot` já usa.

### 2.3 Representação de um ponto (a implementar na 05.2)

```text
ponto = {
  exercicio, data_final, escopo (entidade ou None = Município),
  situacao: {codigo, texto},          # seção 2.1
  tem_valor: codigo in (com_dados, sem_rp),
  valores: {...} se tem_valor, senão None (nunca 0),
  entidades: [situação de cada entidade] (Município),
  rotulos: ["corte posterior à coleta"] quando aplicável,
  retrato, proveniencia               # seções 3 e 1.6
}
```

### 2.4 Universo de pontos (contrato do R1)

- **Série dentro do exercício:** todos os cortes processados do exercício, para **qualquer** escopo. É a lista de `Painel.cortes()` filtrada pelo exercício (hoje: 2025 com 6 cortes; 2026 com 7).
  - A série de uma entidade tem **exatamente** esse universo.
  - Corte em que a entidade não tem snapshot aparece com a situação dela (hoje, `sem_coleta`), nunca é omitido.
- **R1 (pendência, não resolvida):** `Painel.evolucao(exercicio, entidade)` hoje omite esses cortes. Em 2026, as entidades 5 e 15 aparecem só em 4 cortes; 31/01, 31/03 e 31/12 somem.
  - A correção funcional é da 05.2 e será homologada lá.
  - A 05.1 só fixa o contrato, e testa que todo ponto do universo é **representável** com o código atual (`cortes()` + `entidades_do_corte()`).
- **Série entre exercícios:** todos os exercícios de 2016 a 2026, cada um no corte representativo (seção 2.5).
- **Observação:** cortes só coletados, sem nenhum processamento, não entram no universo.
  - Em base disponibilizada isso não ocorre, porque o portão `normalizacao` do `python -m rp portoes` exige 0 snapshots sem processar.
  - Mesmo assim, a camada painel deve continuar avisando quando houver snapshots não processados (aviso já existente em `indicadores`).

### 2.5 Corte representativo de cada exercício (R8; a implementar na 05.3)

- **Regra:** 31/12 do exercício, se o Município estiver disponível nele; senão, o último corte do exercício com Município disponível, rotulado "exercício em aberto".
- **Mesmo corte para todos os escopos.**
- **Hoje:** 31/12 para 2016–2025 e 31/08 para 2026.
- **Sem nenhum corte com Município disponível:** o exercício é lacuna para todos os escopos.

### 2.6 Diferença entre pontos (R9)

- Só entre pontos **adjacentes** do universo.
- Se um dos dois não tiver valor, a diferença é `None`, com o motivo do ponto indisponível.
- Nunca "pula" lacuna. Comparar cortes não adjacentes é escolha explícita na 05.5.

## 3. Contrato de proveniência

Toda métrica numérica nova devolve, da camada painel, a proveniência no formato que já existe (`Painel._prov_curta` e `Painel._proveniencia`):

| Campo | Conteúdo | Origem existente |
|---|---|---|
| `snapshots` | `snapshot_uid` de cada coleta usada (cada um com manifesto no armazém) | `_uids`, `_snapshot` |
| `derivacao_id`, `derivacao_hash` | derivação atual e seu `hash_resultado` | `contexto()` |
| `normalizacao_id` | normalização da derivação | `contexto()` |
| `consulta` | fórmula em texto (a da métrica, seção 5) | — |
| `regras` | regras usadas, com situação de governança | `_regras_publicaveis` |
| retrato | exercício, corte, data da coleta, tipo (atual ou "como estava em") | `_retrato` |

Regras adicionais:
- **Diferença e contribuição:** proveniência **dos dois lados** (`anterior` e `posterior`).
- **Contribuição por empenho:** também o registro de cada lado (resposta HTTP, posição no `content[]`, SHA-256 do objeto bruto), como `_registros` já devolve.
- **Composição:** a de cada grupo é a do corte, mais o filtro que leva à lista de registros do grupo.
- **Anomalia e verificação:** regra (código e versão), derivação e, quando houver, coleta (`anomalia.coleta_id`) ou snapshots do escopo (`verificacao.escopo_json`).
- **Critério objetivo:** todo `snapshot_uid` citado existe em `coleta` e tem manifesto no armazém; `derivacao_id` e `derivacao_hash` são os de `contexto()`.

## 4. Contrato de validação e de fechamento

### 4.1 Dois regimes (plano, seção 9.4)

| Objeto | Regime | Como |
|---|---|---|
| Métrica numérica nova (seção 5) | **bruto** | `app/tests/recalculo_bruto.py` recalcula a partir do JSON bruto do armazém, sem usar `rp.painel`, `rp.derivar` nem `rp.normalizar`, e compara com o painel e a tela, ao centavo, em todo ponto com valor. A função de produção nunca é usada como oráculo de si mesma |
| Anomalias, verificações, situação das diferenças do RREO (seção 6) | **derivação** | o painel lê o que a derivação homologada gravou. O teste confere contagens, escopo e proveniência contra as tabelas da derivação. **Nenhuma regra de derivação é reimplementada** |

### 4.2 Fechamento

- **Forma:** total + componentes (grupos, classes ou contribuições), todos em centavos inteiros.
- **Diferença de fechamento:** `diferenca = Σ componentes − total`.
- **Aprovação:** `diferenca == 0`. Não há tolerância.
- **Falha:**
  - qualquer diferença ≠ 0 reprova a validação e bloqueia a exibição daquele conjunto, com o motivo;
  - nenhum ajuste, arredondamento ou componente "resíduo" pode ser criado para fechar a conta;
  - valor que não seja inteiro (inclusive `bool` e `float`) é erro, não é convertido.
- **Implementação de referência para os testes:** `recalculo_bruto.fechamento()`. A camada painel terá a sua na subetapa que precisar dela.

## 5. Métricas numéricas novas (05.2 a 05.5)

Cada métrica tem as 14 respostas da seção 9.1 do plano.

| Item do pedido da 05.1 (22) | Onde está respondido |
|---|---|
| 1 identificação, 2 pergunta | cabeçalho da métrica |
| 3 fonte | item 1 |
| 4 camada de origem | item 4 |
| 5 regra | itens 2 e 3 |
| 6 unidade, 7 domínio | item 12 |
| 8 sinal | item 11 |
| 9 a 16 (ausência, zero, inexistente, não coletado, não processado, indisponível, Município indisponível, exercício sem cobertura) | item 13, que aplica a taxonomia e a precedência da seção 2 (iguais para todas as métricas), mais o que for específico; e item 14 |
| 17 proveniência | item 8 (formato da seção 3) |
| 18 validação | itens 5 e 6 |
| 19 risco | item 7 |
| 20 casos-limite | item 9 |
| 21 fechamento | item 10 |
| 22 teste | item 6 e o critério da subetapa no plano |

### M-01 — Série de indicadores dentro do exercício (05.2; pergunta P1)

| # | Resposta |
|---|---|
| 1 | API Elotech (`rp_registro`, `rp_derivado`) |
| 2 | cada ponto = os indicadores de `SOMAS` de `Painel.indicadores(exercicio, corte, escopo)`, sem fórmula nova |
| 3 | `derivado` (somas de campos da API e S1–S3 v1, operacionais) |
| 4 | camada painel: método de série novo que percorre o universo da seção 2.4 e usa `indicadores` por ponto |
| 5 | sim: `recalculo_bruto.Bruto.ponto()` |
| 6 | bruto = painel = tela ao centavo em todo ponto com valor; pontos sem valor com `valores = None` |
| 7 | ponto indisponível omitido ou tratado como zero (R1); inscrição variando entre cortes por mudança retroativa (hoje não varia) |
| 8 | por ponto: a da seção 3 |
| 9 | corte sem a entidade (2026: 31/01, 31/03, 31/12 para as entidades 4, 5, 8 e 15); Município indisponível; entidade `sem_rp` (zero verdadeiro); corte posterior à coleta (31/12/2026, entidade 1); LIQ-NEG deixa liquidações negativas |
| 10 | não se aplica à série (cada ponto já é indicador homologado) |
| 11 | não se aplica (valores, não diferença) |
| 12 | centavos inteiros; inscrição e saldo ≥ 0 na prática, mas liquidações podem ser negativas (estornos); nenhum limite artificial |
| 13 | taxonomia e precedência da seção 2; universo completo (seção 2.4); valor só em `com_dados` e `sem_rp` |
| 14 | entidade sem snapshot no corte: ponto presente com a situação (nunca omitido) |

### M-02 — Diferença entre cortes adjacentes (05.2; P1)

| # | Resposta |
|---|---|
| 1 | API Elotech |
| 2 | `indicador(posterior) − indicador(anterior)`, para cada indicador de M-01, só entre cortes adjacentes do universo |
| 3 | natureza `diferenca`; operandos `derivado` |
| 4 | camada painel (junto da série de M-01); a interface não subtrai |
| 5 | sim: `recalculo_bruto.diferenca()` sobre `Bruto.ponto()` |
| 6 | bruto = painel = tela ao centavo em todo par adjacente com os dois pontos com valor |
| 7 | diferença entre cortes coletados em momentos diferentes mistura movimento e mudança retroativa (hoje, mesma janela de coleta); calcular contra lacuna |
| 8 | dos dois pontos (seção 3) |
| 9 | ponto vizinho indisponível (2026, Município: 28/02 → 31/03 e 31/03 → 30/04); primeiro corte do exercício (sem anterior) |
| 10 | soma das diferenças adjacentes de uma sequência sem lacunas = último − primeiro (identidade verificada no teste) |
| 11 | posterior − anterior |
| 12 | centavos inteiros; pode ser negativa |
| 13 | se algum dos dois pontos não tem valor, a diferença é `None` com o motivo; nunca pula lacuna (seção 2.6) |
| 14 | não se aplica (agregado do corte) |

### M-03 — Série de indicadores entre exercícios (05.3; P2, P5)

| # | Resposta |
|---|---|
| 1 | API Elotech |
| 2 | por exercício de 2016 a 2026: os indicadores de M-01 no corte representativo (seção 2.5); inscrição na abertura, pagamentos e cancelamentos acumulados até o corte, saldo S1 no corte |
| 3 | `derivado` |
| 4 | camada painel: método de série entre exercícios |
| 5 | sim: `Bruto.ponto()` no corte representativo |
| 6 | bruto = painel = tela ao centavo em todo ponto com valor; teste do texto do retrato em todo ponto |
| 7 | ler o passado como "o que se sabia na época" (princípio 6); somar entidades 1 e 15 como total corrigido (princípio 7) |
| 8 | por ponto, mais o corte representativo e o motivo da escolha |
| 9 | entidade fora do catálogo (15 antes de 2019; 10 depois de 2022; 3, 6, 9 e 11 em 2026); exercício em aberto (2026 → 31/08); exercício sem cobertura (nenhum hoje) |
| 10 | não se aplica |
| 11 | não se aplica (diferença entre exercícios adjacentes, se exibida, segue M-02) |
| 12 | centavos inteiros |
| 13 | seção 2, com `exercicio_sem_cobertura` e a lacuna "Município indisponível em todos os cortes do exercício" (seção 2.5) |
| 14 | entidade inexistente no exercício: ponto `inexistente`, nunca zero |

### M-04 — Fechamento de A × abertura de A+1 (05.3; P7)

| # | Resposta |
|---|---|
| 1 | API Elotech |
| 2 | `(a)+(f)(A+1) − S1(A)`, em que:<br>• S1(A) = Σ `s1_saldo_total_c` no corte representativo de A;<br>• (a)+(f)(A+1) = Σ `proc_c` dos registros com `faixa_processado = 'a'` + Σ `aproc_c` com `faixa_nao_processado = 'f'`, no corte representativo de A+1.<br>Mesma definição de `Painel._api_do_corte` |
| 3 | natureza `diferenca`; operandos `derivado` (S1 v1, FAIXA v1, operacionais). A verificação ANOM-CONT v1 é exibida ao lado, no regime de derivação (seção 6) |
| 4 | camada painel (reaproveitando `_api_do_corte`, hoje usado só pela coerência) |
| 5 | sim: S1 recalculado do bruto; faixa recalculada do bruto (`anoempenho == exercicio − 1` → b/g, senão a/f; só quando proc > 0 ou aproc > 0) |
| 6 | bruto = painel = tela ao centavo; para os escopos com RREO, igual ao já exibido na coerência (hoje 0 no consolidado e na entidade 1, de 2020 a 2025) |
| 7 | comparar com "inscrição de A+1" (errado: inclui as faixas b/g) — vedado (R2); comparar Municípios com conjuntos de entidades diferentes (R7) |
| 8 | dos dois cortes (A e A+1) e das regras S1 v1 e FAIXA v1 |
| 9 | entidade só de um lado (R7: 15 entra em 2019; 10 sai em 2023; 3, 6, 9 e 11 saem em 2026; hoje todas com 0 registros); A+1 em aberto |
| 10 | identidade esperada: diferença = 0 quando a base fecha (hoje fecha); ≠ 0 é diferença a investigar, nunca erro |
| 11 | (a)+(f)(A+1) − S1(A) |
| 12 | centavos inteiros; pode ser negativa |
| 13 | qualquer dos dois pontos sem valor → `None`. No Município, entidade exclusiva de um lado **com registros** → indisponível, com motivo e lista (R7) |
| 14 | entidade exclusiva de um lado com 0 registros: comparação feita e entidade listada como "entra" ou "sai" |

### M-05 — Composição por categoria (05.4; P3)

| # | Resposta |
|---|---|
| 1 | API Elotech |
| 2 | por `rp_derivado.categoria` (CAT v1): contagem, Σ (proc + aproc), Σ S1; mesma consulta de `indicadores.categorias` |
| 3 | `derivado` (CAT v1, S1 v1) |
| 4 | camada painel (`indicadores.categorias`, já existente) |
| 5 | sim: categoria recalculada do bruto (ambos se proc > 0 e aproc > 0; processado se só proc > 0; não processado se só aproc > 0; sem saldo de abertura nos demais) |
| 6 | bruto = painel = tela por grupo e fechamento ao centavo |
| 7 | nenhum grupo pode desaparecer por ter 0 registros sem ser mostrado como 0 registros |
| 8 | a do corte + filtro `categoria` da lista de empenhos (já existente) |
| 9 | categoria "sem saldo de abertura"; registros com valores negativos |
| 10 | por medida (contagem, inscrição, S1): Σ grupos = total do corte |
| 11 | não se aplica |
| 12 | centavos inteiros e contagem inteira |
| 13 | corte sem valor: composição inteira indisponível com a situação |
| 14 | grupo sem registros: 0 registros (é zero verdadeiro do grupo) |

### M-06 — Composição por faixa (05.4; P3)

| # | Resposta |
|---|---|
| 1 | API Elotech |
| 2 | Σ `proc_c` por `faixa_processado` (a, b) + Σ `aproc_c` por `faixa_nao_processado` (f, g). Rótulo: "composição dos registros da API segundo a regra FAIXA v1", nunca "coluna (a)/(f)" do RREO |
| 3 | `derivado` (FAIXA v1) |
| 4 | camada painel (consulta nova sobre `rp_derivado`) |
| 5 | sim: faixa recalculada do bruto (ver M-04) |
| 6 | bruto = painel = tela por grupo; teste de texto sem referência às colunas do RREO |
| 7 | apresentar como colunas do RREO; somar contagens de registros (não aditivas, R3) |
| 8 | a do corte + regra FAIXA v1 |
| 9 | registro com proc > 0 e aproc > 0 entra em dois grupos (R3); proc = 0 não tem faixa processada |
| 10 | **em valores**: Σ grupos = inscrição total (proc + aproc) do corte. Contagens de registros não fecham e não são somadas |
| 11 | não se aplica |
| 12 | centavos inteiros |
| 13 | corte sem valor: indisponível |
| 14 | grupo sem valor: 0 |

### M-07 — Composição por tipo de credor (05.4; P4)

| # | Resposta |
|---|---|
| 1 | API Elotech (campo `cnpj`, classificado por `publico.tipo_credor`) |
| 2 | por tipo (pessoa jurídica, pessoa física, não identificado): contagem, Σ inscrição, Σ S1 |
| 3 | `derivado` |
| 4 | camada painel (agrupamento pela função SQL `tipo_credor`, já registrada) |
| 5 | sim: tipo recalculado do bruto com a mesma definição documentada (CNPJ completo → PJ; CPF mascarado ou 11 dígitos → PF; resto → não identificado) |
| 6 | bruto = painel = tela e fechamento |
| 7 | expor identificação de credor (vedado; só o tipo) |
| 8 | a do corte |
| 9 | "não identificado" |
| 10 | por medida: Σ tipos = total do corte |
| 11 | não se aplica |
| 12 | centavos e contagem inteiros |
| 13 | corte sem valor: indisponível |
| 14 | tipo sem registros: 0 |

### M-08 — Composição por dimensão orçamentária (05.4; P4)

| # | Resposta |
|---|---|
| 1 | API Elotech |
| 2 | `Painel.por_dimensao(d)`, para d ∈ {fonte_recurso, orgao, funcao, programa, elemento}: contagem, Σ inscrição, Σ S1 por valor do campo, **incluindo o grupo nulo ("sem classificação")** |
| 3 | `derivado` |
| 4 | camada painel (`por_dimensao`, já existente) |
| 5 | sim: agrupamento do bruto pelo campo da API, com chave ausente = nulo |
| 6 | bruto = painel = tela por grupo; fechamento **por dimensão** |
| 7 | descartar "sem classificação" (16 registros em 2025-12-31); publicar dimensão que não fecha |
| 8 | a do corte + filtro da dimensão na lista de empenhos (filtro novo na 05.4) |
| 9 | chave ausente no item da API; fonte de recurso com mais de uma descrição (o agrupamento é por código e descrição) |
| 10 | **cada dimensão separadamente**: Σ grupos (com "sem classificação") = total do corte, por medida. Dimensão que não fecha não é exibida |
| 11 | não se aplica |
| 12 | centavos e contagem inteiros |
| 13 | corte sem valor: indisponível |
| 14 | registro sem o campo: grupo "sem classificação" |

### M-09 — Variação total entre dois cortes (05.5; P6)

| # | Resposta |
|---|---|
| 1 | API Elotech |
| 2 | `total(posterior) − total(anterior)`, para S1 (Σ `s1_saldo_total_c`) e pagamentos (Σ `pago_proc_c + pago_aproc_c`, a expressão do indicador "pagamentos", que vira constante única) |
| 3 | `diferenca` |
| 4 | camada painel (consulta da 05.5) |
| 5 | sim: `recalculo_bruto.Bruto.contribuicoes()` |
| 6 | igual à diferença dos indicadores homologados dos dois cortes, ao centavo |
| 7 | mudança retroativa somada ao movimento do intervalo; por isso as datas de coleta dos dois lados são exibidas |
| 8 | dos dois cortes |
| 9 | par que salta lacuna (2026, Município: 28/02 → 30/04); escopo indisponível em um dos lados |
| 10 | = Σ das contribuições de M-10 / M-11 |
| 11 | posterior − anterior |
| 12 | centavos inteiros; pode ser negativa |
| 13 | qualquer lado sem valor → par indisponível com motivo; Município com conjuntos de entidades diferentes → bloqueado (R6) |
| 14 | não se aplica (é o total) |

### M-10 — Contribuição por empenho: saldo S1 (05.5; P6)

| # | Resposta |
|---|---|
| 1 | API Elotech |
| 2 | chave `(entidade, anoempenho, empenho)`:<br>• **nos dois cortes:** `S1(post) − S1(ant)`;<br>• **só no posterior:** `S1(post)`;<br>• **só no anterior:** `0 − S1(ant)`.<br>Em que S1 = `rp_derivado.s1_saldo_total_c` (proc + aproc − pagoProc − pagoAProc − canceladoAProc) |
| 3 | `diferenca`; operando S1 v1 operacional |
| 4 | camada painel (consulta paginada nova) |
| 5 | sim: `Bruto.contribuicoes(..., metrica="s1")` |
| 6 | contribuição de cada chave ao centavo; fechamento de grupos e classes |
| 7 | valor absoluto esconderia o sinal (vedado); contribuições que se compensam |
| 8 | dos dois lados, inclusive o registro de cada lado (resposta, posição, objeto bruto) |
| 9 | chave só de um lado; chave duplicada (bloqueia o par); contribuição 0; empate de contribuição; cópias 24xxxxx inseridas depois (classe "só no posterior") |
| 10 | Σ contribuições = variação total (M-09), e por classe (nos dois, só no posterior, só no anterior) e por grupo do resumo (TOP N aumentos, outros aumentos, TOP N reduções, outras reduções, sem variação) |
| 11 | posterior − anterior |
| 12 | centavos inteiros; pode ser negativa |
| 13 | par indisponível (M-09) → sem contribuições |
| 14 | chave ausente num lado: classe própria, com o valor do outro lado (nunca zero implícito sem rótulo) |

Ordem da lista completa: contribuição decrescente, com desempate por (entidade, anoempenho, empenho). Lista paginada com subtotal da página e acumulado; a última página fecha com a variação total.

### M-11 — Contribuição por empenho: pagamentos (05.5; P6)

| # | Resposta |
|---|---|
| 1 | API Elotech |
| 2 | como M-10, com pagamentos = `pago_proc_c + pago_aproc_c` (campos da API, acumulados de 01/01 até o corte) |
| 3 | `diferenca`; operandos dado da fonte |
| 4 | camada painel |
| 5 | sim: `Bruto.contribuicoes(..., metrica="pagamentos")` |
| 6 | como M-10 |
| 7 | pagamento "negativo" de chave que some no posterior: aparece como redução da classe "só no anterior", nunca escondido |
| 8 | como M-10 |
| 9 | como M-10; estornos (já descontados em pagoProc e pagoAProc) |
| 10 | como M-10 |
| 11 | posterior − anterior |
| 12 | centavos inteiros; pode ser negativa |
| 13 | como M-10 |
| 14 | como M-10 |

### M-12 — Histórico de um empenho nos cortes (05.5; P8)

| # | Resposta |
|---|---|
| 1 | API Elotech |
| 2 | para a chave, os campos da API e os derivados de `_registros` em cada corte do universo do exercício; sem fórmula nova |
| 3 | `da_fonte` e `derivado` (os mesmos do detalhe) |
| 4 | camada painel (reaproveitando `_registros` por corte) |
| 5 | sim: `Bruto.itens()` filtrado pela chave |
| 6 | bruto = painel = tela por corte |
| 7 | corte em que a chave não aparece sumir da linha do tempo |
| 8 | por corte, a do registro (como no detalhe) |
| 9 | chave ausente num corte; chave duplicada num corte (mostra as ocorrências, sem escolher) |
| 10 | não se aplica |
| 11 | não se aplica |
| 12 | centavos inteiros |
| 13 | corte sem valor no escopo: ponto com a situação (seção 2) |
| 14 | chave ausente num corte com valor: "empenho ausente deste corte" (texto já existente no detalhe) |

## 6. Estruturas já produzidas pela derivação (05.6) — regime "derivação"

Não são métricas novas e **não são recalculadas do bruto** (seção 4.1).

### E-01 — Anomalias (`anomalia` + `anomalia_tipo`)

- **Uma linha por ocorrência.** Colunas: `derivacao_id`, `regra_id`, `tipo`, `coleta_id`, `entidade`, `anoempenho`, `empenho`, `detalhe_json`.
- **Exibição:** por tipo (código, descrição, status de evidência), regra, quantidade e escopo (coletas e exercícios).
- **Drill-down:** só quando entidade, ano e empenho estão preenchidos. Sem chave completa, a anomalia aparece só no agregado (o esquema permite nulo; hoje todas têm chave).
- **Validação:** contagens por tipo iguais às da tabela da derivação atual; proveniência (regra, derivação, coleta).
- **Texto:** anomalia não é erro; usa-se a descrição do tipo.

### E-02 — Verificações (`verificacao`): catálogo de interpretações

São agregadas. Colunas: `derivacao_id`, `regra_id`, `descricao`, `escopo_json`, `verificados`, `falhas`. Nunca viram lista de empenhos.

| Regra | Descrição (literal da derivação) | Significado de "falhas" | Situação exibida |
|---|---|---|---|
| ANOM-CONT v1 | `continuidade fechamento→abertura` | por entidade e par de exercícios (A → A+1): "verificados" = registros do fechamento de A (corte 31/12); "falhas" = registros com S1 ≠ 0 ausentes da abertura de A+1 (anomalia SALDO-SEM-CONTINUIDADE) + registros cuja abertura (proc, aproc) em A+1 difere de (S3, S2) do fechamento (anomalia DESCONTINUIDADE). A abertura usa o snapshot de A+1 de maior data final | 0 = "sem falha"; > 0 = "com falhas" e ligação às anomalias do mesmo escopo |
| PAR-24 v1 | `pareamento de cópias 24xxxxx` | por corte: "verificados" = registros da entidade-cópia com número ≥ base 2.400.000; "falhas" = cópias sem registro correspondente na entidade original, ou com campos de conferência diferentes (anomalia COPIA-SEM-PAR) | 0 = "sem falha"; > 0 = "com falhas" e ligação às anomalias COPIA-SEM-PAR do escopo |
| CONC-RREO v1 | `conciliação RREO × API (colunas com diferença)` | **colunas com diferença** entre a API projetada e o RREO (informativo, não erro) | "colunas com diferença: n de m", remetendo à reconciliação e às situações de E-03 |
| CONC-RREO v1 | `RREO sem valores extraídos (ver problemas da normalização)` | PDFs do RREO que o extrator não leu | "PDFs não lidos: n" |
| (qualquer outra) | — | — | "significado não catalogado", com os números brutos, sem interpretação |

- **Validação:** soma de verificados e falhas por descrição igual à tabela; snapshots de `escopo_json` existem.

### E-03 — Situação das diferenças com o RREO

| Situação | Critério |
|---|---|
| SEM DIFERENÇA | `diferenca_c == 0`, atribuída pela camada painel. **Não é explicação** |
| EXPLICADA | `explicacoes.resumo` = "explicada" |
| PARCIALMENTE EXPLICADA | `explicacoes.resumo` = "parcialmente explicada" |
| HIPÓTESE | `explicacoes.resumo` = "hipótese" |
| NÃO DETERMINADA | `explicacoes.resumo` = "não determinada" (inclui diferença sem nenhuma entrada) |

- **Contagem:** por coluna × documento × regra de agregação (v1 e v2 separadas), e também na coerência.
- **Validação:** contagens iguais às da reconciliação já exibida.

## 7. Técnica de apresentação dos gráficos (decisão da 05.1)

**Decisão:** gráficos, quando houver, serão **SVG gerado no servidor pela própria aplicação**, embutido no HTML, sem biblioteca nova.

Critérios atendidos (plano, seção 10):

| Critério | Como |
|---|---|
| sem JavaScript | SVG estático gerado em Python (biblioteca padrão); nenhum `<script>` |
| compatível com a CSP atual (`default-src 'none'`, `style-src 'self'`) | o `<svg>` faz parte do documento e não é um recurso externo. Só **atributos de apresentação** (`fill`, `stroke`, `x`, `y`, `width`, `height`), nunca o atributo `style` nem `<style>` dentro do SVG (bloqueados pela CSP). Cores e classes podem vir de `estilo.css` (`'self'`) |
| sem CDN | nada externo |
| sem dependência nova | biblioteca padrão |
| tabela sempre presente | o gráfico acompanha a tabela de valores exatos (`<data value>`), que é a fonte da verdade e a alternativa acessível; o SVG leva `role="img"` e `aria-label` |
| lacuna como lacuna | ponto sem valor não é desenhado como 0: a linha é interrompida e há marca e rótulo da situação |
| proveniência | cada ponto ou barra dentro de `<a href>` para a tela do corte (links internos com "/", como exige o teste de segurança da 04.6) |
| legível em 375 px | `viewBox` com largura proporcional, sem largura fixa em pixels; texto mínimo de 11 px; verificado como as telas da 04.6 |

**Fica para a primeira subetapa que tiver gráfico (05.2):** um teste que confere que o SVG não tem `style`, `<script>`, `<style>` nem referência externa, e que todo ponto sem valor está marcado como lacuna. **Nenhum gráfico foi implementado na 05.1.**

## 8. O que a 05.1 não faz

- **Código e interface:** não altera código de produção (`app/rp/`), interface, banco, snapshots nem regras.
- **Séries, composição e investigação:** não implementa séries (05.2, 05.3), composição (05.4), investigação (05.5) nem a tela de qualidade (05.6).
- **Coletas e escopo:** não faz D1, coleta, automação, nem análise de concentração por credor.
- **Pendências registradas, não resolvidas:**
  - R1 (série de entidade omite cortes): corrigida e homologada na 05.2;
  - R4 (rótulo do corte posterior à coleta): exibido na 05.2;
  - as situações `municipio_indisponivel` (05.2) e `exercicio_sem_cobertura` (05.3) só existem hoje na ferramenta de validação e no contrato.
