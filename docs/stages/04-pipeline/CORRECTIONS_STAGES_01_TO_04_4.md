# Correções das Etapas 01 a 04.4 — revisão corretiva antes da Subetapa 04.5

Data: 30/09/2026. Base: repositório `MathFalaise/Dashboard-Restos-a-Pagar-Ponta-Grossa`, ramo `main`, HEAD `adc7510` ("Inclui os dados brutos coletados do portal"). A 04.5 **não** foi iniciada. Arquitetura resultante: `ARQUITETURA_FONTES.md`.

**Resumo:**
- A API Elotech do Portal da Transparência continua sendo a **fonte primária dos dados operacionais de RP**, agora declarada e protegida por teste. O RREO continua sendo **publicação oficial independente / fonte de reconciliação**.
- Criada a camada de consulta **somente leitura** para o futuro dashboard (`app/rp/painel`), com proveniência, rótulo de retrato, natureza de cada valor, catálogo histórico de entidades, área de reconciliação e camada pública com minimização de dados. **Nenhum frontend foi inventado.**
- Criadas, de forma não destrutiva: parâmetros de regra imutáveis, histórico de governança das regras, registro de evidência externa e registro do método de extração de cada RREO (esquema **v4**, que só acrescenta).
- Nenhum snapshot, objeto bruto, PDF, relatório de etapa, hash ou regra histórica foi alterado. Os hashes de resultado continuam **2f6b4e29…** (atual) e **b8a0b2ed…** ("como estava em" 29/09).

---

## 1. Auditoria do estado atual

1. **HEAD:** `adc7510`, sobre `6945d31`. As mudanças desta revisão **não** foram commitadas.
2. **Arquivos de produção:** `app/rp/` (`coletor.py`, `http.py`, `snapshots.py`, `armazem.py`, `banco.py`, `esquema.sql`, `normalizar.py`, `regras.py`, `derivar.py`, `comparador.py`, `consultas.py`, `execucoes.py`, `importar.py`, `config.py`, `cli.py`), `app/config.toml`, `app/tests/`. Scripts de investigação e de lote ficam em `docs/stages/02-accounting-validation/investigation`, `docs/stages/03-data-model/validation` e `docs/stages/04-pipeline/batches|reconciliacao` (fora do pacote).
3. **Onde está o dado Elotech:**
   - bruto: `data/snapshots/objetos` (bytes por SHA-256) + `data/snapshots/coletas` (manifestos) e camada 0 do SQLite (`coleta`, `resposta_bruta`, `objeto_bruto`);
   - normalizado: `rp_registro`, `movimentacao_lancamento`, `entidade_ref`, `exercicio_ref`;
   - derivado: `rp_derivado`, `espelhamento_par`, `movimentacao_interpretada`, `anomalia`, `verificacao`, `visao_valor`, `conciliacao_rreo`.
4. **Existe dashboard?** Não. Não havia HTML, JavaScript, servidor nem camada de consulta; só comandos de coleta, processamento e comparação.
5. **Uso do RREO:** snapshot do PDF → transcrição (`rreo_valor`) → diferença API − RREO (`conciliacao_rreo`). Nos relatórios, também para validar o significado dos campos da API.
6. **Dado Elotech não exposto:** nenhum dado era exposto além da saída do comparador. Ficavam só no banco: classificação orçamentária (programática, fonte de recurso, órgão, unidade, função, subfunção, programa, projeto, elemento, desdobramento), datas de emissão, estornos, retenções, movimentação e catálogos. Agora saem pelo painel, com nome técnico e amigável (`Painel.dicionario_campos`).
7. **RREO usado como fonte primária?**
   - **No código: não.** Nenhum cálculo lê `rreo_valor` fora da conciliação, e a conciliação só registra diferenças.
   - **Na documentação: sim, em trechos** (itens C1 a C4 abaixo): a legenda de evidência da Etapa 02, a afirmação de reconstrução ao centavo e a leitura da Etapa 03 sobre 2025.
   - **Risco de nome:** a visão da derivação chamada `publicado` é a projeção da **API** nas colunas do RREO, não o valor publicado (item C13).
