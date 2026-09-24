#!/usr/bin/env python3
"""Cria uma cópia experimental SEM_IA com a origem assistida explicitada."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys

from executar_validacao import LAB, PADRAO_SOLUCOES, ler_csv, salvar_csv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, help="Pasta nova para a simulação")
    args = parser.parse_args()
    fontes = sorted(PADRAO_SOLUCOES.glob("*__COM_IA.py"))
    if not fontes:
        parser.error("Nenhuma solução COM_IA disponível para a simulação")
    instante = datetime.now(timezone.utc)
    saida = args.saida or LAB / "S02/resultados/simulacoes" / instante.strftime("%Y%m%dT%H%M%S%fZ")
    saida = saida.resolve()
    if saida.exists():
        parser.error("A saída já existe; escolha uma pasta nova")
    solucoes = saida / "solucoes"
    solucoes.mkdir(parents=True)
    for fonte in fontes:
        shutil.copyfile(fonte, solucoes / fonte.name.replace("__COM_IA.py", "__SEM_IA.py"))

    nota = (
        "SEM_IA é um rótulo simulado para testar o fluxo de dados. "
        "Os códigos foram gerados com IA, e sua origem é COM_IA. "
        "Os resultados dos testes e as métricas foram medidos nesta execução. "
        "Não há tempos de resolução humana nem trials reais SEM_IA."
    )
    (saida / "README.md").write_text(
        "# Simulação experimental SEM_IA\n\n" + nota + "\n\n"
        "- Soluções: `solucoes/`\n"
        "- Resultados: `validacao/validacao_consolidada.csv`\n"
        "- Evidências: `validacao/logs/` e `validacao/manifesto.json`\n\n"
        "Os CSVs registram `tratamento=SEM_IA`, `tipo_registro=SIMULACAO`, "
        "`tratamento_original=COM_IA` e `origem_codigo=GERADO_COM_IA`.\n",
        encoding="utf-8",
    )
    validacao = saida / "validacao"
    processo = subprocess.run([
        sys.executable, str(Path(__file__).with_name("executar_validacao.py")),
        "--pasta-solucoes", str(solucoes), "--saida", str(validacao),
    ])
    for arquivo in validacao.glob("*.csv"):
        linhas = ler_csv(arquivo)
        for linha in linhas:
            linha.update(tipo_registro="SIMULACAO", tratamento_original="COM_IA",
                         origem_codigo="GERADO_COM_IA")
        if linhas:
            salvar_csv(arquivo, linhas)
    manifesto = validacao / "manifesto.json"
    if manifesto.exists():
        dados = json.loads(manifesto.read_text(encoding="utf-8"))
        dados.update(tipo_registro="SIMULACAO", tratamento="SEM_IA",
                     tratamento_original="COM_IA", origem_codigo="GERADO_COM_IA", nota=nota)
        manifesto.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Simulação SEM_IA (origem COM_IA): {saida}")
    return processo.returncode


if __name__ == "__main__":
    sys.exit(main())
