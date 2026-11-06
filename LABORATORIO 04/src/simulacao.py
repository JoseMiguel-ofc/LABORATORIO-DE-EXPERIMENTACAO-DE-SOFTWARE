"""Geração de uma amostra por grupo; o motor de repetições fica para a Sprint 2."""

from numbers import Integral, Real

import numpy as np

from src.cenario import SEMENTE, ajustar_cenario
from src.dados import GRUPOS


def _parametros_validos(parametros):
    """Valida também cenários fornecidos diretamente à API pública."""
    try:
        mu = float(parametros["mu"])
        sigma = float(parametros["sigma"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("O cenário deve fornecer mu e sigma numéricos.") from exc
    if not np.isfinite(mu) or not np.isfinite(sigma) or sigma <= 0:
        raise ValueError("O cenário deve ter mu finito e sigma positivo e finito.")
    return mu, sigma


def gerar(n=30, efeito=0.0, situacao="base", rng=None, *, cenario=None):
    """Gera arrays independentes de horas para ``com_bot`` e ``sem_bot``.

    Em ``base``, ambos partem da lognormal comum de ``parametros_base`` e somente
    ``com_bot`` é multiplicado por ``1 + efeito``. Portanto, efeito 0 é H0;
    efeito 0.30 aumenta em 30% a média e a mediana populacionais de ``com_bot``.
    Valores negativos maiores que -1 representam uma redução proporcional.

    ``ajuste_real`` usa os parâmetros individuais para comparação descritiva no
    G1 e exige efeito zero; não representa H0. Outras situações são rejeitadas.

    ``n`` é o tamanho de cada grupo. Sem ``rng``, cada chamada reproduz a semente
    42. Um ``numpy.random.Generator`` fornecido avança normalmente seu estado.
    ``cenario`` permite reutilizar o resultado de ``ajustar_cenario`` sem reler
    os dados em cada chamada.
    """
    if isinstance(n, (bool, np.bool_)) or not isinstance(n, Integral) or n < 2:
        raise ValueError("n deve ser um inteiro maior ou igual a 2 por grupo.")
    if (isinstance(efeito, (bool, np.bool_)) or not isinstance(efeito, Real)
            or not np.isfinite(efeito) or efeito <= -1):
        raise ValueError("efeito deve ser um número finito maior que -1.")
    if situacao not in ("base", "ajuste_real"):
        raise ValueError("situacao deve ser base ou ajuste_real.")
    if situacao == "ajuste_real" and efeito != 0:
        raise ValueError("ajuste_real exige efeito zero; use base para variar o efeito.")
    if rng is None:
        rng = np.random.default_rng(SEMENTE)
    elif not isinstance(rng, np.random.Generator):
        raise ValueError("rng deve ser um numpy.random.Generator ou None.")
    if cenario is None:
        cenario = ajustar_cenario()

    try:
        if situacao == "base":
            parametros = {grupo: _parametros_validos(cenario["parametros_base"])
                          for grupo in GRUPOS}
        else:
            parametros = {
                grupo: _parametros_validos(cenario["parametros_descritivos"][grupo])
                for grupo in GRUPOS
            }
    except (KeyError, TypeError) as exc:
        raise ValueError("O cenário não contém os parâmetros exigidos pela situação.") from exc

    amostras = {grupo: rng.lognormal(mu, sigma, size=int(n))
                for grupo, (mu, sigma) in parametros.items()}
    if situacao == "base":
        with np.errstate(over="ignore", invalid="ignore"):
            amostras["com_bot"] *= 1 + efeito
    if any(not np.isfinite(amostra).all() or np.any(amostra <= 0)
           for amostra in amostras.values()):
        raise ValueError("Os parâmetros produziram tempos fora do limite numérico.")
    return amostras