8. **Cálculos duplicados:**
   - as regras existem em duas implementações (investigação da Etapa 03 e produção) — mantido, é evidência histórica;
   - base 2.400.000 e entidades 1/15 estavam repetidas em `derivar.py` e `comparador.py` (item C8);
   - o painel **não** reimplementa regra: lê CAT, FAIXA e S1–S3 de `rp_derivado` e só soma e agrupa.

---

## 2. Correções

Tipos: **D** documental · **A** arquitetural · **R** regra (governança, sem editar regra existente) · **C** código.

### C1. Hierarquia de fontes não declarada
- **Etapas:** 01 a 04.4.
- **Estado anterior:** os relatórios tratam a API como fonte dos dados e o RREO como "fonte oficial", sem declarar o papel de cada um.
- **Correção:** declaração explícita (`ARQUITETURA_FONTES.md` §1; `painel/fontes.py`; `Painel.fontes()`): API Elotech = fonte primária dos dados operacionais; RREO = publicação oficial independente / reconciliação; e-SIC e normas = fonte externa.
- **Motivo:** especificação da revisão; evitar que o RREO seja lido como verdade que corrige a API.
- **Impacto:** nenhum valor muda.
- **Tipo:** D, A.
- **Testes:** `test_01_indicador_principal_vem_da_api_elotech_e_nao_do_rreo`, `test_02_divergencia_com_rreo_nao_altera_valor_da_api`, `test_fontes_declaram_a_hierarquia_elotech_rreo`.
- **Reinterpretação:** onde os relatórios dizem "fonte oficial (RREO)", leia "publicação oficial independente usada para conferência".

### C2. Legenda "CONFIRMADO — evidência suficiente na fonte oficial (RREO)" (Etapa 02)
- **Etapa:** 02 (legenda do relatório).
- **Estado anterior:** o RREO aparece como a fonte que confirma.
- **Correção:** reinterpretação, sem editar o relatório.
- **Motivo:** a 04.4 mostrou que cada RREO é um retrato da data de emissão; a API mostra a base atual.
- **Impacto:** os status da Etapa 02 continuam válidos **como afirmação sobre o significado dos campos da API**. A coincidência com o RREO prova o significado; não faz do RREO a base.
- **Tipo:** D.
- **Testes:** não se aplica.
- **Reinterpretação:** "CONFIRMADO pelo RREO" = "o campo da API tem esse significado, verificado pela coincidência exata com a publicação oficial vigente na data do teste".

### C3. "O Anexo VII do RREO se reconstrói a partir da API, coluna a coluna, ao centavo" (Etapa 02 §1.1)
- **Etapa:** 02.
- **Estado anterior:** a afirmação já trazia a condição ("`dataInicial` = 01/01 e dados que não tenham sido alterados depois da emissão do RREO") e o item 9 do mesmo resumo já dizia que a API mostra o estado atual e cada RREO é um retrato do dia da emissão. O título, lido sozinho, sugere reconstrução geral.
- **Correção:** nenhuma no conteúdo; reinterpretação do alcance, com o que a 04.4 mediu.
- **Motivo:** a condição raramente vale para exercícios já publicados: dos PDFs conciliados na 04.4, só o de 2021 da entidade 1 fecha nas 12 colunas (04.4 §8).
- **Impacto:** nenhum valor muda.
- **Tipo:** D.
- **Testes:** `test_674_426_01_e_coerencia_entre_publicacoes` (reproduz a tabela de coerência da 04.4).
- **Reinterpretação:** a reconstrução ao centavo comprova o **significado dos campos** da API; não é expectativa de que a API reproduza cada RREO.

### C4. "Com as duas versões 2, o RREO consolidado de 2025 é reconstruído ao centavo" (Etapa 03 §1 e §7.2)
- **Etapa:** 03.
- **Estado anterior:** a coincidência de 2025 com RREO-COL v2 + CONS-PAR v2 é apresentada como "indício forte" da leitura "cópia = remanescente".
- **Correção:** reinterpretação.
- **Motivo:** a 04.4 mostrou que CONS-PAR v2 só fecha 2025 em 31/12, quebra nos cortes intermediários e em 2026 (o RREO de 2026 conta os dois lados), e que a hipótese temporal (cópias inseridas depois das publicações de 2025) explica o mesmo valor (925.702,62) de forma mais simples.
- **Impacto:** CONS-PAR v2 continua **experimental**; a coincidência não a valida.
- **Tipo:** D, R.
- **Testes:** `test_pares_1_15_em_2025`, `test_espelhamento_2026`, `test_governanca_da_revisao_corretiva`.
- **Reinterpretação:** "coincidência numérica compatível com duas leituras; a natureza das cópias continua NÃO DETERMINADA".

