#!/usr/bin/env python3
"""Executa a mesma suíte de contrato para qualquer solução de um kata."""

import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


FUNCOES = {
    "ReposicaoEstoque": "calcular_reposicao",
    "ExcessoBagagem": "calcular_excesso",
}
PASTA_CASOS = Path(__file__).resolve().parents[1] / "testes"


def criar_teste(funcao, caso):
    def verificar():
        teste = unittest.TestCase()
        registros = [tuple(registro) for registro in caso["registros"]]
        original = deepcopy(registros)
        # Repetir detecta consumo da entrada e parte dos erros de estado global.
        for _ in range(2):
            try:
                if caso.get("erro") == "ValueError":
                    with teste.assertRaises(ValueError):
                        funcao(registros, caso["limite"])
                else:
                    resultado = funcao(registros, caso["limite"])
                    teste.assertIs(type(resultado), list)
                    for item in resultado:
                        teste.assertIs(type(item), tuple)
                        teste.assertEqual(len(item), 2)
                        teste.assertIs(type(item[0]), str)
                        teste.assertIs(type(item[1]), int)
                    esperado = [tuple(item) for item in caso["esperado"]]
                    teste.assertEqual(resultado, esperado)
            finally:
                teste.assertEqual(registros, original, "A entrada foi alterada")

    return unittest.FunctionTestCase(verificar, description=caso["nome"])


def executar_suite(kata, arquivo):
    try:
        spec = importlib.util.spec_from_file_location("solucao_trial", arquivo)
        if spec is None or spec.loader is None:
            raise ValueError("Use um arquivo Python com extensão .py")
        modulo = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = modulo
        spec.loader.exec_module(modulo)
        funcao = getattr(modulo, FUNCOES[kata])
        if not callable(funcao):
            raise TypeError(f"{FUNCOES[kata]} precisa ser uma função")
    except (Exception, SystemExit) as erro:
        print(f"Não foi possível carregar a solução: {erro}", file=sys.stderr)
        return 1

    try:
        with (PASTA_CASOS / f"{kata}.json").open(encoding="utf-8") as entrada:
            casos = json.load(entrada)
    except (OSError, ValueError) as erro:
        print(f"Não foi possível carregar os casos: {erro}", file=sys.stderr)
        return 2
    if not casos:
        print("Suíte vazia: avaliação inválida.", file=sys.stderr)
        return 2
    suite = unittest.TestSuite(criar_teste(funcao, caso) for caso in casos)
    resultado = unittest.TextTestRunner(verbosity=2).run(suite)
    aprovados = resultado.testsRun - len(resultado.failures) - len(resultado.errors)
    print(f"{kata}: {aprovados}/{resultado.testsRun} casos aprovados.", flush=True)
    return 0 if resultado.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kata", required=True, choices=FUNCOES)
    parser.add_argument("--arquivo", required=True, type=Path)
    parser.add_argument(
        "--tempo-limite", type=int, default=10,
        help="Limite em segundos para importar a solução e executar a suíte (padrão: 10)",
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.arquivo.is_file():
        parser.error(f"Arquivo inexistente: {args.arquivo}")
    if args.tempo_limite <= 0:
        parser.error("--tempo-limite deve ser positivo")
    if args.worker:
        return executar_suite(args.kata, args.arquivo.resolve())

    # O limite inclui a importação: um loop no topo do arquivo também é encerrado.
    comando = [
        sys.executable, str(Path(__file__).resolve()),
        "--kata", args.kata, "--arquivo", str(args.arquivo.resolve()), "--worker",
    ]
    try:
        return subprocess.run(comando, timeout=args.tempo_limite).returncode
    except subprocess.TimeoutExpired:
        print("Tempo limite dos testes excedido; solução não aprovada.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
