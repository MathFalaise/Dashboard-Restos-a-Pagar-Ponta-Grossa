"""Basic accessibility and absence of external resources on every screen (sub-stage 05.7; read-only).

Usage (inside app/):  python ../docs/stages/05-analysis/results/05_7_acessibilidade.py SAIDA.json [--banco CAMINHO]

Through WSGI (no server), checks on each page:
  * <html lang="pt-BR">; exactly one <h1>; heading levels without jumps (h2 after h1, h3 after h2...);
  * unique ids; every visible <input> and every <select> inside a <label>;
  * every <table> with <thead> and every header <th> with scope="col"; every <a> with text; every <details> with <summary>;
  * every <svg> with role="img" and an accessible name (aria-label, or aria-labelledby with ids that exist on the page);
  * no style attribute, <style> or <script>;
  * no external href/src (http, https or //): the interface works without a network. Exception since 06/10/2026: an <a>
    link to the official portal (servicos.pontagrossa.pr.gov.br/portaltransparencia...), with rel="external" ('onde conferir').
"""
import argparse
import json
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ / "app"))

from rp.config import carregar  # noqa: E402
from rp.interface.aplicacao import Aplicacao  # noqa: E402
from rp.interface.portal import DOMINIO  # noqa: E402

PORTAL = DOMINIO + "/portaltransparencia"

PAGINAS = [
    ("/", {}), ("/", dict(exercicio=2026, data_final="2026-03-31")), ("/", dict(exercicio=2025, data_final="2025-12-31", entidade=15)),
    ("/resumo", {}), ("/resumo", dict(exercicio=2026, data_final="2026-03-31")),
    ("/resumo", dict(exercicio=2025, data_final="2025-12-31", entidade=15)),
    ("/evolucao", dict(exercicio=2026)), ("/evolucao", dict(exercicio=2026, entidade=15)),
    ("/historico", {}), ("/historico", dict(entidade=10)),
    *[("/composicao", dict(exercicio=2025, data_final="2025-12-31", dimensao=d)) for d in
      ("categoria", "faixa", "tipo_credor", "fonte_recurso", "orgao", "funcao", "programa", "elemento")],
    ("/composicao", dict(exercicio=2026, data_final="2026-03-31")),
    ("/variacao", dict(exercicio=2025, anterior="2025-10-31", data_final="2025-12-31")),
    ("/variacao", dict(exercicio=2026, anterior="2026-02-28", data_final="2026-04-30", metrica="pagamentos", pagina=2)),
    ("/variacao", dict(exercicio=2026, anterior="2026-01-31", data_final="2026-02-28")), ("/variacao", dict(exercicio=2024)),
    ("/empenho/cortes", dict(entidade=1, anoempenho=2025, empenho=5659, exercicio=2026)),
    ("/empenho/cortes", dict(entidade=15, anoempenho=2023, empenho=1751, exercicio=2026)),
    ("/qualidade", {}), ("/qualidade", dict(tipo="LIQ-NEG")), ("/qualidade", dict(tipo="CHAVE-DUP")),
    ("/entidades", dict(exercicio=2026, data_final="2026-08-31")),
    ("/empenhos", dict(exercicio=2026, data_final="2026-08-31")), ("/empenhos", dict(exercicio=2025, data_final="2025-12-31", faixa="g")),
    ("/empenhos", dict(exercicio=2026, data_final="2026-08-31", empenho=999999999)),
    ("/empenho", dict(entidade=1, anoempenho=2025, empenho=5659, exercicio=2026)),
    ("/retratos", {}), ("/retratos", dict(entidade=1, exercicio=2026, data_final="2026-08-31")),
    ("/reconciliacao", {}), ("/reconciliacao", dict(exercicio=2026, data_final="2026-08-31", escopo="entidade")),
    ("/pares", dict(exercicio=2026, data_final="2026-08-31")), ("/metodologia", {}),
    ("/empenhos", dict(empenho="abc")), ("/nao-existe", {}),
]
VAZIOS = {"input", "meta", "link", "br", "img", "hr"}


