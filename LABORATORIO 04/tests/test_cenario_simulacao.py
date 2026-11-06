"""Verifica o ajuste e o significado experimental do gerador da Sprint 1."""

import math
import statistics

import numpy as np
import pandas as pd
import pytest

from src.cenario import ALFA, ALTERNATIVA, SEMENTE, ajustar_cenario
from src.dados import carregar
from src.simulacao import gerar


@pytest.fixture
def dados_pequenos():
    return pd.DataFrame({"grupo": ["com_bot"] * 3 + ["sem_bot"] * 3,
                         "horas": [1.0, 2.0, 4.0, 3.0, 9.0, 27.0]})


@pytest.fixture
def cenario(dados_pequenos):
    return ajustar_cenario(dados_pequenos)


def test_parametros_calculados_dos_logaritmos_e_preservacao_dos_dados(dados_pequenos):
    original = dados_pequenos.copy(deep=True)
    cenario = ajustar_cenario(dados_pequenos)
    for grupo, horas in (("com_bot", [1, 2, 4]), ("sem_bot", [3, 9, 27])):
        logs = [math.log(valor) for valor in horas]
        mu, sigma = statistics.mean(logs), statistics.stdev(logs)
        parametros = cenario["parametros_descritivos"][grupo]
        assert parametros == pytest.approx({
            "mu": mu, "sigma": sigma, "n": 3,
            "media_modelo": math.exp(mu + sigma**2 / 2),
            "mediana_modelo": math.exp(mu),
        })
    todos = [math.log(valor) for valor in [1, 2, 4, 3, 9, 27]]
    assert cenario["parametros_base"] == pytest.approx({
        "mu": statistics.mean(todos), "sigma": statistics.stdev(todos),
    })
    assert cenario["n_por_grupo"] == {"com_bot": 3, "sem_bot": 3}
    pd.testing.assert_frame_equal(dados_pequenos, original)


def test_ajuste_da_amostra_real_versionada():
    dados = carregar()
    cenario = ajustar_cenario()
    assert cenario["n_por_grupo"] == {"com_bot": 30, "sem_bot": 30}
    for grupo in ("com_bot", "sem_bot"):
        logs = [math.log(valor) for valor in dados.loc[dados.grupo == grupo, "horas"]]
        assert cenario["parametros_descritivos"][grupo]["mu"] == pytest.approx(
            statistics.mean(logs))
        assert cenario["parametros_descritivos"][grupo]["sigma"] == pytest.approx(
            statistics.stdev(logs))
    logs = [math.log(valor) for valor in dados.horas]
    assert cenario["parametros_base"]["sigma"] == pytest.approx(statistics.stdev(logs))
    assert ALFA == 0.05
    assert ALTERNATIVA == "two-sided"


def test_h0_mesmos_parametros_com_sorteios_independentes(cenario):
    amostras = gerar(n=8, cenario=cenario)
    rng = np.random.default_rng(SEMENTE)
    mu, sigma = cenario["parametros_base"].values()
    np.testing.assert_array_equal(amostras["com_bot"], rng.lognormal(mu, sigma, 8))
    np.testing.assert_array_equal(amostras["sem_bot"], rng.lognormal(mu, sigma, 8))
    assert not np.array_equal(amostras["com_bot"], amostras["sem_bot"])
    assert not np.shares_memory(amostras["com_bot"], amostras["sem_bot"])


@pytest.mark.parametrize("efeito", [0.3, -0.3, 1.0])
def test_efeito_altera_so_escala_do_grupo_com_bot(cenario, efeito):
    base = gerar(n=12, cenario=cenario)
    alterada = gerar(n=12, efeito=efeito, cenario=cenario)
    np.testing.assert_array_equal(alterada["com_bot"], base["com_bot"] * (1 + efeito))
    np.testing.assert_array_equal(alterada["sem_bot"], base["sem_bot"])


