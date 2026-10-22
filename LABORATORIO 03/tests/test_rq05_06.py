import numpy as np
import pandas as pd
import pytest
from scipy.stats import kruskal

from analises import rq05, rq06


# ---------------------------------------------------------------- tamanhos de efeito (à mão)

@pytest.mark.parametrize("x, y, esperado", [
    ([1, 2, 3], [4, 5, 6], -1),            # todo x < todo y
    ([4, 5, 6], [1, 2, 3], 1),             # todo x > todo y
    ([1, 2, 3], [1, 2, 3], 0),             # distribuições iguais
    # x = 2, 4, 6 e y = 1, 3: pares com x > y = 5 (2>1, 4>1, 4>3, 6>1, 6>3); x < y = 1 (2<3)
    # δ = (5 − 1) / (3 · 2) = 4/6
    ([2, 4, 6], [1, 3], 4 / 6),
    # x = 1, 3, 5 e y = 2, 4: x > y = 3 e x < y = 3  ->  δ = 0
    ([1, 3, 5], [2, 4], 0),
    # x = 1, 2 e y = 2: x > y = 0; x < y = 1 (1<2); o empate (2=2) não conta
    # δ = (0 − 1) / (2 · 1) = −0,5
    ([1, 2], [2], -0.5),
])
def test_cliffs_delta_calculado_a_mao(x, y, esperado):
    assert rq06.cliffs_delta(x, y) == pytest.approx(esperado)


def test_epsilon_quadrado_calculado_a_mao():
    # Três grupos sem sobreposição: postos somam 6, 15 e 24 (N = 9).
    # H = 12 / (9 · 10) · (6²/3 + 15²/3 + 24²/3) − 3 · 10 = 37,2 − 30 = 7,2
    # ε² = H / (n − 1) = 7,2 / 8 = 0,9
    h, _ = kruskal([1, 2, 3], [4, 5, 6], [7, 8, 9])
    assert h == pytest.approx(7.2)
    assert rq06.epsilon_quadrado(h, 9) == pytest.approx(0.9)


@pytest.mark.parametrize("valor, esperado", [
    (0.0, "desprezível"), (0.0099, "desprezível"), (0.01, "pequeno"), (0.059, "pequeno"),
    (0.06, "médio"), (0.139, "médio"), (0.14, "grande"), (0.9, "grande"),
])
def test_interpretar_epsilon(valor, esperado):
    assert rq06.interpretar_epsilon(valor) == esperado


@pytest.mark.parametrize("valor, esperado", [
    (0.1, "desprezível"), (-0.146, "desprezível"), (0.147, "pequeno"), (-0.32, "pequeno"),
    (0.33, "médio"), (-0.47, "médio"), (0.474, "grande"), (-1, "grande"),
])
def test_interpretar_delta_romano(valor, esperado):
    assert rq06.interpretar_delta(valor) == esperado


# ---------------------------------------------------------------- RQ 05

@pytest.mark.parametrize("rho, esperado", [
    (0.05, "desprezível"), (0.2, "fraca positiva"), (-0.4, "moderada negativa"),
    (0.8, "forte positiva"),
])
def test_interpretar_rho(rho, esperado):
    assert rq05.interpretar_rho(rho) == esperado


def test_correlacao_monotonica_perfeita_e_ausentes():
    dados = pd.DataFrame({"x": [1, 2, 3, 4, None], "y": [10, 20, 30, 1000, 5]})
    resultado = rq05.correlacionar(dados, "x", "y")
    assert resultado["rho"] == pytest.approx(1) and resultado["n"] == 4


def test_correlacao_com_poucos_dados():
    dados = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    assert rq05.correlacionar(dados, "x", "y")["rho"] is None


# ---------------------------------------------------------------- RQ 06

def dados_ficticios(n=40, semente=1):
    gerador = np.random.default_rng(semente)
    idade = np.arange(n, dtype=float)
    return pd.DataFrame({
        "estrelas": gerador.integers(1000, 50000, n),
        "contribuidores": gerador.integers(1, 500, n),
        "idade_anos": idade,
        "linguagem": ["Python"] * 20 + ["Go"] * 16 + ["Haskell"] * 3 + [None],
        # lead time cresce com a idade: o teste da idade deve dar efeito grande
        "lead_time_a_horas": idade * 10 + gerador.random(n),
        "frequencia_releases_semana": gerador.random(n) + 0.1,
        "cfr_a": gerador.random(n),
        "recuperacao_mediana_horas": [None] * 4 + list(gerador.random(n - 4) * 10),
    })


def test_agrupar_em_quartis_e_linguagens_frequentes():
    dados = dados_ficticios()
    quartis = rq06.agrupar(dados, "idade_anos")
    assert quartis.value_counts().to_dict() == {"Q1": 10, "Q2": 10, "Q3": 10, "Q4": 10}
    linguagens = rq06.agrupar(dados, "linguagem")
    assert set(linguagens) == {"Python", "Go", "Outras"}           # Haskell (3) e vazio viram Outras
    assert (linguagens == "Outras").sum() == 4


def test_analisar_aplica_holm_e_detecta_efeito_conhecido():
    testes, medianas = rq06.analisar(dados_ficticios())
    assert len(testes) == len(rq06.FATORES) * len(rq06.METRICAS) == 16
    assert (testes["p_holm"] >= testes["p_valor"] - 1e-12).all()   # Holm nunca reduz p
    idade_lt = testes[(testes.fator == "Idade") & (testes.metrica == "Lead time (a)")].iloc[0]
    assert idade_lt["significativo_holm"] and idade_lt["interpretacao_efeito"] == "grande"
    assert idade_lt["delta_q4_q1"] == pytest.approx(1)              # Q4 sempre maior que Q1
    recuperacao = testes[testes.metrica == "Recuperação"]
    assert (recuperacao["n"] == 36).all()                            # ausentes ficam de fora
    assert pd.isna(testes[testes.fator == "Linguagem"]["delta_q4_q1"]).all()
    assert set(medianas.columns) == {"fator", "metrica", "grupo", "mediana"}


def test_fator_com_dois_grupos_usa_mann_whitney(monkeypatch):
    dados = dados_ficticios()
    dados["linguagem"] = ["Python"] * 20 + ["Go"] * 20
    linha, _ = rq06.testar(dados, "linguagem", "lead_time_a_horas")
    assert linha["teste"] == "Mann-Whitney" and linha["efeito"] == "Cliff's delta"
    assert -1 <= linha["tamanho_efeito"] <= 1


def test_mains_geram_tabelas_e_figuras(tmp_path):
    entrada = tmp_path / "metricas.csv"
    dados = dados_ficticios()
    dados["cfr_b"] = np.linspace(0, 0.5, len(dados))
    dados.to_csv(entrada, index=False)
    rq05.main(["--entrada", str(entrada), "--saida", str(tmp_path)])
    rq06.main(["--entrada", str(entrada), "--saida", str(tmp_path)])
    for arquivo in ["rq05_spearman.csv", "figuras/rq05_dispersao.png", "rq06_testes.csv",
                    "rq06_medianas.csv", "figuras/rq06_efeitos.png"]:
        assert (tmp_path / arquivo).stat().st_size > 0, arquivo
    assert len(pd.read_csv(tmp_path / "rq05_spearman.csv")) == 2
