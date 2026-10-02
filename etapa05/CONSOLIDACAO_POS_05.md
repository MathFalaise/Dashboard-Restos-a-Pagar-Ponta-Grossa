# Encerramento formal e consolidação técnica pós-Etapa 05

Data: 02/10/2026. Ramo `pos-05-consolidacao`, criado do commit da tag `etapa-05-final` (`b38e884`).

**Regra desta operação:**

```text
PRESERVAR DADOS > PRESERVAR REGRAS > PRESERVAR HOMOLOGAÇÃO > ENCERRAR ETAPA 05 > CONSOLIDAR ENGENHARIA > SÓ DEPOIS EVOLUIR
```

**O que não mudou:**
- **Dados e regras:** nenhum snapshot, dado bruto, normalização, derivação, regra, fórmula, hash ou valor homologado.
- **Interface:** só a seleção de corte, corrigida na seção 4.
- **Fora desta operação:** nenhuma funcionalidade nova, nenhuma coleta, nenhuma CI implantada.

---

## 1. Auditoria do estado (antes de qualquer mudança)

```text
ESTADO ATUAL
- branch: subetapa-05.7
- commit: b38e8841eba6f5fc4911e8f9c2a9084ad4669fdb (05.7)
- tag 04: etapa-04-final → a6bd27c (objeto ed6f35b), local e no GitHub, inalterada
- tag 05: etapa-05-final → b38e884 (objeto 892940f), local e no GitHub (enviada pelo responsável)
- PRs abertos: #1 a #11, base main (adc7510), nenhum mesclado; cadeia linear #1 → #11
- testes: 348/348 produção, 26/26 investigação
- verificar: sem problemas
- portoes: apto
- integridade: estado = homologação 04.6 (bruto, armazém, derivações: 14 de 14 blocos idênticos;
  0 diferenças na camada painel e nos 5.575 valores de tela); hash_resultado 2f6b4e29… / b8a0b2ed…;
  hash_camada0 733670693c01d015…; nenhum arquivo protegido mudou entre as duas tags
- pendências: ver seção 2
```

**Cadeia da Etapa 05** (12 commits entre as tags):

| Fase | Commits |
|---|---|
| plano | `01dc272`, `89d6092`, `988a7cc` |
| 05.1 | `8d22313` |
| 05.2 | `eac9b4d`, `075b9f7`, `fa3f1c7` |
| 05.3 | `6ab3dab` |
| 05.4 | `feca7b7` |
| 05.5 | `017b2b2` |
| 05.6 | `3e60c57` |
| 05.7 | `b38e884` (homologação final) |

**A 05.7 é o estado final homologado:**
- os 14 critérios do plano (seção 17) estão conferidos no relatório final;
- a auditoria acima os reproduz no mesmo commit.

**Conferências:**
- **Marcadores TODO/FIXME:** nenhum; as ocorrências são a palavra "TODO" em português.
- **Documentação desatualizada:** o relatório final (seções 6 e 7) e o README diziam "tag local", e o relatório ainda dizia "ramos sem envio".
  - Corrigido no commit de encerramento por acréscimo (seção 8 do relatório), sem reescrever o texto da 05.7.

Evidências: `resultados/pos05_auditoria_*`.

## 2. Classificação das pendências

