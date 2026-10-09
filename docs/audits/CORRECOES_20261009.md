# Correção integral e auditoria do banco (pedido de 09/10/2026)

Registro do que foi feito, por fase, com os comandos executados e os resultados reais. Nada aqui é declaração de
apuração 100% correta: o que continua pendente está dito em cada fase.

Ordem aprovada pelo responsável pelo projeto em 09/10/2026:

| Fase | Itens do pedido | Situação |
|---|---|---|
| A | 3 (contrato da API), 2 (campo monetário ausente) | feita |
| B | 4 (precisão temporal dos retratos) | feita (suíte: 604 passed) |
| C | 1 (integridade relacional), 7 (proveniência e hashes) | feita (suíte: 616 passed) |
| D | 9 (homologação única), 10 (desempenho) | feita (suíte: 627 passed) |
| E | 5 (pares 1 ↔ 15), 6 (RREO) | feita (suíte: 638 passed + 1 teste ajustado, passa) |
| F | 8 (privacidade do repositório) | inventário, plano e prova feitos; remoção do histórico **não executada** (aguarda autorização) |

## Fase A: contrato da API e campo monetário ausente

### O que mudou

**Item 3, contrato estrito da API (`rp-api-contrato/2`).**
- Arquivos: `app/rp/contrato.py`, `app/rp/coletor.py` e `app/rp/diagnostico.py`.
- O que é exigido de cada página: todos os metadados de paginação, com tipo e domínio.
- O que é exigido de cada registro da listagem de RP e de cada lançamento da movimentação: exatamente as chaves
  conhecidas, com tipo. Os campos monetários são números, nunca nulo, texto ou booleano. As 7 chaves de
  classificação vêm todas juntas ou nenhuma.
- O que acontece com uma violação:
  - a coleta fica `incompleta`, com o motivo (página, registro, chave e tipo);
  - as respostas continuam gravadas;
  - o `diagnosticar-api` aplica o mesmo contrato.
- O que foi mantido:
  - a detecção de duplicidade;
  - a segunda leitura das páginas;
  - as travas de paginação;
  - a conferência do eco da ordem.
- Documentação: `docs/audits/ELOTECH_API_CONTRACT.md` §4.1.

**Item 2, campo monetário ausente nunca vira zero.**
- Arquivos: `app/rp/normalizar.py` (v2), `app/rp/banco.py` (esquema v6), `app/rp/derivar.py`, `app/rp/vigencia.py`,
  `app/rp/portoes.py`, `app/rp/regras.py` e `app/rp/painel/consulta/`.
- **Antes:** `centavos(r.get(campo, 0))` gravava 0 para um campo ausente, e o registro entrava em todos os
  indicadores como se o valor fosse conhecido. Um valor inválido, com mais de 2 casas ou em texto, parava a
  normalização inteira.
- **Agora, na normalização:**
  - o registro com campo monetário ausente, nulo ou inválido não vira linha de `rp_registro`;
  - cada campo recusado vira uma linha da nova tabela `valor_recusado`, com o campo, a natureza (`ausente`, `nulo`,
    `invalido`) e o valor bruto, quando inválido;
  - o zero real continua sendo zero.
- **Agora, na derivação:**
  - o retrato com recusa nunca é o vigente: anomalia `VALOR-RECUSADO`, da nova regra `VALOR-OBRIG v1`;
  - vale o retrato válido anterior do corte, com aviso no painel;
  - sem retrato anterior, o dado fica indisponível, na situação `valor_recusado`, e nunca aparece como R$ 0,00.
- **Agora, nos portões:** o portão `campos_monetarios_ausentes` reprova a carga e nomeia os campos recusados.
- **Esquema v6:**
  - só acréscimos: a tabela `valor_recusado` e gatilhos que impedem uma recusa de outra coleta, um registro com
    valor numa posição recusada e a edição ou exclusão de recusa com derivação existente;
  - nenhuma tabela recriada, nenhuma linha histórica alterada;
  - migração transacional, com backup automático antes;
  - impressão estrutural da v6 registrada; a da v5 continua a mesma.
- Os registros históricos não foram transformados.

### Testes novos e testes ajustados

- `app/tests/test_contrato_estrito.py` (41 testes): cada metadado ausente, com tipo errado ou fora do domínio; cada
  campo monetário ausente, nulo, em texto ou booleano; zero válido aceito; chave nova; grupo de classificação
  parcial; problema na segunda página com as respostas preservadas; movimentação fora do contrato.
- `app/tests/test_valor_ausente.py` (23 testes): ausência em cada um dos 10 campos monetários; nulo e inválido com o
  valor bruto; zero válido; vários campos no mesmo registro; gatilhos da v6; retrato recusado fora da vigência;
  dado indisponível sem retrato anterior, inclusive na tela; portão; nada novo gravado quando não há recusa;
  migração da v5 para a v6 com backup e restauração.
- Os dados sintéticos dos testes agora têm o formato real da API (`conftest.pagina`, `completar_registro`). Testes
  que descreviam o comportamento antigo e tolerante passaram a nomear o motivo novo:
  `test_auditoria_api::test_API08`, `test_seguranca::test_servidor_que_ignora_page_nao_prende_o_coletor`,
  `test_revisao_diagnostico` e `test_auditoria_integridade::test_NORM01`. Este último registrava que o campo
  ausente virava 0; agora registra a recusa. Os testes da migração v5 (`test_decisoes_revisao`) continuam provando
  a v4 → v5 e passaram a aceitar a v6 como versão do código. Nenhum teste foi apagado.

### Verificação com os dados reais

Tudo numa cópia do banco ativo, fora do OneDrive. O banco ativo só foi lido, pela API de backup do SQLite.

