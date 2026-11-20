"""Executa o notebook piloto usando o mesmo Python deste comando.

Uso na pasta do Lab05: python -m analise.executar_notebook
O notebook lê o CSV existente e atualiza seus resultados descritivos.
"""
from pathlib import Path
import os
import sys

import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager

RAIZ = Path(__file__).resolve().parents[1]


def main():
    caminho = RAIZ / "analise" / "piloto.ipynb"
    notebook = nbformat.read(caminho, as_version=4)
    nbformat.validate(notebook)
    kernel = KernelManager(kernel_name="python3",
                           transport="ipc" if os.name != "nt" else "tcp")
    # Evita executar por engano com um Python global sem as dependências do Lab05.
    kernel.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher",
                               "-f", "{connection_file}"]
    cliente = NotebookClient(notebook, km=kernel, timeout=180,
                             resources={"metadata": {"path": str(RAIZ)}})
    try:
        cliente.execute()
    finally:
        if kernel.has_kernel:
            kernel.shutdown_kernel(now=True)
    nbformat.write(notebook, caminho)
    print(f"Notebook executado sem erros: {caminho}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
