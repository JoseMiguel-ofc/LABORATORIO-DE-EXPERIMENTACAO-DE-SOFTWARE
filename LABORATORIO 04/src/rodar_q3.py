"""Q3: Q1 e Q2 nas situações que violam pressupostos, com resumo por situação.

Usa o motor da Parte B: cada configuração reinicia a semente, então as taxas são
idênticas às da grade completa (``src.reproduzir``). Para rodar só a Q3:
python -m src.rodar_q3
"""
import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from src.cenario import ALFA, SEMENTE, ajustar_cenario
from src.conclusoes import classificacao_calibracao
from src.estilo import NOMES_SITUACAO, NOMES_TESTE
from src.experimentos import ALFAS, caminhos_alfa
from src.motor import EFEITOS_PADRAO, RAIZ, SITUACOES, salvar_resultados, simular

SITUACOES_Q3 = tuple(situacao for situacao in SITUACOES if situacao != "base")
# A amostra pequena é a única situação que muda n; as outras usam o n real.
N_POR_SITUACAO = {"n_pequeno": 10}


def executar_q3(reps=10_000, n=30, alfa=ALFA, semente=SEMENTE, cenario=None,
                progresso=None):
    """Taxas de rejeição dos dois testes em cada situação e efeito da Q3."""
    cenario = ajustar_cenario() if cenario is None else cenario
    linhas = []
    total = len(SITUACOES_Q3) * len(EFEITOS_PADRAO)
    for situacao in SITUACOES_Q3:
        for efeito in EFEITOS_PADRAO:
            if progresso is not None:
                progresso(len(linhas) + 1, total, situacao, efeito)
            linhas.append(simular(situacao, efeito, n=N_POR_SITUACAO.get(situacao, n),
                                  reps=reps, cenario=cenario, alfa=alfa, semente=semente))
    return pd.concat(linhas, ignore_index=True)


def _maior_taxa(welch, mann_whitney):
    """Qual teste rejeita mais, só quando os ICs de Wilson não se sobrepõem."""
    if mann_whitney["ic_inf"] > welch["ic_sup"]:
        return "mann_whitney"
    if welch["ic_inf"] > mann_whitney["ic_sup"]:
        return "welch"
    return None


def resumo_q3(dados):
    """Uma linha por situação: calibração no efeito zero e taxas no maior efeito.

    Aceita a grade inteira (inclusive o cenário base, que serve de referência).
    Em variâncias diferentes, efeito zero não é H0 verdadeira, e
    ``classificacao_calibracao`` já a separa do erro tipo I.
    """
    linhas = []
    maior = float(dados["efeito"].max())
    for situacao in (s for s in NOMES_SITUACAO if s in set(dados["situacao"])):
        curva = dados[dados["situacao"] == situacao].set_index(["efeito", "teste"])
        zero = {teste: curva.loc[(0.0, teste)] for teste in NOMES_TESTE}
        topo = {teste: curva.loc[(maior, teste)] for teste in NOMES_TESTE}
        linhas.append({
            "situacao": situacao,
            "n": int(zero["welch"]["n"]),
            "h0_verdadeira": bool(zero["welch"]["hipotese_nula_verdadeira"]),
            "zero_welch": float(zero["welch"]["taxa_rejeicao"]),
            "zero_mann_whitney": float(zero["mann_whitney"]["taxa_rejeicao"]),
            "calibracao_welch": classificacao_calibracao(zero["welch"]),
            "calibracao_mann_whitney": classificacao_calibracao(zero["mann_whitney"]),
            "efeito_maior": maior,
            "maior_welch": float(topo["welch"]["taxa_rejeicao"]),
            "maior_mann_whitney": float(topo["mann_whitney"]["taxa_rejeicao"]),
            "mais_rejeicoes": _maior_taxa(topo["welch"], topo["mann_whitney"]),
            # Efeitos positivos em que Welch rejeitou mais que Mann–Whitney.
            "welch_a_frente": int(sum(
                curva.loc[(efeito, "welch"), "taxa_rejeicao"]
                > curva.loc[(efeito, "mann_whitney"), "taxa_rejeicao"]
                for efeito in curva.index.get_level_values("efeito").unique() if efeito > 0)),
        })
    return pd.DataFrame(linhas)


def _lista(nomes):
    nomes = list(nomes)
    return nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]


