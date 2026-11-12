"""Os dois testes nos dados reais: tabela e conclusão da seção 6.

Para ver no terminal: python -m src.aplicacao_real
"""
import sys

import numpy as np
import pandas as pd

from src.cenario import ALFA
from src.dados import carregar
from src.efeito import cliffs_delta, hedges_g
from src.testes import aplicar_testes

# Cohen (1988) para g e Romano et al. (2006) para δ: limites superiores de cada faixa.
FAIXAS = {"welch": ((0.2, "desprezível"), (0.5, "pequeno"), (0.8, "médio")),
          "mann_whitney": ((0.147, "desprezível"), (0.33, "pequeno"), (0.474, "médio"))}
MEDIDAS = {"welch": "g de Hedges", "mann_whitney": "δ de Cliff"}


def magnitude(teste, valor):
    """Rótulo convencional do tamanho de efeito, pelo valor absoluto."""
    for limite, rotulo in FAIXAS[teste]:
        if abs(valor) < limite:
            return rotulo
    return "grande"


def grupos(df):
    """Arrays de horas de cada grupo, na direção com bot − sem bot."""
    return (df.loc[df["grupo"] == "com_bot", "horas"].to_numpy(),
            df.loc[df["grupo"] == "sem_bot", "horas"].to_numpy())


def aplicar_dados_reais(com_bot, sem_bot, alfa=ALFA):
    """Testes, tamanhos de efeito e diferenças em horas dos dados coletados."""
    testes = aplicar_testes(com_bot, sem_bot, alfa=alfa)
    efeitos = {"welch": hedges_g(com_bot, sem_bot),
               "mann_whitney": cliffs_delta(com_bot, sem_bot)}
    return {
        "testes": testes,
        "efeitos": efeitos,
        "diferenca_medias": float(np.mean(com_bot) - np.mean(sem_bot)),
        "diferenca_medianas": float(np.median(com_bot) - np.median(sem_bot)),
        "desvios": (float(np.std(com_bot, ddof=1)), float(np.std(sem_bot, ddof=1))),
        # Fração de pares (com, sem) em que o PR com bot demorou mais.
        "p_com_maior": float(np.mean(com_bot[:, None] > sem_bot[None, :])),
        "alfa": alfa,
    }


def _conclusao(teste, resultado):
    evidencia = "Há" if resultado["testes"][teste]["rejeita_h0"] else "Sem"
    if teste == "welch":
        return f"{evidencia} evidência nas médias (com bot {resultado['diferenca_medias']:+.1f} h)"
    return (f"{evidencia} evidência nos postos (com bot demorou mais em "
            f"{resultado['p_com_maior']:.0%} dos pares)")


def tabela_secao6(resultado):
    """Estatística, p-valor, tamanho do efeito e conclusão de cada teste."""
    alfa = resultado["alfa"]
    linhas = []
    for teste, r in resultado["testes"].items():
        efeito = resultado["efeitos"][teste]
        linhas.append({
            "Teste": r["nome"],
            "Estatística": r["estatistica"],
            "p-valor": r["p_valor"],
            f"Decisão (α = {alfa:.0%})": "Rejeitar H₀" if r["rejeita_h0"] else "Não rejeitar H₀",
            "Medida do efeito": MEDIDAS[teste],
            "Tamanho do efeito": efeito,
            "Magnitude": magnitude(teste, efeito),
            "Conclusão": _conclusao(teste, resultado),
        })
    return pd.DataFrame(linhas)


def texto_secao6(resultado):
    """De 2 a 4 frases: concordância dos testes e importância prática do efeito."""
    alfa = resultado["alfa"]
    testes, efeitos = resultado["testes"], resultado["efeitos"]
    decisoes = {r["rejeita_h0"] for r in testes.values()}
    if decisoes == {False}:
        concordancia = (f"Com α = {alfa:.0%}, nenhum dos dois testes rejeita H₀ nos "
                        f"{testes['welch']['n_com_bot'] + testes['welch']['n_sem_bot']} "
                        "PRs coletados, então os dois chegam à mesma conclusão.")
    elif decisoes == {True}:
        concordancia = f"Com α = {alfa:.0%}, os dois testes rejeitam H₀."
    else:
        quem = next(r["nome"] for r in testes.values() if r["rejeita_h0"])
        concordancia = (f"Com α = {alfa:.0%}, os testes discordam: só o {quem} rejeita H₀, "
                        "o que é possível porque cada um testa uma hipótese diferente.")
    tamanho = (f"O efeito é {magnitude('welch', efeitos['welch'])} pelo g de Hedges "
               f"({efeitos['welch']:.3f}) e {magnitude('mann_whitney', efeitos['mann_whitney'])} "
               f"pelo δ de Cliff ({efeitos['mann_whitney']:.3f}).")
    desvio_com, desvio_sem = resultado["desvios"]
    pratica = (f"Em horas, o grupo com bot tem mediana {resultado['diferenca_medianas']:+.1f} h "
               f"e média {resultado['diferenca_medias']:+.1f} h em relação ao sem bot, "
               f"diferenças pequenas perto dos desvios padrão de {desvio_com:.0f} h e "
               f"{desvio_sem:.0f} h, o que explica o g de Hedges baixo.")
    limite = ("Como a coleta é observacional e pequena, não rejeitar H₀ não mostra que o "
              "bot não tem efeito, e uma diferença não mostra que ele a causou.")
    return " ".join([concordancia, tamanho, pratica, limite])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    resultado = aplicar_dados_reais(*grupos(carregar()))
    print(tabela_secao6(resultado).to_string(index=False))
    print(f"\n{texto_secao6(resultado)}")
