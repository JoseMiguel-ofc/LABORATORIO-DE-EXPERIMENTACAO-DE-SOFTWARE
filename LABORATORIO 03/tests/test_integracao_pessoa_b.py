"""Executa a CLI com a interface da Pessoa C simulada, sem acessar o GitHub."""

import csv
from datetime import date, datetime, timedelta, timezone
import sys
from types import SimpleNamespace

import pytest
import requests
import yaml

from conftest import Resposta
from pipeline.__main__ import main


def ler_csv(caminho):
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


def configuracao(tmp_path):
    config = {
        "github": {"token_env": "LAB03_TOKEN_TESTE"},
        "janela": {"inicio": date(2025, 10, 1), "fim": date(2026, 9, 30)},
        "busca": {"faixas_estrelas": [{"min": 1001, "max": 2000}]},
        "filtros": {"releases": 5, "runs": 50},
        "amostra": {"tamanho": 1, "semente": 42},
        "saida": {"dir": "dados", "cache_dir": "dados/cache"},
    }
    caminho = tmp_path / "config.yaml"
    caminho.write_text(yaml.safe_dump(config), encoding="utf-8")
    return caminho


def test_cli_integra_selecao_releases_commits_e_metricas_sprint1(
        tmp_path, monkeypatch, cliente_falso):
    def proibir_rede(*args, **kwargs):
        pytest.fail("O teste de integração não deve acessar a rede")

    monkeypatch.setattr(requests.sessions.Session, "request", proibir_rede)
    caminho = configuracao(tmp_path)
    monkeypatch.setenv("LAB03_TOKEN_TESTE", "token-ficticio-do-teste")
    repo = {"full_name": "teste/projeto", "stargazers_count": 1500, "language": "Python",
            "created_at": "2020-01-01T00:00:00Z", "default_branch": "main",
            "html_url": "https://github.com/teste/projeto"}
    sequencia = [("v1.0.0", "2025-09-15"), ("v1.1.0", "2025-10-01"),
                 ("v1.1.1", "2025-10-03"), ("v1.2.0", "2025-10-10"),
                 ("v1.3.0", "2025-10-15"), ("v1.4.0", "2025-10-25")]
    releases = [{"id": i, "tag_name": tag, "published_at": dia + "T12:00:00Z",
                 "draft": False, "prerelease": False}
                for i, (tag, dia) in enumerate(sequencia)]
    prefixo = "/repos/teste/projeto"
    rotas = {
        "/search/repositories": Resposta(200, {"total_count": 1}),
        prefixo + "/actions/workflows": Resposta(200, {"total_count": 1}),
        prefixo + "/actions/runs": lambda p: Resposta(
            200, {"total_count": 50 if p["status"] == "success" else 0}),
        prefixo + "/contributors": Resposta(200, [{}]),
        prefixo + "/releases": Resposta(200, releases),
        prefixo + "/tags": Resposta(200, []),
    }
    for anterior, atual in zip(releases, releases[1:]):
        quando = datetime.fromisoformat(atual["published_at"].replace("Z", "+00:00"))
        data = (quando - timedelta(days=1)).astimezone(timezone.utc).isoformat()
        commit = {"sha": "sha-" + atual["tag_name"], "commit": {
            "message": "fix: falha" if atual["tag_name"] == "v1.1.1" else "feat: recurso",
            "author": {"date": data}, "committer": {"date": data}}}
        rota = prefixo + f'/compare/{anterior["tag_name"]}...{atual["tag_name"]}'
        rotas[rota] = Resposta(200, {"commits": [commit], "total_commits": 1})
    cliente = cliente_falso(rotas, {
        "/search/repositories": [{"items": [repo]}],
        prefixo + "/releases": [releases], prefixo + "/tags": [[]],
    })
    cliente.chamadas_api, cliente.acertos_cache = 0, 0
    modulo_simulado = SimpleNamespace(ClienteGitHub=lambda token, cache_dir: cliente)
    monkeypatch.setitem(sys.modules, "pipeline.api_client", modulo_simulado)

    main(["--config", str(caminho)])

    saida = tmp_path / "dados"
    metrica, = ler_csv(saida / "metricas_entrega.csv")
    assert float(metrica["frequencia_releases_semana"]) == pytest.approx(5 / (365 / 7))
    assert float(metrica["lead_time_a_horas"]) == 24
    assert float(metrica["lead_time_b_horas"]) == 24
    assert int(metrica["releases_com_lead_time"]) == 5
    assert int(metrica["releases_compare_404"]) == 0
    assert len(ler_csv(saida / "commits.csv")) == 5
    assert len(ler_csv(saida / "repositorios.csv")) == 1
    assert ler_csv(saida / "descartes.csv") == []
    assert ler_csv(saida / "funil.csv")[-1]["restantes"] == "1"
    assert {arquivo.name for arquivo in saida.glob("*.csv")} == {
        "candidatos.csv", "repositorios.csv", "descartes.csv", "funil.csv",
        "releases.csv", "tags.csv", "commits.csv", "metricas_entrega.csv",
    }


def test_cli_explica_dependencia_da_pessoa_c(tmp_path, monkeypatch):
    caminho = configuracao(tmp_path)
    monkeypatch.setenv("LAB03_TOKEN_TESTE", "token-ficticio-do-teste")
    monkeypatch.setitem(sys.modules, "pipeline.api_client", None)
    with pytest.raises(SystemExit, match=r"falta pipeline/api_client.py \(Pessoa C\)"):
        main(["--config", str(caminho)])
