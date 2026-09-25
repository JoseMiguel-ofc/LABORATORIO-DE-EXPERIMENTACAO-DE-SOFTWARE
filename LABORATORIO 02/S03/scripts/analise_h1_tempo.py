#!/usr/bin/env python3
"""H1 (primária) - compara tempo até aprovação entre COM_IA e SEM_IA."""

import argparse
from datetime import datetime
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import wilcoxon


LAB = Path(__file__).resolve().parents[2]
PASTA_CONSOLIDACOES_PADRAO = LAB / "S02" / "resultados" / "consolidacoes"
PASTA_SAIDA_PADRAO = LAB / "S03" / "resultados"

TOLERANCIA_SEGUNDOS = 5
LIMITE_TIMEBOX_SEGUNDOS = 35 * 60


def localizar_consolidacao_mais_recente(pasta_consolidacoes):
    candidatos = [
        p / "trials_consolidados.csv"
        for p in pasta_consolidacoes.iterdir()
        if p.is_dir() and (p / "trials_consolidados.csv").exists()
    ]

    if not candidatos:
        raise FileNotFoundError(
            f"Nenhuma consolidação encontrada em {pasta_consolidacoes}. "
            "Rode antes: LABORATORIO 02/S02/scripts/consolidar_trials.py"
        )

    return max(candidatos, key=lambda caminho: caminho.stat().st_mtime)


def diferenca_inicio_fim(inicio, fim):
    try:
        return (datetime.fromisoformat(fim) - datetime.fromisoformat(inicio)).total_seconds()
    except (TypeError, ValueError):
        return None


def carregar_dados(caminho_csv):
    dados = pd.read_csv(caminho_csv, dtype=str, keep_default_na=False)

    dados["tempo_segundos"] = pd.to_numeric(dados.get("tempo_tempo_segundos", ""), errors="coerce")
    dados["censurado"] = dados.get("tempo_censurado", "").eq("True")

    dados["inicio_fim_segundos"] = [
        diferenca_inicio_fim(i, f)
        for i, f in zip(dados.get("tempo_inicio", ""), dados.get("tempo_fim", ""))
    ]

    dados["divergencia_segundos"] = (
        dados["tempo_segundos"] - dados["inicio_fim_segundos"]
    ).abs()

    dados["confiavel"] = (
        dados["tempo_segundos"].notna()
        & dados["inicio_fim_segundos"].notna()
        & (dados["divergencia_segundos"] <= TOLERANCIA_SEGUNDOS)
    )

    return dados


def relatorio_confiabilidade(dados):
    suspeitos = dados[~dados["confiavel"] & dados["tempo_segundos"].notna()]

    print(f"\n=== Confiabilidade dos tempos (tolerância: {TOLERANCIA_SEGUNDOS}s) ===")
    print(f"Confiáveis: {int(dados['confiavel'].sum())}/{len(dados)}")

    if not suspeitos.empty:
        print(
            f"SUSPEITOS ({len(suspeitos)}): tempo_segundos não bate com a diferença "
            "inicio/fim - EXCLUÍDOS da análise principal, listados à parte."
        )
        for _, linha in suspeitos.iterrows():
            print(
                f"  {linha['integrante']:12} {linha['kata']:20} {linha['tratamento']:8} "
                f"tempo_segundos={linha['tempo_segundos']:.2f} "
                f"inicio_fim={linha['inicio_fim_segundos']:.2f} "
                f"divergencia={linha['divergencia_segundos']:.2f}s"
            )

    return suspeitos


def descritivas_por_tratamento(dados):
    grupos = dados.groupby("tratamento")["tempo_segundos"]
    return grupos.agg(n="count", mediana="median", media="mean", desvio_padrao="std")


def pares_por_integrante(dados):
    medias = dados.groupby(["integrante", "tratamento"])["tempo_segundos"].mean().unstack("tratamento")

    if "COM_IA" not in medias.columns or "SEM_IA" not in medias.columns:
        return pd.DataFrame(columns=["COM_IA", "SEM_IA"])

    return medias.dropna(subset=["COM_IA", "SEM_IA"])


def rodar_wilcoxon(pares):
    if len(pares) < 3:
        return {
            "n_pares": len(pares),
            "estatistica": None,
            "p_valor": None,
            "observacao": "Menos de 3 pares disponíveis; teste de Wilcoxon não é aplicável.",
        }

    diferencas = pares["COM_IA"] - pares["SEM_IA"]

    if (diferencas == 0).all():
        return {
            "n_pares": len(pares),
            "estatistica": 0.0,
            "p_valor": 1.0,
            "observacao": "Todas as diferenças pareadas são zero (empate perfeito); Wilcoxon é degenerado aqui.",
        }

    try:
        resultado = wilcoxon(pares["COM_IA"], pares["SEM_IA"])
        return {
            "n_pares": len(pares),
            "estatistica": round(float(resultado.statistic), 4),
            "p_valor": round(float(resultado.pvalue), 4),
            "observacao": (
                "Amostra pequena (n < 6); resultado é exploratório, "
                "não deve ser lido como evidência de efeito ou significância."
                if len(pares) < 6 else ""
            ),
        }
    except ValueError as erro:
        return {
            "n_pares": len(pares),
            "estatistica": None,
            "p_valor": None,
            "observacao": f"Wilcoxon não aplicável: {erro}",
        }


