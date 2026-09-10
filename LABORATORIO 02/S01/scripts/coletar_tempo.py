#!/usr/bin/env python3

import csv
import os
import threading
import time
from datetime import datetime


TIMEBOX_MINUTOS = 35
TIMEBOX_SEGUNDOS = TIMEBOX_MINUTOS * 60

PASTA_SCRIPT = os.path.dirname(os.path.abspath(__file__))

ARQUIVO_RESULTADOS = os.path.abspath(
    os.path.join(
        PASTA_SCRIPT,
        "..",
        "..",
        "S02",
        "resultados",
        "tempos_trials.csv"
    )
)


def solicitar_dados_trial():
    print("\n=== LAB02 - Cronometragem de Trial ===\n")

    integrante = input("Integrante: ").strip()
    kata = input("Kata: ").strip()

    while True:
        tratamento = input(
            "Tratamento [COM_IA / SEM_IA]: "
        ).strip().upper()

        if tratamento in ("COM_IA", "SEM_IA"):
            break

        print("Tratamento inválido. Digite COM_IA ou SEM_IA.")

    


    return integrante, kata, tratamento


def aguardar_enter(evento_finalizacao):
    input("\nPressione ENTER quando terminar o kata...\n")
    evento_finalizacao.set()


def executar_cronometro():
    evento_finalizacao = threading.Event()

    thread_enter = threading.Thread(
        target=aguardar_enter,
        args=(evento_finalizacao,),
        daemon=True
    )

    thread_enter.start()

    inicio_monotonic = time.monotonic()

    while True:
        tempo_decorrido = time.monotonic() - inicio_monotonic

        if evento_finalizacao.is_set():
            return tempo_decorrido, False

        if tempo_decorrido >= TIMEBOX_SEGUNDOS:
            print(
                f"\nTime-box de {TIMEBOX_MINUTOS} minutos atingido."
            )

            return TIMEBOX_SEGUNDOS, True

        minutos = int(tempo_decorrido // 60)
        segundos = int(tempo_decorrido % 60)

        print(
            f"\rTempo: {minutos:02d}:{segundos:02d}",
            end="",
            flush=True
        )

        time.sleep(1)


def salvar_resultado(resultado):
    os.makedirs(
        os.path.dirname(ARQUIVO_RESULTADOS),
        exist_ok=True
    )

    arquivo_existe = os.path.exists(ARQUIVO_RESULTADOS)

    campos = [
        "integrante",
        "kata",
        "tratamento",
        "inicio",
        "fim",
        "tempo_segundos",
        "tempo_minutos",
        "censurado"
    ]

    with open(
        ARQUIVO_RESULTADOS,
        "a",
        newline="",
        encoding="utf-8"
    ) as arquivo:

        escritor = csv.DictWriter(
            arquivo,
            fieldnames=campos
        )

        if not arquivo_existe:
            escritor.writeheader()

        escritor.writerow(resultado)


def main():
    integrante, kata, tratamento = solicitar_dados_trial()

    print("\nDados do trial:")
    print(f"Integrante: {integrante}")
    print(f"Kata: {kata}")
    print(f"Tratamento: {tratamento}")
    print(f"Time-box máximo: {TIMEBOX_MINUTOS} minutos")

    input("\nPressione ENTER para iniciar o trial...")

    inicio = datetime.now()

    print("\nCronômetro iniciado!")

    tempo_segundos, censurado = executar_cronometro()

    fim = datetime.now()

    resultado = {
        "integrante": integrante,
        "kata": kata,
        "tratamento": tratamento,
        "inicio": inicio.isoformat(timespec="seconds"),
        "fim": fim.isoformat(timespec="seconds"),
        "tempo_segundos": round(tempo_segundos, 2),
        "tempo_minutos": round(tempo_segundos / 60, 2),
        "censurado": censurado
    }

    salvar_resultado(resultado)

    print("\n\n=== Trial finalizado ===")
    print(f"Tempo: {resultado['tempo_minutos']:.2f} minutos")
    print(f"Censurado: {'SIM' if censurado else 'NÃO'}")
    print(f"Resultado salvo em: {ARQUIVO_RESULTADOS}")


if __name__ == "__main__":
    main()
