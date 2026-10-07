"""Entities of a cut-off (/entidades)."""
from .. import formato as fm
from ..formato import esc
from .estrutura import _avisos, erro, _formulario, _quando, _retrato, _selecao, SemDados


def entidades(p, q):
    try:
        sel = _selecao(p, q, com_entidade=False)
    except SemDados as e:
        return erro("Sem dados processados", str(e))
    r = p.entidades_do_corte(sel["exercicio"], sel["data_final"], sel["em"])
    titulo = (f"Entidades — exercício {sel['exercicio']}, corte {fm.data_br(sel['data_final'])} "
              f"({_quando(sel)})")
    linhas = []
    for l in r["linhas"]:
        situacao = l["situacao_do_dado"]["texto"]
        if l["retrato_mais_novo_nao_processado"]:
            situacao += "; há retrato mais novo coletado, ainda não processado"
        base = [esc(l["entidade"]), esc(l["nome"] or ""), esc(sel["exercicio"]), esc(l["situacao_no_exercicio"]),
                f'<span id="situacao-{esc(l["entidade"])}">{esc(situacao)}</span>']
        v = l["valores"]
        if v is None:
            base.append(f'<td colspan="5" class="sem-valor" id="sem-valor-{esc(l["entidade"])}">'
                        f'{esc(l["situacao_do_valor"])} — sem valor</td>')
        else:
            ent = l["entidade"]
            base += [fm.valor(v["inscricao_processada"], f"ent-{ent}-proc"),
                     fm.valor(v["inscricao_nao_processada"], f"ent-{ent}-aproc"),
                     fm.valor(v["inscricao_total"], f"ent-{ent}-total"),
                     fm.valor(v["saldo_total"], f"ent-{ent}-s1"),
                     fm.contagem(v["registros"], f"ent-{ent}-registros")]
        retratos = l["retratos_do_corte"]
        base.append(fm.link("/retratos", str(retratos), entidade=l["entidade"], exercicio=sel["exercicio"],
                            data_final=sel["data_final"]) if retratos else "0")
        if v is not None:
            pv = l["proveniencia"]
            base.append(f'<details class="origem"><summary>origem</summary><code>{esc(l["snapshot"]["snapshot_uid"])}</code> '
                        f'— coletado em {esc(fm.data_br(l["snapshot"]["coletada_em"], True))}; derivação '
                        f'{esc(pv["derivacao_id"])}, normalização {esc(pv["normalizacao_id"])}</details>')
        else:
            base.append("—")
        linhas.append(base)
    tabela = fm.tabela([("Entidade", None), ("Nome", None), ("Exercício", None), ("Situação no catálogo", None),
                        ("Situação do dado", None), ("Processado (inscrito)", "proc na abertura"), ("Não processado (inscrito)", "aproc na abertura"),
                        ("Total inscrito", "proc + aproc"), ("Saldo no corte (S1)", "S1 v1"),
                        ("Empenhos", "registros no snapshot"), ("Retratos", "coletas deste corte"),
                        ("Origem", "snapshot e derivação dos valores da linha")], linhas)
    corpo = [f"<h1>{esc(titulo)}</h1>", _avisos(sel["avisos"]), _formulario("/entidades", sel), _retrato(r["retrato"]),
             fm.selo("elotech", "derivado", [{"codigo": "S1", "versao": 1, "situacao": "operacional"}],
                     "somas dos campos da API por entidade"),
             tabela, f'<p class="nota">{esc(r["nota"])}</p>']
    if not r["municipio_disponivel"]:
        corpo.append(f'<p class="aviso">Total do Município indisponível neste corte: {esc(r["motivo_indisponivel"])}.</p>')
    return titulo, "".join(corpo)
