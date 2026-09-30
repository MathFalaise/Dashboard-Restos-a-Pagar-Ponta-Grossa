"""Leitura e validacao de config.toml."""
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

RAIZ_APP = Path(__file__).resolve().parents[1]

# Teto padrao do corpo de UMA resposta HTTP. A maior resposta real ate hoje tem poucos MB;
# o teto so existe para que um servidor defeituoso ou hostil nao esgote a memoria.
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
        """Backups de rotina (ex.: antes de apagar uma execucao reprocessavel): locais, com retencao."""
        return self.dados_locais / "backups_operacionais"


def _validar(c):
    """Recusa configuracao que enfraqueca a coleta: API sem TLS, numeros fora de faixa, cabecalho com quebra de linha."""
    u = urlsplit(c.api_base)
    if u.scheme != "https" or not u.hostname or u.username or u.password or u.query or u.fragment:
        raise ConfiguracaoInvalida(f"api.base precisa ser https://host/caminho, sem credencial, query ou fragmento: {c.api_base!r}")
    if not (c.pausa >= 0 and c.timeout > 0 and c.espera_base >= 0):
        raise ConfiguracaoInvalida("pausa e espera_base precisam ser >= 0 e timeout > 0")
    if isinstance(c.tentativas, bool) or not isinstance(c.tentativas, int) or c.tentativas < 1:
        raise ConfiguracaoInvalida("tentativas precisa ser um inteiro >= 1")
    if isinstance(c.limite_resposta_bytes, bool) or not isinstance(c.limite_resposta_bytes, int) or c.limite_resposta_bytes < 1:
        raise ConfiguracaoInvalida("limite_resposta_bytes precisa ser um inteiro >= 1")
    if not isinstance(c.user_agent, str) or not c.user_agent or any(ord(ch) < 32 or ord(ch) == 127 for ch in c.user_agent):
        raise ConfiguracaoInvalida("user_agent vazio ou com caractere de controle")


def _caminho(v, base):
    p = Path(v)
    return p if p.is_absolute() else (base / p).resolve()


def carregar(arquivo=None, **substituir):
    arquivo = Path(arquivo or os.environ.get("RP_CONFIG") or RAIZ_APP / "config.toml")
    c = tomllib.loads(arquivo.read_text(encoding="utf-8"))
    base = arquivo.parent
    valores = dict(
        dados_locais=_caminho(c["caminhos"]["dados_locais"], base),
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
    )
    valores.update(substituir)
    return Config(**valores)
