"""Casos controlados do piloto: nenhuma requisição de rede é realizada."""
import csv
import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from analise.piloto import COLUNAS, analisar_piloto, carregar_dados, gerar_relatorio, main


CONFIG = {"usuarios_online": {"nome": "ValveStats"},
          "endpoints": [{"nome": "ServicoA"}, {"nome": "ServicoB"}]}


def linha(timestamp="2026-11-19T19:17:00Z", endpoint="ServicoA", status="200",
          latencia_ms="100", usuarios_online="30000000", erro="", jogadores_top="1000000"):
    return dict(zip(COLUNAS, (timestamp, endpoint, status, latencia_ms,
                             usuarios_online, erro, jogadores_top)))


def salvar(tmp_path, linhas):
    caminho = tmp_path / "coleta.csv"
    with caminho.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
        escritor.writeheader()
        escritor.writerows(linhas)
    return caminho


def analisar(tmp_path, linhas, horas=48):
    return analisar_piloto(carregar_dados(salvar(tmp_path, linhas), config=CONFIG),
                           horas=horas, config=CONFIG)


def test_rodada_unica_parcial_sem_replicar_populacao(tmp_path):
    linhas = [linha(endpoint=x) for x in ("ValveStats", "ServicoA", "ServicoB")]
    resultado = analisar(tmp_path, linhas)
    resumo = resultado["resumo_endpoints"].set_index("endpoint")
    assert list(resumo.index) == ["ServicoA", "ServicoB"]
    assert resumo["medicoes"].to_list() == [1, 1]
    assert resumo["latencia_dp_ms"].isna().all()
    assert resumo["latencia_p50_ms"].to_list() == [100, 100]
    assert resultado["metadados"]["status"] == "parcial"
    assert resultado["metadados"]["intervalos_horarios_com_dados"] == 1
    assert resultado["metadados"]["cobertura_horaria_pct"] == pytest.approx(100 / 48)
    assert len(resultado["usuarios_por_hora"]) == 1
    assert resultado["usuarios_por_hora"].iloc[0]["usuarios_online"] == 30_000_000


def test_falhas_nao_contaminam_latencia_sucesso_e_http_difere_operacional(tmp_path):
    linhas = [linha(latencia_ms="10"),
              linha("2026-11-19T20:17:00Z", latencia_ms="30"),
              linha("2026-11-19T21:17:00Z", status="", latencia_ms="15000", erro="Timeout"),
              linha("2026-11-19T22:17:00Z", status="503", latencia_ms="999", erro="HTTP 503"),
              linha("2026-11-19T23:17:00Z", status="200", latencia_ms="200", erro="resposta sem player_count")]
    r = analisar(tmp_path, linhas)["resumo_endpoints"].iloc[0]
    assert r["medicoes"] == 5
    assert r["sucessos_operacionais"] == 2
    assert r["falhas_operacionais"] == 3
    assert r["disponibilidade_http_observada_pct"] == 60
    assert r["sucesso_operacional_observado_pct"] == 40
    assert r["latencias_sucesso_validas"] == 2
    assert r["latencia_media_ms"] == 20
    assert r["latencia_p50_ms"] == 20
    assert r["latencia_p25_ms"] == 15
    assert r["latencia_p75_ms"] == 25
    assert r["latencia_iqr_ms"] == 10
    assert r["latencia_p95_ms"] == 29
    assert r["latencia_dp_ms"] == pytest.approx(np.sqrt(200))


@pytest.mark.parametrize("horas", [24, 48])
def test_janela_semiaberta_ancorada_no_primeiro_timestamp(tmp_path, horas):
    inicio = pd.Timestamp("2026-11-19T19:17:00Z")
    linhas = [linha(inicio.isoformat()),
              linha((inicio + pd.Timedelta(hours=horas) - pd.Timedelta(milliseconds=1)).isoformat()),
              linha((inicio + pd.Timedelta(hours=horas)).isoformat())]
    resultado = analisar(tmp_path, linhas, horas)
    assert resultado["resumo_endpoints"].iloc[0]["medicoes"] == 2
    assert resultado["metadados"]["linhas_fora_da_janela"] == 1
    assert resultado["metadados"]["janela_fim_exclusivo_utc"] == (
        inicio + pd.Timedelta(hours=horas)).isoformat().replace("+00:00", "Z")


def test_intervalos_relativos_nao_confundem_horas_calendario(tmp_path):
    resultado = analisar(tmp_path, [linha("2026-11-19T19:59:59Z"),
                                   linha("2026-11-19T20:00:01Z")], 24)
    m = resultado["metadados"]
    assert m["horas_calendario_utc_com_dados"] == 2
    assert m["intervalos_horarios_com_dados"] == 1
    assert m["cobertura_horaria_pct"] == pytest.approx(100 / 24)


