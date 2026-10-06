# Plano de correções da auditoria técnica

Base: `AUDITORIA_TECNICA_COMPLETA.md`. Ramo `auditoria-tecnica`. A implementação é feita por grupos pequenos, cada um com testes próprios.

**Regra de preservação:** nenhum grupo pode mudar dado bruto, snapshot, regra, fórmula ou valor homologado.

**Critério de aceite de cada grupo** (e todos juntos no fim):
- suíte de produção e da investigação passando;
- `verificar` sem problemas e `portoes` apto;
- reconstrução em banco novo com os mesmos `hash_resultado` (`2f6b4e29…` e `b8a0b2ed…`);
- comparação de estado com a homologação 04.6 com 0 diferenças nos 5.575 valores de tela e na camada painel;
- conferência das telas da Etapa 05 (100.201 valores) sem diferença.

## Grupos implementados nesta tarefa (P0 e P1)

| ID | Problema | Sev. | Correção | Arquivos | Testes | Risco |
|---|---|---|---|---|---|---|
| **G1 — migrações atômicas** | | | | | | |
| MIG-01 | DDL de migração confirmado comando a comando: falha deixa estado intermediário | ALTA | `BEGIN` explícito; COMMIT ou ROLLBACK da migração inteira, inclusive o registro em `esquema_versao` | `rp/banco.py` | migração com comando inválido no meio: nada criado e versão igual; nova tentativa com migração correta aplica | baixo: o mesmo SQL, só a transação muda |
| MIG-02 | criação de banco novo não atômica | MÉDIA | criar em arquivo temporário e renomear no fim (`os.replace`); destino existente nunca é tocado | `rp/banco.py` | falha simulada na semeadura: destino não existe | baixo |
| **G2 — HTTP** | | | | | | |
| HTTP-01 | `except Exception` repete e mascara erro de programação | MÉDIA | `FalhaTransitoria` (timeout, conexão, protocolo) é a única repetida; TLS e URL inválida → `ErroDeRede` sem repetição; o resto propaga | `rp/http.py` | casos 9–15 da fase 15 | médio: muda a classificação de erros. Os testes antigos de 503, 4xx e rede continuam |
| HTTP-02 | `Retry-After` em data HTTP ignorado | BAIXA | aceitar data (RFC 9110), com o mesmo teto | `rp/http.py` | Retry-After em data respeitado | baixo |
| **G3 — paginação e contrato da API** | | | | | | |
| COL-01 | soma = total não prova completude | ALTA | ordem (anoempenho, empenho) estritamente crescente entre páginas; registro idêntico repetido proibido; segunda leitura de todas as páginas se houver mais de uma (bytes iguais), com hashes no manifesto | `rp/coletor.py` | casos 1–8 da fase 15 | médio: dobra as leituras dos cortes de várias páginas; a coleta falha (visível) se a API mudar a ordem |
| COL-02 | metadados da página não validados | MÉDIA | `number`, `numberOfElements`, `size` ecoado e `totalPages` coerentes | `rp/coletor.py` | casos 6–8 | baixo: os campos estão nos 247 snapshots reais |
| COL-03 | sem `totalElements` inteiro, até 10.000 páginas | MÉDIA | falha imediata | `rp/coletor.py` | `totalElements` ausente | baixo |
| COL-04 | `pagina > totalPages` faz 1 requisição a mais | BAIXA | `>=` | `rp/coletor.py` | contagem de requisições | baixo |
| COL-05 | entidade fora do catálogo vira "sem RP" silencioso | MÉDIA | observação no snapshot quando a entidade não está no catálogo vigente | `rp/coletor.py` | observação presente | baixo: não recusa nada |
| **G4 — vigência e determinismo** | | | | | | |
| CLI-01 | `processar --em` cru: comparação textual errada | MÉDIA | `instante()` único (pacote `rp`), usado pela camada painel e pelo CLI; a derivação recusa formato não canônico | `rp/__init__.py`, `rp/cli.py`, `rp/derivar.py`, `rp/painel/consulta.py` | `--em AAAA-MM-DD` = fim do dia; `--em ontem` recusado; mesmo hash com a forma canônica | baixo: a derivação homologada já usa a forma canônica |
| DET-01 | `set` em mensagem gravada | BAIXA | `sorted` | `rp/normalizar.py` | mesma mensagem com `PYTHONHASHSEED` diferentes | nulo |
| **G5 — normalização e derivação (sem mudar regra)** | | | | | | |
| NORM-02 | conflito de valor na mesma célula do RREO descartado em silêncio | MÉDIA | valor diferente → `LayoutDesconhecido`; valor igual aceito | `rp/normalizar.py` | conflito sintético registrado como erro | baixo: 0 conflitos nos 33 PDFs (verificado) |
| DER-01 | movimentação de coleta não completa entra na derivação | MÉDIA | `c.status='completa'` | `rp/derivar.py` | lançamento de coleta incompleta fora | nulo nos dados atuais: hash conferido |
| DB-03 | `INSERT OR IGNORE` do catálogo esconde divergência código × banco | MÉDIA | depois de semear, conferir regras, tipos de anomalia, parâmetros e decisões; divergência → `CatalogoDivergente` | `rp/regras.py`, `rp/governanca.py` | definição alterada → erro; decisão nova acrescentada → aceita | baixo: banco ativo 100% igual (verificado) |
| **G6 — verificação e portões** | | | | | | |
| DB-01 | `hash_resultado` gravado nunca recalculado | ALTA | portão `hash_resultado_confere` (última derivação de cada vigência) | `rp/portoes.py` | UPDATE em `visao_valor` → reprovado | baixo: só leitura; +3 s |
| DB-02a | FKs ausentes; órfãos não procurados | MÉDIA | portão `integridade_relacional`: `foreign_key_check` + órfãos de cada relação lógica (inclusive uids de `coletas_json`) | `rp/portoes.py` | órfão inserido → reprovado | baixo |
| NORM-01 | campo monetário ausente vira 0 | MÉDIA | portão `campos_monetarios_ausentes` | `rp/portoes.py` | registro sem `pagoProc` → reprovado | baixo |
| DER-02 | tipo de lançamento desconhecido vale 0 | MÉDIA | portão `lancamento_desconhecido` | `rp/portoes.py` | tipo 99 → reprovado | baixo |
| POR-01 | `apto` com portões não verificados | MÉDIA | `nao_verificados` e `apto_sem_ressalvas`; `apto` e código de saída mantidos | `rp/portoes.py`, README | campos presentes | baixo |
| REC-01 | `verificar` só compara presença de uid | MÉDIA | conferência manifesto × banco campo a campo | `rp/banco.py` | status adulterado detectado | baixo: banco ativo conferido |
| ARM-01 | órfãos e temporários não relatados | BAIXA | relatados em `Armazem.verificar` | `rp/armazem.py` | objeto órfão e `.tmp` relatados | baixo: 0 hoje |
| **G7 — equivalência de bancos** | | | | | | |
| DET-02 | `hash_camada0` não sobrevive à reconstrução | MÉDIA | `rp/equivalencia.py`: impressões estáveis da camada 0, da normalização e das derivações; comando `comparar-bancos`; `hash_camada0` antigo mantido | `rp/equivalencia.py`, `rp/cli.py` | reconstruído = original; adulterado ≠ | baixo: novo, só leitura |
| **G8 — dependências e repositório** | | | | | | |
| DEP-01 | transitivas sem versão | MÉDIA | `requirements-lock.txt` com as versões exatas do ambiente homologado (nenhuma atualização) | `app/requirements-lock.txt`, README | instalação com a trava (documentada) | nulo |
| REP-01 | backup SQLite novo iria para o Git | BAIXA | `data/backups/*.sqlite` no `.gitignore`; os 4 já versionados continuam | `.gitignore` | — | nulo: nada apagado |

