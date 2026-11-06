"""Valores de referência e invariantes estatísticos da Sprint 1 B."""

import json

import numpy as np
import pytest
from scipy import stats

from src.graficos import CORES_TESTE, g1, g2
from src.testes import aplicar_testes


def test_welch_contra_calculo_analitico():
    resultado = aplicar_testes([1, 2, 3], [3, 5, 7])["welch"]
    t = -np.sqrt(27 / 5)
    gl = 50 / 17
    p = 2 * stats.t.sf(abs(t), df=gl)
    assert resultado["estatistica"] == pytest.approx(t)
    assert resultado["gl"] == pytest.approx(gl)
    assert resultado["p_valor"] == pytest.approx(p)
    assert resultado["rejeita_h0"] is False
    assert "não prova igualdade" in resultado["interpretacao"]


def test_mann_whitney_contra_u_e_variancia_analiticos():
    resultado = aplicar_testes([1, 2, 3], [4, 5, 6])["mann_whitney"]
    assert resultado["estatistica"] == 0
    assert resultado["media_u_h0"] == 4.5
    assert resultado["desvio_u_h0"] ** 2 == pytest.approx(5.25)
    assert resultado["z"] == pytest.approx(-4.5 / np.sqrt(5.25))
    assert resultado["p_valor"] == pytest.approx(0.049534613435626706)
    assert resultado["rejeita_h0"] is True
    assert resultado["correcao_empates"] is False


def test_mann_whitney_com_empates_ajusta_variancia():
    resultado = aplicar_testes([1, 2, 2, 4], [2, 3, 4, 4])["mann_whitney"]
    assert resultado["estatistica"] == 4
    assert resultado["desvio_u_h0"] ** 2 == pytest.approx(76 / 7)
    assert resultado["z"] == pytest.approx(-4 / np.sqrt(76 / 7))
    assert resultado["p_valor"] == pytest.approx(2 * stats.norm.sf(4 / np.sqrt(76 / 7)))
    assert resultado["correcao_empates"] is True


@pytest.mark.parametrize("com_bot,sem_bot", [
    ([1, 7, 8, 11], [2, 5, 10, 13, 19, 21]),
    ([1, 1, 2, 4, 5], [2, 2, 4, 4, 6, 8]),
])
def test_resultados_conferem_com_scipy(com_bot, sem_bot):
    resultados = aplicar_testes(com_bot, sem_bot)
    esperado_w = stats.ttest_ind(com_bot, sem_bot, equal_var=False, alternative="two-sided")
    esperado_u = stats.mannwhitneyu(com_bot, sem_bot, method="asymptotic",
                                  use_continuity=False, alternative="two-sided")
    assert resultados["welch"]["estatistica"] == pytest.approx(esperado_w.statistic)
    assert resultados["welch"]["p_valor"] == pytest.approx(esperado_w.pvalue)
    assert resultados["mann_whitney"]["estatistica"] == pytest.approx(esperado_u.statistic)
    assert resultados["mann_whitney"]["p_valor"] == pytest.approx(esperado_u.pvalue)


def test_trocar_grupos_inverte_t_z_complementa_u_e_preserva_p():
    a, b = [2, 3, 4, 7], [1, 5, 8, 9, 12]
    original, trocado = aplicar_testes(a, b), aplicar_testes(b, a)
    assert original["welch"]["estatistica"] == pytest.approx(-trocado["welch"]["estatistica"])
    assert original["mann_whitney"]["z"] == pytest.approx(-trocado["mann_whitney"]["z"])
    assert original["mann_whitney"]["estatistica"] + trocado["mann_whitney"]["estatistica"] == len(a) * len(b)
    for teste in original:
        assert original[teste]["p_valor"] == pytest.approx(trocado[teste]["p_valor"])


def test_mudanca_comum_de_unidade_preserva_testes():
    a, b = np.array([2, 3, 4, 7]), np.array([1, 5, 8, 9, 12])
    horas, minutos = aplicar_testes(a, b), aplicar_testes(a * 60, b * 60)
    for teste in horas:
        assert horas[teste]["estatistica"] == pytest.approx(minutos[teste]["estatistica"])
        assert horas[teste]["p_valor"] == pytest.approx(minutos[teste]["p_valor"])


def test_amostras_iguais_nao_degeneradas_tem_p_um():
    resultado = aplicar_testes([1, 2, 3, 4], [1, 2, 3, 4])
    for teste in resultado.values():
        assert teste["p_valor"] == 1
        assert teste["rejeita_h0"] is False


