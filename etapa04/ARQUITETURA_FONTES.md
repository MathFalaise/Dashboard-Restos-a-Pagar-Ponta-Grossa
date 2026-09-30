# Arquitetura de fontes — Restos a Pagar de Ponta Grossa

Data: 30/09/2026. Parte da revisão corretiva das Etapas 01 a 04.4 (detalhe das correções em `CORRECOES_ETAPAS_01_A_04_4.md`).

## 1. Declaração de fontes

> Os dados granulares de Restos a Pagar utilizados como fonte operacional do sistema são coletados do Portal da Transparência de Ponta Grossa através da API do sistema Elotech/Oxy Transparência. Os RREOs são publicações oficiais independentes utilizadas para reconciliação e auditoria, não para substituir a base operacional granular.

| Papel | Fonte | O que o projeto guarda | Onde aparece |
|---|---|---|---|
| **Fonte primária dos dados operacionais de RP** | API do Portal da Transparência de Ponta Grossa (Elotech/Oxy Transparência) | registros de RP por empenho, movimentação de empenhos, catálogos de entidades e de exercícios | camadas 0 → 1 → 2 e todos os indicadores do painel |
| **Publicação oficial independente / fonte de reconciliação** | RREO Anexo VII (PDF publicado pelo Município no portal) | o PDF (bytes) e a transcrição das 12 colunas | `rreo_valor`, `conciliacao_rreo` e a área de reconciliação |
| Fonte externa | e-SIC, normas, notas técnicas, documentos oficiais | o arquivo, com SHA-256 e origem | `evidencia_externa` (por enquanto vazia) |

A relação não se inverte:
- o RREO nunca substitui, ajusta nem completa um valor da API;
- uma divergência entre os dois é **registrada** como diferença, com a regra que a produziu e a explicação documentada, se houver;
- nenhum indicador lê a tabela do RREO (teste `test_01` em `app/tests/test_correcoes.py`).

## 2. O que está comprovado sobre cada fonte

O projeto só afirma o que a documentação disponível demonstra.

| Afirmação | Evidência | Status |
|---|---|---|
| A API em `servicos.pontagrossa.pr.gov.br/portaltransparencia-api` alimenta o Portal da Transparência do Município | Etapa 01 §1: a página oficial da Prefeitura aponta para o portal; o portal é uma SPA que busca todos os dados nessa API | CONFIRMADO |
| A plataforma do portal é o Oxy Transparência, da Elotech Gestão Pública, versão 3.128.0 | Etapa 01 §1: `GET /portaltransparencia-api/actuator/info`. **A resposta não foi guardada no bruto.** | CONFIRMADO na Etapa 01, sem cópia no armazém |
| A especificação OpenAPI da API tem título "Web Services" e contato "Elotech Gestão Pública" | `etapa01/amostras_brutas/openapi_v3_api-docs.json` | CONFIRMADO (arquivo guardado) |
| O endpoint de RP usado (`/empenhos/restos-a-pagar`) não consta da especificação OpenAPI | Etapa 01: identificado pelo funcionamento do próprio portal | CONFIRMADO. Consequência: não há contrato do fornecedor para esse endpoint |
| Os 30 PDFs distintos do RREO de 2020 a 2026 trazem no rodapé "FONTE: Sistema Elotech Gestão Pública, Unidade Responsável PREFEITURA MUNICIPAL DE PONTA GROSSA"; os de 2018 e 2019, "Sistema de Contabilidade Pública"; os de 2016 e 2017 não têm essa linha | leitura dos PDFs do armazém em 30/09/2026 (35 PDFs distintos, 36 snapshots: um PDF de 2026 foi coletado duas vezes) | CONFIRMADO |
| O RREO e a API leem a mesma base contábil | a API reproduz a abertura publicada no RREO do ano seguinte (04.4 §8), o que é **coerente** com isso | **NÃO COMPROVADO**: nenhum documento do Município ou da Elotech o afirma |
| Quando cada lançamento foi registrado no sistema | a data do lançamento na movimentação não prova a data do registro (04.4 §15) | NÃO DETERMINADO |
| Natureza das cópias 24xxxxx da entidade 1 (duplicidade ou transferência) | — | NÃO DETERMINADO (pergunta do e-SIC) |

