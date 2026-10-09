"""Fixtures simuladas: nenhum teste da Pessoa C acessa a rede."""
from datetime import date
from unittest.mock import Mock

import pytest
import requests

from metricas.cfr import calcular_cfr
from metricas.recuperacao import calcular_episodios, calcular_recuperacao
from pipeline.api_client import ClienteGitHub, proximo_link
from pipeline.cache import CacheJSON
from pipeline.runs import coletar, coletar_runs_repositorio, meses


def run(id, conclusao, inicio, fim=None, workflow=1, **outros):
    return {"id": id, "workflow_id": workflow, "conclusion": conclusao,
            "run_started_at": inicio, "updated_at": fim or inicio,
            "created_at": inicio, "event": "push", "head_branch": "main", **outros}


def resposta(status, dados, headers=None):
    objeto = Mock()
    objeto.status_code = status
    objeto.headers = headers or {}
    objeto.content = b"{}"
    objeto.json.return_value = dados
    objeto.text = str(dados)
    return objeto


def cliente(tmp_path, respostas, dormir=None, relogio=None):
    sessao = Mock()
    sessao.headers = {}
    sessao.get.side_effect = respostas
    return ClienteGitHub("token-falso", tmp_path, sessao=sessao,
                         dormir=dormir or (lambda _: None), relogio=relogio), sessao


def test_cache_retomada_sem_nova_requisicao(tmp_path):
    c, sessao = cliente(tmp_path, [resposta(200, {"items": [1]}, {"Link": ""})])
    assert c.get("/search/repositories", {"q": "python"}).dados == {"items": [1]}
    outro, outra_sessao = cliente(tmp_path, [])
    assert outro.get("/search/repositories", {"q": "python"}).dados == {"items": [1]}
    assert outro.acertos_cache == 1
    outra_sessao.get.assert_not_called()
    assert c.chamadas_api == 1
    assert "token-falso" not in "".join(p.read_text() for p in tmp_path.rglob("*.json"))


def test_cache_nao_armazena_erro_e_recupera_corrompido(tmp_path):
    cache = CacheJSON(tmp_path)
    cache.gravar("https://api.github.com/repos/x/y", None, 404, {"erro": 1})
    assert cache.ler("https://api.github.com/repos/x/y") is None
    arquivo = cache._caminho("https://api.github.com/repos/x/y")
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text("{invalido", encoding="utf-8")
    assert cache.ler("https://api.github.com/repos/x/y") is None


def test_status_404_403_409_sem_excecao(tmp_path):
    c, _ = cliente(tmp_path, [resposta(404, {}), resposta(403, {}), resposta(409, {})])
    assert [c.get(f"/repos/a/{i}").status for i in range(3)] == [404, 403, 409]


def test_backoff_1_2_4(tmp_path):
    esperas = []
    c, _ = cliente(tmp_path, [resposta(500, {}), resposta(502, {}),
                              resposta(503, {}), resposta(200, ["ok"])], dormir=esperas.append)
    assert c.get("/repos/a/b").dados == ["ok"]
    assert esperas == [1, 2, 4]


def test_limite_primario_espera_reset(tmp_path):
    esperas = []
    c, _ = cliente(tmp_path, [resposta(403, {}, {"X-RateLimit-Remaining": "0",
                                                    "X-RateLimit-Reset": "120"}),
                              resposta(200, [1])], dormir=esperas.append, relogio=lambda: 100)
    assert c.get("/repos/a/b").ok
    assert esperas == [21]


def test_limite_secundario_retry_after(tmp_path):
    esperas = []
    c, _ = cliente(tmp_path, [resposta(429, {"message": "secondary rate limit"},
                                       {"Retry-After": "5"}), resposta(200, [])],
                   dormir=esperas.append)
    assert c.get("/repos/a/b").ok
    assert esperas == [5]


def test_paginacao_link_e_max_paginas(tmp_path):
    url2 = 'https://api.github.com/repos/a/b/releases?per_page=1&page=2'
    r1 = resposta(200, [1], {"Link": f'<{url2}>; rel="next"'})
    c, sessao = cliente(tmp_path, [r1, resposta(200, [2])])
    assert list(c.paginar("/repos/a/b/releases", {"per_page": 1})) == [1, 2]
    assert sessao.get.call_count == 2
    assert proximo_link(f'<{url2}>; rel="next"') == url2
    assert list(c.paginar("/repos/a/b/releases", {"per_page": 1}, max_paginas=1)) == [1]


