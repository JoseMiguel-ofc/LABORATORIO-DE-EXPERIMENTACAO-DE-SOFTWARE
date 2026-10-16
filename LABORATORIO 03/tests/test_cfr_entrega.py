"""Integração offline: config + CSV/gzip -> CFR, previsões e manifesto."""

import csv
import gzip
import json

import pytest
import requests
import yaml

from pipeline.cfr_entrega import calcular_tabelas, main


def salvar_csv(caminho, linhas, campos):
    abrir = gzip.open if caminho.suffix == ".gz" else open
    with abrir(caminho, "wt", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(linhas)


def ler_csv(caminho):
    with caminho.open(newline="", encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


@pytest.fixture
def coleta(tmp_path, monkeypatch):
    def sem_rede(*args, **kwargs):
        pytest.fail("O cálculo de CFR a partir dos CSVs não deve acessar a rede")

    monkeypatch.setattr(requests.sessions.Session, "request", sem_rede)
    pasta = tmp_path / "dados"
    pasta.mkdir()
    releases = [
        {"full_name": "o/r", "tag_name": "v2.3.0", "published_at": "2026-01-01T00:00:00Z",
         "draft": False, "prerelease": False, "commits_status": "primeira_release", "commits_novos": ""},
        {"full_name": "o/r", "tag_name": "v2.3.1", "published_at": "2026-01-03T00:00:00Z",
         "draft": False, "prerelease": False, "commits_status": "ok", "commits_novos": 1},
        {"full_name": "o/r", "tag_name": "v2.4.0", "published_at": "2026-01-29T00:00:00Z",
         "draft": False, "prerelease": False, "commits_status": "sem_commits", "commits_novos": 0},
    ]
    salvar_csv(pasta / "releases.csv", releases, list(releases[0]))
    salvar_csv(pasta / "commits.csv.gz", [{
        "full_name": "o/r", "tag_name": "v2.3.1", "sha": "abc", "message": "fix: corrigir defeito",
    }], ["full_name", "tag_name", "sha", "message"])
    salvar_csv(pasta / "metricas_entrega.csv", [
        {"full_name": "o/r", "releases_status": "ok"},
        {"full_name": "o/inacessivel", "releases_status": "http_404"},
    ], ["full_name", "releases_status"])
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({"janela": {"inicio": "2026-01-01", "fim": "2026-01-31"},
                                      "saida": {"dir": "dados"}, "heuristica": {"versao": "v1"}}))
    return config, pasta


def test_cli_usa_gzip_e_registra_censura_falha_e_hashes(coleta):
    config, pasta = coleta
    assert main(["--config", str(config)]) == 0
    resumo = {r["full_name"]: r for r in ler_csv(pasta / "metricas_cfr_b.csv")}
    assert float(resumo["o/r"]["cfr_b"]) == .5
    assert resumo["o/r"]["denominador"] == "2"
    assert resumo["o/r"]["censuradas"] == "1"
    assert resumo["o/inacessivel"]["cfr_b"] == ""
    assert resumo["o/inacessivel"]["coleta_status"] == "http_404"
    previsoes = {r["tag_name"]: r for r in ler_csv(pasta / "previsoes_cfr_b.csv")}
    assert previsoes["v2.3.0"]["falhou"] == "True"
    assert previsoes["v2.3.1"]["corretiva"] == "True"
    assert previsoes["v2.4.0"]["censurada"] == "True"
    manifesto = json.loads((pasta / "cfr_b_execucao.json").read_text())
    assert manifesto["repositorios"] == 2
    assert manifesto["versao"] == "v1"
    assert all(len(f["sha256"]) == 64 for f in manifesto["fontes"])
    assert manifesto["definicao"]["validada"] is False


def test_cli_aceita_caminhos_explicitos_e_versao(coleta, tmp_path):
    config, pasta = coleta
    destino = tmp_path / "resultado"
    assert main(["--config", str(config), "--releases", str(pasta / "releases.csv"),
                 "--commits", str(pasta / "commits.csv.gz"), "--metricas-entrega",
                 str(pasta / "metricas_entrega.csv"), "--saida", str(destino), "--versao", "v2"]) == 0
    assert all(r["heuristica_versao"] == "v2" for r in ler_csv(destino / "metricas_cfr_b.csv"))


def test_cli_rejeita_sobrescrever_entrada(coleta):
    config, pasta = coleta
    fonte = pasta / "metricas_cfr_b.csv"
    fonte.write_bytes((pasta / "releases.csv").read_bytes())
    anterior = fonte.read_bytes()
    with pytest.raises(SystemExit) as erro:
        main(["--config", str(config), "--releases", str(fonte)])
    assert erro.value.code == 2
    assert fonte.read_bytes() == anterior


def test_cli_arquivo_ausente_nao_gera_resultado(coleta):
    config, pasta = coleta
    (pasta / "commits.csv.gz").unlink()
    with pytest.raises(SystemExit) as erro:
        main(["--config", str(config)])
    assert erro.value.code == 2
    assert not (pasta / "metricas_cfr_b.csv").exists()


def test_metadados_duplicados_e_repo_ausente_sao_rejeitados():
    with pytest.raises(ValueError, match="duplicado"):
        calcular_tabelas([], "2026-01-01", "2026-01-31", metadados=[
            {"full_name": "o/r"}, {"full_name": "o/r"}])
    with pytest.raises(ValueError, match="sem full_name"):
        calcular_tabelas([{}], "2026-01-01", "2026-01-31")
