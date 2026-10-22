import math

import pandas as pd
import pytest

from analises import rq01_04


def test_resumir_mediana_e_iqr_calculados_a_mao():
    # 1, 2, 3, 4, 100 -> mediana 3; Q1 = 2; Q3 = 4 (método linear); IQR = 2.
    # O valor extremo (100) não desloca a mediana, que é o motivo de usá-la.
    resumo = rq01_04.resumir(pd.Series([1, 2, 3, 4, 100]))
    assert (resumo["mediana"], resumo["q1"], resumo["q3"], resumo["iqr"]) == (3, 2, 4, 2)
    assert (resumo["minimo"], resumo["maximo"], resumo["n"], resumo["ausentes"]) == (1, 100, 5, 0)


def test_resumir_ignora_ausentes_sem_virar_zero():
    resumo = rq01_04.resumir(pd.Series([None, 10, 20, math.nan]))
    assert resumo["n"] == 2 and resumo["ausentes"] == 2
    assert resumo["mediana"] == 15 and resumo["minimo"] == 10


def test_resumir_serie_sem_valores():
    resumo = rq01_04.resumir(pd.Series([None, None], dtype=object))
    assert resumo["n"] == 0 and resumo["ausentes"] == 2 and resumo["mediana"] is None


def dados_ficticios():
    """Quatro repositórios com todas as colunas que a análise lê."""
    return pd.DataFrame({
        "frequencia_releases_semana": [0.1, 0.5, 2, 10],
        "lead_time_a_horas": [12, 100, 500, 1000],
        "lead_time_b_horas": [6, 50, 400, 900],
        "cfr_a": [0, 0.1, 0.2, 0.5],
        "cfr_b": [0, 0.2, None, 0.6],
        "recuperacao_mediana_horas": [0.5, 2, None, 200],
        "episodios_resolvidos": [3, 5, 0, 2],
        "episodios_censurados": [0, 1, 0, 2],
        "proporcao_episodios_censurados": [0, 1 / 6, None, 0.5],
        "cfr_b_censuradas": [1, 0, 2, 0],
        "categoria_frequencia": ["Low", "Medium", "High", "Elite"],
        "categoria_lead_time": ["Elite", "High", "Medium", "Low"],
        "categoria_cfr": ["Elite", "Elite", "High", "Low"],
        "categoria_recuperacao": ["Elite", "High", None, "Low"],
        "categoria_geral": ["Elite", "High", "High", "Low"],
    })


def test_tabela_descritiva_tem_as_seis_metricas_das_rqs():
    tabela = rq01_04.tabela_descritiva(dados_ficticios())
    assert tabela["rq"].tolist() == ["RQ 01", "RQ 02", "RQ 02", "RQ 03", "RQ 03", "RQ 04"]
    cfr_b = tabela.set_index("coluna").loc["cfr_b"]
    assert cfr_b["n"] == 3 and cfr_b["ausentes"] == 1


def test_distribuicao_de_categorias_soma_100_por_metrica():
    categorias = rq01_04.distribuicao_categorias(dados_ficticios())
    for _, grupo in categorias.groupby("metrica"):
        assert grupo["repositorios"].sum() == 4
        assert grupo["percentual"].sum() == pytest.approx(100)
    recuperacao = categorias[categorias.coluna == "categoria_recuperacao"].set_index("categoria")
    assert recuperacao.loc["Sem dado", "repositorios"] == 1
    geral = categorias[categorias.coluna == "categoria_geral"].set_index("categoria")
    assert geral.loc["High", "repositorios"] == 2 and geral.loc["Medium", "repositorios"] == 0
    assert categorias.categoria.tolist()[:5] == ["Elite", "High", "Medium", "Low", "Sem dado"]


def test_categoria_desconhecida_e_rejeitada():
    dados = dados_ficticios()
    dados.loc[0, "categoria_cfr"] = "Excelente"
    with pytest.raises(ValueError, match="Excelente"):
        rq01_04.distribuicao_categorias(dados)


def test_tabela_censura():
    censura = rq01_04.tabela_censura(dados_ficticios()).set_index("item")["valor"]
    assert censura["Episódios de falha resolvidos (RQ 04)"] == 10
    assert censura["Episódios de falha censurados (RQ 04)"] == 3
    assert censura["Repositórios com ao menos 1 episódio censurado"] == 2
    assert censura["Repositórios sem episódio resolvido (sem tempo de recuperação)"] == 1
    assert censura["Releases censuradas no CFR (b) (últimos 7 dias da janela)"] == 3


@pytest.mark.parametrize("valor, coluna, esperado", [
    (312, "lead_time_a_horas", "13,0 dias"),          # exemplo da RQ 02: 13 dias
    (1 + 20 / 60, "recuperacao_mediana_horas", "1,3 h"),  # exemplo da RQ 04: 1h20
    (0.155, "cfr_a", "15,5%"),
    (0.316, "frequencia_releases_semana", "0,32/semana"),
    (None, "cfr_b", "—"),
])
def test_formatar(valor, coluna, esperado):
    assert rq01_04.formatar(valor, coluna) == esperado


def test_main_gera_tabelas_e_figuras(tmp_path, capsys):
    entrada = tmp_path / "metricas.csv"
    dados_ficticios().to_csv(entrada, index=False)
    rq01_04.main(["--entrada", str(entrada), "--saida", str(tmp_path / "saida")])
    saida = tmp_path / "saida"
    for arquivo in ["rq01_04_descritiva.csv", "rq01_04_categorias_c1.csv",
                    "rq01_04_censura.csv", "rq01_04_resumo.md",
                    "figuras/rq01_04_histogramas.png", "figuras/rq01_04_boxplots.png",
                    "figuras/rq01_04_categorias_c1.png"]:
        assert (saida / arquivo).stat().st_size > 0, arquivo
    resumo = (saida / "rq01_04_resumo.md").read_text(encoding="utf-8")
    assert "| RQ 01 | Frequência de deploy | 4 |" in resumo
    assert "4 repositórios analisados" in capsys.readouterr().out
