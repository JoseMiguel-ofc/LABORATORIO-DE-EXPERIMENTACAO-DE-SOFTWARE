import os
import pandas as pd
import matplotlib.pyplot as plt


ARQUIVO_RQ01 = "../../LAB01S02/RQ1E2/rq01_idade.csv"
ARQUIVO_RQ02 = "../../LAB01S02/RQ1E2/rq02_pull_requests.csv"


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


def gerar_histograma_idade(dados):
    os.makedirs("graficos", exist_ok=True)

    plt.figure(figsize=(10, 6))

    dados["idade_anos"].dropna().plot(
        kind="hist",
        bins=20,
        edgecolor="black"
    )

    plt.title("Distribuição da idade dos repositórios")
    plt.xlabel("Idade do repositório (anos)")
    plt.ylabel("Quantidade de repositórios")

    plt.tight_layout()
    plt.savefig("graficos/rq01_distribuicao_idade.png")
    plt.close()


def gerar_boxplot_pull_requests(dados):
    os.makedirs("graficos", exist_ok=True)

    plt.figure(figsize=(10, 6))

    plt.boxplot(
        dados["pull_requests_aceitas"].dropna(),
        vert=False,
        tick_labels=["RQ02"],
    )

    plt.title("Distribuição de Pull Requests aceitas nos 1.000 repositórios")
    plt.xlabel("Quantidade de Pull Requests aceitas")
    plt.tight_layout()
    plt.savefig("graficos/rq02_boxplot_pull_requests.png")
    plt.close()


def main():
    dados_rq01 = pd.read_csv(ARQUIVO_RQ01)
    dados_rq02 = pd.read_csv(ARQUIVO_RQ02)

    analisar_coluna(
        dados_rq01,
        "idade_anos",
        "RQ01 — Idade dos repositórios"
    )

    analisar_coluna(
        dados_rq02,
        "pull_requests_aceitas",
        "RQ02 — Pull Requests aceitas"
    )

    gerar_histograma_idade(dados_rq01)
    gerar_boxplot_pull_requests(dados_rq02)
    print("\nGráficos de validação gerados na pasta 'graficos'.")


if __name__ == "__main__":
    main()
