"""Official consolidated Municipality (SICONFI) x Executive from the Elotech source (/oficial). Corrective audit of
13/10/2026, item 5.1: the two scopes side by side, never mixed."""
from .. import formato as fm
from ..formato import esc

GRUPOS_OFICIAIS = [("inscricao", "Inscritos (a+b+f+g)"), ("pagos", "Pagos (c+i)"), ("cancelados", "Cancelados (d+j)"),
                   ("liquidados", "Liquidados (h)"), ("saldo", "Saldo (L)")]
LINHAS_OFICIAIS = [("I", "Consolidado oficial (I): todos os Poderes"), ("executivo", "Poder Executivo"),
                   ("legislativo", "Poder Legislativo (Câmara Municipal)")]


def oficial(p, q):
    em = q.data("em")
    exercicios = sorted({c["exercicio"] for c in p.cortes(em)["cortes"]}, reverse=True)
    ex = q.inteiro("exercicio", 1900, 2999) or (exercicios[0] if exercicios else None)
    titulo = "Consolidado oficial (Siconfi) e Poder Executivo (fonte Elotech)"
    form = (f'<form class="filtros" method="get" action="/oficial"><label>Exercício <select name="exercicio">'
            f'{fm.opcoes([(x, x) for x in exercicios], ex)}</select></label>'
            '<button type="submit">Consultar</button></form>')
    if ex is None:
        return titulo, f"<h1>{esc(titulo)}</h1>{form}<p>Nenhum corte processado.</p>"
    r = p.consolidado_oficial(ex, em=em)
    blocos = []
    for b in r["bimestres"]:
        dec, elo, dif, ent = b["declaracao"], b["executivo_elotech"], b["diferencas"], b["entrega"]
        cab = [("Linha", None)] + [(rot, "num") for _, rot in GRUPOS_OFICIAIS]
        linhas = []
        for chave, rotulo in LINHAS_OFICIAIS:
            v = (dec or {}).get("linhas", {}).get(chave)
            if v is None:
                continue
            linhas.append([esc(rotulo)] + [fm.valor(v[g], f"of-{ex}-{b['bimestre']}-{chave}-{g}",
                                                    ausencia="ausente na declaração") for g, _ in GRUPOS_OFICIAIS])
        if elo:
            linhas.append([esc("Poder Executivo — fonte Elotech (painel)") + (" <small>com ressalva</small>"
                                                                             if elo["com_ressalva"] else "")]
                          + [fm.valor(elo["valores"][g], f"of-{ex}-{b['bimestre']}-elotech-{g}") for g, _ in GRUPOS_OFICIAIS])
        if dif:
            linhas.append([esc("Diferença: Elotech − Siconfi (Poder Executivo)")]
                          + [fm.valor(dif[g], f"of-{ex}-{b['bimestre']}-dif-{g}", ausencia="não comparável")
                             for g, _ in GRUPOS_OFICIAIS])
        situacao = (f"declaração {esc(ent['situacao'])} em {esc(fm.data_br(ent['data_status'][:10]))}"
                    if ent and ent.get("data_status") else "situação da entrega não informada nesta leitura")
        origem = (f"<code>{esc(dec['arquivo'])}</code> (SHA-256 <code>{esc(dec['sha256'][:16])}…</code>)"
                  if dec else "sem declaração ao Siconfi para este bimestre")
        mudou = (f'<p class="aviso">Leituras anteriores com valores diferentes: {esc(", ".join(b["leituras_anteriores_diferentes"]))}'
                 "</p>") if b["leituras_anteriores_diferentes"] else ""
        sem_corte = "" if elo else f'<p class="nota">Sem corte processado da fonte Elotech em {esc(fm.data_br(b["data_final"]))}.</p>'
        blocos.append(f'<section class="grupo"><h2>{b["bimestre"]}º bimestre (corte {esc(fm.data_br(b["data_final"]))})</h2>'
                      f'<p class="fontes">{origem} · {situacao}</p>{mudou}{sem_corte}'
                      + (fm.tabela(cab, linhas) if linhas else "") + "</section>")
    corpo = (f"<h1>{esc(titulo)}</h1>{form}"
             f'<p class="nota">{esc(r["nota"])} Leitura usada: {esc(r.get("leitura") or "—")}.</p>' + "".join(blocos))
    return titulo, corpo
