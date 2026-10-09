# Correção integral e auditoria do banco (pedido de 09/10/2026)

Registro do que foi feito, por fase, com os comandos executados e os resultados reais. Nada aqui é declaração de
apuração 100% correta: o que continua pendente está dito em cada fase.

Ordem aprovada pelo responsável pelo projeto em 09/10/2026:

| Fase | Itens do pedido | Situação |
|---|---|---|
| A | 3 (contrato da API), 2 (campo monetário ausente) | feita |
| B | 4 (precisão temporal dos retratos) | feita (suíte: 604 passed) |
| C | 1 (integridade relacional), 7 (proveniência e hashes) | pendente |
| D | 9 (homologação única), 10 (desempenho) | pendente |
| E | 5 (pares 1 ↔ 15), 6 (RREO) | pendente |
| F | 8 (privacidade do repositório) | pendente; reescrita de histórico só com autorização explícita |

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