| # | Pendência | Classe | Justificativa |
|---|---|---|---|
| 1 | Seleção de corte trocava o corte ou exercício pedido por outro | **A** (corrigida, seção 4) | Mostrava valores de um corte que não foi pedido, e na tela de pares sem nenhum aviso. Contraria a regra da própria interface ("valor inválido nunca vira valor adivinhado") e o tratamento explícito de ausência |
| 2 | Relatório final e README com estado de envio desatualizado | **A** (corrigida) | Informação factual errada no documento de encerramento |
| 3 | Aprovação formal dos relatórios 05.4–05.6 e do final | **B** | Decisão do responsável; não é defeito técnico |
| 4 | D1 não executada | **B** | Decidido no plano (seção 10): fora do caminho crítico. A tag representa a base de 29–30/09/2026 (seção 8) |
| 5 | Limitações das fontes: cópias 24xxxxx, RREO 2016/2018/2019 não lidos, 66/91 diferenças não determinadas, base retroativa | **B** | Propriedades dos dados, não da implementação da 05 |
| 6 | Anomalias contadas por snapshot; verificação fora do catálogo | **B** | Comportamento documentado da derivação, que não pode mudar |
| 7 | `consulta.py` (2.022 linhas) e `paginas.py` (1.710) | **C** | Dívida técnica (seções 5 e 6); refatorar agora arriscaria a homologação sem ganho para o encerramento |
| 8 | Hierarquia: primeiro número a 1.624 px no celular | **C** | Melhoria de interface (seção 7); não é erro de dado |
| 9 | CI | **C** | Viável, com proposta (seção 9); depende de aprovação |
| 10 | Dependências transitivas sem versão fixa | **C** | Reprodutibilidade (seção 11) |
| 11 | Dados pessoais no repositório público | **C**, com decisão do responsável | Risco (seção 10); qualquer remoção exige decisão expressa |
| 12 | Licença do PyMuPDF (AGPL) e repositório sem licença | **C** | Relevante só para distribuição e publicação (seção 11) |
| 13 | Execução em outro Python, outro sistema ou outra máquina | **C** | Não testado (seção 12) |
| 14 | PRs #1–#11 abertos | **C** (operacional) | Mesclagem é decisão do responsável; ordem #1 → #11 |
| 15 | e-SIC | **D** para a engenharia | Envio pelo responsável (CPF); a resposta segue a seção 16.3 do plano |
| 16 | Ranking por credor, consolidação dos pares, promoção de regra experimental | **D** | Fora do escopo (plano, seção 8) |
| 17 | Servidor da porta 8050 com código anterior à 05.4 | **D** | Processo do responsável; basta reiniciar `python -m rp interface` |

**Nenhuma pendência A ficou aberta.** A tag continua válida: as duas correções A vieram depois dela e não tocam dado, regra nem valor homologado.

## 3. Encerramento formal

- **A tag `etapa-05-final` já existia** e não foi recriada nem movida:
  - objeto `892940f83efe8332013725708d2a0451068b79e7`;
  - commit `b38e8841eba6f5fc4911e8f9c2a9084ad4669fdb`;
  - o GitHub aponta para o mesmo objeto.
- **Relação com `etapa-04-final`:** `a6bd27c` é ancestral de `b38e884`.
- **SHA registrado** no relatório final, seção 8 (commit `bf2c780`).
- **D1 continua não executada** e não foi misturada com a tag.

## 4. Seleção de exercício e corte (correção)

**Evidência** (código da tag, `app/rp/interface/paginas.py`):

- `_selecao` trocava o exercício pedido pelo mais recente e o corte pedido pelo "mais recente com o Município completo". O aviso mostrado era:

  ```text
  Corte 15/03/2025 não disponível no exercício 2025: mostrado outro corte.
  ```

  - O aviso não dizia qual corte entrou no lugar; os valores exibidos eram do outro corte.
- A tela de pares (`pares`) usava a mesma seleção **sem exibir o aviso**: a troca era silenciosa.
- A variação trocava o par pedido em dois casos:
  - posterior igual ao primeiro corte;
  - anterior inválido.
- A docstring de `Parametros` (`aplicacao.py`) diz que "valor inválido vira erro 400, nunca um valor adivinhado". A seleção contrariava essa regra.
- Nenhum teste cobria o caso.

**Correção mínima** (só `paginas.py`, sem tocar a camada painel):

| Situação | Antes | Agora |
|---|---|---|
| Nada pedido | padrão | o mesmo padrão (sem mudança) |
| Corte pedido não processado | outro corte, com aviso (pares: sem aviso) | o corte pedido no título e um aviso com a lista dos cortes processados do exercício. A camada painel devolve a situação do dado de cada entidade, por exemplo "corte não coletado para a(s) entidade(s) […]", sem nenhum valor |
| Exercício pedido sem corte | exercício mais recente | "Sem dados processados", com os exercícios que têm corte |
| Pares, corte não processado | "0 pares" de outro corte | indisponível: ausência não é zero (a consulta de pares não informa disponibilidade, por isso a tela não a chama) |
| Variação, par impossível | outro par, com aviso | indisponível com o motivo e o formulário. Anterior não processado segue para a camada painel, que explica |

