"""Coleta dos dados reais: PRs de grafana/grafana com e sem bot de revisão.

Só precisa rodar uma vez: o resultado fica versionado em dados/prs.csv e o
dashboard nunca chama a API. Para repetir: python -m src.coleta
Funciona sem token (mais devagar); com GITHUB_TOKEN definido, a pausa diminui.
"""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

REPO = "grafana/grafana"
BOT = "copilot-pull-request-reviewer[bot]"
BOT_APP = "app/copilot-pull-request-reviewer"
INICIO = date(2026, 5, 1)
FIM = date(2026, 10, 31)
POR_MES = 5  # 6 meses x 5 PRs = 30 por grupo
SEMENTE = 42

FILTROS = {
    "com_bot": f"reviewed-by:{BOT}",
    # Quem só recebeu comentário do bot não entra em nenhum grupo.
    "sem_bot": f"-reviewed-by:{BOT} -commenter:{BOT_APP}",
}
# Backports são cópias automáticas de um PR já revisado, para outra branch.
BACKPORT = re.compile(r"^\[(release|v?\d)|backport", re.IGNORECASE)
SAIDA = Path(__file__).resolve().parent.parent / "dados" / "prs.csv"


def buscar(consulta, pagina, token):
    """Uma página da busca do GitHub, esperando se o limite de requisições estourar."""
    url = ("https://api.github.com/search/issues?per_page=100&sort=created"
           f"&page={pagina}&q={urllib.parse.quote(consulta)}")
    cabecalhos = {"User-Agent": "lab04", "Accept": "application/vnd.github+json"}
    if token:
        cabecalhos["Authorization"] = f"Bearer {token}"
    while True:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=cabecalhos),
                                        timeout=30) as resposta:
                return json.load(resposta)
        except urllib.error.HTTPError as erro:
            if erro.code not in (403, 429):
                raise
            print("  limite de requisições atingido; aguardando 60 s", flush=True)
            time.sleep(60)


def janelas():
    """Semanas do período.

    A busca corta em 1.000 resultados e não ordena por data de merge. Consultar
    o semestre inteiro favoreceria PRs abertos há pouco, ou seja, os de merge
    rápido. Em janelas curtas nada é cortado e a população sai completa.
    """
    inicio = INICIO
    while inicio <= FIM:
        fim = min(inicio + timedelta(days=6), FIM)
        yield inicio, fim
        inicio = fim + timedelta(days=1)


def populacao(grupo, token, pausa):
    """Todos os PRs do grupo no período, sem autores bot e sem backports."""
    linhas = []
    for inicio, fim in janelas():
        consulta = (f"repo:{REPO} is:pr is:merged merged:{inicio}..{fim} "
                    f"{FILTROS[grupo]}")
        pagina = 1
        while True:
            resposta = buscar(consulta, pagina, token)
            time.sleep(pausa)
            if resposta.get("incomplete_results"):
                print(f"  aviso: resultado incompleto em {inicio}", flush=True)
            for item in resposta["items"]:
                autor = item["user"]
                if autor["type"] == "Bot" or autor["login"].endswith("[bot]"):
                    continue
                if BACKPORT.search(item["title"]):
                    continue
                linhas.append({"numero": item["number"],
                               "grupo": grupo,
                               "autor": autor["login"],
                               "titulo": item["title"],
                               "criado_em": item["created_at"],
                               "mergeado_em": item["pull_request"]["merged_at"],
                               "url": item["html_url"]})
            if pagina * 100 >= resposta["total_count"]:
                break
            pagina += 1
        print(f"  {grupo} até {fim}: {len(linhas)} PRs", flush=True)
    return pd.DataFrame(linhas).drop_duplicates("numero")


def sortear(pop, rng):
    """Sorteia POR_MES PRs por mês de merge, para os grupos cobrirem o mesmo período."""
    pop = pop.sort_values("numero").copy()
    pop["mes"] = pop["mergeado_em"].str[:7]
    partes = []
    for _, mes in pop.groupby("mes"):
        escolhidos = rng.choice(len(mes), size=POR_MES, replace=False)
        partes.append(mes.iloc[np.sort(escolhidos)])
    return pd.concat(partes)


def main():
    token = os.environ.get("GITHUB_TOKEN")
    pausa = 2.2 if token else 7
    rng = np.random.default_rng(SEMENTE)
    amostras = []
    for grupo in FILTROS:
        pop = populacao(grupo, token, pausa)
        print(f"{grupo}: população de {len(pop)} PRs", flush=True)
        print(pop["autor"].value_counts().head(8).to_string(), flush=True)
        amostras.append(sortear(pop, rng))
    pd.concat(amostras).to_csv(SAIDA, index=False, lineterminator="\n")
    print(f"Gravado em {SAIDA}", flush=True)


if __name__ == "__main__":
    main()
