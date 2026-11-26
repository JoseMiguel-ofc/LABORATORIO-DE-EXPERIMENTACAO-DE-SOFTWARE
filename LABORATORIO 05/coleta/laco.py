"""Coleta em laço: uma rodada no minuto 17 de cada hora durante uma execução longa.

Motivo: na primeira semana, o agendador do GitHub disparou o workflow só a cada
6 a 12 horas, em minutos aleatórios (20 rodadas em 7 dias, ~12% das horas). Com o
laço, cada execução do workflow fica ativa por até ~5h40 e mede uma vez por hora,
sem depender de o ``cron`` disparar toda hora. O ``cron`` continua ligado para
iniciar uma nova execução assim que a anterior terminar.

Regras do laço:
- O "horário" de uma rodada vai do minuto 17 de uma hora ao minuto 16 da seguinte.
- Se o horário atual ainda não tem rodada no CSV, coleta na hora (cobre o atraso
  do agendador); senão, dorme até o próximo minuto 17.
- Depois de cada rodada roda o comando de commit (``--commit``), para os dados
  irem para o repositório mesmo se a execução for interrompida.

Uso: ``python coleta/laco.py --duracao-min 340 --commit "bash coleta/commitar.sh"``
"""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coleta.coletar import CONFIG_PADRAO, LAB05, agora_utc, carregar_config, gravar, rodada

MINUTO = 17


def horario(momento: datetime, minuto: int = MINUTO) -> datetime:
    """Início do horário de coleta que contém ``momento`` (minuto 17 da hora)."""
    base = momento.astimezone(timezone.utc) - timedelta(minutes=minuto)
    return base.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=minuto)


def ultimo_timestamp(caminho: Path) -> datetime | None:
    """Timestamp da última linha do CSV (as linhas são sempre acrescentadas no fim)."""
    if not caminho.exists():
        return None
    with open(caminho, encoding="utf-8") as arquivo:
        linhas = [linha for linha in arquivo.read().splitlines() if linha.strip()]
    if len(linhas) < 2:
        return None
    try:
        return datetime.fromisoformat(linhas[-1].split(",", 1)[0].replace("Z", "+00:00"))
    except ValueError:
        return None


def executar(config: dict, saida: Path, duracao_min: float, commit: list[str] | None = None,
             agora=agora_utc, dormir=time.sleep, coletar=None) -> int:
    """Roda o laço até ``duracao_min`` e devolve o número de rodadas feitas."""
    coletar = coletar or (lambda: rodada(config,
                                         chave_api=os.environ.get("STEAM_API_KEY") or None))
    fim = agora() + timedelta(minutes=duracao_min)
    rodadas = 0
    while True:
        atual = horario(agora())
        ultimo = ultimo_timestamp(saida)
        if ultimo is None or horario(ultimo) < atual:
            linhas = coletar()
            gravar(linhas, saida)
            rodadas += 1
            falhas = sum(1 for linha in linhas if linha["erro"])
            print(f"{agora():%Y-%m-%d %H:%M:%S} UTC: rodada {rodadas} gravada "
                  f"({falhas} com erro)", flush=True)
            if commit:
                subprocess.run(commit, check=False)
        proximo = horario(agora()) + timedelta(hours=1)
        if proximo >= fim:
            return rodadas
        dormir(max(1.0, (proximo - agora()).total_seconds() + 1))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coleta em laço, uma rodada por hora.")
    parser.add_argument("--config", type=Path, default=CONFIG_PADRAO)
    parser.add_argument("--saida", type=Path, default=None)
    parser.add_argument("--duracao-min", type=float, default=340)
    parser.add_argument("--commit", default=None,
                        help="comando executado depois de cada rodada (ex.: bash coleta/commitar.sh)")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    config = carregar_config(args.config)
    saida = args.saida or Path(config["saida"])
    if not saida.is_absolute():
        saida = LAB05 / saida
    commit = shlex.split(args.commit) if args.commit else None
    total = executar(config, saida, args.duracao_min, commit)
    print(f"Fim do laço: {total} rodadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
