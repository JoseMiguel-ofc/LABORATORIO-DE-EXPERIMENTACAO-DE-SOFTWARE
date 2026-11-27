"""Integração da Sprint 2: seleção temporal, dados reais separados e reprodução."""
import csv
from hashlib import sha256
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from analise.analise import (analisar, diagnostico_temporal, gerar_relatorio,
                             main, preparar_dados)
from analise.piloto import COLUNAS

CONFIG = {"usuarios_online": {"nome": "ValveStats"},
          "endpoints": [{"nome": "GetServerInfo"}, {"nome": "ServicoB"}]}


def linha(ts, endpoint="GetServerInfo", latencia="100", usuarios="30000000",
          status="200", erro=""):
    return dict(zip(COLUNAS, [ts, endpoint, status, latencia, usuarios, erro, "1000000"]))


def gravar(tmp_path, linhas):
    caminho = tmp_path / "coleta.csv"
    with caminho.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUNAS)
        writer.writeheader()
        writer.writerows(linhas)
    return caminho


def amostra():
    return [linha(f"2026-11-{dia:02d}T{hora}:17:00Z", latencia=str(lat), usuarios=str(usuarios))
            for dia, hora, lat, usuarios in [(19, "14", 300, 35_000_000),
                (19, "00", 40, 20_000_000), (20, "14", 200, 33_000_000),
                (20, "00", 30, 21_000_000), (21, "14", 100, 31_000_000),
                (21, "00", 20, 22_000_000)]]


def test_primeira_tentativa_por_hora_independe_do_resultado(tmp_path):
    entrada = gravar(tmp_path, [
        linha("2026-11-26T15:17:00Z", latencia="30"),
        linha("2026-11-26T15:08:00Z", status="", erro="Timeout", latencia="15000"),
        linha("2026-11-26T15:08:00Z", status="", erro="Timeout", latencia="15000"),
        linha("2026-11-26T16:17:00Z", endpoint="ValveStats"),
        linha("2026-11-26T16:17:00Z", endpoint="Desconhecido"),
    ])
    antes = entrada.read_bytes()
    dados, meta = preparar_dados(entrada, config=CONFIG)
    assert len(dados) == 1
    assert not dados.iloc[0].sucesso_operacional
    assert not dados.iloc[0].latencia_analisavel
    assert meta["repeticoes_endpoint_hora_excluidas"] == 1
    assert meta["diagnostico_entrada"]["duplicatas_excluidas"] == 1
    assert meta["consultas_auxiliares_excluidas"] == 1
    assert meta["medicoes_desconhecidas_excluidas"] == 1
    assert entrada.read_bytes() == antes
    assert meta["sha256_csv"] == sha256(antes).hexdigest()


def test_pico_limites_e_janela_manutencao_com_dst(tmp_path):
    timestamps = ["2026-11-23T13:59:00Z", "2026-11-23T14:00:00Z",
                  "2026-11-23T21:59:00Z", "2026-11-23T22:00:00Z",
                  "2026-11-24T22:17:00Z", "2026-11-24T23:17:00Z",
                  "2026-11-25T01:17:00Z", "2026-11-25T02:17:00Z",
                  "2026-06-23T22:17:00Z", "2026-06-24T00:17:00Z", "2026-06-24T01:17:00Z"]
    dados, _ = preparar_dados(gravar(tmp_path, [linha(t) for t in timestamps]), config=CONFIG)
    dados = dados.set_index("timestamp")
    assert [dados.loc[pd.Timestamp(t), "periodo"] for t in timestamps[:4]] == [
        "fora_do_pico", "pico", "pico", "fora_do_pico"]
    assert [bool(dados.loc[pd.Timestamp(t), "janela_manutencao"]) for t in timestamps[4:]] == [
        False, True, True, False, True, True, False]


def test_filtro_semiaberto_com_fusos_equivalentes(tmp_path):
    entrada = gravar(tmp_path, [linha("2026-11-19T13:17:00Z"),
                               linha("2026-11-19T14:17:00Z"),
                               linha("2026-11-19T15:17:00Z")])
    dados, meta = preparar_dados(entrada, config=CONFIG,
                                 inicio="2026-11-19T11:17:00-03:00",
                                 fim="2026-11-19T15:17:00Z")
    assert len(dados) == 1
    assert dados.timestamp.iloc[0] == pd.Timestamp("2026-11-19T14:17:00Z")
    assert meta["linhas_fora_filtro_temporal"] == 2


@pytest.mark.parametrize("kwargs", [{"inicio": "2026-11-19"}, {"fim": "sem-data"},
    {"inicio": "2026-11-20T00:00Z", "fim": "2026-11-19T00:00Z"}])
def test_limites_invalidos_falham_claramente(tmp_path, kwargs):
    with pytest.raises(ValueError):
        preparar_dados(gravar(tmp_path, amostra()), config=CONFIG, **kwargs)


def test_falhas_missing_e_numeradores_nao_se_misturam(tmp_path):
    linhas = [linha("2026-11-19T01:17:00Z", latencia="10"),
              linha("2026-11-19T02:17:00Z", status="", erro="Timeout", latencia="15000"),
              linha("2026-11-19T03:17:00Z", status="", erro="", latencia="999"),
              linha("2026-11-19T04:17:00Z", latencia="", usuarios="")]
    resultado = analisar(gravar(tmp_path, linhas), config=CONFIG)
    r = resultado["tabelas"]["descritiva_endpoint"].iloc[0]
    assert (r.medicoes, r.tentativas_classificaveis, r.tentativas_nao_classificaveis) == (4, 3, 1)
    assert (r.sucessos, r.falhas, r.n_latencias) == (2, 1, 1)
    assert r.mediana_ms == 10
    assert np.isnan(r.dp_ms)
    assert r.sucesso_observado_pct == pytest.approx(200/3)
    assert r.n_pares_usuarios_latencia == 1


