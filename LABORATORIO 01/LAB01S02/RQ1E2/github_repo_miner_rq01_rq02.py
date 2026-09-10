#!/usr/bin/env python3
# RQ01: Sistemas populares são maduros/antigos
#       Métrica: idade do repositório (calculado a partir da data de sua criação)
import csv
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
                createdAt

                pullRequests(states: MERGED) {
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
        "User-Agent": "github-rq01-rq02-research"
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


def calcular_idade_repositorio(data_criacao, data_coleta):
    if not data_criacao:
        return None

    criacao = datetime.fromisoformat(
        data_criacao.replace("Z", "+00:00")
    )

    diferenca = data_coleta - criacao

    return round(
        diferenca.total_seconds() / (86400 * 365.25),
        2
    )


def coletar_repositorios(token, consulta_busca):
    repositorios = []

    cursor = None
    pagina = 0

    data_coleta = datetime.now(timezone.utc)

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

            data_criacao = repositorio.get("createdAt")

            total_pull_requests = (
                repositorio.get("pullRequests") or {}
            ).get("totalCount", 0)

            repositorios.append({
                "repositorio": repositorio.get("nameWithOwner"),
                "url": repositorio.get("url"),
                "data_criacao": data_criacao,
                "idade_anos": calcular_idade_repositorio(
                    data_criacao,
                    data_coleta
                ),
                "pull_requests_aceitas": total_pull_requests
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


def salvar_csv_rq01(repositorios, caminho_saida):

    campos = [
        "repositorio",
        "url",
        "data_criacao",
        "idade_anos"
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


def salvar_csv_rq02(repositorios, caminho_saida):

    campos = [
        "repositorio",
        "url",
        "pull_requests_aceitas"
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


def main():

    token = os.environ.get("GITHUB_TOKEN")

    if not token:
        raise SystemExit(
            "Defina a variável de ambiente "
            "GITHUB_TOKEN antes de executar o script."
        )

    consulta_busca = (
        " ".join(sys.argv[1:]).strip()
        or "stars:>=1 sort:stars-desc"
    )

    repositorios = coletar_repositorios(
        token,
        consulta_busca
    )

    arquivo_rq01 = "rq01_idade.csv"
    arquivo_rq02 = "rq02_pull_requests.csv"

    salvar_csv_rq01(
        repositorios,
        arquivo_rq01
    )

    salvar_csv_rq02(
        repositorios,
        arquivo_rq02
    )

    print(
        f"RQ01: {os.path.abspath(arquivo_rq01)}"
    )

    print(
        f"RQ02: {os.path.abspath(arquivo_rq02)}"
    )

    print(
        f"Concluído: "
        f"{len(repositorios)} repositórios coletados."
    )


if __name__ == "__main__":
    main()
