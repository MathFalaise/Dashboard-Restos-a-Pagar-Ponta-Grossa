"""Names of the government functions (funcao field of the API), from the official federal classification.

The Elotech API only returns the 2-digit code of the function. The names come from a REFERENCE source outside the
API, registered as such: the annex of Portaria MOG n. 42 of 14/04/1999 (Ministerio do Planejamento, DOU of
15/04/1999), which fixes the functions and subfunctions of government for the Union, states and municipalities.
Checked on 07/10/2026 against the annex reproduced by SEF/SC ("Anexo I - Funcao e Subfuncao de Governo"): the 28
functions below, codes 01 to 28. A code outside the table keeps the code (never a guessed name).
"""
FONTE_FUNCOES = ("Portaria MOG nº 42, de 14/04/1999 (Ministério do Planejamento, DOU de 15/04/1999), anexo de "
                 "funções e subfunções de governo")

FUNCOES = {
    "01": "Legislativa", "02": "Judiciária", "03": "Essencial à Justiça", "04": "Administração",
    "05": "Defesa Nacional", "06": "Segurança Pública", "07": "Relações Exteriores", "08": "Assistência Social",
    "09": "Previdência Social", "10": "Saúde", "11": "Trabalho", "12": "Educação", "13": "Cultura",
    "14": "Direitos da Cidadania", "15": "Urbanismo", "16": "Habitação", "17": "Saneamento",
    "18": "Gestão Ambiental", "19": "Ciência e Tecnologia", "20": "Agricultura", "21": "Organização Agrária",
    "22": "Indústria", "23": "Comércio e Serviços", "24": "Comunicações", "25": "Energia", "26": "Transporte",
    "27": "Desporto e Lazer", "28": "Encargos Especiais",
}


def nome_da_funcao(codigo):
    """'10' -> 'Saúde'; a code outside the table (or None) -> None (the caller keeps the API label)."""
    return FUNCOES.get(str(codigo).zfill(2)) if codigo is not None else None
