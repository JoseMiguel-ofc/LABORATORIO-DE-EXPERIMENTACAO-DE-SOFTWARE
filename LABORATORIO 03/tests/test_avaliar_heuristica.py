import csv
import json

import pandas as pd
import pytest

from validacao.avaliar_heuristica import (avaliar_previsoes, avaliar_versoes,
                                          carregar_consenso, main)
from validacao.consenso import consolidar


def previsao(tag, valor, **campos):
    return {"full_name": "o/r", "tag_name": tag, "corretiva": valor, **campos}


def rotulo(tag, valor, metodo="maioria"):
    return previsao(tag, valor, metodo_corretiva=metodo)


def test_matriz_e_metricas_calculadas_a_mao():
    # TP=2 FP=1 FN=1 TN=1 => precisão=recall=F1=2/3.
    previsoes = [previsao(str(i), v) for i, v in enumerate([True, True, True, False, False])]
    consenso = [rotulo(str(i), v) for i, v in enumerate(["sim", "sim", "nao", "sim", "nao"])]
    resultado = avaliar_previsoes(previsoes, consenso)
    assert resultado["matriz_confusao"] == {"tp": 2, "fp": 1, "fn": 1, "tn": 1}
    assert resultado["precisao"] == resultado["recall"] == resultado["f1"] == pytest.approx(2 / 3)
    assert resultado["cobertura"] == 1 and resultado["n_avaliados"] == 5
    assert resultado["status"] == "requer_refinamento" and resultado["atingiu_meta"] is False


def test_ausentes_inconclusivas_e_pendentes_nao_viram_negativos():
    consenso = [rotulo("1", "sim"), rotulo("2", "nao"), rotulo("3", "sim"),
                rotulo("4", "", "pendente")]
    resultado = avaliar_previsoes([previsao("1", True), previsao("2", None)], consenso)
    assert resultado["n_pendentes"] == resultado["n_ausentes"] == resultado["n_inconclusivas"] == 1
    assert resultado["n_avaliados"] == 1 and resultado["cobertura"] == pytest.approx(1 / 3)
    assert resultado["f1"] == 1 and resultado["status"] == "avaliacao_parcial"


def test_rotulos_pendentes_impedem_alegar_meta_da_amostra():
    resultado = avaliar_previsoes([previsao("1", True)],
                                  [rotulo("1", "sim"), rotulo("2", "", "pendente")])
    assert resultado["status"] == "avaliacao_parcial"


@pytest.mark.parametrize("consenso", [None, [], [rotulo("1", "sim", "pendente")]])
def test_sem_consenso_nao_inventa_f1(consenso):
    resultado = avaliar_previsoes([previsao("1", True)], consenso)
    assert resultado["status"] == "pendente_consenso"
    assert resultado["f1"] is resultado["precisao"] is resultado["recall"] is None
    assert resultado["atingiu_meta"] is None


def test_somente_negativos_nao_provam_f1_da_classe_positiva():
    resultado = avaliar_previsoes([previsao("1", "False")], [rotulo("1", "nao")])
    assert resultado["matriz_confusao"]["tn"] == 1
    assert resultado["f1"] is None and resultado["status"] == "f1_indefinido_sem_positivos"


def test_sem_preditos_positivos_mas_fn_presente_f1_zero():
    resultado = avaliar_previsoes([previsao("1", False)], [rotulo("1", "sim")])
    assert resultado["f1"] == resultado["recall"] == 0
    assert resultado["precisao"] is None and resultado["status"] == "requer_refinamento"


def test_sem_previsoes_conclusivas_status_pendente():
    resultado = avaliar_previsoes([], [rotulo("1", "sim")])
    assert resultado["n_ausentes"] == 1 and resultado["status"] == "pendente_previsoes_conclusivas"


@pytest.mark.parametrize("previsoes,consenso,erro", [
    ([previsao("1", True)] * 2, [], "Previsão duplicada"),
    ([], [rotulo("1", "sim")] * 2, "Consenso duplicado"),
    ([], [rotulo("1", "", "maioria")], "sem rótulo"),
    ([], [rotulo("1", "incerto")], "booleano inválido"),
    ([], [rotulo("1", "sim", "inventado")], "Método de consenso"),
    ([{"corretiva": True}], [], "sem full_name"),
])
def test_validacao_estrita(previsoes, consenso, erro):
    with pytest.raises(ValueError, match=erro):
        avaliar_previsoes(previsoes, consenso)