### C5. RREO-COL v1 marcada como estável (revisão de código, item 17)
- **Etapa:** 03 (catálogo), 04.2.
- **Estado anterior:** `uso = 'estavel'`, usada na visão "publicado" e na conciliação.
- **Correção:** decisão de governança em `regra_situacao`: **não recomendada**, sem compor indicador. A linha da tabela `regra` **não** foi editada (imutável); a decisão original ("operacional", 29/09) continua no histórico; a v1 continua calculada lado a lado na reconciliação.
- **Motivo:** nunca concilia mais colunas que a v2 e concilia menos em 2020, 2021, 2022 e 2025; seu L = e + k difere da soma de S1 (04.4 §14).
- **Impacto:** nenhum valor calculado muda. No painel, a projeção pela v1 aparece como **analítica**.
- **Tipo:** R.
- **Testes:** `test_governanca_da_revisao_corretiva`, `test_08_...`.
- **Reinterpretação:** o L da RREO-COL v1 não é saldo; o saldo é a soma de S1.

### C6. CANC v1 marcada como estável e "FORTE EVIDÊNCIA" (item 18)
- **Etapa:** 02/03.
- **Estado anterior:** a divisão de `canceladoAProc` em processado/não processado aparecia como estável.
- **Correção:** **não recomendada**, sem compor indicador; continua calculada (derivação inalterada). O total de cancelamentos (`canceladoAProc`) não depende dela.
- **Motivo:** diverge da divisão (d)/(j) dos RREOs de 2017 a 2021.
- **Validação nesta revisão** (sem regra nova): o script da própria 04.4 (`docs/stages/04-pipeline/batches/hipotese_canc.py`), reexecutado sobre a base completa, mostra que em 2017 a hipótese do excedente fecha (j) ao centavo e deixa (d) em −95.522,00 (7 registros "ambos"), em entidade e consolidado. A 04.4 registrava (j) fechando em 2018–2021; com 2017, o período vai de 2017 a 2021. Continua HIPÓTESE com evidência mista (piora 2022 e 2023).
- **Impacto:** no detalhe de empenho, a divisão sai como **analítica**.
- **Tipo:** R.
- **Testes:** `test_caso_11963_2016`, `test_governanca_da_revisao_corretiva`.
- **Reinterpretação:** 11963/2016 continua com saldo 0; a classificação do cancelamento como "de processado" é analítica.

### C7. CONS-PAR v1 e v2
- **Etapas:** 02 (adendo), 03, 04.4.
- **Estado anterior:** experimentais, calculadas lado a lado como visão analítica.
- **Correção:** decisão registrada em 30/09 confirmando "experimental, só visão analítica"; o lado original de um par nunca é apagado; os dois lados continuam separados no bruto, na normalização e nos indicadores; `Painel.pares` mostra os pares sem consolidar nada.
- **Motivo:** a 04.4 (§14) reduziu a confiança nas duas como explicação do RREO.
- **Impacto:** nenhum valor muda.
- **Tipo:** R.
- **Testes:** `test_07_SINTETICO_pares_espelhados_continuam_separados_no_bruto`, `test_espelhamento_2026`, `test_pares_1_15_em_2025`.
- **Reinterpretação:** nenhuma visão analítica é indicador publicado; a natureza das cópias continua NÃO DETERMINADA.