## Adiados, com motivo

| ID | Motivo | Classe |
|---|---|---|
| DB-02b, DB-04, DB-05 (migração v5: FKs, chaves, gatilhos de `regra` e `anomalia_tipo`) | muda `esquema_versao` e, portanto, o `hash_camada0` homologado; reconstruir tabelas derivadas de 600 mil linhas no banco ativo exige decisão e janela própria | P2 |
| REC-02 (SHA do manifesto no banco) | migração de esquema | P2 |
| NORM-01 (ausência como NULL) | muda regra homologada e esquema: **REGRA HOMOLOGADA A REVISAR** | P2 |
| inscrição negativa fora das faixas | **REGRA HOMOLOGADA A REVISAR**; 0 casos hoje | P2 |
| PNL-02 (`pares` com disponibilidade na camada painel) | muda a saída comparada pela homologação | P2 |
| DB-06 (`coletas_json` relacional) | migração; o portão já confere os uids | P2 |
| DB-07 (retenção de execuções) | política operacional do responsável | P2 |
| COL-06, COL-07, HTTP-04, NORM-03, NORM-04, DER-03, DER-04, MIG-03, PNL-01 | baixo risco ou mudança de hash | P3 |
| hashes de pacotes na trava | exige baixar pacotes (autorização) | P2 |
| CI | proposta da consolidação pós-05; aguarda decisão | P2 |
| bruto fora do Git | decisão de privacidade | decisão |
