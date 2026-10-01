"""Atalho para usar `python -m rp ...` tambem na raiz do projeto.

O pacote fica em app/rp. Dentro de app/ o Python acha o pacote direto e este arquivo nao e usado; na raiz, ele
poe app/ na frente do caminho de busca e executa o pacote de verdade (python -m rp interface, verificar, etc.).
Nao muda nada no comportamento do programa: configuracao, banco e snapshots continuam resolvidos a partir de app/.
"""
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "app"))
sys.modules.pop("rp", None)
runpy.run_module("rp", run_name="__main__", alter_sys=True)
