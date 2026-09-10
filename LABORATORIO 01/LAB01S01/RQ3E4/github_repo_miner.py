#!/usr/bin/env python3
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

GRAPHQL_QUERY = r'''
query SearchRepositories($searchQuery: String!, $pageSize: Int!, $cursor: String) {
  search(query: $searchQuery, type: REPOSITORY, first: $pageSize, after: $cursor) {
    repositoryCount
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      ... on Repository {
        nameWithOwner
        url
        updatedAt
        releases(first: 1) {
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
'''


def executar_graphql(token, variaveis):
    corpo = json.dumps({"query": GRAPHQL_QUERY, "variables": variaveis}).encode("utf-8")
    cabecalhos = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "github-rq03-rq04-research"}
    for tentativa in range(MAX_RETRIES):
        requisicao = urllib.request.Request(GRAPHQL_ENDPOINT, data=corpo, headers=cabecalhos, method="POST")
        try:
            with urllib.request.urlopen(requisicao, timeout=REQUEST_TIMEOUT_SECONDS) as resposta:
                dados = json.loads(resposta.read().decode("utf-8"))
                erros = dados.get("errors") or []
                if erros:
                    mensagem = " | ".join(erro.get("message", "Erro GraphQL") for erro in erros)
                    raise RuntimeError(f"Erro GraphQL: {mensagem}")
                return dados
        except urllib.error.HTTPError as erro_http:
            if erro_http.code in (429, 502, 503, 504) and tentativa < MAX_RETRIES - 1:
                espera = 2 ** tentativa
                print(f"Aviso: HTTP {erro_http.code}. Nova tentativa em {espera}s.", file=sys.stderr)
                time.sleep(espera)
                continue
            corpo_erro = erro_http.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Falha HTTP {erro_http.code}: {corpo_erro}") from erro_http
        except urllib.error.URLError as erro_rede:
            if tentativa < MAX_RETRIES - 1:
                espera = 2 ** tentativa
                print(f"Aviso: falha de rede. Nova tentativa em {espera}s.", file=sys.stderr)
                time.sleep(espera)
                continue
            raise RuntimeError(f"Falha de rede: {erro_rede}") from erro_rede
    raise RuntimeError("Não foi possível concluir a requisição.")


def calcular_dias_desde_atualizacao(data_atualizacao, data_coleta):
    if not data_atualizacao:
        return None
    atualizacao = datetime.fromisoformat(data_atualizacao.replace("Z", "+00:00"))
    diferenca = data_coleta - atualizacao
    return round(diferenca.total_seconds() / 86400, 2)


def coletar_repositorios(token, consulta_busca):
    repositorios = []
    cursor = None
    pagina = 0
    data_coleta = datetime.now(timezone.utc)
    while len(repositorios) < MAX_REPOSITORIES:
        tamanho_pagina = min(PAGE_SIZE, MAX_REPOSITORIES - len(repositorios))
        variaveis = {"searchQuery": consulta_busca, "pageSize": tamanho_pagina, "cursor": cursor}
        resposta = executar_graphql(token, variaveis)
        resultado_busca = resposta["data"]["search"]
        limite = resposta["data"]["rateLimit"]
        pagina += 1
        for repositorio in resultado_busca.get("nodes") or []:
            if not repositorio:
                continue
            ultima_atualizacao = repositorio.get("updatedAt")
            repositorios.append({"repositorio": repositorio.get("nameWithOwner"), "url": repositorio.get("url"), "total_releases": (repositorio.get("releases") or {}).get("totalCount", 0), "ultima_atualizacao": ultima_atualizacao, "dias_desde_ultima_atualizacao": calcular_dias_desde_atualizacao(ultima_atualizacao, data_coleta)})
            if len(repositorios) >= MAX_REPOSITORIES:
                break
        print(f"Página {pagina}: total={len(repositorios)}; custo={limite.get('cost')}; pontos_restantes={limite.get('remaining')}", file=sys.stderr)
        pagina_info = resultado_busca.get("pageInfo") or {}
        if not pagina_info.get("hasNextPage"):
            break
        novo_cursor = pagina_info.get("endCursor")
        if not novo_cursor or novo_cursor == cursor:
            break
        cursor = novo_cursor
    return repositorios


def salvar_csv_rq03(repositorios, caminho_saida):
    campos = ["repositorio", "url", "total_releases"]
    with open(caminho_saida, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(repositorios)


def salvar_csv_rq04(repositorios, caminho_saida):
    campos = ["repositorio", "url", "ultima_atualizacao", "dias_desde_ultima_atualizacao"]
    with open(caminho_saida, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(repositorios)


def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Defina a variável de ambiente GITHUB_TOKEN antes de executar o script.")
    consulta_busca = " ".join(sys.argv[1:]).strip() or "stars:>=1 sort:stars-desc"
    repositorios = coletar_repositorios(token, consulta_busca)
    arquivo_rq03 = "rq03_releases.csv"
    arquivo_rq04 = "rq04_atualizacao.csv"
    dados_rq03 = [{"repositorio": repositorio["repositorio"], "url": repositorio["url"], "total_releases": repositorio["total_releases"]} for repositorio in repositorios]
    dados_rq04 = [{"repositorio": repositorio["repositorio"], "url": repositorio["url"], "ultima_atualizacao": repositorio["ultima_atualizacao"], "dias_desde_ultima_atualizacao": repositorio["dias_desde_ultima_atualizacao"]} for repositorio in repositorios]
    salvar_csv_rq03(dados_rq03, arquivo_rq03)
    salvar_csv_rq04(dados_rq04, arquivo_rq04)
    print(f"RQ03: {os.path.abspath(arquivo_rq03)}")
    print(f"RQ04: {os.path.abspath(arquivo_rq04)}")
    print(f"Concluído: {len(repositorios)} repositórios coletados.")


if __name__ == "__main__":
    main()