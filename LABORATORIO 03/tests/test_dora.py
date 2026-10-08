import math

import pytest

from metricas.dora import (ELITE, HIGH, LOW, MEDIUM, UM_POR_MES_EM_SEMANAS, classificar_cfr,
                           classificar_frequencia, classificar_geral, classificar_lead_time,
                           classificar_recuperacao, classificar_repositorio)


DIA = 24
SEMANA = 7 * DIA


@pytest.mark.parametrize("deploys_por_semana, esperado", [
    (20, ELITE),
    (7, ELITE),                              # limite inferior de Elite
    (6.99, HIGH),
    (1, HIGH),                               # limite inferior de High
    (0.99, MEDIUM),
    (UM_POR_MES_EM_SEMANAS, MEDIUM),         # exatamente 1 por mês
    (UM_POR_MES_EM_SEMANAS - 0.001, LOW),
    (0, LOW),
])
def test_frequencia(deploys_por_semana, esperado):
    assert classificar_frequencia(deploys_por_semana) == esperado


def test_um_por_mes_vale_cerca_de_0_23_por_semana():
    assert UM_POR_MES_EM_SEMANAS == pytest.approx(0.2301, abs=1e-4)


@pytest.mark.parametrize("horas, esperado", [
    (0, ELITE),
    (DIA - 0.01, ELITE),
    (DIA, HIGH),                 # 1 dia já é High
    (SEMANA - 0.01, HIGH),
    (SEMANA, MEDIUM),            # 1 semana já é Medium
    (30 * DIA - 0.01, MEDIUM),
    (30 * DIA, LOW),             # 30 dias já é Low
    (13 * DIA, MEDIUM),          # exemplo da RQ 02: 13 dias
])
def test_lead_time(horas, esperado):
    assert classificar_lead_time(horas) == esperado


@pytest.mark.parametrize("taxa, esperado", [
    (0, ELITE),
    (0.15, ELITE),               # ≤ 15% ainda é Elite
    (0.1501, HIGH),
    (0.30, HIGH),
    (3 / 10, HIGH),              # taxa calculada por divisão bate com o corte
    (0.3001, MEDIUM),
    (0.45, MEDIUM),
    (9 / 20, MEDIUM),
    (0.4501, LOW),
    (1, LOW),
])
def test_cfr(taxa, esperado):
    assert classificar_cfr(taxa) == esperado


@pytest.mark.parametrize("taxa", [-0.1, 15, 1.01])
def test_cfr_fora_de_0_a_1_e_rejeitado(taxa):
    with pytest.raises(ValueError):
        classificar_cfr(taxa)


@pytest.mark.parametrize("horas, esperado", [
    (0.5, ELITE),
    (1, HIGH),                   # 1 hora já é High
    (1 + 20 / 60, HIGH),         # exemplo da RQ 04: 1h20
    (DIA - 0.01, HIGH),
    (DIA, MEDIUM),
    (SEMANA - 0.01, MEDIUM),
    (SEMANA, LOW),
])
def test_recuperacao(horas, esperado):
    assert classificar_recuperacao(horas) == esperado


@pytest.mark.parametrize("funcao", [classificar_frequencia, classificar_lead_time,
                                    classificar_recuperacao])
def test_valores_negativos_sao_rejeitados(funcao):
    with pytest.raises(ValueError):
        funcao(-1)


@pytest.mark.parametrize("funcao", [classificar_frequencia, classificar_lead_time,
                                    classificar_cfr, classificar_recuperacao])
@pytest.mark.parametrize("ausente", [None, math.nan])
def test_metrica_ausente_nao_tem_categoria(funcao, ausente):
    assert funcao(ausente) is None


def test_geral_exemplo_do_enunciado():
    # (4, 3, 3, 1) → mediana 3 → High
    assert classificar_geral([ELITE, HIGH, HIGH, LOW]) == HIGH


@pytest.mark.parametrize("categorias, esperado", [
    ([ELITE, ELITE, ELITE, ELITE], ELITE),
    ([LOW, LOW, LOW, LOW], LOW),
    ([ELITE, HIGH, MEDIUM, LOW], MEDIUM),   # mediana 2,5 → arredonda para baixo
    ([ELITE, ELITE, HIGH, LOW], HIGH),      # mediana 3,5 → 3
    ([ELITE, MEDIUM, LOW, LOW], LOW),       # mediana 1,5 → 1
    ([HIGH, None, HIGH, ELITE], HIGH),      # métrica ausente é ignorada
])
def test_geral_mediana_arredondada_para_baixo(categorias, esperado):
    assert classificar_geral(categorias) == esperado


def test_geral_sem_metricas():
    assert classificar_geral([None, None]) is None


def test_classificar_repositorio_completo():
    resultado = classificar_repositorio(
        deploys_por_semana=10, lead_time_horas=2 * DIA, cfr=0.2, recuperacao_horas=200)
    assert resultado == {"frequencia": ELITE, "lead_time": HIGH, "cfr": HIGH,
                         "recuperacao": LOW, "geral": HIGH}


def test_classificar_repositorio_sem_episodios_de_falha():
    resultado = classificar_repositorio(0.1, 40 * DIA, 0.5, None)
    assert resultado["recuperacao"] is None
    assert resultado["geral"] == LOW
