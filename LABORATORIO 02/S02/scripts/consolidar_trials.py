#!/usr/bin/env python3
"""Relaciona dados reais pela chave do trial, preservando ausências e exclusões."""

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


LAB = Path(__file__).resolve().parents[2]
CHAVE = ("integrante", "kata", "tratamento")
KATAS = {arquivo.stem for arquivo in (LAB / "S01/testes").glob("*.json")}
FONTES = {
    "tempo": "tempos_trials.csv",
    "avaliacao": "avaliacao_trials.csv",
    "estatica": "metricas_estaticas.csv",
    "duplicacao": "metricas_duplicacao.csv",
}


def consolidar(pasta):
    por_chave = {}
    campos = list(CHAVE)
    excluidos = []
    ausentes = []
    for fonte, nome in FONTES.items():
        caminho = pasta / nome
        if not caminho.exists():
            ausentes.append(nome)
            continue
        with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
            leitor = csv.DictReader(arquivo)
            cabecalho = leitor.fieldnames or []
            if any(campo not in cabecalho for campo in CHAVE):
                raise ValueError(f"{nome}: cabeçalho sem a chave completa do trial")
            detalhes = [campo for campo in cabecalho if campo not in CHAVE]
            campos.extend(f"{fonte}_{campo}" for campo in detalhes)
            vistos = set()
            for numero, linha in enumerate(leitor, start=2):
                chave = tuple((linha.get(campo) or "").strip() for campo in CHAVE)
                # O teste de instrumentação preexistente fica auditável na origem.
                if chave == ("Pedro", "Teste", "COM_IA"):
                    excluidos.append({"arquivo": nome, "linha": numero, "chave": chave,
                                      "motivo": "Teste de instrumentação documentado na S01"})
                    continue
                if not chave[0] or chave[1] not in KATAS or chave[2] not in ("COM_IA", "SEM_IA"):
                    raise ValueError(f"{nome}:{numero}: chave de trial inválida: {chave}")
                if chave in vistos:
                    raise ValueError(f"{nome}:{numero}: chave duplicada: {chave}")
                vistos.add(chave)
                registro = por_chave.setdefault(chave, {"fontes": set(), **dict(zip(CHAVE, chave))})
                registro["fontes"].add(fonte)
                registro.update({f"{fonte}_{campo}": linha.get(campo, "") for campo in detalhes})

    campos.append("fontes_pendentes")
    linhas = []
    for chave in sorted(por_chave):
        registro = por_chave[chave]
        presentes = registro.pop("fontes")
        registro["fontes_pendentes"] = ";".join(fonte for fonte in FONTES if fonte not in presentes)
        linhas.append(registro)
    return campos, linhas, excluidos, ausentes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resultados", type=Path, default=LAB / "S02/resultados")
    parser.add_argument("--saida", type=Path, help="Diretório novo para a consolidação")
    parser.add_argument("--esperados", type=int, default=12, help="Total previsto de trials (padrão: 12)")
    args = parser.parse_args()
    if args.esperados < 1:
        parser.error("--esperados precisa ser positivo")
    if not args.resultados.is_dir():
        parser.error("Pasta de resultados inexistente")
    try:
        campos, linhas, excluidos, ausentes = consolidar(args.resultados)
    except ValueError as erro:
        parser.error(str(erro))
    agora = datetime.now(timezone.utc)
    saida = args.saida or args.resultados / "consolidacoes" / agora.strftime("%Y%m%dT%H%M%S%fZ")
    if saida.exists():
        parser.error("A saída já existe; use outra pasta para preservar o histórico")
    saida.mkdir(parents=True)
    with (saida / "trials_consolidados.csv").open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(linhas)
    tempos = sum(bool(linha.get("tempo_tempo_segundos")) for linha in linhas)
    avaliados = sum(bool(linha.get("avaliacao_status_testes")) for linha in linhas)
    completos = sum(not linha["fontes_pendentes"] for linha in linhas)
    diagnostico = {
        "gerado_em_utc": agora.isoformat(), "trials_esperados": args.esperados,
        "chaves_encontradas": len(linhas), "trials_com_tempo": tempos,
        "trials_com_avaliacao": avaliados, "trials_com_todas_as_fontes": completos,
        "tempos_faltantes_para_total": max(0, args.esperados - tempos),
        "arquivos_ausentes": ausentes, "registros_excluidos": excluidos,
        "coleta_completa_em_quantidade": tempos == avaliados == completos == len(linhas) == args.esperados,
        "nota": "Consolidar não valida o desenho, valores ou balanceamento. Rode também validar_trials.py. Campos vazios não foram imputados.",
    }
    (saida / "diagnostico.json").write_text(json.dumps(diagnostico, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Consolidação gerada: {len(linhas)} chaves, {tempos}/{args.esperados} tempos, {avaliados} avaliações.")
    print(f"Registros de instrumentação excluídos: {len(excluidos)}. Saída: {saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
