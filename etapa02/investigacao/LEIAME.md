# Scripts de INVESTIGAÇÃO — Etapa 02

**Nada nesta pasta é código de produção.** São scripts descartáveis, escritos
para testar hipóteses sobre a fonte. A Etapa 03 não deve importar nem copiar
este código. Deve reescrever a partir da especificação do relatório.

| Script | O que faz |
|---|---|
| `coletar.py` | baixa todas as páginas de uma consulta a `/empenhos/restos-a-pagar` e grava os bytes brutos + `MANIFESTO.jsonl` (URL, hora, status, SHA-256) |
| `extrair_rreo.py` | extrai os números do PDF do RREO Anexo VII por coordenada de coluna |
| `conciliar_rreo.py` | soma a API e compara com cada coluna do RREO (`python conciliar_rreo.py todos`) |
| `conciliar_bimestres.py` | diferença API − RREO em cada bimestre de 2025 e 2026 |
| `segmentar.py` | quem está em cada aba, regra de pertinência, somas por segmento |
| `analisar_periodo.py` | testes controlados de `dataInicial`/`dataFinal` (executa ao ser importado) |
| `casos.py` | seleciona os casos A–I e baixa a movimentação de cada empenho |
| `reconstruir.py` | modelo de reconstrução a partir da movimentação × valores da API |
| `validar_amostra.py` | o mesmo modelo numa amostra aleatória estratificada (semente fixa) |

Os dados brutos ficam em `../dados_brutos/` e as saídas em `../resultados/`.
Os scripts leem do disco o que já foi baixado e só consultam a API para o que
ainda não está lá.
