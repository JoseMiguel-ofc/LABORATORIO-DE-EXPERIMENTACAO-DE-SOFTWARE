"""Dashboard do Lab04: t de Welch × Mann-Whitney no tempo de merge de PRs."""
import numpy as np
import pandas as pd
import streamlit as st

from src.cenario import ALFA, H0, H1, PERGUNTA, PREVISAO, SEMENTE, ajustar_cenario
from src.coleta import BOT, FIM, INICIO, REPO
from src.dados import GRUPOS, carregar, resumo
from src.graficos import g1, g2
from src.simulacao import gerar
from src.testes import aplicar_testes

REPOSITORIO = ("https://github.com/JoseMiguel-ofc/LABORATORIO-DE-EXPERIMENTACAO-DE-SOFTWARE"
               "/tree/main/LABORATORIO%2004")
PROJECT = ""  # Preencher com o link do GitHub Project
DASHBOARD = ""  # Preencher com o link público


def link(rotulo, url):
    return f"[{rotulo}]({url})" if url else f"{rotulo}: *a preencher*"


def em_construcao(entrega, sprint):
    st.info(f"{entrega}: previsto para a {sprint}.")


st.set_page_config(page_title="Lab04: Welch × Mann-Whitney", layout="wide")
st.title("Testes de hipótese por dentro")
st.markdown("Bot de revisão e tempo até o merge: **t de Welch × Mann-Whitney**")
st.markdown(" · ".join([link("Dashboard publicado", DASHBOARD),
                        link("Repositório", REPOSITORIO),
                        link("GitHub Project", PROJECT)]))

df = carregar()
reais = {grupo: df.loc[df["grupo"] == grupo, "horas"].to_numpy() for grupo in GRUPOS}
tabela = resumo(df)
cenario = ajustar_cenario(df)
simulados = gerar(10_000, situacao="ajuste_real", rng=np.random.default_rng(SEMENTE),
                  cenario=cenario)

st.header("1. Cenário")
st.markdown(f"""
**Pergunta.** {PERGUNTA}

- **H₀ da simulação:** {H0}
- **H₁ da simulação:** {H1}

Os testes são **bicaudais**, pois investigamos diferenças em qualquer direção,
com nível de significância **α = {ALFA:.2f}**.

**Dados reais.** {len(df)} PRs mergeados de
[{REPO}](https://github.com/{REPO}), {len(reais["com_bot"])} revisados pelo bot
`{BOT}` e {len(reais["sem_bot"])} sem ele, entre {INICIO:%d/%m/%Y} e {FIM:%d/%m/%Y}.
Cada PR foi sorteado da população completa do período, com 5 PRs por mês em cada
grupo. Autores bot e backports ficaram de fora. O tempo até o merge vai da abertura
do PR até o merge, em horas.
""")
st.markdown(f"**Previsão antes de medir erro tipo I e poder.** {PREVISAO}")

st.header("2. Os dados")
log = st.radio("Escala do eixo x", ["Logarítmica", "Linear"], horizontal=True) == "Logarítmica"
st.plotly_chart(g1(reais, simulados, log=log), theme=None)
st.dataframe(tabela.style.format({coluna: "{:.2f}" for coluna in tabela.columns
                                  if coluna not in ("n", "Outliers (Tukey)")}
                                 | {"n": "{:.0f}", "Outliers (Tukey)": "{:.0f}"}),
             width="stretch")
st.markdown("Os tempos reais têm forte assimetria à direita: poucos PRs muito demorados "
            "elevam a média. O G1 usa uma lognormal ajustada separadamente a cada grupo, "
            "com média e desvio padrão dos logaritmos dos tempos reais. A cauda do "
            "modelo pode ser mais longa que a observada; o ajuste descritivo não "
            "significa que os grupos sejam iguais sob H₀.")
st.caption("G1: 10.000 observações simuladas por grupo, semente 42. As faixas são "
           "definidas pelos dados reais; valores simulados fora delas não aparecem "
           "nas barras, em ambas as escalas. Os percentuais usam a amostra inteira.")
