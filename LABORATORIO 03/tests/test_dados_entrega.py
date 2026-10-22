import csv
import gzip

import pytest

from pipeline.dados_entrega import booleano, carregar_releases, linhas_csv


def gravar_csv(caminho, linhas, colunas=None):
    abrir = gzip.open if caminho.suffix == ".gz" else open
    with abrir(caminho, "wt", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas or list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)


def release(**alteracoes):
    return {"full_name": "o/r", "tag_name": "v1.0.1", "published_at": "2026-01-03T00:00:00Z",
            "draft": "False", "prerelease": "False", "commits_status": "ok",
            "commits_novos": "2", **alteracoes}


def commit(sha="abc", mensagem="feat: novidade", **alteracoes):
    return {"full_name": "o/r", "tag_name": "v1.0.1", "sha": sha, "message": mensagem, **alteracoes}


@pytest.mark.parametrize("extensao", [".csv", ".csv.gz"])
def test_streaming_com_quoting_mensagem_completa_e_resumo(tmp_path, extensao):
    r, c = tmp_path / "releases.csv", tmp_path / f"commits{extensao}"
    gravar_csv(r, [release()])
    gravar_csv(c, [commit(mensagem='feat: tela, com "aspas"\n\nFixes erro'), commit("def")])
    dados = carregar_releases(r, c)
    assert dados[0]["draft"] is False
    assert dados[0]["evidencia_commits"] == {"v1": False, "v2": True, "total": 2, "incompletos": 0}
    assert dados[0]["commits_integridade"] == "ok"
    assert "commits" not in dados[0] and "message" not in dados[0]


def test_dedup_sha_nao_infla_total_e_conflitos_invalidam(tmp_path):
    r, c = tmp_path / "r.csv", tmp_path / "c.csv"
    gravar_csv(r, [release(commits_novos="1")])
    gravar_csv(c, [commit(mensagem="fix"), commit(mensagem="fix")])
    dado = carregar_releases(r, c)[0]
    assert dado["commits_duplicados"] == 1 and dado["commits_coletados"] == 1
    assert dado["evidencia_commits"]["v1"] is True
    gravar_csv(c, [commit(mensagem="fix"), commit(mensagem="feat")])
    dado = carregar_releases(r, c)[0]
    assert dado["commits_conflitantes"] == 1
    assert dado["evidencia_commits"]["v1"] is None
    assert "sha_conflitante" in dado["commits_integridade"]


@pytest.mark.parametrize("linhas,alteracoes,motivo", [
    ([commit(mensagem="fix")], {}, "quantidade_divergente"),
    ([commit(mensagem=""), commit("def")], {}, "mensagem_ou_sha_ausente"),
    ([commit(sha=""), commit("def")], {}, "mensagem_ou_sha_ausente"),
    ([commit(), commit("def")], {"commits_status": "http_404"}, "compare_indisponivel"),
    ([commit(), commit("def")], {"commits_status": "sem_commits"}, "status_quantidade_divergente"),
    ([commit(), commit("def")], {"commits_novos": ""}, "quantidade_esperada_ausente"),
])
def test_incompletude_nunca_vira_negativo(tmp_path, linhas, alteracoes, motivo):
    r, c = tmp_path / "r.csv", tmp_path / "c.csv"
    gravar_csv(r, [release(**alteracoes)])
    gravar_csv(c, linhas)
    dado = carregar_releases(r, c)[0]
    assert dado["evidencia_commits"]["v1"] is None
    assert motivo in dado["commits_integridade"]


def test_arquivo_opcional_nao_fabrica_evidencia(tmp_path):
    r = tmp_path / "r.csv"
    gravar_csv(r, [release()])
    assert carregar_releases(r)[0]["evidencia_commits"]["v1"] is None
    gravar_csv(r, [release(commits_novos="0", commits_status="sem_commits")])
    assert carregar_releases(r)[0]["evidencia_commits"]["v1"] is False


def test_sha_pode_se_repetir_em_releases_diferentes(tmp_path):
    r, c = tmp_path / "r.csv", tmp_path / "c.csv"
    gravar_csv(r, [release(commits_novos="1"), release(tag_name="v1.0.2", commits_novos="1")])
    gravar_csv(c, [commit(), commit(tag_name="v1.0.2")])
    assert [linha["commits_coletados"] for linha in carregar_releases(r, c)] == [1, 1]


def test_comparacao_nao_pode_usar_outra_tag_base(tmp_path):
    r, c = tmp_path / "r.csv", tmp_path / "c.csv"
    gravar_csv(r, [release(commits_novos="1", tag_anterior="v1.0.0")])
    gravar_csv(c, [commit(mensagem="fix", tag_anterior="v0.9.0")])
    dado = carregar_releases(r, c)[0]
    assert "comparacao_divergente" in dado["commits_integridade"]
    assert dado["evidencia_commits"]["v1"] is None


def test_rejeita_commit_orfao_e_duplicata_release_conflitante(tmp_path):
    r, c = tmp_path / "r.csv", tmp_path / "c.csv"
    gravar_csv(r, [release(), release()])
    assert len(carregar_releases(r)) == 1
    gravar_csv(c, [commit(tag_name="v99")])
    with pytest.raises(ValueError, match="sem release"):
        carregar_releases(r, c)
    gravar_csv(r, [release(), release(commits_novos="3")])
    dados = carregar_releases(r)
    assert len(dados) == 1  # Uma tag conta como uma única entrega.
    assert "tag_com_releases_conflitantes" in dados[0]["commits_integridade"]
    assert dados[0]["evidencia_commits"]["v1"] is None
    assert dados[0]["evidencia_commits"]["v2"] is None


@pytest.mark.parametrize("valor", ["-1", "1.5", "NaN", "Infinity", "errado"])
def test_quantidade_invalida(tmp_path, valor):
    r = tmp_path / "r.csv"
    gravar_csv(r, [release(commits_novos=valor)])
    with pytest.raises(ValueError, match="commits_novos"):
        carregar_releases(r)


def test_csv_malformado_e_colunas_ausentes(tmp_path):
    r = tmp_path / "r.csv"
    r.write_text("a,b\n1\n")
    with pytest.raises(ValueError, match="incompleto"):
        list(linhas_csv(r, {"a", "b"}))
    with pytest.raises(ValueError, match="colunas ausentes"):
        carregar_releases(r)
    r.write_text("a,a\n1,2\n")
    with pytest.raises(ValueError, match="duplicadas"):
        list(linhas_csv(r, {"a"}))


@pytest.mark.parametrize("valor,esperado", [("False", False), ("TRUE", True), ("nao", False),
                                          ("sim", True), ("0", False), ("", None), (True, True)])
def test_booleanos_csv(valor, esperado):
    assert booleano(valor) is esperado


def test_booleano_nao_aceita_texto_arbitrario():
    with pytest.raises(ValueError, match="booleano inválido"):
        booleano("talvez")


def test_tags_repetidas_com_release_ids_diferentes_ficam_inconclusivas(tmp_path):
    r = tmp_path / "r.csv"
    gravar_csv(r, [
        release(release_id="25582079", tag_anterior="v1.0.0"),
        release(release_id="25582080", tag_anterior="v1.0.1"),
    ])
    dados = carregar_releases(r)
    assert len(dados) == 1
    assert dados[0]["release_ids_agrupados"] == ["25582079", "25582080"]
    assert "tag_com_releases_conflitantes" in dados[0]["commits_integridade"]
    assert dados[0]["evidencia_commits"]["v1"] is None
    assert dados[0]["evidencia_commits"]["v2"] is None