def test_grades_completas_nao_inventam_medicoes_para_grupos_vazios(tmp_path):
    resultado = analisar(gravar(tmp_path, amostra()), config=CONFIG)
    tab = resultado["tabelas"]
    assert len(tab["descritiva_endpoint"]) == 2
    assert len(tab["descritiva_periodo"]) == 4
    assert len(tab["descritiva_dia_semana"]) == 14
    assert len(tab["normalidade"]) == 20
    vazio = tab["descritiva_endpoint"].query("endpoint == 'ServicoB'").iloc[0]
    assert vazio.medicoes == 0 and np.isnan(vazio.mediana_ms)
    assert not resultado["dados"].endpoint.eq("ValveStats").any()


def test_testes_integrados_scipy_holm_preserva_h3_ausente(tmp_path):
    resultado = analisar(gravar(tmp_path, amostra()), config=CONFIG)
    tab = resultado["tabelas"]["hipoteses"]
    primario = tab[tab.endpoint.eq("GetServerInfo")].set_index("hipotese")
    p1 = stats.mannwhitneyu([300, 200, 100], [40, 30, 20],
                           alternative="greater", method="asymptotic", use_continuity=False).pvalue
    assert primario.loc["H1", "p_valor"] == pytest.approx(p1)
    assert primario.loc["H1", "efeito"] == 1
    assert pd.isna(primario.loc["H3", "p_valor"])
    assert primario.loc["H3", "n1"] == 0
    assert primario.m_familia.eq(3).all()
    assert primario.loc["H1", "p_holm"] >= p1
    assert tab.carater.eq("exploratorio_independencia_nao_verificada").all()
    assert tab.query("endpoint == 'ServicoB'").p_holm.isna().all()


def test_fisher_usa_falhas_janela_na_primeira_linha(tmp_path):
    linhas = [linha("2026-11-24T23:17:00Z", status="503", erro="HTTP 503"),
              linha("2026-11-25T00:17:00Z", status="", erro="Timeout"),
              linha("2026-11-25T01:17:00Z"),
              linha("2026-11-25T02:17:00Z"), linha("2026-11-25T03:17:00Z"),
              linha("2026-11-25T04:17:00Z")]
    resultado = analisar(gravar(tmp_path, linhas), config=CONFIG)
    h3 = resultado["tabelas"]["hipoteses"].query("endpoint == 'GetServerInfo' and hipotese == 'H3'").iloc[0]
    assert h3.tabela_2x2 == [[2, 1], [0, 3]]
    assert h3.p_valor == pytest.approx(stats.fisher_exact([[2, 1], [0, 3]], alternative="greater").pvalue)
    assert h3.efeito_limite == "infinito" and pd.isna(h3.efeito)


def test_lag_horario_nao_comprime_lacunas(tmp_path):
    linhas = [linha(f"2026-11-19T{hora:02d}:17:00Z", latencia=str(valor))
              for hora, valor in [(0, 500), (6, 10), (7, 20), (8, 30)]]
    dados, _ = preparar_dados(gravar(tmp_path, linhas), config=CONFIG)
    diag = diagnostico_temporal(dados, ["GetServerInfo"]).iloc[0]
    assert diag.pares_consecutivos_validos_1h == 2
    assert pd.isna(diag.correlacao_descritiva_lag1h)
    assert diag.horas_calendario_entre_primeira_e_ultima == 9


def test_header_only_produz_analise_explicitamente_nao_estimavel(tmp_path):
    resultado = analisar(gravar(tmp_path, []), config=CONFIG)
    assert resultado["dados"].empty
    assert resultado["tabelas"]["hipoteses"].p_holm.isna().all()
    assert resultado["tabelas"]["descritiva_endpoint"].medicoes.eq(0).all()


def test_relatorio_reproduzivel_hashes_figuras_e_preserva_csv(tmp_path):
    entrada = gravar(tmp_path, amostra())
    antes = entrada.read_bytes()
    saida = tmp_path / "resultados"
    caminhos = gerar_relatorio(entrada, saida, config=CONFIG)
    meta = json.loads(caminhos["metadados"].read_text())
    assert entrada.read_bytes() == antes
    assert meta["dataset_congelado"] is False
    assert meta["sha256_csv"] == sha256(antes).hexdigest()
    for arquivo, digest in meta["sha256_artefatos"].items():
        assert sha256((saida/arquivo).read_bytes()).hexdigest() == digest
    for nome in ("latencia_hora", "boxplot_periodo", "dispersao_usuarios"):
        assert caminhos[nome].read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    texto = caminhos["relatorio"].read_text()
    assert "não declara o dataset congelado" in texto
    assert "Não estimável" in texto
    for destino in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", texto):
        assert (saida/destino).exists(), destino
    primeira = caminhos["hipoteses"].read_bytes()
    gerar_relatorio(entrada, saida, config=CONFIG)
    assert primeira == caminhos["hipoteses"].read_bytes()


def test_saida_nao_pode_sobrescrever_pasta_da_fonte(tmp_path):
    entrada = gravar(tmp_path, amostra())
    with pytest.raises(ValueError, match="pasta de resultados"):
        gerar_relatorio(entrada, tmp_path, config=CONFIG)


def test_cli_mensagem_clara_para_erro_de_filtro(tmp_path, capsys):
    entrada = gravar(tmp_path, amostra())
    with pytest.raises(SystemExit) as erro:
        main(["--entrada", str(entrada), "--inicio", "2026-11-19"])
    assert erro.value.code == 2
    assert "fuso" in capsys.readouterr().err
