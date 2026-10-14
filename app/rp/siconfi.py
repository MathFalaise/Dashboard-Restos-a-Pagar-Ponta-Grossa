"""Official consolidated RREO Annex VII declared to the National Treasury (SICONFI) - corrective audit of 13/10/2026,
item 5.1.

The Elotech portal covers the Executive (the Prefeitura and the indirect administration it publishes); the official
consolidated statement of the Municipality also has the Legislative (Câmara Municipal), which the portal API does not
cover. Each source keeps its own scope: the panel's Municipality is the EXECUTIVE from the Elotech source and is
compared with the SICONFI 'PODER EXECUTIVO' row; the official consolidated series is the SICONFI row (I) (all powers,
except intra-budgetary) and TOTAL (III), shown as declared, with its source, never mixed into the Elotech values.

Source files: the public SICONFI readings versioned in docs/audits/rreo/siconfi/raw (public fiscal data, no personal
data), each file checked against the SHA-256 of its reading's manifest before use; the delivery statement
(extrato_entregas) gives the situation (HO homologated, RE rectified...) and its date. A reading folder without
manifest, or a file whose SHA-256 differs, is refused (never silently used).

Absent is not zero: SICONFI omits items whose value is zero. A missing column is taken as 0 only when the
declaration's own identities (e = a + b - c - d, k = f + g - i - j, L = e + k) close with it; otherwise the column
stays None (absent) and the totals that depend on it too.
"""
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

PASTA_PADRAO = Path(__file__).resolve().parents[2] / "docs" / "audits" / "rreo" / "siconfi" / "raw"
COLUNAS = "abcdefghijkL"
LINHAS = {"RESTOS A PAGAR (EXCETO": "I", "PODER EXECUTIVO": "executivo", "PODER LEGISLATIVO": "legislativo",
          "RESTOS A PAGAR (INTRA": "II", "TOTAL (III)": "III"}
ROTULOS_2016 = {
    "RPP e RPNP Liquidados em Exercícios Anteriores - Inscritos Em Exercícios Anteriores": "a",
    "RPP e RPNP Liquidados em Exercícios Anteriores - Inscritos Em 31 de Dezembro de 2015": "b",
    "RPP e RPNP Liquidados Em Exercícios Anteriores - Pagos": "c",
    "RPP e RPNP Liquidados Em Exercícios Anteriores - Cancelados": "d",
    "Saldo (a)": "e",
    "RPNP - Inscritos Em Exercícios Anteriores": "f",
    "RPNP - Inscritos Em 31 de Dezembro de 2015": "g",
    "RPNP - Liquidados": "h",
    "RPNP - Pagos": "i",
    "RPNP - Cancelados": "j",
    "Saldo (b)": "k",
    "Saldo Total (a+b)": "L",
}
SITUACOES = {"HO": "homologada", "RE": "retificada"}


class LeituraInvalida(ValueError):
    pass


def coluna_de(rotulo):
    if rotulo in ROTULOS_2016:
        return ROTULOS_2016[rotulo]
    if rotulo.startswith("Saldo Total L"):
        return "L"
    if rotulo.startswith("Saldo e"):
        return "e"
    if rotulo.startswith("Saldo k"):
        return "k"
    m = re.search(r"\(([a-j])\)\s*$", rotulo)
    if m:
        return m.group(1)
    raise LeituraInvalida(f"coluna SICONFI sem mapeamento: {rotulo!r}")


def leituras(pasta=None):
    """Reading folders, oldest first: the first reading (raw/ itself, files at the top) and each raw/coleta_*."""
    pasta = Path(pasta or PASTA_PADRAO)
    saida = []
    if (pasta / "manifest.json").exists() or any(pasta.glob("rreo_anexo07_*.json")):
        saida.append(pasta)
    saida += sorted(p for p in pasta.glob("coleta_*") if p.is_dir())
    return saida


def _manifesto(leitura):
    for arq in (leitura / "manifest.json", leitura.parent / "manifest.json"):
        if arq.exists():
            m = json.loads(arq.read_text(encoding="utf-8"))
            if m.get("arquivos"):
                return arq, m["arquivos"]
    raise LeituraInvalida(f"{leitura}: leitura do Siconfi sem manifesto")


