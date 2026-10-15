import pytest

from metricas.lead_time import calcular_lead_times, horas_ate_publicacao, instante, resumir_lead_times


PUBLICADA = "2026-01-14T00:00:00Z"
COMMITS = [{"sha": str(dia), "author_date": f"2026-01-{dia:02d}T00:00:00Z"}
           for dia in [1, 9, 13]]


def test_exemplo_enunciado_13_dias_e_13_5_1_em_horas():
    resultado = calcular_lead_times(PUBLICADA, COMMITS)
    assert resultado == {"lead_time_a_horas": 13 * 24,
                         "lead_times_b_horas": [13 * 24, 5 * 24, 24],
                         "commits_validos": 3, "commits_invalidos": 0}
    resumo = resumir_lead_times([{"published_at": PUBLICADA, "commits": COMMITS}])
    assert resumo["lead_time_a_horas"] == 312
    assert resumo["lead_time_b_horas"] == 120


@pytest.mark.parametrize("commits", [None, []])
def test_release_sem_observacoes_nao_tem_lead_time_zero(commits):
    resultado = calcular_lead_times(PUBLICADA, commits)
    assert resultado["lead_time_a_horas"] is None
    assert resultado["lead_times_b_horas"] == []
    assert resumir_lead_times([{"published_at": PUBLICADA, "commits": commits}])["lead_time_b_horas"] is None


def test_variante_b_pesa_cada_commit_em_vez_da_mediana_das_releases():
    releases = [{"published_at": PUBLICADA, "commits": COMMITS},
                {"published_at": PUBLICADA, "commits": [
                    {"sha": "quatro", "author_date": "2026-01-10T00:00:00Z"}]}]
    resumo = resumir_lead_times(releases)
    assert resumo["lead_time_a_horas"] == 8.5 * 24  # mediana(13, 4)
    assert resumo["lead_time_b_horas"] == 4.5 * 24  # mediana(13, 5, 1, 4)


def test_datas_invalidas_futuras_e_duplicatas_nao_viciam_mediana():
    commits = COMMITS + [COMMITS[0], {"sha": "sem_data"},
                         {"sha": "futuro", "author_date": "2026-01-15T00:00:00Z"}]
    resultado = calcular_lead_times(PUBLICADA, commits)
    assert resultado["commits_validos"] == 3
    assert resultado["commits_invalidos"] == 2
    assert resultado["lead_time_a_horas"] == 312


def test_padrao_e_autoria_committer_preservado_e_fusos_normalizados():
    commit = {"commit": {"author": {"date": "2026-01-12T00:00:00Z"},
                         "committer": {"date": "2026-01-13T03:00:00+03:00"}}}
    assert horas_ate_publicacao(PUBLICADA, commit) == 48  # padrão: commit.author.date
    assert horas_ate_publicacao(PUBLICADA, commit, "committer_date") == 24
    assert instante("2026-01-01T00:00:00") is None
    assert instante("data-invalida") is None


def test_lead_time_zero_observado_e_valido():
    assert horas_ate_publicacao(PUBLICADA, {"author_date": PUBLICADA}) == 0


def test_campo_de_data_invalido():
    with pytest.raises(ValueError):
        calcular_lead_times(PUBLICADA, COMMITS, "outro")
