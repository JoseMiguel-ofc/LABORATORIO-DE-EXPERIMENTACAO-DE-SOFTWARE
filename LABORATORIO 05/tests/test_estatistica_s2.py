"""Referências analíticas/SciPy e casos não estimáveis da Sprint 2 A."""
import json

import numpy as np
import pytest
from scipy import stats

from analise.estatistica import (ajustar_holm, h1_latencia, h2_usuarios,
                                 h3_falhas, normalidade)


def test_h1_confere_scipy_direcao_e_delta_com_empates():
    pico, fora = [4, 8, 8, 9], [1, 4, 5, 8, 10]
    r = h1_latencia(pico, fora)
    ref = stats.mannwhitneyu(pico, fora, alternative="greater", method="asymptotic",
                            use_continuity=False)
    assert r["estatistica"] == ref.statistic
    assert r["p_valor"] == pytest.approx(ref.pvalue)
    comparacoes = np.sign(np.subtract.outer(pico, fora))
    assert r["efeito"] == pytest.approx(comparacoes.mean())
    assert r["efeito"] > 0
    assert r["diferenca_mediana_ms"] == 3
    assert r["razao_mediana"] == pytest.approx(8 / 5)


def test_h1_grupo_mais_lento_tem_delta_positivo_e_p_menor():
    a, b = [10, 11, 12, 13, 14], [1, 2, 3, 4, 5]
    lento, rapido = h1_latencia(a, b), h1_latencia(b, a)
    assert lento["efeito"] == 1
    assert rapido["efeito"] == -1
    assert lento["p_valor"] < .05 < rapido["p_valor"]


@pytest.mark.parametrize("a,b", [([], [1, 2]), ([1], [2, 3]), ([1, 2], [])])
def test_h1_insuficiente_nao_inventa_teste_ou_efeito(a, b):
    r = h1_latencia(a, b)
    assert r["status"] == "amostra_insuficiente"
    assert r["p_valor"] is None and r["efeito"] is None


def test_h1_constante_nao_forca_pvalor_nan_nem_prova_igualdade():
    r = h1_latencia([2, 2], [2, 2, 2])
    assert r["status"] == "sem_variacao"
    assert r["estatistica"] == 3
    assert r["efeito"] == 0
    assert r["p_valor"] is None
    json.dumps(r, allow_nan=False)


def test_h1_denominador_zero_nao_produz_razao_infinita():
    r = h1_latencia([1, 2], [0, 0])
    assert r["razao_mediana"] is None
    assert r["diferenca_mediana_ms"] == 1.5


def test_h1_medianas_finitas_e_razao_excessiva_sem_overflow():
    r = h1_latencia([1e308, 1e308], [1e-308, 1e-308])
    assert r["mediana_pico_ms"] == 1e308
    assert r["razao_mediana"] is None
    assert r["razao_mediana_motivo"]
    json.dumps(r, allow_nan=False)


def test_h2_confere_scipy_com_empates_e_alerta_amostra_pequena():
    usuarios, latencias = [100, 200, 200, 300, 500], [2, 4, 3, 6, 5]
    r = h2_usuarios(usuarios, latencias)
    ref = stats.spearmanr(usuarios, latencias, alternative="greater")
    assert r["estatistica"] == pytest.approx(ref.statistic)
    assert r["efeito"] == pytest.approx(ref.statistic)
    assert r["p_valor"] == pytest.approx(ref.pvalue)
    assert "500" in r["motivo"]
    assert "assintotica" in r["p_metodo"]


@pytest.mark.parametrize("x,y", [([1, 1, 1], [1, 2, 3]), ([1, 2, 3], [2, 2, 2])])
def test_h2_variavel_constante_e_indefinida(x, y):
    r = h2_usuarios(x, y)
    assert r["status"] == "sem_variacao"
    assert r["efeito"] is r["p_valor"] is None


def test_h2_insuficiente_e_pares_inconsistentes():
    assert h2_usuarios([1, 2], [1, 3])["p_valor"] is None
    with pytest.raises(ValueError, match="pares"):
        h2_usuarios([1, 2], [1])


def test_h2_associacao_inversa_preserva_direcao_unilateral():
    r = h2_usuarios([1, 2, 3, 4], [5, 4, 3, 2])
    assert r["efeito"] == -1
    assert r["p_valor"] == 1


def test_h3_tabela_e_or_fisher_exato_sem_trocar_direcao():
    r = h3_falhas(6, 4, 2, 18)
    ref = stats.fisher_exact([[6, 4], [2, 18]], alternative="greater")
    assert r["tabela_2x2"] == [[6, 4], [2, 18]]
    assert r["efeito"] == r["estatistica"] == pytest.approx(13.5)
    assert r["p_valor"] == pytest.approx(ref.pvalue)
    assert r["diferenca_taxas_falha"] == pytest.approx(.5)
    assert r["n1"] == 10 and r["n2"] == 20
    assert r["p_valor"] < .05