def ler_arquivo(leitura, nome):
    """(parsed JSON, sha256) of one file of a reading, refused if its SHA-256 differs from the manifest's."""
    arq_man, arquivos = _manifesto(leitura)
    f = leitura / nome
    if not f.exists():
        return None, None
    corpo = f.read_bytes()
    h = hashlib.sha256(corpo).hexdigest()
    esperado = (arquivos.get(nome) or {}).get("sha256")
    if esperado != h:
        raise LeituraInvalida(f"{f}: SHA-256 {h[:12]} difere do manifesto {arq_man.name} ({str(esperado)[:12]})")
    return json.loads(corpo.decode("utf-8")), h


def _fechar(v):
    """Missing columns -> 0 only if the identities close with them; otherwise None (absent, never zero)."""
    ausentes = [c for c in COLUNAS if c not in v]
    if not ausentes:
        return v, []
    z = {**{c: 0 for c in ausentes}, **v}
    fecha = (z["e"] == z["a"] + z["b"] - z["c"] - z["d"] and z["k"] == z["f"] + z["g"] - z["i"] - z["j"]
             and z["L"] == z["e"] + z["k"])
    return (z, ausentes) if fecha else ({**{c: None for c in ausentes}, **v}, ausentes)


def declaracao(leitura, exercicio, bimestre):
    """The declaration of one period in a reading: rows (I, executivo, legislativo, II, III) x columns a..L in cents,
    plus the file and its SHA-256. None when the period has no declaration in that reading."""
    d, h = ler_arquivo(leitura, f"rreo_anexo07_{exercicio}_{bimestre}.json")
    if not d or not d.get("items"):
        return None
    linhas = {}
    for i in d["items"]:
        nome = next((n for p, n in LINHAS.items() if i["conta"].startswith(p)), None)
        if nome is None:
            continue
        col = coluna_de(i["coluna"])
        v = int((Decimal(str(i["valor"])) * 100).to_integral_value())
        if linhas.setdefault(nome, {}).get(col, v) != v:
            raise LeituraInvalida(f"{exercicio}/{bimestre}: {nome} ({col}) com dois valores")
        linhas[nome][col] = v
    fechadas, omitidas = {}, {}
    for nome, v in linhas.items():
        fechadas[nome], omitidas[nome] = _fechar(v)
    if "legislativo" not in fechadas and "I" in fechadas and "executivo" in fechadas:
        # no Legislative row: SICONFI omits it when it has no RP; it is zero ONLY if (I) equals the Executive
        if fechadas["I"] == fechadas["executivo"]:
            fechadas["legislativo"] = {c: 0 for c in COLUNAS}
    return {"exercicio": exercicio, "bimestre": bimestre, "arquivo": f"{leitura.name}/rreo_anexo07_{exercicio}_{bimestre}.json",
            "sha256": h, "linhas": fechadas, "colunas_omitidas": {k: v for k, v in omitidas.items() if v}}


def situacao_da_entrega(leitura, exercicio, bimestre):
    """Situation of the RREO delivery of the period in the reading's delivery statement (None when the reading has no
    statement: the first reading of 09/10/2026 did not collect it)."""
    try:
        d, h = ler_arquivo(leitura, f"extrato_entregas_{exercicio}.json")
    except LeituraInvalida:
        raise
    if not d:
        return None
    for i in d.get("items", []):
        if (i.get("entregavel", "").startswith("Relatório Resumido") and i.get("periodo") == bimestre
                and i.get("periodicidade") == "B"):
            return {"status": i.get("status_relatorio"), "situacao": SITUACOES.get(i.get("status_relatorio"),
                                                                                    i.get("status_relatorio")),
                    "data_status": i.get("data_status"), "instituicao": i.get("instituicao"),
                    "forma_envio": i.get("forma_envio"), "arquivo": f"{leitura.name}/extrato_entregas_{exercicio}.json",
                    "sha256": h}
    return None


def grupos(v):
    """Column groups that do not depend on how a rule splits processed/non-processed: inscription (a+b+f+g),
    payments (c+i), cancellations (d+j), liquidations (h) and the balance L. None when a needed column is absent."""
    def soma(*cs):
        return None if any(v.get(c) is None for c in cs) else sum(v[c] for c in cs)
    return {"inscricao": soma("a", "b", "f", "g"), "pagos": soma("c", "i"), "cancelados": soma("d", "j"),
            "liquidados": soma("h"), "saldo": soma("L")}
