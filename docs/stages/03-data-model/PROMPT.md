# PROJETO — RESTOS A PAGAR DE PONTA GROSSA

## ETAPA 03 — ARQUITETURA E MODELAGEM DE DADOS

> Versão aprovada em 29/09/2026, com os dois ajustes da revisão: regras 5 e 6 e o vocabulário de espelhamento.

As Etapas 01 e 02 investigaram a fonte e validaram a semântica contábil dos dados.

Nesta etapa, o objetivo é **exclusivamente** definir a arquitetura de dados e o modelo do banco. Ainda não se constrói o sistema.

---

# FONTE DE VERDADE

- `docs/stages/02-accounting-validation/REPORT.md`, **incluindo o ADENDO** sobre o espelhamento.
- `docs/stages/01-source-discovery/REPORT.md`, no que a Etapa 02 não corrigiu.

Toda regra de cálculo, classificação ou anomalia desta etapa deve apontar a seção do relatório que a sustenta, com o mesmo nível de confiança (CONFIRMADO / FORTE EVIDÊNCIA / HIPÓTESE / NÃO DETERMINADO).

**Não promova uma HIPÓTESE ou um NÃO DETERMINADO a regra fixa do banco.** Os itens incertos devem ser modelados como **dado classificado**, nunca como verdade embutida na estrutura.

---

# DECISÕES JÁ TOMADAS

## 1. Três visões do Município (nenhuma substitui as outras)

- **Total publicado:** soma das 10 entidades. Reproduz o RREO consolidado publicado pela Prefeitura.
- **Total analítico com espelhamentos consolidados:** cada par espelhado (entidade 15 ↔ entidade 1, número + 2.400.000) consolidado **por componente** (inscrição, pagamento, cancelamento, liquidação), e não escolhendo um lado inteiro.
  - **Atenção (Adendo da Etapa 02):** o lado do par que carrega a execução muda por exercício. Em 2026 é a cópia da entidade 1; em 2025 foi o original da entidade 15.
  - A regra de consolidação é **NÃO DETERMINADA**. Deve ficar como **regra versionada e EXPERIMENTAL** da visão analítica, nunca como exclusão física de registros.
  - Hipótese inicial a testar: inscrição do par contada uma vez + fluxos somados dos dois lados. Ainda não se sabe se os dois lados são sempre complementares.
  - Não usar o termo "deduplicação": não há evidência de que algum lado seja descartável.
- **Por entidade:** cada entidade separada.

As cópias e os originais são **preservados** e **classificados** como espelhamento/anomalia identificada. Esta etapa **não** decide se são erro ou lançamento legítimo.

## 2. Retratos (snapshots) no lugar de "dados atuais"

- Exercício corrente: coleta mensal ou bimestral.
- Exercícios fechados: recoleta periódica, por exemplo trimestral.
- Cada coleta é um **snapshot independente**. Nunca se sobrescreve o anterior.
- O modelo deve responder a perguntas como: "O que o portal informava sobre 2025 em 30/09/2026?" × "O que o portal informa hoje sobre 2025?"

## 3. e-SIC em paralelo

O pedido de esclarecimento (espelhamento da entidade 15, lacuna de (h)/(i) em 2026, empenhos 24xxxxx) é uma investigação externa. **Não bloqueia esta etapa.** O modelo deve comportar a resposta sem refazer a estrutura, por exemplo registrando a resposta como evidência que reclassifica uma anomalia.

## 4. Regra arquitetural: o dado bruto nunca é substituído pelo derivado

```text
SNAPSHOT (imutável)
 ├── resposta bruta da API (bytes exatos)
 ├── metadados da coleta (URL, parâmetros, status HTTP)
 ├── hash SHA-256
 ├── data/hora da coleta
 └── versão do coletor
        ↓
NORMALIZAÇÃO (reprocessável)
        ↓
DADOS DERIVADOS (reprocessáveis, com versão da regra)
 ├── categoria (processado / não processado / ambos)
 ├── S1, S2, S3, S4
 ├── classificação RREO (a–k)
 ├── anomalias
 └── espelhamentos
```

- Todo dado derivado registra **qual versão da regra** o produziu.
- Se uma fórmula mudar, reprocessam-se os snapshots, sem nova coleta.
- O mesmo snapshot com a mesma versão de regra tem de gerar exatamente o mesmo resultado.

## 5. Nenhum lado de um par espelhado é presumido descartável

O modelo não deve assumir que um lado de um par espelhado é sempre descartável.

- O espelhamento é representado **explicitamente**: par de registros, entidade A, entidade B, exercício, valor inscrito, execução de A, execução de B, lado com execução e regra de consolidação aplicada.
- A consolidação é **parametrizada e versionada**.
- A Etapa 03 pode **testar** uma hipótese de consolidação. Não pode declarar como fato que os fluxos dos dois lados devem sempre ser somados sem validação adicional.

## 6. Nenhum registro bruto é excluído por ser considerado duplicado

- Durante a normalização, nenhum registro é excluído, fundido ou alterado por parecer duplicado.
- A identificação de espelhamento e a decisão de consolidação acontecem **só na camada derivada**.

---

# O QUE DEFINIR

