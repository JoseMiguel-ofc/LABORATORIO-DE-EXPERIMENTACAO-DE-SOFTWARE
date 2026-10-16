"""Sprint 2 B: calcula CFR de entrega a partir da coleta existente, sem rede.

Uso: python -m pipeline.cfr_entrega --config config.yaml
Aceita commits.csv ou commits.csv.gz. Não altera os arquivos da Sprint 1.
"""

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import yaml

from metricas.cfr import DEFINICOES_VERSOES as VERSOES, analisar_cfr_b
from pipeline.dados_entrega import carregar_releases


COLUNAS_METRICAS_CFR = ["full_name", "inicio", "fim", "cfr_b", "falhas", "denominador",
                       "censuradas", "inconclusivas", "heuristica_versao", "coleta_status"]
COLUNAS_PREVISOES = ["full_name", "tag_name", "published_at", "tag_anterior", "corretiva",
                     "motivo_corretiva", "falhou", "tag_corretiva", "censurada", "elegivel",
                     "motivo", "heuristica_versao"]


def calcular_repositorio(nome, releases, inicio, fim, *, versao="v1", coleta_status="ok"):
    """Distingue falha de coleta de repositório observado sem falhas."""
    metrica = {"full_name": nome, "inicio": inicio, "fim": fim, "cfr_b": None,
               "falhas": None, "denominador": None, "censuradas": None,
               "inconclusivas": None, "heuristica_versao": versao,
               "coleta_status": coleta_status}
    if versao not in VERSOES:
        raise ValueError(f"Versão desconhecida: {versao}")
    if coleta_status != "ok":
        return metrica, []
    resultado = analisar_cfr_b(releases, inicio, fim, versao=versao)
    for campo in ("cfr_b", "falhas", "denominador", "censuradas", "inconclusivas"):
        metrica[campo] = resultado[campo]
    previsoes = [{**linha, "full_name": nome, "heuristica_versao": versao}
                 for linha in resultado["releases"]]
    return metrica, previsoes


def calcular_tabelas(releases, inicio, fim, *, versao="v1", metadados=None):
    por_repo = defaultdict(list)
    for release in releases:
        if not release.get("full_name"):
            raise ValueError("Release sem full_name")
        por_repo[release["full_name"]].append(release)
    estados = {}
    for linha in metadados or []:
        nome = linha.get("full_name")
        if not nome or nome in estados:
            raise ValueError("Metadados de coleta sem full_name ou com repositório duplicado")
        estados[nome] = linha.get("releases_status") or "status_ausente"
    metricas, previsoes = [], []
    for nome in sorted(set(por_repo) | set(estados)):
        metrica, rotulos = calcular_repositorio(
            nome, por_repo.get(nome, []), inicio, fim, versao=versao,
            coleta_status=estados.get(nome, "ok"))
        metricas.append(metrica)
        previsoes.extend(rotulos)
    return {"metricas_cfr_b": metricas, "previsoes_cfr_b": previsoes}


def escrever_tabelas(tabelas, destino):
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    for nome, colunas in (("metricas_cfr_b", COLUNAS_METRICAS_CFR),
                           ("previsoes_cfr_b", COLUNAS_PREVISOES)):
        arquivo = destino / f"{nome}.csv"
        temporario = arquivo.with_suffix(".csv.tmp")
        with temporario.open("w", encoding="utf-8", newline="") as fluxo:
            escritor = csv.DictWriter(fluxo, fieldnames=colunas, extrasaction="ignore")
            escritor.writeheader()
            escritor.writerows(tabelas[nome])
        temporario.replace(arquivo)


def assinatura(caminho):
    caminho = Path(caminho)
    resumo = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            resumo.update(bloco)
    return {"arquivo": str(caminho), "sha256": resumo.hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--releases", type=Path)
    parser.add_argument("--commits", type=Path)
    parser.add_argument("--metricas-entrega", type=Path)
    parser.add_argument("--saida", type=Path)
    parser.add_argument("--versao", choices=list(VERSOES))
    args = parser.parse_args(argv)
    try:
        config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
        pasta = args.config.resolve().parent / config["saida"]["dir"]
        inicio, fim = config["janela"]["inicio"], config["janela"]["fim"]
        versao = args.versao or (config.get("heuristica") or {}).get("versao", "v1")
        if versao not in VERSOES:
            raise ValueError(f"Versão desconhecida: {versao}")
        fonte_releases = args.releases or pasta / "releases.csv"
        fonte_commits = args.commits or fonte_releases.with_name("commits.csv")
        if not args.commits and not fonte_commits.exists():
            fonte_commits = fonte_commits.with_suffix(".csv.gz")
        fonte_meta = args.metricas_entrega or fonte_releases.with_name("metricas_entrega.csv")
        metadados = None
        if fonte_meta.exists() or args.metricas_entrega:
            with fonte_meta.open(encoding="utf-8-sig", newline="") as arquivo:
                metadados = list(csv.DictReader(arquivo))
        releases = carregar_releases(fonte_releases, fonte_commits)
        tabelas = calcular_tabelas(releases, inicio, fim, versao=versao, metadados=metadados)
        destino = args.saida or pasta
        entradas = [args.config, fonte_releases, fonte_commits]
        if metadados is not None:
            entradas.append(fonte_meta)
        saidas = [destino / nome for nome in (
            "metricas_cfr_b.csv", "previsoes_cfr_b.csv", "cfr_b_execucao.json")]
        if any(saida.resolve() == entrada.resolve() for saida in saidas for entrada in entradas):
            raise ValueError("As saídas não podem sobrescrever os arquivos de entrada")
        manifesto = {
            "executado_em": datetime.now(timezone.utc).isoformat(), "versao": versao,
            "definicao": VERSOES[versao], "inicio": str(inicio), "fim": str(fim),
            "fontes": [assinatura(caminho) for caminho in entradas],
            "repositorios": len(tabelas["metricas_cfr_b"]),
            "releases_historicas_lidas": len(releases),
            "previsoes": len(tabelas["previsoes_cfr_b"]),
            "validacao_humana": "Não avaliada por este comando; executar validacao.avaliar_heuristica.",
        }
        escrever_tabelas(tabelas, destino)
        (destino / "cfr_b_execucao.json").write_text(
            json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, csv.Error) as erro:
        parser.error(str(erro))
    print(f"CFR (b) calculado para {manifesto['repositorios']} repositórios; saídas em {destino}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
