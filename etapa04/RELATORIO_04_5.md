# Relatório da Subetapa 04.5 — primeira interface pública, baseada na fonte Elotech

Data: 30/09/2026. Ramo `subetapa-04.5`, a partir do ponto de restauração `b4c7f8a` (revisão corretiva aprovada, no `main`).

**Resumo:**
- Interface pública **somente leitura** em `app/rp/interface`, sobre a camada `app/rp/painel`: `python -m rp interface` → `http://127.0.0.1:8050/`.
- Fluxo mantido: Elotech → coletor → snapshot imutável → normalização → derivação → painel → interface. O RREO segue o fluxo paralelo e aparece só como conferência e reconciliação.
- **Nenhuma dependência nova:** biblioteca padrão do Python (WSGI com `wsgiref`) e HTML gerado no servidor, sem JavaScript.
- A interface nunca chama a API da Elotech: testado com toda conexão externa bloqueada, em teste automatizado e com o servidor real.
- Testes: **207/207** de produção (174 anteriores + 33 novos) e **26/26** da investigação. Banco, armazém e hashes idênticos aos da linha de base.

---

## 0. Linha de base e ponto de restauração

Antes de qualquer alteração:
- repositório no `main`, HEAD `adc7510`; pendentes só os arquivos da revisão corretiva aprovada e o backup grande;
- suítes: 174/174 de produção e 26/26 de investigação; `python -m rp verificar`: sem problemas;
- camada bruta: `hash_camada0` = `733670693c01d015…`; tabelas `coleta` `d1f4f6ea…`, `resposta_bruta` `10261e4d…`, `objeto_bruto` `b7daff63…`, `coletor_versao` `16cdb0d6…`;
- derivações válidas: 23 (atual) = `2f6b4e29…` e 24 (29/09) = `b8a0b2ed…` (iguais às 21 e 22, que continuam no banco);
- armazém: 466 manifestos e 375 objetos idênticos, arquivo a arquivo, ao fim da revisão corretiva.

**Ponto de restauração:** commit `b4c7f8a` no `main`, com a revisão corretiva. O backup `backups/20260930-145737_antes-migracao-v3-v4.sqlite` (120,5 MB) ficou **fora do Git** por uma linha no `.gitignore`: sem Git LFS, e o arquivo continua no disco. O `app/README.md` passou a explicar que o banco é reconstruível a partir de `snapshots/`.

## 1. Tecnologia escolhida

**Aplicação WSGI da biblioteca padrão do Python** (`wsgiref`), com páginas HTML geradas no servidor, sem JavaScript.

Motivos:
- **Nenhuma dependência nova:** `requirements.txt` continua só com `requests` e `pymupdf`. O FastAPI instalado no computador não é dependência do projeto e não foi usado: exigiria servidor ASGI e bibliotecas extras sem ganho para uma interface só de leitura.
- **Reaproveitamento:** a interface chama `rp.painel.Painel` diretamente, no mesmo processo Python. Não há API intermediária, serialização ou segundo servidor.
- **Publicação futura:** WSGI é o padrão do Python (PEP 3333). A mesma `Aplicacao` roda com qualquer servidor WSGI de produção sem mudar o código.
- **Sem internet:** sem CDN, fonte externa, imagem ou script. O CSS é servido pela própria aplicação.
- **Segurança:** sem JavaScript, a política de conteúdo (CSP) pode ser `default-src 'none'`.

## 2. Arquitetura da interface

```
navegador ──GET──> rp.interface.aplicacao.Aplicacao (WSGI)
                     ├─ valida os parâmetros (inteiros, datas AAAA-MM-DD, listas fechadas, uid de 32 hex)
                     ├─ abre rp.painel.Painel SÓ LEITURA (URI mode=ro + PRAGMA query_only), uma conexão por requisição
                     ├─ rp.interface.paginas: escolhe o que mostrar; não calcula regra
                     └─ rp.interface.formato: escape de HTML, moeda em centavos (aritmética inteira), selos
                   <── HTML + cabeçalhos de segurança
```

