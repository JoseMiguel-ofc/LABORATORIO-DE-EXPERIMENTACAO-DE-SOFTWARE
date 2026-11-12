"""Valida a entrega da Sprint 1 pelos comandos e controles usados no dashboard."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.exemplo import main

RAIZ = Path(__file__).resolve().parents[1]


def test_exemplo_cli_reproduz_resultados_e_interpretacoes(capsys):
    main([])
    primeira = json.loads(capsys.readouterr().out)
    main([])
    segunda = json.loads(capsys.readouterr().out)
    assert primeira == segunda
    assert primeira["semente"] == 42
    assert primeira["n_por_grupo"] == 30
    for resultado in primeira["testes"].values():
        assert 0 <= resultado["p_valor"] <= 1
        assert resultado["interpretacao"]
        assert resultado["rejeita_h0"] == (resultado["p_valor"] < 0.05)


def test_exemplo_cli_erro_util_para_parametro_invalido(capsys):
    with pytest.raises(SystemExit) as erro:
        main(["--efeito", "-1"])
    assert erro.value.code == 2
    assert "maior que -1" in capsys.readouterr().err


def test_dashboard_com_g1_g2_e_controles_funcionando():
    app = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=45).run()
    assert not app.exception
    assert len(app.header) == 7
    assert len(app.get("plotly_chart")) == 5
    assert all("G2" not in aviso.value for aviso in app.info)
    def tabela_exemplo():
        return next(item.value for item in app.dataframe
                    if "Teste" in item.value.columns
                    and "Medida do efeito" not in item.value.columns)

    resultados_iniciais = tabela_exemplo().copy()

    app.slider[0].set_value(-80).run()
    assert not app.exception
    assert not tabela_exemplo().equals(resultados_iniciais)

    app.number_input[0].set_value(200).run()
    assert not app.exception
    assert len(app.get("plotly_chart")) == 5

    app.radio[0].set_value("Linear").run()
    assert not app.exception
    assert len(app.get("plotly_chart")) == 5
