"""Gráficos do dashboard."""
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.dados import GRUPOS

# Os testes (G2 a G4) usam outras cores: aqui a cor identifica o grupo, não o teste.
CORES_GRUPO = {"com_bot": "#1baf7a", "sem_bot": "#6250d6"}
TINTA = "#52514e"
GRADE = "#e5e4df"


def _faixas(reais, n_faixas, log):
    """Faixas do histograma, iguais nos quatro painéis, definidas pelos dados reais."""
    todos = np.concatenate(list(reais.values()))
    if log:
        expoentes = np.linspace(np.floor(np.log10(todos.min())),
                                np.ceil(np.log10(todos.max())), n_faixas + 1)
        return 10.0 ** expoentes
    return np.linspace(0, todos.max(), n_faixas + 1)


def g1(reais, simulados, log=True, n_faixas=18):
    """G1: histograma de cada grupo, dados reais ao lado dos simulados.

    reais e simulados são dicionários {grupo: array de horas}. O eixo y é o
    percentual do grupo porque as duas colunas têm tamanhos de amostra diferentes.
    """
    colunas = [("Dados reais", reais), ("Dados simulados", simulados)]
    grupos = list(GRUPOS)
    fig = make_subplots(rows=2, cols=2, shared_xaxes=True, shared_yaxes=True,
                        horizontal_spacing=0.08, vertical_spacing=0.09,
                        subplot_titles=[f"{GRUPOS[g]} · {titulo}"
                                        for g in grupos for titulo, _ in colunas])
    faixas = _faixas(reais, n_faixas, log)
    posicoes = np.log10(faixas) if log else faixas
    centros = (posicoes[:-1] + posicoes[1:]) / 2
    for linha, grupo in enumerate(grupos, start=1):
        for coluna, (titulo, serie) in enumerate(colunas, start=1):
            contagem, _ = np.histogram(serie[grupo], bins=faixas)
            percentual = 100 * contagem / len(serie[grupo])
            fig.add_trace(go.Bar(
                x=centros, y=percentual, width=(posicoes[1] - posicoes[0]) * 0.92,
                name=GRUPOS[grupo], legendgroup=grupo, showlegend=coluna == 1,
                marker={"color": CORES_GRUPO[grupo], "line": {"width": 0},
                        "cornerradius": 3},
                customdata=np.column_stack([faixas[:-1], faixas[1:]]),
                hovertemplate=(f"{GRUPOS[grupo]} · {titulo}<br>"
                               "%{customdata[0]:,.1f} a %{customdata[1]:,.1f} h"
                               "<br>%{y:.1f}% dos PRs<extra></extra>"),
            ), row=linha, col=coluna)

    if log:
        expoentes = range(int(posicoes[0]), int(posicoes[-1]) + 1)
        eixo_x = {"tickvals": list(expoentes),
                  "ticktext": [f"{10.0 ** e:g} h" for e in expoentes]}
    else:
        eixo_x = {"ticksuffix": " h"}
    fig.update_xaxes(showgrid=False, linecolor=TINTA, **eixo_x)
    # Mesmo limite nos quatro painéis, para os grupos serem comparáveis.
    maximo = max(max(barras.y) for barras in fig.data)
    fig.update_yaxes(range=[0, maximo * 1.05], gridcolor=GRADE, ticksuffix="%",
                     zeroline=False)
    escala = "escala logarítmica" if log else "escala linear"
    for coluna in (1, 2):
        fig.update_xaxes(title_text=f"Tempo até o merge (horas, {escala})",
                         row=2, col=coluna)
    for linha in (1, 2):
        fig.update_yaxes(title_text="PRs do grupo (%)", row=linha, col=1)
    fig.update_layout(title="G1: tempo até o merge, dados reais × simulados",
                      height=560, bargap=0, plot_bgcolor="white",
                      font={"color": TINTA}, legend_title_text="Grupo",
                      margin={"t": 90, "r": 20, "l": 60, "b": 60})
    return fig
