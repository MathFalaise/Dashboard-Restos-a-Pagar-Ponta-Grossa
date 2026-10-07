"""Pages of the public interface.

Each function receives the Painel (read-only connection) and the already validated parameters and returns (title,
HTML body). No function computes an accounting rule: values arrive ready from the panel layer, with nature, source,
rule and provenance; here we only choose what to show and how to label it. Every text from the database goes
through `esc`.

Presentation rules:
  * main value = Elotech API; the RREO only appears in the cross-check and the reconciliation, always labeled;
  * every value shows source, nature and rule, and has its origin within reach (<details>, no JavaScript);
  * every cut-off shows fiscal year, cut-off and collection date (never just "Restos a Pagar de AAAA");
  * a missing value is explicit text, never R$ 0,00; an entity outside the official catalog never becomes zero;
  * always the public level: lists without the creditor's name or document; individuals without a name in the
    detail;
  * analytical views (CONS-PAR) and experimental rules do not appear as indicators.

Modules: estrutura (page structure and shared components) and one tela_* module per screen.
Callers keep using `paginas.<screen>(painel, params)`; aplicacao.py maps each route to one of them.
"""
from ..formato import esc
from .estrutura import DESTAQUES, documento, erro, GRUPOS, MENU, NOME_CATEGORIA, NOME_FAIXA, SemDados, TAMANHO_PAGINA
from .tela_composicao import composicao, TOTAL_NA_LISTA
from .tela_empenho import empenho, empenho_cortes
from .tela_empenhos import empenhos
from .tela_entidades import entidades
from .tela_evolucao import evolucao, SERIE_COLUNAS
from .tela_historico import historico, HISTORICO_COLUNAS
from .tela_metodologia import metodologia
from .tela_pares import pares
from .tela_qualidade import qualidade, SITUACAO_CURTA
from .tela_reconciliacao import reconciliacao
from .tela_resumo import resumo
from .tela_retratos import comparar, retratos
from .tela_variacao import CABECALHO_CONTRIBUICAO, variacao
from .tela_visao import visao

__all__ = ["CABECALHO_CONTRIBUICAO", "comparar", "composicao", "DESTAQUES", "documento", "empenho", "empenho_cortes",
           "empenhos", "entidades", "erro", "esc", "evolucao", "GRUPOS", "historico", "HISTORICO_COLUNAS", "MENU",
           "metodologia", "NOME_CATEGORIA", "NOME_FAIXA", "pares", "qualidade", "reconciliacao", "resumo", "retratos",
           "SemDados", "SERIE_COLUNAS", "SITUACAO_CURTA", "TAMANHO_PAGINA", "TOTAL_NA_LISTA", "variacao", "visao"]
