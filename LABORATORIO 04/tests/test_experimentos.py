"""Caches por α: isolamento, reprodução e limiares sobre os mesmos sorteios."""

from pathlib import Path
from copy import deepcopy
import shutil
import subprocess
import sys

import pandas as pd
import pytest

from src import amostra, experimentos, motor

RAIZ = Path(__file__).resolve().parents[1]


def test_caminhos_preservam_5pct_e_isolam_outros_alfas(tmp_path):
    assert experimentos.diretorio_alfa(.05, tmp_path) == tmp_path
    assert experimentos.diretorio_alfa(.01, tmp_path) == tmp_path / "alfa_001"
    assert experimentos.diretorio_alfa(.10, tmp_path) == tmp_path / "alfa_010"
    assert experimentos.caminhos_alfa(.05)["simulacao"] == motor.RESULTADOS
    assert not (tmp_path / "alfa_001").exists()


@pytest.mark.parametrize("alfa", [0, 1, .02, True, None, "inválido", float("nan")])
def test_rejeita_alfa_nao_suportado(alfa):
    with pytest.raises(ValueError):
        experimentos.diretorio_alfa(alfa)


def test_rejeicoes_crescem_com_alfa_sobre_os_mesmos_sorteios():
    cenario = {"parametros_base": {"mu": 1., "sigma": .7}}
    grades = [motor.executar_grade(reps=100, todas_situacoes=True, alfa=alfa,
                                   cenario=cenario)
              for alfa in experimentos.ALFAS]
    for menor, maior in zip(grades, grades[1:]):
        pd.testing.assert_frame_equal(menor[["situacao", "efeito", "n", "teste"]],
                                      maior[["situacao", "efeito", "n", "teste"]])
        assert maior["rejeicoes"].ge(menor["rejeicoes"]).all()
        assert maior["taxa_rejeicao"].ge(menor["taxa_rejeicao"]).all()
    assert any(grades[2]["rejeicoes"] > grades[0]["rejeicoes"])


@pytest.fixture
def cache_pequeno(tmp_path):
    experimentos.precomputar(reps=3, n_max=2000, raiz=tmp_path,
                             alfas=(.01,), progresso=None)
    return tmp_path


def test_reuso_preserva_bytes_e_nao_chama_simulacoes(cache_pequeno, monkeypatch):
    arquivos = {p: p.read_bytes() for p in cache_pequeno.rglob("*") if p.is_file()}

    def falhar(**kwargs):
        pytest.fail("Um cache válido não deve recalcular a simulação.")

    monkeypatch.setattr(motor, "executar_grade", falhar)
    monkeypatch.setattr(amostra, "analisar_amostra", falhar)
    mensagens = []
    retorno = experimentos.precomputar(reps=3, n_max=2000, raiz=cache_pequeno,
                                       alfas=(.01,), progresso=mensagens.append)
    assert len(retorno[.01]["simulacao"]) == 60
    assert len(mensagens) == 2
    assert all("cache válido" in mensagem for mensagem in mensagens)
    assert arquivos == {p: p.read_bytes() for p in arquivos}


def test_loader_rejeita_cache_de_outro_alfa(cache_pequeno):
    origem = experimentos.diretorio_alfa(.01, cache_pequeno)
    destino = experimentos.diretorio_alfa(.10, cache_pequeno)
    shutil.copytree(origem, destino)
    for carregar in (experimentos.carregar_simulacao_alfa, experimentos.carregar_amostra_alfa):
        with pytest.raises(ValueError, match="outro alfa"):
            carregar(.10, cache_pequeno)


def test_cache_incompleto_regenera_so_a_fase_faltante(cache_pequeno, monkeypatch):
    caminhos = experimentos.caminhos_alfa(.01, cache_pequeno)
    simulacao_original = caminhos["simulacao"].read_bytes()
    caminhos["amostra"].unlink()

    def falhar(**kwargs):
        pytest.fail("A grade Q1/Q2/Q3 válida deve ser preservada.")

    monkeypatch.setattr(motor, "executar_grade", falhar)
    experimentos.precomputar(reps=3, n_max=2000, raiz=cache_pequeno,
                             alfas=(.01,), progresso=None)
    assert caminhos["simulacao"].read_bytes() == simulacao_original
    assert caminhos["amostra"].is_file()
    assert experimentos.carregar_amostra_alfa(.01, cache_pequeno)["alfa"].eq(.01).all()


def test_loader_rejeita_cenario_customizado_e_regenera_so_grade(cache_pequeno, monkeypatch):
    caminhos = experimentos.caminhos_alfa(.01, cache_pequeno)
    curva_original = caminhos["amostra"].read_bytes()
    cenario = deepcopy(experimentos.ajustar_cenario())
    cenario["parametros_base"]["sigma"] = 0.1
    grade = motor.executar_grade(reps=3, todas_situacoes=True, alfa=.01, cenario=cenario)
    motor.salvar_resultados(grade, caminhos["simulacao"], cenario=cenario, substituir=True)
    # A API genérica aceita uma calibração legítima customizada; o dashboard
    # deve recusá-la, pois apresenta resultados do cenário real específico.
    assert len(motor.carregar_resultados(caminhos["simulacao"])) == 60
    with pytest.raises(ValueError, match="outro cenário"):
        experimentos.carregar_simulacao_alfa(.01, cache_pequeno)

    def falhar(**kwargs):
        pytest.fail("A curva de amostra com calibração real deve ser preservada.")

    monkeypatch.setattr(amostra, "analisar_amostra", falhar)
    experimentos.precomputar(reps=3, n_max=2000, raiz=cache_pequeno,
                             alfas=(.01,), progresso=None)
    assert len(experimentos.carregar_simulacao_alfa(.01, cache_pequeno)) == 60
    assert caminhos["amostra"].read_bytes() == curva_original


