"""Camada 1 - normalizacao: tipagem fiel do bruto, SEM interpretacao.

Garantias (portao da Etapa 04.2):
  * cada item de content[] vira exatamente uma linha, na posicao de origem (resposta, indice);
  * nada e descartado, fundido ou inventado; chave ausente fica registrada em `chaves_ausentes`;
  * dinheiro vira centavos; valor com mais de 2 casas decimais e ERRO (nunca arredondado);
  * resposta que nao e uma pagina valida (snapshot com falha) nao gera linhas e e contada;
  * catalogo (entidades/exercicios) com estrutura inesperada nao gera linhas e fica em `problemas`;
  * cada PDF de RREO deixa uma linha em rreo_extracao (extrator, versao do PyMuPDF/MuPDF, SHA-256, id do arquivo,
    data da extracao, quantos valores sairam ou o erro): os valores dependem do metodo, entao o metodo fica junto;
  * a execucao guarda a maior coleta que leu (ultima_coleta_id): snapshot com 0 registros tambem conta como
    processado, sem depender de ter gerado linhas;
  * a camada 0 e so lida.
"""
import json
import logging
import re
from datetime import date
from decimal import Decimal

from . import agora, banco

log = logging.getLogger("rp.normalizar")

VERSAO = "rp-normalizador/1"
EXTRATOR_RREO = "rp-rreo-coordenadas/1"

BASE = ["entidade", "empenho", "anoempenho", "empenhoExercicio", "cnpjNome", "dataEmissao", "programatica",
        "fonteRecurso", "descricaoFonte", "fornecedor", "nome", "cnpj", "proc", "aproc", "canceladoProc",
        "pagoProc", "pagoProcEstornado", "canceladoAProc", "pagoAProc", "pagoAProcEstornado", "retencao",
        "liquidado", "desdobraDesp", "subDesdobramento"]
OPCIONAIS = ["orgao", "unidade", "funcao", "subFuncao", "programa", "projeto", "elemento"]
CONHECIDAS = set(BASE) | set(OPCIONAIS)
ESPERADAS = BASE + OPCIONAIS
DINHEIRO = ["proc", "aproc", "canceladoProc", "pagoProc", "pagoProcEstornado", "canceladoAProc",
            "pagoAProc", "pagoAProcEstornado", "liquidado", "retencao"]

SQL_RP = "INSERT INTO rp_registro VALUES (" + ",".join("?" * 37) + ")"
SQL_MOV = "INSERT INTO movimentacao_lancamento VALUES (" + ",".join("?" * 18) + ")"
SQL_RREO = "INSERT OR IGNORE INTO rreo_valor VALUES (?,?,?,?,?,?,?,?,?,?)"
SQL_EXTRACAO = ("INSERT INTO rreo_extracao (normalizacao_id, resposta_id, coleta_id, extrator_versao, biblioteca, "
                "biblioteca_versao, sha256_pdf, id_arquivo, rotulo, extraida_em, valores, erro) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)")

_CENTAVO = Decimal("0.01")
_INT_SEGURO = 10 ** 20   # nesta faixa um inteiro cabe na precisao do Decimal (28 digitos) com 2 casas


class ValorNaoRepresentavel(ValueError):
    pass


def centavos(v):
    if v is None:
        return None
    if type(v) is int and -_INT_SEGURO < v < _INT_SEGURO:
        return v * 100                                   # mesmo resultado do caminho Decimal, sem conversao
    d = v if type(v) is Decimal else Decimal(str(v))     # Decimal(str(d)) == d para todo Decimal
    q = d.quantize(_CENTAVO)
    if q != d:
        raise ValorNaoRepresentavel(f"{v!r} tem mais de 2 casas decimais")
    return int(q * 100)


def _pagina(corpo):
    try:
        d = json.loads(corpo, parse_float=Decimal)
        return d["content"] if isinstance(d, dict) and isinstance(d.get("content"), list) else None
    except (ValueError, RecursionError):
        return None


def _lista_json(corpo):
    """Lista de objetos JSON, ou None se o corpo nao for isso."""
    try:
        d = json.loads(corpo)
    except (ValueError, RecursionError):
        return None
    return d if isinstance(d, list) and all(isinstance(x, dict) for x in d) else None