| Verificação | Comando | Resultado |
|---|---|---|
| Contrato estrito contra todo o armazém | leitura de todas as respostas gravadas | 383 páginas de listagem (266.787 registros) e 148 de movimentação (2.352 lançamentos) cumprem o contrato v2; nenhum campo monetário ausente ou nulo |
| Migração v5 → v6 da cópia | `scratchpad/verificar_fase_a.py` | esquema 6, impressão confere, backup `antes-migracao-v5-v6` gravado |
| Normalização v2 contra a homologada (14) | idem | 266.787 linhas; 0 diferenças linha a linha nas 36 colunas; 0 recusas |
| Derivação sobre a normalização v2 | idem | `hash_resultado` = `b6f80d879ee89d5f17c42de25c6ff3c030b5c7d238a1235035b6b18f23e1802f`, igual ao homologado; `hash_semantico` igual |
| Portões na cópia migrada e reprocessada | idem | apto; 12 de 14 aprovados; `camada_bruta_preservada` e `testes` não verificados por este comando (fase D) |
| Restauração do backup da migração | cópia do backup + `PRAGMA integrity_check` + nova abertura | integridade ok, versão 5, derivação 25 com o hash homologado, 266.787 registros; volta a migrar para a v6 |
| Banco novo só a partir do armazém | `scratchpad/reconstruir_fase_a.py` (`banco.reconstruir` + normalizar + derivar) | 529 coletas, v6, 266.787 registros, 0 recusas, hash igual ao homologado |
| Suíte de testes | `python -m pytest -q -p no:cacheprovider` (em `app/`, inclui os testes com dados reais) | 590 passed em 326 s |

Os três RREO de layout desconhecido (coletas 403, 426 e 431) continuam sem transcrição, como já estavam: é a fase E.

### Revisão da fase A

Pontos achados na releitura do diff, que os testes não pegavam, e corrigidos:
- `comparar-bancos` (`rp/equivalencia.py`) ignorava `valor_recusado`. Dois bancos com recusas diferentes podiam sair
  como equivalentes. Agora a tabela entra na impressão da normalização; um banco v5, sem a tabela, conta como vazio.
- `comparar-snapshots` (`rp/comparador.py`) trataria um registro recusado como removido ou novo, e o impacto
  financeiro sairia errado sem aviso. Agora ele vai para `recusados`, com os campos, e `impacto_completo` vira
  falso.
- Comparação do banco ativo (v5, só leitura) com o reconstruído do armazém (v6), com as duas vigências derivadas:
  camada bruta igual; as 7 tabelas da normalização iguais (só o rótulo `rp-normalizador/1` × `/2` difere, e o
  comparador acusa isso de propósito); derivação atual `b6f80d87…` e "como estava em 29/09/2026" `b8a0b2ed…`
  iguais; hash gravado = recalculado nos dois.

### Mudanças de indicador

Nenhuma. O hash da derivação sobre os dados reais é o homologado, tanto no banco migrado quanto no reconstruído do
armazém.

### Pendências desta fase

- **Governança da regra `VALOR-OBRIG v1`:** está no catálogo e é usada pela derivação para recusar o retrato. Isso
  falha fechado: nunca produz valor. Ainda não tem decisão registrada em `regra_situacao`. A promoção é do
  responsável pelo projeto, com
  `python -m rp decidir-regra --codigo VALOR-OBRIG --versao 1 --situacao operacional --status CONFIRMADO --motivo ... --fonte docs/audits/CORRECOES_20261009.md --teste tests/test_valor_ausente.py::test_SINTETICO_retrato_com_valor_recusado_nunca_e_o_vigente`.
- **Banco ativo:** continua na v5 até ser aberto pelo código novo. A migração faz backup antes. Recomenda-se
  rodar `python -m rp processar` depois disso, para registrar a normalização v2. O hash esperado é o mesmo.
- **`valorALiquidar` e `valorAPagar` da movimentação:** a normalização ainda aceita esses campos nulos. O contrato v2
  já recusa uma coleta nova com eles nulos. Os 2.352 lançamentos gravados não têm nenhum nulo.

## Fase B: precisão temporal dos retratos

### O que mudou

- **Antes:** "como estava em" comparava o INÍCIO da coleta (`coletada_em`) com o instante pedido. Uma coleta que
  começou antes e terminou depois contava como disponível, embora parte das páginas ainda não tivesse chegado.
- **Esquema v7 (`app/rp/banco.py`):** a tabela `coleta_tempo` guarda, para cada coleta:
  - `inicio_em` e `concluida_em`, em forma canônica (fuso de Brasília, segundos);
  - `fonte_conclusao`: de onde veio a conclusão;
  - `precisao`: quanto ela é confiável.
- **Proteções:** a camada bruta (`coleta`) continua imutável. Gatilhos recusam:
  - instante fora da forma canônica;
  - conclusão antes do início;
  - início diferente do da coleta;
  - edição e exclusão.
- **De onde vem a conclusão, sempre do manifesto e nunca inventada:**
  - `manifesto`: a conclusão gravada pelo coletor desde 05/10/2026 (`coleta_finalizada_em`), precisão `exata`;
  - `ultima_resposta`: o maior `recebida_em` das respostas e da segunda leitura. A precisão segue a origem do
    carimbo: relógio do coletor, manifesto da Etapa 02 ou cabeçalho HTTP dão `ultima_resposta`; a data do arquivo
    (Etapas 01/02) dá `aproximada`;
  - `sem_evidencia`: conclusão nula, precisão `desconhecida`. O retrato vale para o estado atual, mas nunca numa
    consulta com data.
- **Bancos anteriores à v7:** as linhas são preenchidas pelos manifestos na primeira abertura
  (`banco.completar_tempos`), depois da migração com backup. Um manifesto ilegível deixa a coleta sem linha, e o
  portão acusa.
- **Regra de vigência v2 (`app/rp/vigencia.py`, `rp-vigencia/2`; derivador `rp-derivador/2`):**
  - um retrato só vale "como estava em" a partir da conclusão;
  - "mais recente" ordena por início canônico, depois conclusão, depois `snapshot_uid`. Fusos equivalentes comparam
    igual, e duas coletas com o mesmo início ficam em ordem pela que terminou por último;
  - derivação, painel (núcleo, série, empenhos, retratos) e consultas usam o mesmo SQL (`filtro_disponivel`, `ordem`).
