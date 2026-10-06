# Revisão de código — segurança, correções, otimização e anotações (30/09/2026)

Revisão pedida fora do fluxo de subetapas; a 04.5 não foi iniciada.

## 1. Escopo

- **Revisado e alterado:**
  - `app/rp/` (pacote de produção, `esquema.sql`);
  - `app/config.toml` e `app/requirements.txt`;
  - `app/tests/`;
  - `app/README.md`;
  - scripts de `docs/stages/04-pipeline/batches/` e `docs/stages/04-pipeline/reconciliation/`.
- **Não alterado, de propósito:**
  - `docs/stages/02-accounting-validation/investigation` e `docs/stages/03-data-model/validation` — código de investigação de etapas aprovadas, que serve de referência na reconciliação investigação × produção. Conferido byte a byte: intocado.
  - Literais que são dado: definições de regra, descrições de verificação, rótulos do portal, mensagens já existentes. Eles entram no `hash_resultado` e em tabelas imutáveis, e alguns são exigidos pelos testes.
- **Cópia do código original**, fora do OneDrive: `C:\Users\maped\RestosAPagar_local\revisao_codigo\antes_20260930\` (mais a lista SHA-256 ao lado).

## 2. Anotações

- Todos os comentários e docstrings do escopo estão em ASCII, sem acento; o mesmo vale para os comentários de `esquema.sql` e de `config.toml`.
- A conversão foi feita por ferramenta (`revisao_codigo/anotacoes_ascii.py`). Ela só troca tokens de comentário e docstrings, e confere que a AST de cada arquivo fica idêntica.
- Duas anotações estavam **erradas**, não só acentuadas, e foram reescritas:
  - a da visão `snapshot_rp` citava uma visão inexistente e um uso em `consultas.py` que não existe;
  - uma do comparador, escrita nesta revisão.
- Mensagens novas foram escritas em ASCII.
- Os arquivos voltaram a ter fim de linha LF, como os originais. Cinco tinham virado CRLF por edições com `write_text` no Windows.

## 3. Segurança

| Onde | Antes | Agora |
|---|---|---|
| `config.py` | nenhuma validação | API só `https`, sem credencial/query/fragmento; números fora de faixa e `user_agent` com controle recusados |
| `http.py` | corpo lido inteiro, sem teto; redirecionamento seguido; `Retry-After` sem limite | corpo lido em blocos com teto (`limite_resposta_bytes`, 64 MiB) e prazo total (3 × timeout); 3xx não é seguido e vira falha registrada; `Retry-After` limitado a 300 s; caminho da API só com segmentos simples; recusa de segurança não é repetida |
| `armazem.py` | hash usado direto como caminho; descompressão sem teto; verificação "existe?" seguida de `replace` | hash validado (64 hex) antes de virar caminho; descompressão com teto; manifesto publicado de forma exclusiva (nunca sobrescreve); tipo, uid e data do manifesto validados; manifesto ilegível relatado |
| `banco.py` | integridade de objeto conferida com `assert` (some com `python -O`); backup no mesmo segundo sobrescrevia o anterior; `--motivo` entrava cru no nome do arquivo | conferência explícita; nome de backup nunca repete; motivo saneado; banco ativo recusado dentro do OneDrive |
| `coletor.py` | servidor que ignorasse `page` prendia a coleta em laço sem fim; `idArquivo` da resposta entrava na URL sem validação | para quando a soma passa de `totalElements` ou em 10.000 páginas; `idArquivo` só inteiro positivo |
| `cli.py` | `comparar --saida` sobrescrevia arquivo; erro de uso saía como traceback; saída redirecionada em cp1252 quebrava com "→" | saída exclusiva; erro de uso vira JSON com código 4; caractere não representável sai como `\uXXXX` |
| `requirements.txt` | versões mínimas (`>=`) | versões fixadas nas testadas |

## 4. Defeitos corrigidos

Os três primeiros foram reproduzidos no código original antes da correção.

1. **Comparador:** com chave repetida no snapshot, os valores derivados de uma ocorrência se perdiam. S1 dava 2.000 em vez de 3.000 no caso de teste.
2. **Exclusão de execução:** a derivação atual podia ser apagada sem `--permitir-mais-recente` quando existia uma derivação "como estava em" mais nova. É o caso do banco real: derivação 21 (atual) e 22 (29/09). Agora a mais recente de cada vigência é protegida.
3. **Backup:** dois backups com o mesmo motivo no mesmo segundo gravavam o mesmo arquivo; o segundo apagava o primeiro.
4. **Normalização:** um catálogo com corpo inválido abortava a normalização inteira. Agora é contado ou registrado em `problemas`.
5. **Saída da linha de comando e dos scripts:** a saída redirecionada para arquivo (cp1252, padrão do Python 3.14 no Windows) terminava em `UnicodeEncodeError` depois de o trabalho estar feito.

## 5. Otimização

A consulta de linhas por coleta passou a usar a chave primária (`resposta_id IN (...)`) em vez de varrer todos os registros da normalização a cada chamada. Além disso:

- cache de páginas do SQLite de 256 MiB por conexão;
- leitura só das colunas usadas;
- cache LRU pequeno entre continuidade, pareamento e visões;
- visões guardando só os componentes;
- inserções em lote;
- conversão de centavos sem ida e volta por texto.

| Medida (cópia do banco real, 228.873 registros) | Antes | Depois |
|---|--:|--:|
| Normalização | 6,8 s | 4,9 s |
| Derivação atual | 31,5 s | 4,7 s |
| Derivação "como estava em 29/09" | 4,9 s | 1,5 s |
| **Total** | **43,2 s** | **11,1 s** |
| Suíte de produção (mesmos 76 testes) | 88 s | 44 s |

## 6. Verificação

- **Hashes de resultado idênticos** no código novo, sobre cópia do banco real:
  - atual `2f6b4e295ce79593…`;
  - "como estava em 29/09" `b8a0b2ed2328bf09…`;
  - mesmas contagens: 536 respostas, 228.873 registros, 2.352 lançamentos, 1.529 valores de RREO, 3 problemas de extração.
- **Testes:** produção com **138 aprovados** (76 anteriores + 62 novos, em `tests/test_seguranca.py`); investigação da Etapa 03 com **26 aprovados**.
- **Reconciliação investigação × produção da 04.2**, rodada com o código novo, com saída fora do projeto para não sobrescrever a evidência: **ESPERADO == OBTIDO**.
- **Scripts de análise da 04.4:** saídas idênticas às gravadas. Uma exceção explicada: `hipotese_canc.py` ganhou as duas linhas de 2017, dado carregado no Lote F depois de o arquivo ter sido gerado.
- **Banco real intocado:**
  - hash da camada 0 `3fe902f65a54cfb4`, 466 coletas;
  - `verificar` sem problemas;
  - pasta de backups operacionais com os mesmos arquivos;
  - os 7 backups preservados continuam lá.
- As cópias do banco usadas na medição foram apagadas.

## 7. Pontos negativos do projeto

### Fonte de dados
1. Todo o projeto depende de uma API não documentada do portal Elotech, cujos endpoints, parâmetros e campos foram descobertos por inspeção, sem contrato nem versão do fornecedor.
2. A semântica dos campos foi inferida empiricamente; `canceladoProc` vem sempre 0 e sua finalidade é desconhecida.
3. A API devolve o estado atual da base contábil. Cortes históricos mudam retroativamente: há lançamentos com data no passado feitos depois, e cópias 24xxxxx inseridas depois aparecem em cortes antigos (2401751 aparece com 8.410,00 no corte de 2024). Uma consulta histórica feita hoje não mostra o que se sabia na época.
4. A listagem paginada não fixa ordenação (não há parâmetro `sort`). A consistência entre páginas depende da ordem padrão do servidor, e uma mudança da base durante a coleta que mantenha `totalElements` pode passar despercebida.
5. 145 dos 466 snapshots (os importados das Etapas 01/02) têm horário aproximado, tirado da data de modificação do arquivo. A consulta "como estava em" sobre eles herda essa aproximação.
6. O RREO só é coletado para a entidade 1 e para o consolidado. Nenhuma outra entidade tem conciliação individual.
7. De 2016 a 2024 só o 6º bimestre do RREO foi coletado.
8. A transcrição do RREO depende das coordenadas de texto de um layout específico. Os PDFs de 2016, 2018 e 2019 não são lidos pelo extrator de produção, e o de 2016 não foi lido nem pela leitura de investigação.
9. As conciliações de 2018 e 2019 existem só como saída de script de investigação, fora do banco.
10. O RREO consolidado (ex.: 2020) não detalha por órgão, e diferenças consolidadas não podem ser atribuídas a uma entidade.
11. Nenhum RREO fecha nas 12 colunas, exceto o de 2021 da entidade 1.
12. Diferenças sem causa determinada:
    - 674.426,01 (2024) sem registro atribuído;
    - reclassificação de 1.829,50 (2024 a 2026);
    - 3.972,66 entre (d) e (j) em 2024;
    - (d) −159.904,72 em 2022;
    - (h) +1.065.159,06 em 2017;
    - (f) −180.334,82 no consolidado de 2020;
    - (h)/(i) do 3º e 4º bimestres de 2026.
13. A natureza das 731 cópias 24xxxxx (duplicidade ou transferência) não está determinada. O pedido e-SIC existe no projeto só como rascunho, e nenhuma resposta foi incorporada.
14. A tabela `evidencia_externa` existe no esquema, mas nenhum comando grava nela; está vazia.
15. O teste temporal cobriu só cerca de 5 horas, de madrugada.
16. O comparador de snapshots nunca foi exercitado com mudança real: nenhum corte do banco tem retratos diferentes.

### Regras
17. RREO-COL v1 está marcada como estável, embora nunca concilie mais colunas que a v2 experimental e concilie menos em documentos de 2020, 2021, 2022 e 2025.
18. CANC v1, marcada como estável e "FORTE EVIDÊNCIA", diverge da divisão de cancelamentos dos RREOs consolidados de 2017 a 2021.
19. CONS-PAR v2 avalia "saldo final de B" na data do corte: o mesmo par muda de relação ao longo do ano, e a regra só reproduz 2025 em 31/12.
20. Nenhuma das duas CONS-PAR é validável pelo RREO: em 2026 o RREO conta os dois lados, e em 2025 as cópias não existiam quando os RREOs foram emitidos.
21. Constantes de negócio estão fixas no código e duplicadas em dois módulos: base 2.400.000 das cópias e entidades 1 e 15 como lados do par. A conciliação por entidade também é fixa na entidade 1.
22. A visão do Município exige snapshot de todas as entidades do catálogo atual, inclusive das que não existiam no exercício. Por isso foram consultadas combinações fora do catálogo que devolvem páginas vazias.
23. O catálogo de entidades usado é o mais recente, não o de cada exercício.

### Arquitetura e engenharia
24. O projeto não está sob controle de versão; o código vive numa pasta do OneDrive.
25. Existem duas implementações das mesmas regras (investigação da Etapa 03 e produção), e elas já divergem na escolha do snapshot de abertura da continuidade.
26. Todo processamento renormaliza todo o bruto; cada normalização duplica os cerca de 229 mil registros, e o tempo e o espaço crescem com o histórico.
27. Cada exclusão de execução grava um backup completo do banco (hoje cerca de 230 MB).
28. Os backups operacionais ocupam cerca de 1,47 GB, no mesmo disco do banco ativo.
29. Os backups não operacionais e o armazém de snapshots nunca são apagados e crescem sem limite.
30. Os testes de produção dependem dos arquivos brutos reais das Etapas 01/02 (com dados pessoais) e da estrutura de pastas do projeto.
31. Tudo foi executado só no Windows com Python 3.14:
    - o README declara Python 3.11+, sem teste nessas versões;
    - o ramo POSIX da publicação exclusiva de manifesto nunca rodou.
32. Não há integração contínua, lint, verificação de tipos nem configuração de pacote.
33. `pytest` não consta de `requirements.txt`, e as dependências fixadas não têm hash.
34. Os scripts de lote e de análise da `etapa04` ficam fora do pacote, não têm testes automatizados e usam funções internas do pacote (`_fechar`, `_lado_excluido`, `_pagina`).
35. Datas e horas são texto ISO comparado lexicograficamente, com deslocamento fixo −03:00.
36. A versão do PyMuPDF que produziu cada transcrição do RREO não é registrada junto dos valores extraídos.
37. A identidade do coletor (hash do código) muda com qualquer alteração de comentário.
38. Alguns limites de segurança são constantes no código: 300 s de `Retry-After`, 10.000 páginas e prazo total de 3 × o timeout. O prazo total só é conferido entre blocos recebidos.
39. A linha de comando trata `KeyError` como erro de uso (código 4), o que também engloba erro de programação.
40. A visão `snapshot_rp` do esquema não é usada pelo código.
41. `config.toml` aponta para caminho absoluto de uma máquina específica.
42. Os logs são um arquivo por dia, sem retenção.
43. Não há execução automática nem alerta: coleta, recoleta e detecção de falha dependem de alguém rodar os comandos e ler os relatórios.
44. O projeto ainda não tem interface, painel nem indicador, apesar do nome.

### Segurança e dados pessoais
45. Nomes e CNPJ/CPF de fornecedores ficam em texto claro, sem criptografia, no banco, no armazém, nos backups e nos dados brutos das etapas.
46. O armazém de snapshots, os backups não operacionais e os dados brutos das Etapas 01/02 ficam na pasta sincronizada pelo OneDrive, replicados no provedor de nuvem.
47. A integridade do bruto se apoia em SHA-256 guardado ao lado dos próprios dados, e a imutabilidade do banco em gatilhos. Quem tem escrita na pasta consegue alterar objeto e manifesto de forma coerente, ou remover os gatilhos.
48. A proteção contra banco ativo em pasta sincronizada reconhece só o OneDrive.
49. O PDF de terceiros é interpretado por biblioteca nativa (MuPDF) no mesmo processo do pipeline.
50. O PyMuPDF é licenciado sob AGPL-3.0 (ou licença comercial).
51. Textos gravados como dado têm acentos e símbolos fora do ASCII e fazem parte do hash de resultado e de tabelas imutáveis. São eles: definições de regra, descrições de verificação e mensagens.
52. O código de investigação das Etapas 02 e 03 mantém anotações com acento e não passou por esta revisão de segurança.
