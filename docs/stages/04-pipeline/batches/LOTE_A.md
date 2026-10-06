# Lote A — 2024 — entidades 1 e 15 (teste das regras experimentais)

Início 2026-09-30T00:43:19 · fim 2026-09-30T00:46:03 · requisições 7 · **CONCLUÍDO**

- **Exercícios:** [2024]  ·  **Entidades:** [1, 15]
- **Snapshots:** 5 (Counter({'rp_listagem': 2, 'rreo_pdf': 2, 'publicacoes': 1}))
- **Registros normalizados do lote:** 6004
- **Tamanho bruto:** 4.585.086 bytes (491.306 comprimidos)
- **Hashes de resultado:** atual `246cfa5a53d96586` · como estava em 29/09 `b8a0b2ed2328bf09`

## Portões

| Portão | Resultado | Detalhe |
|---|---|---|
| G1 coleta completa | OK | {'completa': 5} |
| G2 integridade armazém×banco (após coleta) | OK | [] |
| G3 fidelidade (registros = bruto; sem chave desconhecida; chaves-base presentes) | OK | {'esperado': 6004, 'obtido': 6004, 'com_chaves_extras': 0, 'chaves_base_faltando': []} |
| G4 continuidade fechamento→abertura | OK | 12 pares entidade×ano, 0 falhas |
| G5 regressão temporal ('como estava em 29/09' inalterado) | OK | {'referencia': 'b8a0b2ed2328bf09', 'obtido': 'b8a0b2ed2328bf09'} |
| G6 sem efeito colateral em cortes não tocados pelo lote | OK | {'alteradas_fora_do_lote': 0, 'sumidas': 0} |
| G7 testes (produção + investigação) | OK | 75 passed in 85.44s (0:01:25) | 26 passed in 17.92s |
| G2b integridade armazém×banco (após processamento) | OK |  |
| G8 sem anomalia estrutural | OK | {} |
| G2c integridade após limpeza | OK |  |

Testes: produção `75 passed in 85.44s (0:01:25)`; investigação `26 passed in 17.92s`.

## Anomalias do lote

{'COPIA-24': 1, 'LIQ-NEG': 201, 'PAGOPROC-SEM-PROC': 1, 'PAR-INSCRICAO-DIVERGENTE': 1}

## Perfil por exercício (comparar com 2025/2026: programática de 28 dígitos, fontes de 3–4 dígitos)

- 2024: {'registros': 6004, 'programatica_28_dig': 6004, 'sem_programatica_detalhada': 18, 'fonte_3_dig': 3079, 'fonte_4_dig': 2781, 'fonte_2_dig': 140, 'fonte_6_dig': 1, 'fonte_5_dig': 3}

## Pares espelhados nos cortes do lote

| Corte | Relação | Execução | Pares | Inscrito A | Inscrito B | Exec. A | Exec. B |
|---|---|---|--:|--:|--:|--:|--:|
| 2024 até 2024-12-31 | outra | B | 1 | 8.410,00 | 19.750,00 | 0,00 | 18.720,00 |

## Conciliação com o RREO (colunas com diferença ≠ 0)

| Exercício | Corte | Escopo | RREO-COL | Coluna | RREO | API | Diferença |
|---|---|---|---|---|--:|--:|--:|
| 2024 | 2024-12-31 | entidade | v1 | (L) | 17.848.930,28 | 18.595.245,38 | 746.315,10 |
| 2024 | 2024-12-31 | entidade | v1 | (a) | 3.454.257,49 | 3.456.086,99 | 1.829,50 |
| 2024 | 2024-12-31 | entidade | v1 | (c) | 12.502.764,37 | 12.389.582,48 | -113.181,89 |
| 2024 | 2024-12-31 | entidade | v1 | (d) | 1.668.539,64 | 2.184.294,30 | 515.754,66 |
| 2024 | 2024-12-31 | entidade | v1 | (e) | 1.887.397,33 | 1.486.654,06 | -400.743,27 |
| 2024 | 2024-12-31 | entidade | v1 | (f) | 17.010.919,52 | 17.006.138,54 | -4.780,98 |
| 2024 | 2024-12-31 | entidade | v1 | (g) | 99.828.227,26 | 99.836.637,26 | 8.410,00 |
| 2024 | 2024-12-31 | entidade | v1 | (h) | 87.184.186,89 | 87.187.138,37 | 2.951,48 |
| 2024 | 2024-12-31 | entidade | v1 | (i) | 87.064.986,41 | 85.925.529,72 | -1.139.456,69 |
| 2024 | 2024-12-31 | entidade | v1 | (j) | 13.812.627,42 | 13.808.654,76 | -3.972,66 |
| 2024 | 2024-12-31 | entidade | v1 | (k) | 15.961.532,95 | 17.108.591,32 | 1.147.058,37 |
| 2024 | 2024-12-31 | entidade | v2 | (L) | 17.848.930,28 | 18.531.766,29 | 682.836,01 |
| 2024 | 2024-12-31 | entidade | v2 | (a) | 3.454.257,49 | 3.456.086,99 | 1.829,50 |
| 2024 | 2024-12-31 | entidade | v2 | (c) | 12.502.764,37 | 12.452.995,57 | -49.768,80 |
| 2024 | 2024-12-31 | entidade | v2 | (d) | 1.668.539,64 | 2.184.294,30 | 515.754,66 |
| 2024 | 2024-12-31 | entidade | v2 | (e) | 1.887.397,33 | 1.423.240,97 | -464.156,36 |
| 2024 | 2024-12-31 | entidade | v2 | (f) | 17.010.919,52 | 17.006.138,54 | -4.780,98 |
| 2024 | 2024-12-31 | entidade | v2 | (g) | 99.828.227,26 | 99.836.637,26 | 8.410,00 |
| 2024 | 2024-12-31 | entidade | v2 | (h) | 87.184.186,89 | 87.187.138,37 | 2.951,48 |
| 2024 | 2024-12-31 | entidade | v2 | (i) | 87.064.986,41 | 85.925.595,72 | -1.139.390,69 |
| 2024 | 2024-12-31 | entidade | v2 | (j) | 13.812.627,42 | 13.808.654,76 | -3.972,66 |
| 2024 | 2024-12-31 | entidade | v2 | (k) | 15.961.532,95 | 17.108.525,32 | 1.146.992,37 |