- **Painel:** exige esquema v7 e avisa quando o retrato usado numa consulta com data tem conclusão aproximada.
- **`verificar`:** recalcula início e conclusão a partir do manifesto e acusa divergência (`tempo_da_coleta`).
- **Portão novo `tempos_das_coletas`:**
  - reprova se alguma coleta não tem tempo;
  - mostra a contagem por precisão;
  - descreve a limitação das conclusões aproximadas e desconhecidas.

### Testes

- **`app/tests/test_tempo_retratos.py` (12 testes):**
  - coleta iniciada antes e concluída depois do instante, no painel e na derivação "como estava em";
  - fusos equivalentes (UTC, -03:00, -05:00);
  - mesmo início, gravado nas duas ordens;
  - três retratos sucessivos do mesmo corte, com instantes na fronteira;
  - conclusão pela última resposta, incluindo a segunda leitura;
  - data do arquivo aproximada, com aviso no painel;
  - sem evidência de conclusão: nunca vale com data, e a tela não mostra R$ 0,00;
  - gatilhos da v7;
  - migração v6 → v7 preenchida pelos manifestos, com backup e `verificar` limpo;
  - `verificar` acusando tempo diferente do manifesto;
  - portão.
- **Ajustados para a regra nova:**
  - `test_etapa03_em_producao::test_mesmo_corte_em_datas_diferentes`, que agora prova que, no instante do início, o
    retrato ainda não vale e, na conclusão, vale;
  - dois testes sintéticos que gravavam retrato sem conclusão (`test_etapa03_em_producao::test_SINTETICO_alteracao_retroativa_preserva_os_dois_retratos`
    e `test_etapa04_3::test_snapshot_antigo_e_coleta_nova_do_mesmo_corte_sao_independentes`). Eles passam a gravar
    a conclusão no próprio instante, como o `conftest` do mundo sintético.
  - Nenhum teste foi apagado.

### Verificação com os dados reais

Cópia do banco ativo, fora do OneDrive, com o script `scratchpad/verificar_fase.py`:

| Verificação | Resultado |
|---|---|
| Situação no banco real antes da mudança | todos os 529 horários no fuso -03:00; nenhuma conclusão antes do início; nenhuma coleta que comece antes e termine depois de 29/09/2026 23:59:59; nenhuma coleta simultânea ou sobreposta do mesmo corte (maior duração: 94 s) |
| Migração v5 → v7 | um backup (`antes-migracao-v5-v7`); impressão da v7 confere |
| `coleta_tempo` | 529 de 529 coletas: 63 `manifesto`/`exata`, 321 `ultima_resposta`/`ultima_resposta`, 145 `ultima_resposta`/`aproximada` (data do arquivo, Etapas 01/02); nenhuma `desconhecida` |
| Normalização sobre a cópia | 266.787 registros idênticos aos da normalização 14 |
| Derivação atual | `b6f80d879ee89d5f…` = homologada (25) |
| Derivação "como estava em 29/09/2026 23:59:59" | `b8a0b2ed2328bf09…` = homologada (24) |
| `verificar` | 0 problemas (agora inclui o tempo de cada coleta) |
| Portões | apto; 13 de 15 aprovados (`camada_bruta_preservada` e `testes` não verificados por este comando) |

### Mudanças de indicador

Nenhuma nos dados reais: os dois hashes homologados se mantêm. A regra nova só muda o resultado de uma consulta
"como estava em" num instante entre o início e a conclusão de uma coleta. Nos dados atuais isso cobre janelas de no
máximo 94 segundos, e nenhuma delas contém um instante já usado por derivação homologada.

### Revisão da fase B

- `consultas.snapshot_em` e `vigencia.coletas_vigentes` aceitavam um `em` fora da forma canônica. Uma data sem
  hora, outro fuso ou um horário sem fuso seria comparado como texto, e o resultado sairia errado. O filtro de
  disponibilidade agora passa sempre o instante por `rp.instante`, o que vale para todo uso. Teste:
  `test_tempo_retratos::test_SINTETICO_instante_nao_canonico_e_normalizado_no_filtro`.

### Limitações registradas

- 145 retratos importados das Etapas 01/02 têm conclusão pela data do arquivo (`aproximada`). Uma consulta "como
  estava em" perto dessas datas mostra aviso no painel.
- 321 retratos anteriores a 05/10/2026 têm conclusão pela última resposta recebida, não pelo fim da gravação. A
  diferença é a escrita do manifesto, que leva menos de um segundo.
- O banco ativo continua na v5 até o código novo abri-lo. A migração faz backup e preenche os tempos pelos manifestos.

## Fase C: integridade relacional, proveniência e hashes

### O que mudou

**Item 1: relações protegidas na gravação (esquema v8, `app/rp/banco.py`).** A v8 só acrescenta: nenhuma tabela
recriada, nenhuma linha existente alterada.
- **Camada 1:** `rp_registro`, `movimentacao_lancamento`, `rreo_extracao`, `valor_recusado`, `rreo_valor`,
  `entidade_ref` e `exercicio_ref` recusam, por gatilho, na inserção e na troca das colunas de ligação:
  - coleta de outro tipo (ex.: registro de RP numa coleta de catálogo);
  - coleta diferente da coleta da resposta HTTP;
  - coleta além da última lida pela normalização.

  Antes, isso só era acusado depois, por leitura (portão `integridade_relacional`, que continua como segunda
  defesa).
- **Camada derivada:** `anomalia`, `verificacao`, `espelhamento_par`, `visao_valor` e `conciliacao_rreo` só podem
  citar regra que a sua derivação declarou.
