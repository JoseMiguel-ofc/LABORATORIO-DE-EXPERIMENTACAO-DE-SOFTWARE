"""Medidas descritivas e planejamento: casos analíticos, incerteza e proveniência."""

import json
import math

import numpy as np
import pandas as pd
import pytest

from src import amostra, motor
from src.efeito import cliffs_delta, hedges_g


@pytest.mark.parametrize("com,sem,esperado", [
    ([1, 2], [3, 4], -2 * math.sqrt(2) / math.sqrt(math.pi)),
    ([1, 2, 3], [4, 5, 6], -3 * math.sqrt(2 / math.pi)),
    ([1, 2, 3], [1, 2, 3], 0),
])
def test_hedges_usa_desvio_amostral_e_correcao_exata(com, sem, esperado):
    assert hedges_g(com, sem) == pytest.approx(esperado)


@pytest.mark.parametrize("funcao", [hedges_g, cliffs_delta])
def test_efeitos_invariantes_a_unidade_e_simetria(funcao):
    com, sem = np.array([1., 2., 4., 8.]), np.array([2., 4., 5., 16.])
    efeito = funcao(com, sem)
    assert funcao(sem, com) == pytest.approx(-efeito)
    assert funcao(com * 3600, sem * 3600) == pytest.approx(efeito)
    assert funcao(com + 100, sem + 100) == pytest.approx(efeito)


def test_hedges_escala_extrema_finita_sem_overflow():
    assert hedges_g(np.array([1, 2, 3]) * 1e150, np.array([4, 5, 6]) * 1e150) == pytest.approx(
        hedges_g([1, 2, 3], [4, 5, 6]))


def test_hedges_grupo_unico_constante_valido_e_ambos_constantes_invalidos():
    assert math.isfinite(hedges_g([1, 1, 1], [1, 2, 3]))
    for com, sem in (([0, 0], [0, 0]), ([1, 1], [1, 1]), ([1, 1], [2, 2])):
        with pytest.raises(ValueError, match="desvio combinado zero"):
            hedges_g(com, sem)


@pytest.mark.parametrize("com,sem,esperado", [
    ([3, 4], [1, 2], 1), ([1, 2], [3, 4], -1),
    ([1, 1], [1, 1], 0), ([1, 1], [2, 2], -1),
    ([1, 2], [2, 3], -0.75), ([1, 2, 3], [1, 2, 3], 0),
])
def test_delta_empates_e_orientacao(com, sem, esperado):
    assert cliffs_delta(com, sem) == pytest.approx(esperado)
    pares = [int(x > y) - int(x < y) for x in com for y in sem]
    assert cliffs_delta(com, sem) == pytest.approx(np.mean(pares))


@pytest.mark.parametrize("funcao", [hedges_g, cliffs_delta])
@pytest.mark.parametrize("invalida", [[], [1], [[1, 2]], [True, False], [1, np.nan],
                                     [1, np.inf], [1+2j, 3j], ["1", "2"]])
def test_efeitos_rejeitam_amostra_invalida(funcao, invalida):
    with pytest.raises(ValueError):
        funcao(invalida, [1, 2, 3])


@pytest.fixture
def dados():
    return pd.DataFrame({"grupo": ["com_bot"] * 3 + ["sem_bot"] * 3,
                         "horas": [2., 4., 8., 1., 2., 4.]})


@pytest.fixture
def simular_falso(monkeypatch):
    chamadas = []

    def simular(**kwargs):
        chamadas.append(kwargs)
        return pd.DataFrame([
            {"situacao": "base", "efeito": kwargs["efeito"], "n": kwargs["n"],
             "reps": kwargs["reps"], "teste": teste, "alfa": kwargs["alfa"],
             "rejeicoes": 5, "taxa_rejeicao": 0.5, "ic_inf": 0.2, "ic_sup": 0.8,
             "hipotese_nula_verdadeira": False, "semente": kwargs["semente"]}
            for teste in kwargs["testes"]])
    monkeypatch.setattr(motor, "simular", simular)
    return chamadas


def test_planejamento_inclui_n_real_razao_mediana_e_reutiliza_celulas(dados, simular_falso):
    original = dados.copy(deep=True)
    resultado = amostra.analisar_amostra([10, 3, 5, 10], reps=10, df=dados, buscar_alvo=False)
    assert len(resultado) == 12
    assert set(resultado.n) == {3, 5, 10}
    assert set(resultado.n_real_por_grupo) == {3}
    assert set(resultado.query("referencia_efeito == 'observado_mediana'").efeito) == {1.0}
    assert set(resultado.query("referencia_efeito == 'planejado_30pct'").efeito) == {0.3}
    assert [chamada["n"] for chamada in simular_falso] == [3, 5, 10, 3, 5, 10]
    assert all(chamada["situacao"] == "base" for chamada in simular_falso)
    assert resultado.attrs["metadados"]["parametros"]["grade_n"] == [3, 5, 10]
    pd.testing.assert_frame_equal(dados, original)


