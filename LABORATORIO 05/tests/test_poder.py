"""Verificações do desenho temporal, estatística e planejamento prospectivo."""

from hashlib import sha256
import json

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from analise import poder


def grade_pequena(**kwargs):
    config = dict(dias=(2, 4), efeitos=(0, .2), sigmas=(.5,), rhos=(0, .5), reps=53)
    config.update(kwargs)
    return poder.executar_simulacao(**config)


def test_horarios_respeitam_unidade_horaria_e_pico_prespecificado():
    pico, fora = poder.indices_horarios(28)
    assert (len(pico), len(fora)) == (28*8, 28*16)
    assert np.all((pico % 24 >= 14) & (pico % 24 < 22))
    assert np.all((fora % 24 < 14) | (fora % 24 >= 22))
    np.testing.assert_array_equal(np.sort(np.r_[pico, fora]), np.arange(28*24))
    assert not set(pico).intersection(fora)


def test_cobertura_nao_transforma_endpoints_em_replicas():
    pico, fora = poder.indices_horarios(7, .73)
    assert len(pico) == int(np.floor(7*8*.73))
    assert len(fora) == int(np.floor(7*16*.73))
    assert np.all(np.diff(pico) > 0) and np.all(np.diff(fora) > 0)


def test_ar1_corresponde_a_recursao_estacionaria_sem_reset_diario():
    rho, horas, seed = .5, 49, 123
    eps = np.random.default_rng(seed).standard_normal((3, horas))
    esperado = np.empty_like(eps)
    esperado[:, 0] = eps[:, 0]
    for t in range(1, horas):
        esperado[:, t] = rho*esperado[:, t-1] + np.sqrt(1-rho*rho)*eps[:, t]
    obtido = poder._gerar_ar1(np.random.default_rng(seed), 3, horas, rho)
    np.testing.assert_allclose(obtido, esperado, atol=1e-15)


def test_ar1_mantem_variancia_estacionaria_e_correlacao_planejadas():
    x = poder._gerar_ar1(np.random.default_rng(7), 30_000, 12, .5)
    np.testing.assert_allclose(x.var(axis=0), 1, atol=.04)
    assert np.corrcoef(x[:, 0], x[:, 1])[0, 1] == pytest.approx(.5, abs=.02)


def test_pvalor_equivale_ao_scipy_e_log_preserva_os_postos():
    pico = np.array([[1, 3, 5], [2, 2, 4]], dtype=float)
    fora = np.array([[.5, 2, 4, 7], [1, 2, 3, 5]], dtype=float)
    esperado = [stats.mannwhitneyu(x, y, alternative="greater", method="asymptotic",
                                  use_continuity=False).pvalue for x, y in zip(pico, fora)]
    np.testing.assert_allclose(poder._p_valores(pico, fora), esperado)
    np.testing.assert_allclose(poder._p_valores(np.log(pico), np.log(fora)), esperado)


@pytest.mark.parametrize("rho", [0, .5])
def test_semente_reproduz_resultados_independentemente_do_lote(rho):
    a = poder.simular(dias=3, reps=197, rho=rho, tamanho_lote=1)
    b = poder.simular(dias=3, reps=197, rho=rho, tamanho_lote=67)
    c = poder.simular(dias=3, reps=197, rho=rho, tamanho_lote=1000)
    assert a == b == c


def test_simular_confere_com_calculo_direto_mesmas_trajetorias():
    dias, reps, efeito, sigma, rho, seed, alfa = 2, 43, .3, .5, .5, 17, .1
    idx_pico, idx_fora = poder.indices_horarios(dias)
    loglat = sigma*poder._gerar_ar1(np.random.default_rng(seed), reps, dias*24, rho)
    p = stats.mannwhitneyu(loglat[:, idx_pico] + np.log1p(efeito), loglat[:, idx_fora],
                           axis=1, alternative="greater", method="asymptotic",
                           use_continuity=False).pvalue
    resultado = poder.simular(dias, efeito, sigma, rho, reps=reps, semente=seed, alfa=alfa)
    assert resultado["rejeicoes"] == int(np.count_nonzero(p < alfa))
    assert resultado["taxa_rejeicao"] == resultado["rejeicoes"]/reps


