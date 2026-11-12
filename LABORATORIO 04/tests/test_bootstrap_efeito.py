"""Validação estatística dos ICs BCa e de sua procedência persistida."""

import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from scipy.stats import bootstrap

from src.efeito import cliffs_delta, hedges_g
from src import intervalos_efeito as ic


@pytest.fixture
def grupos():
    rng = np.random.default_rng(2026)
    return rng.gamma(2, 3, 23), rng.gamma(2.2, 2.5, 31)


@pytest.fixture
def calculado(grupos):
    return ic.calcular_intervalos(*grupos, n_resamples=200)


def test_confere_estimativas_e_bca_scipy_independente(grupos, calculado):
    assert set(calculado.teste) == {"welch", "mann_whitney"}
    for teste, funcao in (("welch", hedges_g), ("mann_whitney", cliffs_delta)):
        referencia = bootstrap(grupos, funcao, n_resamples=200, vectorized=False,
                               paired=False, batch=500, method="BCa", confidence_level=.95,
                               random_state=np.random.default_rng(42))
        linha = calculado.set_index("teste").loc[teste]
        assert linha.estimativa == pytest.approx(funcao(*grupos))
        assert linha.ic_inf == pytest.approx(referencia.confidence_interval.low)
        assert linha.ic_sup == pytest.approx(referencia.confidence_interval.high)
    parametros = calculado.attrs["metadados"]["parametros"]
    assert parametros["n_com_bot"] == 23
    assert parametros["n_sem_bot"] == 31
    assert parametros["paired"] is False


def test_nao_pareia_observacoes_por_posicao(grupos):
    com, sem = grupos[0], grupos[1][:23]
    resultado = ic.calcular_intervalos(com, sem, n_resamples=300)
    pareado = bootstrap((com, sem), hedges_g, n_resamples=300, vectorized=False,
                        paired=True, batch=500, method="BCa", confidence_level=.95,
                        random_state=np.random.default_rng(42))
    independente = bootstrap((com, sem), hedges_g, n_resamples=300, vectorized=False,
                             paired=False, batch=500, method="BCa", confidence_level=.95,
                             random_state=np.random.default_rng(42))
    limites = resultado.iloc[0][["ic_inf", "ic_sup"]].to_numpy(dtype=float)
    np.testing.assert_allclose(limites, independente.confidence_interval)
    assert not np.allclose(limites, pareado.confidence_interval)


def test_reprodutibilidade_e_outra_semente(grupos, calculado):
    pd.testing.assert_frame_equal(calculado, ic.calcular_intervalos(*grupos, n_resamples=200))
    outra = ic.calcular_intervalos(*grupos, n_resamples=200, semente=11)
    np.testing.assert_array_equal(calculado.estimativa, outra.estimativa)
    assert not np.allclose(calculado[["ic_inf", "ic_sup"]], outra[["ic_inf", "ic_sup"]])


def test_nivel_maior_amplia_intervalos_com_as_mesmas_reamostras(grupos, calculado):
    estreito = ic.calcular_intervalos(*grupos, n_resamples=200, confianca=.8)
    assert (calculado.ic_inf <= estreito.ic_inf).all()
    assert (calculado.ic_sup >= estreito.ic_sup).all()


def test_empates_preservam_delta_e_reamostragem_independente():
    com = np.repeat(np.arange(7, dtype=float), [2, 3, 2, 4, 2, 4, 3])
    sem = np.repeat(np.arange(7, dtype=float), [4, 3, 2, 2, 3, 4, 2])
    resultado = ic.calcular_intervalos(com, sem, n_resamples=200)
    pares = com[:, None] - sem[None, :]
    delta = (np.count_nonzero(pares > 0) - np.count_nonzero(pares < 0)) / pares.size
    assert resultado.set_index("teste").loc["mann_whitney", "estimativa"] == pytest.approx(delta)
    assert resultado.loc[resultado.teste == "mann_whitney", "ic_inf"].iloc[0] >= -1
    assert resultado.loc[resultado.teste == "mann_whitney", "ic_sup"].iloc[0] <= 1


@pytest.mark.parametrize("config", [
    {"n_resamples": 0}, {"n_resamples": 1}, {"n_resamples": 2.5},
    {"n_resamples": True}, {"semente": -1}, {"semente": 1.5}, {"semente": False},
    {"confianca": 0}, {"confianca": 1}, {"confianca": np.nan},
    {"confianca": np.inf}, {"confianca": True}, {"confianca": "0.95"},
])
def test_rejeita_configuracao_invalida(grupos, config):
    with pytest.raises(ValueError):
        ic.calcular_intervalos(*grupos, **config)


def test_jackknife_exige_tres_observacoes_em_cada_grupo(grupos):
    with pytest.raises(ValueError, match="três observações"):
        ic.calcular_intervalos(grupos[0][:2], grupos[1], n_resamples=100)


def test_amostras_invalidas_nao_chegam_ao_bootstrap(grupos):
    with pytest.raises(ValueError, match="finitas"):
        ic.calcular_intervalos([1, np.nan, 3], grupos[1])


def test_g_indefinido_tem_erro_explicativo():
    with pytest.raises(ValueError, match="Hedges.*desvio combinado zero"):
        ic.calcular_intervalos(np.ones(10), np.ones(10), n_resamples=200)


def test_cliff_degenerado_nao_vira_intervalo_nulo_sem_aviso():
    with pytest.raises(ValueError, match="Cliff.*degenerado"):
        ic.calcular_intervalos(np.arange(20, 40), np.arange(20), n_resamples=200)