def normalizar(con):
    """Nova execucao de normalizacao sobre todo o bruto. Devolve (id, resumo)."""
    resumo = {"respostas": 0, "ignoradas_sem_pagina": 0, "rp_registro": 0, "movimentacao_lancamento": 0,
              "rreo_valor": 0, "problemas": []}
    with con:
        ultima = con.execute("SELECT IFNULL(MAX(id), 0) FROM coleta").fetchone()[0]
        nid = con.execute("INSERT INTO normalizacao_execucao (normalizador_versao, executada_em, ultima_coleta_id) "
                          "VALUES (?,?,?)", (VERSAO, agora(), ultima)).lastrowid
        itens = con.execute("SELECT r.id, r.coleta_id, c.tipo, r.sha256, c.parametros_json, c.entidade, c.anoempenho, "
                            "c.empenho FROM resposta_bruta r JOIN coleta c ON c.id = r.coleta_id WHERE c.id <= ? "
                            "ORDER BY c.coletada_em, c.snapshot_uid, r.ordem", (ultima,)).fetchall()
        for rid, cid, tipo, sha, params, ent, ano, emp in itens:
            resumo["respostas"] += 1
            corpo = banco.corpo(con, sha)
            if tipo == "rp_listagem":
                conteudo = _pagina(corpo)
                if conteudo is None:
                    resumo["ignoradas_sem_pagina"] += 1
                    continue
                con.executemany(SQL_RP, (_linha_rp(nid, rid, i, cid, r) for i, r in enumerate(conteudo)))
                resumo["rp_registro"] += len(conteudo)
            elif tipo == "movimentacao":
                conteudo = _pagina(corpo)
                if conteudo is None:
                    resumo["ignoradas_sem_pagina"] += 1
                    continue
                con.executemany(SQL_MOV, (_linha_mov(nid, rid, i, cid, ent, ano, emp, m) for i, m in enumerate(conteudo)))
                resumo["movimentacao_lancamento"] += len(conteudo)
            elif tipo == "rreo_pdf":
                if corpo[:4] != b"%PDF":
                    resumo["ignoradas_sem_pagina"] += 1
                    continue
                meta = json.loads(params)
                try:
                    n, erro = _rreo(con, nid, cid, meta, corpo), None
                    resumo["rreo_valor"] += n
                except Exception as e:  # layout novo nao derruba o processamento; fica registrado
                    n, erro = 0, f"{type(e).__name__}: {e}"
                    resumo["problemas"].append({"coleta_id": cid, "extrator": EXTRATOR_RREO, "erro": erro})
                    log.warning("RREO da coleta %d não transcrito: %s", cid, e)
                con.execute(SQL_EXTRACAO, (nid, rid, cid, EXTRATOR_RREO, "PyMuPDF/MuPDF", _versao_biblioteca_pdf(), sha,
                                           meta.get("id_arquivo"), meta.get("rotulo"), agora(), n, erro))
            elif tipo in ("entidades", "exercicios"):
                lista = _lista_json(corpo)
                if lista is None:
                    resumo["ignoradas_sem_pagina"] += 1
                    continue
                try:
                    if tipo == "entidades":
                        linhas = [(nid, cid, e["id"], e.get("nome"), e.get("cnpj"), e.get("tipo")) for e in lista]
                        sql = "INSERT INTO entidade_ref VALUES (?,?,?,?,?,?)"
                    else:
                        linhas = [(nid, cid, x["id"]["entidade"]["id"], x["id"]["exercicio"],
                                   int(bool(x.get("aberto"))), int(bool(x.get("fechado")))) for x in lista]
                        sql = "INSERT INTO exercicio_ref VALUES (?,?,?,?,?,?)"
                except (KeyError, TypeError) as e:  # estrutura inesperada: nenhuma linha, problema registrado
                    resumo["problemas"].append({"coleta_id": cid, "catalogo": tipo, "erro": f"{type(e).__name__}: {e}"})
                    log.warning("catalogo %s da coleta %d nao normalizado: %r", tipo, cid, e)
                    continue
                con.executemany(sql, linhas)
        if resumo["problemas"]:
            con.execute("UPDATE normalizacao_execucao SET observacao=? WHERE id=?",
                        (json.dumps({"problemas": resumo["problemas"]}, ensure_ascii=False), nid))
    log.info("normalização %d: %s", nid, resumo)
    return nid, resumo


def _linha_rp(nid, rid, i, cid, r):
    ausentes = [k for k in ESPERADAS if k not in r]
    extras = sorted(k for k in r if k not in CONHECIDAS)
    return (nid, rid, i, cid, r.get("entidade"), r.get("anoempenho"), r.get("empenho"), r.get("empenhoExercicio"),
            r.get("dataEmissao"), r.get("programatica"), r.get("fonteRecurso"), r.get("descricaoFonte"),
            r.get("fornecedor"), r.get("nome"), r.get("cnpj"), r.get("cnpjNome"),
            *[centavos(r.get(c, 0)) for c in DINHEIRO],
            r.get("orgao"), r.get("unidade"), r.get("funcao"), r.get("subFuncao"), r.get("programa"),
            r.get("projeto"), r.get("elemento"), r.get("desdobraDesp"), r.get("subDesdobramento"),
            json.dumps(ausentes), json.dumps(extras))