## 3. Dois fluxos separados

### 3.1 Fluxo operacional: API Elotech → indicadores

```
API do Portal da Transparência (Elotech/Oxy)
 └─ coletor (app/rp/coletor.py)
    listagem sempre sem tipoPesquisa, dataInicial = 01/01, paginação conferida contra totalElements
    └─ snapshot imutável = CAMADA 0
       snapshots/objetos/<ab>/<sha256>.zlib + snapshots/coletas/.../<manifesto>.json
       tabelas coleta, resposta_bruta, objeto_bruto (gatilhos impedem UPDATE e DELETE)
       └─ normalização = CAMADA 1 (app/rp/normalizar.py)
          rp_registro, movimentacao_lancamento, entidade_ref, exercicio_ref
          dinheiro em centavos inteiros; valor com mais de 2 casas é erro, nunca arredondado
          └─ derivação = CAMADA 2 (app/rp/derivar.py), toda linha com a versão da regra
             rp_derivado (CAT, FAIXA, S1, S2, S3, CANC), espelhamento_par (PAR-24),
             movimentacao_interpretada (MOV-REF), anomalia, verificacao, visao_valor
             └─ camada de consulta (app/rp/painel) — SOMENTE LEITURA
                indicadores = somas de campos da API e de S1–S3, só com regras operacionais
                └─ dashboard (ainda não existe): lê só da camada de consulta
```

### 3.2 Fluxo de reconciliação: RREO → diferenças

```
Publicações da LRF no portal (grupo 1; entidade de [rreo] entidade_publicacoes no config.toml)
 └─ coletor.rreo → snapshot do PDF (CAMADA 0, mesmas garantias)
    └─ extrator versionado rp-rreo-coordenadas/1 (CAMADA 1)
       rreo_valor (transcrição) + rreo_extracao (extrator, PyMuPDF/MuPDF e versão, SHA-256 do PDF,
       idArquivo, rótulo, data da extração, quantos valores saíram ou o erro)
       └─ conciliação CONC-RREO v1 (CAMADA 2): API agregada por RREO-COL v1 e por RREO-COL v2 − RREO
          conciliacao_rreo (registro da diferença, nunca correção)
          └─ área de reconciliação do painel:
             API = X, RREO = Y, Diferença = Z, regra e sua situação, PDF, extração, explicação documentada
```

Os dois fluxos só se encontram na conciliação. A comparação entre publicações (L do RREO de dezembro de A contra (a)+(f) do RREO de A+1) é um terceiro uso do RREO: compara duas publicações entre si e mostra ao lado o que a API dá hoje.

## 4. Cadeias de proveniência

| Valor | Cadeia |
|---|---|
| Indicador do painel | dashboard → camada de consulta → derivação (id e `hash_resultado`) → normalização (id) → snapshot (`snapshot_uid`, manifesto, `coletada_em`, origem do carimbo) → resposta HTTP (URL, status, recebida em) → objeto bruto (SHA-256, tamanho) → endpoint da API Elotech (`/empenhos/restos-a-pagar` e parâmetros) |
| Registro (detalhe de empenho) | a cadeia acima + `resposta_id`, página (`ordem`) e posição no `content[]` |
| Valor do RREO | reconciliação → `conciliacao_rreo` → `rreo_valor` → `rreo_extracao` (método e versão) → snapshot do PDF (`idArquivo`, rótulo, data do arquivo, "emitido em" do rodapé) → objeto bruto |
| Evidência externa | `evidencia_externa` (tipo, descrição, data do documento, arquivo, SHA-256, origem, observação) → manifesto em `snapshots/evidencias/` → objeto bruto |
| Regra | `regra` (imutável) → `regra_parametro` (imutável) → `regra_situacao` (histórico de decisões, só acrescenta) |

## 5. Natureza de cada valor

