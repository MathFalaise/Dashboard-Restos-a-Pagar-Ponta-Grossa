"""The rp.py shortcut at the project root: `python -m rp ...` works both in app/ and at the root (requested by the
owner on 01/10/2026; the error was 'No module named rp' when running at the root)."""
import json
import subprocess
import sys

from conftest import RAIZ_PROJETO


def test_python_m_rp_funciona_na_raiz_do_projeto():
    for pasta in (RAIZ_PROJETO, RAIZ_PROJETO / "app"):
        r = subprocess.run([sys.executable, "-m", "rp", "--help"], cwd=pasta, capture_output=True, text=True,
                           timeout=60)
        assert r.returncode == 0 and "interface" in r.stdout, (pasta, r.stderr[-300:])


def test_atalho_executa_o_pacote_de_app_sem_mudar_a_configuracao():
    codigo = ("import json, runpy, sys; sys.argv = ['rp', '--help']\n"
              "try:\n    runpy.run_path('rp.py', run_name='__main__')\nexcept SystemExit: pass\n"
              "import rp, rp.config; print(json.dumps([rp.__file__, str(rp.config.RAIZ_APP)]))")
    r = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ_PROJETO, capture_output=True, text=True, timeout=60)
    arquivo, raiz_app = json.loads(r.stdout.strip().splitlines()[-1])
    assert arquivo.replace("\\", "/").endswith("app/rp/__init__.py")
    assert raiz_app.replace("\\", "/").endswith("/app")
