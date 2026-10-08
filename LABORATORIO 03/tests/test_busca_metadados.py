from datetime import datetime, timezone

import pytest

from conftest import Resposta, link
from pipeline.busca import buscar_candidatos, montar_consulta, tem_actions, validar_faixas
from pipeline.metadados import coletar_metadados, contar_contribuidores, idade_em_anos, ultima_pagina


def item(nome, estrelas=1500):
    return {"full_name": nome, "stargazers_count": estrelas, "language": None,
            "created_at": "2020-01-01T00:00:00Z", "default_branch": "main",
            "html_url": f"https://github.com/{nome}"}


@pytest.mark.parametrize("minimo, maximo, extra, esperado", [
    (1000, 1999, "", "stars:1000..1999"),
    (50000, None, "", "stars:>=50000"),
    (1000, 1999, "archived:false", "stars:1000..1999 archived:false"),
])
def test_montar_consulta(minimo, maximo, extra, esperado):
    assert montar_consulta(minimo, maximo, extra) == esperado


@pytest.mark.parametrize("faixas", [
    [(1000, 2000), (2000, 3000)],   # 2000 nas duas faixas
    [(2000, 1000)],
    [(1000, None), (2000, 3000)],
])
def test_faixas_invalidas(faixas):
    with pytest.raises(ValueError):
        validar_faixas(faixas)


def test_buscar_candidatos_une_faixas_sem_duplicatas(cliente_falso):
    paginas = {"stars:1000..1999": [{"items": [item("a/x"), item("b/y")]}],
               "stars:>=2000": [{"items": [item("b/y"), item("c/z", 9000)]}]}
    cliente = cliente_falso(
        {"/search/repositories": lambda p: Resposta(200, {"total_count": 2})},
        {"/search/repositories": lambda p: paginas[p["q"]]},
    )
    candidatos = buscar_candidatos(cliente, [(1000, 1999), (2000, None)])
    assert [c["full_name"] for c in candidatos] == ["a/x", "b/y", "c/z"]
    assert candidatos[0]["linguagem"] == ""


def test_buscar_candidatos_respeita_teto_de_1000(cliente_falso, caplog):
    cliente = cliente_falso(
        {"/search/repositories": Resposta(200, {"total_count": 5000})},
        {"/search/repositories": [{"items": [item(f"o/r{i}")]} for i in range(12)]},
    )
    candidatos = buscar_candidatos(cliente, [(1000, 1099)])
    assert len(candidatos) == 10        # 1.000 resultados / 100 por página = 10 páginas
    assert "Divida essa faixa" in caplog.text


def test_buscar_candidatos_ignora_faixa_com_erro(cliente_falso):
    cliente = cliente_falso({"/search/repositories": Resposta(422, {})})
    assert buscar_candidatos(cliente, [(1000, 1099)]) == []


@pytest.mark.parametrize("resposta, esperado", [
    (Resposta(200, {"total_count": 3, "workflows": []}), True),
    (Resposta(200, {"total_count": 0, "workflows": []}), False),
    (Resposta(404, {"message": "Not Found"}), None),
])
def test_tem_actions(cliente_falso, resposta, esperado):
    cliente = cliente_falso({"/repos/o/r/actions/workflows": resposta})
    assert tem_actions(cliente, "o/r") is esperado


def test_ultima_pagina():
    assert ultima_pagina(link("/repos/o/r/contributors", next=2, last=342)) == 342
    assert ultima_pagina("") is None


@pytest.mark.parametrize("resposta, esperado", [
    (Resposta(200, [{}], link("/repos/o/r/contributors", next=2, last=87)), 87),
    (Resposta(200, [{}]), 1),           # um único contribuidor: sem cabeçalho Link
    (Resposta(204, None), 0),           # repositório vazio
    (Resposta(403, {"message": "history too large"}), None),
])
def test_contar_contribuidores(cliente_falso, resposta, esperado):
    cliente = cliente_falso({"/repos/o/r/contributors": resposta})
    assert contar_contribuidores(cliente, "o/r") == esperado
    assert cliente.chamadas[0][1] == {"per_page": 1, "anon": "true"}


def test_idade_em_anos():
    referencia = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert idade_em_anos("2016-01-01T00:00:00Z", referencia) == pytest.approx(10, abs=0.01)


def test_coletar_metadados(cliente_falso):
    cliente = cliente_falso({"/repos/a/x/contributors":
                             Resposta(200, [{}], link("/repos/a/x/contributors", last=12))})
    repositorio = {"full_name": "a/x", "estrelas": 1500, "criado_em": "2024-01-01T00:00:00Z"}
    metadados = coletar_metadados(cliente, repositorio, datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert metadados["contribuidores"] == 12
    assert metadados["idade_anos"] == pytest.approx(2, abs=0.01)
    assert metadados["estrelas"] == 1500