with st.expander("Parâmetros da simulação e diferença entre G1 e o cenário base"):
    parametros = pd.DataFrame.from_dict(cenario["parametros_descritivos"], orient="index")
    parametros.index = parametros.index.map(GRUPOS)
    st.dataframe(parametros.rename(columns={
        "mu": "μ de log(horas)", "sigma": "σ de log(horas)", "n": "n real",
        "media_modelo": "Média do modelo (h)",
        "mediana_modelo": "Mediana do modelo (h)",
    }).style.format(precision=3), width="stretch")
    base = cenario["parametros_base"]
    st.markdown(f"No cenário base, os logaritmos dos **{len(df)} PRs** são reunidos: "
                f"**μ = {base['mu']:.3f}** e **σ = {base['sigma']:.3f}**. "
                "Os dois grupos usam esses mesmos parâmetros quando o efeito é zero, "
                "com sorteios independentes. Um efeito de 30% multiplica os tempos "
                "do grupo com bot por 1,30, alterando sua média e sua mediana "
                "populacionais nessa proporção; isso é uma intervenção na simulação.")

st.header("3. Como os testes funcionam")
st.markdown("**Welch compara médias** de duas amostras independentes, sem exigir "
            "variâncias iguais. **Mann-Whitney compara os postos** das observações "
            "e testa a igualdade das distribuições; interpretá-lo como um teste "
            "de medianas exige condições adicionais sobre suas formas.")
col_n, col_efeito = st.columns(2)
with col_n:
    n_exemplo = st.number_input("PRs por grupo no exemplo", min_value=10, max_value=200,
                                value=30, step=10)
with col_efeito:
    efeito_percentual = st.slider("Mudança simulada no tempo do grupo com bot (%)",
                                  min_value=-80, max_value=200, value=30, step=10,
                                  help="0%: H₀ verdadeira; positivo: mais tempo; "
                                       "negativo: menos tempo. Não é um efeito causal estimado.")
exemplo = gerar(int(n_exemplo), efeito_percentual / 100, "base",
                np.random.default_rng(SEMENTE), cenario=cenario)
resultados = aplicar_testes(exemplo["com_bot"], exemplo["sem_bot"], alfa=ALFA)
st.caption(f"Um único conjunto simulado, com {n_exemplo} PRs por grupo, "
           f"semente {SEMENTE} e efeito configurado de {efeito_percentual}%. "
           "Uma realização não mede poder nem erro tipo I.")
st.dataframe(pd.DataFrame([
    {"Teste": r["nome"], "Estatística": r["estatistica"], "p-valor": r["p_valor"],
     "Decisão (α = 0,05)": "Rejeitar H₀" if r["rejeita_h0"] else "Não rejeitar H₀"}
    for r in resultados.values()
]).style.format({"Estatística": "{:.4f}", "p-valor": "{:.6f}"}),
    hide_index=True, width="stretch")
st.plotly_chart(g2(resultados, alfa=ALFA), theme=None)
st.markdown("O G2 mostra as **distribuições de referência aproximadas sob H₀**: "
            "t com os graus de liberdade de Welch e normal padrão para U padronizado "
            "em Z. As duas caudas além dos limites críticos formam a região de "
            "rejeição, enquanto as caudas tão extremas quanto a estatística observada "
            "formam a área do p-valor. O p-valor não é a probabilidade de H₀ ser verdadeira. "
            "Com dados lognormais assimétricos, a calibração dessas aproximações "
            "precisa ser investigada por repetições na Sprint 2.")
st.caption("Na tabela, a estatística de Mann-Whitney é U do grupo com bot; no G2 ela "
           "é padronizada em Z. Usamos aproximação normal com correção de empates, "
           "sem correção de continuidade, para que a área exibida corresponda ao p-valor. "
           "As áreas informadas incluem as caudas até infinito; o desenho usa uma janela finita.")
for resultado in resultados.values():
    st.markdown(f"**{resultado['nome']}:** {resultado['interpretacao']}")

st.header("4. Erro tipo I")
em_construcao("G3", "Sprint 2")

st.header("5. Poder")
em_construcao("G4", "Sprint 2")

st.header("6. Dados reais")
em_construcao("Tabela com os dois testes", "Entrega Final")

st.header("7. Conclusão")
em_construcao("Conclusão", "Entrega Final")
