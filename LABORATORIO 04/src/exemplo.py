"""Exemplo reproduzível da Sprint 1: python -m src.exemplo."""

import argparse
import json

import numpy as np

from src.cenario import ALFA, SEMENTE, ajustar_cenario
from src.simulacao import gerar
from src.testes import aplicar_testes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=30, help="Observações por grupo (padrão: 30).")
    parser.add_argument("--efeito", type=float, default=0.30,
                        help="Mudança proporcional no grupo com bot (0.30 significa +30%%).")
    args = parser.parse_args(argv)
    try:
        cenario = ajustar_cenario()
        amostras = gerar(args.n, args.efeito, "base", np.random.default_rng(SEMENTE),
                         cenario=cenario)
        testes = aplicar_testes(amostras["com_bot"], amostras["sem_bot"], alfa=ALFA)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps({
        "semente": SEMENTE, "n_por_grupo": args.n, "efeito": args.efeito,
        "parametros_base": cenario["parametros_base"], "testes": testes,
    }, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
