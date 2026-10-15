"""Concordância entre avaliadores pelo kappa de Fleiss, nas três dimensões.

Uso: ``python -m validacao.kappa`` (depois que os rotulos_*.xlsx estiverem preenchidos)

Itens sem rótulo de algum avaliador ficam fora do cálculo e são contados.
"""

import argparse
from pathlib import Path
import warnings

import pandas as pd
from statsmodels.stats.inter_rater import aggregate_raters, fleiss_kappa

from validacao.rotulos import DIMENSOES, PASTA, carregar_avaliadores, tabela_da_dimensao


# Landis & Koch (1977): limite superior (inclusivo) de cada faixa.
FAIXAS_LANDIS_KOCH = [(0.20, "leve"), (0.40, "razoável"), (0.60, "moderada"),
                      (0.80, "substancial"), (1.00, "quase perfeita")]


def interpretar(kappa):
    if kappa is None:
        return "indefinido"
    if kappa < 0:
        return "pobre"
    for limite, nome in FAIXAS_LANDIS_KOCH:
        if kappa <= limite:
            return nome
    return FAIXAS_LANDIS_KOCH[-1][1]


def calcular_kappa(tabela, categorias):
    """Kappa de Fleiss de uma tabela itens × avaliadores com rótulos de ``categorias``.

    O kappa fica indefinido (``None``) quando todos usam uma única categoria em
    todos os itens: não há variação para separar concordância de acaso.
    """
    completos = tabela.dropna()
    resultado = {"itens": len(completos), "itens_incompletos": len(tabela) - len(completos),
                 "avaliadores": tabela.shape[1], "kappa": None,
                 "unanimidade": None}
    if completos.empty:
        return resultado
    codigos = completos.apply(lambda coluna: coluna.map(categorias.index)).to_numpy(dtype=int)
    contagens, _ = aggregate_raters(codigos, n_cat=len(categorias))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # 0/0 quando só há uma categoria
        kappa = float(fleiss_kappa(contagens, method="fleiss"))
    resultado["kappa"] = None if pd.isna(kappa) else kappa
    resultado["unanimidade"] = float((contagens.max(axis=1) == tabela.shape[1]).mean())
    return resultado


def calcular_todas(avaliadores):
    linhas = []
    for dimensao, (_, categorias) in DIMENSOES.items():
        resultado = calcular_kappa(tabela_da_dimensao(avaliadores, dimensao), categorias)
        linhas.append({"dimensao": dimensao, **resultado,
                       "interpretacao": interpretar(resultado["kappa"])})
    return pd.DataFrame(linhas)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Kappa de Fleiss da amostra-ouro")
    parser.add_argument("--pasta", default=PASTA)
    args = parser.parse_args(argv)
    pasta = Path(args.pasta)

    avaliadores = carregar_avaliadores(pasta)
    if len(avaliadores) < 2:
        raise SystemExit(f"Encontrei {len(avaliadores)} arquivo(s) rotulos_*.xlsx em {pasta}; "
                         "são necessários pelo menos 2 (o protocolo prevê 3).")
    resultados = calcular_todas(avaliadores)
    resultados.to_csv(pasta / "resultado_kappa.csv", index=False)
    print(f"Avaliadores: {', '.join(avaliadores)}")
    print(resultados.to_string(index=False, float_format=lambda x: f"{x:.3f}"))


if __name__ == "__main__":
    main()
