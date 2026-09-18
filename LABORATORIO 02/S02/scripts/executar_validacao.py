#!/usr/bin/env python3
"""Executa soluções, guarda evidências e reúne testes e métricas por arquivo."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version, PackageNotFoundError
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import time


LAB = Path(__file__).resolve().parents[2]
S01 = LAB / "S01"
PADRAO_SOLUCOES = LAB / "S02/validacao_tecnica/solucoes"
KATAS = tuple(sorted(p.stem for p in (S01 / "testes").glob("*.json")))


def salvar_csv(caminho, linhas):
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)


def ler_csv(caminho):
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


def resumir_teste(kata, codigo, texto):
    resumo = re.search(
        rf"^{re.escape(kata)}: (\d+)/(\d+) casos aprovados\.$", texto, re.MULTILINE,
    )
    if resumo:
        aprovados, total = map(int, resumo.groups())
        status = "APROVADO" if codigo == 0 and aprovados == total else "REPROVADO"
        return status, aprovados, total
    if "Tempo limite dos testes excedido" in texto:
        return "TIMEOUT", "", ""
    if "Não foi possível carregar a solução" in texto:
        return "ERRO_CARGA", "", ""
    # Um processo sem resumo não comprova execução dos testes, mesmo retornando 0.
    return "ERRO_EXECUTOR", "", ""


def executar(comando, log):
    processo = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log.write_text(processo.stdout, encoding="utf-8")
    return processo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pasta-solucoes", type=Path, default=PADRAO_SOLUCOES)
    parser.add_argument("--saida", type=Path, help="Diretório novo; por padrão usa data/hora UTC")
    args = parser.parse_args()
    arquivos = sorted(args.pasta_solucoes.resolve().glob("*.py"))
    if not arquivos:
        parser.error("Nenhuma solução .py encontrada")
    try:
        radon = version("radon")
    except PackageNotFoundError:
        parser.error("Instale S01/scripts/requirements.txt no Python usado para este comando")

    for arquivo in arquivos:
        partes = arquivo.stem.split("__")
        if len(partes) != 3 or not partes[0] or partes[1] not in KATAS or partes[2] not in ("COM_IA", "SEM_IA"):
            parser.error(f"Nome de solução inválido: {arquivo.name}")

    agora = datetime.now(timezone.utc)
    saida = args.saida or LAB / "S02/resultados/validacoes" / agora.strftime("%Y%m%dT%H%M%S%fZ")
    saida = saida.resolve()
    if saida.exists():
        parser.error("A pasta de saída já existe; use outra para preservar as evidências")
    saida.mkdir(parents=True)
    logs = saida / "logs"
    logs.mkdir()
    evidencias = saida / "fontes"
    evidencias.mkdir()
    hashes = {}
    # Arquiva exatamente as soluções, contratos, casos e ferramentas usados.
    fontes = arquivos + sorted((S01 / "testes").glob("*.json")) + [
        S01 / "scripts/executar_testes.py", S01 / "scripts/metricas_estaticas.py",
        Path(__file__), Path(__file__).with_name("metricas_duplicacao.py"),
    ] + sorted((S01 / "katas").glob("*.md"))
    for indice, arquivo in enumerate(fontes):
        copia = f"{indice:02d}_{arquivo.name}"
        conteudo = arquivo.read_bytes()
        (evidencias / copia).write_bytes(conteudo)
        hashes[str(arquivo.relative_to(LAB)) if arquivo.is_relative_to(LAB) else str(arquivo)] = {
            "sha256": hashlib.sha256(conteudo).hexdigest(), "copia": f"fontes/{copia}",
        }

    linhas = []
    for arquivo in arquivos:
        integrante, kata, tratamento = arquivo.stem.split("__")
        inicio = datetime.now(timezone.utc).isoformat()
        marco = time.monotonic()
        log = logs / f"{arquivo.stem}.txt"
        processo = executar([
            sys.executable, str(S01 / "scripts/executar_testes.py"),
            "--kata", kata, "--arquivo", str(arquivo),
        ], log)
        duracao = time.monotonic() - marco
        status, aprovados, executados = resumir_teste(kata, processo.returncode, processo.stdout)
        total = len(json.loads((S01 / "testes" / f"{kata}.json").read_text(encoding="utf-8")))
        if status == "APROVADO" and executados != total:
            status = "ERRO_EXECUTOR"
        linhas.append({
            "integrante": integrante, "kata": kata, "tratamento": tratamento,
            "tipo_registro": "VALIDACAO_TECNICA", "arquivo": arquivo.name,
            "inicio_testes_utc": inicio, "duracao_testes_segundos": round(duracao, 6),
            "status_testes": status, "casos_aprovados": aprovados,
            "casos_executados": executados, "total_casos": total,
            "codigo_saida": processo.returncode, "python": platform.python_version(),
            "sha256_solucao": hashlib.sha256(arquivo.read_bytes()).hexdigest(),
            "log": str(log.relative_to(saida)),
        })
        print(f"{arquivo.name}: {status} ({aprovados}/{total})")
    salvar_csv(saida / "resultados_testes.csv", linhas)

    for script, nome in [
        (S01 / "scripts/metricas_estaticas.py", "metricas_estaticas"),
        (Path(__file__).with_name("metricas_duplicacao.py"), "metricas_duplicacao"),
    ]:
        processo = executar([
            sys.executable, str(script), "--pasta", str(args.pasta_solucoes.resolve()),
            "--saida", str(saida / f"{nome}.csv"),
        ], logs / f"{nome}.txt")
        if processo.returncode:
            print(f"Falha ao coletar {nome}; consulte {logs}", file=sys.stderr)
            return 1
        metricas = {linha["arquivo"]: linha for linha in ler_csv(saida / f"{nome}.csv")}
        for linha in linhas:
            for campo, valor in metricas[linha["arquivo"]].items():
                if campo not in ("integrante", "kata", "tratamento", "arquivo"):
                    linha[campo] = valor

    salvar_csv(saida / "validacao_consolidada.csv", linhas)
    manifesto = {
        "tipo_registro": "VALIDACAO_TECNICA", "inicio_utc": agora.isoformat(),
        "python": platform.python_version(), "radon": radon,
        "plataforma": platform.platform(), "arquivos": hashes,
        "nota": "Duração mede apenas testes. Não mede resolução humana nem conclusão em 35 minutos.",
    }
    (saida / "manifesto.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Evidências salvas em: {saida}")
    return 0 if all(linha["status_testes"] == "APROVADO" and not linha["erro"] for linha in linhas) else 1


if __name__ == "__main__":
    sys.exit(main())
