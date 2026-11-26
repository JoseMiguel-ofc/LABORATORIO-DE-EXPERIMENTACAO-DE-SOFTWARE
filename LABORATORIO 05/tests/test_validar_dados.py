import csv

import numpy as np
import pandas as pd
import pytest

from coleta.coletar import COLUNAS, carregar_config
from scripts import validar_dados

CONFIG = carregar_config()
ENDPOINTS = [CONFIG["usuarios_online"]["nome"]] + [e["nome"] for e in CONFIG["endpoints"]]


def gerar_csv(caminho, dias=8, pular=(), atraso_min=2, falhas_em=(), semente=1):
    """Uma rodada por horário a partir de segunda 2026-11-02 00:17 UTC."""
    rng = np.random.default_rng(semente)
    inicio = pd.Timestamp("2026-11-02 00:17", tz="UTC")
    linhas = []
    for h in range(dias * 24):
        if h in pular:
            continue
        t = inicio + pd.Timedelta(hours=h, minutes=atraso_min)
        for endpoint in ENDPOINTS:
            falhou = h in falhas_em
            linhas.append({
                "timestamp": t.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "endpoint": endpoint, "status": "" if falhou else 200,
                "latencia_ms": f"{rng.lognormal(np.log(150), 0.3):.1f}",
                "usuarios_online": 30000000, "erro": "Timeout" if falhou else "",
                "jogadores_top": 1800000})
            t += pd.Timedelta(seconds=1.2)
    with open(caminho, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(linhas)
    return caminho


@pytest.fixture
def csv_bom(tmp_path):
    return gerar_csv(tmp_path / "coleta.csv", pular=(30, 31, 32, 100))


def test_dados_bons_passam_e_contam_puladas(csv_bom):
    rel = validar_dados.validar(csv_bom)
    texto = rel.markdown()
    assert rel.erros == []
    assert "execuções puladas: 4**" in texto
    assert "Maior sequência de horários seguidos sem coleta: 3 h" in texto
    assert "188 de 192 horários com dados" in texto
    assert "Outliers de latência" in texto


def test_pico_e_janela_seguem_a_proposta(csv_bom):
    cobertura = validar_dados.validar(csv_bom).cobertura
    assert cobertura["pico"].sum() == 8 * 8          # 14h-22h UTC, 8 dias
    # Terça 03/11 15h-18h em Los Angeles (PST) = 23:17, 00:17 e 01:17 UTC.
    janela = cobertura.loc[cobertura["janela_manutencao"], "horario_utc"]
    assert list(janela.dt.strftime("%m-%d %H:%M")) == ["11-03 23:17", "11-04 00:17",
                                                       "11-04 01:17"]


def test_atraso_e_rodadas_extras(tmp_path):
    caminho = gerar_csv(tmp_path / "c.csv", dias=2, atraso_min=40)
    texto = validar_dados.validar(caminho).markdown()
    assert "acima de 30 min: 48" in texto
    df = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    extra = df.head(7).copy()
    extra["timestamp"] = extra["timestamp"].str.replace("00:57", "01:10")
    pd.concat([df, extra]).to_csv(tmp_path / "e.csv", index=False, lineterminator="\n")
    assert "(ex.: disparo manual): 1" in validar_dados.validar(tmp_path / "e.csv").markdown()


def test_rodada_toda_com_falha_e_apontada(tmp_path):
    caminho = gerar_csv(tmp_path / "c.csv", dias=1, falhas_em=(5,))
    rel = validar_dados.validar(caminho)
    assert rel.erros == []
    assert "tudo falhou (provável problema do runner, não da Steam): 1" in rel.markdown()


def test_reprova_duplicatas_colunas_e_status_sem_erro(tmp_path, csv_bom):
    df = pd.read_csv(csv_bom, dtype=str, keep_default_na=False)
    pd.concat([df, df.head(3)]).to_csv(tmp_path / "dup.csv", index=False)
    assert any("repetem timestamp e endpoint" in e
               for e in validar_dados.validar(tmp_path / "dup.csv").erros)

    df.drop(columns=["erro"]).to_csv(tmp_path / "col.csv", index=False)
    assert any("colunas ausentes: erro" in e
               for e in validar_dados.validar(tmp_path / "col.csv").erros)

    sem = df.copy()
    sem.loc[0, "status"] = ""
    sem.to_csv(tmp_path / "st.csv", index=False)
    assert any("sem status HTTP" in e for e in validar_dados.validar(tmp_path / "st.csv").erros)

    ruim = df.copy()
    ruim.loc[0, "timestamp"] = "ontem"
    ruim.to_csv(tmp_path / "ts.csv", index=False)
    assert any("ilegíveis" in e for e in validar_dados.validar(tmp_path / "ts.csv").erros)


def test_data_de_corte_conta_horarios_ate_o_fim_do_dia(csv_bom):
    texto = validar_dados.validar(csv_bom, ate="2026-11-03").markdown()
    # 02/11 00:17 até 03/11 23:17 = 48 horários; pulados 30, 31 e 32.
    assert "45 de 48 horários com dados" in texto


def test_main_grava_relatorio_e_cobertura(tmp_path, csv_bom):
    saida = tmp_path / "val"
    assert validar_dados.main(["--csv", str(csv_bom), "--saida", str(saida)]) == 0
    assert (saida / "relatorio_validacao.md").read_text(encoding="utf-8").startswith(
        "# Relatório de validação")
    cobertura = pd.read_csv(saida / "cobertura_por_horario.csv")
    assert len(cobertura) == 192 and cobertura["coletado"].sum() == 188
    assert validar_dados.main(["--csv", str(tmp_path / "nao_existe.csv")]) == 1
