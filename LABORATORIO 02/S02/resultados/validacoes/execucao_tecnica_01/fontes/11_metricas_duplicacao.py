#!/usr/bin/env python3
"""Detecta blocos de código duplicados entre/dentro das soluções dos katas."""

import argparse
import csv
import os


PASTA_SCRIPT = os.path.dirname(os.path.abspath(__file__))

PASTA_SOLUCOES_PADRAO = os.path.abspath(
    os.path.join(PASTA_SCRIPT, "..", "..", "solucoes")
)

ARQUIVO_SAIDA_PADRAO = os.path.abspath(
    os.path.join(
        PASTA_SCRIPT, "..", "resultados", "metricas_duplicacao.csv"
    )
)

TAMANHO_BLOCO_PADRAO = 4

CAMPOS = [
    "integrante",
    "kata",
    "tratamento",
    "arquivo",
    "linhas_comparaveis",
    "linhas_duplicadas",
    "percentual_duplicacao",
    "blocos_duplicados",
    "arquivos_relacionados",
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


def coletar_arquivos_python(pasta):
    if not os.path.isdir(pasta):
        return []

    return sorted(
        os.path.join(pasta, nome)
        for nome in os.listdir(pasta)
        if nome.endswith(".py")
    )


def linhas_normalizadas(caminho):
    """Retorna [(numero_da_linha, linha_normalizada), ...], pulando linhas em branco e comentários puros."""
    resultado = []

    with open(caminho, "r", encoding="utf-8") as arquivo:
        for numero, linha in enumerate(arquivo, start=1):
            normalizada = linha.strip()

            if not normalizada or normalizada.startswith("#"):
                continue

            resultado.append((numero, normalizada))

    return resultado


def montar_blocos(linhas, tamanho_bloco):
    """A partir de [(numero, linha), ...], gera {hash_do_bloco: [(numero_inicial, numero_final), ...]}."""
    blocos = {}

    for indice in range(len(linhas) - tamanho_bloco + 1):
        janela = linhas[indice:indice + tamanho_bloco]
        chave = tuple(linha for _, linha in janela)

        intervalo = (janela[0][0], janela[-1][0])
        blocos.setdefault(chave, []).append(intervalo)

    return blocos


def detectar_duplicacoes(arquivos, tamanho_bloco):
    """Retorna, por arquivo: linhas duplicadas, quantidade de blocos duplicados e arquivos relacionados."""
    linhas_por_arquivo = {
        arquivo: linhas_normalizadas(arquivo) for arquivo in arquivos
    }

    ocorrencias_globais = {}

    for arquivo, linhas in linhas_por_arquivo.items():
        blocos = montar_blocos(linhas, tamanho_bloco)

        for chave, intervalos in blocos.items():
            for inicio, fim in intervalos:
                ocorrencias_globais.setdefault(chave, []).append(
                    (arquivo, inicio, fim)
                )

    grupos_duplicados = [
        ocorrencias
        for ocorrencias in ocorrencias_globais.values()
        if len(ocorrencias) > 1
    ]

    resultado = {
        arquivo: {
            "linhas_comparaveis": len(linhas_por_arquivo[arquivo]),
            "linhas_duplicadas": set(),
            "blocos_duplicados": 0,
            "arquivos_relacionados": set(),
        }
        for arquivo in arquivos
    }

    for ocorrencias in grupos_duplicados:
        arquivos_no_grupo = {arquivo for arquivo, _, _ in ocorrencias}

        for arquivo, inicio, fim in ocorrencias:
            info = resultado[arquivo]
            info["linhas_duplicadas"].update(range(inicio, fim + 1))
            info["arquivos_relacionados"].update(
                outro for outro in arquivos_no_grupo if outro != arquivo
            )

    for info in resultado.values():
        info["blocos_duplicados"] = contar_regioes_contiguas(
            info["linhas_duplicadas"]
        )

    return resultado


def contar_regioes_contiguas(numeros_de_linha):
    """Conta quantas faixas contínuas de linhas existem em um conjunto de números de linha."""
    if not numeros_de_linha:
        return 0

    ordenados = sorted(numeros_de_linha)
    regioes = 1

    for anterior, atual in zip(ordenados, ordenados[1:]):
        if atual - anterior > 1:
            regioes += 1

    return regioes


def processar_pasta(pasta, tamanho_bloco):
    arquivos = coletar_arquivos_python(pasta)
    duplicacoes = detectar_duplicacoes(arquivos, tamanho_bloco)

    linhas_csv = []

    for caminho in arquivos:
        nome_arquivo = os.path.basename(caminho)
        trial = identificar_trial(nome_arquivo)

        linha = {campo: "" for campo in CAMPOS}
        linha["arquivo"] = nome_arquivo

        if trial is not None:
            integrante, kata, tratamento = trial
            linha["integrante"] = integrante
            linha["kata"] = kata
            linha["tratamento"] = tratamento

        info = duplicacoes[caminho]
        comparaveis = info["linhas_comparaveis"]
        duplicadas = len(info["linhas_duplicadas"])
        percentual = (
            round(100 * duplicadas / comparaveis, 2) if comparaveis else 0
        )

        linha["linhas_comparaveis"] = comparaveis
        linha["linhas_duplicadas"] = duplicadas
        linha["percentual_duplicacao"] = percentual
        linha["blocos_duplicados"] = info["blocos_duplicados"]
        linha["arquivos_relacionados"] = ";".join(
            sorted(os.path.basename(outro) for outro in info["arquivos_relacionados"])
        )

        linhas_csv.append(linha)

    return linhas_csv


def salvar_resultados(linhas, caminho_saida):
    pasta_saida = os.path.dirname(caminho_saida)

    if pasta_saida:
        os.makedirs(pasta_saida, exist_ok=True)

    with open(caminho_saida, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CAMPOS)
        escritor.writeheader()
        escritor.writerows(linhas)


def exibir_resumo(linhas):
    print("\n=== LAB02 S02 - Duplicação de Código ===\n")

    if not linhas:
        print("Nenhum arquivo .py encontrado.")
        return

    for linha in linhas:
        print(
            f"{linha['arquivo']}: "
            f"{linha['linhas_duplicadas']}/{linha['linhas_comparaveis']} linhas duplicadas "
            f"({linha['percentual_duplicacao']}%), "
            f"{linha['blocos_duplicados']} bloco(s), "
            f"relacionado a: {linha['arquivos_relacionados'] or '-'}"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--pasta",
        default=PASTA_SOLUCOES_PADRAO,
        help=f"Pasta com os arquivos .py das soluções (padrão: {PASTA_SOLUCOES_PADRAO})",
    )
    parser.add_argument(
        "--saida",
        default=ARQUIVO_SAIDA_PADRAO,
        help=f"Caminho do CSV de saída (padrão: {ARQUIVO_SAIDA_PADRAO})",
    )
    parser.add_argument(
        "--tamanho-bloco",
        type=int,
        default=TAMANHO_BLOCO_PADRAO,
        help=(
            "Quantidade mínima de linhas consecutivas (normalizadas, sem "
            f"brancos/comentários) para considerar um bloco duplicado (padrão: {TAMANHO_BLOCO_PADRAO})"
        ),
    )

    args = parser.parse_args()

    if args.tamanho_bloco < 1:
        parser.error("--tamanho-bloco deve ser positivo")

    linhas = processar_pasta(args.pasta, args.tamanho_bloco)

    exibir_resumo(linhas)
    salvar_resultados(linhas, args.saida)

    print(f"\nResultados salvos em: {args.saida}")


if __name__ == "__main__":
    main()
