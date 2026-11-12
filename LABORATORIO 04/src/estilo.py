"""Identidade visual comum aos gráficos do laboratório.

As cores dos grupos identificam PRs com e sem bot; as cores dos testes
permanecem constantes nas referências, no Monte Carlo e na análise de n.
"""

CORES_GRUPO = {"com_bot": "#1baf7a", "sem_bot": "#6250d6"}
CORES_TESTE = {"welch": "#2563eb", "mann_whitney": "#d97706"}
NOMES_TESTE = {"welch": "Welch", "mann_whitney": "Mann–Whitney"}
NOMES_SITUACAO = {
    "base": "Cenário base",
    "assimetria_forte": "Assimetria forte",
    "outliers": "Contaminação por outliers",
    "n_pequeno": "Amostra pequena",
    "variancias_diferentes": "Variâncias diferentes",
}
TINTA = "#52514e"
GRADE = "#e5e4df"


def aplicar_estilo(figura):
    """Aplica tema comum sem modificar dados, cores ou limites dos eixos."""
    figura.update_layout(
        template="plotly_white", paper_bgcolor="white", plot_bgcolor="white",
        font={"family": "Arial, sans-serif", "size": 13, "color": TINTA},
        title={"x": 0, "xanchor": "left"},
        legend={"orientation": "h", "y": -0.20, "x": 0,
                "title": {"text": "Teste"}},
        margin={"t": 100, "r": 25, "l": 70, "b": 120},
    )
    figura.update_xaxes(linecolor=TINTA, gridcolor=GRADE, zeroline=False)
    figura.update_yaxes(linecolor=TINTA, gridcolor=GRADE, zeroline=False)
    return figura
