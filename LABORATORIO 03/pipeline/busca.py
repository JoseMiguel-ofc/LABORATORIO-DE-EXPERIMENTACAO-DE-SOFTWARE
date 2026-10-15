"""Busca de repositórios candidatos e descarte dos que não usam GitHub Actions.

A Search API devolve no máximo 1.000 resultados por consulta. Para passar desse
teto, a busca é fatiada em faixas de estrelas que não se sobrepõem; cada faixa
é uma consulta separada, e os resultados são unidos sem duplicatas. Uma faixa
com mais de 1.000 repositórios é dividida ao meio automaticamente até caber.
"""

import logging


LIMITE_BUSCA = 1000
POR_PAGINA = 100

log = logging.getLogger(__name__)


def montar_consulta(minimo, maximo=None, filtro_extra=""):
    """Faixa fechada ``minimo..maximo``; sem máximo, vira ``>=minimo``."""
    estrelas = f"stars:>={minimo}" if maximo is None else f"stars:{minimo}..{maximo}"
    return f"{estrelas} {filtro_extra}".strip()


def validar_faixas(faixas):
    """Garante faixas em ordem crescente e sem sobreposição (senão haveria duplicatas)."""
    for i, (minimo, maximo) in enumerate(faixas):
        if maximo is not None and maximo < minimo:
            raise ValueError(f"Faixa inválida: {minimo}..{maximo}")
        if maximo is None and i != len(faixas) - 1:
            raise ValueError("Só a última faixa pode ficar sem máximo")
        if i and faixas[i - 1][1] is not None and minimo <= faixas[i - 1][1]:
            raise ValueError(f"Faixas sobrepostas em {minimo}")


def resumir_repositorio(item):
    return {
        "full_name": item["full_name"],
        "estrelas": item["stargazers_count"],
        "linguagem": item.get("language") or "",
        "criado_em": item["created_at"],
        "default_branch": item["default_branch"],
        "url": item["html_url"],
    }


def buscar_candidatos(cliente, faixas, filtro_extra=""):
    validar_faixas(faixas)
    candidatos = {}
    for minimo, maximo in faixas:
        _buscar_faixa(cliente, minimo, maximo, filtro_extra, candidatos)
    return list(candidatos.values())


def _buscar_faixa(cliente, minimo, maximo, filtro_extra, candidatos):
    consulta = montar_consulta(minimo, maximo, filtro_extra)
    params = {"q": consulta, "sort": "stars", "order": "desc", "per_page": POR_PAGINA}
    primeira = cliente.get("/search/repositories", params)
    if not primeira.ok:
        log.warning("Busca '%s' retornou HTTP %s", consulta, primeira.status)
        return
    total = primeira.dados["total_count"]
    if total > LIMITE_BUSCA:
        if maximo is not None and maximo > minimo:
            meio = (minimo + maximo) // 2
            log.info("Faixa '%s' tem %d repositórios; dividindo em %d..%d e %d..%d",
                     consulta, total, minimo, meio, meio + 1, maximo)
            _buscar_faixa(cliente, minimo, meio, filtro_extra, candidatos)
            _buscar_faixa(cliente, meio + 1, maximo, filtro_extra, candidatos)
            return
        # Faixa aberta (>=N) ou de um único valor: não há como dividir por estrelas.
        log.warning("Faixa '%s' tem %d repositórios e não pode ser dividida; só os %d "
                    "primeiros são acessíveis.", consulta, total, LIMITE_BUSCA)
    paginas = -(-min(total, LIMITE_BUSCA) // POR_PAGINA)
    for item in cliente.paginar("/search/repositories", params, chave="items",
                                max_paginas=paginas):
        candidatos.setdefault(item["full_name"], resumir_repositorio(item))
    log.info("Faixa '%s': %d no total, %d candidatos acumulados",
             consulta, total, len(candidatos))


def tem_actions(cliente, full_name):
    """``True`` se o repositório tem algum workflow; ``None`` se a API não respondeu."""
    resposta = cliente.get(f"/repos/{full_name}/actions/workflows", {"per_page": 1})
    if not resposta.ok:
        return None
    return resposta.dados["total_count"] > 0