- **Relações que viviam só em JSON** viraram tabelas com FOREIGN KEY:
  - `derivacao_regra` (de `regras_json`);
  - `visao_valor_coleta` (de `coletas_json`);
  - `conciliacao_rreo_coleta` (de `coletas_api_json`, com chave única nova na conciliação).

  O JSON continua: ele faz parte do hash homologado e a interface o usa. Um gatilho recusa a ligação que o JSON não
  tem. As derivações existentes recebem as ligações na migração, a partir do próprio JSON; as novas, na derivação.
  `apagar-execucao` apaga as ligações antes.
- **JSON que continua só descritivo:** `anomalia.detalhe_json`, `verificacao.escopo_json`, e `parametros_json` e
  `cabecalhos_json` da camada bruta.

**Item 7: proveniência e hashes (`app/rp/proveniencia.py`, `app/rp/regras.py`, `app/rp/__init__.py`).**
- **Hash de cada manifesto:** SHA-256 e tamanho em `coleta_manifesto`, gravado no registro do snapshot. Nos bancos
  anteriores, é lido do armazém na primeira abertura. Os manifestos são versionados byte a byte (`-text`), então o
  hash é o mesmo em qualquer clone. O `verificar` acusa um manifesto com outros bytes.
- **Identificação de cada normalização e derivação:**
  - `sha256_codigo`: o hash de todos os módulos de `rp/` e do `esquema.sql`;
  - `ambiente_json`: Python, SQLite, PyMuPDF e MuPDF;
  - `sha256_regras`, na derivação: o hash das regras usadas, com definição, situação de evidência e parâmetros,
    mais o catálogo de anomalias. É calculado por código e versão, nunca por id interno.
  - As execuções antigas ficam com esses campos nulos. Preenchê-los com o código de hoje seria inventar.
- **`python -m rp rastrear --valor ID`:** percorre a cadeia valor → derivação (hashes) → regras declaradas →
  snapshots → registros normalizados → respostas HTTP → objeto bruto (hash recalculado) → manifesto (hash gravado ×
  arquivo), e diz o que não confere.
- **`python -m rp raiz --gravar ARQ` / `--conferir ARQ`:** manifesto-raiz com o hash de cada manifesto e de cada
  objeto, as duas raízes e o `hash_resultado` das derivações atuais. A conferência aceita bruto novo, porque a
  camada só cresce, e acusa bruto que sumiu ou mudou, além de arquivo de raiz adulterado.
- **Limite do manifesto-raiz:** guardado no mesmo disco, ele **não** prova imutabilidade contra quem administra o
  banco e o armazém. Ele só vale guardado fora deles: outro disco, e-mail, commit assinado, carimbo de tempo. Para
  os manifestos, o histórico Git de `data/snapshots` já é uma referência externa; para o banco, não.
- **Portões novos:**
  - `proveniencia_completa`: todo valor chega a snapshot, resposta, objeto e hash de manifesto, e as relações
    batem com o JSON;
  - `execucao_identificada`: código, ambiente e regras registrados, e o hash das regras igual ao recalculado.

### Testes

- **`app/tests/test_integridade_proveniencia.py` (11 testes):**
  - camada 1 recusando coleta de outro tipo, de outra resposta ou além da lida, e troca de coleta;
  - regra não declarada;
  - relações iguais ao JSON e ligação fora do JSON recusada;
  - apagar derivação com as ligações;
  - código, regras e ambiente registrados;
  - hash das regras pelo conteúdo;
  - hash do manifesto e `verificar`;
  - cadeia de um valor, com acusação de manifesto alterado;
  - manifesto-raiz: grava, aceita bruto novo, acusa arquivo e banco alterados;
  - CLI `rastrear` e `raiz`, sem sobrescrever o arquivo;
  - migração v7 → v8 preenchendo relações e hashes, sem alterar nenhuma linha e com as execuções antigas nulas.
- **Ajustados:**
  - `test_valor_ausente::test_SINTETICO_gatilhos_da_v6`: a mensagem agora pode vir do gatilho da v8, que dispara
    primeiro; a recusa continua;
  - `test_tempo_retratos::test_banco_v6_migra_para_v7_preenchendo_pelos_manifestos`: passou a fixar o código na
    v7.
  - Nenhum teste foi apagado.

### Verificação com os dados reais

Cópia do banco ativo, com o script `scratchpad/verificar_fase.py` e as conferências de proveniência:

| Verificação | Resultado |
|---|---|
| Dados existentes contra as travas novas (antes de criar) | 0 linhas de camada 1 com coleta de outro tipo, de outra resposta ou além da lida; 0 linhas citando regra fora do `regras_json`; conciliação com chave natural única (3.888 de 3.888) |
| Migração v5 → v8 | um backup (`antes-migracao-v5-v8`); impressão da v8 confere |
| Relações preenchidas do JSON | `derivacao_regra` 107, `visao_valor_coleta` 101.880, `conciliacao_rreo_coleta` 19.008; `coleta_manifesto` 529 de 529 |
| Normalização e derivações | 266.787 registros idênticos aos da normalização 14; atual `b6f80d87…` e "como estava em 29/09" `b8a0b2ed…` iguais às homologadas |
| Proveniência | derivação nova e derivação homologada 25 (migrada): 7.890 valores, nenhum elo quebrado |
| Identificação | derivação nova com o código atual; hash das regras confere; ambiente registrado |
| `rastrear` de um valor real (S1, 2026, 28/02) | cadeia completa: 10 snapshots, 12 respostas, objetos e manifestos conferidos |
| Manifesto-raiz | 529 coletas, 411 objetos; raiz dos manifestos `4065bea9…`, dos objetos `cfb99745…`; confere |
| `verificar` | 0 problemas (inclui o hash de cada manifesto) |
| Portões | apto; 15 de 17 aprovados (`camada_bruta_preservada` e `testes`: fase D) |

### Mudanças de indicador

Nenhuma: os dois hashes homologados se mantêm.

