"""Gráficos preservam as probabilidades e o significado das hipóteses."""

import json

import numpy as np
import pandas as pd
import pytest

from src.estilo import CORES_GRUPO, CORES_TESTE
from src.graficos import g1, g2, g3, g4, grafico_amostra
from src.testes import aplicar_testes


@pytest.fixture
def resultados():
    linhas = []
    for situacao in ("base", "assimetria_forte", "outliers", "n_pequeno", "variancias_diferentes"):
        for teste, contagens in (("welch", [40, 120, 250]), ("mann_whitney", [50, 190, 380])):
            for efeito, rejeicoes in zip([0.0, 0.3, 0.6], contagens):
                taxa = rejeicoes / 1000
                # Intervalo Wilson 95%, com z arredondado apenas para a fixture.
                z = 1.959963984540054
                denominador = 1 + z ** 2 / 1000
                centro = (taxa + z ** 2 / 2000) / denominador
                margem = z * np.sqrt(taxa * (1 - taxa) / 1000 + z ** 2 / 4_000_000) / denominador
                linhas.append({
                    "situacao": situacao, "teste": teste, "efeito": efeito,
                    "n": 10 if situacao == "n_pequeno" else 30,
                    "reps": 1000, "rejeicoes": rejeicoes, "taxa_rejeicao": taxa,
                    "ic_inf": centro - margem, "ic_sup": centro + margem,
                    "alfa": 0.05, "semente": 42,
                    "hipotese_nula_verdadeira": efeito == 0 and situacao != "variancias_diferentes",
                })
    return pd.DataFrame(linhas)


def test_g3_exclui_efeito_zero_com_hipoteses_diferentes(resultados):
    figura = g3(resultados)
    assert len(figura.data) == 2
    assert figura.layout.meta["situacoes_excluidas"] == ["variancias_diferentes"]
    assert len(figura.layout.shapes) == 1
    assert figura.layout.shapes[0].y0 == figura.layout.shapes[0].y1 == 5
    for barra in figura.data:
        assert barra.meta["tipo"] == "erro_tipo_i"
        assert barra.meta["situacoes"] == ["base", "assimetria_forte", "outliers", "n_pequeno"]
        assert not any("Variâncias diferentes" in categoria for categoria in barra.x)
        assert barra.marker.color == CORES_TESTE[barra.meta["teste"]]
        assert np.asarray(barra.y) == pytest.approx([4] * 4 if barra.meta["teste"] == "welch" else [5] * 4)
    assert "Erro tipo I" in figura.layout.yaxis.title.text


def test_g3_so_hipotese_falsa_nao_pode_ser_chamada_erro_tipo_i(resultados):
    with pytest.raises(ValueError, match="hipótese nula verdadeira"):
        g3(resultados.loc[resultados["situacao"] == "variancias_diferentes"])


def test_g4_converte_efeito_taxa_e_ic_em_percentuais_sem_mudar_pontos(resultados):
    figura = g4(resultados.sample(frac=1, random_state=2))
    assert len(figura.data) == 10
    for curva in figura.data:
        assert curva.x == pytest.approx([0, 30, 60])
        teste, situacao = curva.meta["teste"], curva.meta["situacao"]
        original = resultados.loc[(resultados["teste"] == teste)
                                  & (resultados["situacao"] == situacao)].sort_values("efeito")
        assert curva.y == pytest.approx(100 * original["taxa_rejeicao"])
        assert curva.line.color == CORES_TESTE[teste]
        assert curva.error_y.array == pytest.approx(100 * (original["ic_sup"] - original["taxa_rejeicao"]))
        assert curva.error_y.arrayminus == pytest.approx(100 * (original["taxa_rejeicao"] - original["ic_inf"]))
        assert np.asarray(curva.customdata)[:, 0] == pytest.approx(100 * original["ic_inf"])
        assert np.asarray(curva.customdata)[:, 1] == pytest.approx(100 * original["ic_sup"])
    assert sum(curva.showlegend for curva in figura.data) == 2
    assert any("hipóteses distintas" in anotacao.text for anotacao in figura.layout.annotations)
    assert "Rejeições de H₀ (%)" == figura.layout.yaxis.title.text
    json.loads(figura.to_json())


@pytest.fixture
def amostra(resultados):
    pontos = resultados.loc[(resultados["situacao"] == "base") & (resultados["efeito"] != 0)].copy()
    pontos["referencia_efeito"] = pontos["efeito"].map({0.3: "planejado_30pct", 0.6: "observado_mediana"})
    pontos["rotulo_efeito"] = pontos["efeito"].map({0.3: "Efeito planejado: +30%", 0.6: "Efeito observado: razão de medianas"})
    pontos["n_real_por_grupo"] = 30
    pontos["alvo_poder"] = 0.8
    maior = pontos.copy()
    maior["n"] = 100
    return pd.concat([maior, pontos], ignore_index=True)


