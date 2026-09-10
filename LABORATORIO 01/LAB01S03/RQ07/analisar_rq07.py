import os
import pandas as pd
import matplotlib.pyplot as plt


ARQUIVO_RQ02 = "../../LAB01S02/RQ1E2/rq02_pull_requests.csv"
ARQUIVO_RQ03 = "../../LAB01S01/RQ3E4/rq03_releases.csv"
ARQUIVO_RQ04 = "../../LAB01S01/RQ3E4/rq04_atualizacao.csv"
ARQUIVO_RQ05 = "../../LAB01S02/RQ05E6/rq05_linguagem.csv"

ARQUIVO_SAIDA = "rq07_por_linguagem.csv"

# Mesma referência usada na RQ05: linguagens mais populares
# segundo o GitHub Octoverse, mantida ao longo de todo o laboratório.
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


def montar_dataset():
    dados_rq02 = pd.read_csv(ARQUIVO_RQ02)[["repositorio", "pull_requests_aceitas"]]
    dados_rq03 = pd.read_csv(ARQUIVO_RQ03)[["repositorio", "total_releases"]]
    dados_rq04 = pd.read_csv(ARQUIVO_RQ04)[["repositorio", "dias_desde_ultima_atualizacao"]]
    dados_rq05 = pd.read_csv(ARQUIVO_RQ05)[["repositorio", "linguagem_primaria"]]

    dados = dados_rq05.merge(dados_rq02, on="repositorio", how="inner")
    dados = dados.merge(dados_rq03, on="repositorio", how="inner")
    dados = dados.merge(dados_rq04, on="repositorio", how="inner")

    dados["pull_requests_aceitas"] = pd.to_numeric(dados["pull_requests_aceitas"], errors="coerce")
    dados["total_releases"] = pd.to_numeric(dados["total_releases"], errors="coerce")
    dados["dias_desde_ultima_atualizacao"] = pd.to_numeric(dados["dias_desde_ultima_atualizacao"], errors="coerce")

    return dados.dropna(subset=["linguagem_primaria"])


def resumir_por_linguagem(dados):
    resumo = dados.groupby("linguagem_primaria").agg(
        quantidade_repositorios=("repositorio", "count"),
        mediana_pull_requests=("pull_requests_aceitas", "median"),
        mediana_releases=("total_releases", "median"),
        mediana_dias_desde_atualizacao=("dias_desde_ultima_atualizacao", "median"),
    )

    resumo["popular"] = resumo.index.isin(LINGUAGENS_MAIS_POPULARES)
    resumo = resumo.sort_values("quantidade_repositorios", ascending=False)

    resumo.to_csv(ARQUIVO_SAIDA, index_label="linguagem_primaria")

    return resumo


def imprimir_comparacao_popular_vs_outras(dados):
    grupo = dados["linguagem_primaria"].isin(LINGUAGENS_MAIS_POPULARES)

    populares = dados[grupo]
    outras = dados[~grupo]

    print("\n=== RQ07 — Linguagens populares vs. demais linguagens ===")
    print(f"Repositórios em linguagens populares: {len(populares)}")
    print(f"Repositórios em outras linguagens: {len(outras)}")

    for coluna, rotulo in [
        ("pull_requests_aceitas", "Mediana de Pull Requests aceitas"),
        ("total_releases", "Mediana de releases"),
        ("dias_desde_ultima_atualizacao", "Mediana de dias desde a última atualização"),
    ]:
        print(
            f"\n{rotulo}:"
            f"\n- Linguagens populares: {populares[coluna].median():.2f}"
            f"\n- Outras linguagens: {outras[coluna].median():.2f}"
        )


def gerar_grafico_top_linguagens(resumo, coluna, titulo, rotulo_x, nome_arquivo):
    os.makedirs("graficos", exist_ok=True)

    top = resumo.sort_values("quantidade_repositorios", ascending=False).head(10)
    top = top.sort_values(coluna)

    plt.figure(figsize=(10, 6))

    cores = ["#1f77b4" if popular else "#aaaaaa" for popular in top["popular"]]
    plt.barh(top.index, top[coluna], color=cores)

    plt.title(titulo)
    plt.xlabel(rotulo_x)
    plt.ylabel("Linguagem")

    plt.tight_layout()
    plt.savefig(f"graficos/{nome_arquivo}")
    plt.close()


def main():
    dados = montar_dataset()

    resumo = resumir_por_linguagem(dados)
    imprimir_comparacao_popular_vs_outras(dados)

    print(f"\nResumo por linguagem salvo em '{ARQUIVO_SAIDA}'.")

    gerar_grafico_top_linguagens(
        resumo,
        "mediana_pull_requests",
        "Mediana de Pull Requests aceitas por linguagem (Top 10 por volume)",
        "Mediana de Pull Requests aceitas",
        "rq07_pull_requests_por_linguagem.png",
    )

    gerar_grafico_top_linguagens(
        resumo,
        "mediana_releases",
        "Mediana de releases por linguagem (Top 10 por volume)",
        "Mediana de releases",
        "rq07_releases_por_linguagem.png",
    )

    gerar_grafico_top_linguagens(
        resumo,
        "mediana_dias_desde_atualizacao",
        "Mediana de dias desde a última atualização por linguagem (Top 10 por volume)",
        "Mediana de dias desde a última atualização",
        "rq07_atualizacao_por_linguagem.png",
    )

    print("\nGráficos de validação gerados na pasta 'graficos'.")
    print("(barras azuis = linguagens mais populares segundo o GitHub Octoverse)")


if __name__ == "__main__":
    main()
