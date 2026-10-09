"""Downloads the RREO Annex 07 declared by the Município of Ponta Grossa to the National Treasury (SICONFI), as an
independent reference for the reconciliation (correction request of 09/10/2026, item 6). It touches neither the
project database nor the store.

Source: SICONFI open-data API of the Tesouro Nacional (https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo),
ente 4119905 (Ponta Grossa - PR), esfera M, demonstrativo RREO, anexo "RREO-Anexo 07", one request per fiscal year and
bimester. Each response is saved byte for byte in raw/ (public fiscal data, no personal data), and manifest.json keeps
URL, retrieval time, HTTP status and SHA-256 of every file. Existing files are never overwritten: run again to add
only the missing periods.

Usage (from the repository root): python docs/audits/rreo/siconfi/baixar_siconfi.py [--anos 2016-2026]
"""
import argparse
import hashlib
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

PASTA = Path(__file__).resolve().parent
BASE = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo"
ENTE = 4119905
PAUSA = 1.5
UA = "RestosAPagarPG-conferencia (pesquisa sobre dados publicos de Restos a Pagar)"
BRT = timezone(timedelta(hours=-3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anos", default="2016-2026")
    a = ap.parse_args()
    ini, fim = (int(x) for x in a.anos.split("-"))
    (PASTA / "raw").mkdir(exist_ok=True)
    arq_manifesto = PASTA / "manifest.json"
    manifesto = json.loads(arq_manifesto.read_text(encoding="utf-8")) if arq_manifesto.exists() else {
        "fonte": BASE, "ente_ibge": ENTE, "anexo": "RREO-Anexo 07", "arquivos": {}}
    for ano in range(ini, fim + 1):
        for periodo in range(1, 7):
            nome = f"rreo_anexo07_{ano}_{periodo}.json"
            if nome in manifesto["arquivos"]:
                continue
            q = {"an_exercicio": ano, "nr_periodo": periodo, "co_tipo_demonstrativo": "RREO",
                 "no_anexo": "RREO-Anexo 07", "co_esfera": "M", "id_ente": ENTE}
            url = BASE + "?" + urllib.parse.urlencode(q)
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                corpo, status = r.read(), r.status
            d = json.loads(corpo)
            if d.get("hasMore"):
                raise RuntimeError(f"{nome}: resposta paginada (hasMore); o script não trata paginação")
            if not d.get("items"):                     # not declared yet: recorded as such, fetched again next run
                manifesto.setdefault("sem_declaracao", {})[nome] = datetime.now(BRT).isoformat(timespec="seconds")
                print(nome, status, 0, flush=True)
                time.sleep(PAUSA)
                continue
            manifesto.get("sem_declaracao", {}).pop(nome, None)
            destino = PASTA / "raw" / nome
            with open(destino, "xb") as f:                         # "x": never overwrites
                f.write(corpo)
            manifesto["arquivos"][nome] = {"url": url, "obtido_em": datetime.now(BRT).isoformat(timespec="seconds"),
                                           "http_status": status, "itens": len(d.get("items", [])),
                                           "sha256": hashlib.sha256(corpo).hexdigest(), "tamanho": len(corpo)}
            print(nome, status, len(d.get("items", [])), flush=True)
            time.sleep(PAUSA)
    arq_manifesto.write_text(json.dumps(manifesto, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