class Leitor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.pilha, self.problemas, self.ids, self.titulos, self.lang = [], [], Counter(), [], None
        self.links, self.tabelas, self.details, self.rotulados_por = [], [], [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang")
        if "style" in a:
            self.problemas.append(f"atributo style em <{tag}>")
        if tag in ("style", "script"):
            self.problemas.append(f"<{tag}>")
        for k in ("href", "src"):
            v = a.get(k) or ""
            # since 06/10/2026: only a link (never src) to the official portal, marked rel="external" ("onde conferir")
            portal = (k == "href" and tag == "a" and v.startswith(PORTAL) and "external" in (a.get("rel") or ""))
            if v.startswith(("http:", "https:", "//")) and not portal:
                self.problemas.append(f"recurso externo: {v}")
        if a.get("id"):
            self.ids[a["id"]] += 1
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.titulos.append(int(tag[1]))
        if tag in ("input", "select") and a.get("type") != "hidden" and "label" not in self.pilha:
            self.problemas.append(f"<{tag} name={a.get('name')}> sem <label>")
        if tag == "svg":
            if a.get("role") != "img" or not (a.get("aria-label") or a.get("aria-labelledby")):
                self.problemas.append("<svg> sem role=img e nome acessivel")
            self.rotulados_por += (a.get("aria-labelledby") or "").split()
        if tag == "table":
            self.tabelas.append({"thead": False, "th_sem_scope": 0})
        if tag == "thead" and self.tabelas:
            self.tabelas[-1]["thead"] = True
        if tag == "th" and self.tabelas and "thead" in self.pilha and a.get("scope") != "col":
            self.tabelas[-1]["th_sem_scope"] += 1
        if tag == "a":
            self.links.append({"texto": "", "aria": a.get("aria-label")})
        if tag == "details":
            self.details.append(False)
        if tag == "summary" and self.details:
            self.details[-1] = True
        if tag not in VAZIOS:
            self.pilha.append(tag)

    def handle_endtag(self, tag):
        if tag in self.pilha:
            while self.pilha and self.pilha.pop() != tag:
                pass

    def handle_data(self, data):
        if "a" in self.pilha and self.links and data.strip():
            self.links[-1]["texto"] += data.strip()


def conferir(html):
    l = Leitor()
    l.feed(html)
    p = list(l.problemas)
    if l.lang != "pt-BR":
        p.append(f"lang = {l.lang!r}")
    if l.titulos.count(1) != 1:
        p.append(f"{l.titulos.count(1)} <h1>")
    for antes, depois in zip(l.titulos, l.titulos[1:]):
        if depois > antes + 1:
            p.append(f"salto de titulo h{antes} -> h{depois}")
    p += [f"id repetido: {k} ({n}x)" for k, n in l.ids.items() if n > 1]
    p += [f"aria-labelledby aponta para id inexistente: {i}" for i in l.rotulados_por if i not in l.ids]
    p += ["<table> sem <thead>" for t in l.tabelas if not t["thead"]]
    p += [f"<th> sem scope=col ({t['th_sem_scope']})" for t in l.tabelas if t["th_sem_scope"]]
    p += ["<a> sem texto" for x in l.links if not (x["texto"] or x["aria"])]
    p += ["<details> sem <summary>" for d in l.details if not d]
    return p, {"titulos": l.titulos.count(1), "tabelas": len(l.tabelas), "links": len(l.links), "ids": len(l.ids)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("saida")
    ap.add_argument("--banco")
    a = ap.parse_args()
    app = Aplicacao(Path(a.banco) if a.banco else carregar().banco)
    saida = {"paginas": []}
    for caminho, q in PAGINAS:
        status = []
        corpo = b"".join(app({"REQUEST_METHOD": "GET", "PATH_INFO": caminho, "QUERY_STRING": urlencode(q)},
                             lambda s, h: status.append(s))).decode("utf-8")
        problemas, contagem = conferir(corpo)
        saida["paginas"].append({"caminho": caminho, "consulta": q, "status": status[0], "problemas": problemas, **contagem})
    saida["resumo"] = {"paginas": len(saida["paginas"]),
                       "paginas_com_problema": sum(1 for x in saida["paginas"] if x["problemas"])}
    Path(a.saida).write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(saida["resumo"], ensure_ascii=False))
    for x in saida["paginas"]:
        if x["problemas"]:
            print(x["caminho"], x["consulta"], x["status"], x["problemas"][:6])


if __name__ == "__main__":
    main()