def test_rejeicao_usa_p_estritamente_menor_que_alfa():
    a, b = [1, 2, 3], [4, 5, 6]
    p = aplicar_testes(a, b)["mann_whitney"]["p_valor"]
    assert aplicar_testes(a, b, alfa=p)["mann_whitney"]["rejeita_h0"] is False
    assert aplicar_testes(a, b, alfa=p * 1.01)["mann_whitney"]["rejeita_h0"] is True


@pytest.mark.parametrize("valores", [[], [1], [[1, 2], [3, 4]], [1, np.nan],
                                       [1, np.inf], [1, -np.inf], [1, "a"],
                                       [1j, 2j], [True, False], None])
@pytest.mark.parametrize("posicao", [0, 1])
def test_rejeita_amostras_invalidas(valores, posicao):
    grupos = [[1, 2, 3], [4, 5, 6]]
    grupos[posicao] = valores
    with pytest.raises(ValueError):
        aplicar_testes(*grupos)


@pytest.mark.parametrize("alfa", [0, 1, -0.1, 1.1, np.nan, np.inf, True, [], "x"])
def test_rejeita_alfa_invalido(alfa):
    with pytest.raises(ValueError, match="alfa"):
        aplicar_testes([1, 2], [2, 3], alfa=alfa)


@pytest.mark.parametrize("a,b", [([1, 1], [1, 1]), ([1, 1], [2, 2])])
def test_duas_amostras_constantes_sao_degeneradas(a, b):
    with pytest.raises(ValueError, match="constantes"):
        aplicar_testes(a, b)


def test_resultados_sao_serializaveis_sem_nan():
    json.dumps(aplicar_testes([1, 2, 4], [3, 5, 9, 11]), allow_nan=False)


@pytest.mark.parametrize("alfa", [0.01, 0.05, 0.10])
@pytest.mark.parametrize("inverter", [False, True])
def test_g2_fronteiras_e_areas_correspondem_aos_p_valores(alfa, inverter):
    a, b = [1, 2, 2, 4, 7], [2, 3, 4, 4, 9, 12]
    resultados = aplicar_testes(*( [b, a] if inverter else [a, b]), alfa=alfa)
    figura = g2(resultados, alfa=alfa)
    for chave in ("welch", "mann_whitney"):
        resultado = resultados[chave]
        distribuicao = stats.t(df=resultado["gl"]) if chave == "welch" else stats.norm()
        observado = resultado["estatistica"] if chave == "welch" else resultado["z"]
        caudas = [t for t in figura.data if t.meta["teste"] == chave
                  and t.meta["tipo"] == "p_valor"]
        assert len(caudas) == 2
        for cauda in caudas:
            assert cauda.meta["corte"] == abs(observado)
            assert cauda.meta["area"] == pytest.approx(resultado["p_valor"] / 2)
            x, y = np.asarray(cauda.x), np.asarray(cauda.y)
            assert np.max(x) == -abs(observado) if cauda.meta["lado"] < 0 else np.min(x) == abs(observado)
            # A janela é finita; somar a massa residual analítica recupera a cauda.
            integral = np.trapezoid(y, x) + cauda.meta["massa_fora_janela"]
            assert integral == pytest.approx(resultado["p_valor"] / 2, abs=2e-5)
        criticas = [t for t in figura.data if t.meta["teste"] == chave
                    and t.meta["tipo"] == "rejeicao"]
        assert sum(t.meta["area"] for t in criticas) == pytest.approx(alfa)
        assert criticas[0].meta["corte"] == pytest.approx(distribuicao.isf(alfa / 2))
        linha = next(t for t in figura.data if t.meta["teste"] == chave
                     and t.meta["tipo"] == "observado")
        assert linha.x == (observado, observado)
        assert linha.line.color == CORES_TESTE[chave]
    assert "aproximadas sob H₀" in figura.layout.title.text
    json.loads(figura.to_json())


def test_g2_p_um_sombreia_as_duas_metades():
    figura = g2(aplicar_testes([1, 2, 3], [1, 2, 3]))
    caudas_p = [t for t in figura.data if t.meta["tipo"] == "p_valor"]
    assert all(t.meta["corte"] == 0 and t.meta["area"] == 0.5 for t in caudas_p)


def test_g2_recusa_p_incompativel_com_referencia():
    resultados = aplicar_testes([1, 2, 3], [4, 5, 6])
    resultados["mann_whitney"]["p_valor"] = 0.9
    with pytest.raises(ValueError, match="não corresponde"):
        g2(resultados)


def test_g1_continua_funcionando():
    grupos = {"com_bot": np.array([1, 2, 4, 8]),
              "sem_bot": np.array([2, 4, 8, 16])}
    figura = g1(grupos, grupos)
    assert len(figura.data) == 4
    assert figura.layout.title.text.startswith("G1:")
