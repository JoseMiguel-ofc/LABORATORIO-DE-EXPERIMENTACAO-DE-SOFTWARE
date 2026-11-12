"""Equivalência escalar/vetorial, cenários e persistência da simulação."""

import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from src.motor import (EFEITOS_PADRAO, SITUACOES, caminho_manifesto,
                       carregar_resultados, executar_grade, intervalo_wilson,
                       salvar_resultados, simular, validar_resultados)
from src.simulacao import gerar
from src.testes import aplicar_testes


@pytest.fixture
def cenario():
    return {"parametros_base": {"mu": 1.0, "sigma": 0.7}}


@pytest.mark.parametrize("situacao", SITUACOES)
def test_motor_equivale_a_repeticoes_escalares(cenario, situacao):
    rng = np.random.default_rng(42)
    contagens = {"welch": 0, "mann_whitney": 0}
    for _ in range(41):
        amostra = gerar(8, 0.3, situacao, rng, cenario=cenario)
        testes = aplicar_testes(**amostra)
        for teste in contagens:
            contagens[teste] += testes[teste]["rejeita_h0"]
    observado = simular(situacao, 0.3, n=8, reps=41, tamanho_lote=13, cenario=cenario)
    assert observado.set_index("teste").rejeicoes.to_dict() == contagens


@pytest.mark.parametrize("situacao", SITUACOES)
def test_resultado_independe_de_tamanho_lote(cenario, situacao):
    pequeno = simular(situacao, 0.2, n=8, reps=101, tamanho_lote=7, cenario=cenario)
    grande = simular(situacao, 0.2, n=8, reps=101, tamanho_lote=1000, cenario=cenario)
    pd.testing.assert_frame_equal(pequeno, grande)


def test_rng_fornecido_avanca_sem_inventar_semente(cenario):
    rng = np.random.default_rng(55)
    inicio = json.dumps(rng.bit_generator.state)
    resultado = simular(rng=rng, reps=21, n=7, cenario=cenario)
    assert resultado.semente.isna().all()
    assert json.dumps(rng.bit_generator.state) != inicio
    repetido = simular(rng=np.random.default_rng(55), reps=21, n=7, cenario=cenario)
    pd.testing.assert_frame_equal(resultado, repetido)


@pytest.mark.parametrize("teste", ["welch", "mann_whitney"])
def test_subconjunto_de_testes_preserva_resultado(cenario, teste):
    ambos = simular(reps=111, n=8, efeito=0.3, cenario=cenario)
    sozinho = simular(reps=111, n=8, efeito=0.3, cenario=cenario, testes=(teste,))
    pd.testing.assert_frame_equal(sozinho, ambos.loc[ambos.teste.eq(teste)].reset_index(drop=True))


@pytest.mark.parametrize("testes", [(), [], ("welch", "welch"), ("desconhecido",), "welch", None])
def test_rejeita_subconjunto_de_testes_invalido(cenario, testes):
    with pytest.raises(ValueError, match="testes deve"):
        simular(reps=3, cenario=cenario, testes=testes)


def test_h0_independente_e_efeito_zero_identificados(cenario):
    for situacao in SITUACOES:
        amostras = gerar(12, 0, situacao, cenario=cenario)
        assert not np.array_equal(amostras["com_bot"], amostras["sem_bot"])
        resultado = simular(situacao, 0, reps=5, cenario=cenario)
        assert resultado.hipotese_nula_verdadeira.all() == (situacao != "variancias_diferentes")
    assert not simular(efeito=0.1, reps=5, cenario=cenario).hipotese_nula_verdadeira.any()


@pytest.mark.parametrize("situacao", SITUACOES)
def test_efeito_apenas_reescala_com_bot(cenario, situacao):
    base = gerar(10, 0, situacao, cenario=cenario)
    alternativa = gerar(10, 0.5, situacao, cenario=cenario)
    np.testing.assert_array_equal(alternativa["com_bot"], base["com_bot"] * 1.5)
    np.testing.assert_array_equal(alternativa["sem_bot"], base["sem_bot"])


def test_situacoes_mudam_parametros_exatamente(cenario):
    base = gerar(11, cenario=cenario)
    pequena = gerar(11, situacao="n_pequeno", cenario=cenario)
    assimetria = gerar(11, situacao="assimetria_forte", cenario=cenario)
    heterogenea = gerar(11, situacao="variancias_diferentes", cenario=cenario)
    for grupo in base:
        np.testing.assert_array_equal(pequena[grupo], base[grupo])
        np.testing.assert_allclose(np.log(assimetria[grupo])-1,
                                   (np.log(base[grupo])-1)*1.35)
    np.testing.assert_array_equal(heterogenea["sem_bot"], base["sem_bot"])
    np.testing.assert_array_equal(heterogenea["com_bot"], assimetria["com_bot"])


def test_outliers_correspondem_a_mistura_independente(cenario):
    esperado_rng = np.random.default_rng(42)
    base = esperado_rng.lognormal(1.0, 0.7, size=(2, 200))
    contaminacao = esperado_rng.random((2, 200)) < 0.05
    esperado = base * np.where(contaminacao, 20.0, 1.0)
    observado = gerar(200, situacao="outliers", cenario=cenario)
    np.testing.assert_array_equal(observado["com_bot"], esperado[0])
    np.testing.assert_array_equal(observado["sem_bot"], esperado[1])
    assert contaminacao.any() and (~contaminacao).any()


