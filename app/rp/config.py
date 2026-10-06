"""Reading and validation of config.toml."""
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

RAIZ_APP = Path(__file__).resolve().parents[1]

# Default cap on the body of ONE HTTP response. The largest real response so far is a few MB;
# the cap only exists so that a faulty or hostile server cannot exhaust memory.
LIMITE_RESPOSTA_PADRAO = 64 * 1024 * 1024


class ConfiguracaoInvalida(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    dados_locais: Path
    snapshots: Path
    backups: Path
    api_base: str
    pausa: float
    timeout: float
    tentativas: int
    espera_base: float
    user_agent: str
    entidades: tuple
    exercicios: tuple
    limite_resposta_bytes: int = LIMITE_RESPOSTA_PADRAO
    entidade_rreo: int = 1          # entity whose publications (LRF group) carry the RREO Annex VII
    timeout_conexao: float = 30.0   # time limit to establish the connection (the read limit is `timeout`; see http.py)

    def __post_init__(self):
        _validar(self)

    @property
    def banco(self):
        return self.dados_locais / "banco" / "restos_a_pagar.sqlite"

    @property
    def logs(self):
        return self.dados_locais / "logs"

    @property
    def temporario(self):
        return self.dados_locais / "banco" / "tmp"

    @property
    def backups_operacionais(self):
        """Routine backups (e.g. before deleting a reprocessable run): local, with retention."""
        return self.dados_locais / "backups_operacionais"


def _validar(c):
    """Rejects a config that would weaken collection: API without TLS, numbers out of range, header with a line break."""
    u = urlsplit(c.api_base)
    if u.scheme != "https" or not u.hostname or u.username or u.password or u.query or u.fragment:
        raise ConfiguracaoInvalida(f"api.base precisa ser https://host/caminho, sem credencial, query ou fragmento: {c.api_base!r}")
    if not (c.pausa >= 0 and c.timeout > 0 and c.espera_base >= 0 and c.timeout_conexao > 0):
        raise ConfiguracaoInvalida("pausa e espera_base precisam ser >= 0; timeout e timeout_conexao, > 0")
    if isinstance(c.tentativas, bool) or not isinstance(c.tentativas, int) or c.tentativas < 1:
        raise ConfiguracaoInvalida("tentativas precisa ser um inteiro >= 1")
    if isinstance(c.limite_resposta_bytes, bool) or not isinstance(c.limite_resposta_bytes, int) or c.limite_resposta_bytes < 1:
        raise ConfiguracaoInvalida("limite_resposta_bytes precisa ser um inteiro >= 1")
    if not isinstance(c.user_agent, str) or not c.user_agent or any(ord(ch) < 32 or ord(ch) == 127 for ch in c.user_agent):
        raise ConfiguracaoInvalida("user_agent vazio ou com caractere de controle")
    if isinstance(c.entidade_rreo, bool) or not isinstance(c.entidade_rreo, int) or c.entidade_rreo < 1:
        raise ConfiguracaoInvalida("rreo.entidade_publicacoes precisa ser um inteiro >= 1")


def _caminho(v, base):
    """'~' = the user's folder (on any system); relative = from the config file's folder."""
    p = Path(v).expanduser()
    return p if p.is_absolute() else (base / p).resolve()


def carregar(arquivo=None, **substituir):
    """Reads config.toml (or the RP_CONFIG file). RP_DADOS_LOCAIS, if set, replaces caminhos.dados_locais: lets you
    point to another local folder (active database and logs) without editing the versioned file."""
    arquivo = Path(arquivo or os.environ.get("RP_CONFIG") or RAIZ_APP / "config.toml")
    c = tomllib.loads(arquivo.read_text(encoding="utf-8"))
    base = arquivo.parent
    valores = dict(
        dados_locais=_caminho(os.environ.get("RP_DADOS_LOCAIS") or c["caminhos"]["dados_locais"], base),
        snapshots=_caminho(c["caminhos"]["snapshots"], base),
        backups=_caminho(c["caminhos"]["backups"], base),
        api_base=c["api"]["base"].rstrip("/"),
        pausa=float(c["api"]["pausa_segundos"]),
        timeout=float(c["api"]["timeout_segundos"]),
        tentativas=int(c["api"]["tentativas"]),
        espera_base=float(c["api"]["espera_base_segundos"]),
        user_agent=c["api"]["user_agent"],
        entidades=tuple(int(e) for e in c["escopo"]["entidades"]),
        exercicios=tuple(int(x) for x in c["escopo"]["exercicios"]),
        limite_resposta_bytes=int(c["api"].get("limite_resposta_bytes", LIMITE_RESPOSTA_PADRAO)),
        entidade_rreo=int(c.get("rreo", {}).get("entidade_publicacoes", 1)),
        timeout_conexao=float(c["api"].get("timeout_conexao_segundos", 30)),
    )
    valores.update(substituir)
    return Config(**valores)