### C8. Constantes de negócio fixas e duplicadas no código (item 21)
- **Etapa:** 04.2 (código de produção).
- **Estado anterior:** 2.400.000 e entidades 1 e 15 em `derivar.py` e `comparador.py`; entidade 1 do RREO por entidade fixa na derivação e no coletor.
- **Correção:** tabela imutável `regra_parametro` (PAR-24 v1: entidades 1/15, base 2.400.000, conferência por CNPJ/CPF e data; CONC-RREO v1: entidade 1), lida a cada derivação; `[rreo] entidade_publicacoes` no `config.toml` para a coleta.
- **Motivo:** mudar parâmetro passa a exigir versão nova da regra, rastreável.
- **Impacto:** transcrição sem mudança de significado: hashes idênticos.
- **Tipo:** C, R.
- **Testes:** `test_09_mudanca_de_regra_exige_nova_versao`, `test_parametros_de_negocio_nao_estao_espalhados_no_codigo`.
- **Reinterpretação:** não se aplica (os valores das regras não mudaram).

### C9. Evidência externa sem comando de registro (item 14)
- **Etapas:** 03 (esquema), 04.1–04.4.
- **Estado anterior:** tabela `evidencia_externa` vazia e sem caminho de gravação.
- **Correção:** `python -m rp registrar-evidencia --tipo --descricao --arquivo --origem [--data] [--observacao]`: guarda o arquivo no armazém (SHA-256), grava manifesto imutável em `data/snapshots/evidencias/`, registra a linha (com origem, observação, manifesto e identificador estável) e entra na reconstrução do banco e no `verificar`.
- **Motivo:** decisão de governança precisa apontar para evidência registrada (ex.: resposta do e-SIC).
- **Impacto:** nenhum valor; a tabela continua vazia até o primeiro registro.
- **Tipo:** C.
- **Testes:** `test_evidencia_externa_registrada_com_sha256_e_reconstruivel`.
- **Reinterpretação:** não se aplica.

### C10. Método da extração do RREO não registrado (item 36)
- **Etapas:** 04.2–04.4.
- **Estado anterior:** só a versão do extrator ficava em `rreo_valor`; a versão do PyMuPDF/MuPDF e o PDF de origem não ficavam junto dos valores, e o PDF que falhava só aparecia na observação da normalização.
- **Correção:** tabela `rreo_extracao`: para cada PDF, extrator (`rp-rreo-coordenadas/1`), biblioteca e versão (`PyMuPDF 1.28.2 / MuPDF 1.28.2`), SHA-256 do PDF, `idArquivo`, rótulo, data da extração, quantos valores saíram ou o erro.
- **Motivo:** os valores transcritos dependem do método; o método fica junto.
- **Impacto:** nenhum valor; os 3 PDFs não lidos (2016 entidade, 2018, 2019) ficam registrados com o erro.
- **Tipo:** C.
- **Testes:** `test_extracao_do_rreo_registra_metodo_e_pdf`.
- **Reinterpretação:** não se aplica.

### C11. Não havia camada de consulta nem indicador (item 44)
- **Etapas:** 04 (produção).
- **Estado anterior:** nenhuma interface; os indicadores só existiam como consultas avulsas dos relatórios.
- **Correção:** `app/rp/painel` — `Painel` somente leitura (URI `mode=ro` + `PRAGMA query_only`), sem chamar a API:
  - `cortes`, `entidades`, `indicadores`, `evolucao`, `por_dimensao`, `empenhos`, `detalhe_empenho`, `fornecedores`, `pares`, `retratos`, `comparar_retratos`, `reconciliacao`, `coerencia_entre_publicacoes`, `visao_analitica`, `regras`, `evidencias`, `fontes`, `metodologia`, `dicionario_campos`;
  - linha de comando: `python -m rp painel <consulta>` (JSON);
  - todo valor sai com natureza, regras usadas e sua situação, fonte, rótulo de retrato e proveniência até o endpoint; regra não operacional faz a consulta falhar (`RegraNaoOperacional`); valores em centavos, sem arredondamento.
- **Motivo:** especificação da revisão: infraestrutura para o futuro dashboard, sem inventar frontend.
- **Impacto:** nenhum valor muda; só leitura.
- **Tipo:** A, C.
- **Testes:** `test_03` a `test_12` e `test_casos_reais.py`.
- **Reinterpretação:** não se aplica.

