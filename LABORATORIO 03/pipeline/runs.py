"""Coleta GitHub Actions em janelas mensais e métricas DORA de CI.

Coleta apenas event=push na branch padrão. A API limita a 1.000 resultados
por consulta; meses saturados são subdivididos em dias, sem truncar dados.
"""
import csv
from datetime import date, timedelta
import logging
from pathlib import Path

from metricas.cfr import calcular_cfr
from metricas.recuperacao import calcular_episodios, calcular_recuperacao
from pipeline.funil import CONCLUSOES_VALIDAS, ler_data

log = logging.getLogger(__name__)
COLUNAS_RUNS = ["full_name", "id", "workflow_id", "name", "event", "head_branch",
                "status", "conclusion", "created_at", "run_started_at", "updated_at", "html_url"]
COLUNAS_METRICAS = ["full_name", "runs_validos", "runs_falha", "runs_sucesso",
                    "cfr_a", "recuperacao_mediana_horas", "episodios_resolvidos",
                    "episodios_censurados", "coleta_completa"]
COLUNAS_EPISODIOS = ["full_name", "workflow_id", "inicio", "fim", "horas", "censurado"]


def _date(valor):
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor))


def meses(inicio, fim):
    """Gera intervalos inclusivos sem sobreposição, mesmo em meses parciais."""
    atual, final = _date(inicio), _date(fim)
    if atual > final:
        raise ValueError("Data inicial posterior à final")
    while atual <= final:
        proximo_mes = (atual.replace(day=28) + timedelta(days=4)).replace(day=1)
        fim_mes = min(proximo_mes - timedelta(days=1), final)
        yield atual, fim_mes
        atual = fim_mes + timedelta(days=1)


def _consultar_periodo(cliente, nome, branch, inicio, fim):
    caminho = f"/repos/{nome}/actions/runs"
    parametros = {"branch": branch, "event": "push", "created": f"{inicio}..{fim}",
                  "per_page": 100}
    resposta = cliente.get(caminho, parametros)
    if not resposta.ok:
        raise RuntimeError(f"{nome}: HTTP {resposta.status} ao coletar runs de {inicio} a {fim}")
    if not isinstance(resposta.dados, dict) or not isinstance(resposta.dados.get("workflow_runs"), list):
        raise ValueError(f"{nome}: resposta inválida de workflow_runs")
    total = resposta.dados.get("total_count", 0)
    if total >= 1000:
        log.warning("%s: %s a %s atingiu o limite de 1000 runs; subdividindo", nome, inicio, fim)
        if inicio == fim:
            raise RuntimeError(f"{nome}: mais de 1000 runs em {inicio}; coleta incompleta")
        meio = inicio + timedelta(days=(fim - inicio).days // 2)
        return (_consultar_periodo(cliente, nome, branch, inicio, meio) +
                _consultar_periodo(cliente, nome, branch, meio + timedelta(days=1), fim))
    # A primeira página já foi consultada; paginação do cliente lê do cache.
    return list(cliente.paginar(caminho, parametros, chave="workflow_runs"))


def coletar_runs_repositorio(cliente, full_name, branch, inicio, fim):
    """Retorna apenas runs válidos, únicos e dentro da janela."""
    inicio, fim = _date(inicio), _date(fim)
    vistos = {}
    for de, ate in meses(inicio, fim):
        for run in _consultar_periodo(cliente, full_name, branch, de, ate):
            if (run.get("event") != "push" or run.get("head_branch") != branch or
                    run.get("conclusion") not in CONCLUSOES_VALIDAS):
                continue
            criada = ler_data(run.get("created_at"))
            if criada is None or not inicio <= criada.date() <= fim:
                continue
            if run.get("id") is not None:
                vistos[run["id"]] = run
    return list(vistos.values())


def _csv(caminho, linhas, colunas):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(linhas)


def coletar(cliente, amostra, config):
    """Interface exigida por pipeline.__main__; gera três CSVs em dados/."""
    inicio, fim = config["janela"]["inicio"], config["janela"]["fim"]
    saida = Path(config["saida"]["dir"])
    tabela_runs, tabela_metricas, tabela_episodios = [], [], []
    vistos = set()
    for repo in amostra:
        nome = repo["full_name"]
        if nome in vistos:
            continue
        vistos.add(nome)
        try:
            runs = coletar_runs_repositorio(cliente, nome, repo["default_branch"], inicio, fim)
        except (RuntimeError, ValueError) as erro:
            log.error("Coleta de %s incompleta: %s", nome, erro)
            tabela_metricas.append({"full_name": nome, "coleta_completa": False})
            continue
        for run in runs:
            tabela_runs.append({"full_name": nome, **{campo: run.get(campo) for campo in COLUNAS_RUNS
                                                      if campo != "full_name"}})
        episodios = calcular_episodios(runs)
        tabela_episodios.extend({"full_name": nome, **episodio} for episodio in episodios)
        tabela_metricas.append({"full_name": nome, "runs_validos": len(runs),
                                "runs_falha": sum(r["conclusion"] != "success" for r in runs),
                                "runs_sucesso": sum(r["conclusion"] == "success" for r in runs),
                                "cfr_a": calcular_cfr(runs),
                                "recuperacao_mediana_horas": calcular_recuperacao(runs),
                                "episodios_resolvidos": sum(not e["censurado"] for e in episodios),
                                "episodios_censurados": sum(e["censurado"] for e in episodios),
                                "coleta_completa": True})
        log.info("%s: %d runs válidos, CFR(a)=%s, recuperação=%s h", nome, len(runs),
                 tabela_metricas[-1]["cfr_a"], tabela_metricas[-1]["recuperacao_mediana_horas"])
    _csv(saida / "runs.csv", tabela_runs, COLUNAS_RUNS)
    _csv(saida / "metricas_ci.csv", tabela_metricas, COLUNAS_METRICAS)
    _csv(saida / "episodios_recuperacao.csv", tabela_episodios, COLUNAS_EPISODIOS)
    return {"runs": tabela_runs, "metricas_ci": tabela_metricas,
            "episodios_recuperacao": tabela_episodios}
