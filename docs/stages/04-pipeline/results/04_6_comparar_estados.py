"""Compara 04_6_estado_antes.json e 04_6_estado_depois.json (secao 29 da especificacao da 04.6).

Uso:  python 04_6_comparar_estados.py ANTES.json DEPOIS.json SAIDA.json
Separa: (1) bruto, armazem e derivacoes (precisam ser identicos); (2) VALORES numericos da camada painel e da tela
(precisam ser identicos); (3) textos (motivos, rotulos), listados um a um para conferencia.
"""
import json
import sys

antes, depois = (json.load(open(a, encoding="utf-8")) for a in sys.argv[1:3])
r = {"identicos": {}, "valores_painel_diferentes": [], "textos_painel_diferentes": [], "valores_tela_diferentes": [],
     "ids_de_tela_novos": {}, "ids_de_tela_removidos": {}}
for k in ("integrity_check", "hash_camada0", "bruto", "contagens", "esquema_versao", "derivacoes", "regra_situacao",
          "armazem_manifestos", "armazem_objetos", "cortes") + tuple(k for k in antes if k.startswith("derivacao_")):
    r["identicos"][k] = antes[k] == depois[k]


def numeros(x, caminho=""):
    """Achata a estrutura em {caminho: valor}, separando numeros de textos."""
    if isinstance(x, dict):
        for k, v in x.items():
            yield from numeros(v, f"{caminho}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from numeros(v, f"{caminho}[{i}]")
    else:
        yield caminho, x


pa, pd = dict(numeros(antes["painel"])), dict(numeros(depois["painel"]))
for k in sorted(set(pa) | set(pd)):
    a, d = pa.get(k, "<ausente>"), pd.get(k, "<ausente>")
    if a != d:
        alvo = r["textos_painel_diferentes"] if isinstance(a, str) or isinstance(d, str) else r["valores_painel_diferentes"]
        alvo.append({"chave": k, "antes": a, "depois": d})
for pagina in sorted(set(antes["tela"]) | set(depois["tela"])):
    a, d = antes["tela"].get(pagina, {}), depois["tela"].get(pagina, {})
    for i in sorted(set(a) & set(d)):
        if a[i] != d[i]:
            r["valores_tela_diferentes"].append({"pagina": pagina, "id": i, "antes": a[i], "depois": d[i]})
    if set(d) - set(a):
        r["ids_de_tela_novos"][pagina] = sorted(set(d) - set(a))
    if set(a) - set(d):
        r["ids_de_tela_removidos"][pagina] = sorted(set(a) - set(d))
r["resumo"] = {"bruto_armazem_derivacoes_identicos": all(r["identicos"].values()),
               "valores_painel_diferentes": len(r["valores_painel_diferentes"]),
               "valores_tela_diferentes": len(r["valores_tela_diferentes"]),
               "textos_painel_diferentes": len(r["textos_painel_diferentes"]),
               "paginas_com_ids_novos": len(r["ids_de_tela_novos"]),
               "paginas_com_ids_removidos": len(r["ids_de_tela_removidos"]),
               "valores_de_tela_comparados": sum(len(set(antes["tela"].get(p, {})) & set(depois["tela"].get(p, {})))
                                                 for p in antes["tela"])}
json.dump(r, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(r["resumo"], ensure_ascii=False, indent=1))
print(json.dumps(r["identicos"], indent=0))