def test_efeito_maior_nao_reduz_rejeicao_com_mesmos_sorteios():
    resultados = [poder.simular(dias=3, efeito=e, reps=300, rho=.5)["rejeicoes"]
                  for e in (0, .1, .2, .3)]
    assert resultados == sorted(resultados)
    assert resultados[-1] > resultados[0]


def test_nulo_iid_proximo_alfa_e_dependencia_alerta_inflacao():
    iid = poder.simular(dias=7, efeito=0, reps=5000)
    ar1 = poder.simular(dias=7, efeito=0, reps=5000, rho=.5)
    assert .035 < iid["taxa_rejeicao"] < .065
    assert ar1["taxa_rejeicao"] > .08
    assert ar1["ic_inf"] > .05


@pytest.mark.parametrize("campo,valor", [
    ("dias", 0), ("dias", True), ("dias", 1.5), ("reps", 0), ("reps", False),
    ("semente", -1), ("tamanho_lote", 0), ("efeito", -.1), ("efeito", np.nan),
    ("sigma_log", 0), ("sigma_log", np.inf), ("rho", -1), ("rho", 1),
    ("alfa", 0), ("alfa", 1), ("alfa", True), ("cobertura", 0), ("cobertura", 1.1),
    ("cobertura", .001),
])
def test_rejeita_configuracoes_invalidas(campo, valor):
    args = dict(dias=1, reps=1)
    args[campo] = valor
    with pytest.raises(ValueError):
        poder.simular(**args)


def test_wilson_extremos_e_referencia_conhecida():
    assert poder.intervalo_wilson(0, 10)[0] == pytest.approx(0)
    assert poder.intervalo_wilson(10, 10)[1] == pytest.approx(1)
    np.testing.assert_allclose(poder.intervalo_wilson(50, 100), (.4038315304, .5961684696))
    with pytest.raises(ValueError):
        poder.intervalo_wilson(11, 10)


@pytest.mark.parametrize("kwargs", [dict(dias=()), dict(sigmas=(.5, .5)), dict(efeitos=(.1, .2))])
def test_grade_exige_configuracoes_unicas_e_cenario_nulo(kwargs):
    with pytest.raises(ValueError):
        grade_pequena(**kwargs)


def test_grade_guarda_pressupostos_sem_ler_coleta():
    eventos = []
    df = grade_pequena(progresso=lambda *args: eventos.append(args))
    assert len(df) == 8 and len(eventos) == 8
    assert eventos[-1][:2] == (8, 8)
    meta = df.attrs["metadados"]
    assert meta["dados_reais_utilizados"] is False
    assert meta["data_used"] is False
    assert meta["pressupostos_sinteticos"] is True
    assert meta["alternativa"] == "greater"
    assert meta["configuracao"]["reps"] == 53
    assert not df.duplicated(poder.CHAVE).any()
    assert df.hipotese_nula_verdadeira.equals(df.efeito.eq(0))


def grade_controlada(taxas=(.5, .85), taxa_nulo=.05, rho=0):
    df = grade_pequena(rhos=(rho,), reps=1000)
    for i, linha in df.iterrows():
        taxa = taxa_nulo if linha.efeito == 0 else taxas[0 if linha.dias == 2 else 1]
        k = int(taxa*1000)
        df.loc[i, ["rejeicoes", "taxa_rejeicao", "ic_inf", "ic_sup"]] = [
            k, k/1000, *poder.intervalo_wilson(k, 1000)]
    return df


def test_resumo_primeiro_dia_avaliado_nao_minimo_exato():
    resumo = poder.resumir_planejamento(grade_controlada()).iloc[0]
    assert resumo.primeiro_dia_taxa_alvo == 4
    assert resumo.dias_planejamento_iid == 4
    assert resumo.alvo_atingido
    assert resumo.limite_inferior_atinge_alvo
    assert "não é mínimo exato" in resumo.interpretacao


