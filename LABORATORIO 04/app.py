"""Dashboard do Lab04: t de Welch × Mann-Whitney no tempo de merge de PRs."""
import numpy as np
import streamlit as st

from src.coleta import BOT, FIM, INICIO, REPO
from src.dados import GRUPOS, carregar, resumo, simular_provisorio
from src.graficos import g1

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
simulados = simular_provisorio(df, np.random.default_rng(42))

st.header("1. Cenário")
st.markdown(f"""
**Pergunta.** PRs revisados por um bot chegam ao merge em um tempo diferente dos PRs sem bot?

- **H₀:** o tempo até o merge se distribui da mesma forma nos dois grupos.
- **H₁:** o tempo até o merge difere entre os grupos (teste bicaudal).

**Dados reais.** {len(df)} PRs mergeados de
[{REPO}](https://github.com/{REPO}), {len(reais["com_bot"])} revisados pelo bot
`{BOT}` e {len(reais["sem_bot"])} sem ele, entre {INICIO:%d/%m/%Y} e {FIM:%d/%m/%Y}.
Cada PR foi sorteado da população completa do período, com 5 PRs por mês em cada
grupo. Autores bot e backports ficaram de fora. O tempo até o merge vai da abertura
do PR até o merge, em horas.
""")

st.header("2. Os dados")
log = st.radio("Escala do eixo x", ["Logarítmica", "Linear"], horizontal=True) == "Logarítmica"
st.plotly_chart(g1(reais, simulados, log=log), width="stretch", theme=None)
st.dataframe(tabela.style.format({coluna: "{:.2f}" for coluna in tabela.columns
                                  if coluna not in ("n", "Outliers (Tukey)")}
                                 | {"n": "{:.0f}", "Outliers (Tukey)": "{:.0f}"}),
             width="stretch")
st.caption("Dados simulados provisórios: lognormal ajustada aos dados reais, "
           "até o gerador da simulação ficar pronto. Na escala linear, o eixo termina "
           "no maior valor real, e os simulados acima dele ficam fora do gráfico.")

st.header("3. Como os testes funcionam")
em_construcao("G2", "Sprint 1")

st.header("4. Erro tipo I")
em_construcao("G3", "Sprint 2")

st.header("5. Poder")
em_construcao("G4", "Sprint 2")

st.header("6. Dados reais")
em_construcao("Tabela com os dois testes", "Entrega Final")

st.header("7. Conclusão")
em_construcao("Conclusão", "Entrega Final")
