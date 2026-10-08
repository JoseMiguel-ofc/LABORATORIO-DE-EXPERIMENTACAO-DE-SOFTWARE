import pytest

from conftest import Resposta, link
from pipeline.commits import coletar_commits_entre_releases


CAMINHO = "/repos/o/r/compare/v1...v2"


def commit(numero):
    return {"sha": f"sha{numero}", "commit": {"message": f"fix {numero}",
            "committer": {"date": "2026-01-01T00:00:00Z"},
            "author": {"date": "2025-12-31T00:00:00Z"}}}


def test_compare_paginado_supera_250_commits(cliente_falso):
    def pagina(params):
        n = params["page"]
        assert params["per_page"] == 100
        commits = [commit(i) for i in range((n - 1) * 100, min(n * 100, 301))]
        return Resposta(200, {"total_commits": 301, "commits": commits},
                        link(CAMINHO, next=n + 1) if n < 4 else "")
    cliente = cliente_falso({CAMINHO: pagina})
    resultado = coletar_commits_entre_releases(cliente, "o/r", "v1", "v2")
    assert resultado["status"] == "ok"
    assert len(resultado["commits"]) == 301
    assert resultado["commits"][-1]["sha"] == "sha300"
    assert resultado["commits"][0]["message"] == "fix 0"
    assert [p["page"] for _, p in cliente.chamadas] == [1, 2, 3, 4]


def test_total_commits_evitaria_truncamento_mesmo_sem_link(cliente_falso):
    cliente = cliente_falso({CAMINHO: lambda p: Resposta(200, {
        "total_commits": 2, "commits": [commit(p["page"])]})})
    assert len(coletar_commits_entre_releases(cliente, "o/r", "v1", "v2")["commits"]) == 2


@pytest.mark.parametrize("status", [404, 403, 409, 500])
def test_erro_http_e_ausencia_nao_lista_vazia(cliente_falso, status):
    cliente = cliente_falso({CAMINHO: Resposta(status, {"message": "erro"})})
    assert coletar_commits_entre_releases(cliente, "o/r", "v1", "v2") == {
        "commits": None, "status": f"http_{status}", "http_status": status}


def test_erro_na_segunda_pagina_descarta_primeira_pagina(cliente_falso):
    cliente = cliente_falso({CAMINHO: lambda p: (
        Resposta(200, {"total_commits": 2, "commits": [commit(1)]}, link(CAMINHO, next=2))
        if p["page"] == 1 else Resposta(404, {}))})
    resultado = coletar_commits_entre_releases(cliente, "o/r", "v1", "v2")
    assert resultado["commits"] is None and resultado["status"] == "http_404"


def test_sem_commits_novos_e_comparacao_completa(cliente_falso):
    cliente = cliente_falso({CAMINHO: Resposta(200, {"total_commits": 0, "commits": []})})
    resultado = coletar_commits_entre_releases(cliente, "o/r", "v1", "v2")
    assert resultado["commits"] == [] and resultado["status"] == "sem_commits"


def test_deduplica_sha_entre_paginas(cliente_falso):
    cliente = cliente_falso({CAMINHO: lambda p: Resposta(200, {
        "total_commits": 2, "commits": [commit(1)] if p["page"] == 1 else [commit(1), commit(2)]})})
    assert len(coletar_commits_entre_releases(cliente, "o/r", "v1", "v2")["commits"]) == 2


def test_paginacao_que_repete_pagina_e_rejeitada(cliente_falso):
    cliente = cliente_falso({CAMINHO: Resposta(200, {"total_commits": 3, "commits": [commit(1)]})})
    resultado = coletar_commits_entre_releases(cliente, "o/r", "v1", "v2")
    assert resultado["status"] == "paginacao_incompleta"
    assert resultado["commits"] is None
    assert len(cliente.chamadas) == 2


def test_link_circular_e_rejeitado(cliente_falso):
    cliente = cliente_falso({CAMINHO: Resposta(200, {"commits": [commit(1)]}, link(CAMINHO, next=1))})
    assert coletar_commits_entre_releases(cliente, "o/r", "v1", "v2")["status"] == "paginacao_incompleta"


@pytest.mark.parametrize("dados", [[], {}, {"commits": [{}]}, {"commits": None}])
def test_dados_invalidos(cliente_falso, dados):
    cliente = cliente_falso({CAMINHO: Resposta(200, dados)})
    assert coletar_commits_entre_releases(cliente, "o/r", "v1", "v2")["status"] == "dados_invalidos"


def test_tags_com_barra_sao_codificadas_e_ausentes_nao_consultam(cliente_falso):
    cliente = cliente_falso({"/repos/o/r/compare/pkg%2Fv1...pkg%2Fv2":
                            Resposta(200, {"commits": [], "total_commits": 0})})
    assert coletar_commits_entre_releases(cliente, "o/r", "pkg/v1", "pkg/v2")["status"] == "sem_commits"
    assert coletar_commits_entre_releases(cliente, "o/r", None, "v2")["status"] == "tag_ausente"
    assert len(cliente.chamadas) == 1
