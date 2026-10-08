"""Comparações entre tags com paginação explícita e diagnóstico de falhas."""

from urllib.parse import parse_qs, quote, urlparse


def _proxima_pagina(link):
    for parte in (link or "").split(","):
        if 'rel="next"' in parte:
            url = parte.split(";", 1)[0].strip().strip("<>")
            return int(parse_qs(urlparse(url).query)["page"][0])
    return None


def normalizar_commit(commit):
    dados = commit.get("commit") or {}
    return {"sha": commit.get("sha", ""), "message": dados.get("message", ""),
            "author_date": (dados.get("author") or {}).get("date"),
            "committer_date": (dados.get("committer") or {}).get("date")}


def coletar_commits_entre_releases(cliente, full_name, base_tag, head_tag):
    """Retorna ``commits=None`` em erro, preservando a diferença de lista vazia.

    Sem ``per_page`` o GitHub limita compare a 250 commits. Aqui pedimos páginas
    de 100, seguimos Link e verificamos ``total_commits``. Uma falha em qualquer
    página invalida a comparação inteira para não calcular métricas parciais.
    """
    if not base_tag or not head_tag:
        return {"commits": None, "status": "tag_ausente", "http_status": None}
    base, head = quote(str(base_tag), safe=""), quote(str(head_tag), safe="")
    caminho = f"/repos/{full_name}/compare/{base}...{head}"
    pagina, visitadas, commits, vistos = 1, set(), [], set()
    total = None
    while pagina is not None:
        if pagina in visitadas:
            return {"commits": None, "status": "paginacao_incompleta", "http_status": 200}
        visitadas.add(pagina)
        resposta = cliente.get(caminho, {"per_page": 100, "page": pagina})
        if not resposta.ok:
            return {"commits": None, "status": f"http_{resposta.status}",
                    "http_status": resposta.status}
        dados = resposta.dados
        if not isinstance(dados, dict) or not isinstance(dados.get("commits"), list):
            return {"commits": None, "status": "dados_invalidos", "http_status": resposta.status}
        if total is None:
            total = dados.get("total_commits")
        antes = len(commits)
        for commit in dados["commits"]:
            sha = commit.get("sha")
            if not sha:
                return {"commits": None, "status": "dados_invalidos", "http_status": resposta.status}
            if sha not in vistos:
                vistos.add(sha)
                commits.append(normalizar_commit(commit))
        proxima = _proxima_pagina(resposta.link)
        if proxima is None and total is not None and len(commits) < total:
            proxima = pagina + 1
        if proxima is not None and len(commits) == antes:
            return {"commits": None, "status": "paginacao_incompleta", "http_status": resposta.status}
        pagina = proxima
    if total is not None and len(commits) != total:
        return {"commits": None, "status": "paginacao_incompleta", "http_status": 200}
    return {"commits": commits, "status": "ok" if commits else "sem_commits", "http_status": 200}
