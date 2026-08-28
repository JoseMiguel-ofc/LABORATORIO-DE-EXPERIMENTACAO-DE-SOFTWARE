import os
import pandas as pd
import matplotlib.pyplot as plt


ARQUIVO_RQ01 = "../../LAB01S02/RQ1E2/rq01_idade.csv"
ARQUIVO_RQ02 = "../../LAB01S02/RQ1E2/rq02_pull_requests.csv"

PASTA_GRAFICOS = "graficos"


def preparar_pasta():
    os.makedirs(PASTA_GRAFICOS, exist_ok=True)


def gerar_grafico_rq01(dados):
    serie = pd.to_numeric(
        dados["idade_anos"],
        errors="coerce"
    ).dropna()

    media = serie.mean()
    mediana = serie.median()

    plt.figure(figsize=(10, 6))

    plt.hist(
        serie,
        bins=20,
        edgecolor="black"
    )

    plt.axvline(
        mediana,
        linestyle="--",
        linewidth=2,
        label=f"Mediana: {mediana:.2f} anos"
    )

    plt.axvline(
        media,
        linestyle=":",
        linewidth=2,
        label=f"Média: {media:.2f} anos"
    )

    plt.title(
        "Distribuição da idade dos 1.000 repositórios mais populares"
    )

    plt.xlabel("Idade do repositório (anos)")
    plt.ylabel("Quantidade de repositórios")

    plt.legend()
    plt.tight_layout()

    caminho = os.path.join(
        PASTA_GRAFICOS,
        "rq01_idade_final.png"
    )

    plt.savefig(caminho, dpi=300)
    plt.close()

    print(f"Gráfico RQ01 gerado: {caminho}")


def gerar_grafico_rq02(dados):
    serie = pd.to_numeric(
        dados["pull_requests_aceitas"],
        errors="coerce"
    ).dropna()

    mediana = serie.median()

    plt.figure(figsize=(10, 6))

    plt.boxplot(
        serie,
        vert=False,
        tick_labels=["RQ02"]
    )

    plt.xscale("symlog")

    plt.axvline(
        mediana,
        linestyle="--",
        linewidth=2,
        label=f"Mediana: {mediana:.0f} PRs"
    )

    plt.title(
        "Distribuição de Pull Requests aceitas nos 1.000 repositórios"
    )

    plt.xlabel(
        "Quantidade de Pull Requests aceitas (escala logarítmica)"
    )

    plt.legend()
    plt.tight_layout()

    caminho = os.path.join(
        PASTA_GRAFICOS,
        "rq02_pull_requests_final.png"
    )

    plt.savefig(caminho, dpi=300)
    plt.close()
    media = serie.mean()
    mediana = serie.median()
    plt.axvline(
    media,
    linestyle=":",
    linewidth=2,
    label=f"Média: {media:.2f} PRs"
    )

    print(f"Gráfico RQ02 gerado: {caminho}")


def main():
    preparar_pasta()

    dados_rq01 = pd.read_csv(ARQUIVO_RQ01)
    dados_rq02 = pd.read_csv(ARQUIVO_RQ02)

    gerar_grafico_rq01(dados_rq01)
    gerar_grafico_rq02(dados_rq02)

    print("\nVisualizações finais concluídas.")


if __name__ == "__main__":
    main()
