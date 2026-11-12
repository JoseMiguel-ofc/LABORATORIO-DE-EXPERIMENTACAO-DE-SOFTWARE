"""Textos do dashboard derivados dos resultados, sem recalcular simulações."""

import numpy as np

from src.testes import validar_alfa


NOMES_TESTE = {"welch": "Welch", "mann_whitney": "Mann–Whitney"}
ALFAS_DASHBOARD = (.01, .05, .10)


def validar_configuracao_dashboard(resultados, alfa=.05):
    """Exige a grade da entrega para o nível de significância selecionado."""
    alfa = validar_alfa(alfa)
    if alfa not in ALFAS_DASHBOARD:
        raise ValueError("O dashboard aceita apenas α = 1%, 5% ou 10%.")
    situacoes = {"base", "assimetria_forte", "outliers", "n_pequeno",
                 "variancias_diferentes"}
    efeitos = np.array([0, .1, .2, .3, .4, .5])
    if (set(resultados["situacao"]) != situacoes or len(resultados) != 60
            or set(resultados["teste"]) != set(NOMES_TESTE)):
        raise ValueError("A entrega exige as cinco situações; execute --todas-situacoes.")
    for (situacao, teste), curva in resultados.groupby(["situacao", "teste"]):
        n_esperado = 10 if situacao == "n_pequeno" else 30
        if (len(curva) != 6 or not np.allclose(np.sort(curva["efeito"]), efeitos)
                or not curva["n"].eq(n_esperado).all()
                or not np.allclose(curva["alfa"], alfa, rtol=0, atol=1e-12)
                or not curva["reps"].eq(10_000).all()
                or curva["semente"].isna().any() or not curva["semente"].eq(42).all()):
            raise ValueError("O dashboard exige a configuração da entrega: n = 30 "
                             f"(10 na amostra pequena), α = {alfa:.0%}, semente 42, "
                             "10.000 repetições e seis efeitos de 0 a 50%. "
                             "Salve experimentos alternativos em outro destino.")


def _alfa_unico(resultados):
    """Não interpreta taxas calculadas com limiares diferentes como uma grade."""
    if "alfa" not in resultados:
        raise ValueError("Os resultados devem informar um único alfa.")
    try:
        valores = resultados["alfa"].to_numpy(dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Os resultados devem informar um único alfa válido.") from exc
    if not np.isfinite(valores).all() or len(np.unique(valores)) != 1:
        raise ValueError("Selecione uma configuração com um único alfa válido.")
    return validar_alfa(valores[0])


def classificacao_calibracao(linha):
    """Compara alfa ao IC Monte Carlo; não confunde uma H0 falsa com erro I."""
    if not bool(linha["hipotese_nula_verdadeira"]):
        return "Não é erro tipo I (H₀ falsa)"
    if linha["ic_sup"] < linha["alfa"]:
        return "Conservador"
    if linha["ic_inf"] > linha["alfa"]:
        return "Liberal"
    return "Compatível com α no IC de 95%"


def textos_simulacao(resultados):
    """Resume uma grade com uma única configuração por situação/efeito/teste.

    Os ICs descrevem o erro Monte Carlo das taxas individuais. Não são um teste
    da diferença de poder, nem incluem a incerteza dos parâmetros estimados.
    """
    if resultados.empty:
        raise ValueError("Não há resultados para interpretar.")
    if resultados.duplicated(["situacao", "efeito", "teste"]).any():
        raise ValueError("Selecione uma configuração por situação, efeito e teste.")
    alfa = _alfa_unico(resultados)
    referencia_alfa = f"α = {100 * alfa:g}%"
    base = resultados[resultados["situacao"] == "base"]
    nulos = base[np.isclose(base["efeito"], 0)].set_index("teste")
    if set(nulos.index) != set(NOMES_TESTE):
        raise ValueError("A interpretação exige Q1 dos dois testes no cenário base.")
    frases = []
    for teste, nome in NOMES_TESTE.items():
        linha = nulos.loc[teste]
        frases.append(f"{nome}: {linha['taxa_rejeicao']:.2%} "
                      f"({classificacao_calibracao(linha).lower()})")
    erro = (f"Sob H₀ no cenário base, com {referencia_alfa}, " + "; ".join(frases) + ". "
            "Os intervalos de 95% quantificam a incerteza das repetições; "
            "não incluem a incerteza da amostra usada para ajustar a lognormal. "
            f"Taxas abaixo da referência nominal de {100 * alfa:g}% indicam menos "
            "falsos positivos, mas podem "
            "vir acompanhadas de menor capacidade de detectar diferenças.")

    maior = float(base["efeito"].max())
    if maior <= 0:
        raise ValueError("A interpretação exige pelo menos um efeito positivo em Q2.")
    ponto = base[np.isclose(base["efeito"], maior)].set_index("teste")
    w, m = ponto.loc["welch"], ponto.loc["mann_whitney"]
    diferenca = float(m["taxa_rejeicao"] - w["taxa_rejeicao"])
    poder = (f"No cenário base com {referencia_alfa} e efeito de +{maior:.0%}, "
             "o poder estimado é "
             f"{w['taxa_rejeicao']:.2%} para Welch e {m['taxa_rejeicao']:.2%} "
             f"para Mann–Whitney, com n = {int(w['n'])} por grupo. "
             "Nesse cenário, o ponto de efeito zero é a taxa de erro tipo I; "
             "nos efeitos positivos, H₀ é falsa e a taxa de rejeição mede poder. "
             "As curvas das situações adversas permitem conferir se essa "
             "comparação muda com a assimetria, contaminação e tamanho da amostra. "
             "Na situação de variâncias diferentes, efeito zero não torna H₀ "
             "verdadeira: a probabilidade de rejeição não é erro tipo I.")
    if diferenca > 0:
        confronto = ("A previsão de vantagem de Mann–Whitney é compatível com "
                     f"as estimativas no cenário base: no efeito de +{maior:.0%}, "
                     f"a diferença de poder é {diferenca * 100:.2f} pontos percentuais.")
    elif diferenca < 0:
        confronto = ("A previsão de vantagem de Mann–Whitney não se confirmou "
                     f"na estimativa do maior efeito base (+{maior:.0%}): "
                     f"Welch teve {-diferenca * 100:.2f} pontos percentuais a mais.")
    else:
        confronto = ("A previsão de vantagem de Mann–Whitney não foi demonstrada: "
                     "os poderes estimados coincidiram no maior efeito base.")
    confronto += (f" A comparação usa {referencia_alfa} e descreve estes cenários e parâmetros, "
                  "sem afirmar superioridade universal.")
    recomendacao = (
        f"A recomendação considera {referencia_alfa}. "
        "Para investigar deslocamentos de posição nos tempos assimétricos deste "
        "modelo, considere Mann–Whitney junto de sua calibração e do delta de Cliff. "
        "Se a pergunta for especificamente sobre a média em horas, Welch responde "
        "a esse parâmetro; sua calibração e seu poder com amostras pequenas devem "
        "ser examinados antes de decidir o tamanho da coleta. "
        "Medianas iguais com dispersões diferentes não garantem as hipóteses "
        "nulas de médias ou distribuições iguais. "
        "A amostra de um único repositório é observacional: os resultados "
        "não demonstram que o bot cause a diferença de tempo."
    )
    return {"erro_tipo_i": erro, "poder": poder, "previsao": confronto,
            "recomendacao": recomendacao}