Para cada item: a estrutura proposta, a justificativa e a evidência da Etapa 02 que a sustenta.

1. **Modelo dos snapshots**
   - Um snapshot da listagem é identificado por `entidade`, `exercicio`, `dataInicial` (sempre 01/01), `dataFinal` (o corte), `coletado_em`.
   - O mesmo corte recoletado depois é **outro snapshot**, porque a base muda retroativamente.
   - Tipos de snapshot: listagem de RP, movimentação de empenho, PDF do RREO, listagens auxiliares (exercícios, entidades, publicações).
2. **Modelo dos empenhos:** campos brutos preservados, inclusive `canceladoProc` (sempre 0) e `*Estornado`.
3. **Chave composta:** (`entidade`, `anoempenho`, `empenho`). O número se repete entre entidades.
4. **Modelo das movimentações**
   - A coleta é uma requisição por empenho (cerca de 4,5 mil por exercício só na entidade 1).
   - Definir a política: sob demanda, para auditoria e amostra. **Não é coleta em massa.**
   - Registrar os rótulos trocados nos lançamentos 40/41.
5. **Entidades:** as 10, com o atributo "tem RP" (1, 4, 5, 8, 15 em 2025/2026) mantido por snapshot, não fixo.
6. **Exercícios**
   - 2016–2026 oficiais; aberto/fechado.
   - Relação entre exercício de referência e `anoempenho`.
   - Proibir combinações `exercicio` × datas de anos diferentes.
7. **Fórmulas derivadas:** só F1–F3 e S1–S4 do relatório, com versão. **Nada fora disso.**
8. **Catálogo de anomalias**, cada uma com regra de detecção, evidência e status:
   - `liquidado` < 0;
   - `pagoProc` ≠ 0 com `proc` = 0;
   - `canceladoProc` ≠ 0;
   - cópia 24xxxxx;
   - descontinuidade entre exercícios;
   - divergência com o RREO;
   - registro fora do universo.
9. **Espelhamentos:** entidade de ligação entre pares (entidade A/B, exercício, inscrito, execução A/B, lado com execução), com critério de pareamento versionado, confiança e as regras de consolidação que a usam. Casos obrigatórios da carga de validação:
   - entidade 15 ↔ entidade 1;
   - 2025 e 2026, com a execução em lados diferentes;
   - empenhos nas duas abas;
   - o mesmo período coletado em datas diferentes;
   - alteração retroativa da base;
   - 11963/2016 e 5659/2025;
   - registros 24xxxxx;
   - movimentações negativas;
   - RREO × API.
10. **RREO**
    - Armazenar o PDF, os valores extraídos por coluna e a **conciliação** com o snapshot correspondente.
    - A conciliação é registro de diferença, nunca correção.
11. **Hashes e versionamento:** das coletas, do coletor, das regras e das visões.
12. **Política de imutabilidade:** o que nunca pode ser alterado ou apagado e como isso é garantido.
13. **Esquema do banco**
    - Propor a tecnologia com justificativa: volume, consultas temporais, imutabilidade, custo de operação.
    - **A decisão final é do usuário.**
14. **Testes de integridade**, no mínimo:
    - paginação completa (`Σ numberOfElements` = `totalElements`);
    - esquema esperado;
    - identidades S1–S3;
    - continuidade entre exercícios;
    - reprocessamento determinístico;
    - conciliação com o RREO como relatório de diferenças.

---

# PERMITIDO E PROIBIDO

**Permitido:**
- Escrever o DDL do esquema proposto.
- Validar o modelo carregando os **dados brutos já baixados na Etapa 02** num banco local **descartável**, para provar que ele comporta os casos reais: espelhamento, retroatividade, empenhos nas duas abas, estornos e cancelamentos.
- Testes de integridade sobre essa carga.
- **Nenhuma coleta nova** além do mínimo indispensável, e justificada.

**Proibido nesta etapa:**
- interface, frontend, dashboard, gráficos;
- indicadores e rankings;
- coletor definitivo ou agendado;
- coleta histórica completa;
- API própria e deploy.

O código de validação desta etapa fica separado do futuro código de produção, como em `docs/stages/02-accounting-validation/investigation/`.

---

# RELATÓRIO FINAL DA ETAPA 03

1. RESUMO
2. DECISÕES INCORPORADAS (e como o modelo as implementa)
3. MODELO CONCEITUAL (diagrama)
4. ESQUEMA DO BANCO (DDL + justificativa da tecnologia)
5. SNAPSHOTS, HASHES E IMUTABILIDADE
6. FÓRMULAS E VERSIONAMENTO DE REGRAS
7. ANOMALIAS E ESPELHAMENTOS
8. RREO E CONCILIAÇÃO
9. TESTES DE INTEGRIDADE (e resultado da carga de validação)
10. LIMITAÇÕES E PONTOS EM ABERTO
11. ESPECIFICAÇÃO PARA A ETAPA 04

---

# REGRA DE ENCERRAMENTO

Ao final da Etapa 03, PARE. Não implemente a Etapa 04. Aguarde análise e autorização explícita.

A última mensagem deve ser:

> ETAPA 03 CONCLUÍDA — AGUARDANDO APROVAÇÃO PARA A ETAPA 04.
