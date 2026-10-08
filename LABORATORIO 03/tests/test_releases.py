import csv

import pytest

from conftest import Resposta
from pipeline.releases import coletar, coletar_releases, coletar_tags


def release(tag, data, **extra):
    return {"id": tag, "tag_name": tag, "published_at": data, "draft": False,
            "prerelease": False, "html_url": f"https://github.com/o/r/releases/tag/{tag}", **extra}


def commit(sha, data="2026-01-01T00:00:00Z"):
    return {"sha": sha, "commit": {"message": "fix bug", "committer": {"date": data},
                                   "author": {"date": "2025-12-31T00:00:00Z"}}}


def cliente_coleta(cliente_falso, releases, tags=None, outras=None):
    rotas = {"/repos/o/r/releases": Resposta(200, releases),
             "/repos/o/r/tags": Resposta(200, tags or [])}
    rotas.update(outras or {})
    return cliente_falso(rotas, {"/repos/o/r/releases": [releases], "/repos/o/r/tags": [tags or []]})


def config(tmp_path):
    return {"janela": {"inicio": "2026-01-01", "fim": "2026-01-14"},
            "saida": {"dir": tmp_path}}


def test_coleta_com_predecessora_pre_janela_e_exportacao(cliente_falso, tmp_path):
    releases = [release("v2", "2026-01-14T00:00:00Z"),
                release("v1", "2025-12-01T00:00:00Z")]
    commits = [commit(str(dia), f"2026-01-{dia:02d}T00:00:00Z") for dia in [1, 9, 13]]
    tags = [{"name": "v2", "commit": {"sha": "tagsha"}}]
    cliente = cliente_coleta(cliente_falso, releases, tags, {
        "/repos/o/r/compare/v1...v2": Resposta(200, {"total_commits": 3, "commits": commits}),
        "/repos/o/r/commits/tagsha": Resposta(200, commit("tagsha"))})
    tabelas = coletar(cliente, [{"full_name": "o/r"}, {"full_name": "o/r"}], config(tmp_path))
    resumo = tabelas["metricas_entrega"][0]
    assert resumo["frequencia_releases_semana"] == 0.5
    assert resumo["tags_janela"] == 1
    assert resumo["lead_time_a_horas"] == 312
    assert resumo["lead_time_b_horas"] == 120
    assert resumo["releases_ignoradas"] == 0
    assert len(tabelas["metricas_entrega"]) == 1
    assert len(tabelas["commits"]) == 3
    assert tabelas["releases"][1]["tag_anterior"] == "v1"
    for nome in ["releases", "tags", "commits", "metricas_entrega"]:
        with (tmp_path / f"{nome}.csv").open(encoding="utf-8", newline="") as arquivo:
            assert len(list(csv.DictReader(arquivo))) == len(tabelas[nome])


def test_unica_release_primeira_historia_ignorada_sem_falso_zero(cliente_falso, tmp_path):
    cliente = cliente_coleta(cliente_falso, [release("v1", "2026-01-02T00:00:00Z")])
    tabelas = coletar(cliente, [{"full_name": "o/r"}], config(tmp_path))
    resumo = tabelas["metricas_entrega"][0]
    assert resumo["lead_time_a_horas"] is None and resumo["lead_time_b_horas"] is None
    assert resumo["releases_primeira_historia"] == resumo["releases_ignoradas"] == 1
    assert not any("/compare/" in caminho for caminho, _ in cliente.chamadas)


@pytest.mark.parametrize("resposta,status,coluna", [
    (Resposta(200, {"commits": [], "total_commits": 0}), "sem_commits", "releases_sem_commits"),
    (Resposta(404, {}), "http_404", "releases_compare_404"),
    (Resposta(403, {}), "http_403", "releases_erro_compare"),
])
def test_release_sem_commits_ou_com_erro_contabilizada(cliente_falso, tmp_path, resposta, status, coluna):
    cliente = cliente_coleta(cliente_falso, [release("v0", "2025-12-01T00:00:00Z"),
                                           release("v1", "2026-01-02T00:00:00Z")], outras={
                                               "/repos/o/r/compare/v0...v1": resposta})
    tabelas = coletar(cliente, [{"full_name": "o/r"}], config(tmp_path))
    assert tabelas["releases"][1]["commits_status"] == status
    resumo = tabelas["metricas_entrega"][0]
    assert resumo[coluna] == resumo["releases_ignoradas"] == 1
    assert resumo["lead_time_a_horas"] is None