def test_mesmo_efeito_com_nomes_diferentes_reutiliza_simulacao(dados, simular_falso):
    resultado = amostra.analisar_amostra([3, 5], efeitos={"a": .3, "b": .3}, reps=10,
                                        df=dados, buscar_alvo=False)
    assert len(resultado) == 8
    assert len(simular_falso) == 2


@pytest.mark.parametrize("kwargs", [
    {"grade_n": []}, {"grade_n": [1]}, {"grade_n": [3.2]}, {"grade_n": [True]},
    {"grade_n": None}, {"reps": 0}, {"reps": True}, {"semente": -1},
    {"alfa": 1}, {"tamanho_lote": 0}, {"efeitos": {}}, {"efeitos": {"x": 0}},
    {"efeitos": {"x": -1}}, {"efeitos": {"x": np.nan}}, {"efeitos": {"": .3}},
    {"efeitos": {"x": True}}, {"progresso": True},
    {"buscar_alvo": "sim"}, {"n_max": 1}, {"n_max": 2},
])
def test_planejamento_rejeita_parametros_invalidos(dados, simular_falso, kwargs):
    argumentos = {"df": dados, "grade_n": [3], "reps": 10, **kwargs}
    with pytest.raises(ValueError):
        amostra.analisar_amostra(**argumentos)
    assert not simular_falso


def test_planejamento_rejeita_dados_desbalanceados(dados, simular_falso):
    with pytest.raises(ValueError, match="mesmo tamanho"):
        amostra.analisar_amostra([3], df=dados.iloc[1:], reps=10)


def test_grade_pequena_real_reproduz_semente(dados):
    a = amostra.analisar_amostra([3, 5], efeitos={"piloto": .3}, reps=20, df=dados,
                                tamanho_lote=7, buscar_alvo=False)
    b = amostra.analisar_amostra([5, 3], efeitos={"piloto": .3}, reps=20, df=dados,
                                tamanho_lote=13, buscar_alvo=False)
    pd.testing.assert_frame_equal(a, b)
    assert len(a) == 4
    assert a.reps.eq(20).all()


@pytest.fixture
def curvas():
    return pd.DataFrame([
        {"referencia_efeito": "x", "teste": teste, "n": n, "reps": 100,
         "taxa_rejeicao": poder, "ic_inf": max(0, poder - .06), "ic_sup": min(1, poder + .06)}
        for teste, poderes in (("welch", [.2, .7, .79]), ("mann_whitney", [.4, .81, .9]))
        for n, poder in zip([10, 30, 100], poderes)
    ])


def test_resumo_primeiro_ponto_80_sem_extrapolar_e_com_incerteza(curvas):
    resumo = amostra.resumir_amostra(curvas).set_index("teste")
    mw = resumo.loc["mann_whitney"]
    assert mw.n_grade_80 == 30
    assert mw.atingiu_alvo
    assert not mw.limite_inferior_atinge_alvo
    welch = resumo.loc["welch"]
    assert np.isnan(welch.n_grade_80)
    assert not welch.atingiu_alvo
    assert welch.limite_censurado == "> 100"
    assert welch.n_ponto_reportado == 100
    assert welch.poder_ponto_reportado == .79


def test_resumo_nao_pressupoe_monotonicidade(curvas):
    curvas.loc[(curvas.teste == "welch") & (curvas.n == 10), ["taxa_rejeicao", "ic_inf", "ic_sup"]] = [.85, .80, .9]
    resumo = amostra.resumir_amostra(curvas).set_index("teste")
    assert resumo.loc["welch", "n_grade_80"] == 10
    assert resumo.loc["welch", "limite_inferior_atinge_alvo"]


@pytest.mark.parametrize("alteracao", ["vazio", "duplicado", "nan", "probabilidade", "ic", "n", "teste"])
def test_resumo_valida_curvas(curvas, alteracao):
    if alteracao == "vazio":
        curvas = curvas.iloc[:0]
    elif alteracao == "duplicado":
        curvas = pd.concat([curvas, curvas.iloc[:1]])
    else:
        campo, valor = {"nan": ("taxa_rejeicao", np.nan), "probabilidade": ("ic_sup", 1.1),
                        "ic": ("ic_inf", .9), "n": ("n", 0), "teste": ("teste", "outro")}[alteracao]
        curvas.loc[0, campo] = valor
    with pytest.raises(ValueError):
        amostra.resumir_amostra(curvas)


