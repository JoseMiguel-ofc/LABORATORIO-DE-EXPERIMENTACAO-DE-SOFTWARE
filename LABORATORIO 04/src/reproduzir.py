"""Reproduz simulações para três alfas e ICs bootstrap com um único comando."""

import argparse
import sys
from src import intervalos_efeito
from src.experimentos import argumentos, precomputar
from src.motor import RAIZ


def main(argv=None):
    parser = argumentos(argparse.ArgumentParser(description=__doc__))
    parser.add_argument("--n-resamples", type=int, default=10_000,
                        help="Reamostragens dos ICs bootstrap de 95%% (independente de --reps).")
    args = parser.parse_args(argv)
    saida = args.saida if args.saida.is_absolute() else RAIZ / args.saida
    try:
        # Valida antes de iniciar as simulações demoradas.
        if args.n_resamples < 2:
            raise ValueError("n-resamples deve ser pelo menos 2.")
        precomputar(args.reps, args.semente, args.n_max, raiz=saida, alfas=args.alfas,
                    forcar=args.forcar, progresso=lambda texto: print(texto, flush=True))
        caminho_ic = saida / "efeitos_ic.csv"
        intervalos = None
        if not args.forcar:
            try:
                candidato = intervalos_efeito.carregar_intervalos(caminho_ic)
                parametros = candidato.attrs["metadados"]["parametros"]
                if (parametros["n_resamples"] == args.n_resamples
                        and parametros["semente"] == args.semente
                        and parametros["confianca"] == 0.95):
                    intervalos = candidato
            except (OSError, ValueError, KeyError):
                pass
        if intervalos is None:
            print(f"Bootstrap: calculando ICs de 95% com {args.n_resamples} reamostragens.",
                  flush=True)
            intervalos = intervalos_efeito.gerar_intervalos_reais(
                n_resamples=args.n_resamples, confianca=0.95, semente=args.semente)
            intervalos_efeito.salvar_intervalos(intervalos, caminho_ic)
        else:
            print("Bootstrap: cache válido reutilizado.", flush=True)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(f"\nResultados salvos em: {saida}")
    if args.reps < 10_000 or args.n_resamples < 10_000:
        print("Esta execução reduzida é apenas para diagnóstico; a entrega usa 10.000 repetições.")
    return 0


# Saída redirecionada no Windows usa cp1252, que não tem α.
if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
