from datetime import date

import pytest

from metricas.frequencia import frequencia_por_semana, semanas_da_janela


def test_semana_com_dias_inicial_e_final_inclusivos():
    assert semanas_da_janela(date(2026, 1, 1), date(2026, 1, 7)) == 1
    assert frequencia_por_semana(3, "2026-01-01", "2026-01-07") == 3


def test_ano_bissexto_e_um_dia():
    assert semanas_da_janela("2024-01-01", "2024-12-31") == 366 / 7
    assert frequencia_por_semana(1, "2026-01-01", "2026-01-01") == 7


def test_zero_observado_e_ausente_sao_distintos():
    assert frequencia_por_semana(0, "2026-01-01", "2026-01-07") == 0
    assert frequencia_por_semana(None, "2026-01-01", "2026-01-07") is None


@pytest.mark.parametrize("quantidade", [-1, 0.5, float("nan"), float("inf"), "2"])
def test_rejeita_quantidade_invalida(quantidade):
    with pytest.raises(ValueError):
        frequencia_por_semana(quantidade, "2026-01-01", "2026-01-07")


def test_rejeita_janela_invertida():
    with pytest.raises(ValueError):
        semanas_da_janela("2026-01-02", "2026-01-01")