def test_timestamps_com_offsets_equivalentes_sao_utc_e_deduplicados(tmp_path):
    resultado = analisar(tmp_path, [linha("2026-11-19T16:17:00-03:00"),
                                   linha("2026-11-19T19:17:00Z", latencia_ms="999")])
    assert resultado["resumo_endpoints"].iloc[0]["medicoes"] == 1
    assert resultado["resumo_endpoints"].iloc[0]["latencia_p50_ms"] == 100
    assert resultado["metadados"]["diagnostico_entrada"]["duplicatas_excluidas"] == 1
    assert resultado["metadados"]["diagnostico_entrada"]["pares_duplicados_com_valores_divergentes"] == 1
    assert resultado["metadados"]["janela_inicio_inclusivo_utc"] == "2026-11-19T19:17:00Z"


@pytest.mark.parametrize("timestamp", ["2026-11-19T19:17:00", "2026-11-19", "", "ontem"])
def test_naive_e_timestamp_invalido_rejeitados(tmp_path, timestamp):
    with pytest.raises(ValueError, match="timestamp"):
        carregar_dados(salvar(tmp_path, [linha(timestamp)]), config=CONFIG)


def test_header_only_e_endpoints_sem_medicao_nao_viram_zero_de_disponibilidade(tmp_path):
    resultado = analisar(tmp_path, [])
    resumo = resultado["resumo_endpoints"]
    assert len(resumo) == 2
    assert resumo["medicoes"].eq(0).all()
    assert resumo["sucesso_operacional_observado_pct"].isna().all()
    assert resumo["latencia_p50_ms"].isna().all()
    assert resultado["usuarios_por_hora"].empty
    assert resultado["metadados"]["status"] == "parcial"
    assert resultado["metadados"]["janela_inicio_inclusivo_utc"] is None


def test_valores_ausentes_invalidos_sem_imputacao(tmp_path):
    linhas = [linha(latencia_ms="", usuarios_online="", jogadores_top=""),
              linha("2026-11-19T20:17:00Z", latencia_ms="-1", status="700"),
              linha("2026-11-19T21:17:00Z", latencia_ms="inf", status="abc"),
              linha("2026-11-19T22:17:00Z", latencia_ms="abc", usuarios_online="-2"),
              linha("2026-11-19T23:17:00Z", latencia_ms="0", usuarios_online="30.5")]
    resultado = analisar(tmp_path, linhas)
    r = resultado["resumo_endpoints"].iloc[0]
    assert r["latencias_ausentes_ou_invalidas"] == 4
    assert r["latencias_sucesso_validas"] == 1
    assert r["latencia_p50_ms"] == 0
    assert r["usuarios_online_ausentes"] == 3
    assert resultado["metadados"]["diagnostico_entrada"]["status_ausentes_ou_invalidos"] == 2


def test_denominador_so_classificaveis_sem_converter_dados_invalidos_em_falhas(tmp_path):
    inicio = pd.Timestamp("2026-11-19T19:17:00Z")
    casos = [("200", ""), ("302", ""), ("503", "HTTP 503"), ("", "Timeout"),
             ("", ""), ("700", ""), ("abc", ""), ("101", "")]
    linhas = [linha((inicio + pd.Timedelta(hours=i)).isoformat(), status=status, erro=erro)
              for i, (status, erro) in enumerate(casos)]
    resultado = analisar(tmp_path, linhas)
    r = resultado["resumo_endpoints"].iloc[0]
    assert r["medicoes"] == 8
    assert r["tentativas_classificaveis"] == 4
    assert r["tentativas_nao_classificaveis"] == 4
    assert r["sucessos_operacionais"] == 2
    assert r["falhas_operacionais"] == 2
    assert r["sucesso_operacional_observado_pct"] == 50
    assert r["disponibilidade_http_observada_pct"] == 50
    assert resultado["metadados"]["tentativas_nao_classificaveis_na_janela"] == 4


def test_sem_classificacao_nao_estima_taxa_nem_conta_falhas(tmp_path):
    resultado = analisar(tmp_path, [linha(status="", erro="")])
    r = resultado["resumo_endpoints"].iloc[0]
    assert r["medicoes"] == 1
    assert r["tentativas_classificaveis"] == 0
    assert r["tentativas_nao_classificaveis"] == 1
    assert r["falhas_operacionais"] == 0
    assert np.isnan(r["sucesso_operacional_observado_pct"])
    assert np.isnan(r["disponibilidade_http_observada_pct"])


def test_duplicata_identica_nao_sinaliza_conflito(tmp_path):
    resultado = analisar(tmp_path, [linha(), linha()])
    diagnostico = resultado["metadados"]["diagnostico_entrada"]
    assert diagnostico["duplicatas_excluidas"] == 1
    assert diagnostico["pares_duplicados_com_valores_divergentes"] == 0


