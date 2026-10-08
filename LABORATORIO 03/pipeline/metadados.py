"""Metadados dos repositórios usados como fatores na RQ 06."""

from urllib.parse import parse_qs, urlparse

from pipeline.funil import ler_data


DIAS_POR_ANO = 365.25


def ultima_pagina(link):
    """Número da página ``rel="last"`` do cabeçalho Link, ou ``None`` se não houver."""
    for parte in (link or "").split(","):
        if 'rel="last"' in parte:
            url = parte.split(";")[0].strip().strip("<>")
            return int(parse_qs(urlparse(url).query)["page"][0])
    return None


def contar_contribuidores(cliente, full_name):
    """Com ``per_page=1``, o número da última página é o número de contribuidores.

    Retorna ``None`` quando o GitHub se recusa a calcular (histórico grande demais).
    """
    resposta = cliente.get(f"/repos/{full_name}/contributors", {"per_page": 1, "anon": "true"})
    if resposta.status == 204:  # Repositório vazio.
        return 0
    if not resposta.ok:
        return None
    paginas = ultima_pagina(resposta.link)
    return paginas if paginas is not None else len(resposta.dados or [])


def idade_em_anos(criado_em, referencia):
    return round((referencia - ler_data(criado_em)).days / DIAS_POR_ANO, 2)


def coletar_metadados(cliente, repositorio, referencia):
    """Completa o resumo da busca com idade (até ``referencia``) e contribuidores.

    Estrelas, linguagem e data de criação já vêm da Search API, sem chamada extra.
    """
    return {
        **repositorio,
        "idade_anos": idade_em_anos(repositorio["criado_em"], referencia),
        "contribuidores": contar_contribuidores(cliente, repositorio["full_name"]),
    }
