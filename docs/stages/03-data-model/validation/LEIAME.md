# Validação do modelo — Etapa 03

**Não é código de produção.** Existe para provar que o modelo de `../modelo/schema.sql` comporta os casos reais das Etapas 01 e 02. A Etapa 04 deve reimplementar a partir da especificação do relatório, não copiar este código.

- Não faz nenhuma requisição à internet: lê só os arquivos brutos de `../../etapa01` e `../../etapa02`.
- O banco é **descartável**: é recriado do zero a cada execução.

```bash
python construir_banco.py CAMINHO/rp_validacao.sqlite
```

```bash
python -m pytest tests -q
```

| Módulo | Camada | O que faz |
|---|---|---|
| `rpval/bruto.py` | 0 | cria o banco; `registrar_coleta` (única via de escrita do bruto, atômica); importa as Etapas 01/02 |
| `rpval/normalizar.py` | 1 | tipagem fiel (centavos, chaves ausentes), sem interpretação; transcrição do PDF do RREO |
| `rpval/regras.py` | 2 | catálogo versionado de regras e tipos de anomalia |
| `rpval/derivar.py` | 2 | categoria, S1–S3, anomalias, continuidade, pares espelhados, visões, conciliação, hash |
| `rpval/consultas.py` | — | "como estava em", histórico de um corte, diferença entre snapshots |
| `tests/test_integridade.py` | — | 26 testes; um deles é **SINTÉTICO** e está marcado assim no nome |
