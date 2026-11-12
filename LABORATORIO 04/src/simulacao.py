"""Geração dos grupos independentes para as situações do experimento P1."""

from numbers import Integral, Real

import numpy as np

from src.cenario import SEMENTE, ajustar_cenario
from src.dados import GRUPOS

SITUACOES = ("base", "assimetria_forte", "outliers", "n_pequeno",
             "variancias_diferentes")


def _validar_geracao(n, efeito, situacao, cenario):
    """Validação comum à amostra isolada e ao motor em lotes."""
    if isinstance(n, (bool, np.bool_)) or not isinstance(n, Integral) or n < 2:
        raise ValueError("n deve ser um inteiro maior ou igual a 2 por grupo.")
    if (isinstance(efeito, (bool, np.bool_)) or not isinstance(efeito, Real)
            or not np.isfinite(efeito) or efeito <= -1):
        raise ValueError("efeito deve ser um número finito maior que -1.")
    if situacao not in (*SITUACOES, "ajuste_real"):
        raise ValueError("situacao deve ser uma das situações do experimento ou ajuste_real.")
    if situacao == "ajuste_real" and efeito != 0:
        raise ValueError("ajuste_real exige efeito zero; use base para variar o efeito.")
    if cenario is None:
        cenario = ajustar_cenario()
    try:
        if situacao == "ajuste_real":
            parametros = [_parametros_validos(cenario["parametros_descritivos"][grupo])
                          for grupo in GRUPOS]
        else:
            mu, sigma = _parametros_validos(cenario["parametros_base"])
            parametros = [(mu, sigma), (mu, sigma)]
            if situacao == "assimetria_forte":
                parametros = [(mu, sigma * 1.35)] * 2
            elif situacao == "variancias_diferentes":
                parametros = [(mu, sigma * 1.35), (mu, sigma)]
    except (KeyError, TypeError) as exc:
        raise ValueError("O cenário não contém os parâmetros exigidos pela situação.") from exc
    return np.asarray(parametros, dtype=float)


def _gerar_lote(n, efeito, situacao, rng, parametros, repeticoes):
    """Mantém a mesma ordem de sorteios de chamadas sucessivas a ``gerar``.

    O eixo 0 contém repetições, o eixo 1 grupos e o eixo 2 observações. A
    contaminação usa sorteios adicionais independentes; somente sua geração
    percorre as repetições, enquanto os dois testes são sempre vetorizados.
    """
    mu, sigma = parametros[:, 0, None], parametros[:, 1, None]
    with np.errstate(over="ignore", invalid="ignore"):
        if situacao == "outliers":
            amostras = np.empty((repeticoes, 2, n))
            for indice in range(repeticoes):
                amostras[indice] = rng.lognormal(mu, sigma, size=(2, n))
                mascara = rng.random((2, n)) < 0.05
                amostras[indice] *= np.where(mascara, 20.0, 1.0)
        else:
            amostras = rng.lognormal(mu, sigma, size=(repeticoes, 2, n))
        if situacao != "ajuste_real":
            amostras[:, 0, :] *= 1 + efeito
    if not np.isfinite(amostras).all() or np.any(amostras <= 0):
        raise ValueError("Os parâmetros produziram tempos fora do limite numérico.")
    return amostras


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
    G1 e exige efeito zero; não representa H0. ``assimetria_forte`` aumenta o
    sigma de ambos os grupos em 35%; ``outliers`` multiplica independentemente
    5% dos tempos de cada grupo por 20. ``n_pequeno`` mantém a distribuição base
    (a grade do experimento escolhe n=10). ``variancias_diferentes`` aumenta
    apenas o sigma de com_bot em 35%: com efeito zero as medianas coincidem,
    mas as médias e distribuições diferem, portanto NÃO representa H0.

    ``n`` é o tamanho de cada grupo. Sem ``rng``, cada chamada reproduz a semente
    42. Um ``numpy.random.Generator`` fornecido avança normalmente seu estado.
    ``cenario`` permite reutilizar o resultado de ``ajustar_cenario`` sem reler
    os dados em cada chamada.
    """
    parametros = _validar_geracao(n, efeito, situacao, cenario)
    if rng is None:
        rng = np.random.default_rng(SEMENTE)
    elif not isinstance(rng, np.random.Generator):
        raise ValueError("rng deve ser um numpy.random.Generator ou None.")
    amostras = _gerar_lote(int(n), efeito, situacao, rng, parametros, 1)[0]
    return {grupo: amostras[indice] for indice, grupo in enumerate(GRUPOS)}