@pytest.mark.parametrize("kwargs", [
    {"reps": 0}, {"reps": True}, {"reps": 2.5}, {"n": 1},
    {"tamanho_lote": 0}, {"tamanho_lote": False}, {"semente": -1},
    {"alfa": 0}, {"alfa": 1}, {"alfa": float("nan")},
    {"efeito": -1}, {"rng": 42}, {"situacao": "ajuste_real"},
])
def test_rejeita_argumentos_invalidos(cenario, kwargs):
    parametros = {"reps": 5, "cenario": cenario, **kwargs}
    with pytest.raises(ValueError):
        simular(**parametros)


def test_wilson_referencia_e_extremos():
    assert intervalo_wilson(50, 100) == pytest.approx((0.4038315303659957, 0.5961684696340044))
    assert intervalo_wilson(0, 100)[0] == pytest.approx(0)
    assert intervalo_wilson(100, 100)[1] == pytest.approx(1)
    with pytest.raises(ValueError):
        intervalo_wilson(101, 100)


def test_grade_e_upsert_preservam_q3(tmp_path, cenario):
    caminho = tmp_path / "simulacao.csv"
    completa = executar_grade(reps=7, todas_situacoes=True, cenario=cenario)
    assert len(completa) == 5 * len(EFEITOS_PADRAO) * 2
    assert set(completa.loc[completa.situacao.eq("n_pequeno"), "n"]) == {10}
    salvar_resultados(completa, caminho, cenario=cenario)
    base = executar_grade(reps=11, cenario=cenario)
    salvar_resultados(base, caminho, cenario=cenario)
    lido = carregar_resultados(caminho)
    assert len(lido) == len(completa)
    assert set(lido.loc[lido.situacao.eq("base"), "reps"]) == {11}
    q3 = lido.loc[lido.situacao.ne("base")].reset_index(drop=True)
    esperado_q3 = validar_resultados(completa.loc[completa.situacao.ne("base")])
    pd.testing.assert_frame_equal(q3, esperado_q3)
    manifesto = json.loads(caminho_manifesto(caminho).read_text())
    assert len(manifesto["execucoes"]) == 2
    assert manifesto["contexto"]["parametros"] == cenario
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("adulteracao", ["taxa", "ic", "duplicata", "h0", "teste_ausente", "nao_finito"])
def test_valida_integridade_numerica(cenario, adulteracao):
    dados = simular(reps=10, cenario=cenario)
    if adulteracao == "taxa":
        dados.loc[0, "taxa_rejeicao"] = 0.999
    elif adulteracao == "ic":
        dados.loc[0, "ic_inf"] = -1
    elif adulteracao == "duplicata":
        dados = pd.concat([dados, dados.iloc[:1]])
    elif adulteracao == "h0":
        dados.loc[0, "hipotese_nula_verdadeira"] = False
    elif adulteracao == "teste_ausente":
        dados = dados.iloc[:1]
    else:
        dados.loc[0, "efeito"] = float("nan")
    with pytest.raises(ValueError):
        validar_resultados(dados)


def test_manifesto_detecta_csv_trocado_ou_ausente(tmp_path, cenario):
    caminho = tmp_path / "simulacao.csv"
    dados = simular(reps=5, cenario=cenario)
    salvar_resultados(dados, caminho, cenario=cenario)
    caminho.write_text(caminho.read_text() + "\n")
    with pytest.raises(ValueError, match="divergem"):
        carregar_resultados(caminho)
    caminho_manifesto(caminho).unlink()
    with pytest.raises(ValueError, match="manifesto"):
        carregar_resultados(caminho)


def test_nao_mistura_calibracoes(tmp_path, cenario):
    caminho = tmp_path / "simulacao.csv"
    salvar_resultados(simular(reps=5, cenario=cenario), caminho, cenario=cenario)
    outro = {"parametros_base": {"mu": 2.0, "sigma": 0.7}}
    with pytest.raises(ValueError, match="outra calibração"):
        salvar_resultados(simular(reps=5, cenario=outro), caminho, cenario=outro)


def test_cli_executa_e_valida_entrada(tmp_path):
    raiz = Path(__file__).resolve().parents[1]
    saida = tmp_path / "execucao.csv"
    comando = [sys.executable, "-m", "src.rodar_q1_q2", "--reps", "3", "--saida", str(saida)]
    execucao = subprocess.run(comando, cwd=raiz, capture_output=True, text=True,
                              encoding="utf-8")
    assert execucao.returncode == 0, execucao.stderr
    assert len(carregar_resultados(saida)) == 12
    assert "Execução rápida" in execucao.stdout
    invalida = subprocess.run(comando + ["--reps", "0"], cwd=raiz, capture_output=True, text=True,
                              encoding="utf-8")
    assert invalida.returncode != 0
    assert "reps deve" in invalida.stderr


def test_grade_completa_recupera_manifesto_obsoleto_e_remove_configuracoes_antigas(tmp_path):
    raiz = Path(__file__).resolve().parents[1]
    saida = tmp_path / "execucao.csv"
    salvar_resultados(simular(reps=3, n=50), saida)
    manifesto_path = caminho_manifesto(saida)
    manifesto = json.loads(manifesto_path.read_text())
    manifesto["contexto"]["codigo_sha256"]["motor.py"] = "obsoleto"
    manifesto_path.write_text(json.dumps(manifesto))
    with pytest.raises(ValueError, match="divergem"):
        carregar_resultados(saida)
    execucao = subprocess.run(
        [sys.executable, "-m", "src.rodar_q1_q2", "--reps", "3",
         "--todas-situacoes", "--saida", str(saida)], cwd=raiz, capture_output=True, text=True,
                              encoding="utf-8")
    assert execucao.returncode == 0, execucao.stderr
    assert "[30/30]" in execucao.stdout
    dados = carregar_resultados(saida)
    assert len(dados) == 60
    assert set(dados.n) == {10, 30}