def texto_erro_tipo_i(resumo, alfa):
    """Seção 4: em quais situações cada teste ficou perto de α e qual se desviou."""
    sob_h0 = resumo[resumo["h0_verdadeira"]]
    frases = []
    for teste, nome in NOMES_TESTE.items():
        taxas = sob_h0[f"zero_{teste}"]
        desvios = sob_h0[~sob_h0[f"calibracao_{teste}"].str.startswith("Compatível")]
        faixa = f"entre {taxas.min():.2%} e {taxas.max():.2%}"
        if desvios.empty:
            frases.append(f"{nome} ficou compatível com {alfa:.0%} em todas as "
                          f"situações sob H₀ ({faixa}).")
        else:
            situacoes = _lista(f"{NOMES_SITUACAO[s].lower()} "
                               f"({c.lower()}, {t:.2%})"
                               for s, c, t in zip(desvios["situacao"],
                                                  desvios[f"calibracao_{teste}"],
                                                  desvios[f"zero_{teste}"]))
            frases.append(f"{nome} variou {faixa} e se desviou de {alfa:.0%} nas "
                          f"situações: {situacoes}.")
    return " ".join(frases)


def texto_poder(resumo):
    """Seção 5: quem rejeita mais no maior efeito e se a vantagem muda de lado.

    Só as situações com H0 verdadeira no efeito zero comparam poder para a mesma
    hipótese; variâncias diferentes fica de fora do veredito.
    """
    nomes = {s: NOMES_SITUACAO[s].lower() for s in resumo["situacao"]}
    fora = resumo[~resumo["h0_verdadeira"]]
    resumo = resumo[resumo["h0_verdadeira"]].reset_index(drop=True)
    vencedores = resumo["mais_rejeicoes"]
    maior = resumo["efeito_maior"].iloc[0]
    diferenca = (resumo["maior_mann_whitney"] - resumo["maior_welch"]) * 100
    if vencedores.notna().all() and vencedores.nunique() == 1:
        lider = NOMES_TESTE[vencedores.iloc[0]]
        texto = (f"No efeito de +{maior:.0%}, {lider} rejeita mais em todas as "
                 "situações, e a vantagem não muda de lado. ")
    else:
        partes = []
        for teste, nome in NOMES_TESTE.items():
            situacoes = resumo.loc[vencedores == teste, "situacao"]
            if not situacoes.empty:
                partes.append(f"{nome} rejeita mais em {_lista(nomes[s] for s in situacoes)}")
        empates = resumo.loc[vencedores.isna(), "situacao"]
        if not empates.empty:
            partes.append("os intervalos se sobrepõem em "
                          f"{_lista(nomes[s] for s in empates)}")
        texto = f"No efeito de +{maior:.0%}, a vantagem muda conforme a situação: " \
                + "; ".join(partes) + ". "
    menor, maior_dif = resumo.loc[diferenca.idxmin()], resumo.loc[diferenca.idxmax()]
    texto += (f"A distância entre os testes vai de {diferenca.min():.2f} pontos percentuais "
              f"({nomes[menor['situacao']]}) a {diferenca.max():.2f} "
              f"({nomes[maior_dif['situacao']]}). ")
    inversoes = resumo.loc[resumo["welch_a_frente"] > 0, "situacao"]
    if inversoes.empty:
        texto += ("Em nenhum efeito positivo da grade Welch rejeitou mais que "
                  "Mann–Whitney.")
    else:
        texto += ("Welch rejeitou mais em algum efeito positivo de "
                  f"{_lista(nomes[s] for s in inversoes)}.")
    if not fora.empty:
        texto += (f" Em {_lista(nomes[s] for s in fora['situacao'])}, as taxas comparam "
                  "rejeições sob distribuições já diferentes, não o poder para a "
                  "mesma hipótese, e por isso ficam fora dessa comparação.")
    return texto


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reps", type=int, default=10_000)
    parser.add_argument("--alfa", type=float, default=ALFA, choices=ALFAS)
    parser.add_argument("--semente", type=int, default=SEMENTE)
    parser.add_argument("--saida", type=Path, default=None,
                        help="CSV de destino; o padrão é a grade da entrega para o α escolhido.")
    args = parser.parse_args(argv)
    caminho = caminhos_alfa(args.alfa)["simulacao"] if args.saida is None else args.saida
    caminho = caminho if caminho.is_absolute() else RAIZ / caminho
    cenario = ajustar_cenario()
    try:
        q3 = executar_q3(reps=args.reps, alfa=args.alfa, semente=args.semente,
                         cenario=cenario,
                         progresso=lambda i, total, situacao, efeito: print(
                             f"[{i}/{total}] {situacao}, efeito={efeito:+.0%}", flush=True))
        # Atualiza só as linhas da Q3 e preserva o cenário base já salvo.
        grade = salvar_resultados(q3, caminho, cenario=cenario,
                                  configuracao={**vars(args), "saida": str(caminho),
                                                "q3": True})
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    resumo = resumo_q3(grade)
    print(resumo.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print(f"\n{texto_erro_tipo_i(resumo, args.alfa)}\n\n{texto_poder(resumo)}")
    print(f"\nSalvo: {caminho}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
