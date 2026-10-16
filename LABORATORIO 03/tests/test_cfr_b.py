"""Casos controlados de CFR (b); não constituem validação humana da heurística."""

from copy import deepcopy
from datetime import date
import json

import pytest

from metricas.cfr import (DEFINICOES_VERSOES, analisar_cfr_b, calcular_cfr,
                         calcular_cfr_b, classificar_corretiva, palavras_corretivas)


INICIO, FIM = "2026-01-01", "2026-01-31"


def release(tag, dia, mensagem="feat: add feature", **extra):
    data = f"2026-01-{dia:02d}T00:00:00Z" if isinstance(dia, int) else dia
    return {"full_name": "org/projeto", "tag_name": tag, "published_at": data,
            "draft": False, "prerelease": False, "commits_status": "ok",
            "commits_novos": 1, "commits": [{"sha": tag, "message": mensagem}], **extra}


def por_tag(resultado):
    return {r["tag_name"]: r for r in resultado["releases"]}


def test_exemplo_patch_fix_em_tres_dias_atribui_falha_a_original():
    releases = [release("v2.3.0", 10), release("v2.3.1", 13, "fix: login bug"),
                release("v2.4.0", 20, "fix: include new features")]
    resultado = analisar_cfr_b(releases, INICIO, FIM)
    linhas = por_tag(resultado)
    assert resultado["cfr_b"] == pytest.approx(1 / 3)
    assert resultado["falhas"] == 1 and resultado["denominador"] == 3
    assert linhas["v2.3.0"]["falhou"] is True
    assert linhas["v2.3.0"]["tag_corretiva"] == "v2.3.1"
    assert linhas["v2.3.0"]["corretiva"] is None  # primeira da história
    assert linhas["v2.3.1"]["corretiva"] is True
    assert linhas["v2.3.1"]["falhou"] is False  # sucessora muda o minor
    assert linhas["v2.4.0"]["corretiva"] is False
    assert calcular_cfr_b(releases, INICIO, FIM) == resultado["cfr_b"]


def test_censura_original_nao_apaga_classificacao_propria_corretiva():
    resultado = analisar_cfr_b([release("v2.3.0", 23),
                               release("v2.3.1", 26, "hotfix login")], INICIO, FIM)
    original, corretiva = resultado["releases"]
    assert original["falhou"] is True and original["elegivel"] is True
    assert corretiva["corretiva"] is True and corretiva["censurada"] is True
    assert corretiva["falhou"] is None and corretiva["elegivel"] is False
    assert resultado["falhas"] == resultado["denominador"] == resultado["censuradas"] == 1
    assert resultado["cfr_b"] == 1


def test_ultimos_sete_dias_nao_entram_denominador_mesmo_com_correcao():
    resultado = analisar_cfr_b([release("v1.0.0", 25), release("v1.0.1", 27, "fix bug")],
                               INICIO, FIM)
    assert resultado["censuradas"] == 2
    assert resultado["denominador"] == resultado["falhas"] == 0
    assert resultado["cfr_b"] is None
    assert resultado["releases"][1]["corretiva"] is True


def test_borda_censura_janela_inclusiva_em_utc():
    resultado = analisar_cfr_b([
        release("v1.0.0", "2026-01-24T23:59:59.999999Z"),
        release("v1.0.1", "2026-01-25T00:00:00Z", "fix bug"),
        release("v1.0.2", "2026-01-31T23:59:59.999999Z", "fix bug"),
    ], date(2026, 1, 1), date(2026, 1, 31))
    assert [r["censurada"] for r in resultado["releases"]] == [False, True, True]
    assert resultado["denominador"] == 1 and resultado["falhas"] == 1


@pytest.mark.parametrize("intervalo,esperado", [(7, True), (8, False)])
def test_corretiva_no_limite_de_sete_dias(intervalo, esperado):
    resultado = classificar_corretiva(release("v2.3.1", 10 + intervalo, "fix bug"),
                                     release("v2.3.0", 10))
    assert resultado["corretiva"] is esperado
    assert resultado["intervalo_dias"] == intervalo


