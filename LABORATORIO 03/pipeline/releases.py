"""Coleta da Pessoa B: releases, tags, commits e métricas de entrega.

Usa somente o cliente recebido do pipeline. Exporta o histórico de releases,
incluindo a predecessora anterior à janela; apenas releases estáveis na janela
entram no lead time de referência. Pré-releases não substituem essa predecessora.
"""

import csv
from datetime import datetime, time, timezone
import logging
from pathlib import Path
from urllib.parse import quote

from metricas.frequencia import data_da_janela, frequencia_por_semana, semanas_da_janela
from metricas.lead_time import calcular_lead_times, horas_ate_publicacao, instante, resumir_lead_times
from pipeline.commits import coletar_commits_entre_releases, normalizar_commit


log = logging.getLogger(__name__)
COLUNAS_RELEASES = ["full_name", "release_id", "tag_name", "draft", "prerelease",
                    "published_at", "url", "na_janela", "tag_anterior", "commits_status",
                    "commits_novos", "lead_time_a_horas"]
COLUNAS_TAGS = ["full_name", "tag_name", "sha", "committer_date", "author_date",
                "na_janela", "status"]
COLUNAS_COMMITS = ["full_name", "release_id", "tag_name", "tag_anterior", "sha", "message",
                   "author_date", "committer_date", "published_at", "lead_time_horas"]
COLUNAS_METRICAS = ["full_name", "inicio", "fim", "semanas_janela", "releases_status",
                    "tags_status", "releases_janela", "tags_janela", "tags_ignoradas",
                    "frequencia_releases_semana", "lead_time_a_horas", "lead_time_b_horas",
                    "releases_com_lead_time", "commits_com_lead_time",
                    "commits_datas_invalidas", "releases_ignoradas", "releases_primeira_historia",
                    "releases_sem_commits", "releases_erro_compare", "releases_compare_404"]


def _limites(inicio, fim):
    semanas_da_janela(inicio, fim)  # valida antes de qualquer requisição
    return (datetime.combine(data_da_janela(inicio), time.min, timezone.utc),
            datetime.combine(data_da_janela(fim), time.max, timezone.utc))


def _listar(cliente, caminho):
    """A consulta inicial diferencia endpoint indisponível de lista vazia."""
    resposta = cliente.get(caminho, {"per_page": 100})
    if not resposta.ok:
        return None, f"http_{resposta.status}"
    if resposta.status == 204:
        return [], "ok"
    if not isinstance(resposta.dados, list):
        return None, "dados_invalidos"
    # O cliente central reaproveita a primeira página pelo cache.
    return list(cliente.paginar(caminho, {"per_page": 100})), "ok"


def coletar_releases(cliente, full_name, inicio, fim):
    """Devolve histórico normalizado e status; não pressupõe ordem por publicação."""
    inicio, fim = _limites(inicio, fim)
    itens, status = _listar(cliente, f"/repos/{full_name}/releases")
    if itens is None:
        return [], status
    resultado, vistos = [], set()
    for item in itens:
        chave = item.get("id")
        if chave is None:
            chave = (item.get("tag_name"), item.get("published_at"), bool(item.get("draft")))
        if chave in vistos:
            continue
        vistos.add(chave)
        publicada = instante(item.get("published_at"))
        resultado.append({"full_name": full_name, "release_id": item.get("id", ""),
                          "tag_name": item.get("tag_name", ""),
                          "draft": bool(item.get("draft")),
                          "prerelease": bool(item.get("prerelease")),
                          "published_at": item.get("published_at"),
                          "url": item.get("html_url", ""),
                          "na_janela": publicada is not None and inicio <= publicada <= fim,
                          "tag_anterior": "", "commits_status": "nao_aplicavel",
                          "commits_novos": None, "lead_time_a_horas": None,
                          "commits": None})
    resultado.sort(key=lambda r: (instante(r["published_at"]) or datetime.min.replace(
        tzinfo=timezone.utc), str(r["release_id"]), r["tag_name"]))
    return resultado, status


def coletar_tags(cliente, full_name, inicio, fim):
    """A janela de tags usa a data de autoria do commit apontado, nunca a data da tag."""
    inicio, fim = _limites(inicio, fim)
    itens, status = _listar(cliente, f"/repos/{full_name}/tags")
    if itens is None:
        return [], status
    resultado, vistos, por_sha = [], set(), {}
    for item in itens:
        nome = item.get("name", "")
        if nome in vistos:
            continue
        vistos.add(nome)
        sha = (item.get("commit") or {}).get("sha", "")
        linha = {"full_name": full_name, "tag_name": nome, "sha": sha,
                 "committer_date": None, "author_date": None,
                 "na_janela": False, "status": "sha_ausente"}
        if sha:
            if sha not in por_sha:
                resposta = cliente.get(f"/repos/{full_name}/commits/{quote(sha, safe='')}")
                if resposta.ok and isinstance(resposta.dados, dict):
                    por_sha[sha] = normalizar_commit(resposta.dados), "ok"
                else:
                    por_sha[sha] = {}, f"http_{resposta.status}" if not resposta.ok else "dados_invalidos"
            commit, linha["status"] = por_sha[sha]
            linha.update({campo: commit.get(campo) for campo in ("committer_date", "author_date")})
            data = instante(linha["author_date"])
            if linha["status"] == "ok" and data is None:
                linha["status"] = "data_ausente"
            linha["na_janela"] = data is not None and inicio <= data <= fim
        resultado.append(linha)
    return resultado, status


