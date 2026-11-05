"""Leitura e resumo dos dados reais. Para ver o resumo: python -m src.dados"""
from pathlib import Path

import numpy as np
import pandas as pd

CSV = Path(__file__).resolve().parent.parent / "dados" / "prs.csv"
GRUPOS = {"com_bot": "Com bot", "sem_bot": "Sem bot"}


def carregar(caminho=CSV):
    """Lê o CSV e calcula o tempo até o merge em horas."""
    df = pd.read_csv(caminho, parse_dates=["criado_em", "mergeado_em"])
    df["horas"] = (df["mergeado_em"] - df["criado_em"]).dt.total_seconds() / 3600
    return df


def contar_outliers(valores):
    """Conta os valores fora das cercas de Tukey (1,5 × IQR)."""
    q1, q3 = valores.quantile([0.25, 0.75])
    iqr = q3 - q1
    return int(((valores < q1 - 1.5 * iqr) | (valores > q3 + 1.5 * iqr)).sum())


def resumo(df):
    """Mediana, média, desvio, assimetria e outliers do tempo de merge por grupo."""
    linhas = {}
    for grupo, rotulo in GRUPOS.items():
        horas = df.loc[df["grupo"] == grupo, "horas"]
        linhas[rotulo] = {"n": len(horas),
                          "Mediana (h)": horas.median(),
                          "Média (h)": horas.mean(),
                          "Desvio padrão (h)": horas.std(),
                          "Assimetria": horas.skew(),
                          "Outliers (Tukey)": contar_outliers(horas),
                          "Máximo (h)": horas.max()}
    return pd.DataFrame(linhas).T


def parametros_lognormal(df):
    """μ e σ de log(horas) por grupo: os parâmetros da lognormal ajustada."""
    log_horas = np.log(df["horas"]).groupby(df["grupo"])
    return {grupo: (serie.mean(), serie.std()) for grupo, serie in log_horas}


def simular_provisorio(df, rng, n=10_000):
    """Amostra lognormal por grupo, só para o G1 enquanto o gerador da simulação não chega."""
    return {grupo: rng.lognormal(mu, sigma, n)
            for grupo, (mu, sigma) in parametros_lognormal(df).items()}


if __name__ == "__main__":
    dados = carregar()
    print(resumo(dados).round(2).to_string())
    print("\nParâmetros lognormal (μ, σ de log(horas)):")
    for grupo, (mu, sigma) in parametros_lognormal(dados).items():
        print(f"  {grupo}: μ={mu:.3f}  σ={sigma:.3f}  mediana={np.exp(mu):.2f} h")
