from datetime import date

from conftest import Resposta
from pipeline.__main__ import selecionar_amostra
from pipeline.funil import NAO_AVALIADO, limites_da_janela


INICIO, FIM = limites_da_janela(date(2025, 10, 1), date(2026, 9, 30))
MINIMOS = {"releases": 5, "runs": 50}


def candidato(nome):
    return {"full_name": nome, "estrelas": 2000, "linguagem": "Python",
            "criado_em": "2020-01-01T00:00:00Z", "default_branch": "main", "url": ""}


def test_selecionar_amostra(cliente_falso):
    release = {"published_at": "2026-01-01T00:00:00Z", "draft": False, "prerelease": False}
    rotas, paginas = {}, {}
    # sem Actions | poucas releases | poucos runs | aprovado | aprovado (não avaliado)
    for nome, workflows, releases, runs in [("o/sem", 0, 9, 99), ("o/rel", 1, 4, 99),
                                            ("o/runs", 1, 9, 10), ("o/ok", 1, 9, 99),
                                            ("o/extra", 1, 9, 99)]:
        rotas[f"/repos/{nome}/actions/workflows"] = Resposta(200, {"total_count": workflows})
        rotas[f"/repos/{nome}/actions/runs"] = (
            lambda p, runs=runs: Resposta(200, {"total_count": runs if p["status"] == "success" else 0}))
        rotas[f"/repos/{nome}/contributors"] = Resposta(200, [{}])
        paginas[f"/repos/{nome}/releases"] = [[release] * releases]
    nomes = ["o/sem", "o/rel", "o/runs", "o/404", "o/ok", "o/extra"]

    amostra, descartes = selecionar_amostra(
        cliente_falso(rotas, paginas), [candidato(n) for n in nomes], INICIO, FIM, 1, MINIMOS)

    assert descartes == {"o/sem": "actions", "o/rel": "releases", "o/runs": "runs",
                         "o/404": "acessivel", "o/ok": None, "o/extra": NAO_AVALIADO}
    assert [r["full_name"] for r in amostra] == ["o/ok"]
    assert amostra[0]["releases_janela"] == 9 and amostra[0]["runs_validos_janela"] == 99
    assert amostra[0]["contribuidores"] == 1