### C12. Entidade inexistente no exercício tratada como parte do total (itens 22 e 23)
- **Etapas:** 04.3 e 04.4 (visão do Município).
- **Estado anterior:** a visão do Município exige todas as entidades do catálogo **atual**; combinações fora do catálogo foram consultadas e devolveram 0 registros.
- **Correção:** o painel cruza o catálogo de exercícios de cada entidade: "fora do catálogo oficial" = não existia, **não é RP zero**; não entra no total; a consulta por entidade responde "indisponível". A derivação não foi alterada (para não mudar o hash).
- **Motivo:** entidade que não existia no exercício não pode aparecer como entidade com RP zero.
- **Impacto:** totais iguais aos da derivação (as combinações fora do catálogo têm 0 registros), agora com o significado correto.
- **Tipo:** A.
- **Testes:** `test_06_SINTETICO_entidade_fora_do_catalogo_nao_e_rp_zero`, `test_entidade_inexistente_no_exercicio_nao_e_zero`.
- **Reinterpretação:** nos relatórios da 04.4, "entidade X em ano Y: 0 registros" para combinação fora do catálogo significa "não existia", não "RP zero".

### C13. Nome "visão publicado" da derivação
- **Etapas:** 03 (modelo), 04.2.
- **Estado anterior:** `visao_valor.visao = 'publicado'` guarda a projeção **da API** nas colunas do RREO.
- **Correção:** documental e de apresentação. O painel a rotula "projeção dos registros da API nas colunas do RREO (NÃO é o valor publicado)", com natureza analítica enquanto nenhuma RREO-COL for operacional. O nome na tabela foi mantido (faz parte do `hash_resultado`).
- **Motivo:** o nome sugere valor do RREO.
- **Impacto:** nenhum valor muda.
- **Tipo:** D.
- **Testes:** `test_casos_reais.py` (reconciliação e coerência separam `publicado` de `derivado` e `analitico`).
- **Reinterpretação:** onde os relatórios citam a "visão publicada", leia "visão da API no formato do RREO".

### C14. Snapshot com 0 registros não deixava rastro na normalização (achado desta revisão)
- **Etapas:** 04.2 (normalização).
- **Estado anterior:** não havia como saber se um snapshot vazio (comum nas entidades 3, 6, 9, 10 e 11) já tinha sido processado.
- **Correção:** `normalizacao_execucao.ultima_coleta_id` (v4); o painel só usa snapshots até esse limite e avisa quando há snapshot não processado, em vez de mostrar zero.
- **Motivo:** evitar que um corte ainda não processado apareça como RP zero.
- **Impacto:** nenhum valor muda (a normalização lê as mesmas coletas).
- **Tipo:** C.
- **Testes:** `test_SINTETICO_snapshot_ainda_nao_processado_nao_vira_zero`, `test_06_...`.
- **Reinterpretação:** não se aplica.

### C15. Dados pessoais sem camada pública (item 45, em parte)
- **Etapas:** 04 (produção).
- **Estado anterior:** nome, código e CNPJ/CPF do credor em todas as consultas; razão social de MEI com o CPF do titular.
- **Correção:** `painel/publico.py`: listagens e agregados sem identificação do credor; detalhe com nome de pessoa jurídica sem documento; nome de pessoa física omitido; campos do credor só no nível `interno`. A camada bruta e os backups continuam guardando os dados como a API devolveu (são a evidência).
- **Motivo:** minimização de dados na exposição pública.
- **Impacto:** nenhum valor muda.
- **Tipo:** C.
- **Testes:** `test_12_SINTETICO_dado_sensivel_fora_da_visao_publica`, `test_publico_mascara_documentos_no_nome`.
- **Reinterpretação:** não se aplica.

### C16. Itens desatualizados da revisão de código de 30/09
- **Etapa:** revisão de código (`REVISAO_CODIGO_20260930.md`).
- **Estado anterior e correção:**
  - item 24 ("o projeto não está sob controle de versão") — desatualizado: o projeto está no GitHub desde 30/09/2026 (`6945d31`, `adc7510`);
  - item 46 (dados na pasta do OneDrive) — complementado: além do OneDrive, os dados brutos e o armazém estão no repositório **público** do GitHub, por decisão do responsável (30/09/2026);
  - itens 14, 21, 36 e 44 — tratados por C9, C8, C10 e C11; itens 17 e 18 — tratados por governança (C5, C6); itens 22, 23 e 45 — tratados em parte (C12, C15).