- Só **GET e HEAD**; outros métodos recebem 405.
- Consulta maior que 2 KB ou com mais de 40 campos recebe 400. Rota desconhecida recebe 404. Erro interno recebe 500 sem pilha (o detalhe vai para o log).
- **Cabeçalhos:**
  - `Content-Security-Policy: default-src 'none'; style-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'`;
  - `X-Content-Type-Options: nosniff`;
  - `Referrer-Policy: no-referrer`;
  - `X-Frame-Options: DENY`;
  - `Cache-Control: no-store`.
- **Servidor local:**
  - escuta em `127.0.0.1` por padrão; com `--host` diferente, avisa que fica acessível pela rede sem autenticação;
  - não faz resolução de nome ao iniciar: o `server_bind` não chama `getfqdn`;
  - os acessos vão para o log do programa.
- **Linha de comando:** `python -m rp interface` abre o banco só para leitura, antes de qualquer caminho que migre ou escreva. É a mesma regra do comando `painel`.

## 3. Páginas criadas

| Rota | Conteúdo |
|---|---|
| `/` **Resumo** | filtros (exercício, corte, entidade ou Município, "como estava em"); bloco do retrato (exercício, corte, coleta); 13 indicadores em 4 grupos; entidades abrangidas; aviso de mais de um retrato; **Conferência com o RREO** |
| `/entidades` | por entidade: situação no catálogo do exercício, processado, não processado, total inscrito, saldo S1, empenhos, retratos e origem. Entidade fora do catálogo aparece como "não existia no exercício — sem valor", nunca R$ 0,00 |
| `/empenhos` | lista paginada (50 por página) com filtros: categoria, fonte de recurso, programação (começa com), tipo de credor, CNPJ de pessoa jurídica e ordem; totais do conjunto filtrado; origem dos snapshots |
| `/empenho` | detalhe de um empenho: identificação; valores da API (nome amigável ↔ nome técnico, significado, status); classificação e saldos com regra e situação; classificação orçamentária; par espelhado; movimentações; **Origem do dado** (fonte, endpoint, parâmetros, coleta, snapshot, manifesto, resposta HTTP, página, posição, SHA-256 do objeto bruto) |
| `/retratos` | índice dos cortes com mais de um retrato; por corte, cada retrato com coleta, status, registros, total inscrito, saldo, diferença para o anterior e se os bytes são idênticos |
| `/comparar` | dois retratos do mesmo corte: novos, removidos e alterados; impacto por grupo; saldo. Campos do credor aparecem como [restrito] |
| `/reconciliacao` | índice dos RREOs conciliados; por documento, coluna a coluna: API Elotech × RREO × diferença, com regra, PDF, extração e explicação; PDFs sem transcrição; **coerência entre publicações** |
| `/metodologia` | fontes e hierarquia, metodologia, exercício × corte × coleta, naturezas, regras e situação, dados pessoais, dicionário de campos |
| `/pares` | área técnica: identificação de pares (PAR-24 v1), com resumo, lista e origem. Não é consolidação |

## 4. Consultas

As telas usam só a camada `rp.painel`. Na camada de consulta, esta subetapa:
- **acrescentou:**
  - `entidades_do_corte`;
  - `retratos_multiplos`;
  - `documentos_rreo`;
  - `conferencia_rreo` dentro de `indicadores` (saldo S1 × coluna L);
  - filtros e totais em `empenhos` (categoria, fonte de recurso, prefixo da programação, tipo de credor, CNPJ);
  - valores e diferenças por retrato em `retratos`;
  - contagem de retratos por entidade no corte;
  - proveniência em `empenhos`, `pares` e `entidades_do_corte`;
- **mudou:**
  - a natureza "dado da fonte" passou a se chamar `da_fonte`, como pede a especificação;
  - a reconciliação sai na ordem das colunas do Anexo VII (a…k, L);
  - o rótulo da fonte Elotech passou a ser "Portal da Transparência de Ponta Grossa — API do sistema Elotech/Oxy Transparência";
