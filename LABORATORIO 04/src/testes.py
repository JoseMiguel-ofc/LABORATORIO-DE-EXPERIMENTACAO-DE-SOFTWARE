"""Testes bicaudais para duas amostras independentes (Sprint 1).

Welch compara médias sem pressupor variâncias iguais. Mann–Whitney compara
postos; interpretá-lo como diferença de medianas exige formas semelhantes das
distribuições. O p-valor é calculado sob H0, não é a probabilidade de H0 ser
verdadeira. A normal usada para U é uma aproximação com correção de empates.
"""

import numpy as np
from scipy import stats


def _amostra(valores, nome):
    """Valida sem descartar silenciosamente observações inválidas."""
    try:
        amostra = np.asarray(valores)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{nome} deve ser uma amostra numérica unidimensional.") from exc
    if amostra.ndim != 1 or amostra.dtype.kind not in "iuf":
        raise ValueError(f"{nome} deve ser uma amostra numérica real unidimensional.")
    if len(amostra) < 2:
        raise ValueError(f"{nome} deve conter pelo menos duas observações.")
    amostra = amostra.astype(float)
    if not np.isfinite(amostra).all():
        raise ValueError(f"{nome} deve conter somente valores finitos.")
    return amostra


def validar_alfa(alfa):
    """Retorna alfa como float, exigindo 0 < alfa < 1."""
    if isinstance(alfa, (bool, np.bool_)) or not np.isscalar(alfa):
        raise ValueError("alfa deve ser um número entre 0 e 1, exclusivamente.")
    try:
        alfa = float(alfa)
    except (TypeError, ValueError) as exc:
        raise ValueError("alfa deve ser um número entre 0 e 1, exclusivamente.") from exc
    if not np.isfinite(alfa) or not 0 < alfa < 1:
        raise ValueError("alfa deve ser um número entre 0 e 1, exclusivamente.")
    return alfa


def aplicar_testes(com_bot, sem_bot, alfa=0.05):
    """Aplica Welch e Mann–Whitney bicaudais a amostras independentes.

    Retorna dicionários JSON-serializáveis ``welch`` e ``mann_whitney``.
    ``estatistica`` é t para Welch e U do grupo com bot para Mann–Whitney.
    Welch inclui ``gl`` (Welch–Satterthwaite). Mann–Whitney inclui ``z``,
    ``media_u_h0`` e ``desvio_u_h0`` para desenhar a referência normal do G2.
    Ambos usam a decisão estrita p < alfa. U usa o método assintótico, correção
    de empates e nenhuma correção de continuidade; assim 2*sf(abs(z)) é seu p.

    Duas amostras constantes têm variância de Welch nula e são rejeitadas como
    caso degenerado, mesmo quando suas constantes são diferentes.
    """
    alfa = validar_alfa(alfa)
    com_bot = _amostra(com_bot, "com_bot")
    sem_bot = _amostra(sem_bot, "sem_bot")
    n_com, n_sem = len(com_bot), len(sem_bot)
    variancias = np.array([np.var(com_bot, ddof=1), np.var(sem_bot, ddof=1)])
    if not np.isfinite(variancias).all():
        raise ValueError("A escala dos dados impede calcular variâncias finitas.")
    if not np.any(variancias > 0):
        raise ValueError("Ambos os grupos são constantes: Welch tem variância nula.")

    welch = stats.ttest_ind(com_bot, sem_bot, equal_var=False, alternative="two-sided")
    componentes = variancias / [n_com, n_sem]
    # Normalizar evita overflow no quadrado da fórmula de Satterthwaite.
    pesos = componentes / componentes.sum()
    gl = 1.0 / (pesos[0] ** 2 / (n_com - 1) + pesos[1] ** 2 / (n_sem - 1))
    if not np.isfinite([welch.statistic, welch.pvalue, gl]).all():
        raise ValueError("A escala dos dados impede calcular o teste de Welch.")

    mann_whitney = stats.mannwhitneyu(
        com_bot, sem_bot, alternative="two-sided", method="asymptotic",
        use_continuity=False,
    )
    _, contagens = np.unique(np.concatenate([com_bot, sem_bot]), return_counts=True)
    contagens = contagens.astype(float)
    n_total = n_com + n_sem
    soma_empates = float(np.sum(contagens ** 3 - contagens))
    media_u = n_com * n_sem / 2.0
    variancia_u = n_com * n_sem / 12.0 * (
        n_total + 1 - soma_empates / (n_total * (n_total - 1))
    )
    desvio_u = float(np.sqrt(variancia_u))
    z = float((mann_whitney.statistic - media_u) / desvio_u)
    if not np.isfinite([mann_whitney.pvalue, z]).all() or desvio_u <= 0:
        raise ValueError("Mann–Whitney não é definido: variância dos postos nula.")

    rejeita_welch = bool(welch.pvalue < alfa)
    rejeita_mw = bool(mann_whitney.pvalue < alfa)
    decisao_welch = (
        "Rejeitamos H0 de médias iguais; há evidência de diferença entre as médias."
        if rejeita_welch else
        "Não rejeitamos H0 de médias iguais; a amostra não fornece evidência "
        "suficiente de diferença. Isso não prova igualdade."
    )
    decisao_mw = (
        "Rejeitamos H0 de distribuições iguais; há evidência de diferença nos postos."
        if rejeita_mw else
        "Não rejeitamos H0 de distribuições iguais; a amostra não fornece evidência "
        "suficiente de diferença nos postos. Isso não prova igualdade."
    )
    comuns = {"alfa": alfa, "n_com_bot": n_com, "n_sem_bot": n_sem,
              "alternativa": "two-sided"}
    return {
        "welch": {
            **comuns, "nome": "t de Welch", "estatistica": float(welch.statistic),
            "p_valor": float(welch.pvalue), "rejeita_h0": rejeita_welch,
            "gl": float(gl), "interpretacao": decisao_welch,
        },
        "mann_whitney": {
            **comuns, "nome": "Mann–Whitney U",
            "estatistica": float(mann_whitney.statistic),
            "p_valor": float(mann_whitney.pvalue), "rejeita_h0": rejeita_mw,
            "z": z, "media_u_h0": media_u, "desvio_u_h0": desvio_u,
            "correcao_empates": bool(soma_empates > 0),
            "metodo": "asymptotic", "correcao_continuidade": False,
            "interpretacao": decisao_mw + " Não é uma comparação de médias; "
            "interpretar medianas exige distribuições de formas semelhantes.",
        },
    }
