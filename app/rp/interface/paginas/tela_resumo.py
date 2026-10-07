"""Summary screen (/): the indicators of a cut-off."""
from .. import formato as fm, portal as P
from ..formato import esc
from .estrutura import (_avisos, _cartao, _entidades_do_catalogo, erro, _explicacoes, _formulario, GRUPOS, _quando,
                        _retrato, _selecao, SemDados)


def resumo(p, q):
    try:
        sel = _selecao(p, q)
    except SemDados as e:
        return erro("Sem dados processados", str(e))
    ind = p.indicadores(sel["exercicio"], sel["data_final"], sel["entidade"], sel["em"])
    escopo = f"entidade {sel['entidade']}" if sel["entidade"] is not None else "Município"
    titulo = (f"Restos a Pagar — {escopo}, exercício {sel['exercicio']}, corte {fm.data_br(sel['data_final'])} "
              f"({_quando(sel)})")
    partes = [f"<h1>{esc(titulo)}</h1>", _avisos(sel["avisos"]),
              _formulario("/", sel, _entidades_do_catalogo(p)),
              '<p class="dica">' + fm.link("/evolucao", f"Ver a evolução de todos os cortes do exercício "
                                                        f"{sel['exercicio']}", exercicio=sel["exercicio"],
                                           entidade=sel["entidade"], em=sel["em"]) + " · "
              + fm.link("/composicao", "Ver a composição do saldo deste corte", exercicio=sel["exercicio"],
                        data_final=sel["data_final"], entidade=sel["entidade"], em=sel["em"]) + "</p>",
              _retrato(ind["retrato"])]
    unicas = [e for e in ind["entidades"] if e["entra_no_total"]]
    if ind["disponivel"] and unicas and all(e["situacao_do_dado"]["codigo"] == "sem_rp" for e in unicas):
        partes.append('<p class="aviso" id="sem-rp">Zero de verdade: a API devolveu zero registros de RP para '
                      "este escopo e corte (entidade existente, sem RP).</p>")
    if not ind["disponivel"]:
        partes.append('<section class="indisponivel" id="indisponivel"><h2>Dados indisponíveis para este recorte</h2>'
                      f'<p>{esc(ind["motivo_indisponivel"])}.</p><p>Nenhum valor é mostrado: ausência de dado não é '
                      "zero.</p></section>")
    else:
        v = ind["valores"]
        for nome, ids in GRUPOS:
            partes.append(f'<section class="grupo"><h2>{esc(nome)}</h2><div class="cartoes">'
                          + "".join(_cartao(v[i]) for i in ids) + "</div></section>")
        ret = ind["retrato"]
        partes.append(P.secao_onde_conferir(ind["entidades"], sel["exercicio"], sel["data_final"],
                                            fm.data_br(ret["coletado_de"], True) if ret else ""))
    partes.append(_entidades_abrangidas(ind))
    partes.append(_aviso_retratos(ind, sel))
    if ind["disponivel"]:
        partes.append(_conferencia(ind, sel))
    partes.append(_avisos([a for a in ind["avisos"][1:]]))
    return titulo, "".join(partes)


def _entidades_abrangidas(ind):
    linhas = []
    for e in ind["entidades"]:
        s = e["snapshot"]
        fora = e["situacao_no_exercicio"] == "fora do catálogo oficial"
        situacao = e["situacao_do_dado"]["texto"]
        if e["retrato_mais_novo_nao_processado"]:
            situacao += "; há retrato mais novo coletado, ainda não processado"
        linhas.append([esc(e["entidade"]), esc(e["nome"] or ""), esc(e["situacao_no_exercicio"]),
                       f'<span id="situacao-{esc(e["entidade"])}">{esc(situacao)}</span>',
                       "sim" if e["entra_no_total"] else "não",
                       esc(fm.data_br(s["coletada_em"], True)) if s else "—",
                       fm.contagem(s["registros"]) if s and not fora else "—",
                       f"<code>{esc(s['snapshot_uid'])}</code>" if s else "—"])
    return ('<section class="grupo"><h2>Entidades abrangidas</h2>'
            + fm.tabela([("Entidade", None), ("Nome", None), ("Situação no catálogo do exercício", None),
                         ("Situação do dado", None), ("Entra no total", None), ("Coletado em", None),
                         ("Registros", None), ("Snapshot", "retrato usado (origem dos valores)")], linhas)
            + f'<p>{fm.link("/entidades", "Ver valores por entidade")}</p></section>')


def _aviso_retratos(ind, sel):
    varios = [e for e in ind["entidades"] if e.get("retratos_do_corte", 0) > 1]
    if not varios:
        return ""
    itens = "".join("<li>" + fm.link("/retratos", f"entidade {e['entidade']}: {e['retratos_do_corte']} retratos deste corte",
                                     entidade=e["entidade"], exercicio=sel["exercicio"], data_final=sel["data_final"])
                    + "</li>" for e in varios)
    return ('<section class="grupo"><h2>Mais de um retrato disponível</h2><p>O mesmo corte foi coletado mais de uma '
            "vez. Cada coleta é um retrato independente; os valores acima usam o mais recente (vigente).</p>"
            f"<ul>{itens}</ul></section>")


def _conferencia(ind, sel):
    c = ind.get("conferencia_rreo")
    cab = ('<section class="grupo conferencia" id="conferencia-rreo"><h2>Conferência com o RREO (publicação oficial '
           'independente)</h2><p class="fontes"><strong>Fonte primária:</strong> API Elotech · <strong>Fonte de '
           "reconciliação:</strong> RREO Anexo VII</p>")
    if not c:
        motivo = ind.get("reconciliacao") or "sem RREO transcrito para este corte e escopo"
        return cab + f"<p>{esc(motivo)}.</p></section>"
    linhas = [
        [esc(c["api"]["rotulo"]), fm.valor(c["api"]["valor_c"], "conf-api"), "API Elotech", fm.natureza("derivado")],
        [esc(c["rreo"]["rotulo"]), fm.valor(c["rreo"]["valor_c"], "conf-rreo"),
         esc(f"RREO Anexo VII — {c['rreo']['pdf']['rotulo']}, emitido em {c['rreo']['pdf']['emitido_em']}"),
         fm.natureza("publicado")],
        ["Diferença (API − RREO)", fm.valor(c["diferenca_c"], "conf-dif"), "—", fm.natureza("diferenca")],
    ]
    detalhe = fm.link("/reconciliacao", "Ver a reconciliação coluna a coluna deste documento",
                      exercicio=sel["exercicio"], data_final=sel["data_final"], escopo=c["escopo"])
    return (cab + fm.tabela([("", None), ("Valor", None), ("Fonte", None), ("Natureza", None)], linhas)
            + f'<p>Situação do dado: {esc(c["situacao_do_dado"]["texto"])}.</p>'
            + f'<p>Situação da diferença: {_explicacoes(c["situacao_da_diferenca"], c["explicacoes"])}</p>'
            + f'<p class="nota">{esc(c["nota"])}</p><p>{detalhe}</p></section>')
