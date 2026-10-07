"""Snapshots of a cut-off (/retratos) and snapshot comparison (/comparar)."""
from .. import formato as fm
from ..formato import esc
from .estrutura import erro


def retratos(p, q):
    entidade, exercicio, df = q.inteiro("entidade", 1, 10 ** 6), q.inteiro("exercicio", 1900, 2999), q.data("data_final")
    if None in (entidade, exercicio, df):
        itens = "".join("<li>" + fm.link("/retratos", f"entidade {x['entidade']} — exercício {x['exercicio']}, corte "
                                                      f"{fm.data_br(x['data_final'])}: {x['retratos']} retratos",
                                          entidade=x["entidade"], exercicio=x["exercicio"], data_final=x["data_final"])
                        + "</li>" for x in p.retratos_multiplos())
        return "Retratos", ("<h1>Retratos</h1><p>Cada coleta de um corte é um retrato independente e nenhum é apagado. "
                            "Cortes com mais de um retrato:</p>" + (f"<ul>{itens}</ul>" if itens else "<p>nenhum.</p>"))
    r = p.retratos(entidade, exercicio, df)
    titulo = f"Retratos — entidade {entidade}, exercício {exercicio}, corte {fm.data_br(df)}"
    linhas = []
    for x in r["retratos"]:
        v, dif = x["valores"], x["diferenca_para_o_anterior"]
        comparar = "—"
        if dif:
            comparar = fm.link("/comparar", "comparar com o anterior", a=dif["anterior"], b=x["snapshot_uid"])
        linhas.append([f"<code>{esc(x['snapshot_uid'])}</code>", esc(fm.data_br(x["coletada_em"], True)),
                       esc(x["origem_carimbo"]), esc(x["status"]), "sim" if x["processado"] else "não",
                       fm.contagem(x["registros"], ausencia="—"),
                       fm.valor(v["inscricao_total_c"]) if v else "—", fm.valor(v["saldo_total_c"]) if v else "—",
                       (fm.valor(dif["saldo_total_c"]) + f" ({esc(dif['registros'])} registros)") if dif else "—",
                       ("sim" if dif["bytes_identicos"] else "não") if dif else "—",
                       "vigente" if x["vigente"] else "", comparar])
    tabela = fm.tabela([("Snapshot", None), ("Coletado em", None), ("Carimbo", "origem do horário"), ("Status", None),
                        ("Processado", None), ("Registros", None), ("Total inscrito", "proc + aproc"),
                        ("Saldo (S1)", "S1 v1"), ("Diferença de saldo para o anterior", None),
                        ("Bytes idênticos ao anterior", None), ("", None), ("", None)], linhas)
    return titulo, (f"<h1>{esc(titulo)}</h1><p>{esc(r['nota'])}</p>"
                    + fm.selo("elotech", "derivado", [{"codigo": "S1", "versao": 1, "situacao": "operacional"}],
                              "somas por retrato; diferença = retrato − anterior")
                    + tabela)


def comparar(p, q):
    a, b = q.snapshot("a"), q.snapshot("b")
    if not a or not b:
        return erro("Comparar retratos", "Informe os dois snapshots (a e b).")
    r = p.comparar_retratos(a, b)
    titulo = "Comparação de dois retratos do mesmo corte"
    c = r["contagens"]
    grupos = [[esc(g), fm.valor(v["antes"]), fm.valor(v["depois"]), fm.valor(v["diferenca"])]
              for g, v in r["impacto_financeiro_por_grupo"].items()]
    alterados = [[esc("/".join(str(x) for x in alt["chave"])),
                  esc("; ".join(f"{x['campo']}: {x['antes']} → {x['depois']}" for x in alt["campos"]))]
                 for alt in r["alterados"][:50]]
    corpo = (f"<h1>{esc(titulo)}</h1>" + fm.selo("elotech", "diferenca")
             + fm.lista_definicoes([
                 ("Corte", esc(f"entidade {r['corte']['entidade']}, exercício {r['corte']['exercicio']}, "
                               f"{fm.data_br(r['corte']['data_inicial'])} a {fm.data_br(r['corte']['data_final'])}")),
                 ("Anterior", f"<code>{esc(r['anterior']['snapshot_uid'])}</code> — {esc(fm.data_br(r['anterior']['coletada_em'], True))}, "
                              f"{esc(r['anterior']['registros'])} registros"),
                 ("Posterior", f"<code>{esc(r['posterior']['snapshot_uid'])}</code> — {esc(fm.data_br(r['posterior']['coletada_em'], True))}, "
                               f"{esc(r['posterior']['registros'])} registros"),
                 ("Bytes idênticos", "sim" if r["bytes_identicos"] else "não"),
                 ("Registros", esc(f"{c['novos']} novos, {c['removidos']} removidos, {c['alterados']} alterados, "
                                   f"{c['comuns']} em comum")),
                 ("Saldo S1", f"{fm.valor(r['saldo_s1']['antes'])} → {fm.valor(r['saldo_s1']['depois'])} "
                              f"(diferença {fm.valor(r['saldo_s1']['diferenca'])})")])
             + "<h2>Impacto por grupo</h2>"
             + fm.tabela([("Grupo", None), ("Antes", None), ("Depois", None), ("Diferença", None)], grupos)
             + ("<h2>Registros alterados (até 50)</h2>" + fm.tabela([("Chave", None), ("Campos", None)], alterados)
                if alterados else "<p>Nenhum registro alterado.</p>")
             + '<p class="nota">A comparação relata fatos, não causas. Campos do credor aparecem como [restrito].</p>')
    return titulo, corpo