- **Motivo:** o documento de revisão não é editado; a atualização fica aqui.
- **Impacto:** nenhum valor.
- **Tipo:** D.
- **Testes:** não se aplica.
- **Reinterpretação:** ler a lista de pontos negativos com estas atualizações.

### C17. Explicações das diferenças só existiam em texto
- **Etapas:** 02 a 04.4.
- **Estado anterior:** as causas das diferenças estavam espalhadas nos relatórios e lotes.
- **Correção:** `painel/explicacoes.py` transcreve, com fonte e grau de evidência, as explicações dos relatórios (classes T, C, R, P, E, H e ND da 04.4 §9) para a área de reconciliação e para a coerência entre publicações. Uma diferença só é "explicada" quando todas as explicações aplicáveis são explicadas; mistura vira "parcialmente explicada"; sem explicação, "não determinada".
- **Motivo:** a área de reconciliação precisa mostrar o status de cada diferença sem análise nova.
- **Impacto:** nenhum valor muda.
- **Tipo:** D, C.
- **Testes:** `test_resumo_so_chama_de_explicada_quando_tudo_esta_explicado`, `test_explicacoes_apontam_documentos_que_existem`.
- **Reinterpretação:** não se aplica.

---

## 3. Achados da 04.4 incorporados à arquitetura

1. **A API mostra o estado atual da base; cada RREO é um retrato do momento da emissão.** Onde as publicações são coerentes entre si (2020→2022), a API as reproduz; quase sempre ela reproduz a abertura publicada no ano **seguinte**. → rótulo de retrato em todo valor; coerência entre publicações no painel, com as colunas da API ao lado.
2. **Alterações retroativas:** lançamentos com data no passado feitos depois da emissão; cópias inseridas depois aparecem em cortes antigos (2401751 com 8.410,00 desde o corte de 2024). → texto "Importante" da metodologia; retrato histórico sempre marcado.
3. **Coerência entre publicações** (L de A × (a)+(f) de A+1), reproduzida ao centavo pelo painel para 2020–2026:

| | 20→21 | 21→22 | 22→23 | 23→24 | 24→25 | 25→26 |
|---|--:|--:|--:|--:|--:|--:|
| entidade 1 | 0,00 | 0,00 | 162.536,97 | 47.857,04 | **674.426,01** | 925.702,62 |
| consolidado | −180.334,82 | 0,00 | 162.536,97 | 44.654,52 | 669.761,65 | 925.702,62 |

   2017→2020 do consolidado vêm da leitura de investigação dos PDFs de 2018/2019, que o extrator de produção não lê.
4. **Classes de diferença** (04.4 §9) → `explicacoes.py`, com o mesmo grau de evidência.
5. **Pares espelhados:** 1 par em 2024 (relação "outra", execução em B); 20 em 2025 ("A = saldo final de B" sobe de 2 para 9, 11 iguais, "outra" cai de 7 para 0); 731 em 2026, todos iguais, execução nunca em B. → `Painel.pares`; natureza das cópias NÃO DETERMINADA.
6. **Confiança das regras:** RREO-COL v1 diminuiu, v2 aumentou, CONS-PAR v1/v2 diminuíram, PAR-24 inalterada. → governança (C5–C7), sem promoção.
7. **Limitações:** extrator não lê 2016 (entidade), 2018 e 2019; consolidado antigo sem detalhe por órgão; data de lançamento ≠ data de registro; teste temporal de ~5 h; comparador sem mudança real em dado real. → registradas no painel (`pdfs_sem_valores_transcritos`) e aqui.

## 4. Candidatas não promovidas e critérios propostos (não aplicados)

Nenhuma regra foi criada ou promovida. Critérios **propostos** para decisão do responsável:

