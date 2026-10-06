"""Public layer: data minimization for the dashboard.

A value being in the official source does not mean it should appear on every screen. At the public level (default):
  * lists and aggregates NEVER carry creditor identification (code, name, CNPJ/CPF): only the creditor type;
  * the detail of ONE commitment shows the name of a legal-entity creditor without any document: it drops the
    "CNPJ - " prefix and masks every document-like sequence (an MEI's corporate name often ends with the owner's
    CPF, sometimes without the leading zero, and starts with the CNPJ root);
  * an individual creditor (CPF masked by the API itself) has no name shown;
  * the creditor's document (CNPJ, masked CPF) only at the "interno" level, when explicitly requested.
There is no bank data in the collected fields.
"""
import re

CAMPOS_RESTRITOS = ("fornecedor", "nome", "cnpj", "cnpj_nome")
TIPOS_CREDOR = ("pessoa jurídica", "pessoa física", "não identificado")
OMITIDO = "[documento omitido]"
PESSOA_FISICA_OMITIDA = "[nome de pessoa física omitido]"

_PREFIXO_DOC = re.compile(r"^\s*[\d.*/-]{8,}\s*-\s*")
# sequence of digits, dots, slashes, hyphens and asterisks that starts and ends with a digit or an asterisk
_TOKEN = re.compile(r"[\d*][\d.*/-]*[\d*]|\d")
_CNPJ = re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}")
_CPF_MASCARADO = re.compile(r"\*+\d{3}\*+")


def _mascarar(m):
    t = m.group(0)
    digitos = sum(ch.isdigit() for ch in t)
    if digitos >= 8 or ("*" in t and digitos >= 3):
        return OMITIDO   # CNPJ, CNPJ root, CPF (with or without punctuation) or an already masked CPF
    return t


def tipo_credor(cnpj):
    """Creditor type: legal entity (CNPJ), individual (CPF masked by the API) or not identified."""
    s = str(cnpj or "")
    if _CNPJ.fullmatch(s):
        return "pessoa jurídica"
    if _CPF_MASCARADO.fullmatch(s) or len(re.sub(r"\D", "", s)) == 11:
        return "pessoa física"
    return "não identificado"


def nome_publico(nome, cnpj=None):
    """Creditor name for the public level (see the module docstring). None when there is nothing to show."""
    if tipo_credor(cnpj) == "pessoa física":
        return PESSOA_FISICA_OMITIDA
    if not nome:
        return None
    s = _TOKEN.sub(_mascarar, _PREFIXO_DOC.sub("", nome)).strip()
    return s or None


def sem_restritos(registro):
    """Copy of the record without the fields that identify the creditor."""
    return {k: v for k, v in registro.items() if k not in CAMPOS_RESTRITOS}
