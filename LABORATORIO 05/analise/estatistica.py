"""Testes e medidas de efeito da Sprint 2 da Pessoa A.

As funções recebem amostras já selecionadas e pares completos. Elas não
descartam faltantes silenciosamente. Os valores-p abaixo pressupõem a
independência apropriada a cada teste; calculá-los não valida essa condição
nas medições horárias da Steam. A análise chamadora deve identificá-los como
exploratórios enquanto a dependência temporal não tiver tratamento adequado.

Referências dos métodos:
https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html
https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html
https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.fisher_exact.html
https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.shapiro.html
"""
from __future__ import annotations

from numbers import Integral, Real
import warnings

import numpy as np
from scipy import stats


def _amostra(valores, nome: str) -> np.ndarray:
    try:
        dados = np.asarray(valores, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{nome} deve conter números finitos e não negativos.") from exc
    if (dados.ndim != 1 or not np.isfinite(dados).all()
            or (dados < 0).any()):
        raise ValueError(f"{nome} deve ser um vetor de números finitos e não negativos.")
    return dados


def _resultado(teste: str, n1: int, n2: int | None = None,
               efeito_nome: str | None = None, alternativa: str = "greater") -> dict:
    return {"teste": teste, "estatistica": None, "p_valor": None,
            "status": "amostra_insuficiente", "motivo": "",
            "n1": int(n1), "n2": None if n2 is None else int(n2),
            "efeito_nome": efeito_nome, "efeito": None,
            "alternativa": alternativa, "alternative": alternativa}


def _mediana(valores: np.ndarray) -> float:
    """Ponto médio estável, sem somar duas latências próximas ao limite float."""
    ordenados = np.sort(valores)
    meio = len(ordenados) // 2
    if len(ordenados) % 2:
        return float(ordenados[meio])
    inferior, superior = float(ordenados[meio - 1]), float(ordenados[meio])
    return inferior + (superior - inferior) / 2


def h1_latencia(pico, fora) -> dict:
    """Mann–Whitney U unilateral e delta de Cliff, pico menos fora do pico.

    Usa a aproximação assintótica corrigida para empates, sem correção de
    continuidade, como no protocolo e na simulação de poder. O delta é
    P(pico > fora) - P(pico < fora); empates contribuem zero. Diferença e razão
    de medianas são descrições adicionais, não a hipótese geral do teste.
    São exigidas pelo menos duas latências válidas em cada grupo.
    """
    x, y = _amostra(pico, "pico"), _amostra(fora, "fora")
    resultado = _resultado("Mann–Whitney U", len(x), len(y), "delta de Cliff")
    resultado.update({"metodo": "asymptotic", "correcao_continuidade": False,
                      "mediana_pico_ms": _mediana(x) if len(x) else None,
                      "mediana_fora_ms": _mediana(y) if len(y) else None,
                      "diferenca_mediana_ms": None, "razao_mediana": None,
                      "razao_mediana_motivo": None})
    if min(len(x), len(y)) < 2:
        resultado["motivo"] = "São necessárias ao menos duas latências por grupo."
        return resultado
    mx, my = _mediana(x), _mediana(y)
    resultado["diferenca_mediana_ms"] = mx - my
    razao = mx / my if my > 0 else None
    if razao is not None and np.isfinite(razao):
        resultado["razao_mediana"] = razao
    else:
        resultado["razao_mediana_motivo"] = ("Mediana fora do pico igual a zero." if my == 0
                                               else "Razão excede a precisão numérica representável.")
    if np.ptp(np.r_[x, y]) == 0:
        resultado.update({"estatistica": len(x) * len(y) / 2,
                          "efeito": 0.0, "status": "sem_variacao",
                          "motivo": "Todas as latências são iguais. O delta é zero, mas "
                          "o valor-p assintótico sem continuidade é indefinido."})
        return resultado
    teste = stats.mannwhitneyu(x, y, alternative="greater", method="asymptotic",
                               use_continuity=False)
    resultado.update({"estatistica": float(teste.statistic),
                      "p_valor": float(teste.pvalue),
                      "efeito": float(2 * teste.statistic / (len(x) * len(y)) - 1),
                      "status": "ok",
                      "motivo": "Valor-p sob independência; Mann–Whitney compara "
                      "distribuições/postos e não é um teste geral de medianas."})
    return resultado


def h2_usuarios(usuarios, latencias) -> dict:
    """Spearman unilateral: associação positiva entre uso e latência.

    Usa o valor-p assintótico de scipy.stats.spearmanr. A documentação alerta
    que sua precisão é adequada para amostras muito grandes (>500); amostras
    menores exigem cautela e uma inferência adequada ao desenho temporal.
    Uma permutação arbitrária das horas também pressuporia intercambialidade
    e não seria uma correção automática da autocorrelação.
    """
    x, y = _amostra(usuarios, "usuarios"), _amostra(latencias, "latencias")
    if len(x) != len(y):
        raise ValueError("usuarios e latencias devem conter o mesmo número de pares.")
    resultado = _resultado("Spearman", len(x), len(y), "rho de Spearman")
    resultado["p_metodo"] = "aproximacao_assintotica_spearman"
    resultado["n_pares"] = len(x)
    if len(x) < 3:
        resultado["motivo"] = "São necessários ao menos três pares completos."
        return resultado
    if np.ptp(x) == 0 or np.ptp(y) == 0:
        resultado.update({"status": "sem_variacao", "motivo": "Spearman é indefinido "
                          "quando usuários ou latência não variam."})
        return resultado
    teste = stats.spearmanr(x, y, alternative="greater")
    motivo = "Valor-p assintótico sob independência; associação não implica causalidade."
    if len(x) <= 500:
        motivo += " Com até 500 pares, a aproximação do valor-p pode ser imprecisa."
    resultado.update({"estatistica": float(teste.statistic),
                      "p_valor": float(teste.pvalue), "efeito": float(teste.statistic),
                      "status": "ok", "motivo": motivo})
    return resultado


def _contagem(valor, nome: str) -> int:
    if (isinstance(valor, (bool, np.bool_)) or not isinstance(valor, Integral)
            or valor < 0):
        raise ValueError(f"{nome} deve ser uma contagem inteira não negativa.")
    return int(valor)


def h3_falhas(falhas_janela, sucessos_janela, falhas_fora, sucessos_fora) -> dict:
    """Fisher unilateral para OR de falha janela/fora > 1, sem pseudocontagens.

    Tabela [[falhas_janela, sucessos_janela], [falhas_fora, sucessos_fora]].
    Fisher é usado em todas as tabelas 2×2; não depende de escolher um teste
    depois de observar sua significância. OR infinita é identificada pelo
    campo efeito_limite, mantendo números não finitos fora do resultado JSON.
    A ausência de observações em um dos grupos torna a comparação não estimável.
    """
    nomes = ("falhas_janela", "sucessos_janela", "falhas_fora", "sucessos_fora")
    a, b, c, d = (_contagem(valor, nome) for valor, nome in
                   zip((falhas_janela, sucessos_janela, falhas_fora, sucessos_fora), nomes))
    resultado = _resultado("Fisher exato", a + b, c + d, "razao de chances de falha")
    resultado.update({"tabela_2x2": [[a, b], [c, d]], "efeito_limite": None,
                      "taxa_falha_janela": a / (a + b) if a + b else None,
                      "taxa_falha_fora": c / (c + d) if c + d else None,
                      "diferenca_taxas_falha": None})
    if not a + b or not c + d:
        resultado["motivo"] = "Faltam tentativas classificáveis na janela ou fora dela."
        return resultado
    resultado["diferenca_taxas_falha"] = a / (a + b) - c / (c + d)
    teste = stats.fisher_exact([[a, b], [c, d]], alternative="greater")
    or_amostral = float(teste.statistic)
    if np.isfinite(or_amostral):
        resultado["estatistica"] = resultado["efeito"] = or_amostral
    elif np.isinf(or_amostral):
        resultado["efeito_limite"] = "infinito"
    resultado.update({"p_valor": float(teste.pvalue), "status": "ok",
                      "motivo": "Valor-p de Fisher sob independência das tentativas; "
                      "janelas repetidas e autocorrelação precisam ser consideradas."})
    if a + c == 0:
        resultado.update({"status": "sem_falhas", "motivo": "Não houve falhas observadas. "
                          "Fisher produz p=1, mas OR é indefinida e isso não prova "
                          "ausência de efeito nem disponibilidade global de 100%."})
    elif b + d == 0:
        resultado.update({"status": "sem_sucessos", "motivo": "Todas as tentativas "
                          "falharam. Fisher produz p=1 e OR é indefinida; não há "
                          "contraste de sucessos para comparar a janela."})
    elif resultado["efeito_limite"] == "infinito":
        resultado["motivo"] += " OR amostral infinita por célula zero; não foram adicionadas pseudocontagens."
    return resultado


def normalidade(valores) -> dict:
    """Shapiro–Wilk descritivo; não decide automaticamente o teste de H1.

    Requer n>=3 e variabilidade. Para n>5000 informa W, mas não reporta um
    valor-p que a documentação considera potencialmente impreciso. Nenhuma
    subamostra é selecionada para obter outro resultado de normalidade.
    """
    x = _amostra(valores, "valores")
    resultado = _resultado("Shapiro–Wilk", len(x), alternativa="two-sided")
    if len(x) < 3:
        resultado["motivo"] = "Shapiro–Wilk exige ao menos três observações."
        return resultado
    if np.ptp(x) == 0:
        resultado.update({"status": "sem_variacao", "motivo": "A amostra é constante; "
                          "não há variabilidade para avaliar normalidade."})
        return resultado
    with warnings.catch_warnings():
        if len(x) > 5000:
            warnings.filterwarnings("ignore", message=".*N > 5000.*", category=UserWarning)
        # W é invariante a translação e escala positiva. Padronizar o intervalo
        # evita overflow interno para entradas finitas de magnitude muito alta.
        teste = stats.shapiro((x - x.min()) / np.ptp(x))
    resultado["estatistica"] = float(teste.statistic)
    if len(x) > 5000:
        resultado.update({"status": "n_acima_limite_p", "motivo": "W calculado em todas "
                          "as observações. Para n>5000, o valor-p pode ser impreciso "
                          "e foi omitido."})
    else:
        resultado.update({"p_valor": float(teste.pvalue), "status": "ok",
                          "motivo": "Diagnóstico sob independência. Não rejeitar "
                          "normalidade não prova uma distribuição normal; os testes "
                          "das hipóteses continuam seguindo o protocolo."})
    return resultado


def ajustar_holm(valores) -> list[float | None]:
    """Valores-p ajustados de Holm para a família planejada, preservando ordem.

    None e NaN representam hipóteses sem teste estimável. Elas permanecem na
    contagem da família, como p=1 durante o ajuste, e voltam a None na saída.
    Assim, indisponibilidade de H3 não reduz a família H1–H3 após observar os
    dados. Não são aceitos valores-p infinitos, negativos ou maiores que um.
    """
    valores = list(valores)
    p_valores, ausentes = [], []
    for valor in valores:
        if valor is None or (isinstance(valor, Real) and np.isnan(valor)):
            p_valores.append(1.0)
            ausentes.append(True)
        elif (isinstance(valor, (bool, np.bool_)) or not isinstance(valor, Real)
              or not np.isfinite(valor) or not 0 <= valor <= 1):
            raise ValueError("Valores-p devem estar em [0,1], ou ser None/NaN para ausentes.")
        else:
            p_valores.append(float(valor))
            ausentes.append(False)
    ordem = np.argsort(p_valores, kind="stable")
    ajustados = [None] * len(valores)
    acumulado = 0.0
    for posicao, indice in enumerate(ordem):
        acumulado = min(1.0, max(acumulado, (len(valores) - posicao) * p_valores[indice]))
        if not ausentes[indice]:
            ajustados[indice] = acumulado
    return ajustados
