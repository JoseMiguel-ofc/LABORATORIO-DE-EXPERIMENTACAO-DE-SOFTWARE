"""As figuras mantêm as amostras por endpoint, sem inventar dados faltantes."""
import numpy as np
import pandas as pd
import pytest
from PIL import Image

from analise.graficos_s2 import gerar_graficos, resumir_horarios


def dados():
    return pd.DataFrame([
        {"endpoint": "Servico A", "hora_utc": 14, "periodo": "pico",
         "sucesso_operacional": True, "latencia_ms": 10.5, "usuarios_online": 30e6},
        {"endpoint": "Servico A", "hora_utc": 14, "periodo": "pico",
         "sucesso_operacional": True, "latencia_ms": 30.5, "usuarios_online": 31e6},
        {"endpoint": "Servico A", "hora_utc": 1, "periodo": "fora_do_pico",
         "sucesso_operacional": True, "latencia_ms": 5.5, "usuarios_online": np.nan},
        {"endpoint": "Servico A", "hora_utc": 2, "periodo": "fora_do_pico",
         "sucesso_operacional": False, "latencia_ms": 15000, "usuarios_online": 31e6},
        {"endpoint": "Servico B", "hora_utc": 14, "periodo": "pico",
         "sucesso_operacional": True, "latencia_ms": 100.25, "usuarios_online": 30e6},
        {"endpoint": "Servico B", "hora_utc": 15, "periodo": "pico",
         "sucesso_operacional": True, "latencia_ms": np.inf, "usuarios_online": 30e6},
        {"endpoint": "Servico B", "hora_utc": 16, "periodo": "pico",
         "sucesso_operacional": True, "latencia_ms": -5, "usuarios_online": 30e6},
        {"endpoint": "ValveStats", "hora_utc": 14, "periodo": "pico",
         "sucesso_operacional": True, "latencia_ms": 999, "usuarios_online": 30e6},
    ])


def test_resumo_horario_preserva_fracoes_quartis_e_nao_reune_endpoints():
    entrada = dados()
    antes = entrada.copy(deep=True)
    resumo = resumir_horarios(entrada).set_index(["endpoint", "hora_utc"])
    assert set(resumo.index) == {("Servico A", 1), ("Servico A", 14), ("Servico B", 14)}
    assert resumo.loc[("Servico A", 14), "n"] == 2
    assert resumo.loc[("Servico A", 14), "mediana_ms"] == 20.5
    assert resumo.loc[("Servico A", 14), "q25_ms"] == 15.5
    assert resumo.loc[("Servico A", 14), "q75_ms"] == 25.5
    assert resumo.loc[("Servico B", 14), "n"] == 1
    assert resumo.loc[("Servico B", 14), "mediana_ms"] == 100.25
    pd.testing.assert_frame_equal(entrada, antes)


@pytest.mark.parametrize("vazia", [False, True])
def test_gera_pngs_com_paineis_validos_e_servico_sem_amostra(tmp_path, vazia):
    entrada = dados().iloc[:0].copy() if vazia else dados()
    entrada.attrs["endpoints_esperados"] = ["Servico A", "Servico B", "Servico sem medições"]
    caminhos = gerar_graficos(entrada, tmp_path / "figuras")
    assert set(caminhos) == {"latencia_hora", "boxplot_periodo", "dispersao_usuarios"}
    for caminho in caminhos.values():
        with Image.open(caminho) as figura:
            assert figura.format == "PNG"
            assert figura.width >= 1800
            assert figura.height >= 1000
            assert np.asarray(figura.convert("RGB")).std() > 10


def test_todas_falhas_e_usuarios_ausentes_ainda_geram_tres_figuras(tmp_path):
    entrada = dados().query('endpoint != "ValveStats"').copy()
    entrada["sucesso_operacional"] = False
    entrada["usuarios_online"] = np.nan
    assert resumir_horarios(entrada).empty
    caminhos = gerar_graficos(entrada, tmp_path)
    assert all(caminho.stat().st_size > 1000 for caminho in caminhos.values())


@pytest.mark.parametrize("coluna,valor", [("hora_utc", 24), ("hora_utc", .5),
                                         ("periodo", "inventado"),
                                         ("sucesso_operacional", "False")])
def test_rejeita_classificacoes_incompativeis_em_vez_de_rotular_grafico_errado(coluna, valor):
    entrada = dados()
    entrada[coluna] = entrada[coluna].astype(object)
    entrada.loc[0, coluna] = valor
    with pytest.raises(ValueError):
        resumir_horarios(entrada)


def test_rejeita_esquema_nao_preparado():
    with pytest.raises(ValueError, match="dados preparados"):
        gerar_graficos(pd.DataFrame({"latencia_ms": [1]}), "nao_deve_criar")