@pytest.mark.parametrize("defeito", ["replica_nan", "limite_nan", "invertido"])
def test_erro_se_alguma_reamostra_ou_limite_invalido(monkeypatch, grupos, defeito):
    def invalido(*args, **kwargs):
        return SimpleNamespace(
            confidence_interval=((np.nan, 1) if defeito == "limite_nan" else
                                 (1, -1) if defeito == "invertido" else (-1, 1)),
            bootstrap_distribution=np.array([0, np.nan if defeito == "replica_nan" else .5]),
        )
    monkeypatch.setattr(ic, "bootstrap", invalido)
    with pytest.raises(ValueError, match="Nenhuma reamostra foi descartada"):
        ic.calcular_intervalos(*grupos, n_resamples=200)


def test_bca_pode_nao_conter_estimativa_pontual(monkeypatch, grupos, tmp_path):
    monkeypatch.setattr(ic, "bootstrap", lambda *args, **kwargs: SimpleNamespace(
        confidence_interval=(.8, .9), bootstrap_distribution=np.array([.5, .8, .9]),
    ))
    resultado = ic.calcular_intervalos(*grupos, n_resamples=200)
    assert (resultado.estimativa < resultado.ic_inf).all()
    ic.salvar_intervalos(resultado, tmp_path / "fora_estimativa.csv")


def test_cache_roundtrip_e_caminho_fora_do_diretorio_corrente(
        monkeypatch, grupos, calculado, tmp_path):
    monkeypatch.setattr(ic, "_grupos_reais", lambda: grupos)
    arquivo = tmp_path / "outro" / "efeitos_ic.csv"
    caminhos = ic.salvar_intervalos(calculado, arquivo)
    monkeypatch.chdir(tmp_path)
    reaberto = ic.carregar_intervalos(arquivo)
    pd.testing.assert_frame_equal(calculado, reaberto)
    meta = json.loads(caminhos["metadados"].read_text())
    assert set(meta["metodo_sha256"]) == {"efeito.py", "intervalos_efeito.py"}
    assert meta["parametros"]["confianca"] == .95
    assert meta["parametros"]["n_resamples"] == 200
    assert {"python", "numpy", "pandas", "scipy"} <= set(meta["versoes"])


def test_cache_detecta_csv_modificado(monkeypatch, grupos, calculado, tmp_path):
    monkeypatch.setattr(ic, "_grupos_reais", lambda: grupos)
    arquivo = ic.salvar_intervalos(calculado, tmp_path / "ic.csv")["csv"]
    arquivo.write_text(arquivo.read_text() + "\n")
    with pytest.raises(ValueError, match="CSV de intervalos foi modificado"):
        ic.carregar_intervalos(arquivo)


def test_cache_detecta_dados_diferentes(monkeypatch, grupos, calculado, tmp_path):
    arquivo = ic.salvar_intervalos(calculado, tmp_path / "ic.csv")["csv"]
    monkeypatch.setattr(ic, "_grupos_reais", lambda: (grupos[0] * 2, grupos[1]))
    with pytest.raises(ValueError, match="dados reais mudaram"):
        ic.carregar_intervalos(arquivo)


def test_cache_detecta_metodo_diferente(monkeypatch, grupos, calculado, tmp_path):
    arquivo = ic.salvar_intervalos(calculado, tmp_path / "ic.csv")["csv"]
    monkeypatch.setattr(ic, "_grupos_reais", lambda: grupos)
    monkeypatch.setattr(ic, "_hashes_metodo", lambda: {"efeito.py": "novo"})
    with pytest.raises(ValueError, match="método mudou"):
        ic.carregar_intervalos(arquivo)


@pytest.mark.parametrize("alteracao", ["config", "ausente", "pareado", "n"])
def test_cache_rejeita_manifesto_inconsistente(
        monkeypatch, grupos, calculado, tmp_path, alteracao):
    monkeypatch.setattr(ic, "_grupos_reais", lambda: grupos)
    caminhos = ic.salvar_intervalos(calculado, tmp_path / "ic.csv")
    meta = json.loads(caminhos["metadados"].read_text())
    if alteracao == "config":
        meta["parametros"]["confianca"] = .9
    elif alteracao == "ausente":
        del meta["parametros"]
    elif alteracao == "pareado":
        meta["parametros"]["paired"] = True
    else:
        meta["parametros"]["n_com_bot"] = 10
    caminhos["metadados"].write_text(json.dumps(meta))
    with pytest.raises(ValueError):
        ic.carregar_intervalos(caminhos["csv"])


def test_salvar_recusa_tabela_sem_procedencia(calculado, tmp_path):
    calculado.attrs = {}
    with pytest.raises(ValueError, match="Metadados"):
        ic.salvar_intervalos(calculado, tmp_path / "ic.csv")


def test_cli_real_salva_e_detecta_alteracao_da_fonte(tmp_path, monkeypatch, capsys):
    origem = tmp_path / "fonte.csv"
    origem.write_bytes(ic.CSV.read_bytes())
    monkeypatch.setattr(ic, "CSV", origem)
    arquivo = tmp_path / "efeitos_ic.csv"
    ic.main(["--n-resamples", "200", "--saida", str(arquivo)])
    resultado = ic.carregar_intervalos(arquivo)
    assert len(resultado) == 2
    assert "g de Hedges" in capsys.readouterr().out
    assert resultado.attrs["metadados"]["fonte"] == "dados/prs.csv"
    origem.write_bytes(origem.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="CSV de origem mudou"):
        ic.carregar_intervalos(arquivo)


def test_cli_parametro_invalido_retorna_erro(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        ic.main(["--confianca", "1", "--saida", str(tmp_path / "ic.csv")])
    assert exc.value.code == 2
    assert "confianca" in capsys.readouterr().err