def test_resumo_nao_inventa_duracao_quando_alvo_nao_atingido():
    resumo = poder.resumir_planejamento(grade_controlada(taxas=(.4, .6))).iloc[0]
    assert not resumo.alvo_atingido
    assert pd.isna(resumo.primeiro_dia_taxa_alvo)
    assert pd.isna(resumo.dias_planejamento_iid)
    assert resumo.dia_reportado == resumo.max_dias_avaliado == 4


@pytest.mark.parametrize("rho,nulo", [(0, .15), (.5, .05), (.5, .15)])
def test_resumo_nao_recomenda_independencia_violada_ou_nulo_descalibrado(rho, nulo):
    resumo = poder.resumir_planejamento(grade_controlada(rho=rho, taxa_nulo=nulo)).iloc[0]
    assert resumo.primeiro_dia_taxa_alvo == 4
    assert pd.isna(resumo.dias_planejamento_iid)
    assert not resumo.elegivel_planejamento_iid


def test_resumo_distingue_estimativa_pontual_de_limite_inferior():
    resumo = poder.resumir_planejamento(grade_controlada(taxas=(.4, .8))).iloc[0]
    assert resumo.alvo_atingido
    assert not resumo.limite_inferior_atinge_alvo


def test_resumo_rejeita_efeito_nao_simulado():
    with pytest.raises(ValueError, match="ausente"):
        poder.resumir_planejamento(grade_pequena(), efeito_planejado=.3)


@pytest.mark.parametrize("campo,valor", [("n_pico", 9), ("rejeicoes", -1), ("taxa_rejeicao", .999),
                                         ("ic_inf", .99), ("hipotese_nula_verdadeira", "sim"),
                                         ("alfa", np.nan), ("reps", 8.5)])
def test_validacao_rejeita_resultados_incoerentes(campo, valor):
    df = grade_pequena()
    if campo == "hipotese_nula_verdadeira":
        df[campo] = df[campo].astype(object)
    if campo == "reps":
        df[campo] = df[campo].astype(float)
    df.loc[0, campo] = valor
    with pytest.raises(ValueError):
        poder.validar_resultados(df)


def test_validacao_recusa_grupo_sem_controle_nulo_e_duplicatas():
    df = grade_pequena()
    with pytest.raises(ValueError, match="nula"):
        poder.validar_resultados(df[df.efeito != 0])
    with pytest.raises(ValueError, match="duplicados"):
        poder.validar_resultados(pd.concat([df, df.iloc[:1]]))


def test_salvar_carregar_preserva_taxas_metadados_e_hashes(tmp_path):
    df = grade_pequena()
    caminhos = poder.salvar_resultados(df, tmp_path)
    recarregado = poder.carregar_resultados(tmp_path)
    pd.testing.assert_frame_equal(poder.validar_resultados(df), recarregado, check_flags=False)
    meta = json.loads(caminhos["metadados"].read_text())
    assert meta["csv_sha256"] == sha256(caminhos["csv"].read_bytes()).hexdigest()
    assert meta["resumo_sha256"] == sha256(caminhos["resumo"].read_bytes()).hexdigest()
    assert set(meta["versoes"]) == {"python", "numpy", "pandas", "scipy"}
    assert meta["dados_reais_utilizados"] is False


@pytest.mark.parametrize("arquivo", ["csv", "resumo"])
def test_carregar_detecta_modificacao_de_artefatos(tmp_path, arquivo):
    caminhos = poder.salvar_resultados(grade_pequena(), tmp_path)
    with caminhos[arquivo].open("a") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="divergentes"):
        poder.carregar_resultados(tmp_path)


def test_cli_executa_fluxo_curto_e_alfa_conservador(tmp_path, capsys):
    assert poder.main(["--reps", "20", "--dias", "2", "--sigmas", ".5", "--rhos", "0",
                       "--efeitos", "0", ".2", "--alfa", str(.05/3), "--saida", str(tmp_path)]) == 0
    df = poder.carregar_resultados(tmp_path)
    assert len(df) == 2
    assert df.alfa.iloc[0] == pytest.approx(.05/3)
    assert "Não são dados nem potência observada" in capsys.readouterr().out