@pytest.mark.parametrize("metadados_discordam_do_csv", [False, True])
def test_loader_rejeita_efeitos_customizados_e_regenera_so_amostra(
        cache_pequeno, monkeypatch, metadados_discordam_do_csv):
    caminhos = experimentos.caminhos_alfa(.01, cache_pequeno)
    simulacao_original = caminhos["simulacao"].read_bytes()
    efeitos_padrao = experimentos.carregar_amostra_alfa(.01, cache_pequeno).attrs[
        "metadados"]["parametros"]["efeitos"]
    curvas = amostra.analisar_amostra(
        reps=3, n_max=2000, alfa=.01,
        efeitos={"planejado_30pct": 1.7, "observado_mediana": 3.4})
    if metadados_discordam_do_csv:
        curvas.attrs["metadados"]["parametros"]["efeitos"] = efeitos_padrao
    amostra.salvar_amostra(curvas, experimentos.diretorio_alfa(.01, cache_pequeno))
    with pytest.raises(ValueError, match="efeitos"):
        experimentos.carregar_amostra_alfa(.01, cache_pequeno)

    def falhar(**kwargs):
        pytest.fail("A grade Q1/Q2/Q3 válida deve ser preservada.")

    monkeypatch.setattr(motor, "executar_grade", falhar)
    experimentos.precomputar(reps=3, n_max=2000, raiz=cache_pequeno,
                             alfas=(.01,), progresso=None)
    carregado = experimentos.carregar_amostra_alfa(.01, cache_pequeno)
    assert carregado.attrs["metadados"]["parametros"]["efeitos"] == efeitos_padrao
    assert caminhos["simulacao"].read_bytes() == simulacao_original


def test_configuracao_diferente_regenera_e_forcar_recalcula(cache_pequeno, monkeypatch):
    chamadas = []
    grade_real = motor.executar_grade

    def calcular(**kwargs):
        chamadas.append(kwargs)
        return grade_real(**kwargs)

    monkeypatch.setattr(motor, "executar_grade", calcular)
    for forcar in (False, True):
        experimentos.precomputar(reps=4, semente=7, n_max=2000, raiz=cache_pequeno,
                                 alfas=(.01,), forcar=forcar, progresso=None)
    assert len(chamadas) == 2
    for carregar in (experimentos.carregar_simulacao_alfa, experimentos.carregar_amostra_alfa):
        lido = carregar(.01, cache_pequeno)
        assert lido["reps"].eq(4).all()
        assert lido["semente"].eq(7).all()


@pytest.mark.parametrize("kwargs", [{"reps": 0}, {"reps": True}, {"semente": -1},
                                   {"n_max": 1999}, {"alfas": []}, {"alfas": None},
                                   {"alfas": [.02]}, {"forcar": "sim"}, {"progresso": 1}])
def test_configuracao_invalida_nao_cria_arquivos(tmp_path, kwargs):
    with pytest.raises(ValueError):
        experimentos.precomputar(raiz=tmp_path, **kwargs)
    assert not list(tmp_path.iterdir())


def test_cli_rapida_gera_tres_caches_e_reproduzir_bootstrap(tmp_path):
    comando = [sys.executable, "-m", "src.reproduzir", "--reps", "2", "--n-max", "2000",
               "--n-resamples", "100", "--saida", str(tmp_path)]
    execucao = subprocess.run(comando, cwd=RAIZ, capture_output=True, text=True)
    assert execucao.returncode == 0, execucao.stderr
    assert "α=1% | Simulação [30/30]" in execucao.stdout
    assert "α=5% | Amostra" in execucao.stdout
    assert "α=10% | Amostra" in execucao.stdout
    assert "diagnóstico" in execucao.stdout
    for alfa in experimentos.ALFAS:
        assert len(experimentos.carregar_simulacao_alfa(alfa, tmp_path)) == 60
        assert experimentos.carregar_amostra_alfa(alfa, tmp_path)["alfa"].eq(alfa).all()
    assert (tmp_path / "efeitos_ic.csv").is_file()
    repetida = subprocess.run(comando, cwd=RAIZ, capture_output=True, text=True)
    assert repetida.returncode == 0, repetida.stderr
    assert repetida.stdout.count("cache válido reutilizado") == 7


def test_cli_rejeita_configuracao_invalida_antes_de_escrever(tmp_path):
    execucao = subprocess.run(
        [sys.executable, "-m", "src.reproduzir", "--n-resamples", "1", "--saida", str(tmp_path)],
        cwd=RAIZ, capture_output=True, text=True)
    assert execucao.returncode != 0
    assert "n-resamples deve" in execucao.stderr
    assert not list(tmp_path.iterdir())