def test_rng_padrao_reproduz_e_rng_fornecido_avanca(cenario):
    primeira = gerar(cenario=cenario)
    segunda = gerar(cenario=cenario)
    for grupo in primeira:
        np.testing.assert_array_equal(primeira[grupo], segunda[grupo])
    rng = np.random.default_rng(99)
    primeira = gerar(rng=rng, cenario=cenario)
    segunda = gerar(rng=rng, cenario=cenario)
    assert not np.array_equal(primeira["com_bot"], segunda["com_bot"])
    refeito = gerar(rng=np.random.default_rng(99), cenario=cenario)
    np.testing.assert_array_equal(primeira["com_bot"], refeito["com_bot"])


def test_ajuste_real_preserva_parametros_individuais(cenario):
    amostras = gerar(n=10, situacao="ajuste_real", cenario=cenario)
    rng = np.random.default_rng(SEMENTE)
    for grupo in ("com_bot", "sem_bot"):
        parametros = cenario["parametros_descritivos"][grupo]
        np.testing.assert_array_equal(
            amostras[grupo], rng.lognormal(parametros["mu"], parametros["sigma"], 10))
        assert np.all(amostras[grupo] > 0)


@pytest.mark.parametrize("n", [True, False, 0, 1, -3, 2.5, "30", None])
def test_rejeita_tamanho_invalido(cenario, n):
    with pytest.raises(ValueError, match="n deve"):
        gerar(n=n, cenario=cenario)


@pytest.mark.parametrize("efeito", [-1, -2, math.inf, -math.inf, math.nan, "0.3", True])
def test_rejeita_efeito_invalido(cenario, efeito):
    with pytest.raises(ValueError, match="efeito deve"):
        gerar(efeito=efeito, cenario=cenario)


def test_rejeita_situacoes_nao_implementadas_e_efeito_no_ajuste(cenario):
    with pytest.raises(ValueError, match="situacao deve"):
        gerar(situacao="Q3", cenario=cenario)
    with pytest.raises(ValueError, match="efeito zero"):
        gerar(situacao="ajuste_real", efeito=0.3, cenario=cenario)
    with pytest.raises(ValueError, match="Generator"):
        gerar(rng=42, cenario=cenario)


@pytest.mark.parametrize("valor", [0, -1, math.nan, math.inf, -math.inf])
def test_rejeita_horas_nao_positivas_ou_nao_finitas(dados_pequenos, valor):
    dados_pequenos.loc[0, "horas"] = valor
    with pytest.raises(ValueError, match="positivos e finitos"):
        ajustar_cenario(dados_pequenos)


def test_rejeita_grupo_ausente_desconhecido_e_nulo(dados_pequenos):
    with pytest.raises(ValueError, match="exatamente os grupos"):
        ajustar_cenario(dados_pequenos.iloc[:3])
    dados_pequenos.loc[0, "grupo"] = "outro"
    with pytest.raises(ValueError, match="exatamente os grupos"):
        ajustar_cenario(dados_pequenos)
    dados_pequenos.loc[0, "grupo"] = None
    with pytest.raises(ValueError, match="exatamente os grupos"):
        ajustar_cenario(dados_pequenos)


def test_rejeita_grupo_sem_variabilidade_ou_com_um_elemento(dados_pequenos):
    with pytest.raises(ValueError, match="pelo menos duas"):
        ajustar_cenario(dados_pequenos.iloc[2:])
    dados_pequenos.loc[dados_pequenos.grupo == "com_bot", "horas"] = 2
    with pytest.raises(ValueError, match="variabilidade"):
        ajustar_cenario(dados_pequenos)


def test_rejeita_estrutura_e_texto_invalidos(dados_pequenos):
    with pytest.raises(ValueError, match="colunas grupo e horas"):
        ajustar_cenario(pd.DataFrame())
    dados_pequenos["horas"] = dados_pequenos["horas"].astype(object)
    dados_pequenos.loc[0, "horas"] = "tempo desconhecido"
    with pytest.raises(ValueError, match="numéricos"):
        ajustar_cenario(dados_pequenos)


@pytest.mark.parametrize("base", [{}, {"mu": 0, "sigma": 0},
                                  {"mu": math.inf, "sigma": 1},
                                  {"mu": 0, "sigma": math.nan}])
def test_rejeita_parametros_externos_invalidos(base):
    with pytest.raises(ValueError):
        gerar(cenario={"parametros_base": base})