def _linha_mov(nid, rid, i, cid, ent, ano, emp, m):
    return (nid, rid, i, cid, ent, ano, emp, m["data"], m["tipoLancamento"], (m.get("descricaoTipoLancamento") or "").strip(),
            centavos(m["valor"]), centavos(m.get("valorALiquidar")), centavos(m.get("valorAPagar")),
            m.get("exercicioLiquidacao"), m.get("noLiquidacao"), m.get("exercicioPagamento"), m.get("noPagamento"),
            m.get("nroDocumento"))


# --- transcricao do RREO Anexo VII (PDF de 1 pagina, layout Elotech) ------
NUM = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d{2}$")
ROTULOS = {"(a)": "a", "(b)": "b", "(c)": "c", "(d)": "d", "e=(a+b)": "e", "(f)": "f", "(g)": "g",
           "(h)": "h", "(i)": "i", "(j)": "j", "k=(f+g)": "k", "L=(e+k)": "L"}
MESES = {"JANEIRO": 1, "FEVEREIRO": 2, "MARÇO": 3, "ABRIL": 4, "MAIO": 5, "JUNHO": 6, "JULHO": 7,
         "AGOSTO": 8, "SETEMBRO": 9, "OUTUBRO": 10, "NOVEMBRO": 11, "DEZEMBRO": 12}
LINHAS = ("RESTOS A PAGAR (EXCETO", "PODER EXECUTIVO", "RESTOS A PAGAR (INTRA", "TOTAL (III)")


class LayoutDesconhecido(ValueError):
    pass


def _versao_biblioteca_pdf():
    """Versao do PyMuPDF e do MuPDF que fizeram a transcricao (os valores dependem delas)."""
    try:
        import pymupdf
    except ImportError:  # versoes antigas so expoem `fitz`
        import fitz as pymupdf
    return f"PyMuPDF {getattr(pymupdf, 'VersionBind', '?')} / MuPDF {getattr(pymupdf, 'VersionFitz', '?')}"


def _abrir_pdf(corpo):
    """Documento PDF (usar com `with`, para liberar o documento depois da leitura)."""
    try:
        import pymupdf
    except ImportError:  # versoes antigas so expoem `fitz`
        import fitz as pymupdf
    return pymupdf.open(stream=corpo, filetype="pdf")


def _rreo(con, nid, cid, params, corpo):
    with _abrir_pdf(corpo) as doc:
        pg = doc[0]
        texto = pg.get_text()
        palavras = pg.get_text("words")
    m = re.search(r"JANEIRO A ([A-ZÇ]+) (\d)\.(\d{3})", texto)
    if not m:
        raise LayoutDesconhecido(f"período não encontrado no RREO (coleta {cid})")
    mes, ano = MESES[m.group(1)], int(m.group(2) + m.group(3))
    data_final = date.fromordinal(date(ano + (mes == 12), mes % 12 + 1, 1).toordinal() - 1).isoformat()
    em = re.search(r"emitido em (\d+/\w+/\d{4}) as (\d+)h e (\d+)m", texto)
    emitido = f"{em.group(1)} {em.group(2)}:{em.group(3)}" if em else None
    escopo = "consolidado" if "Consolidado" in params.get("rotulo", "") else "entidade"
    cols = {}
    for x0, y0, x1, y1, w, *_ in palavras:
        for r, c in ROTULOS.items():
            if w.startswith(r) and c not in cols:
                cols[c] = (x0 + x1) / 2
    if set(cols) != set(ROTULOS.values()):
        raise LayoutDesconhecido(f"colunas não encontradas no RREO: {set(ROTULOS.values()) - set(cols)}")
    linhas = {}
    for x0, y0, x1, y1, w, *_ in palavras:
        if NUM.match(w):
            y = next((k for k in linhas if abs(k - y0) < 2.5), y0)
            linhas.setdefault(y, []).append(((x0 + x1) / 2, w))
    rotulo = {}
    for x0, y0, x1, y1, w, *_ in palavras:
        if x0 < 200 and not NUM.match(w):
            y = next((k for k in linhas if abs(k - y0) < 2.5), None)
            if y is not None:
                rotulo.setdefault(y, []).append(w)
    valores = []
    for y, vals in linhas.items():
        nome = " ".join(rotulo.get(y, []))
        linha = next((l for l in LINHAS if nome.startswith(l)), None)
        if not linha:
            continue
        vistos = {}
        for xc, w in vals:
            vistos.setdefault(min(cols, key=lambda k: abs(cols[k] - xc)), w)
        for c, w in vistos.items():
            valores.append((nid, cid, EXTRATOR_RREO, escopo, ano, data_final, emitido, linha, c,
                            int(Decimal(w.replace(".", "").replace(",", ".")) * 100)))
    return con.executemany(SQL_RREO, valores).rowcount if valores else 0
