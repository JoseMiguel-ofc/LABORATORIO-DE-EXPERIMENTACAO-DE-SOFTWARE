"""Q3: mesmas taxas da grade completa, resumo por situação e textos."""

import pandas as pd
import pytest

from src.motor import EFEITOS_PADRAO, carregar_resultados, executar_grade, intervalo_wilson
from src.rodar_q3 import (SITUACOES_Q3, executar_q3, main, resumo_q3, texto_erro_tipo_i,
                          texto_poder)


@pytest.fixture
def cenario():
    return {"parametros_base": {"mu": 1.0, "sigma": 0.7}}


def test_q3_reproduz_as_linhas_da_grade_completa(cenario):
    q3 = executar_q3(reps=60, cenario=cenario)
    grade = executar_grade(reps=60, todas_situacoes=True, cenario=cenario)
    esperado = grade[grade["situacao"] != "base"].reset_index(drop=True)
    pd.testing.assert_frame_equal(q3, esperado)


def test_q3_cobre_situacoes_efeitos_e_n_pequeno(cenario):
    q3 = executar_q3(reps=20, cenario=cenario)
    assert tuple(q3["situacao"].unique()) == SITUACOES_Q3
    assert sorted(q3["efeito"].unique()) == list(EFEITOS_PADRAO)
    assert set(q3.loc[q3["situacao"] == "n_pequeno", "n"]) == {10}
    assert set(q3.loc[q3["situacao"] != "n_pequeno", "n"]) == {30}


def _grade(taxas, reps=10_000, alfa=0.05):
    """Grade sintética: taxas[situacao][teste] = taxas nos efeitos 0 e 0,5."""
    linhas = []
    for situacao, por_teste in taxas.items():
        for teste, (zero, topo) in por_teste.items():
            for efeito, taxa in ((0.0, zero), (0.5, topo)):
                rejeicoes = round(taxa * reps)
                ic_inf, ic_sup = intervalo_wilson(rejeicoes, reps)
                linhas.append({
                    "situacao": situacao, "efeito": efeito, "teste": teste, "alfa": alfa,
                    "n": 10 if situacao == "n_pequeno" else 30, "reps": reps,
                    "taxa_rejeicao": rejeicoes / reps, "ic_inf": ic_inf, "ic_sup": ic_sup,
                    "hipotese_nula_verdadeira": efeito == 0
                                                and situacao != "variancias_diferentes"})
    return pd.DataFrame(linhas)


def test_resumo_classifica_calibracao_e_quem_rejeita_mais():
    resumo = resumo_q3(_grade({
        "base": {"welch": (0.015, 0.03), "mann_whitney": (0.05, 0.10)},
        "outliers": {"welch": (0.05, 0.20), "mann_whitney": (0.05, 0.10)},
        "variancias_diferentes": {"welch": (0.03, 0.050), "mann_whitney": (0.05, 0.051)},
    })).set_index("situacao")
    assert resumo.loc["base", "calibracao_welch"] == "Conservador"
    assert resumo.loc["base", "calibracao_mann_whitney"].startswith("Compatível")
    assert resumo.loc["base", "mais_rejeicoes"] == "mann_whitney"
    assert resumo.loc["outliers", "mais_rejeicoes"] == "welch"
    assert resumo.loc["outliers", "welch_a_frente"] == 1
    assert pd.isna(resumo.loc["variancias_diferentes", "mais_rejeicoes"])
    assert not resumo.loc["variancias_diferentes", "h0_verdadeira"]


def test_texto_de_poder_aponta_inversao_e_ignora_variancias_diferentes():
    resumo = resumo_q3(_grade({
        "base": {"welch": (0.015, 0.03), "mann_whitney": (0.05, 0.10)},
        "outliers": {"welch": (0.05, 0.20), "mann_whitney": (0.05, 0.10)},
        "variancias_diferentes": {"welch": (0.03, 0.050), "mann_whitney": (0.05, 0.051)},
    }))
    texto = texto_poder(resumo)
    assert "muda conforme a situação" in texto
    assert "Welch rejeita mais em contaminação por outliers" in texto
    assert "Mann–Whitney rejeita mais em cenário base" in texto
    # A sobreposição em variâncias diferentes não entra no veredito sobre poder.
    assert "se sobrepõem" not in texto
    assert "ficam fora dessa comparação" in texto


def test_texto_sem_inversao_e_calibracao_por_situacao():
    resumo = resumo_q3(_grade({
        "base": {"welch": (0.015, 0.03), "mann_whitney": (0.05, 0.10)},
        "n_pequeno": {"welch": (0.008, 0.01), "mann_whitney": (0.052, 0.07)},
    }))
    assert "a vantagem não muda de lado" in texto_poder(resumo)
    assert "Em nenhum efeito positivo" in texto_poder(resumo)
    texto = texto_erro_tipo_i(resumo, 0.05)
    assert "Welch variou entre 0.80% e 1.50%" in texto
    assert "amostra pequena (conservador, 0.80%)" in texto
    assert "Mann–Whitney ficou compatível com 5% em todas as situações" in texto


def test_cli_salva_q3_em_destino_separado(tmp_path, capsys):
    destino = tmp_path / "q3.csv"
    main(["--reps", "30", "--saida", str(destino)])
    salvo = carregar_resultados(destino)
    assert tuple(salvo["situacao"].unique()) == tuple(sorted(SITUACOES_Q3))
    assert salvo["reps"].eq(30).all()
    assert "Salvo:" in capsys.readouterr().out
