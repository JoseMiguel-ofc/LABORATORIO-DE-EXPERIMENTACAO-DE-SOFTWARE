"""Tamanhos de efeito de duas amostras independentes, orientados com − sem bot.

As duas medidas são adimensionais e descritivas. Não atribuem causalidade ao
uso do bot nem convertem uma associação observacional em efeito causal.
"""

import numpy as np
from scipy.special import gammaln
from scipy.stats import rankdata


def _amostra(valores, nome):
    try:
        amostra = np.asarray(valores)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{nome} deve ser uma amostra numérica unidimensional.") from exc
    if amostra.ndim != 1 or amostra.dtype.kind not in "iuf" or len(amostra) < 2:
        raise ValueError(f"{nome} deve ter ao menos duas observações numéricas reais.")
    amostra = amostra.astype(float)
    if not np.isfinite(amostra).all():
        raise ValueError(f"{nome} deve conter apenas observações finitas.")
    return amostra


def hedges_g(com_bot, sem_bot):
    """Diferença de médias padronizada pelo desvio combinado, com correção J.

    g = J(df) * (média(com_bot) − média(sem_bot)) / s_pooled, df = n1+n2−2.
    Usa desvios amostrais (ddof=1) e a correção exata
    J(df) = Γ(df/2) / [sqrt(df/2) Γ((df−1)/2)]. O sinal positivo indica maior
    média com bot. g não tem unidade e não é limitado a [-1, 1].

    O denominador combinado é uma convenção descritiva; não pressupõe que
    Welch tenha passado a exigir variâncias iguais. Dois grupos constantes
    têm denominador zero e geram ValueError, mesmo com médias diferentes.
    """
    com = _amostra(com_bot, "com_bot")
    sem = _amostra(sem_bot, "sem_bot")
    escala = max(float(np.max(np.abs(com))), float(np.max(np.abs(sem))))
    if escala == 0:
        raise ValueError("Hedges g é indefinido com desvio combinado zero.")
    # A padronização é invariante a unidades; normalizar primeiro evita overflow.
    com, sem = com / escala, sem / escala
    gl = len(com) + len(sem) - 2
    variancia = ((len(com) - 1) / gl * np.var(com, ddof=1)
                 + (len(sem) - 1) / gl * np.var(sem, ddof=1))
    if not np.isfinite(variancia) or variancia <= 0:
        raise ValueError("Hedges g é indefinido com desvio combinado zero.")
    correcao = np.exp(gammaln(gl / 2) - 0.5 * np.log(gl / 2)
                     - gammaln((gl - 1) / 2))
    g = float(correcao * (np.mean(com) - np.mean(sem)) / np.sqrt(variancia))
    if not np.isfinite(g):
        raise ValueError("A escala dos dados impede calcular Hedges g finito.")
    return g


def cliffs_delta(com_bot, sem_bot):
    """δ = P(com_bot > sem_bot) − P(com_bot < sem_bot), no intervalo [-1, 1].

    Cada par entre grupos tem o mesmo peso e empates contribuem zero. O sinal
    positivo indica que tempos com bot tendem a ser maiores. Usa postos médios
    para calcular U e δ = 2U/(n1*n2)−1, sem construir uma matriz n1 × n2.
    Grupos constantes são válidos: constantes iguais dão zero; separadas, ±1.
    """
    com = _amostra(com_bot, "com_bot")
    sem = _amostra(sem_bot, "sem_bot")
    postos = rankdata(np.concatenate([com, sem]), method="average")
    u = np.sum(postos[:len(com)]) - len(com) * (len(com) + 1) / 2
    delta = 2 * u / (len(com) * len(sem)) - 1
    return float(np.clip(delta, -1, 1))