def test_h3_ausencia_de_janela_nao_e_ausencia_de_efeito():
    r = h3_falhas(0, 0, 2, 10)
    assert r["status"] == "amostra_insuficiente"
    assert r["p_valor"] is r["efeito"] is None
    assert r["taxa_falha_janela"] is None


@pytest.mark.parametrize("tabela,status", [((0, 10, 0, 20), "sem_falhas"),
                                          ((10, 0, 20, 0), "sem_sucessos")])
def test_h3_sem_contraste_mostra_p_um_e_or_indefinida(tabela, status):
    r = h3_falhas(*tabela)
    assert r["status"] == status
    assert r["p_valor"] == 1
    assert r["efeito"] is r["estatistica"] is None
    json.dumps(r, allow_nan=False)


def test_h3_celula_zero_or_infinita_sem_pseudocontagem():
    r = h3_falhas(3, 7, 0, 20)
    assert r["efeito"] is r["estatistica"] is None
    assert r["efeito_limite"] == "infinito"
    assert r["p_valor"] == pytest.approx(stats.fisher_exact([[3, 7], [0, 20]], alternative="greater").pvalue)
    json.dumps(r, allow_nan=False)


@pytest.mark.parametrize("valor", [-1, 1.5, True, np.nan, "1"])
def test_h3_contagens_invalidas_rejeitadas(valor):
    with pytest.raises(ValueError, match="contagem"):
        h3_falhas(valor, 2, 1, 3)


def test_normalidade_scipy_e_tamanho_real_da_amostra():
    x = [1.5, 2, 3.1, 3.2, 4.6, 5.2, 8]
    r = normalidade(x)
    ref = stats.shapiro(x)
    assert r["estatistica"] == pytest.approx(ref.statistic)
    assert r["p_valor"] == pytest.approx(ref.pvalue)
    assert r["n1"] == len(x)


def test_normalidade_amostra_pequena_e_constante_nao_concluem_normalidade():
    assert normalidade([1, 2])["status"] == "amostra_insuficiente"
    r = normalidade([1, 1, 1])
    assert r["status"] == "sem_variacao"
    assert r["p_valor"] is None


def test_normalidade_n_grande_nao_subamostra_para_obter_valor_p():
    x = np.random.default_rng(42).lognormal(size=5001)
    r = normalidade(x)
    assert r["status"] == "n_acima_limite_p"
    assert r["n1"] == 5001
    assert 0 < r["estatistica"] <= 1
    assert r["p_valor"] is None


def test_normalidade_invariante_a_escala_sem_overflow():
    pequeno = normalidade([0, .5, 1])
    grande = normalidade([0, 5e307, 1e308])
    assert grande["estatistica"] == pytest.approx(pequeno["estatistica"])
    assert grande["p_valor"] == pytest.approx(pequeno["p_valor"])
    json.dumps(grande, allow_nan=False)


@pytest.mark.parametrize("funcao,args", [
    (h1_latencia, ([1, np.nan], [2, 3])), (h1_latencia, ([1, -1], [2, 3])),
    (h2_usuarios, ([1, 2, 3], [1, 2, np.inf])), (normalidade, ([[1, 2, 3]],)),
    (normalidade, ([1, -1, 3],)),
])
def test_amostras_invalidas_nao_sao_descartadas_silenciosamente(funcao, args):
    with pytest.raises(ValueError, match="vetor|números"):
        funcao(*args)


def test_holm_referencia_conhecida_ordem_e_monotonicidade():
    assert ajustar_holm([.04, .01, .03]) == pytest.approx([.06, .03, .06])
    assert ajustar_holm([0, .5, 1]) == [0, 1, 1]
    assert ajustar_holm([]) == []


def test_holm_hipotese_ausente_permanece_na_familia_planejada():
    r = ajustar_holm([.01, .04, None])
    assert r[:2] == pytest.approx([.03, .08])
    assert r[2] is None
    assert ajustar_holm([None, np.nan]) == [None, None]


@pytest.mark.parametrize("valor", [-.1, 1.01, np.inf, True, ".1"])
def test_holm_pvalores_invalidos_rejeitados(valor):
    with pytest.raises(ValueError, match="Valores-p"):
        ajustar_holm([.1, valor])


def test_resultados_puros_sao_serializaveis_sem_nan_nem_infinito():
    casos = [h1_latencia([1, 2], [3, 4]), h2_usuarios([1, 2, 3], [3, 1, 2]),
             h3_falhas(0, 0, 0, 0), h3_falhas(1, 0, 0, 1), normalidade([1, 2, 3])]
    json.dumps(casos, allow_nan=False)
