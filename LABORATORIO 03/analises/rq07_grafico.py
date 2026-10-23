"""RQ 07: gráfico da sensibilidade da classificação DORA à definição operacional.

Uso: ``python -m analises.rq07_grafico`` (depois de ``python -m analises.rq07_sensibilidade``)

Lê ``dados/rq07_classificacoes.csv`` e ``dados/rq07_comparacoes.csv`` e grava
``analises/resultados/figuras/rq07_sensibilidade.png`` com dois painéis:
a distribuição das categorias em cada combinação (C1, C2, C3) e a proporção de
repositórios que mudam de categoria em cada par, com o kappa ponderado.
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from analises.rq01_04 import (AZUL, CATEGORIAS, RAMPA, RAIZ, SAIDA, SUPERFICIE, TEXTO,  # noqa: E402
                              TEXTO_2, _estilo)


DADOS = RAIZ / "dados"
CENARIOS = {"C1": "C1 · release, LT (a), CFR (a)",
            "C2": "C2 · release + pré, LT (b), CFR (b)",
            "C3": "C3 · tag, LT (b), CFR (a)"}


def distribuicao_por_cenario(classificacoes):
    """Percentual de cada categoria entre os repositórios classificados em cada cenário."""
    completas = classificacoes.dropna(subset=["categoria_geral"])
    contagem = completas.groupby("cenario")["categoria_geral"].value_counts().unstack(fill_value=0)
    contagem = contagem.reindex(index=list(CENARIOS), columns=CATEGORIAS, fill_value=0)
    return contagem.div(contagem.sum(axis=1), axis=0) * 100, contagem.sum(axis=1)


def grafico(classificacoes, comparacoes, caminho):
    percentuais, totais = distribuicao_por_cenario(classificacoes)
    figura, (esquerda, direita) = plt.subplots(
        1, 2, figsize=(12, 3.6), gridspec_kw={"width_ratios": [1.6, 1]})

    nomes = [f"{CENARIOS[c]} (n={totais[c]})" for c in CENARIOS][::-1]
    inicio = np.zeros(len(nomes))
    for categoria in CATEGORIAS:
        largura = percentuais[categoria].to_numpy()[::-1]
        barras = esquerda.barh(nomes, largura, left=inicio, color=RAMPA[categoria],
                               label=categoria, edgecolor=SUPERFICIE, linewidth=2, height=0.6)
        for barra, valor in zip(barras, largura):
            if valor >= 6:
                esquerda.text(barra.get_x() + barra.get_width() / 2,
                              barra.get_y() + barra.get_height() / 2, f"{valor:.0f}%",
                              ha="center", va="center", fontsize=8,
                              color="#ffffff" if categoria in ("Elite", "High") else TEXTO)
        inicio += largura
    esquerda.set_xlim(0, 100)
    esquerda.set_xlabel("% dos repositórios classificados", fontsize=8, color=TEXTO_2)
    _estilo(esquerda)
    esquerda.grid(False)
    esquerda.legend(ncol=4, loc="lower left", bbox_to_anchor=(0, 1.02), frameon=False,
                    fontsize=8, labelcolor=TEXTO)
    esquerda.set_title("Categoria geral em cada combinação", fontsize=9.5, color=TEXTO,
                       loc="left", pad=24)

    pares = comparacoes.iloc[::-1]
    rotulos = [p.replace("x", " × ") for p in pares["comparacao"]]
    barras = direita.barh(rotulos, pares["percentual_mudanca"], color=AZUL, height=0.6)
    for barra, (_, linha) in zip(barras, pares.iterrows()):
        texto = f"{linha.percentual_mudanca:.1f}% · κ = {linha.kappa_linear:.2f}".replace(".", ",")
        direita.text(barra.get_width() + 1, barra.get_y() + barra.get_height() / 2, texto,
                     va="center", fontsize=8.5, color=TEXTO)
    direita.set_xlim(0, max(60, pares["percentual_mudanca"].max() * 1.6))
    direita.set_xlabel("% de repositórios que mudam de categoria", fontsize=8, color=TEXTO_2)
    _estilo(direita)
    direita.set_title("Mudança de categoria por par", fontsize=9.5, color=TEXTO, loc="left",
                      pad=24)

    figura.suptitle("RQ 07 · Sensibilidade da classificação DORA à definição operacional",
                    fontsize=10.5, color=TEXTO, x=0.01, ha="left")
    figura.tight_layout()
    figura.savefig(caminho, dpi=200, facecolor=SUPERFICIE)
    plt.close(figura)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Gráfico da RQ 07")
    parser.add_argument("--dados", default=DADOS)
    parser.add_argument("--saida", default=SAIDA)
    args = parser.parse_args(argv)
    dados, saida = Path(args.dados), Path(args.saida)
    (saida / "figuras").mkdir(parents=True, exist_ok=True)
    destino = saida / "figuras" / "rq07_sensibilidade.png"
    grafico(pd.read_csv(dados / "rq07_classificacoes.csv"),
            pd.read_csv(dados / "rq07_comparacoes.csv"), destino)
    print(f"Gráfico salvo em {destino}")


if __name__ == "__main__":
    main()
