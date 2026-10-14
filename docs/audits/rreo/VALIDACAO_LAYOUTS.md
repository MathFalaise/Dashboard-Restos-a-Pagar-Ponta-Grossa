# Validação das regras de layout do RREO (2016 e impressões do Siconfi)

Gerada por `docs/audits/rreo/validar_layouts.py`: cada PDF recusado pelo extrator de produção é lido pela regra de layout versionada (PyMuPDF) e comparado, célula a célula, com a segunda leitura (xpdf `pdftotext -table`) e, nas impressões do Siconfi, com a declaração estruturada do mesmo período.

| Exercício | Documento | Snapshot | Regra | Escopo | Corte | Células | Conferidas (xpdf) | Divergentes (xpdf) | Linhas sem segunda leitura | Diferenças de conteúdo com o Siconfi | Situação |
|---|---|---|---|---|---|---:|---:|---:|---|---:|---|
| 2016 | 6º Bimestre | 722468ea | rp-rreo-2016/1 | entidade | 2016-12-31 | 24 | 24 | 0 | — | 0 | validado |
| 2016 | 1º Bimestre | 31f6bf86 | rp-rreo-2016/1 | entidade | 2016-02-29 | 24 | 24 | 0 | — | 0 | validado |
| 2016 | 2º Bimestre | 9d38c530 | rp-rreo-2016/1 | entidade | 2016-04-30 | 24 | 24 | 0 | — | 0 | validado |
| 2016 | 3º Bimestre | ea623d30 | rp-rreo-2016/1 | entidade | 2016-06-30 | 24 | 24 | 0 | — | 0 | validado |
| 2016 | 4º Bimestre | b2684286 | rp-rreo-2016/1 | entidade | 2016-08-31 | 24 | 24 | 0 | — | 0 | validado |
| 2016 | 5º Bimestre | a93119d1 | rp-rreo-2016/1 | entidade | 2016-10-31 | 24 | 24 | 0 | — | 0 | validado |
| 2018 | 6º Bimestre | d369f5b9 | rp-rreo-siconfi/1 | consolidado | 2018-12-31 | 36 | 36 | 0 | — | 9 | validado |
| 2018 | 1º Bimestre | 77fd0254 | rp-rreo-siconfi/1 | consolidado | 2018-02-28 | 36 | 36 | 0 | — | 0 | validado |
| 2018 | 2º Bimestre | e37c512e | rp-rreo-siconfi/1 | consolidado | 2018-04-30 | 36 | 36 | 0 | — | 0 | validado |
| 2018 | 3º Bimestre | 08671224 | rp-rreo-siconfi/1 | consolidado | 2018-06-30 | 36 | 36 | 0 | — | 0 | validado |
| 2018 | 4º Bimestre | a353e1dd | rp-rreo-siconfi/1 | consolidado | 2018-08-31 | 36 | 36 | 0 | — | 0 | validado |
| 2018 | 5º Bimestre | 104ce0dc | rp-rreo-siconfi/1 | consolidado | 2018-10-31 | 36 | 36 | 0 | — | 0 | validado |
| 2019 | 6º BIMESTRE | 36f1ef8e | rp-rreo-siconfi/1 | consolidado | 2019-12-31 | 36 | 36 | 0 | — | 12 | validado |
| 2019 | 1º BIMESTRE | b218b702 | — | — | — | — | — | 0 | — | 0 | continua_recusado: período não encontrado na impressão do Siconfi |
| 2019 | 2º BIMESTRE | 49cc40f6 | rp-rreo-siconfi/1 | consolidado | 2019-04-30 | 36 | 36 | 0 | — | 11 | validado |
| 2019 | 4º BIMESTRE | ea117bf6 | rp-rreo-siconfi/1 | consolidado | 2019-08-31 | 36 | 36 | 0 | — | 12 | validado |
| 2019 | 5º BIMESTRE | 35dae607 | rp-rreo-siconfi/1 | consolidado | 2019-10-31 | 36 | 36 | 0 | — | 12 | validado |
| 2020 | 3º Bimestre 2020 Consolidado | c39d70b9 | — | — | — | — | — | 0 | — | 0 | continua_recusado: linha 'RESTOS A PAGAR (EXCETO' com 11 número(s); o layout conhecido tem 12 colunas: transcrição parcial recusada |