def test_paginacao_chave_e_erro(tmp_path):
    c, _ = cliente(tmp_path, [resposta(200, {"workflow_runs": [1, 2]})])
    assert list(c.paginar("/repos/a/b/actions/runs", chave="workflow_runs")) == [1, 2]
    c2, _ = cliente(tmp_path / "novo", [resposta(404, {})])
    with pytest.raises(RuntimeError, match="404"):
        list(c2.paginar("/repos/a/b/actions/runs"))


def test_cfr_conclusoes_validas():
    assert calcular_cfr([{"conclusion": x} for x in
                         ["success", "failure", "timed_out", "startup_failure", "cancelled", None]]) == 0.75
    assert calcular_cfr([{"conclusion": "cancelled"}]) is None
    assert calcular_cfr([]) is None


def test_recuperacao_uma_hora_e_vinte_cancelado_ignorado():
    runs = [run(1, "success", "2026-01-01T09:00:00Z"),
            run(2, "failure", "2026-01-01T10:00:00Z"),
            run(3, "cancelled", "2026-01-01T10:20:00Z"),
            run(4, "success", "2026-01-01T11:00:00Z", "2026-01-01T11:20:00Z")]
    assert calcular_recuperacao(runs) == pytest.approx(4 / 3)
    assert calcular_episodios(runs)[0]["censurado"] is False


def test_recuperacao_censurada_e_separada_por_workflow():
    runs = [run(1, "success", "2026-01-01T09:00:00Z"),
            run(2, "failure", "2026-01-01T10:00:00Z"),
            run(3, "success", "2026-01-01T11:00:00Z", workflow=2)]
    episodios = calcular_episodios(runs)
    assert len(episodios) == 1 and episodios[0]["censurado"]
    assert calcular_recuperacao(runs) is None


def test_meses_parciais():
    assert list(meses(date(2026, 1, 30), date(2026, 3, 2))) == [
        (date(2026, 1, 30), date(2026, 1, 31)),
        (date(2026, 2, 1), date(2026, 2, 28)),
        (date(2026, 3, 1), date(2026, 3, 2))]


def test_coleta_filtro_runs_e_csv(tmp_path, cliente_falso):
    caminho = "/repos/org/proj/actions/runs"
    dados = [run(1, "success", "2026-01-01T09:00:00Z"),
             run(2, "failure", "2026-01-01T10:00:00Z"),
             run(3, "success", "2026-01-01T11:00:00Z", "2026-01-01T11:20:00Z"),
             run(4, "cancelled", "2026-01-01T12:00:00Z")]
    from conftest import Resposta
    falso = cliente_falso({caminho: Resposta(200, {"total_count": 4, "workflow_runs": dados})},
                          {caminho: [{"workflow_runs": dados}]})
    config = {"janela": {"inicio": date(2026, 1, 1), "fim": date(2026, 1, 31)},
              "saida": {"dir": tmp_path}}
    resultado = coletar(falso, [{"full_name": "org/proj", "default_branch": "main"}], config)
    assert len(resultado["runs"]) == 3
    assert resultado["metricas_ci"][0]["cfr_a"] == pytest.approx(1 / 3)
    assert resultado["metricas_ci"][0]["recuperacao_mediana_horas"] == pytest.approx(4 / 3)
    assert (tmp_path / "runs.csv").exists()
    assert (tmp_path / "metricas_ci.csv").exists()
    assert (tmp_path / "episodios_recuperacao.csv").exists()


def test_mes_saturado_subdivide(tmp_path, cliente_falso):
    from conftest import Resposta
    caminho = "/repos/org/proj/actions/runs"
    chamadas = []
    def rota(params):
        chamadas.append(params["created"])
        if params["created"] == "2026-01-01..2026-01-02":
            return Resposta(200, {"total_count": 1000, "workflow_runs": []})
        return Resposta(200, {"total_count": 0, "workflow_runs": []})
    falso = cliente_falso({caminho: rota}, {caminho: lambda params: [{"workflow_runs": []}]})
    assert coletar_runs_repositorio(falso, "org/proj", "main", date(2026, 1, 1),
                                   date(2026, 1, 2)) == []
    assert "2026-01-01..2026-01-01" in chamadas
    assert "2026-01-02..2026-01-02" in chamadas


def test_mes_saturado_no_dia_falha(tmp_path, cliente_falso):
    from conftest import Resposta
    caminho = "/repos/org/proj/actions/runs"
    falso = cliente_falso({caminho: Resposta(200, {"total_count": 1000, "workflow_runs": []})})
    with pytest.raises(RuntimeError, match="1000"):
        coletar_runs_repositorio(falso, "org/proj", "main", date(2026, 1, 1),
                                 date(2026, 1, 1))
