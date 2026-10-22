"""RQ 06: características dos repositórios associadas ao desempenho DORA.

Uso: ``python -m analises.rq06``

Fatores: estrelas, contribuidores e idade (em quartis) e linguagem principal
(linguagens com pelo menos ``MIN_GRUPO`` repositórios; as demais viram "Outras").
O tipo do projeto não entra porque só existe para os 60 repositórios da
amostra-ouro. Métricas: as quatro da combinação de referência (C1).

Para cada fator × métrica: Kruskal-Wallis (ou Mann-Whitney se houver só dois
grupos), correção de Holm sobre todos os testes e tamanho de efeito (ε² para
Kruskal-Wallis; Cliff's delta para dois grupos). Para os fatores em quartis,
também reportamos o Cliff's delta entre o 4º e o 1º quartil, que mostra a
direção do efeito.

Saídas em ``analises/resultados/``: ``rq06_testes.csv``, ``rq06_medianas.csv`` e
``figuras/rq06_efeitos.png``.
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import kruskal, mannwhitneyu  # noqa: E402
from statsmodels.stats.multitest import multipletests  # noqa: E402

from analises.rq01_04 import ENTRADA, SAIDA, SUPERFICIE, TEXTO, TEXTO_2  # noqa: E402


ALFA = 0.05
MIN_GRUPO = 15
QUARTIS = ["Q1", "Q2", "Q3", "Q4"]
FATORES = {"estrelas": "Estrelas", "contribuidores": "Contribuidores",
           "idade_anos": "Idade", "linguagem": "Linguagem"}
METRICAS = {"frequencia_releases_semana": "Frequência", "lead_time_a_horas": "Lead time (a)",
            "cfr_a": "CFR (a)", "recuperacao_mediana_horas": "Recuperação"}
# Rampa sequencial azul (skill dataviz) para o mapa de tamanho de efeito.
RAMPA_SEQUENCIAL = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab"]
LIMITES_EPSILON = [0, 0.01, 0.06, 0.14]  # desprezível, pequeno, médio, grande


# ---------------------------------------------------------------- tamanhos de efeito

def epsilon_quadrado(h, n):
    """ε² = H / (n − 1), tamanho de efeito do Kruskal-Wallis (0 a 1)."""
    return h / (n - 1)


def cliffs_delta(x, y):
    """δ = 2·U₁ / (n₁·n₂) − 1, com U₁ de ``mannwhitneyu(x, y)`` (−1 a +1).

    Equivale a P(x > y) − P(x < y): positivo quando x tende a ser maior que y.
    """
    u1 = mannwhitneyu(x, y, alternative="two-sided").statistic
    return 2 * u1 / (len(x) * len(y)) - 1


def interpretar_epsilon(e2):
    """Por analogia ao η² (Cohen, 1988): 0,01 pequeno; 0,06 médio; 0,14 grande."""
    return ("desprezível" if e2 < 0.01 else "pequeno" if e2 < 0.06
            else "médio" if e2 < 0.14 else "grande")


def interpretar_delta(delta):
    """Romano et al. (2006): |δ| < 0,147 desprezível; < 0,33 pequeno; < 0,474 médio."""
    modulo = abs(delta)
    return ("desprezível" if modulo < 0.147 else "pequeno" if modulo < 0.33
            else "médio" if modulo < 0.474 else "grande")


# ---------------------------------------------------------------- grupos e testes

def agrupar(dados, fator):
    """Converte o fator em grupos: quartis para numéricos; linguagens frequentes para texto."""
    if fator == "linguagem":
        linguagem = dados[fator].fillna("Outras")
        frequentes = linguagem.value_counts()
        frequentes = frequentes[frequentes >= MIN_GRUPO].index
        return linguagem.where(linguagem.isin(frequentes), "Outras")
    return pd.qcut(pd.to_numeric(dados[fator], errors="coerce"), 4, labels=QUARTIS).astype(str)


def testar(dados, fator, metrica):
    grupos = agrupar(dados, fator)
    valores = pd.to_numeric(dados[metrica], errors="coerce")
    validos = valores.notna() & grupos.notna() & (grupos != "nan")
    amostras = {g: valores[validos & (grupos == g)].to_numpy() for g in sorted(grupos[validos].unique())}
    n = int(validos.sum())
    linha = {"fator": FATORES[fator], "metrica": METRICAS[metrica], "n": n, "grupos": len(amostras)}
    if len(amostras) == 2:
        x, y = amostras.values()
        linha.update(teste="Mann-Whitney", estatistica=float(mannwhitneyu(x, y).statistic),
                     p_valor=float(mannwhitneyu(x, y).pvalue), efeito="Cliff's delta",
                     tamanho_efeito=float(cliffs_delta(x, y)))
        linha["interpretacao_efeito"] = interpretar_delta(linha["tamanho_efeito"])
    else:
        h, p = kruskal(*amostras.values())
        linha.update(teste="Kruskal-Wallis", estatistica=float(h), p_valor=float(p),
                     efeito="ε²", tamanho_efeito=float(epsilon_quadrado(h, n)))
        linha["interpretacao_efeito"] = interpretar_epsilon(linha["tamanho_efeito"])
    if fator != "linguagem":
        delta = cliffs_delta(amostras["Q4"], amostras["Q1"])
        linha.update(delta_q4_q1=float(delta), interpretacao_delta_q4_q1=interpretar_delta(delta))
    medianas = {g: float(np.median(v)) for g, v in amostras.items()}
    return linha, medianas


def analisar(dados):
    linhas, medianas = [], []
    for fator in FATORES:
        for metrica in METRICAS:
            linha, por_grupo = testar(dados, fator, metrica)
            linhas.append(linha)
            medianas += [{"fator": FATORES[fator], "metrica": METRICAS[metrica], "grupo": g,
                          "mediana": m} for g, m in por_grupo.items()]
    testes = pd.DataFrame(linhas)
    rejeita, p_holm, _, _ = multipletests(testes["p_valor"], alpha=ALFA, method="holm")
    testes["p_holm"] = p_holm
    testes["significativo_holm"] = rejeita
    return testes, pd.DataFrame(medianas)


# ---------------------------------------------------------------- gráfico

def grafico_efeitos(testes, caminho):
    """Mapa fator × métrica com ε²; asterisco marca p de Holm < 0,05."""
    fatores, metricas = list(FATORES.values()), list(METRICAS.values())
    matriz = testes.pivot(index="fator", columns="metrica", values="tamanho_efeito"
                          ).loc[fatores, metricas]
    significativo = testes.pivot(index="fator", columns="metrica", values="significativo_holm"
                                 ).loc[fatores, metricas]
    figura, eixo = plt.subplots(figsize=(7.5, 4))
    for i, fator in enumerate(fatores):
        for j, metrica in enumerate(metricas):
            valor = matriz.loc[fator, metrica]
            classe = int(np.searchsorted(LIMITES_EPSILON, valor, side="right")) - 1
            eixo.add_patch(plt.Rectangle((j, i), 1, 1, facecolor=RAMPA_SEQUENCIAL[classe],
                                         edgecolor=SUPERFICIE, linewidth=2))
            marca = "*" if significativo.loc[fator, metrica] else ""
            eixo.text(j + 0.5, i + 0.5, f"{valor:.3f}{marca}".replace(".", ","), ha="center",
                      va="center", fontsize=9, color="#ffffff" if classe >= 2 else TEXTO)
    eixo.set_xlim(0, len(metricas))
    eixo.set_ylim(len(fatores), 0)
    eixo.set_xticks(np.arange(len(metricas)) + 0.5, metricas)
    eixo.set_yticks(np.arange(len(fatores)) + 0.5, fatores)
    eixo.tick_params(length=0, colors=TEXTO_2, labelsize=8.5)
    for lado in eixo.spines.values():
        lado.set_visible(False)
    eixo.xaxis.tick_top()
    nomes = ["desprezível (< 0,01)", "pequeno (< 0,06)", "médio (< 0,14)", "grande (≥ 0,14)"]
    eixo.legend(handles=[plt.Rectangle((0, 0), 1, 1, facecolor=cor) for cor in RAMPA_SEQUENCIAL],
                labels=nomes, ncol=4, loc="upper left", bbox_to_anchor=(0, -0.02), frameon=False,
                fontsize=8, labelcolor=TEXTO, handlelength=1.2)
    figura.suptitle("RQ 06 · Tamanho de efeito ε² (Kruskal-Wallis); * = significativo após Holm",
                    fontsize=10, color=TEXTO, x=0.01, ha="left")
    figura.tight_layout()
    figura.savefig(caminho, dpi=200, facecolor=SUPERFICIE)
    plt.close(figura)


def main(argv=None):
    parser = argparse.ArgumentParser(description="RQ 06")
    parser.add_argument("--entrada", default=ENTRADA)
    parser.add_argument("--saida", default=SAIDA)
    args = parser.parse_args(argv)
    saida = Path(args.saida)
    (saida / "figuras").mkdir(parents=True, exist_ok=True)
    testes, medianas = analisar(pd.read_csv(args.entrada))
    testes.to_csv(saida / "rq06_testes.csv", index=False)
    medianas.to_csv(saida / "rq06_medianas.csv", index=False)
    grafico_efeitos(testes, saida / "figuras" / "rq06_efeitos.png")
    colunas = ["fator", "metrica", "n", "estatistica", "p_valor", "p_holm", "tamanho_efeito",
               "interpretacao_efeito", "delta_q4_q1"]
    print(testes[colunas].to_string(index=False, float_format=lambda v: f"{v:.4f}"))


if __name__ == "__main__":
    main()
