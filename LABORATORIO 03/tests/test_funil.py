from datetime import date, datetime, timezone

import pytest

from conftest import Resposta
from pipeline.funil import (NAO_AVALIADO, avaliar_contagens, contar_releases_na_janela,
                            contar_runs_validos, limites_da_janela, montar_funil, release_valida)


INICIO, FIM = limites_da_janela(date(2025, 10, 1), date(2026, 9, 30))


def release(publicada, draft=False, prerelease=False):
    return {"published_at": publicada, "draft": draft, "prerelease": prerelease}


def test_janela_inclui_o_dia_final_inteiro():
    assert INICIO == datetime(2025, 10, 1, tzinfo=timezone.utc)
    assert FIM.date() == date(2026, 9, 30) and FIM.hour == 23 and FIM.minute == 59


@pytest.mark.parametrize("dados, esperado", [
    (release("2026-03-15T10:00:00Z"), True),
    (release("2025-10-01T00:00:00Z"), True),             # primeiro instante da janela
    (release("2026-09-30T23:59:59Z"), True),             # último segundo da janela
    (release("2025-09-30T23:59:59Z"), False),            # antes da janela
    (release("2026-10-01T00:00:00Z"), False),            # depois da janela
    (release("2026-03-15T10:00:00Z", draft=True), False),
    (release("2026-03-15T10:00:00Z", prerelease=True), False),
    (release(None, draft=True), False),                  # rascunho não tem published_at
])
def test_release_valida(dados, esperado):
    assert release_valida(dados, INICIO, FIM) is esperado


@pytest.mark.parametrize("n_releases, n_runs, esperado", [
    (5, 50, None),          # exatamente no mínimo: aprovado
    (30, 900, None),
    (4, 900, "releases"),
    (4, None, "releases"),  # runs nem consultados
    (5, 49, "runs"),
    (5, None, "runs"),
])
def test_avaliar_contagens(n_releases, n_runs, esperado):
    assert avaliar_contagens(n_releases, n_runs) == esperado


def test_avaliar_contagens_com_minimos_do_config():
    assert avaliar_contagens(3, 10, min_releases=3, min_runs=10) is None


def test_contar_releases_ignora_draft_prerelease_e_fora_da_janela(cliente_falso):
    cliente = cliente_falso({}, {"/repos/o/r/releases": [[
        release("2026-08-01T00:00:00Z"),
        release("2026-07-01T00:00:00Z", prerelease=True),
        release(None, draft=True),
        release("2026-01-01T00:00:00Z"),
        release("2025-01-01T00:00:00Z"),
    ]]})
    assert contar_releases_na_janela(cliente, "o/r", INICIO, FIM) == 2


def test_contar_releases_para_de_paginar_longe_da_janela(cliente_falso):
    antigas = [release("2020-01-01T00:00:00Z")] * 30
    cliente = cliente_falso({}, {"/repos/o/r/releases": [
        [release("2026-01-01T00:00:00Z")] + antigas,
        [release("2026-02-01T00:00:00Z")],  # nunca deve ser lida
    ]})
    assert contar_releases_na_janela(cliente, "o/r", INICIO, FIM) == 1
    assert len(cliente.chamadas) == 1


def test_contar_runs_soma_so_conclusoes_validas(cliente_falso):
    totais = {"success": 40, "failure": 8, "timed_out": 1, "startup_failure": 1}
    cliente = cliente_falso({"/repos/o/r/actions/runs":
                             lambda p: Resposta(200, {"total_count": totais[p["status"]]})})
    assert contar_runs_validos(cliente, "o/r", "main", INICIO, FIM) == 50
    consultados = {params["status"] for _, params in cliente.chamadas}
    assert consultados == set(totais)  # cancelled, skipped etc. nunca são pedidos
    _, params = cliente.chamadas[0]
    assert params["event"] == "push" and params["branch"] == "main"
    assert params["created"] == "2025-10-01..2026-09-30"


def test_contar_runs_com_erro_da_api(cliente_falso):
    assert contar_runs_validos(cliente_falso({}), "o/r", "main", INICIO, FIM) is None


def test_montar_funil():
    descartes = {"a": None, "b": None, "c": "actions", "d": "actions", "e": "releases",
                 "f": "runs", "g": "acessivel", "h": NAO_AVALIADO, "i": NAO_AVALIADO}
    funil = montar_funil(9, descartes)
    restantes = [linha["restantes"] for linha in funil]
    descartados = [linha["descartados"] for linha in funil]
    assert restantes == [9, 7, 6, 4, 3, 2, 2]
    assert descartados == [0, 2, 1, 2, 1, 1, 0]
    assert funil[-1]["etapa"] == "Amostra final"
    assert "total_count = 0" in funil[3]["motivo"]


def test_funil_sem_descartes_em_uma_etapa_nao_tem_motivo():
    funil = montar_funil(1, {"a": None})
    assert all(linha["motivo"] == "" for linha in funil)
    assert funil[-1]["restantes"] == 1


def test_funil_rejeita_etapa_desconhecida():
    with pytest.raises(ValueError):
        montar_funil(1, {"a": "estrelas"})