**Validação:**
- `app/tests/test_selecao_pos05.py`: 5 testes.
  - Passam com a correção.
  - Com o código da tag, **4 falham**; só passa o que confirma que o padrão não mudou.
- **Teste da 05.5 ajustado:** `test_variacao_05_5.py::test_SINTETICO_tela_da_variacao_e_do_empenho` afirmava a troca, esperando "imediatamente anterior" com o par invertido.
  - Foi o único teste a falhar com a correção (352 de 353 passaram).
  - A asserção passou a exigir o comportamento corrigido: página 200, indisponível com o motivo, sem nenhum valor.
  - Nenhuma outra asserção mudou.
- Estado antes × depois: 0 diferenças nos 5.575 valores de tela e na camada painel; bruto, armazém e derivações idênticos.
- Telas da Etapa 05 (100.201 valores) e acessibilidade refeitas; números na seção 13.

## 5. `consulta.py`: dívida técnica (sem refatoração agora)

**Tamanho:** 2.022 linhas.
- São 86 funções e métodos (quase todos na classe `Painel`), de 10 responsabilidades.
- Todos dependem de `_corte`, `_vigentes`, `_catalogo` e `contexto`.

| Módulo futuro | Conteúdo hoje em `consulta.py` | Linhas |
|---|---|---|
| `contexto.py` | abertura somente leitura, `contexto`, `_vigentes`, `instante`, `fechamento`, `diferenca` | ~100 |
| `cortes.py` | catálogo, `_corte`, `_estado_sem_snapshot`, `_retrato`, `cortes`, retratos, entidades do corte | ~250 |
| `indicadores.py` | `_somas`, `indicadores`, conferência do saldo | ~85 |
| `series.py` | `evolucao`, corte representativo, série entre exercícios, fechamento × abertura, continuidade | ~180 |
| `dimensoes.py` | `por_dimensao`, `_por_grupo`, `_por_faixa`, `composicao` | ~165 |
| `empenhos.py` | `_registros`, filtros, `empenhos`, `detalhe_empenho`, movimentação, pares, fornecedores | ~260 |
| `variacoes.py` | `variacao`, `historico_empenho` | ~190 |
| `qualidade.py` | `qualidade`, verificações, situação das diferenças, `anomalias` | ~170 |
| `reconciliacao.py` | conciliação, documentos, coerência entre publicações, visão analítica | ~235 |
| `metadados.py` | governança, proveniência, regras, fontes, metodologia, dicionário | ~70 |

**Condições para uma refatoração futura** (subetapa própria):

- **Fachada:** `consulta.py` continua como fachada e reexporta `Painel`, `ErroDoPainel` e as constantes. Hoje elas são importadas por `interface/paginas.py`, `interface/aplicacao.py`, pelos testes e pelos scripts de resultado da 04.6 e da 05.7.
- **Técnica:** uma classe base por módulo (mixin), combinadas em `Painel`. Assim nenhuma assinatura pública muda.
- **Critério de aceite:**
  - estado antes × depois sem nenhuma diferença (`04_6_estado.py`);
  - `05_7_telas_novas.py` com 0 diferenças;
  - as duas suítes passando;
  - nenhuma consulta SQL alterada, só movida.

## 6. `paginas.py`: dívida técnica (sem reescrita agora)

**Tamanho:** 1.710 linhas e 67 funções.