### Revisão da fase C

- O `comparar-bancos` não comparava as tabelas que vêm do armazém junto da camada bruta (`coleta_tempo`, v7, e
  `coleta_manifesto`, v8). Dois bancos com tempos ou hashes de manifesto diferentes sairiam como equivalentes. Agora
  elas entram em `complementos_camada0_iguais`. Um banco sem a tabela fica "não comparável", nunca "igual". Teste:
  `test_integridade_proveniencia::test_SINTETICO_comparar_bancos_ve_tempo_e_hash_de_manifesto`.
- Prova com os dados reais: a cópia do banco ativo migrada v5 → v8 (tempos e hashes lidos dos manifestos) contra um
  banco montado do zero pelo armazém com o código atual (`banco.reconstruir`) dá `equivalentes: true`. Batem a
  camada bruta, os dois complementos, as 7 tabelas da normalização (as duas na v2) e as duas vigências (`b6f80d87…`
  e `b8a0b2ed…`).

### Pendências

- O manifesto-raiz precisa ser guardado **fora** do banco e do armazém pelo responsável. A escolha do lugar (disco,
  e-mail, commit assinado, carimbo de tempo) é dele.
- As execuções anteriores à v8 não têm hash de código nem de ambiente registrado. Isso não é recuperável sem
  inventar.
- A normalização ficou mais lenta com os gatilhos da camada 1 (23 s → 35 s na cópia real). Medição e decisão ficam
  para a fase D.

## Fase D: homologação única e desempenho

### Item 9: `python -m rp homologar`

Arquivo: `app/rp/homologar.py`. O comando lê o banco só para leitura e roda, nesta ordem:
1. **Portões:**
   - integridade do SQLite e relações;
   - armazém × banco (`verificar`, com hash de manifesto e tempo da coleta);
   - coleta e normalização completas;
   - derivação da normalização vigente e hashes recalculados;
   - sem chave repetida, sem valor monetário recusado;
   - tempos das coletas, proveniência, execução identificada e esquema.
2. **Referência da camada bruta anterior à carga** (`--referencia` do `portoes --gravar-referencia` e/ou `--raiz` do
   manifesto-raiz guardado fora). Pelo menos uma é obrigatória.
3. **Reprodução determinística:** um banco novo montado só do armazém, numa pasta temporária, normalizado e derivado
   em cada vigência do ativo, e comparado camada a camada: bruto, tempos, manifestos, as 7 tabelas da normalização e
   cada vigência.
4. **Testes:** a suíte de produção (`app/tests`) e a de investigação (`docs/stages/03-data-model/validation`, 26
   testes), em processo separado. O resumo e o código de saída são a evidência.
5. **Pendências contábeis:** divergências com o RREO por regra de agregação, PDFs do RREO sem transcrição, pares
   1 ↔ 15 de natureza indeterminada e regras em uso sem decisão de governança.

O resultado nunca é mais forte do que o que rodou:

| Resultado | Quando | Saída |
|---|---|---|
| `reprovada` | alguma verificação técnica executada falhou | 1 |
| `incompleta` | sem falha técnica, mas alguma verificação obrigatória não foi executada (`--sem-testes`, `--sem-reproducao`, sem referência). **Não é homologação.** | 2 |
| `aprovada_com_ressalvas` | aprovação técnica (tudo obrigatório executado e aprovado), com pendências contábeis listadas | 3 |
| `aprovada_sem_ressalvas` | aprovação técnica e nenhuma pendência | 0 |

O banco ativo e o armazém não são escritos. `--saida` grava o relatório completo e nunca sobrescreve.

**Execução real** (cópia v8 do banco ativo, com `--raiz` gerado na fase C):
```
python -m rp homologar --banco <copia v8> --raiz <raiz_real_fase_c.json> --saida <homologacao_real.json>
```
| Verificação | Resultado |
|---|---|
| 15 portões técnicos | todos aprovados |
| Raiz externa e referência da camada bruta | confere |
| Reprodução determinística | igual nas duas vigências (`b6f80d87…`, `b8a0b2ed…`), normalizador v2 nos dois (43 s) |
| Testes de produção | `627 passed in 340.22s` |
| Testes de investigação | `26 passed in 11.73s` |
| **Resultado** | **`aprovada_com_ressalvas`** (saída 3), em 411 s |
| Pendências contábeis | divergência com o RREO em 32 documentos (RREO-COL v1: 257 colunas; v2: 231); 3 PDFs sem transcrição (snapshots `36f1ef8e`, `722468ea`, `d369f5b9`); pares 1 ↔ 15 (3.776 linhas de par somando todos os cortes); regra `VALOR-OBRIG v1` sem decisão de governança |

Esta execução foi feita **antes** da retirada do índice `ix_visao_valor_coleta` (ver item 10), ou seja, com a
impressão anterior da v8. Ela é refeita sobre uma cópia nova na validação final.

Testes: `app/tests/test_homologar.py` (10 testes).
- Sem testes, sem reprodução e sem referência dá `incompleta`, com a lista do que faltou.
- Tudo executado dá `aprovada_com_ressalvas`, com a pendência de governança do mundo sintético.
- Uma suíte que falha reprova, e um portão que falha reprova.
- A reprodução acusa um valor alterado depois da derivação.
- A CLI devolve o código de saída e não sobrescreve o relatório.

### Revisão da fase D

- **Pares nas pendências:** o "3.776" vinha rotulado como pares, mas soma as linhas de par de todos os cortes. A
  pendência agora separa `empenhos_distintos_em_par` (731 nos dados reais) de
  `linhas_de_par_somando_todos_os_cortes` (3.776).
- **Execução anterior à v8:** num banco recém-migrado, a derivação homologada não tem hash de código, e o portão
  `execucao_identificada` reprova. Isso está certo: a identificação não existe e não é inventada. Agora o detalhe diz
  o que fazer: `python -m rp processar` produz uma normalização e uma derivação identificadas.

