#!/usr/bin/env python3
# RQ05: Sistemas populares são escritos nas linguagens mais populares
#       Métrica: linguagem primária de cada repositório
#       (referência de "linguagens mais populares" utilizada: GitHub Octoverse)
# RQ06: Sistemas populares possuem um alto percentual de issues fechadas
#       Métrica: razão entre issues fechadas e total de issues
import csv
import getpass
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


GRAPHQL_ENDPOINT = "https://api.github.com/graphql"

MAX_REPOSITORIES = 1000
PAGE_SIZE = 10
MAX_RETRIES = 5
REQUEST_TIMEOUT_SECONDS = 45


GRAPHQL_QUERY = r"""
query SearchRepositories(
    $searchQuery: String!,
    $pageSize: Int!,
    $cursor: String
) {
    search(
        query: $searchQuery,
        type: REPOSITORY,
        first: $pageSize,
        after: $cursor
    ) {
        repositoryCount

        pageInfo {
            hasNextPage
            endCursor
        }

        nodes {
            ... on Repository {
                nameWithOwner
                url

                primaryLanguage {
                    name
                }

                issuesTotal: issues {
                    totalCount
                }

                issuesFechadas: issues(states: CLOSED) {
                    totalCount
                }
            }
        }
    }

    rateLimit {
        cost
        remaining
        resetAt
    }
}
"""


def executar_graphql(token, variaveis):
    corpo = json.dumps({
        "query": GRAPHQL_QUERY,
        "variables": variaveis
    }).encode("utf-8")

    cabecalhos = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "github-rq05-rq06-research"
    }

    for tentativa in range(MAX_RETRIES):
        requisicao = urllib.request.Request(
            GRAPHQL_ENDPOINT,
            data=corpo,
            headers=cabecalhos,
            method="POST"
        )

        try:
            with urllib.request.urlopen(
                requisicao,
                timeout=REQUEST_TIMEOUT_SECONDS
            ) as resposta:

                dados = json.loads(
                    resposta.read().decode("utf-8")
                )

                erros = dados.get("errors") or []

                if erros:
                    mensagem = " | ".join(
                        erro.get("message", "Erro GraphQL")
                        for erro in erros
                    )

                    raise RuntimeError(
                        f"Erro GraphQL: {mensagem}"
                    )

                return dados

        except urllib.error.HTTPError as erro_http:

            if (
                erro_http.code in (429, 502, 503, 504)
                and tentativa < MAX_RETRIES - 1
            ):
                espera = 2 ** tentativa

                print(
                    f"Aviso: HTTP {erro_http.code}. "
                    f"Nova tentativa em {espera}s.",
                    file=sys.stderr
                )

                time.sleep(espera)
                continue

            corpo_erro = erro_http.read().decode(
                "utf-8",
                errors="replace"
            )

            raise RuntimeError(
                f"Falha HTTP {erro_http.code}: {corpo_erro}"
            ) from erro_http

        except urllib.error.URLError as erro_rede:

            if tentativa < MAX_RETRIES - 1:
                espera = 2 ** tentativa

                print(
                    f"Aviso: falha de rede. "
                    f"Nova tentativa em {espera}s.",
                    file=sys.stderr
                )

                time.sleep(espera)
                continue

            raise RuntimeError(
                f"Falha de rede: {erro_rede}"
            ) from erro_rede

    raise RuntimeError(
        "Não foi possível concluir a requisição."
    )


def calcular_percentual_issues_fechadas(issues_total, issues_fechadas):
    if not issues_total:
        return None

    return round(
        (issues_fechadas / issues_total) * 100,
        2
    )


