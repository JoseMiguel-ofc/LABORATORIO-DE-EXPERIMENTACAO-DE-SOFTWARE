"""CLI reproduzível de Q1/Q2; --todas-situacoes inclui o complemento Q3."""

import argparse
import sys
from pathlib import Path

from src.cenario import ALFA, SEMENTE, ajustar_cenario
from src.motor import RAIZ, RESULTADOS, executar_grade, salvar_resultados


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reps", type=int, default=10_000,
                        help="Repetições por configuração; a entrega usa 10000.")
    parser.add_argument("--n", type=int, default=30, help="Tamanho de cada grupo; n_pequeno usa 10.")
    parser.add_argument("--alfa", type=float, default=ALFA)
    parser.add_argument("--semente", type=int, default=SEMENTE)
    parser.add_argument("--tamanho-lote", type=int, default=500)
    parser.add_argument("--todas-situacoes", action="store_true",
                        help="Recalcula Q1/Q2/Q3 e substitui integralmente o CSV de saída.")
    parser.add_argument("--saida", type=Path, default=RESULTADOS,
                        help="CSV; caminhos relativos são resolvidos pela pasta do Lab04.")
    args = parser.parse_args(argv)
    caminho = args.saida if args.saida.is_absolute() else RAIZ / args.saida
    cenario = ajustar_cenario()
    try:
        novos = executar_grade(reps=args.reps, todas_situacoes=args.todas_situacoes,
                                n=args.n, alfa=args.alfa, semente=args.semente,
                                tamanho_lote=args.tamanho_lote, cenario=cenario,
                                progresso=lambda indice, total, situacao, efeito:
                                print(f"[{indice}/{total}] {situacao}, efeito={efeito:.0%}...",
                                      flush=True))
        configuracao = vars(args).copy()
        configuracao["saida"] = str(caminho)
        total = salvar_resultados(novos, caminho, cenario=cenario, configuracao=configuracao,
                                  substituir=args.todas_situacoes)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(novos[["situacao", "efeito", "n", "teste", "reps", "taxa_rejeicao", "ic_inf", "ic_sup"]]
          .to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print(f"\nSalvo: {caminho} ({len(total)} linhas; semente {args.semente}).")
    if args.reps < 10_000:
        print("Execução rápida: para a entrega, repita com --reps 10000.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