| Grupo | Funções | Linhas | Mistura observada |
|---|---|---|---|
| estrutura | `documento`, `erro`, `_avisos` | ~30 | — |
| seleção e filtros | `_selecao`, `_formulario`, `_formulario_variacao`, `_filtros_empenho`, `_mais_filtros` | ~90 | regra de seleção ao lado do HTML do formulário; leitura de parâmetros dentro das telas |
| blocos comuns | `_retrato`, `_origem_*`, `_cartao`, `_pdf`, `_explicacoes` | ~90 | — |
| resumo | `resumo`, `_entidades_abrangidas`, `_conferencia` | ~85 | auditoria (retrato, snapshots) antes do resultado |
| séries | `evolucao`, `historico` e tabelas | ~200 | — |
| composição | `composicao` e tabelas | ~115 | — |
| variação | `variacao` e 10 auxiliares | ~175 | validação do par dentro da tela |
| empenhos | `entidades`, `empenhos`, `empenho`, `empenho_cortes`, `retratos`, `comparar` | ~385 | detalhe, movimentação, par e proveniência na mesma função |
| qualidade | `qualidade` e tabelas | ~150 | — |
| reconciliação | `reconciliacao`, `_coerencia` | ~90 | — |
| técnico e metodologia | `pares`, `metodologia` | ~80 | — |

**Separação futura:**
- `paginas/` como pacote, com um módulo por grupo e `paginas/__init__.py` reexportando as funções de rota (as `ROTAS` de `aplicacao.py` não mudam);
- `selecao.py` com `_selecao` e os formulários;
- `blocos.py` com os blocos comuns.

Mesmo critério de aceite da seção 5.

## 7. Interface: hierarquia (medida, sem redesign)

**Princípio:** resumo → análise → detalhamento → auditoria.

**Medição na 8051, com o código da tag:** posição do primeiro valor (`<data>`) a partir do topo da página.

| Tela | Celular 375 px | Notebook 1280×800 | O que vem antes |
|---|---|---|---|
| Resumo | 1.624 px (2 telas) | 710 px | menu 226 px, formulário 300 px, bloco do retrato 680 px com 5 identificadores de snapshot |
| Composição | 1.894 px | 881 px | formulário 363 px, retrato 679 px |
| Evolução | 1.434 px (gráfico em 1.022 px) | — | formulário 241 px |
| Variação | 1.051 px | — | formulário 424 px |
| Qualidade | 764 px | — | — |

**Problema evidente:** o bloco do retrato, obrigatório desde a 04.5, mistura duas coisas:
- o contexto essencial: exercício, corte, coleta e o texto do retrato;
- a auditoria: lista de snapshots e nota longa.

Ele fica antes do resultado e, no celular, empurra o primeiro número para duas telas abaixo.

**Proposta (não aplicada):**
1. manter no topo só a frase do retrato e a data da coleta;
2. levar "Snapshots usados" e a nota para um `<details>` ("Origem do retrato"), como já é feito nos cartões;
3. no celular, menu recolhível sem JavaScript (`<details>`), já sugerido no relatório final.

**Por que não foi aplicada agora:**
- muda a estrutura de um bloco homologado na 04.5 e na 04.6;
- é melhoria de apresentação, não condição de encerramento;
- os rótulos técnicos (S1, FAIXA v1, PAR-24, RREO-COL) já aparecem como selo secundário, depois da descrição humana.

Entra como subetapa de interface, com medição antes × depois.

## 8. D1: primeira atualização real da base

**Situação:**
- **Pendente:** nunca executada.
- **Base atual:** 466 snapshots, coletados de 29/09 19h56 a 30/09 01h27 de 2026. Os cortes bimestrais completos de 2026 vão até 31/08/2026; há também cortes só da entidade 1 (31/01, 31/03 e 31/12/2026, este posterior à coleta).
- **Procedimento documentado:** existe (`app/README.md`, "Atualização dos dados"; plano, seção 10).
- **Referência do bruto:** nunca gravada (não há `referencia_*.json`).
- **Preservação:** a D1 não altera nada do que existe, só acrescenta snapshots.
  - Os hashes a preservar são os do bruto anterior: o portão "linhas do bruto anteriores à carga idênticas às da referência" compara isso.
  - Os `hash_resultado` **vão mudar**, porque a derivação passa a incluir os novos snapshots. Isso é efeito documentado da coleta, não regressão.