def test_salvar_e_carregar_verifica_hashes_e_dados(tmp_path, simular_falso):
    curvas = amostra.analisar_amostra([30], reps=10, buscar_alvo=False)
    caminhos = amostra.salvar_amostra(curvas, tmp_path)
    carregado = amostra.carregar_amostra(caminhos["curvas"])
    pd.testing.assert_frame_equal(curvas, carregado, check_exact=False)
    metadados = json.loads(caminhos["metadados"].read_text())
    assert metadados["versoes"]["scipy"]
    assert len(metadados["dados_sha256"]) == 64
    caminhos["curvas"].write_text(caminhos["curvas"].read_text().replace("0.5", "0.6"))
    with pytest.raises(ValueError, match="modificado"):
        amostra.carregar_amostra(caminhos["curvas"])


@pytest.mark.parametrize("campo", ["dados_sha256", "cenario_sha256", "metodo_sha256"])
def test_loader_rejeita_proveniencia_obsoleta(tmp_path, simular_falso, campo):
    caminhos = amostra.salvar_amostra(amostra.analisar_amostra([30], reps=10, buscar_alvo=False), tmp_path)
    metadados = json.loads(caminhos["metadados"].read_text())
    metadados[campo] = "hash_antigo"
    caminhos["metadados"].write_text(json.dumps(metadados))
    with pytest.raises(ValueError, match="mud|mudou"):
        amostra.carregar_amostra(caminhos["curvas"])


def test_loader_inspecao_sem_metadata_ainda_valida_probabilidades(curvas, tmp_path):
    caminho = tmp_path / "amostra.csv"
    curvas.to_csv(caminho, index=False)
    assert len(amostra.carregar_amostra(caminho, validar_metadados=False)) == len(curvas)
    curvas.loc[0, "taxa_rejeicao"] = 5
    curvas.to_csv(caminho, index=False)
    with pytest.raises(ValueError, match="probabilidades"):
        amostra.carregar_amostra(caminho, validar_metadados=False)


def test_busca_dobra_n_so_para_testes_que_ainda_nao_atingiram_alvo(dados, monkeypatch):
    chamadas = []
    def simular(**kwargs):
        chamadas.append((kwargs["n"], kwargs["testes"]))
        return pd.DataFrame([
            {"situacao": "base", "efeito": kwargs["efeito"], "n": kwargs["n"], "reps": 100,
             "teste": teste, "alfa": .05, "rejeicoes": 90 if poder >= .8 else 40,
             "taxa_rejeicao": poder, "ic_inf": poder - .05, "ic_sup": poder + .05,
             "hipotese_nula_verdadeira": False, "semente": 42}
            for teste in kwargs["testes"]
            for poder in [.9 if (teste == "mann_whitney" or kwargs["n"] >= 12) else .4]
        ])
    monkeypatch.setattr(motor, "simular", simular)
    curvas = amostra.analisar_amostra([3], efeitos={"piloto": .3}, reps=100,
                                     df=dados, n_max=24)
    assert chamadas == [(3, ("welch", "mann_whitney")), (6, ("welch",)), (12, ("welch",))]
    assert curvas.query("teste == 'mann_whitney'").n.tolist() == [3]
    assert curvas.query("teste == 'welch'").n.tolist() == [3, 6, 12]
    resumo = amostra.resumir_amostra(curvas).set_index("teste")
    assert resumo.loc["welch", "n_grade_80"] == 12
    assert resumo.loc["mann_whitney", "n_grade_80"] == 3
    assert curvas.attrs["metadados"]["parametros"]["grade_n_por_curva"] == {
        "piloto": {"mann_whitney": [3], "welch": [3, 6, 12]}}


def test_busca_para_no_limite_inclusive_sem_extrapolar(dados, simular_falso):
    curvas = amostra.analisar_amostra([3], efeitos={"piloto": .3}, reps=10,
                                     df=dados, n_max=10)
    assert [chamada["n"] for chamada in simular_falso] == [3, 6, 10]
    resumo = amostra.resumir_amostra(curvas)
    assert not resumo.atingiu_alvo.any()
    assert resumo.n_grade_80.isna().all()
    assert resumo.limite_censurado.eq("> 10").all()