def test_amostra_faceta_por_origem_efeito_e_nao_extrapola_n(amostra):
    figura = grafico_amostra(amostra)
    assert len(figura.data) == 4
    for curva in figura.data:
        assert curva.x == pytest.approx([30, 100])
        assert curva.line.color == CORES_TESTE[curva.meta["teste"]]
        assert curva.meta["referencia_efeito"] in ["planejado_30pct", "observado_mediana"]
    assert sum(s.y0 == s.y1 == 80 for s in figura.layout.shapes) == 2
    assert sum(s.x0 == s.x1 == 30 for s in figura.layout.shapes) == 2
    marcacoes = [a for a in figura.layout.annotations if a.text.startswith("Amostra real:")]
    assert len(marcacoes) == 2
    assert all(a.x == pytest.approx(np.log10(30)) for a in marcacoes)
    assert figura.layout.xaxis.title.text == "Amostra por grupo (PRs; escala logarítmica)"
    assert figura.layout.xaxis.type == "log"
    assert figura.layout.yaxis.title.text == "Poder estimado (%)"
    assert figura.layout.meta["alvo_poder"] == 0.8
    json.loads(figura.to_json())


def test_estilo_comum_e_cores_constantes_entre_g1_g2_g3_g4_amostra(resultados, amostra):
    grupos = {"com_bot": np.array([1, 2, 4, 8]), "sem_bot": np.array([2, 4, 8, 16])}
    figuras = [g1(grupos, grupos), g2(aplicar_testes(*grupos.values())),
               g3(resultados), g4(resultados), grafico_amostra(amostra)]
    for figura in figuras:
        assert figura.layout.paper_bgcolor == "white"
        assert figura.layout.plot_bgcolor == "white"
        assert figura.layout.font.family == "Arial, sans-serif"
        assert figura.layout.legend.orientation == "h"
    for barra in figuras[0].data:
        assert barra.marker.color == CORES_GRUPO[barra.legendgroup]


@pytest.mark.parametrize("grafico", [g3, g4])
def test_recusa_pontos_duplicados_em_vez_de_conectar_execucoes_distintas(resultados, grafico):
    duplicados = pd.concat([resultados, resultados.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicados"):
        grafico(duplicados)


def test_g4_recusa_mistura_de_n_na_mesma_curva(resultados):
    resultados.loc[1, "n"] = 100
    with pytest.raises(ValueError, match="único n"):
        g4(resultados)


def test_graficos_aceitam_semente_desconhecida_sem_inventar_42(resultados):
    resultados["semente"] = None
    for figura in (g3(resultados), g4(resultados)):
        for curva in figura.data:
            assert all(valor == "não informada" for valor in np.asarray(curva.customdata)[:, 5])
            assert np.asarray(curva.customdata)[0, 0] >= 0
        json.loads(figura.to_json())


def test_amostra_aceita_grade_estendida_apenas_para_um_teste(amostra):
    ponto = amostra.loc[(amostra["teste"] == "welch") & (amostra["n"] == 100)].copy()
    ponto["n"] = 64_000
    figura = grafico_amostra(pd.concat([amostra, ponto], ignore_index=True))
    for curva in figura.data:
        esperado = [30, 100, 64_000] if curva.meta["teste"] == "welch" else [30, 100]
        assert curva.x == pytest.approx(esperado)


def test_amostra_recusa_mudar_efeito_dentro_da_curva(amostra):
    amostra.loc[0, "efeito"] = 0.4
    with pytest.raises(ValueError, match="mesmo efeito"):
        grafico_amostra(amostra)


def test_amostra_nao_chama_erro_tipo_i_de_poder(amostra):
    amostra.loc[0, "hipotese_nula_verdadeira"] = True
    with pytest.raises(ValueError, match="sob H₁"):
        grafico_amostra(amostra)


@pytest.mark.parametrize("coluna,valor,mensagem", [
    ("taxa_rejeicao", 40, "taxa_rejeicao"),
    ("ic_inf", -0.1, "intervalo de confiança"),
    ("ic_sup", 0.001, "intervalo de confiança"),
    ("n", np.inf, "finitos"),
    ("teste", "teste inexistente", "Teste desconhecido"),
    ("alfa", 0.1, "único alfa"),
])
def test_erros_de_entrada_nao_viram_graficos_enganosos(resultados, coluna, valor, mensagem):
    resultados[coluna] = resultados[coluna].astype(object)
    resultados.loc[0, coluna] = valor
    with pytest.raises(ValueError, match=mensagem):
        g4(resultados)