**O que coletar é decisão do responsável.** Duas opções:
- **(a) Recoleta de um corte existente** (ex.: `recoletar` de 31/08/2026): testa o procedimento ponta a ponta já. Cria um segundo retrato, e o anterior fica preservado.
- **(b) Corte novo de 31/10/2026** (5º bimestre): só depois de 31/10/2026. O RREO do bimestre sai cerca de 30 dias depois.

```text
PROCEDIMENTO DE D1 (parar antes do passo 4 e pedir confirmação)
1. Ramo próprio a partir do commit homologado; registrar git HEAD e as tags.
2. Estado de referência (somente leitura), dentro de app/:
     python ../etapa04/resultados/04_6_estado.py ../etapa05/resultados/d1_estado_antes.json
     python -m rp verificar
     python -m rp portoes          (precisa dar apto)
3. Referência do bruto e backup:
     python -m rp portoes --gravar-referencia ../etapa04/resultados/referencia_AAAAMMDD.json
     python -m rp backup --motivo antes-carga-AAAAMMDD
4. Coleta (rede; API não documentada; pausa 1,5 s entre requisições). Uma das opções:
     (a) python -m rp recoletar ...                       (mesmos parâmetros de um snapshot existente)
     (b) python -m rp coletar-catalogos
         python -m rp coletar-listagem --entidade E --exercicio 2026 --data-final 2026-10-31   (cada entidade do Município)
         python -m rp coletar-rreo --exercicio 2026 --bimestres 5                              (quando publicado)
   Coleta "incompleta" ou "falhou" fica registrada e não vira retrato válido.
5. Validar: python -m rp verificar; python -m rp comparar-snapshots / comparar (o que mudou em relação ao retrato anterior).
6. Processar: python -m rp processar  (e --normalizacao/--em, se houver data histórica a reproduzir).
7. Testar: python -m pytest tests (app/) e os 26 da investigação (etapa03/validacao).
8. Portões: python -m rp portoes --referencia ../etapa04/resultados/referencia_AAAAMMDD.json  (apto obrigatório).
9. Estado depois e comparação:
     python ../etapa04/resultados/04_6_estado.py ../etapa05/resultados/d1_estado_depois.json
     python ../etapa04/resultados/04_6_comparar_estados.py ...antes.json ...depois.json ../etapa05/resultados/d1_comparacao.json
   Esperado: bruto anterior idêntico (portão de referência); cortes antigos com os mesmos valores, salvo onde o retrato
   novo do mesmo corte passa a ser o vigente. Toda diferença é listada e explicada como efeito da coleta.
10. Disponibilizar: reiniciar python -m rp interface; relatório da D1; commit próprio; nenhuma tag movida.
```

**Evidências geradas:**
- referência do bruto e backup;
- os manifestos e objetos novos em `snapshots/`;
- `verificar`, `portoes --referencia`, as duas suítes;
- estado antes e depois e a comparação, com toda diferença explicada;
- log da coleta.

## 9. CI: avaliação (nada implementado)

| Item | Situação verificada |
|---|---|
| Sistema | só Windows 11 comprovado |
| Python | 3.14.3 (o README aceita 3.11+, não testado) |
| Dependências | `requests==2.34.2`, `pymupdf==1.28.2`, `pytest==9.1.1`; transitivas sem versão (seção 11) |
| Comandos | `python -m pytest tests` (app/), `python -m pytest tests` (etapa03/validacao), `verificar`, `portoes` |
| Dados reais | os testes **não** usam o banco ativo: as fixtures montam bancos temporários a partir do armazém versionado (`snapshots/`, 15 MB, 466 snapshots) e de dados sintéticos. A rede fica bloqueada nos testes de interface |
| Banco | ativo com 230 MB, fora do repositório; reconstruível em cerca de 30 s (`reconstruir` + `processar`, como na instalação limpa) |
| Tempo | cerca de 6 min (345 s) a suíte de produção; 13 s a investigação |
| Segredos | nenhum: a coleta não roda em CI, e os dados já estão no repositório |