def gerar_grafico(dados, caminho_saida):
    if dados.empty:
        return None

    grupos = [
        dados.loc[dados["tratamento"] == tratamento, "tempo_segundos"] / 60
        for tratamento in ("COM_IA", "SEM_IA")
    ]

    plt.figure(figsize=(6, 5))
    plt.boxplot(grupos, tick_labels=["COM_IA", "SEM_IA"])
    plt.scatter([1] * len(grupos[0]), grupos[0], alpha=0.6, zorder=3)
    plt.scatter([2] * len(grupos[1]), grupos[1], alpha=0.6, zorder=3)
    plt.axhline(
        LIMITE_TIMEBOX_SEGUNDOS / 60, linestyle="--", color="red", alpha=0.5,
        label="Limite de 35 min",
    )
    plt.ylabel("Tempo até aprovação (minutos)")
    plt.title("H1 - Tempo por tratamento (trials com tempo confiável)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(caminho_saida)
    plt.close()

    return caminho_saida


def analisar(dados, pasta_saida):
    pasta_saida.mkdir(parents=True, exist_ok=True)

    suspeitos = relatorio_confiabilidade(dados)
    confiaveis = dados[dados["confiavel"]]

    print("\n=== Tempo até aprovação (trials confiáveis) ===")
    descritivas = descritivas_por_tratamento(confiaveis)
    print(descritivas.to_string() if not descritivas.empty else "(sem dados)")

    if confiaveis["censurado"].any():
        print(
            f"\nAtenção: {int(confiaveis['censurado'].sum())} trial(s) confiável(is) censurado(s) "
            "em 35 min - tempo é limite inferior, não tempo real de conclusão."
        )

    pares = pares_por_integrante(confiaveis)
    teste = rodar_wilcoxon(pares)
    print(f"\nWilcoxon pareado por integrante (só confiáveis): {teste}")

    linhas_resumo = []
    for tratamento, linha in descritivas.iterrows():
        linhas_resumo.append({
            "subconjunto": "confiavel", "tratamento": tratamento,
            "n": int(linha["n"]), "mediana_segundos": linha["mediana"],
            "media_segundos": linha["media"], "desvio_padrao_segundos": linha["desvio_padrao"],
        })

    linhas_resumo.append({
        "subconjunto": "wilcoxon_pareado_confiaveis", "tratamento": "COM_IA_vs_SEM_IA",
        "n": teste["n_pares"], "mediana_segundos": teste["p_valor"],
        "media_segundos": teste["estatistica"], "desvio_padrao_segundos": teste["observacao"],
    })

    resumo = pd.DataFrame(linhas_resumo)
    resumo.to_csv(pasta_saida / "h1_resumo_tempo.csv", index=False)

    suspeitos_saida = suspeitos[[
        "integrante", "kata", "tratamento", "tempo_segundos",
        "inicio_fim_segundos", "divergencia_segundos",
    ]]
    suspeitos_saida.to_csv(pasta_saida / "h1_trials_suspeitos.csv", index=False)

    grafico = gerar_grafico(confiaveis, pasta_saida / "h1_tempo_por_tratamento.png")
    if grafico:
        print(f"\nGráfico salvo em: {grafico}")

    print(f"Resumo salvo em: {pasta_saida / 'h1_resumo_tempo.csv'}")
    print(f"Trials suspeitos salvos em: {pasta_saida / 'h1_trials_suspeitos.csv'}")

    return resumo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--consolidado", type=Path,
        help="Caminho direto para um trials_consolidados.csv (padrão: consolidação mais recente em S02/resultados/consolidacoes)",
    )
    parser.add_argument(
        "--saida", type=Path, default=PASTA_SAIDA_PADRAO,
        help=f"Pasta para salvar CSVs e gráfico (padrão: {PASTA_SAIDA_PADRAO})",
    )
    args = parser.parse_args()

    try:
        caminho_csv = args.consolidado or localizar_consolidacao_mais_recente(
            PASTA_CONSOLIDACOES_PADRAO
        )
    except FileNotFoundError as erro:
        parser.error(str(erro))

    dados = carregar_dados(caminho_csv)

    if dados.empty:
        print(f"Consolidado vazio em {caminho_csv}; nada para analisar.")
        return 1

    print(f"Analisando {len(dados)} trial(s) de {caminho_csv}")
    analisar(dados, args.saida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