def test_prerelease_e_draft_nao_substituem_predecessora_estavel(cliente_falso, tmp_path):
    releases = [release("v0", "2025-12-01T00:00:00Z"),
                release("v1-rc", "2026-01-01T00:00:00Z", prerelease=True),
                release("draft", "2026-01-02T00:00:00Z", draft=True),
                release("v1", "2026-01-14T23:59:59Z")]
    cliente = cliente_coleta(cliente_falso, releases, outras={
        "/repos/o/r/compare/v0...v1": Resposta(200, {"commits": [commit("c")], "total_commits": 1})})
    tabelas = coletar(cliente, [{"full_name": "o/r"}], config(tmp_path))
    resumo = tabelas["metricas_entrega"][0]
    assert resumo["releases_janela"] == 1
    assert resumo["frequencia_releases_semana"] == 0.5
    assert tabelas["releases"][-1]["tag_anterior"] == "v0"


def test_releases_ordenadas_por_publicacao_deduplicadas_sem_parada_prematura(cliente_falso):
    recentes = release("nova", "2026-01-02T00:00:00Z")
    antigas = [release(str(i), "2020-01-01T00:00:00Z") for i in range(35)]
    cliente = cliente_falso({"/repos/o/r/releases": Resposta(200, antigas)},
                            {"/repos/o/r/releases": [antigas, [recentes, recentes]]})
    releases, status = coletar_releases(cliente, "o/r", "2026-01-01", "2026-01-14")
    assert status == "ok" and len(releases) == 36
    assert releases[-1]["tag_name"] == "nova" and releases[-1]["na_janela"]


def test_tags_usam_data_commit_deduplicam_nome_mas_contam_tags_no_mesmo_sha(cliente_falso):
    tags = [{"name": nome, "commit": {"sha": "a"}} for nome in ["v1", "v1", "v2"]]
    cliente = cliente_coleta(cliente_falso, [], tags, {
        "/repos/o/r/commits/a": Resposta(200, commit("a", "2026-01-14T23:59:59Z"))})
    resultado, status = coletar_tags(cliente, "o/r", "2026-01-01", "2026-01-14")
    assert status == "ok" and len(resultado) == 2
    assert all(t["na_janela"] for t in resultado)
    assert sum(c == "/repos/o/r/commits/a" for c, _ in cliente.chamadas) == 1


def test_tag_inacessivel_deixa_contagem_ausente(cliente_falso, tmp_path):
    cliente = cliente_coleta(cliente_falso, [], [{"name": "tag", "commit": {"sha": "sumiu"}}])
    tabelas = coletar(cliente, [{"full_name": "o/r"}], config(tmp_path))
    assert tabelas["tags"][0]["status"] == "http_404"
    resumo = tabelas["metricas_entrega"][0]
    assert resumo["tags_ignoradas"] == 1
    assert resumo["tags_janela"] is None
    assert resumo["frequencia_releases_semana"] == 0


def test_endpoints_inacessiveis_nao_sao_interpretados_como_zero(cliente_falso, tmp_path):
    tabelas = coletar(cliente_falso({}), [{"full_name": "o/r"}], config(tmp_path))
    resumo = tabelas["metricas_entrega"][0]
    assert resumo["releases_status"] == resumo["tags_status"] == "http_404"
    assert resumo["frequencia_releases_semana"] is None
    assert resumo["tags_janela"] is None


def test_amostra_vazia_gera_csvs_com_cabecalho(cliente_falso, tmp_path):
    coletar(cliente_falso({}), [], config(tmp_path))
    assert {arquivo.stem for arquivo in tmp_path.glob("*.csv")} == {
        "releases", "tags", "commits", "metricas_entrega",
    }
    for nome in ["releases", "tags", "commits", "metricas_entrega"]:
        assert (tmp_path / f"{nome}.csv").read_text().startswith("full_name,")