- **filtros:**
  - todo filtro vira SQL parametrizado; nenhum texto do usuário entra na consulta;
  - o tipo de credor é calculado no SQL pela mesma função da camada pública (função registrada na conexão, sem escrita);
  - filtro só escolhe linhas: a soma dos totais por categoria reproduz o total (teste 10).

## 5. Origem dos dados

**Vêm da API Elotech:**
- **Os 13 indicadores do Resumo:**
  - RP inscritos (total, processados, não processados);
  - saldo S1, a liquidar S2, liquidado a pagar S3;
  - pagamentos (total, processado, não processado);
  - liquidações, cancelamentos, retenções;
  - registros.
  
  Todos são natureza `derivado`: somas de campos da API ou fórmulas S1–S3, com regra operacional.
- Os valores por entidade, os totais filtrados, a lista de empenhos, o detalhe (campos `da_fonte`, derivados `derivado`), as movimentações, os retratos e os pares.
- Todo valor mostra "Fonte · Natureza · Regra" (ou "Cálculo", quando é soma sem regra). A origem fica num bloco recolhível:
  - snapshots, derivação com hash e normalização, nos indicadores e nas entidades;
  - endpoint, parâmetros, resposta HTTP e SHA-256, no detalhe.

**Vêm do RREO (`publicado`):**
- a coluna L na Conferência do Resumo;
- as 12 colunas de cada documento na Reconciliação;
- L de A e (a)+(f) de A+1 na Coerência entre publicações.

## 6. Tratamento do RREO

- O RREO aparece em seções próprias, sempre com "Fonte primária: API Elotech · Fonte de reconciliação: RREO Anexo VII".
- **Conferência no Resumo:** saldo S1 da API × coluna L do PDF do mesmo corte. Não usa RREO-COL. A diferença vem com a situação e a explicação documentada. O saldo mostrado é sempre o da API.
- **Reconciliação:**
  - o lado API é a projeção dos registros nas colunas do RREO por RREO-COL v1 (não recomendada) ou v2 (experimental), e por isso sai rotulado **valor analítico (não oficial)**;
  - o RREO sai como **valor publicado**;
  - a diferença sai como **diferença**;
  - nenhuma divergência é escondida (filtro "só diferenças" opcional).
- Mostra também: PDF (rótulo, `idArquivo`, data, emissão), snapshot, SHA-256, extrator e versão do PyMuPDF/MuPDF, e os PDFs que o extrator não lê (2016 entidade, 2018, 2019).
- O mesmo PDF coletado duas vezes aparece uma vez, com os dois snapshots.

## 7. Tratamento dos snapshots

- Toda tela de valores diz exercício, corte e data da coleta. Não aparece só "Restos a Pagar de 2024".
- "Como estava em" usa o retrato vigente na data, com o rótulo "Como a base estava em DD/MM/AAAA: …".
- **Retratos:**
  - cada coleta do mesmo corte é listada com registros, valores e diferença para a anterior;
  - nenhuma é apagada;
  - dá para comparar duas.
- Snapshot ainda não processado vira aviso, nunca corte com valor zero.
- Corte posterior à data da coleta recebe uma nota.

## 8. Minimização de dados

- Só existe o nível público: não há parâmetro que ative o nível interno (`nivel=interno` é ignorado).
- Listas e totais trazem só o tipo de credor, sem nome, código ou documento.
- No detalhe, o nome de pessoa jurídica aparece sem documento (CPF/CNPJ mascarados, inclusive o CPF no fim da razão social de MEI). O nome de pessoa física não é exibido.
- O filtro de credor aceita só CNPJ completo de pessoa jurídica; CPF recebe 400.
- Não há tela de "todos os fornecedores". Não há dado bancário nos dados coletados.

## 9. Testes

Produção: **207/207** (174 anteriores + 22 em `tests/test_interface.py` + 11 em `tests/test_interface_casos_reais.py`). Investigação: **26/26**. Saídas em `etapa04/resultados/04_5_testes_producao.txt` e `04_5_testes_investigacao.txt`.

