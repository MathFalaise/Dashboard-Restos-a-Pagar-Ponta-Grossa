"""New dated reading of the SICONFI declarations (corrective audit of 13/10/2026, item 6.1).

The first reading (09/10/2026, baixar_siconfi.py) stays in raw/ untouched. Each run of this script writes a NEW folder
raw/coleta_<YYYYMMDD-HHMMSS>/ with:
  * rreo_anexo07_<ano>_<periodo>.json  - the RREO Annex 07 values declared for each fiscal year and bimester;
  * extrato_entregas_<ano>.json        - the delivery statement of the ente: per report and period, the situation
                                          (HO = homologated, RE = rectified...), its date and the delivery form;
  * manifest.json                      - URL, time, HTTP status, size and SHA-256 of every file.
Nothing is ever overwritten (files opened with "x"). Public fiscal data, no personal data.

Usage (from the repository root): python docs/audits/rreo/siconfi/recoletar_siconfi.py [--anos 2016-2026]
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
BASE = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"
ENTE = 4119905
PAUSA = 1.5
UA = "RestosAPagarPG-conferencia (pesquisa sobre dados publicos de Restos a Pagar)"
BRT = timezone(timedelta(hours=-3))


def obter(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read(), r.status


def gravar(destino, nome, url, manifesto):
    corpo, status = obter(url)
    d = json.loads(corpo)
    if d.get("hasMore"):
        raise RuntimeError(f"{nome}: resposta paginada (hasMore); o script nao trata paginacao")
    with open(destino / nome, "xb") as f:
        f.write(corpo)
    manifesto["arquivos"][nome] = {"url": url, "obtido_em": datetime.now(BRT).isoformat(timespec="seconds"),
                                   "http_status": status, "itens": len(d.get("items", [])),
                                   "sha256": hashlib.sha256(corpo).hexdigest(), "tamanho": len(corpo)}
    print(nome, status, len(d.get("items", [])), flush=True)
    time.sleep(PAUSA)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anos", default="2016-2026")
    a = ap.parse_args()
    ini, fim = (int(x) for x in a.anos.split("-"))
    carimbo = datetime.now(BRT).strftime("%Y%m%d-%H%M%S")
    destino = PASTA / "raw" / f"coleta_{carimbo}"
    destino.mkdir(parents=True, exist_ok=False)
    manifesto = {"fonte": BASE, "ente_ibge": ENTE, "anexo": "RREO-Anexo 07", "iniciada_em": carimbo, "arquivos": {}}
    for ano in range(ini, fim + 1):
        q = {"id_ente": ENTE, "an_referencia": ano}
        gravar(destino, f"extrato_entregas_{ano}.json", f"{BASE}/extrato_entregas?{urllib.parse.urlencode(q)}",
               manifesto)
        for periodo in range(1, 7):
            q = {"an_exercicio": ano, "nr_periodo": periodo, "co_tipo_demonstrativo": "RREO",
                 "no_anexo": "RREO-Anexo 07", "co_esfera": "M", "id_ente": ENTE}
            gravar(destino, f"rreo_anexo07_{ano}_{periodo}.json", f"{BASE}/rreo?{urllib.parse.urlencode(q)}",
                   manifesto)
    with open(destino / "manifest.json", "x", encoding="utf-8") as f:
        f.write(json.dumps(manifesto, ensure_ascii=False, indent=1, sort_keys=True))
    print(destino)


if __name__ == "__main__":
    main()
