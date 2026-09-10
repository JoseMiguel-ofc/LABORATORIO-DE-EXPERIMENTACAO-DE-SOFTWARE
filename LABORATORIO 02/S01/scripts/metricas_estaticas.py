#!/usr/bin/env python3

import argparse
import csv
import os
import sys

try:
    from radon.raw import analyze
    from radon.complexity import cc_visit
except ImportError:
    sys.exit(
        "Radon não está instalado. Rode:\n"
        "  pip install -r requirements.txt"
    )


PASTA_SCRIPT = os.path.dirname(os.path.abspath(__file__))

PASTA_SOLUCOES_PADRAO = os.path.abspath(
    os.path.join(PASTA_SCRIPT, "..", "..", "solucoes")
)

ARQUIVO_SAIDA_PADRAO = os.path.abspath(
    os.path.join(
        PASTA_SCRIPT, "..", "..", "S02", "resultados", "metricas_estaticas.csv"
    )
)

CAMPOS = [
    "integrante",
    "kata",
    "tratamento",
    "arquivo",
    "loc",
    "lloc",
    "sloc",
    "comentarios",
    "linhas_em_branco",
    "num_blocos",
    "complexidade_total",
    "complexidade_media",
    "complexidade_maxima",
    "erro",
]


def identificar_trial(nome_arquivo):
    nome, _ = os.path.splitext(nome_arquivo)
    partes = nome.split("__")

    if len(partes) != 3:
        return None

    integrante, kata, tratamento = partes
    tratamento = tratamento.upper()

    if tratamento not in ("COM_IA", "SEM_IA"):
        return None

    return integrante, kata, tratamento


def analisar_arquivo(caminho):
    with open(caminho, "r", encoding="utf-8") as arquivo:
        codigo = arquivo.read()

    metricas_brutas = analyze(codigo)
    blocos = cc_visit(codigo)

    complexidades = [bloco.complexity for bloco in blocos]

    return {
        "loc": metricas_brutas.loc,
        "lloc": metricas_brutas.lloc,
        "sloc": metricas_brutas.sloc,
        "comentarios": metricas_brutas.comments,
        "linhas_em_branco": metricas_brutas.blank,
        "num_blocos": len(complexidades),
        "complexidade_total": sum(complexidades) if complexidades else 0,
        "complexidade_media": (
            round(sum(complexidades) / len(complexidades), 2)
            if complexidades
            else 0
        ),
        "complexidade_maxima": max(complexidades) if complexidades else 0,
    }


def coletar_arquivos_python(pasta):
    if not os.path.isdir(pasta):
        return []

    return sorted(
        os.path.join(pasta, nome)
        for nome in os.listdir(pasta)
        if nome.endswith(".py")
    )


def processar_pasta(pasta):
    linhas = []

    for caminho in coletar_arquivos_python(pasta):
        nome_arquivo = os.path.basename(caminho)
        trial = identificar_trial(nome_arquivo)

        linha = {campo: "" for campo in CAMPOS}
        linha["arquivo"] = nome_arquivo

        if trial is None:
            linha["erro"] = (
                "Nome fora do padrão "
                "integrante__kata__tratamento.py"
            )
            linhas.append(linha)
            continue

        integrante, kata, tratamento = trial
        linha["integrante"] = integrante
        linha["kata"] = kata
        linha["tratamento"] = tratamento

        try:
            linha.update(analisar_arquivo(caminho))
        except SyntaxError as erro:
            linha["erro"] = f"Erro de sintaxe: {erro}"

        linhas.append(linha)

    return linhas


def processar_arquivo_unico(caminho, integrante, kata, tratamento):
    linha = {campo: "" for campo in CAMPOS}
    linha["arquivo"] = os.path.basename(caminho)
    linha["integrante"] = integrante
    linha["kata"] = kata
    linha["tratamento"] = tratamento.upper()

    try:
        linha.update(analisar_arquivo(caminho))
    except SyntaxError as erro:
        linha["erro"] = f"Erro de sintaxe: {erro}"

    return [linha]


def salvar_resultados(linhas, caminho_saida):
    pasta_saida = os.path.dirname(caminho_saida)

    if pasta_saida:
        os.makedirs(pasta_saida, exist_ok=True)

    with open(caminho_saida, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CAMPOS)
        escritor.writeheader()
        escritor.writerows(linhas)


def exibir_resumo(linhas):
    print("\n=== LAB02 - Métricas Estáticas ===\n")

    for linha in linhas:
        if linha["erro"]:
            print(f"[ERRO] {linha['arquivo']}: {linha['erro']}")
            continue

        print(
            f"{linha['arquivo']}: "
            f"LOC={linha['loc']} "
            f"SLOC={linha['sloc']} "
            f"CC_total={linha['complexidade_total']} "
            f"CC_media={linha['complexidade_media']} "
            f"CC_max={linha['complexidade_maxima']}"
        )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Calcula LOC e complexidade ciclomática (via Radon) das "
            "soluções dos katas do Laboratório 02."
        )
    )

    parser.add_argument(
        "--pasta",
        default=PASTA_SOLUCOES_PADRAO,
        help=(
            "Pasta com os arquivos .py das soluções, nomeados como "
            "integrante__kata__tratamento.py "
            f"(padrão: {PASTA_SOLUCOES_PADRAO})"
        ),
    )
    parser.add_argument(
        "--saida",
        default=ARQUIVO_SAIDA_PADRAO,
        help=f"Caminho do CSV de saída (padrão: {ARQUIVO_SAIDA_PADRAO})",
    )
    parser.add_argument(
        "--arquivo",
        help="Analisa um único arquivo .py em vez da pasta inteira",
    )
    parser.add_argument("--integrante", help="Usado junto com --arquivo")
    parser.add_argument("--kata", help="Usado junto com --arquivo")
    parser.add_argument(
        "--tratamento",
        choices=["COM_IA", "SEM_IA"],
        help="Usado junto com --arquivo",
    )

    args = parser.parse_args()

    if args.arquivo:
        if not (args.integrante and args.kata and args.tratamento):
            parser.error(
                "--arquivo requer --integrante, --kata e --tratamento"
            )

        linhas = processar_arquivo_unico(
            args.arquivo, args.integrante, args.kata, args.tratamento
        )
    else:
        linhas = processar_pasta(args.pasta)

        if not linhas:
            print(f"Nenhum arquivo .py encontrado em: {args.pasta}")
            return

    exibir_resumo(linhas)
    salvar_resultados(linhas, args.saida)

    print(f"\nResultados salvos em: {args.saida}")


if __name__ == "__main__":
    main()