def coletar_repositorios(token, consulta_busca):
    repositorios = []

    cursor = None
    pagina = 0

    while len(repositorios) < MAX_REPOSITORIES:

        tamanho_pagina = min(
            PAGE_SIZE,
            MAX_REPOSITORIES - len(repositorios)
        )

        variaveis = {
            "searchQuery": consulta_busca,
            "pageSize": tamanho_pagina,
            "cursor": cursor
        }

        resposta = executar_graphql(
            token,
            variaveis
        )

        resultado_busca = resposta["data"]["search"]
        limite = resposta["data"]["rateLimit"]

        pagina += 1

        for repositorio in resultado_busca.get("nodes") or []:

            if not repositorio:
                continue

            linguagem_primaria = repositorio.get("primaryLanguage")

            issues_total = (
                repositorio.get("issuesTotal") or {}
            ).get("totalCount", 0)

            issues_fechadas = (
                repositorio.get("issuesFechadas") or {}
            ).get("totalCount", 0)

            repositorios.append({
                "repositorio": repositorio.get("nameWithOwner"),
                "url": repositorio.get("url"),
                "linguagem_primaria": (
                    linguagem_primaria.get("name")
                    if linguagem_primaria else None
                ),
                "issues_total": issues_total,
                "issues_fechadas": issues_fechadas,
                "percentual_issues_fechadas": (
                    calcular_percentual_issues_fechadas(
                        issues_total,
                        issues_fechadas
                    )
                )
            })

            if len(repositorios) >= MAX_REPOSITORIES:
                break

        print(
            f"Página {pagina}: "
            f"total={len(repositorios)}; "
            f"custo={limite.get('cost')}; "
            f"pontos_restantes={limite.get('remaining')}",
            file=sys.stderr
        )

        pagina_info = resultado_busca.get("pageInfo") or {}

        if not pagina_info.get("hasNextPage"):
            break

        novo_cursor = pagina_info.get("endCursor")

        if not novo_cursor or novo_cursor == cursor:
            break

        cursor = novo_cursor

    return repositorios


def salvar_csv_rq05(repositorios, caminho_saida):

    campos = [
        "repositorio",
        "url",
        "linguagem_primaria"
    ]

    with open(
        caminho_saida,
        "w",
        encoding="utf-8",
        newline=""
    ) as arquivo:

        escritor = csv.DictWriter(
            arquivo,
            fieldnames=campos,
            extrasaction="ignore"
        )

        escritor.writeheader()
        escritor.writerows(repositorios)


def salvar_csv_rq06(repositorios, caminho_saida):

    campos = [
        "repositorio",
        "url",
        "issues_total",
        "issues_fechadas",
        "percentual_issues_fechadas"
    ]

    with open(
        caminho_saida,
        "w",
        encoding="utf-8",
        newline=""
    ) as arquivo:

        escritor = csv.DictWriter(
            arquivo,
            fieldnames=campos,
            extrasaction="ignore"
        )

        escritor.writeheader()
        escritor.writerows(repositorios)


def obter_token():
    token = os.environ.get("GITHUB_TOKEN")

    if token:
        return token

    token = getpass.getpass(
        "Informe seu token de acesso do GitHub "
        "(entrada oculta, não será exibida nem salva): "
    ).strip()

    if not token:
        raise SystemExit(
            "Nenhum token informado. Operação cancelada."
        )

    return token


def main():

    token = obter_token()

    consulta_busca = (
        " ".join(sys.argv[1:]).strip()
        or "stars:>=1 sort:stars-desc"
    )

    repositorios = coletar_repositorios(
        token,
        consulta_busca
    )

    arquivo_rq05 = "rq05_linguagem.csv"
    arquivo_rq06 = "rq06_issues.csv"

    salvar_csv_rq05(
        repositorios,
        arquivo_rq05
    )

    salvar_csv_rq06(
        repositorios,
        arquivo_rq06
    )

    print(
        f"RQ05: {os.path.abspath(arquivo_rq05)}"
    )

    print(
        f"RQ06: {os.path.abspath(arquivo_rq06)}"
    )

    print(
        f"Concluído: "
        f"{len(repositorios)} repositórios coletados."
    )


if __name__ == "__main__":
    main()
