"""Camada publica: minimizacao de dados para o dashboard.

O fato de um dado estar na fonte oficial nao faz com que ele deva aparecer em toda tela. No nivel publico (padrao):
  * listagens e agregados NUNCA trazem identificacao do credor (codigo, nome, CNPJ/CPF): so o tipo de credor;
  * o detalhe de UM empenho traz o nome do credor pessoa juridica sem nenhum documento: tira o prefixo
    "CNPJ - " e mascara toda sequencia com cara de documento (a razao social de MEI costuma terminar com o CPF
    do titular, as vezes sem o zero inicial, e comecar com a raiz do CNPJ);
  * credor pessoa fisica (CPF mascarado pela propria API) nao tem o nome exibido;
  * documento do credor (CNPJ, CPF mascarado) so no nivel "interno", pedido explicitamente.
Nao ha dado bancario nos campos coletados.
"""
import re

CAMPOS_RESTRITOS = ("fornecedor", "nome", "cnpj", "cnpj_nome")
TIPOS_CREDOR = ("pessoa jurídica", "pessoa física", "não identificado")
OMITIDO = "[documento omitido]"
PESSOA_FISICA_OMITIDA = "[nome de pessoa física omitido]"

_PREFIXO_DOC = re.compile(r"^\s*[\d.*/-]{8,}\s*-\s*")
# sequencia de digitos, pontos, barras, hifens e asteriscos que comeca e termina com digito ou asterisco
_TOKEN = re.compile(r"[\d*][\d.*/-]*[\d*]|\d")
_CNPJ = re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}")
_CPF_MASCARADO = re.compile(r"\*+\d{3}\*+")


def _mascarar(m):
    t = m.group(0)
    digitos = sum(ch.isdigit() for ch in t)
    if digitos >= 8 or ("*" in t and digitos >= 3):
        return OMITIDO   # CNPJ, raiz de CNPJ, CPF (com ou sem pontuacao) ou CPF ja mascarado
    return t


def tipo_credor(cnpj):
    """Tipo do credor: pessoa juridica (CNPJ), pessoa fisica (CPF mascarado pela API) ou nao identificado."""
    s = str(cnpj or "")
    if _CNPJ.fullmatch(s):
        return "pessoa jurídica"
    if _CPF_MASCARADO.fullmatch(s) or len(re.sub(r"\D", "", s)) == 11:
        return "pessoa física"
    return "não identificado"


def nome_publico(nome, cnpj=None):
    """Nome do credor para o nivel publico (ver docstring do modulo). None quando nao ha o que mostrar."""
    if tipo_credor(cnpj) == "pessoa física":
        return PESSOA_FISICA_OMITIDA
    if not nome:
        return None
    s = _TOKEN.sub(_mascarar, _PREFIXO_DOC.sub("", nome)).strip()
    return s or None


def sem_restritos(registro):
    """Copia do registro sem os campos que identificam o credor."""
    return {k: v for k, v in registro.items() if k not in CAMPOS_RESTRITOS}
