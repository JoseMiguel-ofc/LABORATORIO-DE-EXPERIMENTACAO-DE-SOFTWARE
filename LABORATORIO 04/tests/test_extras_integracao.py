"""O seletor troca a análise inteira sem executar as simulações novamente."""

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.experimentos import ALFAS, carregar_amostra_alfa, carregar_simulacao_alfa

RAIZ = Path(__file__).resolve().parents[1]


def tabela_real(app):
    return next(item.value for item in app.dataframe
                if "Tamanho do efeito" in item.value.columns)


def tabela_ic(app):
    return next(item.value for item in app.dataframe
                if "Estimativa" in item.value.columns)


def figuras(app):
    return [json.loads(item.proto.spec) for item in app.get("plotly_chart")]


def test_seletor_atualiza_decisoes_e_graficos_sem_motor_ou_bootstrap():
    with patch("src.motor.simular", side_effect=AssertionError("Recalculou Monte Carlo")), \
         patch("src.intervalos_efeito.calcular_intervalos",
               side_effect=AssertionError("Recalculou bootstrap")):
        app = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=45).run()
        assert app.selectbox[0].value == .05
        assert app.selectbox[0].options == ["1%", "5%", "10%"]
        inicial = tabela_real(app).copy()
        ic = tabela_ic(app).copy()
        criticos = []
        for alfa in ALFAS:
            app.selectbox[0].set_value(alfa).run()
            assert not app.exception
            assert not app.warning
            assert len(figuras(app)) == 5
            real = tabela_real(app)
            for campo in ("Estatística", "p-valor", "Tamanho do efeito"):
                pd.testing.assert_series_equal(real[campo], inicial[campo])
            assert list(real[f"Decisão (α = {alfa:.0%})"]) == [
                "Não rejeitar H₀", "Rejeitar H₀" if alfa == .10 else "Não rejeitar H₀"]
            pd.testing.assert_frame_equal(tabela_ic(app), ic)
            graficos = figuras(app)
            assert all(fig["layout"]["meta"]["alfa"] == alfa for fig in graficos[1:])
            criticos.append(graficos[1]["layout"]["meta"]["testes"]["mann_whitney"]["critico"])
            assert graficos[2]["layout"]["shapes"][0]["y0"] == pytest.approx(alfa * 100)
            assert all(f"α = {alfa:.0%}" in fig["layout"]["title"]["text"]
                       for fig in graficos[2:])
        assert criticos[0] > criticos[1] > criticos[2]


def test_cache_ausente_nao_exibe_resultados_de_outro_alfa():
    app = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=45).run()
    with patch("src.experimentos.carregar_simulacao_alfa", side_effect=FileNotFoundError()), \
         patch("src.experimentos.carregar_amostra_alfa", side_effect=FileNotFoundError()), \
         patch("src.intervalos_efeito.carregar_intervalos", side_effect=ValueError("Método mudou")):
        app.selectbox[0].set_value(.01).run()
    assert not app.exception
    assert len(app.warning) == 3
    assert len(figuras(app)) == 2
    assert [item.value for item in app.code].count(
        ".venv/bin/python -m src.experimentos --alfas 0.01") == 2
    assert any("src.intervalos_efeito" in item.value for item in app.code)
    assert not any("Estimativa" in item.value.columns for item in app.dataframe)


@pytest.mark.parametrize("carregar,chaves", [
    (carregar_simulacao_alfa, ["situacao", "efeito", "n", "teste"]),
    (carregar_amostra_alfa, ["referencia_efeito", "n", "teste"]),
])
def test_producao_usa_mesmos_sorteios_taxas_monotonicas_e_dez_mil_repeticoes(carregar, chaves):
    anterior = None
    for alfa in ALFAS:
        dados = carregar(alfa)
        assert dados["alfa"].eq(alfa).all()
        assert dados["reps"].eq(10_000).all()
        assert dados["semente"].eq(42).all()
        atual = dados.set_index(chaves)["rejeicoes"]
        if anterior is not None:
            comuns = atual.index.intersection(anterior.index)
            assert len(comuns) > 0
            assert np.all(atual.loc[comuns] >= anterior.loc[comuns])
        anterior = atual