**Conclusão:** há base para uma CI confiável sem mudar a arquitetura. A proposta, a aprovar antes de implementar:
- **Gatilho e plataforma:** um workflow do GitHub Actions em `windows-latest` com Python 3.14, em PR e push.
- **Instalação:** `pip install -r app/requirements-dev.txt`.
- **Verificações:**
  - as duas suítes;
  - `reconstruir` + `processar` num diretório temporário (`RP_DADOS_LOCAIS`);
  - os hashes esperados (`2f6b4e29…`, `b8a0b2ed…`), `verificar` e `portoes`.
- **Fora da CI:** coleta e rede (salvo o pip).
- **Segunda etapa:** matriz com Ubuntu e outra versão do Python, **como teste**, não como portão, até ser comprovada.

**Riscos:** o tempo de execução e a ordem de arquivos do NTFS × ext4, que precisam ser verificados na primeira execução Linux.

## 10. Dados e privacidade

**O repositório é público** (GitHub, visibilidade `public`) e não tem licença.

| Conteúdo versionado | Dados pessoais | Situação |
|---|---|---|
| `snapshots/` (841 arquivos, 466 snapshots da API, ~15 MB) | nome do credor, CNPJ e CPF **já mascarado pela API**; **44.503 registros de pessoa física com nome**; 89.006 ocorrências de CPF mascarado | decisão do responsável de 30/09/2026 (`.gitignore`): "dados públicos do portal" |
| `etapa02/dados_brutos/` | mesmos campos (51.648 CPFs mascarados) | idem |
| `etapa01/amostras_brutas/` | 1.247 CPFs mascarados. Uma amostra de pagamentos (empenho 5659/2025) tem banco, agência e conta; o credor é a CAIXA ECONOMICA FEDERAL (pessoa jurídica) | risco baixo (conta institucional) |
| `backups/` (4 SQLite versionados) | os de 30/09 repetem os registros (6.196 CPFs mascarados cada); o de 120 MB fica fora (`.gitignore`) | idem |
| telefones e e-mails | só institucionais (catálogo de entidades, normas, OpenAPI) | sem risco |
| `esic/` | rascunho sem CPF do responsável | sem risco |
| testes | CPF completo só sintético ("123.456.789-01") | sem risco |
| banco ativo, logs | fora do repositório e fora do OneDrive | privado |

**A interface já minimiza** (`painel/publico.py`):
- nunca lista nome nem documento de credor;
- omite o nome de pessoa física;
- mascara documento dentro de razão social.

O risco está no **bruto versionado**, não na tela.

**Pode ficar público:**
- código e documentação;
- agregados e evidências sem identificação.

**Proposta de procedimento seguro** (nada foi apagado nem alterado; a decisão é do responsável):
1. **Menor impacto:** tornar o repositório privado.
   - É reversível e não muda nenhum SHA, tag, hash de manifesto nem PR.
2. **Repositório futuro público:** separar código e documentação dos dados.
   - O bruto vai para um repositório ou armazenamento privado. O código já aceita `snapshots` em outra pasta (`config.toml`).
   - Antes disso, avaliar a base legal da republicação (LGPD: minimização, mesmo para dado já publicado pelo portal).
3. **Remover do histórico** (`git filter-repo`) só com decisão expressa:
   - muda todos os SHAs;
   - invalida `etapa-04-final` e `etapa-05-final`, os PRs e as referências dos relatórios;
   - clones e forks já feitos continuam com os dados.
   - Exige backup integral antes e nova homologação dos hashes do armazém.

## 11. Licenças e dependências

