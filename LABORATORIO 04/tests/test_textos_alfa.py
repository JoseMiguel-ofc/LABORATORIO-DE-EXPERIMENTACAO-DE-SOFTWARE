"""Interpretações devem acompanhar o alfa selecionado e as taxas observadas."""

import numpy as np
import pandas as pd
import pytest

from src.conclusoes import textos_simulacao, validar_configuracao_dashboard


def grade(alfa=.05):
    linhas = []
    for situacao in ("base", "assimetria_forte", "outliers", "n_pequeno",
                     "variancias_diferentes"):
        for efeito in (0, .1, .2, .3, .4, .5):
            for teste in ("welch", "mann_whitney"):
                taxa = alfa if efeito == 0 else (.12 if teste == "welch" else .31)
                linhas.append({
                    "situacao": situacao, "teste": teste, "efeito": efeito,
                    "n": 10 if situacao == "n_pequeno" else 30,
                    "reps": 10_000, "semente": 42, "alfa": alfa,
                    "taxa_rejeicao": taxa, "ic_inf": max(0, taxa-.005),
                    "ic_sup": taxa+.005,
                    "hipotese_nula_verdadeira": efeito == 0
                    and situacao != "variancias_diferentes",
                })
    return pd.DataFrame(linhas)


@pytest.mark.parametrize("alfa", [.01, .05, .10])
def test_grade_da_entrega_aceita_o_alfa_selecionado(alfa):
    dados = grade(alfa)
    original = dados.copy(deep=True)
    validar_configuracao_dashboard(dados, alfa=alfa)
    pd.testing.assert_frame_equal(dados, original)


@pytest.mark.parametrize("alfa", [.01, .10])
def test_grade_de_outro_alfa_exige_selecao_explicita(alfa):
    with pytest.raises(ValueError, match="configuração da entrega"):
        validar_configuracao_dashboard(grade(alfa))


@pytest.mark.parametrize("alfa", [0, .025, .2, 1, np.nan, True])
def test_dashboard_nao_aceita_alfa_fora_das_tres_opcoes(alfa):
    with pytest.raises(ValueError, match="alfa|α"):
        validar_configuracao_dashboard(grade(), alfa=alfa)


@pytest.mark.parametrize("coluna,valor", [
    ("n", 20), ("reps", 100), ("semente", 7), ("efeito", .75), ("alfa", .05),
])
def test_mudar_alfa_nao_relaxa_os_demais_requisitos_da_entrega(coluna, valor):
    dados = grade(.01)
    dados.loc[0, coluna] = valor
    with pytest.raises(ValueError, match="configuração da entrega"):
        validar_configuracao_dashboard(dados, alfa=.01)


def test_dashboard_mantem_as_cinco_situacoes_e_sessenta_pontos():
    dados = grade(.10)
    with pytest.raises(ValueError, match="cinco situações"):
        validar_configuracao_dashboard(dados[dados.situacao == "base"], alfa=.10)
    with pytest.raises(ValueError, match="cinco situações"):
        validar_configuracao_dashboard(dados.iloc[:-1], alfa=.10)


@pytest.mark.parametrize("alfa", [.01, .05, .10])
def test_textos_inferem_alpha_e_mantem_a_confianca_monte_carlo_em_95(alfa):
    textos = textos_simulacao(grade(alfa))
    rotulo = f"α = {100 * alfa:g}%"
    assert set(textos) == {"erro_tipo_i", "poder", "previsao", "recomendacao"}
    assert all(rotulo in texto for texto in textos.values())
    assert f"referência nominal de {100 * alfa:g}%" in textos["erro_tipo_i"]
    assert "intervalos de 95%" in textos["erro_tipo_i"]
    assert "12.00%" in textos["poder"] and "31.00%" in textos["poder"]
    assert "19.00 pontos percentuais" in textos["previsao"]
    assert "H₀ é falsa e a taxa de rejeição mede poder" in textos["poder"]
    assert "variâncias diferentes" in textos["poder"]
    assert "probabilidade de rejeição não é erro tipo I" in textos["poder"]


@pytest.mark.parametrize("alfa_invalido", [.05, np.nan, np.inf, 0, 1])
def test_textos_rejeitam_alfa_misto_ou_invalido(alfa_invalido):
    dados = grade(.01)
    dados.loc[0, "alfa"] = alfa_invalido
    with pytest.raises(ValueError, match="único alfa"):
        textos_simulacao(dados)


def test_textos_exigem_metadado_alfa():
    with pytest.raises(ValueError, match="único alfa"):
        textos_simulacao(grade().drop(columns="alfa"))


@pytest.mark.parametrize("alfa", [.01, .10])
def test_confronto_usa_resultados_reais_sem_fixar_o_vencedor_ou_n(alfa):
    dados = grade(alfa)
    dados = dados[(dados.situacao == "base") & (dados.efeito <= .2)].copy()
    dados["n"] = 17
    ponto_final = dados.efeito == .2
    dados.loc[ponto_final & (dados.teste == "welch"), "taxa_rejeicao"] = .4
    dados.loc[ponto_final & (dados.teste == "mann_whitney"), "taxa_rejeicao"] = .2
    textos = textos_simulacao(dados)
    assert "n = 17" in textos["poder"] and "+20%" in textos["poder"]
    assert "40.00% para Welch" in textos["poder"]
    assert "20.00% para Mann–Whitney" in textos["poder"]
    assert "não se confirmou" in textos["previsao"]
    assert "Welch teve 20.00 pontos percentuais a mais" in textos["previsao"]
    dados.loc[ponto_final, "taxa_rejeicao"] = .2
    assert "coincidiram" in textos_simulacao(dados)["previsao"]
