"""Ponto de entrada do dashboard do Lab04 no Streamlit Cloud.

O Streamlit Cloud instala o requirements.txt da pasta do arquivo principal, mas
quebra o caminho no espaço de "LABORATORIO 04" (uv lê "04/requirements.txt").
Por isso o app é publicado a partir da raiz, com o requirements.txt daqui.
Localmente, continue usando "streamlit run app.py" dentro de LABORATORIO 04.
"""
import runpy
import sys
from pathlib import Path

LAB04 = Path(__file__).resolve().parent / "LABORATORIO 04"
if str(LAB04) not in sys.path:
    sys.path.insert(0, str(LAB04))
runpy.run_path(str(LAB04 / "app.py"), run_name="__main__")
