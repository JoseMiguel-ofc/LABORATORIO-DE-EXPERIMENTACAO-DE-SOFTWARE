"""Tabela e texto da seção 6 nos dados reais."""

import copy

import numpy as np
import pytest

from src.aplicacao_real import (aplicar_dados_reais, grupos, magnitude, tabela_secao6,
                                texto_secao6)
from src.dados import carregar


@pytest.mark.parametrize(("teste", "valor", "esperado"), [
    ("welch", 0.05, "desprezível"), ("welch", -0.2, "pequeno"),
    ("welch", 0.79, "médio"), ("welch", 0.8, "grande"),
    ("mann_whitney", 0.146, "desprezível"), ("mann_whitney", 0.271, "pequeno"),
    ("mann_whitney", -0.4, "médio"), ("mann_whitney", 0.474, "grande"),
])
def test_magnitude_usa_faixas_convencionais(teste, valor, esperado):
    assert magnitude(teste, valor) == esperado


def test_diferencas_em_horas_e_fracao_de_pares():
    resultado = aplicar_dados_reais(np.array([2.0, 4.0, 9.0]), np.array([1.0, 3.0, 5.0]))
    assert resultado["diferenca_medias"] == pytest.approx(5.0 - 3.0)
    assert resultado["diferenca_medianas"] == pytest.approx(4.0 - 3.0)
    # Pares em que com bot > sem bot: 2>1, 4>1, 4>3, 9>1, 9>3, 9>5.
    assert resultado["p_com_maior"] == pytest.approx(6 / 9)


@pytest.fixture(scope="module")
def real():
    return aplicar_dados_reais(*grupos(carregar()))


def test_tabela_tem_os_campos_da_secao6(real):
    tabela = tabela_secao6(real)
    for coluna in ("Estatística", "p-valor", "Tamanho do efeito", "Conclusão"):
        assert tabela[coluna].notna().all()
    assert list(tabela["Medida do efeito"]) == ["g de Hedges", "δ de Cliff"]
    # Valores registrados no README a partir dos dados coletados.
    assert tabela["p-valor"].tolist() == pytest.approx([0.844723, 0.071278], abs=1e-6)
    assert tabela["Tamanho do efeito"].tolist() == pytest.approx([0.050139, 0.271111],
                                                                 abs=1e-6)
    assert list(tabela["Magnitude"]) == ["desprezível", "pequeno"]


def test_decisao_acompanha_alfa(real):
    com, sem = grupos(carregar())
    a10 = tabela_secao6(aplicar_dados_reais(com, sem, alfa=0.10))
    assert list(a10["Decisão (α = 10%)"]) == ["Não rejeitar H₀", "Rejeitar H₀"]
    assert "os testes discordam: só o Mann–Whitney U rejeita" in texto_secao6(
        aplicar_dados_reais(com, sem, alfa=0.10))


def test_texto_tem_concordancia_magnitude_e_horas(real):
    texto = texto_secao6(real)
    assert "nenhum dos dois testes rejeita H₀ nos 60 PRs" in texto
    assert "desprezível pelo g de Hedges" in texto and "pequeno pelo δ de Cliff" in texto
    assert "mediana +14.0 h" in texto and "média +10.1 h" in texto
    assert 2 <= texto.count(". ") + 1 <= 4


def test_texto_quando_os_dois_rejeitam(real):
    resultado = copy.deepcopy(real)
    for r in resultado["testes"].values():
        r["rejeita_h0"] = True
    assert "os dois testes rejeitam H₀" in texto_secao6(resultado)