def release(tag, data, mensagens=(), **campos):
    return {"full_name": "o/r", "tag_name": tag, "published_at": data,
            "draft": False, "prerelease": False, "commits_status": "ok",
            "commits_novos": len(mensagens), "commits": [{"sha": str(i), "message": m}
                                                          for i, m in enumerate(mensagens)], **campos}


def test_avalia_release_corretiva_propria_mesmo_censurada_nunca_falhou():
    releases = [release("v1.0.0", "2026-01-01T00:00:00Z"),
                release("v1.0.1", "2026-01-03T00:00:00Z", ["fixes regression"])]
    consenso = [rotulo("v1.0.1", "sim")]
    resultado = avaliar_versoes(releases, consenso, "2026-01-01", "2026-01-04")
    assert resultado[0]["f1"] == 0 and resultado[0]["status"] == "requer_refinamento"
    assert resultado[1]["f1"] == 1 and resultado[1]["matriz_confusao"]["tp"] == 1
    assert resultado[1]["alvo"] == "corretiva_da_propria_release"


def test_apenas_estaveis_da_janela_avaliadas_contexto_anterior_preservado():
    releases = [release("v1.0.0", "2025-12-31T00:00:00Z"),
                release("v1.0.1", "2026-01-02T00:00:00Z", ["fix"]),
                release("v1.0.2", "2026-01-03T00:00:00Z", ["fix"], prerelease=True)]
    resultado = avaliar_versoes(releases, [rotulo("v1.0.1", "sim")], "2026-01-01", "2026-01-31")
    assert all(v["n_previsoes"] == 1 and v["f1"] == 1 for v in resultado)


def test_le_consenso_gerado_pela_pessoa_a(tmp_path):
    repos = pd.DataFrame([["o/r", "biblioteca/framework", "sim"]],
                         columns=["full_name", "tipo_projeto", "entregas_reais"])
    rels = pd.DataFrame([["o/r", "v1.0.1", "sim"]], columns=["full_name", "tag_name", "corretiva"])
    avaliadores = {letra: {"repositorios": repos, "releases": rels} for letra in "ABC"}
    consenso, _ = consolidar(avaliadores, {})
    caminho = tmp_path / "consenso_releases.csv"
    consenso["releases"].to_csv(caminho, index=False)
    resultado = avaliar_previsoes([previsao("v1.0.1", True)], carregar_consenso(caminho))
    assert resultado["f1"] == 1 and resultado["n_rotulados"] == 1


def preparar_cli(tmp_path):
    releases, commits = tmp_path / "releases.csv", tmp_path / "commits.csv"
    with releases.open("w", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=["full_name", "tag_name", "published_at",
                                                       "draft", "prerelease", "commits_status", "commits_novos"])
        escritor.writeheader()
        escritor.writerow({"full_name": "o/r", "tag_name": "v1.0.0", "published_at": "2026-01-01T00:00:00Z",
                            "draft": "False", "prerelease": "False", "commits_status": "sem_commits", "commits_novos": "0"})
    commits.write_text("full_name,tag_name,sha,message\n")
    return ["--releases", str(releases), "--commits", str(commits), "--inicio", "2026-01-01", "--fim", "2026-01-31",
            "--consenso", str(tmp_path / "sem_consenso.csv"), "--saida", str(tmp_path / "resultado.json"),
            "--historico", str(tmp_path / "historico.jsonl")]