Conciliações com TODAS as colunas iguais: nenhuma

## Análise do lote (escrita depois dos portões; nada foi alterado para "fechar")

**Todos os portões passaram.** O RREO de 2024 (entidade 1, 6º bim, emitido 30/jan/2025) **não** é reproduzido pela API — nem em v1 nem em v2. A diferença foi decomposta; nada foi forçado.

### 1. As duas publicações oficiais divergem entre si

| Valor | RREO 2024 L (fechamento) | RREO 2025 (a)+(f) (abertura dos mesmos RP) | API 2024 L em v2 (= ΣS1) |
|---|--:|--:|--:|
| Saldo dos RP de 2023 e anteriores | 17.848.930,28 | 18.523.356,29 | 18.531.766,29 |

- Os dois RREOs deveriam coincidir (o saldo que fecha 2024 é o que abre 2025 como "exercícios anteriores"). **Divergem em 674.426,01.**
- A API atual reproduz a abertura publicada de 2025, menos 8.410,00 (item 2). Ou seja: a API mostra o estado **posterior** a 30/jan/2025, não o estado em que o RREO de 2024 foi emitido.
- Classificação: **diferença temporal entre publicações** (FORTE EVIDÊNCIA no agregado). Registros responsáveis pelo total: **NÃO DETERMINADO** — sem um retrato da API anterior a 2025 não há como saber o que mudou.

### 2. Cópia 24xxxxx: (g) +8.410,00

- É exatamente a inscrição de 2401751/2023 (entidade 1), cópia de 1751/2023 (entidade 15).
- Relação do par em 2024: **"outra"** (A inscreve 8.410,00; B inscreve 19.750,00 e executou 9.360,00). Nenhuma versão de CONS-PAR consolida esse par.
- A mesma cópia também está fora da abertura publicada de 2025. É coerente com a hipótese da Etapa 02 (cópias inseridas depois das publicações) e mostra que essa inserção aparece **retroativamente** nas listagens históricas.

### 3. Cancelamentos: (d)+(j) +511.782,00

- É exatamente um registro: **2023/9459 (entidade 1)** — proc 511.782,00, liquidação estornada (−511.782,00) e cancelado em 2024 segundo a API.
- O RREO de 2024 não tem esse cancelamento. HIPÓTESE: registrado depois da emissão; a data do lançamento pode ser conferida na movimentação.
- Dentro dos cancelamentos, (d) +515.754,66 e (j) −3.972,66: reclassificação de 3.972,66 entre processado e não processado, registros **NÃO DETERMINADOS**.

### 4. Pagamentos: (c)+(i) −1.189.159,49 em v2 (−1.252.638,58 em v1)

- Somados ao item 3 e às inscrições, fecham os 674.426,01 do item 1.
- 124 registros têm estorno de pagamento dentro de 2024 (3,54 milhões). Qualquer subconjunto pode ter sido estornado depois da emissão. **NÃO DETERMINADO.**

### 5. Reclassificações pequenas

- (a) +1.829,50: o mesmo valor da reclassificação de 2025 (Etapa 02 §7). Registro não achado — NÃO DETERMINADO.
- (f) −4.780,98 e (h) +2.951,48: 2.951,48 é exatamente 2011/21040 (processado com liquidação estornada e cancelado). **Candidato**, não confirmado.

### Regras experimentais: a confiança mudou?

| Regra | Efeito em 2024 | Confiança |
|---|---|---|
| CONS-PAR v1 | nenhum (o único par é "outra") | **inalterada** — 2024 não discrimina |
| CONS-PAR v2 | nenhum (idem) | **inalterada**; o RREO exclui a cópia de um par "outra", caso que nenhuma das duas cobre |
| RREO-COL v1 | L = 18.595.245,38, que não é saldo: excede ΣS1 em 63.479,09 (pagamentos que v1 descarta) | **diminuiu** |
| RREO-COL v2 | L = ΣS1 = abertura oficial de 2025 + cópia, ao centavo; (c) mais perto do RREO | **aumentou moderadamente** na parte "L = ΣS1"; "pagamento segue a categoria" não pôde ser isolado da diferença temporal |

Nenhuma regra foi promovida. Os snapshots de 2024 ficam preservados como estão.
