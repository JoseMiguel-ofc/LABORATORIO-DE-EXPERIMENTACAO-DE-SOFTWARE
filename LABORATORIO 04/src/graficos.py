"""Gráficos do dashboard."""
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats

from src.dados import GRUPOS
from src.testes import validar_alfa

# Os testes (G2 a G4) usam outras cores: aqui a cor identifica o grupo, não o teste.
CORES_GRUPO = {"com_bot": "#1baf7a", "sem_bot": "#6250d6"}
CORES_TESTE = {"welch": "#2563eb", "mann_whitney": "#d97706"}
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


def _cor_alpha(hexadecimal, alpha):
    r, g, b = (int(hexadecimal[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r}, {g}, {b}, {alpha})"


def g2(resultados, alfa=0.05):
    """G2: referências aproximadas sob H0, regiões críticas e p bicaudal.

    Recebe o retorno de ``aplicar_testes``. Welch usa t com os graus de liberdade
    observados; Mann–Whitney usa Z normal, corrigido para empates e sem correção
    de continuidade. As áreas p correspondem aos p-valores desses métodos, não
    a uma distribuição empírica obtida por Monte Carlo. As caudas continuam além
    da janela visível; seus valores são probabilidades analíticas até infinito.
    """
    alfa = validar_alfa(alfa)
    referencias = []
    for chave in ("welch", "mann_whitney"):
        resultado = resultados[chave]
        p = float(resultado["p_valor"])
        estatistica = float(resultado["estatistica"] if chave == "welch"
                            else resultado["z"])
        if not np.isfinite([p, estatistica]).all() or not 0 <= p <= 1:
            raise ValueError("G2 exige estatísticas finitas e p-valores entre 0 e 1.")
        if chave == "welch":
            gl = float(resultado["gl"])
            if not np.isfinite(gl) or gl <= 0:
                raise ValueError("G2 exige graus de liberdade positivos para Welch.")
            distribuicao = stats.t(df=gl)
            referencia = f"t com {gl:.2f} graus de liberdade"
        else:
            if resultado.get("correcao_continuidade", False):
                raise ValueError("G2 usa Mann–Whitney sem correção de continuidade.")
            distribuicao = stats.norm()
            referencia = "Normal N(0, 1) para U padronizado"
        p_area = float(2 * distribuicao.sf(abs(estatistica)))
        if not np.isclose(p, p_area, rtol=1e-8, atol=1e-14):
            raise ValueError("O p-valor informado não corresponde à referência do G2.")
        critico = float(distribuicao.isf(alfa / 2))
        limite = max(4.5, critico * 1.4, abs(estatistica) * 1.2)
        referencias.append((chave, resultado, distribuicao, estatistica, critico,
                            limite, referencia))

    titulos = []
    for chave, resultado, _, _, _, _, referencia in referencias:
        decisao = "rejeita H₀" if resultado["p_valor"] < alfa else "não rejeita H₀"
        titulos.append(f"{resultado['nome']}<br><sup>{referencia}<br>"
                       f"p = {resultado['p_valor']:.4g} · {decisao}</sup>")
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.13,
                        subplot_titles=titulos)
    metadados = {"alfa": alfa, "referencia": "aproximada sob H0", "testes": {}}
    for coluna, (chave, resultado, distribuicao, observado, critico,
                  limite, referencia) in enumerate(referencias, start=1):
        cor = CORES_TESTE[chave]
        nome = "Welch" if chave == "welch" else "Mann–Whitney"
        # Incluir exatamente as fronteiras evita deslocar visualmente as caudas.
        x = np.unique(np.r_[np.linspace(-limite, limite, 1201),
                            -critico, critico, -abs(observado), abs(observado)])
        for tipo, corte, probabilidade, preenchimento in (
            ("rejeicao", critico, alfa / 2, "rgba(185, 28, 28, 0.20)"),
            ("p_valor", abs(observado), resultado["p_valor"] / 2,
             _cor_alpha(cor, 0.35)),
        ):
            for lado in (-1, 1):
                inicio, fim = (-limite, -corte) if lado < 0 else (corte, limite)
                cauda_x = np.linspace(inicio, fim, 601)
                legenda = (f"{nome}: p/2 em cada cauda" if tipo == "p_valor"
                           else "Rejeição: α/2 em cada cauda")
                fig.add_trace(go.Scatter(
                    x=cauda_x, y=distribuicao.pdf(cauda_x), mode="lines",
                    line={"width": 0}, fill="tozeroy", fillcolor=preenchimento,
                    name=legenda, legendgroup=f"{tipo}_{chave}",
                    showlegend=lado < 0 and (tipo == "p_valor" or coluna == 1),
                    hovertemplate=(f"{legenda}<br>Área da cauda até ∞: "
                                   f"{probabilidade:.6g}<extra></extra>"),
                    meta={"teste": chave, "tipo": tipo, "lado": lado,
                          "corte": float(corte), "area": float(probabilidade),
                          "massa_fora_janela": float(distribuicao.sf(limite))},
                ), row=1, col=coluna)
        fig.add_trace(go.Scatter(
            x=x, y=distribuicao.pdf(x), mode="lines", name=f"{nome}: referência",
            line={"color": cor, "width": 2.5}, showlegend=False,
            hovertemplate="Estatística: %{x:.3f}<br>Densidade: %{y:.4f}<extra></extra>",
            meta={"teste": chave, "tipo": "densidade"},
        ), row=1, col=coluna)
        for sinal in (-1, 1):
            fig.add_vline(x=sinal * critico, line_color="#b91c1c",
                          line_dash="dot", line_width=1.4, row=1, col=coluna)
        fig.add_trace(go.Scatter(
            x=[observado, observado], y=[0, float(distribuicao.pdf(0)) * 1.04],
            mode="lines", name=f"{nome}: observado = {observado:.3f}",
            line={"color": cor, "dash": "dash", "width": 2},
            hovertemplate=f"Estatística observada: {observado:.6g}<extra></extra>",
            meta={"teste": chave, "tipo": "observado"},
        ), row=1, col=coluna)
        fig.add_annotation(
            x=0.5, y=0.96, xref=f"x{coluna if coluna > 1 else ''} domain",
            yref=f"y{coluna if coluna > 1 else ''} domain", showarrow=False,
            text=f"Limites críticos: ±{critico:.3f}",
            font={"size": 11, "color": "#991b1b"}, bgcolor="rgba(255,255,255,0.8)",
        )
        titulo_eixo = ("t = (média com bot − média sem bot) / erro padrão"
                       if chave == "welch" else "Z = (U com bot − E[U | H₀]) / DP[U | H₀]")
        fig.update_xaxes(title_text=titulo_eixo, range=[-limite, limite],
                         zeroline=False, gridcolor=GRADE, row=1, col=coluna)
        fig.update_yaxes(title_text="Densidade", rangemode="tozero",
                         gridcolor=GRADE, zeroline=False, row=1, col=coluna)
        metadados["testes"][chave] = {
            "estatistica_exibida": observado, "critico": critico,
            "p_valor": float(resultado["p_valor"]), "referencia": referencia,
        }
    fig.update_layout(
        title={"text": "G2: regiões críticas e p-valores"
               "<br><sup>Distribuições de referência aproximadas sob H₀ · "
               f"testes bicaudais · α = {alfa:g}</sup>"},
        height=590, plot_bgcolor="white", font={"color": TINTA},
        legend={"orientation": "h", "y": -0.20, "x": 0},
        margin={"t": 155, "r": 25, "l": 65, "b": 145}, meta=metadados,
    )
    return fig
