#!/usr/bin/env python3
"""H3 (exploratória) - compara estrutura do código (complexidade/LOC/duplicação) entre COM_IA e SEM_IA."""

import argparse
from pathlib import Path
import sys
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import wilcoxon


LAB = Path(__file__).resolve().parents[2]
PASTA_CONSOLIDACOES_PADRAO = LAB / "S02" / "resultados" / "consolidacoes"
PASTA_SAIDA_PADRAO = LAB / "S03" / "resultados"

METRICAS = {
    "estatica_complexidade_maxima": "Complexidade ciclomática máxima",
    "estatica_loc": "LOC",
    "estatica_sloc": "SLOC",
    "duplicacao_percentual_duplicacao": "Duplicação literal (%)",
}


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


def carregar_dados(caminho_csv):
    dados = pd.read_csv(caminho_csv, dtype=str, keep_default_na=False)

    for coluna in METRICAS:
        if coluna in dados.columns:
            dados[coluna] = pd.to_numeric(dados[coluna], errors="coerce")

    avaliacao_concluido = dados.get("avaliacao_concluido", pd.Series("", index=dados.index))
    dados["situacao"] = avaliacao_concluido.map(
        lambda v: "concluido" if v == "True" else ("nao_concluido" if v == "False" else "sem_avaliacao")
    )

    if "estatica_erro" in dados.columns:
        com_erro = dados["estatica_erro"].astype(bool) & (dados["estatica_erro"] != "")
        if com_erro.any():
            warnings.warn(
                f"{com_erro.sum()} trial(s) com erro nas métricas estáticas foram excluídos "
                f"da análise: {dados.loc[com_erro, ['integrante', 'kata', 'tratamento']].values.tolist()}"
            )
        dados = dados.loc[~com_erro].copy()

    return dados


def descritivas_por_tratamento(dados, coluna):
    grupos = dados.dropna(subset=[coluna]).groupby("tratamento")[coluna]

    return grupos.agg(n="count", mediana="median", media="mean", desvio_padrao="std")


def pares_por_integrante(dados, coluna):
    """Para cada integrante com pelo menos um trial válido em cada tratamento, retorna (com_ia, sem_ia)."""
    validos = dados.dropna(subset=[coluna])
    medias = validos.groupby(["integrante", "tratamento"])[coluna].mean().unstack("tratamento")

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


def gerar_grafico(dados, coluna, titulo, caminho_saida):
    validos = dados.dropna(subset=[coluna])

    if validos.empty:
        return None

    grupos = [
        validos.loc[validos["tratamento"] == tratamento, coluna]
        for tratamento in ("COM_IA", "SEM_IA")
    ]

    plt.figure(figsize=(6, 5))
    plt.boxplot(grupos, tick_labels=["COM_IA", "SEM_IA"])
    plt.scatter(
        [1] * len(grupos[0]), grupos[0], alpha=0.6, zorder=3
    )
    plt.scatter(
        [2] * len(grupos[1]), grupos[1], alpha=0.6, zorder=3
    )
    plt.ylabel(titulo)
    plt.title(f"{titulo} por tratamento (soluções concluídas)")
    plt.tight_layout()
    plt.savefig(caminho_saida)
    plt.close()

    return caminho_saida


def analisar(dados, pasta_saida):
    pasta_saida.mkdir(parents=True, exist_ok=True)

    completas = dados[dados["situacao"] == "concluido"]
    parciais = dados[dados["situacao"] == "nao_concluido"]
    sem_avaliacao = dados[dados["situacao"] == "sem_avaliacao"]

    if not sem_avaliacao.empty:
        print(
            f"\nAviso: {len(sem_avaliacao)} trial(s) sem avaliacao_concluido preenchido em "
            "avaliacao_trials.csv - não entram nas estatísticas por situação, só nos totais gerais."
        )

    linhas_resumo = []

    for coluna, titulo in METRICAS.items():
        if coluna not in dados.columns:
            continue

        print(f"\n=== {titulo} ===")

        for rotulo, subconjunto in (
            ("concluido", completas), ("nao_concluido", parciais), ("sem_avaliacao", sem_avaliacao)
        ):
            descritivas = descritivas_por_tratamento(subconjunto, coluna)
            print(f"-- {rotulo} --")
            print(descritivas.to_string() if not descritivas.empty else "(sem dados)")

            for tratamento, linha in descritivas.iterrows():
                linhas_resumo.append({
                    "metrica": coluna,
                    "subconjunto": rotulo,
                    "tratamento": tratamento,
                    "n": int(linha["n"]),
                    "mediana": linha["mediana"],
                    "media": linha["media"],
                    "desvio_padrao": linha["desvio_padrao"],
                })

        pares = pares_por_integrante(completas, coluna)
        teste = rodar_wilcoxon(pares)
        print(f"Wilcoxon pareado por integrante (só completas): {teste}")

        linhas_resumo.append({
            "metrica": coluna,
            "subconjunto": "wilcoxon_pareado_completas",
            "tratamento": "COM_IA_vs_SEM_IA",
            "n": teste["n_pares"],
            "mediana": teste["p_valor"],
            "media": teste["estatistica"],
            "desvio_padrao": teste["observacao"],
        })

        nome_arquivo = coluna.replace("estatica_", "").replace("duplicacao_", "dup_")
        grafico = gerar_grafico(
            completas, coluna, titulo, pasta_saida / f"h3_{nome_arquivo}.png"
        )
        if grafico:
            print(f"Gráfico salvo em: {grafico}")

    resumo = pd.DataFrame(linhas_resumo)
    caminho_csv = pasta_saida / "h3_resumo_estrutura.csv"
    resumo.to_csv(caminho_csv, index=False)
    print(f"\nResumo salvo em: {caminho_csv}")

    return resumo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--consolidado", type=Path,
        help="Caminho direto para um trials_consolidados.csv (padrão: consolidação mais recente em S02/resultados/consolidacoes)",
    )
    parser.add_argument(
        "--saida", type=Path, default=PASTA_SAIDA_PADRAO,
        help=f"Pasta para salvar CSV e gráficos (padrão: {PASTA_SAIDA_PADRAO})",
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
