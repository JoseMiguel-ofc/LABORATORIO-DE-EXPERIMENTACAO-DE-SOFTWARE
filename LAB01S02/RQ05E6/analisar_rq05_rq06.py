import os
import pandas as pd
import matplotlib.pyplot as plt


ARQUIVO_RQ05 = "rq05_linguagem.csv"
ARQUIVO_RQ06 = "rq06_issues.csv"

# Linguagens mais populares segundo o GitHub Octoverse
# (referência mantida ao longo de todo o laboratório)
LINGUAGENS_MAIS_POPULARES = [
    "JavaScript",
    "Python",
    "Java",
    "TypeScript",
    "C#",
    "C++",
    "PHP",
    "Shell",
    "C",
    "Go"
]


def analisar_linguagem_primaria(dados):
    serie = dados["linguagem_primaria"]

    total_registros = len(serie)
    valores_ausentes = serie.isna().sum()

    contagem = serie.value_counts(dropna=True)
    percentuais = serie.value_counts(
        dropna=True,
        normalize=True
    ) * 100

    print("\n=== RQ05 — Linguagem primária dos repositórios ===")

    print(f"Total de registros: {total_registros}")
    print(f"Valores ausentes: {valores_ausentes}")

    print("\nTop 10 linguagens mais utilizadas:")

    for linguagem in contagem.head(10).index:
        print(
            f"- {linguagem}: "
            f"{contagem[linguagem]} repositórios "
            f"({percentuais[linguagem]:.2f}%)"
        )

    percentual_entre_populares = sum(
        percentuais.get(linguagem, 0)
        for linguagem in LINGUAGENS_MAIS_POPULARES
    )

    print(
        "\nPercentual de repositórios escritos em alguma das "
        "linguagens mais populares (ref. GitHub Octoverse): "
        f"{percentual_entre_populares:.2f}%"
    )

    return contagem


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
        print("\nMenores outliers:")

        indices_menores = outliers.nsmallest(10).index

        for indice in indices_menores:
            repositorio = dados.loc[indice, "repositorio"]
            valor = serie.loc[indice]

            print(f"- {repositorio}: {valor:.2f}")


def gerar_grafico_top_linguagens(contagem):
    os.makedirs("graficos", exist_ok=True)

    top_linguagens = contagem.head(15)

    plt.figure(figsize=(10, 6))

    top_linguagens.sort_values().plot(kind="barh")

    plt.title("Linguagens primárias mais utilizadas (Top 15)")
    plt.xlabel("Quantidade de repositórios")
    plt.ylabel("Linguagem")

    plt.tight_layout()
    plt.savefig("graficos/rq05_top_linguagens.png")
    plt.close()


def gerar_boxplot_issues_fechadas(dados):
    os.makedirs("graficos", exist_ok=True)

    plt.figure(figsize=(10, 6))

    plt.boxplot(
        dados["percentual_issues_fechadas"].dropna(),
        vert=False,
        tick_labels=["RQ06"],
    )

    plt.title(
        "Distribuição do percentual de issues fechadas "
        "nos 1.000 repositórios"
    )
    plt.xlabel("Percentual de issues fechadas (%)")
    plt.tight_layout()
    plt.savefig("graficos/rq06_boxplot_issues_fechadas.png")
    plt.close()


def main():
    dados_rq05 = pd.read_csv(ARQUIVO_RQ05)
    dados_rq06 = pd.read_csv(ARQUIVO_RQ06)

    contagem_linguagens = analisar_linguagem_primaria(dados_rq05)

    analisar_coluna(
        dados_rq06,
        "percentual_issues_fechadas",
        "RQ06 — Percentual de issues fechadas"
    )

    gerar_grafico_top_linguagens(contagem_linguagens)
    gerar_boxplot_issues_fechadas(dados_rq06)
    print("\nGráficos de validação gerados na pasta 'graficos'.")


if __name__ == "__main__":
    main()
