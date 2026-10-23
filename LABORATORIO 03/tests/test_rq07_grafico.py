import pandas as pd
import pytest

from analises import rq07_grafico


def classificacoes():
    linhas = [("a", "C1", "Elite"), ("b", "C1", "High"), ("c", "C1", "High"), ("d", "C1", None),
              ("a", "C2", "Medium"), ("b", "C2", "Medium"), ("c", "C2", "Low"), ("d", "C2", None),
              ("a", "C3", "Elite"), ("b", "C3", "Elite"), ("c", "C3", "High"), ("d", "C3", None)]
    return pd.DataFrame(linhas, columns=["full_name", "cenario", "categoria_geral"])


def test_distribuicao_ignora_incompletos_e_soma_100():
    percentuais, totais = rq07_grafico.distribuicao_por_cenario(classificacoes())
    assert totais.to_dict() == {"C1": 3, "C2": 3, "C3": 3}          # "d" sem categoria fica fora
    assert percentuais.sum(axis=1).tolist() == pytest.approx([100, 100, 100])
    assert percentuais.loc["C1", "High"] == pytest.approx(200 / 3)
    assert percentuais.loc["C2", "Elite"] == 0                        # categoria ausente vira 0%
    assert list(percentuais.columns) == ["Elite", "High", "Medium", "Low"]


def test_main_gera_figura(tmp_path):
    classificacoes().to_csv(tmp_path / "rq07_classificacoes.csv", index=False)
    pd.DataFrame({"comparacao": ["C1xC2", "C1xC3", "C2xC3"], "percentual_mudanca": [100, 33.3, 100],
                  "kappa_linear": [-0.2, 0.5, -0.1]}).to_csv(tmp_path / "rq07_comparacoes.csv",
                                                             index=False)
    rq07_grafico.main(["--dados", str(tmp_path), "--saida", str(tmp_path)])
    assert (tmp_path / "figuras" / "rq07_sensibilidade.png").stat().st_size > 0