def test_sete_dias_exatos_nao_arredonda_para_dias_de_calendario():
    resultado = classificar_corretiva(release("v1.0.1", "2026-01-17T00:00:01Z", "fix bug"),
                                     release("v1.0.0", 10))
    assert resultado["corretiva"] is False


def test_patch_sem_palavra_minor_com_palavra_e_major_nao_sao_corretivas():
    base = release("v2.3.0", 10)
    for tag, mensagem in [("v2.3.1", "add feature"), ("v2.4.0", "fix bug"),
                           ("v3.0.0", "hotfix"), ("v2.3.0", "revert"),
                           ("v2.2.9", "fix bug")]:
        assert classificar_corretiva(release(tag, 11, mensagem), base)["corretiva"] is False


def test_semver_aceita_prefixo_opcional_build_e_salto_patch():
    resultado = classificar_corretiva(release("2.3.4+linux.2", 11, "fix bug"),
                                     release("v2.3.0+linux.1", 10))
    assert resultado["corretiva"] is True


@pytest.mark.parametrize("tag", ["stable", "v2.3", "v02.3.1", "v2.3.1-rc.1", ""])
def test_tags_nao_semver_ficam_inconclusivas(tag):
    resultado = analisar_cfr_b([release("v2.3.0", 23), release(tag, 26, "fix bug")],
                               INICIO, FIM)
    assert resultado["inconclusivas"] == 1 and resultado["denominador"] == 0
    assert resultado["cfr_b"] is None
    assert resultado["releases"][0]["motivo"] == "tag_nao_semver"


@pytest.mark.parametrize("mensagem", ["fix", "Fix: login", "HOTFIX login", 'Revert "x"',
                                      "docs\n\nfix login", "bug-fix"])
def test_v1_palavras_inteiras_sem_diferenciar_caixa(mensagem):
    assert palavras_corretivas(mensagem, "v1")


@pytest.mark.parametrize("mensagem", ["prefix", "suffix", "hotfixer", "revertible", "fix_bug",
                                      "fixes", "fixed", "fixing", "reverted", ""])
def test_v1_nao_confunde_substrings_ou_flexoes(mensagem):
    assert not palavras_corretivas(mensagem, "v1")


@pytest.mark.parametrize("mensagem", ["fixes", "fixed", "fixing", "hotfixes", "hotfixed",
                                      "hotfixing", "reverts", "reverted", "reverting"])
def test_v2_refinamento_de_flexoes(mensagem):
    assert palavras_corretivas(mensagem, "v2")


def test_v2_muda_somente_lexico_conserva_patch_e_prazo():
    original = release("v2.3.0", 10)
    patch = release("v2.3.1", 11, "fixed crash")
    assert classificar_corretiva(patch, original, versao="v1")["corretiva"] is False
    assert classificar_corretiva(patch, original, versao="v2")["corretiva"] is True
    assert classificar_corretiva(release("v2.4.0", 11, "fixed crash"), original,
                                versao="v2")["corretiva"] is False
    assert classificar_corretiva(release("v2.3.1", 18, "fixed crash"), original,
                                versao="v2")["corretiva"] is False
    assert not palavras_corretivas("prefixes suffixes", "v2")


@pytest.mark.parametrize("status", ["http_404", "http_422", "paginacao_incompleta"])
def test_erro_comparacao_nao_vira_sucesso_ou_zero(status):
    resultado = analisar_cfr_b([release("v1.0.0", 23),
        release("v1.0.1", 26, "fix bug", commits_status=status, commits=None,
                commits_novos=None)], INICIO, FIM)
    assert resultado["cfr_b"] is None and resultado["inconclusivas"] == 1
    assert resultado["releases"][0]["falhou"] is None
    assert resultado["releases"][1]["motivo_corretiva"] == f"commits_{status}"