def enriquecer_commits(cliente, full_name, releases):
    """Compara cada release estável elegível com a estável anterior da história."""
    anterior, linhas = None, []
    for release in releases:
        if release["draft"] or release["prerelease"] or instante(release["published_at"]) is None:
            continue
        release["tag_anterior"] = anterior["tag_name"] if anterior else ""
        if not release["na_janela"]:
            release["commits_status"] = "fora_janela"
        elif anterior is None:
            release["commits_status"] = "primeira_release"
        else:
            comparacao = coletar_commits_entre_releases(
                cliente, full_name, anterior["tag_name"], release["tag_name"])
            release["commits_status"] = comparacao["status"]
            release["commits"] = comparacao["commits"]
            release["commits_novos"] = (len(comparacao["commits"])
                                          if comparacao["commits"] is not None else None)
            lt = calcular_lead_times(release["published_at"], release["commits"])
            release["lead_time_a_horas"] = lt["lead_time_a_horas"]
            for commit in release["commits"] or []:
                linhas.append({"full_name": full_name, "release_id": release["release_id"],
                               "tag_name": release["tag_name"], "tag_anterior": release["tag_anterior"],
                               **commit, "published_at": release["published_at"],
                               "lead_time_horas": horas_ate_publicacao(release["published_at"], commit)})
        anterior = release
    return linhas


def _resumir(full_name, releases, tags, status_releases, status_tags, inicio, fim):
    estaveis = [r for r in releases if r["na_janela"] and not r["draft"] and not r["prerelease"]]
    n_estaveis = len(estaveis) if status_releases == "ok" else None
    tags_ignoradas = sum(t["status"] != "ok" for t in tags)
    n_tags = sum(t["na_janela"] for t in tags) if status_tags == "ok" and not tags_ignoradas else None
    resumo = {"full_name": full_name, "inicio": data_da_janela(inicio), "fim": data_da_janela(fim),
              "semanas_janela": semanas_da_janela(inicio, fim),
              "releases_status": status_releases, "tags_status": status_tags,
              "releases_janela": n_estaveis,
              "tags_janela": n_tags, "tags_ignoradas": tags_ignoradas,
              "frequencia_releases_semana": frequencia_por_semana(n_estaveis, inicio, fim),
              **resumir_lead_times(estaveis)}
    resumo.update(releases_ignoradas=len(estaveis) - resumo["releases_com_lead_time"],
                  releases_primeira_historia=sum(r["commits_status"] == "primeira_release" for r in estaveis),
                  releases_sem_commits=sum(r["commits_status"] == "sem_commits" for r in estaveis),
                  releases_compare_404=sum(r["commits_status"] == "http_404" for r in estaveis),
                  releases_erro_compare=sum(r["commits_status"] not in {
                      "ok", "sem_commits", "primeira_release"} for r in estaveis))
    return resumo


def _escrever_csv(caminho, linhas, colunas):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    with temporario.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(linhas)
    temporario.replace(caminho)


def coletar(cliente, amostra, config):
    """Ponto de integração já chamado por ``python -m pipeline``.

    Retorna também as tabelas em memória para testes de integração.
    Métricas indisponíveis são ``None`` e aparecem como célula vazia no CSV.
    """
    inicio, fim = config["janela"]["inicio"], config["janela"]["fim"]
    _limites(inicio, fim)
    # Tags custam uma chamada por tag (data do commit apontado) e só servem à
    # variante da RQ 07; por isso a coleta é opcional.
    coletar_tags_ativo = (config.get("tags") or {}).get("coletar", False)
    tabelas = {"releases": [], "tags": [], "commits": [], "metricas_entrega": []}
    vistos = set()
    for repositorio in amostra:
        nome = repositorio["full_name"]
        if nome in vistos:
            continue
        vistos.add(nome)
        releases, status_releases = coletar_releases(cliente, nome, inicio, fim)
        if coletar_tags_ativo:
            tags, status_tags = coletar_tags(cliente, nome, inicio, fim)
        else:
            tags, status_tags = [], "nao_coletado"
        commits = enriquecer_commits(cliente, nome, releases)
        resumo = _resumir(nome, releases, tags, status_releases, status_tags, inicio, fim)
        tabelas["releases"].extend(releases)
        tabelas["tags"].extend(tags)
        tabelas["commits"].extend(commits)
        tabelas["metricas_entrega"].append(resumo)
        log.info("%s: %s releases na janela, %d com lead time; %d ignoradas (%d compare 404)",
                 nome, resumo["releases_janela"], resumo["releases_com_lead_time"],
                 resumo["releases_ignoradas"], resumo["releases_compare_404"])
    saida = Path(config["saida"]["dir"])
    for nome, colunas in [("releases", COLUNAS_RELEASES), ("tags", COLUNAS_TAGS),
                          ("commits", COLUNAS_COMMITS), ("metricas_entrega", COLUNAS_METRICAS)]:
        _escrever_csv(saida / f"{nome}.csv", tabelas[nome], colunas)
    return tabelas
