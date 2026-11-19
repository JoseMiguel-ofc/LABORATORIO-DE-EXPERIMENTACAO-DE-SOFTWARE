import csv

import requests

from coleta import coletar
from coleta.coletar import COLUNAS, carregar_config, gravar, rodada


class RespostaFalsa:
    def __init__(self, status=200, corpo=None):
        self.status_code = status
        self.ok = 200 <= status < 300
        self._corpo = corpo

    def json(self):
        if self._corpo is None:
            raise ValueError("sem JSON")
        return self._corpo


class SessaoFalsa:
    """Responde por trecho de URL; registra as chamadas."""

    def __init__(self, respostas):
        self.respostas = respostas
        self.headers = {}
        self.chamadas = []

    def get(self, url, timeout=None, params=None):
        self.chamadas.append({"url": url, "timeout": timeout, "params": params})
        for trecho, resposta in self.respostas.items():
            if trecho in url:
                if isinstance(resposta, Exception):
                    raise resposta
                return resposta
        return RespostaFalsa(200, {})


def respostas_ok():
    return {"about/stats": RespostaFalsa(200, {"users_online": "31,902,845"}),
            "appid=730": RespostaFalsa(200, {"response": {"player_count": 900000, "result": 1}}),
            "appid=570": RespostaFalsa(200, {"response": {"player_count": 600000, "result": 1}}),
            "appid=578080": RespostaFalsa(200, {"response": {"player_count": 300000, "result": 1}})}


def sem_pausa(segundos):
    pass


def test_rodada_mede_todos_os_alvos_com_pausa_de_1s():
    config = carregar_config()
    sessao, pausas = SessaoFalsa(respostas_ok()), []
    linhas = rodada(config, sessao=sessao, dormir=pausas.append)

    assert len(linhas) == 1 + len(config["endpoints"])
    assert pausas == [1.0] * (len(linhas) - 1)
    assert all(c["timeout"] == config["timeout_s"] for c in sessao.chamadas)
    assert "projeto academico" in sessao.headers["User-Agent"]
    assert {l["usuarios_online"] for l in linhas} == {31902845}
    assert {l["jogadores_top"] for l in linhas} == {1800000}
    assert all(l["erro"] == "" and l["status"] == 200 for l in linhas)
    assert all(l["timestamp"].endswith("Z") for l in linhas)


def test_pausa_nunca_fica_abaixo_de_1s():
    config = dict(carregar_config(), pausa_s=0.1)
    pausas = []
    rodada(config, sessao=SessaoFalsa(respostas_ok()), dormir=pausas.append)
    assert min(pausas) == 1.0


def test_falhas_viram_linhas_com_erro_sem_vazar_a_url():
    respostas = respostas_ok()
    respostas["appid=570"] = requests.Timeout("https://x/?key=SEGREDO")
    respostas["appdetails"] = RespostaFalsa(503)
    linhas = {l["endpoint"]: l for l in rodada(carregar_config(), sessao=SessaoFalsa(respostas),
                                                dormir=sem_pausa)}

    assert linhas["GetNumberOfCurrentPlayers_570"]["status"] == ""
    assert linhas["GetNumberOfCurrentPlayers_570"]["erro"] == "Timeout"
    assert linhas["appdetails"]["erro"] == "HTTP 503"
    # Um jogo sem resposta: a soma fica vazia em vez de somar só 2 jogos.
    assert {l["jogadores_top"] for l in linhas.values()} == {""}
    assert all("SEGREDO" not in str(l) for l in linhas.values())


def test_resposta_200_sem_o_campo_esperado_conta_como_erro():
    respostas = respostas_ok()
    respostas["about/stats"] = RespostaFalsa(200, {"outra": 1})
    respostas["appid=730"] = RespostaFalsa(200, {"response": {"result": 42}})
    linhas = {l["endpoint"]: l for l in rodada(carregar_config(), sessao=SessaoFalsa(respostas),
                                                dormir=sem_pausa)}
    assert linhas["ValveStats"]["erro"] == "resposta sem usuarios_online"
    assert linhas["ValveStats"]["usuarios_online"] == ""
    assert linhas["GetNumberOfCurrentPlayers_730"]["erro"] == "resposta sem player_count"


def test_chave_so_vai_para_endpoints_marcados():
    config = carregar_config()
    config["endpoints"][0]["usa_chave"] = True
    sessao = SessaoFalsa(respostas_ok())
    rodada(config, sessao=sessao, dormir=sem_pausa, chave_api="abc")
    com_chave = [c for c in sessao.chamadas if c["params"]]
    assert len(com_chave) == 1 and com_chave[0]["params"] == {"key": "abc"}


def test_gravar_cria_cabecalho_uma_vez_e_acrescenta(tmp_path):
    destino = tmp_path / "sub" / "coleta.csv"
    linha = {"timestamp": "2026-11-19T19:17:00.000Z", "endpoint": "GetServerInfo",
             "status": 200, "latencia_ms": "10.0", "usuarios_online": 1, "erro": "",
             "jogadores_top": 2}
    gravar([linha], destino)
    gravar([linha], destino)
    with open(destino, encoding="utf-8", newline="") as arquivo:
        conteudo = arquivo.read()
    assert "\r" not in conteudo
    linhas = list(csv.reader(conteudo.splitlines()))
    assert linhas[0] == COLUNAS and len(linhas) == 3


def test_main_grava_no_caminho_pedido(tmp_path, monkeypatch):
    monkeypatch.setattr(coletar, "rodada", lambda config, chave_api=None: [
        {"timestamp": "t", "endpoint": "e", "status": 200, "latencia_ms": "1.0",
         "usuarios_online": "", "erro": "", "jogadores_top": ""}])
    destino = tmp_path / "saida.csv"
    assert coletar.main(["--saida", str(destino)]) == 0
    assert destino.read_text(encoding="utf-8").startswith("timestamp,endpoint")