| Exigência (seção 20) | Teste |
|---|---|
| 1. interface não chama a API | `test_01` (todas as rotas com a rede bloqueada; nenhum import de cliente HTTP, `socket`, coletor ou armazém) e `test_guarda_de_rede_do_teste_bloqueia_de_verdade` |
| 2. painel com banco somente leitura | `test_02` (arquivo do banco com atributo de só leitura no sistema) |
| 3. valor principal vem da Elotech | `test_03` (cartões = somas SQL dos registros da API) |
| 4. RREO não substitui a Elotech | `test_04` |
| 5. fora do catálogo não vira zero | `test_05` |
| 6. snapshot anterior acessível | `test_06` |
| 7. proveniência de todo valor | `test_07`, `test_07b` |
| 8. regra experimental fora dos indicadores | `test_08`, `test_08b` (regra rebaixada bloqueia a tela) |
| 9. dado sensível fora do padrão | `test_09` |
| 10. filtros não alteram dados | `test_10` |
| 11. ausência ≠ zero | `test_11` |
| 12. centavos | `test_12` |
| 13. retratos independentes | `test_13` |
| seção 21: escrita recusada | `test_interface_recusa_qualquer_escrita` (UPDATE, DELETE, INSERT, regra nova, decisão de governança, derivação nova, hash) |
| seções 23/24: sem internet | `test_interface_funciona_sem_internet` (servidor HTTP real em 127.0.0.1, rede bloqueada) |
| segurança | `test_cabecalhos_de_seguranca_e_nenhum_recurso_externo`, `test_SINTETICO_texto_do_banco_e_escapado`, `test_parametros_invalidos_e_rotas` |
| seção 19: regressão | `test_5659_2025_detalhe`, `test_11963_2016_detalhe`, `test_2401751_2023_e_seu_par`, `test_entidade_5_empenho_1485_2025`, `test_pares_1_15_em_2025`, `test_pares_de_2026`, `test_divergencias_h_i_de_2026`, `test_674_426_01`, e mais três testes de coerência com a camada painel e desempenho |

**Execução sem internet com o servidor real:**
- `python -m rp interface` rodou num processo em que toda conexão e toda resolução de nome para fora da máquina eram recusadas e anotadas (`etapa04/resultados/04_5_servidor_sem_rede.py`);
- as telas foram percorridas por HTTP a partir de outro processo (`04_5_percorrer_telas.py`): inicialização, resumos, filtros, detalhes, retratos, comparação, reconciliação, pares, metodologia e proveniência;
- as 17 visitas responderam 200;
- nenhuma tentativa de rede foi registrada (`04_5_percurso_sem_rede.json`).

A máquina não foi desconectada: o bloqueio é no processo.

## 10. Desempenho

Banco completo (228.873 registros por normalização), pelo HTTP local:

| Tela | Tempo |
|---|--:|
| Resumo padrão (primeira requisição) | 0,21 s |
| Resumo do Município, 2025 | 0,09 s |
| Resumo "como estava em" 29/09 | 0,07 s |
| Entidades 2016 | 0,09 s |
| Empenhos do Município, 2025 (página 1 e página 20) | 0,07 s / 0,06 s |
| Empenhos com 4 filtros | 0,04 s |
| Detalhe de empenho | 0,02–0,03 s |
| Retratos / comparação | 0,04 s / 0,15 s |
| Reconciliação: índice + coerência | **0,43 s** (a mais lenta: monta as ~1.500 linhas e a coerência) |
| Reconciliação de um documento | 0,02 s |
| Pares 2026 (731) | 0,03 s |

- Nenhuma tela carrega o banco inteiro:
  - somas e agrupamentos são feitos no SQL, restritos às respostas do corte pela chave primária;
  - a lista usa `LIMIT/OFFSET` de 50 linhas (teste `test_listagem_paginada_nao_carrega_o_corte_inteiro`).
- **Nenhum índice foi criado**, porque nenhuma medida pediu. Não há cache.

## 11. Limitações