### Item 10: desempenho medido

Script reproduzível: `docs/audits/benchmark_processamento.py`. Resultados em
`docs/audits/benchmark_processamento_20261009.json`. Mesma máquina e mesmos dados, uma execução por vez, comparando o
código de `main` (82a2d75, antes das fases) com o código atual.

| Medida | `main` (v5) | atual (v8) | Observação |
|---|---|---|---|
| Abrir (migração v5 → v8 + tempos e hashes dos manifestos) | 0,03 s | 7,85 s | uma vez só por banco |
| Normalizar | 10,6 s | 8,0 s | variação entre rodadas; sem os gatilhos da camada 1: 8,7 s, ou seja, o custo dos gatilhos não aparece acima do ruído |
| Derivar (atual) | 7,4 s | 7,4 s | |
| Derivar ("como estava em") | 2,1 s | 2,1 s | |
| Tamanho após VACUUM | 450,3 MB | 454,2 MB | +0,9% (relações e tempos novos) |
| Painel: série entre exercícios (mediana de 15) | 0,316 s | 0,307 s | com ordenação por subconsultas era 0,359 s; trocada por junção |
| Painel: visão geral (mediana de 15) | 0,492 s | 0,499 s | com subconsultas era 0,559 s |
| Demais consultas do painel | — | iguais dentro do ruído | ver o JSON |

Decisões tomadas pela medição:
- **Junção em vez de subconsultas:** em `vigencia.coletas_vigentes`, o caminho mais chamado do painel, a ordenação
  nova (início, conclusão, `snapshot_uid`) usa uma junção com `coleta_tempo` em vez de três subconsultas
  correlacionadas. Mesma ordem e mesmo resultado (os testes da fase B passam); tempo de volta ao de `main`.
- **Índice removido:** o índice `ix_visao_valor_coleta (coleta_id)`, criado na v8 sem medição, foi **retirado**,
  pois a v8 ainda não foi publicada. Medido com cerca de 200 mil ligações: ele piorava a conferência de proveniência
  (4,2 → 13,0 ms). A alternativa `(derivacao_id, coleta_id)` ganharia 1,4 ms por cerca de 300 KB. Nenhum índice
  novo foi criado. A impressão da v8 foi recalculada.
- **Planos (`EXPLAIN QUERY PLAN`):** a seleção do retrato vigente, os gatilhos da camada 1 e o da regra declarada
  usam só chave primária ou índice existente.
- **Nada incremental:** nenhum processamento incremental nem outra otimização que aumente a complexidade foi
  feito, como o pedido manda.

## Fase E: pares 1 ↔ 15 e reconciliação com o RREO

### Item 6: extração e conferência do RREO Anexo VII

**Problema encontrado e corrigido: omissão silenciosa.**
- **O defeito:** o extrator v1 atribuía cada número ao rótulo de coluna mais próximo e aceitava dois números iguais
  na mesma célula. Em 31 PDFs reais, a linha "RESTOS A PAGAR (INTRA-ORÇAMENTÁRIOS)", toda de zeros, perdia a coluna
  (e) sem nenhum erro: o "0,00" de (e), alinhado à direita, fica mais perto do rótulo de (f).
- **Medição nos 33 PDFs transcritos:** todas as 130 linhas reconhecidas têm exatamente 12 números. Cada número fica
  estritamente entre os rótulos das colunas vizinhas, com folga mínima de 24 pt. As identidades do próprio documento
  fecham em todas: e = a + b − c − d, k = f + g − i − j, L = e + k, TOTAL (III) = (I) + (II).

**Extrator v2 (`rp-rreo-coordenadas/2`, `app/rp/normalizar.py`):**
- uma linha reconhecida é transcrita inteira (12 números, posição a posição, cada um entre as colunas vizinhas) ou
  o PDF é recusado;
- as identidades do documento precisam fechar;
- TOTAL (III) e a linha (I) são obrigatórias;
- linha repetida com outro valor continua recusada.

Sobre os dados reais:
- as 1.529 células da v1 saem iguais;
- as 31 células perdidas são recuperadas (todas iguais a 0);
- os mesmos 3 PDFs continuam recusados;
- `rreo_valor` passa de 1.529 para 1.560 linhas;
- o hash das derivações não muda, porque a conciliação usa só a linha TOTAL (III).

**Matriz de cobertura (`app/rp/rreo_cobertura.py`, usada pela homologação):** documentos esperados (todos os
arquivos do Anexo VII na lista de publicações mais recente de cada exercício) × coletado × transcrito × recusado.

| Esperados | Transcritos | Recusados pelo extrator | Não coletados |
|---|---|---|---|
| 114 | 32 | 3 (2016, 2018 e 2019, 6º bimestre) | 79 (bimestres 1 a 5 de 2016 a 2024) |

**Conferência independente (`docs/audits/rreo/conferencia_independente.py`):**
- **Método:** cada PDF coletado é lido de novo por **outro motor**, o `pdftotext -table` do xpdf 4.06 (a produção
  usa as coordenadas de palavra do PyMuPDF/MuPDF). As células são comparadas e as identidades conferidas nessa
  segunda leitura.
- **Resultado:** os **32 transcritos estão conferidos**, com **1.512 de 1.512 células iguais** e 0 divergentes.
- **Os 3 recusados também são lidos pela segunda leitura, e as identidades fecham:**
  - 2016: o modelo antigo de colunas (rótulos diferentes);
  - 2018 e 2019: o PDF não imprime o período nem a data de emissão.
- **Limite:** isso prova que os números do banco são os impressos no PDF. Não prova a correção contábil do RREO.
- Resultado completo em `docs/audits/rreo/COBERTURA_E_CONFERENCIA.md` e `.json`.