| Natureza | Definição | Exemplo |
|---|---|---|
| **Dado da fonte** | valor devolvido pela API para um registro | `pagoProc` de 5659/2025 |
| **Dado publicado** | valor impresso no RREO | coluna (h) do RREO do 4º bimestre de 2026 |
| **Valor derivado** | soma ou fórmula documentada sobre dados da API, com regra **operacional** | soma de S1 do corte |
| **Valor analítico** | resultado de regra experimental, não recomendada ou de hipótese | visões CONS-PAR; divisão CANC v1; projeção RREO-COL v1/v2 |
| **Diferença** | divergência entre duas fontes ou entre dois retratos | API − RREO; L(A) − (a)+(f)(A+1); retrato B − retrato A |

Valor calculado por regra que não esteja `operacional` sai como analítico, e nunca entra num indicador publicado (`RegraNaoOperacional`).

## 6. Retrato atual × retrato histórico

- Todo valor sai com o rótulo do retrato:
  - "Estado atual da base para o exercício de 2024, corte 31/12/2024, coletado em 30/09/2026";
  - "Como a base estava em 29/09/2026: exercício de 2025, corte 31/12/2025, coletado em 29/09/2026".
- O mesmo corte coletado em dois momentos são **dois snapshots** (A ≠ B). O novo nunca substitui o antigo; o vigente numa data é o mais recente completo coletado até ela.
- Um exercício histórico é o estado da base **na data da coleta**, e não necessariamente o que estava disponível ao público naquele ano: a 04.4 registrou lançamentos com data no passado feitos depois e cópias inseridas depois que aparecem em cortes antigos.
- Só entram snapshots que a normalização em uso processou (`normalizacao_execucao.ultima_coleta_id`). Snapshot novo ainda não processado vira aviso, nunca um corte com valor zero.
- A reconciliação "como estava em" usa a derivação com a mesma vigência (`python -m rp processar --em ...`).

## 7. Catálogo histórico de entidades

- O painel cruza o catálogo de entidades da API com o **catálogo de exercícios de cada entidade**:
  - "no catálogo oficial" — a entidade existia no exercício;
  - "fora do catálogo oficial" — não existia: **não é RP zero**; a consulta por entidade responde "indisponível" e a entidade não entra no total do Município;
  - "sem catálogo de exercícios" — não há como saber; entra no total se houver snapshot.
- Catálogos atuais: entidades 1, 4, 5 e 8 em 2016–2026; 15 em 2019–2026; 3, 6, 9 e 11 em 2016–2025; 10 em 2016–2022 (04.4 §3).
- O total do Município só existe quando toda entidade do catálogo oficial do exercício tem snapshot processado do mesmo corte.
- A visão "publicado" da derivação (inalterada, para não mudar o `hash_resultado`) continua exigindo as 10 entidades do catálogo atual. As combinações fora do catálogo devolveram 0 registros (04.4 §1), então os totais coincidem; quem separa "não existia" de "zero" é o painel.
- O catálogo de entidades é o que a API devolve hoje: entidade extinta que não conste dele não é conhecida.

## 8. Camada pública e dados pessoais

- Nível `publico` (padrão):
  - listagens e agregados não trazem nome, código, CNPJ nem CPF do credor; só o tipo (pessoa jurídica, pessoa física, não identificado);
  - o detalhe de **um** empenho mostra o nome do credor pessoa jurídica sem documento: tira o prefixo "CNPJ - " e mascara toda sequência com cara de documento (a razão social de MEI costuma terminar com o CPF do titular, às vezes sem o zero inicial);
  - credor pessoa física não tem o nome exibido;
  - na comparação de retratos, mudanças nos campos do credor aparecem como "[restrito]".
- Nível `interno`: só quando pedido explicitamente (`--nivel interno`); traz os campos do credor como a API devolve.
- Os campos coletados não têm dado bancário.
- A camada bruta continua guardando tudo como a API devolveu (é a evidência). A minimização vale para o que sai para o dashboard.

## 9. Parâmetros e governança das regras

- **Parâmetros de negócio** ficam em `regra_parametro`, presos à versão da regra (tabela imutável):
  - PAR-24 v1: entidade da cópia 1, entidade original 15, base 2.400.000, conferência por CNPJ/CPF e data de emissão;
  - CONC-RREO v1: o RREO "por entidade" é comparado com a entidade 1.
  - Mudar um parâmetro = versão nova da regra.
