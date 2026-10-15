"""Dimensões rotuladas na amostra-ouro e leitura das planilhas dos avaliadores.

Cada avaliador preenche uma cópia de ``planilha_rotulagem.xlsx`` salva como
``rotulos_<letra>.xlsx`` nesta pasta (ex.: ``rotulos_A.xlsx``).
"""

from pathlib import Path

import pandas as pd


PASTA = Path(__file__).resolve().parent
RAIZ = PASTA.parent
PADRAO_ARQUIVOS = "rotulos_*.xlsx"

ABA_REPOSITORIOS = "repositorios"
ABA_RELEASES = "releases"
CHAVES = {ABA_REPOSITORIOS: ["full_name"], ABA_RELEASES: ["full_name", "tag_name"]}

# Dimensão -> (aba da planilha, categorias permitidas). Seção 6 do enunciado.
DIMENSOES = {
    "tipo_projeto": (ABA_REPOSITORIOS,
                     ["biblioteca/framework", "aplicacao/servico", "ferramenta CLI", "outro"]),
    "entregas_reais": (ABA_REPOSITORIOS, ["sim", "nao", "incerto"]),
    "corretiva": (ABA_RELEASES, ["sim", "nao"]),
}


def normalizar(valor):
    """Célula vazia vira ``None``; o resto perde espaços e diferenças de caixa."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    texto = str(valor).strip()
    return texto or None


def carregar_planilha(caminho):
    abas = pd.read_excel(caminho, sheet_name=[ABA_REPOSITORIOS, ABA_RELEASES], dtype=str)
    return {aba: tabela for aba, tabela in abas.items()}


def carregar_avaliadores(pasta=PASTA):
    """``{"A": {"repositorios": df, "releases": df}, "B": ...}`` a partir de rotulos_*.xlsx."""
    avaliadores = {}
    for caminho in sorted(Path(pasta).glob(PADRAO_ARQUIVOS)):
        if caminho.name.startswith("~$"):  # arquivo de bloqueio do Excel aberto
            continue
        avaliadores[caminho.stem.removeprefix("rotulos_")] = carregar_planilha(caminho)
    return avaliadores


def tabela_da_dimensao(avaliadores, dimensao):
    """Itens nas linhas, avaliadores nas colunas, rótulos (ou ``None``) nas células.

    Rótulos fora das categorias permitidas geram erro com o arquivo e o item,
    para que o avaliador corrija a planilha antes de calcular a concordância.
    """
    aba, categorias = DIMENSOES[dimensao]
    por_minusculas = {c.lower(): c for c in categorias}
    colunas = {}
    for avaliador, abas in avaliadores.items():
        tabela = abas[aba].set_index(CHAVES[aba])
        valores = {}
        for item, valor in tabela[dimensao].items():
            rotulo = normalizar(valor)
            if rotulo is not None:
                if rotulo.lower() not in por_minusculas:
                    raise ValueError(f"rotulos_{avaliador}: '{rotulo}' não é um valor válido de "
                                     f"{dimensao} em {item}. Use: {', '.join(categorias)}")
                rotulo = por_minusculas[rotulo.lower()]
            valores[item] = rotulo
        colunas[avaliador] = pd.Series(valores, dtype=object)
    resultado = pd.DataFrame(colunas)
    resultado.index.names = CHAVES[aba]
    return resultado.astype(object).where(resultado.notna(), None)
