"""RQ 05: frequência de deploy × change failure rate (correlação de Spearman).

Uso: ``python -m analises.rq05``

Calcula ρ de Spearman, p-valor e n entre a frequência de releases (RQ 01) e cada
variante do CFR (RQ 03), e gera o gráfico de dispersão com a frequência em escala
log. Saídas em ``analises/resultados/``: ``rq05_spearman.csv`` e
``figuras/rq05_dispersao.png``.
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

from analises.rq01_04 import AZUL, ENTRADA, SAIDA, SUPERFICIE, TEXTO, TEXTO_2, _estilo  # noqa: E402


FREQUENCIA = "frequencia_releases_semana"
VARIANTES_CFR = {"cfr_a": "CFR (a) proxy de CI", "cfr_b": "CFR (b) proxy de entrega"}


def interpretar_rho(rho):
    """Força da correlação pelo módulo de ρ (faixas usuais em engenharia de software)."""
    modulo = abs(rho)
    forca = ("desprezível" if modulo < 0.1 else "fraca" if modulo < 0.3
             else "moderada" if modulo < 0.5 else "forte")
    if forca == "desprezível":
        return forca
    return f"{forca} {'positiva' if rho > 0 else 'negativa'}"


def correlacionar(dados, x, y):
    pares = dados[[x, y]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(pares) < 3:
        return {"x": x, "y": y, "n": len(pares), "rho": None, "p_valor": None,
                "interpretacao": "insuficiente"}
    resultado = spearmanr(pares[x], pares[y])
    rho = float(resultado.statistic)
    return {"x": x, "y": y, "n": len(pares), "rho": rho, "p_valor": float(resultado.pvalue),
            "interpretacao": interpretar_rho(rho)}


def tabela_spearman(dados):
    return pd.DataFrame([correlacionar(dados, FREQUENCIA, y) for y in VARIANTES_CFR])


def grafico_dispersao(dados, resultados, caminho):
    figura, eixos = plt.subplots(1, 2, figsize=(11, 4.2), sharex=True)
    for eixo, (coluna, nome) in zip(eixos, VARIANTES_CFR.items()):
        pares = dados[[FREQUENCIA, coluna]].dropna()
        eixo.scatter(pares[FREQUENCIA], pares[coluna] * 100, s=18, color=AZUL, alpha=0.55,
                     edgecolors=SUPERFICIE, linewidths=0.5)
        eixo.set_xscale("log")
        _estilo(eixo)
        eixo.grid(axis="y", color="#e5e4df", linewidth=0.8)
        r = resultados.set_index("y").loc[coluna]
        eixo.set_title(f"{nome}\nρ = {r.rho:.2f}; p = {r.p_valor:.3g}; n = {r.n}".replace(".", ","),
                       fontsize=9.5, color=TEXTO, loc="left")
        eixo.set_xlabel("frequência de deploy (releases/semana, escala log)", fontsize=8,
                        color=TEXTO_2)
        eixo.set_ylabel("% de falha", fontsize=8, color=TEXTO_2)
        eixo.set_ylim(-3, 100)
    figura.suptitle("RQ 05 · Frequência de deploy × change failure rate", fontsize=10.5,
                    color=TEXTO, x=0.01, ha="left")
    figura.tight_layout()
    figura.savefig(caminho, dpi=200, facecolor=SUPERFICIE)
    plt.close(figura)


def main(argv=None):
    parser = argparse.ArgumentParser(description="RQ 05")
    parser.add_argument("--entrada", default=ENTRADA)
    parser.add_argument("--saida", default=SAIDA)
    args = parser.parse_args(argv)
    saida = Path(args.saida)
    (saida / "figuras").mkdir(parents=True, exist_ok=True)
    dados = pd.read_csv(args.entrada)
    resultados = tabela_spearman(dados)
    resultados.to_csv(saida / "rq05_spearman.csv", index=False)
    grafico_dispersao(dados, resultados, saida / "figuras" / "rq05_dispersao.png")
    print(resultados.to_string(index=False))


if __name__ == "__main__":
    main()
