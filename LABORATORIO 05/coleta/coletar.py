"""Coleta horária de latência e disponibilidade dos serviços públicos da Steam.

Cada execução faz uma rodada: consulta os usuários online na página oficial de
estatísticas da Valve e mede cada endpoint de ``config.json``, com uma pausa de
1 s entre requisições (no máximo 1 requisição por segundo, ver docs/etica.md).
As linhas da rodada são acrescentadas ao CSV com esquema fixo:

    timestamp, endpoint, status, latencia_ms, usuarios_online, erro, jogadores_top

- ``timestamp``: início da requisição, em UTC (ISO 8601, milissegundos).
- ``status``: código HTTP; vazio quando não houve resposta (timeout, DNS...).
- ``latencia_ms``: tempo até receber a resposta completa (corpo incluído), com
  conexão nova a cada requisição (DNS + TCP + TLS).
- ``usuarios_online``: usuários online segundo a Valve, igual em toda a rodada.
- ``erro``: vazio quando a requisição deu certo; senão, o motivo da falha.
- ``jogadores_top``: soma dos jogadores atuais dos jogos monitorados (aproximação
  de usuários online pela API), igual em toda a rodada.

Uso: ``python coleta/coletar.py [--config coleta/config.json] [--saida arquivo.csv]``
O caminho de saída é relativo à pasta do Lab05, não ao diretório atual.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

LAB05 = Path(__file__).resolve().parent.parent
CONFIG_PADRAO = Path(__file__).resolve().parent / "config.json"
COLUNAS = ["timestamp", "endpoint", "status", "latencia_ms", "usuarios_online",
           "erro", "jogadores_top"]


def agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def formatar_ts(momento: datetime) -> str:
    return momento.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z")


def carregar_config(caminho: Path = CONFIG_PADRAO) -> dict:
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def medir(sessao: requests.Session, url: str, timeout: float,
          params: dict | None = None) -> dict:
    """Faz um GET e devolve horário, status, latência, resposta e erro (sem lançar)."""
    inicio = agora_utc()
    t0 = time.perf_counter()
    try:
        resposta = sessao.get(url, timeout=timeout, params=params)
        latencia = (time.perf_counter() - t0) * 1000
        erro = "" if resposta.ok else f"HTTP {resposta.status_code}"
        return {"timestamp": inicio, "status": resposta.status_code,
                "latencia_ms": latencia, "erro": erro, "resposta": resposta}
    except requests.RequestException as exc:
        latencia = (time.perf_counter() - t0) * 1000
        # Só o nome da exceção: a mensagem pode conter a URL (e a chave da API).
        return {"timestamp": inicio, "status": None, "latencia_ms": latencia,
                "erro": type(exc).__name__, "resposta": None}


def ler_json(medicao: dict):
    """Corpo JSON da resposta, ou None se não houver resposta válida."""
    resposta = medicao["resposta"]
    if resposta is None or not resposta.ok:
        return None
    try:
        return resposta.json()
    except ValueError:
        return None


def extrair_usuarios_online(dados, campo: str) -> int | None:
    """A Valve devolve o número como texto com separador de milhar ("31,902,845")."""
    try:
        return int(str(dados[campo]).replace(",", "").replace(".", "").strip())
    except (KeyError, TypeError, ValueError):
        return None


def extrair_jogadores(dados) -> int | None:
    try:
        resposta = dados["response"]
        if resposta.get("result") != 1:
            return None
        return int(resposta["player_count"])
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def rodada(config: dict, sessao: requests.Session | None = None,
           dormir=time.sleep, chave_api: str | None = None) -> list[dict]:
    """Executa uma rodada completa e devolve as linhas já no formato do CSV.

    Sem ``sessao`` (uso normal), cada requisição abre uma conexão nova: todas as
    latências incluem DNS, TCP e TLS. Reaproveitar a conexão faria a primeira
    requisição a cada domínio parecer bem mais lenta que as seguintes.
    """
    timeout = config.get("timeout_s", 15)
    pausa = max(1.0, float(config.get("pausa_s", 1.0)))  # nunca mais de 1 req/s

    alvos = [dict(config["usuarios_online"], tipo="usuarios")]
    alvos += [dict(endpoint, tipo="endpoint") for endpoint in config["endpoints"]]

    linhas, usuarios, jogadores = [], None, []
    for i, alvo in enumerate(alvos):
        if i:
            dormir(pausa)
        params = {"key": chave_api} if alvo.get("usa_chave") and chave_api else None
        atual = sessao or requests.Session()
        atual.headers["User-Agent"] = config["user_agent"]
        try:
            medicao = medir(atual, alvo["url"], timeout, params=params)  # corpo já lido
        finally:
            if sessao is None:
                atual.close()
        erro = medicao["erro"]

        if alvo["tipo"] == "usuarios":
            usuarios = extrair_usuarios_online(ler_json(medicao), alvo["campo"])
            if usuarios is None and not erro:
                erro = "resposta sem usuarios_online"
        elif alvo.get("jogadores"):
            contagem = extrair_jogadores(ler_json(medicao))
            jogadores.append(contagem)
            if contagem is None and not erro:
                erro = "resposta sem player_count"

        linhas.append({"timestamp": formatar_ts(medicao["timestamp"]),
                       "endpoint": alvo["nome"],
                       "status": "" if medicao["status"] is None else medicao["status"],
                       "latencia_ms": f"{medicao['latencia_ms']:.1f}",
                       "erro": erro})

    # A soma só vale se todos os jogos responderem; senão fica vazia, para não
    # misturar somas de 2 e de 3 jogos na mesma série.
    soma = sum(jogadores) if jogadores and None not in jogadores else ""
    for linha in linhas:
        linha["usuarios_online"] = "" if usuarios is None else usuarios
        linha["jogadores_top"] = soma
    return linhas


def gravar(linhas: list[dict], caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    novo = not caminho.exists() or caminho.stat().st_size == 0
    with open(caminho, "a", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS, lineterminator="\n")
        if novo:
            escritor.writeheader()
        escritor.writerows(linhas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=CONFIG_PADRAO)
    parser.add_argument("--saida", type=Path, default=None,
                        help="CSV de saída (padrão: o definido no config)")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):  # console do Windows usa cp1252
        sys.stdout.reconfigure(encoding="utf-8")

    config = carregar_config(args.config)
    saida = args.saida or Path(config["saida"])
    if not saida.is_absolute():
        saida = LAB05 / saida

    linhas = rodada(config, chave_api=os.environ.get("STEAM_API_KEY") or None)
    gravar(linhas, saida)
    falhas = sum(1 for linha in linhas if linha["erro"])
    print(f"{len(linhas)} medições gravadas em {saida} ({falhas} com erro)")
    for linha in linhas:
        print(f"  {linha['endpoint']:<34} {str(linha['status']):>4} "
              f"{linha['latencia_ms']:>9} ms  {linha['erro']}")
    # Falhas dos endpoints são dados do estudo, não erro do coletor: sai com 0.
    return 0


if __name__ == "__main__":
    sys.exit(main())
