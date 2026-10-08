"""Ponto de entrada único: ``python -m pipeline --config config.yaml``."""

import argparse
import csv
import importlib
import logging
import os
from pathlib import Path
import random
import sys

import yaml

from pipeline.busca import buscar_candidatos, tem_actions
from pipeline.funil import (ETAPAS, NAO_AVALIADO, avaliar_contagens, contar_releases_na_janela,
                            contar_runs_validos, limites_da_janela, montar_funil)
from pipeline.metadados import coletar_metadados


# Coletas detalhadas das Pessoas B e C. Cada módulo expõe
# ``coletar(cliente, amostra, config)`` e roda só sobre a amostra aprovada.
ETAPAS_DE_COLETA = ["pipeline.releases", "pipeline.runs"]
MOTIVOS = {chave: motivo for chave, _, motivo in ETAPAS}
MOTIVOS[NAO_AVALIADO] = "não avaliado: amostra-alvo já atingida"

log = logging.getLogger("pipeline")


def carregar_config(caminho):
    caminho = Path(caminho).resolve()
    config = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    base = caminho.parent
    config["saida"]["dir"] = base / config["saida"]["dir"]
    config["saida"]["cache_dir"] = base / config["saida"]["cache_dir"]
    return config


def escrever_csv(caminho, linhas, colunas):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(linhas)


def selecionar_amostra(cliente, candidatos, inicio, fim, tamanho, minimos):
    """Aplica os filtros em ordem até a amostra atingir ``tamanho`` (``None`` = todos)."""
    amostra, descartes = [], {}
    for i, repo in enumerate(candidatos, 1):
        nome = repo["full_name"]
        if tamanho is not None and len(amostra) >= tamanho:
            descartes[nome] = NAO_AVALIADO
            continue

        actions = tem_actions(cliente, nome)
        if not actions:
            descartes[nome] = "acessivel" if actions is None else "actions"
            continue
        n_releases = contar_releases_na_janela(cliente, nome, inicio, fim)
        n_runs = None
        if n_releases >= minimos["releases"]:
            n_runs = contar_runs_validos(cliente, nome, repo["default_branch"], inicio, fim)
            if n_runs is None:
                descartes[nome] = "acessivel"
                continue
        etapa = avaliar_contagens(n_releases, n_runs, minimos["releases"], minimos["runs"])
        descartes[nome] = etapa
        if etapa is None:
            amostra.append({**coletar_metadados(cliente, repo, fim),
                            "releases_janela": n_releases, "runs_validos_janela": n_runs})
        log.info("[%d/%d] %s: %s (amostra: %d)", i, len(candidatos), nome,
                 "aprovado" if etapa is None else MOTIVOS[etapa], len(amostra))
    return amostra, descartes


def executar_coletas_detalhadas(cliente, amostra, config):
    for nome_modulo in ETAPAS_DE_COLETA:
        try:
            modulo = importlib.import_module(nome_modulo)
        except ModuleNotFoundError as erro:
            if erro.name != nome_modulo:
                raise
            log.warning("Etapa %s ainda não implementada; pulando.", nome_modulo)
            continue
        log.info("Executando %s", nome_modulo)
        modulo.coletar(cliente, amostra, config)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Pipeline de mineração de métricas DORA")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    config = carregar_config(args.config)
    variavel = config["github"]["token_env"]
    token = os.environ.get(variavel)
    if not token:
        sys.exit(f"Defina a variável de ambiente {variavel} com um token do GitHub.")

    saida = config["saida"]["dir"]
    # Cliente com cache, rate limit e backoff: pipeline/api_client.py (Pessoa C).
    # Os módulos daqui só usam get(caminho, params) -> resposta com .status,
    # .dados, .link e .ok, e paginar(caminho, params, chave=None, max_paginas=None).
    try:
        from pipeline.api_client import ClienteGitHub
    except ModuleNotFoundError as erro:
        if erro.name != "pipeline.api_client":
            raise
        sys.exit("Coleta real indisponível: falta pipeline/api_client.py (Pessoa C). "
                 "Os módulos da Pessoa B podem ser validados sem rede com python -m pytest.")
    cliente = ClienteGitHub(token, config["saida"]["cache_dir"])
    inicio, fim = limites_da_janela(config["janela"]["inicio"], config["janela"]["fim"])
    faixas = [(f["min"], f.get("max")) for f in config["busca"]["faixas_estrelas"]]

    candidatos = buscar_candidatos(cliente, faixas, config["busca"].get("filtro_extra", ""))
    escrever_csv(saida / "candidatos.csv", candidatos, list(candidatos[0]) if candidatos else [])

    # Ordena antes de embaralhar: a ordem da Search API pode variar entre execuções.
    candidatos.sort(key=lambda repo: repo["full_name"])
    random.Random(config["amostra"]["semente"]).shuffle(candidatos)
    amostra, descartes = selecionar_amostra(
        cliente, candidatos, inicio, fim, config["amostra"]["tamanho"],
        config["filtros"],
    )

    escrever_csv(saida / "repositorios.csv", amostra, [
        "full_name", "estrelas", "linguagem", "criado_em", "idade_anos", "contribuidores",
        "default_branch", "url", "releases_janela", "runs_validos_janela",
    ])
    escrever_csv(saida / "descartes.csv",
                 [{"full_name": nome, "etapa": etapa, "motivo": MOTIVOS[etapa]}
                  for nome, etapa in descartes.items() if etapa is not None],
                 ["full_name", "etapa", "motivo"])
    funil = montar_funil(len(candidatos), descartes)
    escrever_csv(saida / "funil.csv", funil, ["etapa", "restantes", "descartados", "motivo"])
    for linha in funil:
        log.info("Funil | %-45s %6d  (-%d)", linha["etapa"], linha["restantes"], linha["descartados"])

    executar_coletas_detalhadas(cliente, amostra, config)
    log.info("Fim. Chamadas à API: %d; respostas do cache: %d",
             cliente.chamadas_api, cliente.acertos_cache)


if __name__ == "__main__":
    main()
