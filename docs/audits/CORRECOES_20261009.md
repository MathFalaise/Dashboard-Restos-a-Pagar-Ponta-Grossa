# Correção integral e auditoria do banco (pedido de 09/10/2026)

Registro do que foi feito, por fase, com os comandos executados e os resultados reais. Nada aqui é declaração de
apuração 100% correta: o que continua pendente está dito em cada fase.

Ordem aprovada pelo responsável pelo projeto em 09/10/2026:

| Fase | Itens do pedido | Situação |
|---|---|---|
| A | 3 (contrato da API), 2 (campo monetário ausente) | feita (este documento) |
| B | 4 (precisão temporal dos retratos) | pendente |
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