def test_endpoint_desconhecido_diagnosticado_sem_contaminar_estatisticas(tmp_path):
    resultado = analisar(tmp_path, [linha(), linha(endpoint="Outro", usuarios_online="99999999")])
    assert resultado["resumo_endpoints"]["medicoes"].sum() == 1
    assert resultado["metadados"]["diagnostico_entrada"]["endpoints_desconhecidos"] == ["Outro"]
    assert resultado["usuarios_por_hora"].iloc[0]["usuarios_online"] == 30_000_000


def test_populacao_prefere_consulta_auxiliar_e_reporta_conflito(tmp_path):
    resultado = analisar(tmp_path, [linha(usuarios_online="100"),
                                   linha("2026-11-19T19:17:01Z", endpoint="ValveStats", usuarios_online="200"),
                                   linha("2026-11-19T19:17:02Z", endpoint="ServicoB", usuarios_online="200")])
    assert len(resultado["usuarios_por_hora"]) == 1
    assert resultado["usuarios_por_hora"].iloc[0]["usuarios_online"] == 200
    assert resultado["metadados"]["horas_com_contagens_usuarios_conflitantes"] == 1


def test_apos_24h_repetidas_piloto_disponivel_com_lacunas_explicitas(tmp_path):
    linhas = [linha(timestamp, endpoint=endpoint) for timestamp in (
        "2026-11-19T19:17:00Z", "2026-11-20T19:17:00Z")
        for endpoint in ("ServicoA", "ServicoB")]
    resultado = analisar(tmp_path, linhas)
    assert resultado["metadados"]["status"] == "disponivel_para_inspecao"
    assert resultado["metadados"]["cobertura_horaria_pct"] == pytest.approx(2 / 48 * 100)


def test_arquivo_incompativel_falha_clara(tmp_path):
    caminho = tmp_path / "invalido.csv"
    caminho.write_text("timestamp,endpoint\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Colunas obrigatórias"):
        carregar_dados(caminho, config=CONFIG)


def test_gerar_relatorio_preserva_bruto_e_grava_artefatos_auditaveis(tmp_path):
    entrada = salvar(tmp_path, [linha()])
    antes = entrada.read_bytes()
    caminhos = gerar_relatorio(entrada, tmp_path / "saida", config=CONFIG)
    assert entrada.read_bytes() == antes
    assert set(caminhos) == {"resumo_endpoints", "usuarios_por_hora", "grafico", "metadados"}
    assert caminhos["grafico"].read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    metadados = json.loads(caminhos["metadados"].read_text())
    assert metadados["sha256_csv"] == hashlib.sha256(antes).hexdigest()
    assert metadados["status"] == "parcial"
    assert metadados["versoes"]["matplotlib"]
    assert len(metadados["sha256_codigo_piloto"]) == 64
    assert len(metadados["sha256_configuracao"]) == 64
    for nome, sha in metadados["sha256_artefatos"].items():
        assert sha == hashlib.sha256(caminhos[nome].read_bytes()).hexdigest()


def test_relatorio_header_only_tambem_gera_png(tmp_path):
    caminhos = gerar_relatorio(salvar(tmp_path, []), tmp_path / "saida", config=CONFIG)
    assert caminhos["grafico"].stat().st_size > 1_000


def test_series_de_um_ponto_usam_janela_de_uma_hora(tmp_path, monkeypatch):
    import matplotlib.pyplot as plt
    import analise.piloto as piloto

    resultado = analisar(tmp_path, [linha()])
    figuras = []
    fechar = plt.close
    monkeypatch.setattr(plt, "close", lambda figura: figuras.append(figura)
                        if hasattr(figura, "axes") else None)
    piloto._grafico(resultado, tmp_path / "um_ponto.png")
    figura = figuras[-1]
    for eixo in figura.axes[2:]:
        inicio, fim = eixo.get_xlim()
        assert (fim - inicio) * 24 == pytest.approx(1)
    fechar(figura)


def test_cli_piloto_parcial_sai_com_sucesso(tmp_path, capsys):
    entrada = salvar(tmp_path, [linha()])
    config = tmp_path / "config.json"
    config.write_text(json.dumps(CONFIG), encoding="utf-8")
    assert main(["--entrada", str(entrada), "--saida", str(tmp_path / "saida"),
                 "--config", str(config), "--horas", "24"]) == 0
    assert "Piloto: parcial" in capsys.readouterr().out


def test_horas_nao_planejadas_rejeitadas(tmp_path):
    with pytest.raises(ValueError, match="24 ou 48"):
        analisar(tmp_path, [], horas=12)
