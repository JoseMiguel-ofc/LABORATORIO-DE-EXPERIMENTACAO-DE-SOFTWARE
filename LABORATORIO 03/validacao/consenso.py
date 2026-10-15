"""Rótulo de consenso da amostra-ouro.

Uso: ``python -m validacao.consenso``

Protocolo de desempate:
1. maioria simples: o rótulo dado por mais da metade dos avaliadores (2 de 3);
2. empates (1-1-1, ou 1-1 quando falta um rótulo) vão para ``desempate.csv``;
   os três discutem cada caso em reunião e preenchem a coluna ``decisao``;
3. rodar este script de novo aplica as decisões da reunião. Decisões já
   preenchidas são preservadas quando a lista de empates é regenerada.

Saídas: ``consenso_repositorios.csv`` (tipo do projeto e entregas reais, usados
na RQ 06) e ``consenso_releases.csv`` (release corretiva, usada para avaliar a
heurística do CFR b).
"""

import argparse
from collections import Counter
from pathlib import Path

import pandas as pd

from validacao.rotulos import (ABA_RELEASES, ABA_REPOSITORIOS, DIMENSOES, PASTA,
                               carregar_avaliadores, normalizar, tabela_da_dimensao)


MAIORIA, REUNIAO, PENDENTE = "maioria", "reuniao", "pendente"
COLUNAS_DESEMPATE = ["dimensao", "full_name", "tag_name", "votos", "decisao"]


def votar(votos):
    """``(rótulo, "maioria")`` se alguém tem mais da metade dos votos; senão ``(None, "pendente")``."""
    validos = [voto for voto in votos if voto is not None]
    if validos:
        rotulo, quantidade = Counter(validos).most_common(1)[0]
        if quantidade > len(votos) / 2:
            return rotulo, MAIORIA
    return None, PENDENTE


def _chave(dimensao, item):
    item = item if isinstance(item, tuple) else (item,)
    return (dimensao, item[0], item[1] if len(item) > 1 else "")


def carregar_decisoes(caminho):
    if not Path(caminho).exists():
        return {}
    tabela = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    return {(linha.dimensao, linha.full_name, linha.tag_name): normalizar(linha.decisao)
            for linha in tabela.itertuples()}


def consolidar(avaliadores, decisoes):
    """Devolve as tabelas de consenso por aba e a lista de empates para a reunião."""
    por_aba, empates = {}, []
    for dimensao, (aba, categorias) in DIMENSOES.items():
        tabela = tabela_da_dimensao(avaliadores, dimensao)
        rotulos, metodos = [], []
        for item, votos in tabela.iterrows():
            rotulo, metodo = votar(list(votos))
            if metodo == PENDENTE:
                chave = _chave(dimensao, item)
                decisao = decisoes.get(chave)
                if decisao is not None:
                    if decisao not in categorias:
                        raise ValueError(f"Decisão inválida '{decisao}' em {chave}. "
                                         f"Use: {', '.join(categorias)}")
                    rotulo, metodo = decisao, REUNIAO
                empates.append({"dimensao": chave[0], "full_name": chave[1], "tag_name": chave[2],
                                 "votos": " | ".join(f"{a}={v or '-'}" for a, v in votos.items()),
                                 "decisao": decisao or ""})
            rotulos.append(rotulo)
            metodos.append(metodo)
        coluna = pd.DataFrame({dimensao: rotulos, f"metodo_{dimensao}": metodos},
                              index=tabela.index)
        por_aba[aba] = coluna if aba not in por_aba else por_aba[aba].join(coluna)
    return {aba: tabela.reset_index() for aba, tabela in por_aba.items()}, empates


def main(argv=None):
    parser = argparse.ArgumentParser(description="Consenso da amostra-ouro")
    parser.add_argument("--pasta", default=PASTA)
    args = parser.parse_args(argv)
    pasta = Path(args.pasta)

    avaliadores = carregar_avaliadores(pasta)
    if len(avaliadores) < 2:
        raise SystemExit(f"Encontrei {len(avaliadores)} arquivo(s) rotulos_*.xlsx em {pasta}; "
                         "são necessários pelo menos 2 (o protocolo prevê 3).")
    caminho_desempate = pasta / "desempate.csv"
    consenso, empates = consolidar(avaliadores, carregar_decisoes(caminho_desempate))
    consenso[ABA_REPOSITORIOS].to_csv(pasta / "consenso_repositorios.csv", index=False)
    consenso[ABA_RELEASES].to_csv(pasta / "consenso_releases.csv", index=False)
    pd.DataFrame(empates, columns=COLUNAS_DESEMPATE).to_csv(caminho_desempate, index=False)

    for aba, tabela in consenso.items():
        for dimensao in [c for c in tabela.columns if c.startswith("metodo_")]:
            contagem = tabela[dimensao].value_counts().to_dict()
            print(f"{dimensao.removeprefix('metodo_')}: {contagem}")
    pendentes = sum(not e["decisao"] for e in empates)
    if pendentes:
        print(f"{pendentes} empate(s) sem decisão: preencha a coluna 'decisao' de "
              f"{caminho_desempate.name} na reunião e rode o script de novo.")
    else:
        print("Todos os itens têm rótulo de consenso.")


if __name__ == "__main__":
    main()