- A entidade cujas publicações trazem o RREO fica em `config.toml`, seção `[rreo]`.
- **Governança**: `regra_situacao` guarda o histórico de decisões de cada versão (só acrescenta). Situação atual:

| Regra | Situação | Compõe indicador publicado |
|---|---|---|
| CAT v1, FAIXA v1, S1 v1, S2 v1, S3 v1 | operacional | sim |
| MOV-REF v1 | operacional | sim (interpretação da movimentação) |
| PAR-24 v1, CONC-RREO v1, ANOM-REG v1, ANOM-CONT v1 | operacional | não (identificam, registram; não alteram valor) |
| RREO-COL v1 | não recomendada (decisão original "operacional" preservada no histórico) | não |
| CANC v1 | não recomendada (continua calculada) | não |
| RREO-COL v2 | experimental | não |
| CONS-PAR v1 e v2 | experimental (só visão analítica) | não |

- Não foram criadas nem promovidas: RREO-COL v2 como padrão, CANC v2, CONS-PAR v3.
- Decisão nova só com `governanca.registrar_decisao(...)`, com motivo, fonte, origem e, quando houver, o id da evidência externa. O banco recusa "experimental" compondo indicador publicado (CHECK) e recusa editar ou apagar decisão (gatilhos).

## 10. Texto de metodologia (exibido pelo painel)

- **Dados operacionais:** Portal da Transparência de Ponta Grossa — dados da API do sistema Elotech/Oxy Transparência. São os registros granulares de Restos a Pagar por empenho, coletados pelo coletor do projeto.
- **Publicações de referência:** RREO Anexo VII e demais documentos oficiais publicados pelo Município, usados para conferência, reconciliação e auditoria.
- **Tratamento:** os dados Elotech são preservados em snapshots imutáveis, normalizados sem alteração dos valores originais (em centavos) e depois derivados segundo regras versionadas. Uma divergência com o RREO é mostrada como diferença; o valor da API nunca é ajustado para coincidir com o RREO.
- **Importante:** um exercício histórico representa o estado da base observado na data da coleta, e não necessariamente o estado que estava disponível ao público naquele ano. A Etapa 04.4 registrou alterações retroativas na base (lançamentos com data no passado feitos depois e registros inseridos depois que aparecem em cortes antigos).

## 11. Mapa de componentes

| Arquivo | Papel |
|---|---|
| `app/rp/coletor.py`, `http.py`, `snapshots.py`, `armazem.py` | coleta e camada 0 (snapshot imutável, objetos por SHA-256, manifestos) |
| `app/rp/banco.py`, `esquema.sql` | banco, migrações (v4 desta revisão), registro e reconstrução a partir do armazém |
| `app/rp/normalizar.py` | camada 1 e transcrição versionada do RREO (`rreo_extracao`) |
| `app/rp/regras.py`, `governanca.py` | catálogo de regras, parâmetros e decisões de governança |
| `app/rp/derivar.py` | camada 2 e conciliação |
| `app/rp/comparador.py` | comparação de dois retratos do mesmo corte |
| `app/rp/evidencias.py` | registro de evidência externa |
| `app/rp/painel/consulta.py` | camada de consulta somente leitura (`Painel`) |
| `app/rp/painel/fontes.py` | fontes, naturezas, dicionário de campos (nome técnico ↔ amigável) e metodologia |
| `app/rp/painel/publico.py` | minimização de dados do nível público |
| `app/rp/painel/explicacoes.py` | explicações documentadas das diferenças (transcrição dos relatórios) |
| `app/rp/cli.py` | `python -m rp painel <consulta>` (JSON) e `python -m rp registrar-evidencia` |

## 12. O que não existe, de propósito

- **Não há frontend.** Esta revisão construiu só a infraestrutura de leitura. O dashboard futuro deve usar `rp.painel.Painel` (Python) ou `python -m rp painel ...` (JSON), e nunca chamar a API da Elotech.
- Não há agendamento de coleta.
- Não há regra criada para "fechar" diferença com o RREO.
