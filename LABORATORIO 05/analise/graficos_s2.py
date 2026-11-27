"""Gráficos descritivos da Sprint 2, separados por serviço.

As figuras usam as medições já preparadas pela análise: uma tentativa por
endpoint e hora, com período e hora UTC definidos pelo protocolo. Falhas e
latências inválidas não são convertidas em zeros. Os painéis são descritivos;
nenhuma curva é ajustada nem há interpretação causal.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd


CORES = {"pico": "#d97706", "fora_do_pico": "#2563eb"}
ROTULOS = {"pico": "Pico", "fora_do_pico": "Fora do pico"}
COLUNAS = {"endpoint", "latencia_ms", "usuarios_online", "sucesso_operacional",
           "periodo", "hora_utc"}
CONFIG = Path(__file__).resolve().parents[1] / "coleta" / "config.json"


def _validar(dados: pd.DataFrame) -> None:
    if not isinstance(dados, pd.DataFrame) or not COLUNAS.issubset(dados.columns):
        raise ValueError("Os gráficos exigem os dados preparados da análise, com "
                         "endpoint, latência, usuários, sucesso, período e hora UTC.")
    if dados["endpoint"].isna().any() or dados["endpoint"].astype(str).str.strip().eq("").any():
        raise ValueError("Os endpoints devem ter nomes preenchidos.")
    if not dados["periodo"].isin(ROTULOS).all():
        raise ValueError("Período deve ser pico ou fora_do_pico.")
    horas = pd.to_numeric(dados["hora_utc"], errors="coerce")
    if not (np.isfinite(horas) & horas.between(0, 23) & horas.eq(np.floor(horas))).all():
        raise ValueError("A hora UTC deve ser um inteiro entre 0 e 23.")
    if not dados["sucesso_operacional"].map(lambda x: isinstance(x, (bool, np.bool_))).all():
        raise ValueError("sucesso_operacional deve conter indicadores booleanos.")


def _endpoints(dados: pd.DataFrame) -> list[str]:
    esperados = list(dados.attrs.get("endpoints_esperados", []))
    presentes = dados["endpoint"].astype(str).drop_duplicates().tolist()
    nomes = [nome for nome in dict.fromkeys(esperados + presentes) if nome != "ValveStats"]
    if not nomes:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        nomes = [item["nome"] for item in config["endpoints"]]
    # A consulta de população não é um serviço estudado, mesmo se o chamador
    # acidentalmente a incluir na entrada dos gráficos.
    return nomes


def _latencias_validas(dados: pd.DataFrame) -> pd.DataFrame:
    _validar(dados)
    valores = pd.to_numeric(dados["latencia_ms"], errors="coerce")
    validos = (dados["sucesso_operacional"] & np.isfinite(valores) & valores.ge(0)
               & dados["endpoint"].ne("ValveStats"))
    resultado = dados.loc[validos].copy()
    resultado["latencia_ms"] = valores.loc[validos].astype(float)
    return resultado.reset_index(drop=True)


def resumir_horarios(dados: pd.DataFrame) -> pd.DataFrame:
    """Mediana, quartis e n por serviço e hora UTC, somente onde houve dados.

    Não reindexa horas ausentes e não reúne serviços como réplicas. O resumo é
    utilizado pelo gráfico e também pode ser inspecionado independentemente.
    """
    validos = _latencias_validas(dados)
    colunas = ["endpoint", "hora_utc", "n", "q25_ms", "mediana_ms", "q75_ms"]
    if validos.empty:
        return pd.DataFrame(columns=colunas)
    resumo = (validos.groupby(["endpoint", "hora_utc"], sort=True)["latencia_ms"]
              .agg(n="size", q25_ms=lambda x: x.quantile(.25), mediana_ms="median",
                   q75_ms=lambda x: x.quantile(.75)).reset_index())
    return resumo.loc[:, colunas]


def _paineis(nomes: list[str], titulo: str, subtitulo: str):
    quantidade = max(1, len(nomes))
    colunas = min(2, quantidade)
    linhas = (quantidade + colunas - 1) // colunas
    fig, eixos = plt.subplots(linhas, colunas, figsize=(14, 3.6 * linhas + 1.1),
                             squeeze=False)
    fig.suptitle(titulo + "\n" + subtitulo, fontsize=14, y=.985)
    for eixo in eixos.flat:
        eixo.grid(alpha=.2)
        eixo.set_axisbelow(True)
    for eixo in list(eixos.flat)[quantidade:]:
        eixo.set_visible(False)
    return fig, list(eixos.flat)


def _vazio(eixo, mensagem: str) -> None:
    eixo.text(.5, .5, mensagem, ha="center", va="center", transform=eixo.transAxes,
              fontsize=10, color="#4b5563")


def _salvar(fig, caminho: Path) -> None:
    try:
        fig.tight_layout(rect=(0, .035, 1, .935), h_pad=2.4, w_pad=2.5)
        fig.savefig(caminho, dpi=150, facecolor="white")
    finally:
        plt.close(fig)


def _latencia_hora(dados: pd.DataFrame, nomes: list[str], caminho: Path) -> None:
    resumo = resumir_horarios(dados)
    fig, eixos = _paineis(nomes, "Steam · latência por hora do dia (UTC)",
                          "Pontos: mediana · barras: intervalo interquartil · n: sucessos válidos")
    for eixo, nome in zip(eixos, nomes):
        pontos = resumo.loc[resumo["endpoint"].eq(nome)]
        eixo.set_title(f"{nome}\nn = {int(pontos['n'].sum())}", fontsize=10)
        if pontos.empty:
            _vazio(eixo, "Sem latências de sucesso válidas")
        else:
            eixo.errorbar(pontos["hora_utc"], pontos["mediana_ms"],
                          yerr=[pontos["mediana_ms"] - pontos["q25_ms"],
                                pontos["q75_ms"] - pontos["mediana_ms"]],
                          fmt="o", color="#2563eb", capsize=3, markersize=4)
            for ponto in pontos.itertuples():
                eixo.annotate(f"n={ponto.n}", (ponto.hora_utc, ponto.q75_ms),
                              xytext=(0, 6), textcoords="offset points", ha="center",
                              fontsize=7, color="#374151")
            eixo.margins(y=.20)
        eixo.set(xlim=(-.7, 23.7), xticks=[0, 3, 6, 9, 12, 15, 18, 21, 23],
                 xlabel="Hora do dia (UTC)", ylabel="Latência de sucesso (ms)")
        eixo.set_ylim(bottom=0)
    _salvar(fig, caminho)


def _boxplot_periodo(dados: pd.DataFrame, nomes: list[str], caminho: Path) -> None:
    validos = _latencias_validas(dados)
    fig, eixos = _paineis(nomes, "Steam · latência no pico e fora do pico",
                          "Pico: 14:00–22:00 UTC · caixas: Q1–Q3 · linha: mediana · extremos preservados")
    for eixo, nome in zip(eixos, nomes):
        grupo = validos.loc[validos["endpoint"].eq(nome)]
        periodos = ["pico", "fora_do_pico"]
        amostras, posicoes, cores, rotulos = [], [], [], []
        for posicao, periodo in enumerate(periodos):
            amostra = grupo.loc[grupo["periodo"].eq(periodo), "latencia_ms"].to_numpy()
            rotulos.append(f"{ROTULOS[periodo]}\nn={len(amostra)}")
            if len(amostra):
                amostras.append(amostra)
                posicoes.append(posicao)
                cores.append(CORES[periodo])
        eixo.set_title(f"{nome}\nn = {len(grupo)}", fontsize=10)
        if amostras:
            desenho = eixo.boxplot(amostras, positions=posicoes, widths=.5,
                                    patch_artist=True, showfliers=True, whis=1.5,
                                    manage_ticks=False,
                                    medianprops={"color": "#111827", "linewidth": 1.5},
                                    flierprops={"marker": "o", "markersize": 3, "alpha": .6})
            for caixa, cor in zip(desenho["boxes"], cores):
                caixa.set_facecolor(cor)
                caixa.set_alpha(.35)
        else:
            _vazio(eixo, "Sem latências de sucesso válidas")
        for posicao in set(range(2)) - set(posicoes):
            eixo.text(posicao, .04, "Sem observações", transform=eixo.get_xaxis_transform(),
                      ha="center", fontsize=8, color="#6b7280")
        eixo.set(xlim=(-.6, 1.6), ylabel="Latência de sucesso (ms)")
        # tick_labels foi introduzido depois do mínimo matplotlib>=3.8.
        eixo.set_xticks([0, 1], rotulos)
        eixo.set_ylim(bottom=0)
    _salvar(fig, caminho)


def _dispersao(dados: pd.DataFrame, nomes: list[str], caminho: Path) -> None:
    validos = _latencias_validas(dados)
    usuarios = pd.to_numeric(validos["usuarios_online"], errors="coerce")
    pares = validos.loc[np.isfinite(usuarios) & usuarios.ge(0)].copy()
    pares["usuarios_online"] = usuarios.loc[pares.index].astype(float)
    fig, eixos = _paineis(nomes, "Steam · usuários online e latência",
                          "Um ponto por medição horária válida do endpoint · associação descritiva")
    for eixo, nome in zip(eixos, nomes):
        grupo = pares.loc[pares["endpoint"].eq(nome)]
        eixo.set_title(f"{nome}\nn de pares = {len(grupo)}", fontsize=10)
        if grupo.empty:
            _vazio(eixo, "Sem pares válidos de usuários e latência")
        for periodo, cor in CORES.items():
            parte = grupo.loc[grupo["periodo"].eq(periodo)]
            if not parte.empty:
                eixo.scatter(parte["usuarios_online"] / 1e6, parte["latencia_ms"],
                             color=cor, label=ROTULOS[periodo], alpha=.75,
                             s=22, edgecolors="white", linewidths=.3)
        eixo.set(xlabel="Usuários online (milhões)", ylabel="Latência de sucesso (ms)")
        eixo.set_ylim(bottom=0)
    fig.legend([Patch(color=CORES[p], alpha=.75) for p in CORES],
               [ROTULOS[p] for p in CORES], loc="lower center", ncol=2,
               frameon=False, bbox_to_anchor=(.5, .005))
    _salvar(fig, caminho)


def gerar_graficos(dados: pd.DataFrame, saida: str | Path) -> dict[str, Path]:
    """Grava as três figuras da Sprint 2, sem alterar o dataframe recebido.

    ``dados.attrs['endpoints_esperados']`` pode fornecer a ordem e os serviços
    esperados, inclusive serviços sem medições. Na sua ausência são usados os
    nomes presentes; uma entrada totalmente vazia usa os endpoints do coletor.
    """
    _validar(dados)
    nomes = _endpoints(dados)
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    caminhos = {"latencia_hora": saida / "latencia_por_hora.png",
                "boxplot_periodo": saida / "boxplot_pico_fora.png",
                "dispersao_usuarios": saida / "dispersao_usuarios_latencia.png"}
    _latencia_hora(dados, nomes, caminhos["latencia_hora"])
    _boxplot_periodo(dados, nomes, caminhos["boxplot_periodo"])
    _dispersao(dados, nomes, caminhos["dispersao_usuarios"])
    return caminhos