**Divergência de 2026 reavaliada (`docs/audits/rreo/DIVERGENCIA_2026.md`):**
- **Ela não é estável.** Os 0,14% e 0,28% em (i) dos 3º e 4º bimestres eram os valores da coleta de 29/09. Na
  coleta de 06/10 passaram a 0,24% e 0,66%:
  - 3º bimestre: (i) de 109.112,43 para 183.276,43; (h) de 216.913,24 para 291.077,24;
  - 4º bimestre: (i) de 237.728,25 para 551.817,35; (h) de 345.479,56 para 685.898,72.
- **A coluna (j) do 2º bimestre**, que conferia, passou a diferir em 1.270.679,25.
- **Causa da mudança, com evidência:** a comparação dos retratos da API do mesmo período fechado (29/09 × 06/10)
  mostra, empenho por empenho, cancelamentos novos de 1.270.679,25 (8 empenhos de 2025, com data até 30/04) e
  pagamentos e liquidações menores (16818 e 18883 de 2025 até 30/06: −74.164,00 exatos em (h) e (i); até 31/08:
  pagamentos −314.089,10 e liquidações −340.419,16). São lançamentos que a API passou a mostrar em períodos cujos RREOs
  já estavam emitidos.
- **Causa da diferença original: não determinada.** Não há retrato da API anterior à emissão de cada RREO.
- Nada foi ajustado. A API continua como fonte primária, e a divergência continua visível no painel e nas
  pendências da homologação.

### Item 5: pares entidade 1 ↔ 15

`docs/audits/pares/PARES_1_15.md` (gerado por `pares_1_15.py`) documenta:
- **Pares por corte:**
  - 2024: 1 par;
  - 2025: 20 pares, 11 com a mesma inscrição;
  - 2026: 731 pares, todos com a mesma inscrição, somando R$ 31.813.905,47 de cada lado. São 711 de empenhos de 2025,
    19 de 2024 e 1 de 2023: os "711 pares" do pedido são os de 2025.
- **Valores de cada lado e lado com execução:** em 2026 a execução está só na Prefeitura (571 pares em 30/09).
- **As regras:**
  - PAR-24 v1: operacional, FORTE EVIDÊNCIA; só identifica, não altera valor;
  - CONS-PAR v1 e v2: experimentais, HIPÓTESE.
- **O efeito de cada decisão no Município:** em 2026, as duas regras de consolidação retirariam R$ 31.813.905,47 de L
  e de S1. O oficial continua com os dois lados, como a API e o RREO consolidado de 2026 publicam.
- **Nenhuma conclusão sobre a natureza** (duplicidade ou transferência). Promover CONS-PAR exige evidência
  independente (decisão D7), e ela não existe.

**Rascunho do e-SIC, versão 3 (`docs/foi-requests/FOI_REQUEST_DRAFT.md`):**
- item 1 detalhado por ano;
- pergunta 6 com os valores das duas coletas;
- pergunta 10, nova, com as alterações retroativas observadas, empenho por empenho.
- **Situação: não enviado.** O envio exige CPF e cabe ao responsável. Nenhuma resposta foi inventada nem presumida.

### Testes

- **`app/tests/test_rreo_extrator_v2.py` (12 testes):**
  - linha de zeros com número alinhado à direita (o caso real) sai inteira;
  - número faltando recusa a linha inteira;
  - número fora da faixa da coluna é recusado;
  - cada identidade que não fecha é recusada;
  - TOTAL diferente da soma é recusado;
  - sem TOTAL ou sem (I), o PDF é recusado;
  - linha repetida com outro valor é recusada;
  - matriz de cobertura e pendências da homologação.
- **Ajustados para o extrator v2,** que agora exige linhas completas que fecham as identidades:
  - `test_auditoria_processamento::test_NORM02_*` (a célula repetida agora recusa a linha inteira, pela contagem);
  - `test_revisao_banco::test_REV11_*`.
  - Nenhum teste foi apagado.

### Verificação com os dados reais

Cópia nova do banco ativo, migrada para a v8 e processada com o extrator v2:
- **Normalização:** 266.787 registros iguais aos da normalização 14; `rreo_valor` com 1.560 células.
- **Derivações:** atual `b6f80d87…` e "como estava em 29/09" `b8a0b2ed…`, **iguais às homologadas**.
- **`verificar`:** 0 problemas.
- **Portões:** apto (15 de 17).

### Pendências (dependem de decisão ou de informação externa)

- **Transcrever os 3 PDFs recusados.** Os de 2018 e 2019 precisariam do período tirado dos metadados da publicação,
  e o de 2016 de um mapeamento de colunas próprio. Isso mudaria a reconciliação (linhas novas na conciliação, novo
  hash) e é decisão do responsável. A segunda leitura já mostra que os totais fecham.
- **Coletar os 79 documentos não coletados** (bimestres 1 a 5 de 2016 a 2024). Isso acrescenta bruto e muda a
  reconciliação, então também é decisão do responsável.
- **Natureza dos pares e origem da diferença original de 2026:** dependem da resposta oficial (e-SIC versão 3, não
  enviado).

## Fase F: privacidade do repositório público

Documento completo: `docs/audits/privacidade/PLANO_PRIVACIDADE.md`.

**Inventário (fatos de 09/10/2026).** O repositório é público, com 0 forks, 77 commits e as tags `etapa-04-final`
e `etapa-05-final`. Ficam versionados, com dado de credor (nome e CPF de pessoa física mascarado pela própria API):
- `data/snapshots`: 841 arquivos;
- `data/stage02-raw`: 239 arquivos;
- `data/stage01-samples`: 23 arquivos, entre eles um CSV com 1.025 CPFs mascarados;
- `data/backups`: 4 bancos SQLite.

Os mesmos conteúdos estão no histórico em caminhos antigos (`snapshots/`, `etapa01/amostras_brutas`,
`etapa02/dados_brutos`, `backups/`). Fora de `data/`, nenhum dos 5.715 nomes de pessoa física aparece em código,
testes ou documentos. Os testes usam nomes inventados.