@pytest.mark.parametrize("extra", [
    {"commits": None, "commits_novos": None},
    {"commits": [], "commits_novos": 1},
    {"commits": [{"sha": "a"}], "commits_novos": 1},
    {"commits": [{"sha": "a", "message": ""}], "commits_novos": 1},
    {"commits": [{"sha": "a", "message": "  "}], "commits_novos": 1},
    {"commits": [{"sha": "a", "message": "fix bug"}], "commits_novos": 2},
])
def test_evidencia_ausente_ou_parcial_inconclusiva(extra):
    resultado = classificar_corretiva(release("v1.0.1", 11, **extra), release("v1.0.0", 10))
    assert resultado["corretiva"] is None


@pytest.mark.parametrize("commits", [[], None])
def test_comparacao_vazia_observada_e_negativa(commits):
    resultado = classificar_corretiva(release("v1.0.1", 11, commits=commits,
                                             commits_status="sem_commits", commits_novos=0),
                                     release("v1.0.0", 10))
    assert resultado["corretiva"] is False


def test_commits_raw_github_e_duplicados_por_sha():
    commit = {"sha": "x", "commit": {"message": "fix bug"}}
    resultado = classificar_corretiva(release("v1.0.1", 11, commits=[commit, commit]),
                                     release("v1.0.0", 10))
    assert resultado["corretiva"] is True


def test_evidencia_compacta_csv_gz_equivale_a_lista():
    base = release("v1.0.0", 10)
    atual = release("v1.0.1", 11, "fixed bug")
    compacta = {k: v for k, v in atual.items() if k != "commits"}
    compacta["commits_novos"] = "1"
    compacta["evidencia_commits"] = {"v1": False, "v2": True, "total": 1, "incompletos": 0}
    for versao in ("v1", "v2"):
        assert classificar_corretiva(compacta, base, versao=versao) == classificar_corretiva(
            atual, base, versao=versao)


@pytest.mark.parametrize("resumo", [
    {"v1": True, "v2": True, "total": 0, "incompletos": 0},
    {"v1": True, "v2": True, "total": 1, "incompletos": 1},
    {"v1": None, "v2": None, "total": 1, "incompletos": 0},
])
def test_resumo_incompleto_nao_adivinha_predicao(resumo):
    assert classificar_corretiva(release("v1.0.1", 11, evidencia_commits=resumo),
                                release("v1.0.0", 10))["corretiva"] is None


def test_predecessora_divergente_impede_usar_mensagens_de_outra_comparacao():
    resultado = classificar_corretiva(release("v1.0.1", 11, "fix bug", tag_anterior="v0.9.0"),
                                     release("v1.0.0", 10))
    assert resultado["corretiva"] is None
    assert resultado["motivo_corretiva"] == "comparacao_predecessora_divergente"


def test_pre_releases_e_drafts_nao_interrompem_sequencia_estavel():
    resultado = analisar_cfr_b([
        release("v1.0.0", 10, draft="False", prerelease="False"),
        release("v1.0.1-rc.1", 11, "fix bug", prerelease="True"),
        release("rascunho", 12, "fix bug", draft=True),
        release("v1.0.1", 13, "fix bug"),
    ], INICIO, FIM)
    assert resultado["denominador"] == 2 and resultado["falhas"] == 1
    assert resultado["releases_janela"] == 2
    assert resultado["releases"][3]["tag_anterior"] == "v1.0.0"
    assert all(r["motivo"] == "release_nao_estavel" for r in resultado["releases"][1:3])


def test_pre_janela_contexto_e_pos_janela_nao_completa_censura():
    releases = [release("v1.0.0", "2025-12-30T00:00:00Z"),
                release("v1.0.1", 2, "fix bug"), release("v1.0.2", 30, "fix bug"),
                release("v1.0.3", "2026-02-01T00:00:00Z", "fix bug")]
    resultado = analisar_cfr_b(list(reversed(releases)), INICIO, FIM)
    linhas = por_tag(resultado)
    assert linhas["v1.0.1"]["corretiva"] is True
    assert linhas["v1.0.0"]["elegivel"] is False
    assert linhas["v1.0.2"]["censurada"] is True
    assert linhas["v1.0.2"]["tag_seguinte"] == ""
    assert linhas["v1.0.3"]["motivo_corretiva"] == "fora_observacao"
    assert resultado["denominador"] == 1 and resultado["cfr_b"] == 0