def test_cli_registra_versoes_hashes_e_pendencia_sem_inventar_resultados(tmp_path):
    args = preparar_cli(tmp_path)
    resultado = main(args)
    assert resultado["versao_selecionada"] is None
    assert all(v["status"] == "pendente_consenso" and v["f1"] is None for v in resultado["avaliacoes"])
    linhas = [json.loads(linha) for linha in (tmp_path / "historico.jsonl").read_text().splitlines()]
    assert [linha["versao"] for linha in linhas] == ["v1", "v2"]
    assert all(len(linha["entradas"]["releases"]["sha256"]) == 64 for linha in linhas)
    assert linhas[0]["entradas"]["consenso"]["presente"] is False
    assert linhas[0]["parametros"]["limiar_f1"] == 0.7
    assert linhas[0]["executado_em_utc"] and linhas[0]["definicao"]
    fontes_antes = {nome: (tmp_path / nome).read_bytes() for nome in ("releases.csv", "commits.csv")}
    (tmp_path / "sem_consenso.csv").write_text(
        "full_name,tag_name,corretiva,metodo_corretiva\no/r,v1.0.0,sim,maioria\n")
    main(args)
    historico = [json.loads(linha) for linha in (tmp_path / "historico.jsonl").read_text().splitlines()]
    assert len(historico) == 4 and historico[:2] == linhas
    ultimo = json.loads((tmp_path / "resultado.json").read_text())
    assert ultimo["entradas"]["consenso"]["presente"] is True
    assert ultimo["avaliacoes"][0]["n_rotulados"] == 1
    assert ultimo["avaliacoes"][0]["status"] == "pendente_previsoes_conclusivas"
    assert all((tmp_path / nome).read_bytes() == conteudo for nome, conteudo in fontes_antes.items())
    assert not list(tmp_path.glob("*.tmp"))


def test_cli_nao_sobrescreve_fontes_nem_confunde_relatorio_com_historico(tmp_path):
    args = preparar_cli(tmp_path)
    args[args.index("--saida") + 1] = str(tmp_path / "releases.csv")
    with pytest.raises(SystemExit):
        main(args)
    args[args.index("--saida") + 1] = str(tmp_path / "resultado.json")
    args[args.index("--historico") + 1] = str(tmp_path / "releases.csv")
    with pytest.raises(SystemExit):
        main(args)
    args[args.index("--historico") + 1] = str(tmp_path / "resultado.json")
    with pytest.raises(SystemExit):
        main(args)


def test_cli_usa_janela_configurada_quando_omitida(tmp_path):
    args = preparar_cli(tmp_path)
    for opcao in ("--inicio", "--fim"):
        indice = args.index(opcao)
        del args[indice:indice + 2]
    config = tmp_path / "config.yaml"
    config.write_text("janela:\n  inicio: 2026-01-01\n  fim: 2026-01-31\n")
    args.extend(["--config", str(config)])
    assert main(args)["parametros"]["inicio"] == "2026-01-01"


@pytest.mark.parametrize("conteudo", ["janela: [", "{}", "janela: {}", "janela: null",
                                     "janela:\n  inicio: 42\n  fim: 2026-01-31\n"])
def test_cli_config_invalida_tem_erro_legivel_sem_traceback(tmp_path, capsys, conteudo):
    args = preparar_cli(tmp_path)
    for opcao in ("--inicio", "--fim"):
        indice = args.index(opcao)
        del args[indice:indice + 2]
    config = tmp_path / "config.yaml"
    config.write_text(conteudo)
    args.extend(["--config", str(config)])
    with pytest.raises(SystemExit) as erro:
        main(args)
    assert erro.value.code == 2
    mensagem = capsys.readouterr().err
    assert "error:" in mensagem and "Traceback" not in mensagem
    assert not (tmp_path / "resultado.json").exists()


@pytest.mark.parametrize("tipo", ["ausente", "colunas", "csv_malformado"])
def test_cli_erros_de_entrada_sao_legiveis(tmp_path, capsys, tipo):
    args = preparar_cli(tmp_path)
    commits = tmp_path / "commits.csv"
    if tipo == "ausente":
        commits.unlink()
    elif tipo == "colunas":
        commits.write_text("full_name,tag_name,sha\n")
    else:
        commits.write_text('full_name,tag_name,sha,message\no/r,v1.0.0,abc,"fix\n')
    with pytest.raises(SystemExit) as erro:
        main(args)
    assert erro.value.code == 2
    mensagem = capsys.readouterr().err
    assert "error:" in mensagem and "Traceback" not in mensagem
    assert not (tmp_path / "resultado.json").exists()
