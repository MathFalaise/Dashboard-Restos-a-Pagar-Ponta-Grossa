# Correção da matriz de concordância (19/10/2026)

**Erro corrigido:** a matriz de 13/10/2026 classificava como "diferença de escopo" diferenças entre a fonte Elotech e
o Siconfi que não tinham essa causa. Só a classificação muda: nenhum valor, regra contábil, banco ou indicador
publicado é alterado.

## O erro

- **Onde estava:** na comparação C (Elotech no escopo publicado × Siconfi), quando o RREO do portal era igual ao
  Siconfi, a célula herdava a explicação do catálogo.
- **Por que estava errado:** o catálogo explica a diferença entre o Elotech no escopo da derivação (ESCOPO-MUN v1) e o
  RREO. Nos bimestres em que a ESCOPO-MUN v2 já tira a entidade 7, o Elotech publicado é outro valor, e a explicação
  herdada ("entidade 7 dentro, documento sem ela") não vale.
- **Exemplo:** em 31/12/2018, o saldo tinha diferença de +R$ 3.052,00 e aparecia como "diferença de escopo". O painel
  já exclui a entidade 7 nesse corte; a diferença vem de R$ 3.052,00 a menos de cancelados na fonte, sem causa
  determinada.

## A correção

- **Regra nova de herança** (`matriz_concordancia.py`): a explicação do catálogo só é herdada quando o Elotech
  publicado é igual, na coluna, ao Elotech da derivação que o catálogo explica.
- **Quando não é igual:** a célula fica "causa não determinada", com a evidência "PDF igual ao Siconfi; a explicação
  do catálogo é do escopo da derivação (ESCOPO-MUN v1), diferente do escopo publicado neste período".
- **Teste de regressão:** `tests/test_auditoria_20261013.py::test_matriz_nao_herda_escopo_onde_a_escopo_mun_v2_difere_da_v1`.
  - Falha com a matriz de 13/10/2026 e passa com a nova.
  - Confere que nenhuma célula Elotech × Siconfi ou painel × Siconfi é "diferença de escopo" num bimestre em que a
    ESCOPO-MUN v2 difere da v1.

## Prova de que só a classificação mudou

1. **Antes da correção:** o script reproduziu a matriz publicada byte a byte (mesma derivação 37, normalização 18 e
   leitura do Siconfi `coleta_20261013-223143`).
2. **Depois da correção:** as 3.140 células têm os mesmos valores (esperado, observado, diferença). Só a classe e a
   evidência mudaram, em 15 células.

| Comparação | Corte | Coluna/grupo | Diferença (R$) | Antes | Depois |
|---|---|---|---:|---|---|
| Elotech × Siconfi | 2018, 2º bim | k | −518.958,95 | diferença de escopo | causa não determinada |
| Elotech × Siconfi | 2018, 2º bim | L | −631.523,26 | diferença de escopo | causa não determinada |
| Painel × Siconfi | 2018, 2º bim | saldo | −631.523,26 | diferença de escopo | causa não determinada |
| Elotech × Siconfi | 2018, 3º bim | k | 220.214,74 | diferença de escopo | causa não determinada |
| Elotech × Siconfi | 2018, 3º bim | L | 245.563,59 | diferença de escopo | causa não determinada |
| Painel × Siconfi | 2018, 3º bim | saldo | 245.563,59 | diferença de escopo | causa não determinada |
| Elotech × Siconfi | 2018, 4º bim | k | −281.242,19 | diferença de escopo | causa não determinada |
| Elotech × Siconfi | 2018, 4º bim | L | −255.262,90 | diferença de escopo | causa não determinada |
| Painel × Siconfi | 2018, 4º bim | saldo | −255.262,90 | diferença de escopo | causa não determinada |
| Elotech × Siconfi | 2018, 5º bim | k | −42.835,18 | diferença de escopo | causa não determinada |
| Elotech × Siconfi | 2018, 5º bim | L | −13.803,79 | diferença de escopo | causa não determinada |
| Painel × Siconfi | 2018, 5º bim | saldo | −13.803,79 | diferença de escopo | causa não determinada |
| Elotech × Siconfi | 2018, 6º bim | k | −47.982,08 | diferença de escopo | causa não determinada |
| Elotech × Siconfi | 2018, 6º bim | L | 3.052,00 | diferença de escopo | causa não determinada |
| Painel × Siconfi | 2018, 6º bim | saldo | 3.052,00 | diferença de escopo | causa não determinada |

Os demais bimestres em que a v2 difere da v1 (2019, 1º ao 4º; 2020, 2º ao 6º) não tinham herança indevida.

## Impacto

**Resíduos sem causa de 2018** (relatório de qualidade):

| Comparação | Antes: células | Antes: valor | Depois: células | Depois: valor |
|---|---:|---:|---:|---:|
| Elotech × Siconfi | 36 | 63.108.756,55 | 46 | 65.369.195,23 |
| Painel × Siconfi | 19 | 42.639.252,66 | 24 | 43.788.458,20 |

**Relatórios de qualidade:**
- `QUALIDADE_20261019.md` / `.json` foi gerado com a matriz corrigida.
- `QUALIDADE_20261013.*` continua como registro histórico.
- Fora os resíduos de 2018, a única diferença entre os dois é a idade da última coleta, que depende da data da medição.

**Testes:** a suíte de produção tem 692 testes passando: os 691 anteriores e o novo.
