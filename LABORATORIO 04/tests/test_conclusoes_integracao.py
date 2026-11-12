"""Verifica interpretações e integração sem repetir a simulação no dashboard."""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.conclusoes import (classificacao_calibracao, textos_simulacao,
                            validar_configuracao_dashboard)

RAIZ = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("ic_inf,ic_sup,esperado", [
    (0.01, 0.03, "Conservador"), (0.06, 0.09, "Liberal"),
    (0.04, 0.06, "Compatível com α no IC de 95%"),
])
def test_calibracao_considera_incerteza_monte_carlo(ic_inf, ic_sup, esperado):
    linha = dict(ic_inf=ic_inf, ic_sup=ic_sup, alfa=.05,
                 hipotese_nula_verdadeira=True)
    assert classificacao_calibracao(linha) == esperado
    linha["hipotese_nula_verdadeira"] = False
    assert "Não é erro tipo I" in classificacao_calibracao(linha)


def grade_minima(mw=.3, welch=.1):
    return pd.DataFrame([
        {"situacao": "base", "efeito": efeito, "teste": teste,
         "n": 30, "taxa_rejeicao": taxa, "ic_inf": taxa-.01,
         "ic_sup": taxa+.01, "alfa": .05, "hipotese_nula_verdadeira": efeito == 0}
        for efeito in (0, .5)
        for teste, taxa in (("welch", .02 if efeito == 0 else welch),
                            ("mann_whitney", .05 if efeito == 0 else mw))
    ])


def test_conclusao_muda_com_os_resultados_em_vez_de_fixar_um_vencedor():
    assert "compatível" in textos_simulacao(grade_minima())["previsao"]
    assert "não se confirmou" in textos_simulacao(grade_minima(mw=.1, welch=.3))["previsao"]
    assert "coincidiram" in textos_simulacao(grade_minima(mw=.1, welch=.1))["previsao"]
    texto = textos_simulacao(grade_minima())["poder"]
    assert "10.00%" in texto and "30.00%" in texto


def test_nao_mistura_grades_ou_inventa_q1_ausente():
    df = grade_minima()
    with pytest.raises(ValueError, match="configuração"):
        textos_simulacao(pd.concat([df, df]))
    with pytest.raises(ValueError, match="Q1"):
        textos_simulacao(df[df["efeito"] > 0])


@pytest.mark.parametrize("coluna,valor", [("alfa", .1), ("n", 50),
                                           ("reps", 100), ("semente", 123)])
def test_dashboard_nao_mistura_diagnostico_com_textos_da_entrega(coluna, valor):
    from src.motor import carregar_resultados
    dados = carregar_resultados()
    validar_configuracao_dashboard(dados)
    dados.loc[0, coluna] = valor
    with pytest.raises(ValueError, match="configuração da entrega"):
        validar_configuracao_dashboard(dados)


def test_dashboard_usa_csv_sem_reexecutar_motor():
    with patch("src.motor.simular", side_effect=AssertionError("Motor chamado pelo app")):
        app = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=45).run()
    assert not app.exception
    assert not app.warning
    assert len(app.header) == 7
    assert len(app.get("plotly_chart")) == 5
    assert not any("previsto para" in aviso.value for aviso in app.info)
    real = next(item.value for item in app.dataframe
                if "Medida do efeito" in item.value.columns)
    assert set(real["Medida do efeito"]) == {"g de Hedges", "δ de Cliff"}
    assert real["p-valor"].between(0, 1).all()
    assert real["Tamanho do efeito"].notna().all()


def test_dashboard_orienta_se_resultados_estiverem_ausentes():
    with patch("src.motor.carregar_resultados", side_effect=FileNotFoundError("simulacao.csv")), \
         patch("src.amostra.carregar_amostra", side_effect=FileNotFoundError("amostra.csv")):
        app = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=45).run()
    assert not app.exception
    assert len(app.warning) == 2
    assert len(app.code) == 2
    assert all("src.experimentos --alfas 0.05" in item.value for item in app.code)
