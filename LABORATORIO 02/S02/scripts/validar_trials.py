import csv
import os
from collections import Counter, defaultdict


CAMINHO_SCRIPT = os.path.dirname(os.path.abspath(__file__))

ARQUIVO_CSV = os.path.abspath(
    os.path.join(
        CAMINHO_SCRIPT,
        "..",
        "resultados",
        "tempos_trials.csv"
    )
)

TRIALS_ESPERADOS_TOTAL = 12
TRIALS_ESPERADOS_POR_INTEGRANTE = 4
TRIALS_COM_IA_ESPERADOS = 2
TRIALS_SEM_IA_ESPERADOS = 2

LIMITE_SEGUNDOS = 35 * 60

CAMPOS_OBRIGATORIOS = [
    "integrante",
    "kata",
    "tratamento",
    "inicio",
    "fim",
    "tempo_segundos",
    "tempo_minutos",
    "censurado"
]


def carregar_trials():
    if not os.path.exists(ARQUIVO_CSV):
        raise FileNotFoundError(
            f"Arquivo não encontrado: {ARQUIVO_CSV}"
        )

    with open(
        ARQUIVO_CSV,
        "r",
        encoding="utf-8",
        newline=""
    ) as arquivo:
        return list(csv.DictReader(arquivo))


def valor_booleano(valor):
    return str(valor).strip().lower() in (
        "true",
        "1",
        "sim",
        "yes"
    )


def validar_campos_ausentes(trials):
    erros = []

    for indice, trial in enumerate(trials, start=1):
        for campo in CAMPOS_OBRIGATORIOS:
            valor = trial.get(campo)

            if valor is None or str(valor).strip() == "":
                erros.append(
                    f"Trial {indice}: campo '{campo}' vazio."
                )

    return erros


def validar_tratamentos(trials):
    erros = []

    for indice, trial in enumerate(trials, start=1):
        tratamento = trial.get("tratamento", "").strip().upper()

        if tratamento not in ("COM_IA", "SEM_IA"):
            erros.append(
                f"Trial {indice}: tratamento inválido "
                f"('{tratamento}')."
            )

    return erros


def validar_duplicados(trials):
    erros = []

    combinacoes = [
        (
            trial.get("integrante", "").strip(),
            trial.get("kata", "").strip()
        )
        for trial in trials
    ]

    contagem = Counter(combinacoes)

    for combinacao, quantidade in contagem.items():
        if quantidade > 1:
            integrante, kata = combinacao

            erros.append(
                f"Trial duplicado: integrante='{integrante}', "
                f"kata='{kata}' ({quantidade} ocorrências)."
            )

    return erros


def validar_tempos(trials):
    erros = []

    for indice, trial in enumerate(trials, start=1):
        try:
            tempo_segundos = float(trial["tempo_segundos"])
        except (ValueError, TypeError):
            erros.append(
                f"Trial {indice}: tempo_segundos inválido."
            )
            continue

        censurado = valor_booleano(
            trial.get("censurado", "")
        )

        if tempo_segundos < 0:
            erros.append(
                f"Trial {indice}: tempo negativo."
            )

        if tempo_segundos > LIMITE_SEGUNDOS:
            erros.append(
                f"Trial {indice}: ultrapassou "
                f"{LIMITE_SEGUNDOS} segundos."
            )

        if censurado and tempo_segundos != LIMITE_SEGUNDOS:
            erros.append(
                f"Trial {indice}: marcado como censurado, "
                f"mas tempo = {tempo_segundos:.2f}s."
            )

        if (
            not censurado
            and tempo_segundos == LIMITE_SEGUNDOS
        ):
            erros.append(
                f"Trial {indice}: atingiu 35 minutos "
                f"mas não está marcado como censurado."
            )

    return erros


def validar_quantidades(trials):
    erros = []

    if len(trials) != TRIALS_ESPERADOS_TOTAL:
        erros.append(
            f"Quantidade total esperada: "
            f"{TRIALS_ESPERADOS_TOTAL}. "
            f"Encontrada: {len(trials)}."
        )

    por_integrante = defaultdict(list)

    for trial in trials:
        integrante = trial.get(
            "integrante",
            ""
        ).strip()

        por_integrante[integrante].append(trial)

    for integrante, trials_integrante in por_integrante.items():
        total = len(trials_integrante)

        com_ia = sum(
            1
            for trial in trials_integrante
            if trial.get(
                "tratamento",
                ""
            ).strip().upper() == "COM_IA"
        )

        sem_ia = sum(
            1
            for trial in trials_integrante
            if trial.get(
                "tratamento",
                ""
            ).strip().upper() == "SEM_IA"
        )

        if total != TRIALS_ESPERADOS_POR_INTEGRANTE:
            erros.append(
                f"{integrante}: esperado "
                f"{TRIALS_ESPERADOS_POR_INTEGRANTE} trials, "
                f"encontrado {total}."
            )

        if com_ia != TRIALS_COM_IA_ESPERADOS:
            erros.append(
                f"{integrante}: esperado "
                f"{TRIALS_COM_IA_ESPERADOS} trials COM_IA, "
                f"encontrado {com_ia}."
            )

        if sem_ia != TRIALS_SEM_IA_ESPERADOS:
            erros.append(
                f"{integrante}: esperado "
                f"{TRIALS_SEM_IA_ESPERADOS} trials SEM_IA, "
                f"encontrado {sem_ia}."
            )

    return erros, por_integrante


def imprimir_resumo(trials, por_integrante):
    print("\n=== RESUMO DOS TRIALS ===\n")

    print(f"Total de trials: {len(trials)}")

    for integrante in sorted(por_integrante):
        trials_integrante = por_integrante[integrante]

        com_ia = sum(
            1
            for trial in trials_integrante
            if trial.get(
                "tratamento",
                ""
            ).strip().upper() == "COM_IA"
        )

        sem_ia = sum(
            1
            for trial in trials_integrante
            if trial.get(
                "tratamento",
                ""
            ).strip().upper() == "SEM_IA"
        )

        print(f"\n{integrante}")
        print(f"  Total: {len(trials_integrante)}")
        print(f"  COM_IA: {com_ia}")
        print(f"  SEM_IA: {sem_ia}")
        katas = [
         trial.get("kata", "").strip()
            for trial in trials_integrante
        ]

        print(f"  Katas: {', '.join(katas)}")


def main():
    print("=== LAB02 S02 - Validação dos Trials ===")

    try:
        trials = carregar_trials()
    except FileNotFoundError as erro:
        print(f"\nERRO: {erro}")
        return

    erros = []

    erros.extend(
        validar_campos_ausentes(trials)
    )

    erros.extend(
        validar_tratamentos(trials)
    )

    erros.extend(
        validar_duplicados(trials)
    )

    erros.extend(
        validar_tempos(trials)
    )

    erros_quantidade, por_integrante = (
        validar_quantidades(trials)
    )

    erros.extend(erros_quantidade)

    imprimir_resumo(
        trials,
        por_integrante
    )

    print("\n=== RESULTADO DA VALIDAÇÃO ===\n")

    if erros:
        print(
            f"Dataset inválido. "
            f"{len(erros)} problema(s) encontrado(s):\n"
        )

        for erro in erros:
            print(f"- {erro}")

        print(
            "\nDataset apto para análise da Sprint 3: NÃO"
        )

    else:
        print("Nenhum problema encontrado.")
        print(
            "Dataset apto para análise da Sprint 3: SIM"
        )


if __name__ == "__main__":
    main()