| Dependência | Versão (ativo / instalação limpa) | Licença | Uso no projeto | Risco |
|---|---|---|---|---|
| requests | 2.34.2 | Apache-2.0 | coletor (`rp/http.py`) | nenhum |
| urllib3 | 2.7.0 / 2.8.0 | MIT | transitiva | versão não fixada |
| idna | 3.19 / 3.20 | BSD-3-Clause | transitiva | versão não fixada |
| charset-normalizer | 3.5.1 / 3.5.2 | MIT | transitiva | versão não fixada; caminho longo no Windows (05.7) |
| certifi | 2026.7.22 | MPL-2.0 | transitiva (certificados) | baixo (copyleft por arquivo, sem modificação) |
| **pymupdf** | 1.28.2 | **AGPL-3.0 ou licença comercial Artifex** | `rp/normalizar.py`, importado sob demanda: transcrição dos PDFs do RREO no `processar`. A interface não importa (teste da 04.6) | **médio:** distribuir o projeto com PyMuPDF sujeita o conjunto à AGPL-3.0; oferecer como serviço de rede uma versão modificada exige publicar o código |
| pytest, pluggy, iniconfig | 9.1.1, 1.6.0, 2.3.0 | MIT | testes | nenhum |
| packaging | 26.3 | Apache-2.0 ou BSD-2-Clause | testes | nenhum |
| colorama, Pygments | 0.4.6, 2.21.0 | BSD | testes | nenhum |

A interface e a camada painel usam só a biblioteca padrão.

**Alternativas ao PyMuPDF** (não aplicadas): pypdf (BSD-3), pdfplumber/pdfminer.six (MIT), pypdfium2 (Apache-2.0/BSD-3).
- Trocar o extrator muda a transcrição do RREO e exige uma nova versão do extrator, com nova normalização, novo hash e homologação própria.
- O caminho mais simples é decidir a licença do projeto: uma licença compatível com a AGPL resolve o conflito sem mexer em código.

**Pendências:**
- escolher a licença do repositório (hoje ausente: todos os direitos reservados);
- fixar as transitivas com hash, num arquivo de trava gerado da instalação limpa.

## 12. Testes multiambiente

| Ambiente | Situação |
|---|---|
| Windows 11, Python 3.14.3, cópia no OneDrive (banco fora) | **testado** (todas as subetapas e esta auditoria) |
| Instalação completamente limpa (venv novo, cópia fora do OneDrive, caminho curto) | **testado** na 04.6 e na 05.7 (mesmos hashes, 348 + 26) |
| Instalação limpa em caminho profundo | **testado:** falha de caminho longo do `charset_normalizer` (aviso), documentada |
| Outra versão do Python (3.11–3.13) | **não testado** |
| Outro Windows ou outro computador | **não testado** |
| Linux ou macOS | **não testado** |
| Fora do OneDrive (projeto inteiro) | **testado** só na instalação limpa (pasta temporária); o uso diário roda no OneDrive |

A CI da seção 9 resolveria as três primeiras linhas "não testado" para Windows e Linux. Outra máquina física continua a cargo do responsável.

## 13. Validação final desta operação

| Verificação | Resultado |
|---|---|
| Testes de produção | 353/353 (348 + 5 novos) |
| Investigação | 26/26 |
| `verificar` / `portoes` | sem problemas / apto |
| Estado × auditoria e × homologação 04.6 | idênticos: 0 diferenças nos 5.575 valores de tela e na camada painel; bruto, armazém e derivações iguais |
| Telas da Etapa 05 × camada painel (`05_7_telas_novas.py`) | 100.201 valores, 0 páginas com problema, 0 status diferente de 200 |
| Acessibilidade (`05_7_acessibilidade.py`) | 38 páginas, 0 problemas |
| Celular (375 px), corte não processado | sem estouro de largura; aviso logo abaixo do título; nenhum valor exibido |

Evidências: `resultados/pos05_*`.

## 14. Próxima etapa recomendada (não iniciada)

1. **Decisões do responsável:**
   - aprovar os relatórios;
   - mesclar #1 → #11 e o PR desta consolidação;
   - visibilidade do repositório e licença (seções 10 e 11);
   - opção (a) ou (b) da D1.
2. **D1** como subetapa própria, pelo procedimento da seção 8.
3. **Engenharia:** CI (seção 9) e trava das dependências; depois, refatoração de `consulta.py` e `paginas.py` sob o critério de aceite das seções 5 e 6.
4. **Interface:** hierarquia do retrato e menu no celular (seção 7), com medição antes × depois.
5. **Só então** uma nova etapa funcional (Etapa 06), planejada como a 05: plano, contrato, subetapas.
