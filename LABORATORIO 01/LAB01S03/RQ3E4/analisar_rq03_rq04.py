import os
import pandas as pd
import matplotlib.pyplot as plt


ARQUIVO_RQ03 = "../../LAB01S01/RQ3E4/rq03_releases.csv"
ARQUIVO_RQ04 = "../../LAB01S01/RQ3E4/rq04_atualizacao.csv"


def analisar_coluna(dados, coluna, nome_rq):
    serie = pd.to_numeric(dados[coluna], errors="coerce")

    total_registros = len(serie)
    valores_ausentes = serie.isna().sum()

    media = serie.mean()
    mediana = serie.median()
    minimo = serie.min()
    maximo = serie.max()

    q1 = serie.quantile(0.25)
    q3 = serie.quantile(0.75)

    iqr = q3 - q1

    limite_inferior = q1 - 1.5 * iqr
    limite_superior = q3 + 1.5 * iqr

    outliers = serie[
        (serie < limite_inferior) |
        (serie > limite_superior)
    ]

    print(f"\n=== {nome_rq} ===")

    print(f"Total de registros: {total_registros}")
    print(f"Valores ausentes: {valores_ausentes}")

    print(f"\nMínimo: {minimo:.2f}")
    print(f"Máximo: {maximo:.2f}")
    print(f"Média: {media:.2f}")
    print(f"Mediana: {mediana:.2f}")

    print(f"\nQ1: {q1:.2f}")
    print(f"Q3: {q3:.2f}")
    print(f"IQR: {iqr:.2f}")

    print(f"Limite inferior: {limite_inferior:.2f}")
    print(f"Limite superior: {limite_superior:.2f}")

    print(f"Quantidade de outliers: {len(outliers)}")

    if len(outliers) > 0:
        print("\nMaiores outliers:")

        indices_maiores = outliers.nlargest(10).index

        for indice in indices_maiores:
            repositorio = dados.loc[indice, "repositorio"]
            valor = serie.loc[indice]

            print(f"- {repositorio}: {valor:.2f}")


def gerar_boxplot_releases(dados):
    os.makedirs("graficos", exist_ok=True)

    plt.figure(figsize=(10, 6))

    plt.boxplot(
        dados["total_releases"].dropna(),
        vert=False,
        tick_labels=["RQ03"],
    )

    plt.title("Distribuição do total de releases nos 1.000 repositórios")
    plt.xlabel("Quantidade de releases")
    plt.tight_layout()
    plt.savefig("graficos/rq03_boxplot_releases.png")
    plt.close()


def gerar_histograma_atualizacao(dados):
    os.makedirs("graficos", exist_ok=True)

    plt.figure(figsize=(10, 6))

    dados["dias_desde_ultima_atualizacao"].dropna().plot(
        kind="hist",
        bins=20,
        edgecolor="black"
    )

    plt.title("Distribuição do tempo até a última atualização")
    plt.xlabel("Dias desde a última atualização")
    plt.ylabel("Quantidade de repositórios")

    plt.tight_layout()
    plt.savefig("graficos/rq04_histograma_atualizacao.png")
    plt.close()


def main():
    dados_rq03 = pd.read_csv(ARQUIVO_RQ03)
    dados_rq04 = pd.read_csv(ARQUIVO_RQ04)

    analisar_coluna(
        dados_rq03,
        "total_releases",
        "RQ03 — Total de releases"
    )

    analisar_coluna(
        dados_rq04,
        "dias_desde_ultima_atualizacao",
        "RQ04 — Dias desde a última atualização"
    )

    gerar_boxplot_releases(dados_rq03)
    gerar_histograma_atualizacao(dados_rq04)
    print("\nGráficos de validação gerados na pasta 'graficos'.")


if __name__ == "__main__":
    main()