| Candidata | Situação | Critério proposto para promover |
|---|---|---|
| RREO-COL v2 como padrão | experimental | (a) nunca conciliar menos que a v1 em nenhum documento de 2017–2026 (observado até aqui); (b) ao menos um caso explicado que não seja cópia 24xxxxx (Etapa 03 §10); (c) resposta do e-SIC sobre o critério de classificação do RREO, registrada como evidência; (d) decisão registrada em `regra_situacao` apontando a evidência |
| CANC v2 (excedente vai para (d)) | não criada | fechar (d) e (j) em 2017–2023 sem piorar nenhum ano, ou documento do Município com o critério; evidência hoje é mista |
| CONS-PAR v3 ("saldo final de B" no fechamento do exercício) | não criada | resposta do e-SIC sobre a natureza das cópias; enquanto isso, a hipótese temporal explica o mesmo |

## 5. Portões (seção 33 da especificação)

| Portão | Resultado |
|---|---|
| Suíte de produção completa | 174/174 (138 anteriores + 24 em `test_correcoes.py` + 12 em `test_casos_reais.py`) |
| 26 testes de investigação (Etapa 03) | 26/26 |
| Integridade armazém × banco (`python -m rp verificar`) | sem problemas |
| Hash do bruto (tabelas `coleta`, `resposta_bruta`, `objeto_bruto`, `coletor_versao`) | idêntico ao de antes da revisão |
| Snapshots (466 manifestos, 375 objetos) e dados brutos das Etapas 01/02 (262 arquivos) | idênticos, arquivo a arquivo (SHA-256) |
| Valores históricos | derivações 21 e 22 intactas; as novas 23 (atual) e 24 (29/09) têm os mesmos `hash_resultado` e as mesmas tabelas `visao_valor` e `conciliacao_rreo` (hash por tabela) |
| Banco reconstruído só do armazém real (teste `test_casos_reais.py`) | mesmos hashes 2f6b4e29… e b8a0b2ed…; nenhum arquivo do armazém muda |

**Diferenças antes × depois, todas explicadas:**
- `esquema_versao` ganhou a linha **v4** (a migração só acrescenta tabelas, colunas e um índice). Por isso o hash agregado da camada 0 (`execucoes.hash_camada0`, que inclui `esquema_versao`) mudou de `3fe902f65a54cfb4` para `733670693c01d015`; as tabelas do bruto, uma a uma, não mudaram, e `evidencia_externa` continua vazia.
- Nova normalização **13** (a 12 continua) com 36 linhas a mais: as de `rreo_extracao`.
- Novas derivações **23** e **24**; as 21 e 22 continuam. Nenhuma execução foi apagada.
- Backup antes da migração, pela política do projeto: `data/backups/20260930-145737_antes-migracao-v3-v4.sqlite` (120.520.704 bytes). **Esse arquivo passa do limite de 100 MB por arquivo do GitHub e não deve ser commitado sem decisão sua** (Git LFS ou mantê-lo só no OneDrive).
- Banco ativo: 230 MB (as execuções antigas foram mantidas).

Nenhuma divergência foi causada pela alteração arquitetural.

**Evidência dos portões** (em `docs/stages/04-pipeline/results/`):
- `revisao_corretiva_testes_producao.txt` e `revisao_corretiva_testes_investigacao.txt`: saídas completas das duas suítes;
- `revisao_corretiva_estado_antes.json` e `revisao_corretiva_estado_depois.json`: retratos do banco ativo, do armazém e dos dados brutos antes e depois, gerados por `revisao_corretiva_estado.py` (somente leitura).

**Ordem seguida no banco ativo:** ensaio completo em duas cópias (migração, normalização, derivações e portões) → `python -m rp processar` (backup e migração v3→v4, normalização 13, derivação 23) → `python -m rp processar --normalizacao 13 --em 2026-09-29T23:59:59-03:00` (derivação 24) → `python -m rp verificar` → comparação dos retratos antes/depois.

## 6. O que não mudou (§25)

- `RELATORIO_ETAPA01.md`, `RELATORIO_ETAPA02.md`, `RELATORIO_ETAPA03.md` e `RELATORIO_04_4.md`: sem edição (as reinterpretações estão aqui).
- Snapshots, objetos brutos, PDFs, respostas originais, hashes e dados brutos: sem alteração.
- Tabela `regra`: nenhuma linha editada; decisões novas só em `regra_situacao`.
- Os 7 backups preservados (`PRESERVAR.txt`) continuam lá.
