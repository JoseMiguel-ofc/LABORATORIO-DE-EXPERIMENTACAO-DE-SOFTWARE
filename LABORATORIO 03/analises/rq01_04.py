"""RQ 01 a 04: estatística descritiva, gráficos e classificação DORA de referência (C1).

Uso: ``python -m analises.rq01_04``

Lê ``dados/metricas_consolidadas.csv`` e grava em ``analises/resultados/``:
- ``rq01_04_descritiva.csv``: n, ausentes, mediana, Q1, Q3, IQR, mínimo e máximo;
- ``rq01_04_censura.csv``: casos censurados da recuperação (RQ 04) e do CFR (b);
- ``rq01_04_categorias_c1.csv``: repositórios por categoria DORA em cada métrica;
- ``rq01_04_resumo.md``: as mesmas tabelas formatadas para o artigo;
- ``figuras/``: histogramas, boxplots e distribuição das categorias.

Quartis pelo método linear (padrão do pandas/NumPy). Métricas ausentes ficam
fora de cada cálculo e são contadas na coluna ``ausentes``; nunca viram zero.
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # gera arquivos sem abrir janela
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from metricas.dora import UM_POR_MES_EM_SEMANAS  # noqa: E402


RAIZ = Path(__file__).resolve().parents[1]
ENTRADA = RAIZ / "dados" / "metricas_consolidadas.csv"
SAIDA = RAIZ / "analises" / "resultados"

CATEGORIAS = ["Elite", "High", "Medium", "Low"]
SEM_DADO = "Sem dado"

# coluna -> (RQ, nome no artigo, unidade, cortes DORA, escala log no gráfico)
METRICAS = {
    "frequencia_releases_semana": ("RQ 01", "Frequência de deploy", "releases/semana",
                                   [UM_POR_MES_EM_SEMANAS, 1, 7], True),
    "lead_time_a_horas": ("RQ 02", "Lead time (a) por release", "horas", [24, 168, 720], True),
    "lead_time_b_horas": ("RQ 02", "Lead time (b) por commit", "horas", [24, 168, 720], True),
    "cfr_a": ("RQ 03", "CFR (a) proxy de CI", "fração", [0.15, 0.30, 0.45], False),
    "cfr_b": ("RQ 03", "CFR (b) proxy de entrega", "fração", [0.15, 0.30, 0.45], False),
    "recuperacao_mediana_horas": ("RQ 04", "Tempo de recuperação", "horas", [1, 24, 168], True),
}
# coluna de categoria -> nome; C1 = release, lead time (a), CFR (a), recuperação.
CATEGORIAS_C1 = {
    "categoria_frequencia": "Frequência de deploy",
    "categoria_lead_time": "Lead time (a)",
    "categoria_cfr": "CFR (a)",
    "categoria_recuperacao": "Tempo de recuperação",
    "categoria_geral": "Classificação geral",
}

# Paleta de referência (skill dataviz): um tom para uma série; rampa ordinal azul
# para categorias ordenadas (Low claro -> Elite escuro); tinta neutra no texto.
AZUL = "#2a78d6"
RAMPA = {"Elite": "#0d366b", "High": "#1c5cab", "Medium": "#3987e5", "Low": "#86b6ef",
         SEM_DADO: "#d6d5d0"}
TEXTO, TEXTO_2, GRADE, SUPERFICIE = "#0b0b0b", "#52514e", "#e5e4df", "#ffffff"


# ---------------------------------------------------------------- cálculos

def resumir(serie):
    """Estatística descritiva robusta de uma métrica (ausentes excluídos)."""
    valores = pd.to_numeric(serie, errors="coerce").dropna()
    if valores.empty:
        return {"n": 0, "ausentes": len(serie), "mediana": None, "q1": None, "q3": None,
                "iqr": None, "minimo": None, "maximo": None}
    q1, mediana, q3 = valores.quantile([0.25, 0.5, 0.75])
    return {"n": len(valores), "ausentes": len(serie) - len(valores),
            "mediana": float(mediana), "q1": float(q1), "q3": float(q3),
            "iqr": float(q3 - q1), "minimo": float(valores.min()),
            "maximo": float(valores.max())}


def tabela_descritiva(dados):
    linhas = []
    for coluna, (rq, nome, unidade, _, _) in METRICAS.items():
        linhas.append({"rq": rq, "metrica": nome, "coluna": coluna, "unidade": unidade,
                       **resumir(dados[coluna])})
    return pd.DataFrame(linhas)


def distribuicao_categorias(dados):
    """Contagem e percentual de repositórios por categoria, na ordem Elite -> Low."""
    linhas = []
    for coluna, nome in CATEGORIAS_C1.items():
        contagem = dados[coluna].fillna(SEM_DADO).value_counts()
        desconhecidas = set(contagem.index) - set(CATEGORIAS) - {SEM_DADO}
        if desconhecidas:
            raise ValueError(f"{coluna}: categorias desconhecidas {sorted(desconhecidas)}")
        for categoria in CATEGORIAS + [SEM_DADO]:
            quantidade = int(contagem.get(categoria, 0))
            linhas.append({"metrica": nome, "coluna": coluna, "categoria": categoria,
                           "repositorios": quantidade,
                           "percentual": 100 * quantidade / len(dados)})
    return pd.DataFrame(linhas)


def tabela_censura(dados):
    resolvidos = pd.to_numeric(dados["episodios_resolvidos"], errors="coerce")
    censurados = pd.to_numeric(dados["episodios_censurados"], errors="coerce")
    proporcao = pd.to_numeric(dados["proporcao_episodios_censurados"], errors="coerce")
    return pd.DataFrame([
        {"item": "Episódios de falha resolvidos (RQ 04)", "valor": int(resolvidos.sum())},
        {"item": "Episódios de falha censurados (RQ 04)", "valor": int(censurados.sum())},
        {"item": "Repositórios com ao menos 1 episódio censurado",
         "valor": int((censurados > 0).sum())},
        {"item": "Mediana da proporção de episódios censurados por repositório",
         "valor": float(proporcao.median())},
        {"item": "Repositórios sem episódio resolvido (sem tempo de recuperação)",
         "valor": int(dados["recuperacao_mediana_horas"].isna().sum())},
        {"item": "Releases censuradas no CFR (b) (últimos 7 dias da janela)",
         "valor": int(pd.to_numeric(dados["cfr_b_censuradas"], errors="coerce").sum())},
    ])


# ---------------------------------------------------------------- formatação

def formatar(valor, coluna):
    """Valor em unidade legível para o artigo (dias para lead time, % para CFR)."""
    if valor is None or pd.isna(valor):
        return "—"
    unidade = METRICAS[coluna][2]
    if coluna.startswith("lead_time"):
        return f"{valor / 24:.1f} dias".replace(".", ",")
    if unidade == "fração":
        return f"{100 * valor:.1f}%".replace(".", ",")
    if unidade == "horas":
        return f"{valor:.1f} h".replace(".", ",")
    return f"{valor:.2f}/semana".replace(".", ",")


def resumo_markdown(descritiva, categorias, censura):
    linhas = ["## Estatística descritiva (RQ 01 a 04)", "",
              "| RQ | Métrica | n | Mediana | Q1 | Q3 | IQR |", "|---|---|---:|---:|---:|---:|---:|"]
    for r in descritiva.itertuples():
        linhas.append(f"| {r.rq} | {r.metrica} | {r.n} | {formatar(r.mediana, r.coluna)} | "
                      f"{formatar(r.q1, r.coluna)} | {formatar(r.q3, r.coluna)} | "
                      f"{formatar(r.iqr, r.coluna)} |")
    linhas += ["", "## Categorias DORA na combinação de referência (C1)", "",
               "| Métrica | " + " | ".join(CATEGORIAS + [SEM_DADO]) + " |",
               "|---|" + "---:|" * (len(CATEGORIAS) + 1)]
    for nome, grupo in categorias.groupby("metrica", sort=False):
        celulas = [f"{r.repositorios} ({r.percentual:.0f}%)" for r in grupo.itertuples()]
        linhas.append(f"| {nome} | " + " | ".join(celulas) + " |")
    linhas += ["", "## Casos censurados", "", "| Item | Valor |", "|---|---:|"]
    for r in censura.itertuples():
        valor = (f"{r.valor:.0f}" if float(r.valor).is_integer()
                 else f"{r.valor:.3f}".replace(".", ","))
        linhas.append(f"| {r.item} | {valor} |")
    return "\n".join(linhas) + "\n"


# ---------------------------------------------------------------- gráficos

def _estilo(eixo):
    eixo.set_facecolor(SUPERFICIE)
    for lado in ("top", "right", "left"):
        eixo.spines[lado].set_visible(False)
    eixo.spines["bottom"].set_color(TEXTO_2)
    eixo.tick_params(colors=TEXTO_2, labelsize=8)
    eixo.grid(axis="x", color=GRADE, linewidth=0.8)
    eixo.set_axisbelow(True)


def _valores_para_grafico(dados, coluna):
    """Frações viram %; em escala log, valores ≤ 0 não podem ser plotados."""
    _, _, unidade, cortes, log = METRICAS[coluna]
    valores = pd.to_numeric(dados[coluna], errors="coerce").dropna()
    if unidade == "fração":
        return valores * 100, [c * 100 for c in cortes], log
    return valores[valores > 0] if log else valores, cortes, log


def grafico_histogramas(dados, caminho):
    figura, eixos = plt.subplots(2, 3, figsize=(12, 6.5))
    for eixo, coluna in zip(eixos.flat, METRICAS):
        rq, nome, unidade, _, _ = METRICAS[coluna]
        valores, cortes, log = _valores_para_grafico(dados, coluna)
        if log:
            bins = np.logspace(np.log10(valores.min()), np.log10(valores.max()), 25)
            eixo.set_xscale("log")
        else:
            bins = np.linspace(0, 100, 26)
        eixo.hist(valores, bins=bins, color=AZUL, edgecolor=SUPERFICIE, linewidth=1)
        for corte in cortes:
            eixo.axvline(corte, color=TEXTO_2, linestyle=(0, (3, 3)), linewidth=1)
        mediana = valores.median()
        eixo.axvline(mediana, color=TEXTO, linewidth=1.5)
        eixo.annotate(f"mediana {formatar(mediana / 100 if unidade == 'fração' else mediana, coluna)}",
                      (mediana, 1), xycoords=("data", "axes fraction"), xytext=(4, -4),
                      textcoords="offset points", va="top", fontsize=8, color=TEXTO)
        _estilo(eixo)
        eixo.grid(False)
        eixo.set_title(f"{rq} · {nome} (n={len(valores)})", fontsize=9.5, color=TEXTO, loc="left")
        eixo.set_xlabel("%" if unidade == "fração" else unidade, fontsize=8, color=TEXTO_2)
    eixos[0, 0].set_ylabel("repositórios", fontsize=8, color=TEXTO_2)
    eixos[1, 0].set_ylabel("repositórios", fontsize=8, color=TEXTO_2)
    figura.suptitle("Distribuição das métricas DORA (linhas tracejadas: cortes Elite/High/Medium/Low)",
                    fontsize=10.5, color=TEXTO, x=0.01, ha="left")
    figura.tight_layout()
    figura.savefig(caminho, dpi=200, facecolor=SUPERFICIE)
    plt.close(figura)


def grafico_boxplots(dados, caminho):
    paineis = [("Frequência de deploy", "releases/semana", ["frequencia_releases_semana"], True),
               ("Lead time", "horas", ["lead_time_a_horas", "lead_time_b_horas"], True),
               ("Change failure rate", "%", ["cfr_a", "cfr_b"], False),
               ("Tempo de recuperação", "horas", ["recuperacao_mediana_horas"], True)]
    rotulos = {"frequencia_releases_semana": "releases", "lead_time_a_horas": "(a) por release",
               "lead_time_b_horas": "(b) por commit", "cfr_a": "(a) CI",
               "cfr_b": "(b) entrega", "recuperacao_mediana_horas": "episódios"}
    figura, eixos = plt.subplots(len(paineis), 1, figsize=(8, 7.5))
    for eixo, (titulo, unidade, colunas, log) in zip(eixos, paineis):
        series = [_valores_para_grafico(dados, c)[0] for c in colunas]
        caixas = eixo.boxplot(series, orientation="horizontal", widths=0.5, patch_artist=True,
                              flierprops={"marker": "o", "markersize": 3, "alpha": 0.5,
                                          "markerfacecolor": AZUL, "markeredgecolor": "none"},
                              medianprops={"color": TEXTO, "linewidth": 1.5},
                              whiskerprops={"color": TEXTO_2}, capprops={"color": TEXTO_2})
        for caixa in caixas["boxes"]:
            caixa.set(facecolor="#b7d3f6", edgecolor=AZUL, linewidth=1)
        eixo.set_yticks(range(1, len(colunas) + 1), [rotulos[c] for c in colunas])
        if log:
            eixo.set_xscale("log")
        _estilo(eixo)
        eixo.set_title(titulo, fontsize=9.5, color=TEXTO, loc="left")
        eixo.set_xlabel(unidade, fontsize=8, color=TEXTO_2)
    figura.suptitle("Boxplots por métrica (caixa = IQR; linha = mediana)", fontsize=10.5,
                    color=TEXTO, x=0.01, ha="left")
    figura.tight_layout()
    figura.savefig(caminho, dpi=200, facecolor=SUPERFICIE)
    plt.close(figura)


def grafico_categorias(categorias, caminho):
    nomes = list(CATEGORIAS_C1.values())[::-1]  # geral embaixo, primeira métrica no topo
    figura, eixo = plt.subplots(figsize=(9, 3.6))
    inicio = np.zeros(len(nomes))
    for categoria in CATEGORIAS + [SEM_DADO]:
        largura = np.array([categorias[(categorias.metrica == n) & (categorias.categoria == categoria)]
                            ["percentual"].iloc[0] for n in nomes])
        barras = eixo.barh(nomes, largura, left=inicio, color=RAMPA[categoria], label=categoria,
                           edgecolor=SUPERFICIE, linewidth=2, height=0.6)
        escuro = categoria in ("Elite", "High")
        for barra, valor in zip(barras, largura):
            if valor >= 6:  # rótulo só onde cabe
                eixo.text(barra.get_x() + barra.get_width() / 2, barra.get_y() + barra.get_height() / 2,
                          f"{valor:.0f}%", ha="center", va="center", fontsize=8,
                          color="#ffffff" if escuro else TEXTO)
        inicio += largura
    eixo.set_xlim(0, 100)
    eixo.set_xlabel("% dos repositórios", fontsize=8, color=TEXTO_2)
    _estilo(eixo)
    eixo.grid(False)
    eixo.legend(ncol=5, loc="lower left", bbox_to_anchor=(0, 1.02), frameon=False, fontsize=8,
                labelcolor=TEXTO)
    figura.suptitle("Categorias DORA na combinação de referência (C1)", fontsize=10.5,
                    color=TEXTO, x=0.01, ha="left")
    figura.tight_layout()
    figura.savefig(caminho, dpi=200, facecolor=SUPERFICIE)
    plt.close(figura)


# ---------------------------------------------------------------- execução

def main(argv=None):
    parser = argparse.ArgumentParser(description="RQ 01 a 04")
    parser.add_argument("--entrada", default=ENTRADA)
    parser.add_argument("--saida", default=SAIDA)
    args = parser.parse_args(argv)
    saida = Path(args.saida)
    (saida / "figuras").mkdir(parents=True, exist_ok=True)

    dados = pd.read_csv(args.entrada)
    descritiva = tabela_descritiva(dados)
    categorias = distribuicao_categorias(dados)
    censura = tabela_censura(dados)
    descritiva.to_csv(saida / "rq01_04_descritiva.csv", index=False)
    categorias.to_csv(saida / "rq01_04_categorias_c1.csv", index=False)
    censura.to_csv(saida / "rq01_04_censura.csv", index=False)
    (saida / "rq01_04_resumo.md").write_text(resumo_markdown(descritiva, categorias, censura),
                                             encoding="utf-8")
    grafico_histogramas(dados, saida / "figuras" / "rq01_04_histogramas.png")
    grafico_boxplots(dados, saida / "figuras" / "rq01_04_boxplots.png")
    grafico_categorias(categorias, saida / "figuras" / "rq01_04_categorias_c1.png")
    print(f"{len(dados)} repositórios analisados. Resultados em {saida}")


if __name__ == "__main__":
    main()
