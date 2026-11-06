"""Cenário P1 e parâmetros lognormais estimados da amostra real.

O ajuste descritivo mantém os parâmetros de cada grupo para o G1. O cenário
experimental base reúne os logaritmos dos dois grupos para definir uma única
distribuição de referência. Assim, efeito zero representa H0 de fato.
"""

import numpy as np
import pandas as pd

from src.dados import GRUPOS, carregar

PERGUNTA = (
    "PRs revisados por um bot chegam ao merge em um tempo diferente dos PRs sem bot?"
)
H0 = (
    "No cenário base, os tempos dos dois grupos seguem a mesma distribuição "
    "lognormal, com médias e medianas iguais."
)
H1 = (
    "No cenário base, os tempos dos grupos diferem por um fator de escala, "
    "com médias e medianas diferentes (alternativa bilateral)."
)
ALTERNATIVA = "two-sided"
ALFA = 0.05
SEMENTE = 42
PREVISAO = (
    "Antes das simulações repetidas, prevemos que o Mann-Whitney possa ter maior "
    "poder que o t de Welch para n = 30 por grupo e tempos fortemente assimétricos. "
    "É uma hipótese a verificar, não um resultado empírico. Welch compara médias; "
    "Mann-Whitney compara posições relativas das observações e não testa medianas "
    "em geral. No cenário base, a mudança de escala lognormal altera tanto médias "
    "quanto medianas e a ordenação probabilística. Uma associação nos dados reais "
    "não permite atribuir causalidade ao bot."
)


def ajustar_cenario(df=None):
    """Retorna parâmetros descritivos e uma referência comum para simulação.

    ``df`` deve conter exatamente os grupos ``com_bot`` e ``sem_bot``, com pelo
    menos duas observações positivas, finitas e variáveis em ``horas`` por grupo.
    Sem argumento, lê o CSV versionado. Não modifica o DataFrame nem o arquivo.

    ``mu`` é a média e ``sigma`` é o desvio padrão amostral (ddof=1) de log(horas).
    ``parametros_base`` usa os logaritmos reunidos de todas as observações, sem
    calcular a média dos desvios dos grupos. ``media_modelo`` e ``mediana_modelo``
    são momentos da lognormal ajustada, não as estatísticas empíricas da amostra.
    """
    if df is None:
        df = carregar()
    if not isinstance(df, pd.DataFrame) or not {"grupo", "horas"}.issubset(df.columns):
        raise ValueError("Os dados devem conter as colunas grupo e horas.")
    if df["grupo"].isna().any() or set(df["grupo"]) != set(GRUPOS):
        raise ValueError("Os dados devem conter exatamente os grupos com_bot e sem_bot.")
    try:
        horas = pd.to_numeric(df["horas"], errors="raise").to_numpy(dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Os tempos em horas devem ser numéricos.") from exc
    if not np.isfinite(horas).all() or np.any(horas <= 0):
        raise ValueError("Os tempos em horas devem ser positivos e finitos.")

    log_horas = np.log(horas)
    parametros_descritivos = {}
    for grupo in GRUPOS:
        valores = log_horas[df["grupo"].to_numpy() == grupo]
        if len(valores) < 2:
            raise ValueError(f"O grupo {grupo} precisa de pelo menos duas observações.")
        mu = float(np.mean(valores))
        sigma = float(np.std(valores, ddof=1))
        if sigma <= 0:
            raise ValueError(f"O grupo {grupo} precisa ter variabilidade nos tempos.")
        with np.errstate(over="ignore"):
            media_modelo = float(np.exp(mu + sigma**2 / 2))
            mediana_modelo = float(np.exp(mu))
        if not np.isfinite(media_modelo):
            raise ValueError(f"A média lognormal do grupo {grupo} excede o limite numérico.")
        parametros_descritivos[grupo] = {
            "mu": mu,
            "sigma": sigma,
            "n": len(valores),
            "media_modelo": media_modelo,
            "mediana_modelo": mediana_modelo,
        }

    return {
        "parametros_descritivos": parametros_descritivos,
        "parametros_base": {
            "mu": float(np.mean(log_horas)),
            "sigma": float(np.std(log_horas, ddof=1)),
        },
        "n_por_grupo": {grupo: parametros["n"]
                        for grupo, parametros in parametros_descritivos.items()},
    }
