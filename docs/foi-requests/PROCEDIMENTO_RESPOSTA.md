# Como registrar a resposta do e-SIC como evidência externa

Auditoria corretiva de 13/10/2026, item 11.

**Enquanto não houver resposta:**
- nenhuma pergunta da minuta (`ESIC_MINUTA_V4_20261013.md`) é dada como resolvida;
- as regras que dependem dela continuam com ressalva.

## 1. Ao enviar

1. **Guardar o comprovante:**
   - **O quê:** o protocolo, a data e o texto efetivamente enviado.
   - **Onde:** no armazenamento privado, em `~/RestosAPagar_local/evidencias_sessoes/esic/`. O comprovante tem dados
     do solicitante e nunca vai para o repositório.
2. **Registrar no repositório:** número do protocolo e data de envio no topo da minuta, num commit. Esses dois dados
   não identificam o solicitante.

## 2. Ao receber a resposta

1. **Guardar o documento como recebido:** PDF ou e-mail exportado, sem editar, na mesma pasta privada.
2. **Registrar a evidência no banco e no armazém:**
   ```bash
   python -m rp registrar-evidencia --tipo e-SIC --arquivo CAMINHO_DO_DOCUMENTO --origem "e-SIC Prefeitura de Ponta Grossa, protocolo N" --data AAAA-MM-DD --descricao "Resposta ao pedido de 13/10/2026 (blocos ...)"
   ```
   O comando grava o SHA-256, a data, a origem e o manifesto, e devolve o `evidencia_id`.
3. **Avaliar cada pergunta.** Para cada bloco, registrar uma de três situações:
   - **respondida:** com o trecho que responde;
   - **respondida em parte:** com o trecho e o que falta;
   - **não respondida.**

## 3. Efeito nas regras e nos indicadores

| Pergunta | Regras afetadas | Se a resposta CONFIRMA | Se a resposta CONTRADIZ |
|---|---|---|---|
| A1–A3 (natureza das cópias) | COPIA-ORIGEM v1, CONS-PAR v4, PAR-24 v1 | nova decisão (`decidir-regra`) com `--evidencia <id>`, status CONFIRMADO, sem ressalva | nova versão da regra (nunca editar a vigente), testes, decisão e registro de impacto |
| A4, B1, B2 (datas de inclusão) | catálogo de explicações (classe T) | a explicação passa a "explicada" com a fonte do e-SIC | a diferença volta a "não determinada" |
| C1–C2 (entidade 7) | ESCOPO-MUN v2 | ressalva dos períodos resolvidos retirada (nova decisão) | ESCOPO-MUN v3 com o mapa corrigido |
| D1–D3 (versões do Siconfi) | matriz de concordância | a nova leitura do Siconfi (`recoletar_siconfi.py`) passa a citar a versão válida | contradição mantida e documentada |
| E1 (resíduos) | matriz, catálogo de explicações | causa registrada com a fonte | resíduo continua contado |

**Toda mudança de valor publicado** segue o mesmo rito de 13/10/2026:
1. backup conferido;
2. `docs/audits/governanca/retrato_municipio.py` antes e depois;
3. relatório de impacto;
4. testes;
5. `python -m rp homologar`.

## 4. O que nunca fazer

- **Não declarar respondido** sem documento registrado (SHA-256 no banco e no armazém).
- **Não editar uma regra vigente** para encaixar a resposta: a correção vira versão nova.
- **Não apagar a pendência** de uma pergunta não respondida: ela continua com o seu impacto financeiro.