**Feito sem reescrever nada:**
- **Fragmento de CPF:** o fragmento real de CPF mascarado citado em dois relatórios foi trocado por um exemplo
  sintético (commit `02dec6d`).
- **Prova dos testes sem o bruto:** o código exportado sem `data/` roda
  `pytest -m "not dados_reais"` → `469 passed, 1 skipped` (o pulado depende de `.git`, não de dados). O CI já pula os
  passos com dados reais quando o bruto não está no repositório.

**Plano proposto, não executado:**
1. Copiar o bruto e os backups para um local privado, com conferência por `verificar`, `raiz` e as listas SHA-256.
2. Parar de publicar com `git rm --cached` (precisa de push: autorização).
3. Retirar do histórico com `git filter-repo` num clone espelho, seguido de force push. Isso é irreversível para
   quem já clonou: muda os 77 SHAs, exige recriar as duas tags (conflita com a regra de não mover tags) e exige
   pedido ao GitHub Support para remover as referências dos PRs #1 a #19.
4. Conferência final pela API.

A alternativa é tornar o repositório privado (mudança de visibilidade, só com autorização).

**Situação:** a privacidade **não** está resolvida. O histórico público continua com os dados até a decisão do
responsável.

## Validação final (09/10/2026, código do commit `6f1663d`)

Executada sobre uma cópia nova do banco ativo, fora do OneDrive. O banco ativo só foi lido, pela API de backup do
SQLite.

| # | Verificação | Comando ou método | Resultado real |
|---|---|---|---|
| 1 | Banco ativo intacto | SHA-256 do arquivo antes e depois de tudo | `5ed6551f…` antes = depois |
| 2 | Referência da camada bruta ANTES da carga | `portoes --gravar-referencia` na cópia v5 | 529 coletas, 613 respostas, hashes gravados |
| 3 | Migração v5 → v8 | abertura pelo código | um backup (`antes-migracao-v5-v8`), impressão da v8 confere |
| 4 | Manifesto-raiz | `raiz --gravar`, fora da pasta do banco | 529 coletas, 411 objetos; raízes `4065bea9…` / `cfb99745…` |
| 5 | Normalização v2 | `normalizar` | 266.787 registros, 0 recusas, `rreo_valor` 1.560, 3 PDFs recusados (os já conhecidos) |
| 6 | Derivações | `derivar` atual e "como estava em 29/09" | `b6f80d879ee89d5f…` e `b8a0b2ed2328bf09…`, **iguais às homologadas** (25 e 24) |
| 7 | `verificar` | `banco.verificar` | 0 problemas |
| 8 | Testes sintéticos | `python -m pytest -q tests -m "not dados_reais"` | `470 passed, 169 deselected in 113.00s` |
| 9 | Testes com dados reais | `python -m pytest -q tests -m dados_reais` | `169 passed, 470 deselected in 187.67s` |
| 10 | Testes de investigação | `python -m pytest -q tests` (validation) | `26 passed in 11.00s` |
| 11 | Testes sem o bruto (privacidade) | exportação sem `data/`, `-m "not dados_reais"` | `469 passed, 1 skipped` (o pulado depende de `.git`) |
| 12 | Comparação com a base homologada | `comparar-bancos` (ativo v5 × cópia v8) | bruto igual; `rp_registro`, movimentação e catálogos iguais; `rreo_valor` 1.529 → 1.560 e `rreo_extracao` diferentes, só pelo extrator v2 (rótulo de versão + 31 células recuperadas); derivações iguais nas duas vigências; tempos e hashes de manifesto "não comparáveis" (o ativo é v5) |
| 13 | Banco novo só do armazém | reprodução do `homologar` e fases A–C | igual camada a camada à cópia processada (bruto, tempos, manifestos, 7 tabelas da normalização, 2 vigências) |
| 14 | Regras, parâmetros, decisões | catálogo ativo × cópia | nenhuma linha alterada ou removida; acréscimos: regra `VALOR-OBRIG v1` e tipo de anomalia `VALOR-RECUSADO` |
| 15 | Restauração de backup | cópia do backup da migração + `integrity_check` | `ok`, versão 5, derivação 25 `b6f80d87…`, bruto igual ao do ativo |
| 16 | Interface só leitura | 7 páginas pela aplicação WSGI + um POST | 7 × `200 OK`, POST `405`, arquivo do banco idêntico depois |
| 17 | Homologação oficial | `python -m rp homologar --referencia … --raiz … --saida …` | **`aprovada_com_ressalvas`** (saída 3) em 500,7 s: 21 verificações obrigatórias executadas e aprovadas (19 técnicas + `639 passed` + `26 passed`) |

### Mudanças de resultado em relação ao homologado

- **Indicadores e derivações:** nenhuma mudança. Os dois `hash_resultado` homologados se mantêm.
- **Normalização do RREO:** 31 células a mais em `rreo_valor`, todas da coluna (e) da linha INTRA e todas iguais a 0.
  O extrator v1 as omitia em silêncio. Elas não entram na conciliação, que usa só a linha TOTAL (III).
- **Regra nova:** `VALOR-OBRIG v1`, que recusa o retrato com campo monetário ausente. Nos dados reais não há recusa;
  a regra não produz valor.

### Estado da homologação

**Aprovação técnica: sim. Aprovação sem ressalvas: não.** Pendências contábeis e de governança abertas, listadas pelo
próprio comando:
- **Divergência com o RREO** em 32 documentos (RREO-COL v1: 257 colunas; v2: 231). A causa está explicada só na
  parte que cresceu entre as coletas de 2026.
- **79 documentos do Anexo VII não coletados** e **3 coletados e recusados pelo extrator** (2016, 2018, 2019).
- **Pares 1 ↔ 15** (731 empenhos) de natureza não determinada.
- **Regra `VALOR-OBRIG v1`** sem decisão de governança.

Não se declara a apuração 100% correta. A privacidade do histórico público também não está resolvida (fase F).
