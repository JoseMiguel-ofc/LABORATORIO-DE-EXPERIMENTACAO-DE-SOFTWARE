import csv
import json
import os
import urllib.request


GRAPHQL_ENDPOINT = "https://api.github.com/graphql"


OWNER = "JoseMiguel-ofc"


PROJECT_NUMBER = 1

ARQUIVO_SAIDA = "snapshot_lab01s03.csv"


GRAPHQL_QUERY = r"""
query ProjectSnapshot(
    $owner: String!,
    $projectNumber: Int!,
    $cursor: String
) {
    user(login: $owner) {
        projectV2(number: $projectNumber) {
            title

            items(first: 100, after: $cursor) {
                pageInfo {
                    hasNextPage
                    endCursor
                }

                nodes {
                    id

                    content {
                        ... on Issue {
                            number
                            title
                            url
                            state

                            repository {
                                nameWithOwner
                            }

                            assignees(first: 10) {
                                nodes {
                                    login
                                }
                            }
                        }
                    }

                    fieldValues(first: 20) {
                        nodes {
                            ... on ProjectV2ItemFieldSingleSelectValue {
                                name

                                field {
                                    ... on ProjectV2SingleSelectField {
                                        name
                                    }
                                }
                            }
                        }
                    }
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
        "User-Agent": "lab01-project-snapshot"
    }

    requisicao = urllib.request.Request(
        GRAPHQL_ENDPOINT,
        data=corpo,
        headers=cabecalhos,
        method="POST"
    )

    with urllib.request.urlopen(requisicao) as resposta:
        dados = json.loads(
            resposta.read().decode("utf-8")
        )

    if dados.get("errors"):
        mensagens = [
            erro.get("message", "Erro GraphQL")
            for erro in dados["errors"]
        ]

        raise RuntimeError(
            " | ".join(mensagens)
        )

    return dados


def obter_status(item):
    field_values = (
        item.get("fieldValues") or {}
    ).get("nodes") or []

    for valor in field_values:
        if not valor:
            continue

        campo = valor.get("field") or {}

        if campo.get("name") == "Status":
            return valor.get("name")

    return None


def coletar_snapshot(token):
    itens = []
    cursor = None

    while True:
        variaveis = {
            "owner": OWNER,
            "projectNumber": PROJECT_NUMBER,
            "cursor": cursor
        }

        resposta = executar_graphql(
            token,
            variaveis
        )

        usuario = resposta["data"]["user"]

        if not usuario:
            raise RuntimeError(
                f"Usuário '{OWNER}' não encontrado."
            )

        projeto = usuario["projectV2"]

        if not projeto:
            raise RuntimeError(
                f"Project #{PROJECT_NUMBER} não encontrado."
            )

        resultado = projeto["items"]

        for item in resultado["nodes"]:
            conteudo = item.get("content")

            # ignora itens sem Issue associada
            if not conteudo:
                continue

            numero = conteudo.get("number")

            # ignora itens que não sejam Issues
            if numero is None:
                continue

            responsaveis = [
                pessoa["login"]
                for pessoa in (
                    conteudo.get("assignees") or {}
                ).get("nodes", [])
            ]

            itens.append({
                "issue": numero,
                "titulo": conteudo.get("title"),
                "status": obter_status(item),
                "responsavel": ", ".join(responsaveis),
                "estado_issue": conteudo.get("state"),
                "repositorio": (
                    conteudo.get("repository") or {}
                ).get("nameWithOwner"),
                "url": conteudo.get("url")
            })

        pagina = resultado["pageInfo"]

        limite = resposta["data"]["rateLimit"]

        print(
            f"Itens coletados: {len(itens)} | "
            f"custo={limite['cost']} | "
            f"restantes={limite['remaining']}"
        )

        if not pagina["hasNextPage"]:
            break

        cursor = pagina["endCursor"]

    return itens


def salvar_csv(itens):
    campos = [
        "issue",
        "titulo",
        "status",
        "responsavel",
        "estado_issue",
        "repositorio",
        "url"
    ]

    with open(
        ARQUIVO_SAIDA,
        "w",
        encoding="utf-8",
        newline=""
    ) as arquivo:

        escritor = csv.DictWriter(
            arquivo,
            fieldnames=campos
        )

        escritor.writeheader()
        escritor.writerows(itens)


def main():
    token = os.environ.get("GITHUB_TOKEN")

    if not token:
        raise SystemExit(
            "Defina GITHUB_TOKEN antes de executar."
        )

    itens = coletar_snapshot(token)

    salvar_csv(itens)

    print(
        f"\nSnapshot concluído: "
        f"{len(itens)} Issues exportadas."
    )

    print(
        f"Arquivo: {os.path.abspath(ARQUIVO_SAIDA)}"
    )


if __name__ == "__main__":
    main()
