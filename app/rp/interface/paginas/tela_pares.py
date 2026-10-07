"""Technical screen: mirrored pairs (/pares)."""
from .. import formato as fm
from ..formato import esc
from .estrutura import _avisos, erro, _formulario, _origem_conjunto, _selecao, SemDados


def pares(p, q):
    try:
        sel = _selecao(p, q, com_entidade=False)
    except SemDados as e:
        return erro("Sem dados processados", str(e))
    titulo = f"Técnico: pares espelhados — exercício {sel['exercicio']}, corte {fm.data_br(sel['data_final'])}"
    if not sel["corte_processado"]:   # without a snapshot at the cut-off, "0 pares" would be absence shown as zero
        return titulo, (f"<h1>{esc(titulo)}</h1>{_avisos(sel['avisos'])}" + _formulario("/pares", sel)
                        + '<section class="indisponivel" id="indisponivel"><h2>Dados indisponíveis para este corte</h2>'
                          "<p>Corte não processado: não há registros para identificar pares. Nenhuma contagem é "
                          "mostrada: ausência de dado não é zero.</p></section>")
    r = p.pares(sel["exercicio"], sel["data_final"], sel["em"])
    res = r.get("resumo", {})
    resumo_html = fm.lista_definicoes([
        ("Pares", fm.contagem(res.get("pares", 0), "pares-total")),
        ("Relação da inscrição", esc(", ".join(f"{k}: {v}" for k, v in sorted(res.get("relacao", {}).items())) or "—")),
        ("Lado com execução", esc(", ".join(f"{k}: {v}" for k, v in sorted(res.get("lado_com_execucao", {}).items())) or "—")),
        ("Ano do empenho (cópia)", esc(", ".join(f"{k}: {v}" for k, v in sorted(res.get("anoempenho", {}).items())) or "—")),
    ])
    linhas = [[esc(f"{x['a']['entidade']} / {x['a']['empenho']}/{x['a']['anoempenho']}"), fm.valor(x["a"]["inscrito_c"]),
               esc(f"{x['b']['entidade']} / {x['b']['empenho']}/{x['b']['anoempenho']}"), fm.valor(x["b"]["inscrito_c"]),
               "sim" if x["mesma_inscricao"] else "não", esc(x["relacao_inscricao"]), esc(x["lado_com_execucao"])]
              for x in r.get("pares", [])[:500]]
    corpo = (f"<h1>{esc(titulo)}</h1>" + _formulario("/pares", sel)
             + '<p class="aviso">Área técnica. Identificação de pares pela regra PAR-24 v1 (operacional): não é '
               "consolidação. Os dois lados continuam nos indicadores, como a API os devolve. A natureza das cópias "
               "(duplicidade ou transferência) não está determinada. As visões analíticas CONS-PAR (experimentais) "
               "não são exibidas nesta interface.</p>"
             + fm.selo("elotech", "derivado", [{"codigo": "PAR-24", "versao": 1, "situacao": "operacional"}],
                       "identificação por regra; nenhum valor é alterado")
             + resumo_html + (_origem_conjunto(r["proveniencia"]) if r.get("proveniencia") else "")
             + fm.tabela([("Lado A (entidade / empenho)", None), ("Inscrito A", None), ("Lado B (entidade / empenho)", None),
                          ("Inscrito B", None), ("Mesma inscrição", None), ("Relação", None), ("Execução", None)], linhas))
    return titulo, corpo