- O servidor `wsgiref` atende um pedido por vez e não tem autenticação, HTTPS nem limite de acesso. Serve para uso local; publicar na internet exige servidor WSGI de produção e proxy com HTTPS (fora do escopo).
- "Como estava em" mostra valores de qualquer data, mas a reconciliação da data exige derivação com essa vigência; hoje só existe a de 29/09/2026.
- O total do Município não existe nos cortes em que só a entidade 1 foi coletada (31/01/2026, 31/03/2026 e 31/12/2026). A tela diz "Município incompleto" e não mostra zero.
- Sem JavaScript, trocar o exercício exige uma consulta para atualizar a lista de cortes.
- A reconciliação e a coerência cobrem só os PDFs que o extrator de produção lê: nada de 2016 (entidade), 2018 e 2019; a coerência vai de 2020 em diante.
- O filtro de programação é por prefixo, sem navegação pela hierarquia. A lista de fontes de recurso mostra as do corte.
- A tela inicial não mostra "estornos de pagamento", que é informativo (continua na camada painel e no comando `painel`). Não há gráficos.
- O layout foi conferido num navegador de desktop. Em celular, o CSS é responsivo, mas não foi verificado.
- O teste sem internet bloqueia a rede no processo; a máquina não foi desconectada.
- Continuam as limitações das etapas anteriores:
  - catálogo de entidades atual;
  - natureza das cópias 24xxxxx não determinada;
  - diferenças não determinadas;
  - teste temporal curto.

## 12. Problemas encontrados

1. A natureza "dado da fonte" se chamava `fonte` na camada painel, o que se confundia com a chave `fonte` (o rótulo da origem). Passou a `da_fonte`, como pede a especificação.
2. O Resumo mostrava "0" registros para entidade fora do catálogo. Passou a "—".
3. Coleta no mesmo minuto aparecia como "01:14 a 01:14". Corrigido.
4. A reconciliação ordenava a coluna L antes de a (ordem alfabética). Agora segue a ordem do Anexo VII.
5. A medição sem internet mostrou telas com valores sem origem acessível (entidades, lista de empenhos, pares, coerência). A origem foi acrescentada e é testada (`test_07b` e casos reais).
6. O teste de igualdade interface × painel falhou porque a tela não mostra "estornos de pagamento". O teste passou a comparar exatamente os indicadores exibidos.
7. O visualizador do aplicativo exige um arquivo de configuração fora da pasta do projeto. Ele não foi criado: o servidor foi aberto pelo endereço.

## 13. Decisões técnicas

- Trabalho no ramo `subetapa-04.5`; o `main` fica no ponto de restauração `b4c7f8a`. Não foi aberto PR.
- A interface nunca recebe conexão de escrita: uma conexão somente leitura por requisição, sem estado compartilhado entre pedidos.
- Nível público fixo. O filtro de credor só por CNPJ de pessoa jurídica é a leitura de "fornecedor, quando a exposição for adequada".
- As visões analíticas CONS-PAR não aparecem. Os pares ficam numa área técnica rotulada, sem valor consolidado.
- A conferência do Resumo usa S1 × L, e não a RREO-COL, para que nenhuma regra experimental participe da comparação principal.
- Todo valor monetário vai também em `<data value="centavos">`, legível por máquina e sem arredondamento.
- Os auxiliares de teste (mundo sintético, banco do armazém real, chamada WSGI) foram para o `conftest.py`, compartilhados pelos testes.

## 14. Portões finais

| Portão | Resultado |
|---|---|
| Testes | 207/207 de produção; 26/26 de investigação |
| `python -m rp verificar` | sem problemas |
| Camada bruta | `hash_camada0` `733670693c01d015…`, igual à linha de base; tabelas do bruto idênticas |
| Snapshots | 466 manifestos e 375 objetos idênticos à linha de base |
| Hashes de resultado | derivações 23 = `2f6b4e29…` e 24 = `b8a0b2ed…`; 21 e 22 intactas; nenhuma execução nova no banco ativo |
| Banco ativo | não foi escrito pela interface (aberto sempre só para leitura) |