def test_releases_simultaneas_nao_recebem_ordem_artificial():
    resultado = analisar_cfr_b([release("v1.0.0", 10),
                               release("v1.0.1", 11, "fix bug"),
                               release("v1.0.2", 11, "fix bug"),
                               release("v1.0.3", 12, "fix bug")], INICIO, FIM)
    assert resultado["inconclusivas"] == 3
    assert resultado["denominador"] == 1 and resultado["falhas"] == 0
    assert all(r["corretiva"] is None for r in resultado["releases"])


def test_repositorios_nao_misturam_predecessoras():
    resultado = analisar_cfr_b([release("v1.0.0", 10),
                               release("v1.0.1", 11, "fix bug", full_name="outra/org")],
                               INICIO, FIM)
    assert resultado["denominador"] == 2 and resultado["falhas"] == 0
    assert all(r["corretiva"] is None for r in resultado["releases"])


def test_primeira_release_sem_anterior_explicita_e_vazio_sem_falso_zero():
    primeira = release("v1.0.0", 10, "fix bug", commits_status="primeira_release")
    assert classificar_corretiva(primeira)["motivo_corretiva"] == "primeira_release"
    assert calcular_cfr_b([], INICIO, FIM) is None
    assert calcular_cfr_b([primeira], INICIO, FIM) == 0  # sem sucessora observada


def test_release_com_data_invalida_e_ignoradas_explicitamente():
    resultado = analisar_cfr_b([release("v1.0.0", "invalida")], INICIO, FIM)
    assert resultado["releases"][0]["motivo"] == "data_invalida"
    assert resultado["cfr_b"] is None and resultado["denominador"] == 0


def test_data_invalida_estavel_impede_adivinhar_ordem_no_mesmo_repositorio():
    resultado = analisar_cfr_b([release("v1.0.0", 10), release("v1.0.1", "invalida"),
                               release("v1.0.2", 11, "fix bug"),
                               release("v1.0.3", 29, "fix bug"),
                               release("v1.0.0", 10, full_name="outro/projeto")],
                               INICIO, FIM)
    assert resultado["inconclusivas"] == 2 and resultado["censuradas"] == 1
    assert resultado["denominador"] == 1
    assert resultado["releases"][2]["motivo_corretiva"] == "historico_data_invalida"
    assert resultado["releases"][4]["falhou"] is False


def test_data_invalida_draft_nao_afeta_historico_estavel():
    resultado = analisar_cfr_b([release("v1.0.0", 10),
                               release("rascunho", "invalida", draft=True)], INICIO, FIM)
    assert resultado["denominador"] == 1 and resultado["inconclusivas"] == 0


def test_entrada_nao_e_mutada_e_metadata_nao_alega_validacao():
    releases = [release("v1.0.0", 10), release("v1.0.1", 11, "fix bug")]
    original = deepcopy(releases)
    analisar_cfr_b(releases, INICIO, FIM)
    assert releases == original
    assert all(not definicao["validada"] for definicao in DEFINICOES_VERSOES.values())
    json.dumps(DEFINICOES_VERSOES)


def test_parametros_invalidos_rejeitados():
    with pytest.raises(ValueError, match="versao"):
        analisar_cfr_b([], INICIO, FIM, versao="v99")
    with pytest.raises(ValueError, match="fim"):
        analisar_cfr_b([], FIM, INICIO)


def test_cfr_a_da_pessoa_c_permanece_compativel():
    assert calcular_cfr([{"conclusion": c} for c in
                         ["success", "failure", "timed_out", "startup_failure",
                          "cancelled", None]]) == 0.75
    assert calcular_cfr([]) is None
    assert calcular_cfr([{"conclusion": "cancelled"}]) is None
