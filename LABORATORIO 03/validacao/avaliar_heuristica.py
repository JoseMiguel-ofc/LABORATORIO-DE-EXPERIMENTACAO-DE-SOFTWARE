"""Avalia a release corretiva contra o consenso humano da Pessoa A.

O consenso rotula a própria release, não a release anterior marcada como
falha no CFR(b). Sem consenso, as métricas são nulas. Cada execução registra
as duas versões, sem escolher automaticamente uma versão pelos resultados.
"""

import argparse
from collections import defaultdict
import csv
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile

import yaml

from metricas.cfr import DEFINICOES_VERSOES, analisar_cfr_b
from metricas.frequencia import semanas_da_janela
from pipeline.dados_entrega import VERSOES, booleano, carregar_releases, linhas_csv


DEFINICOES = DEFINICOES_VERSOES


def _chave(linha):
    chave = (linha.get("full_name"), linha.get("tag_name"))
    if not all(chave):
        raise ValueError("Item sem full_name/tag_name")
    return chave


def carregar_consenso(caminho):
    """Lê o formato gerado por validacao.consenso; ausência retorna None."""
    if caminho is None or not Path(caminho).exists():
        return None
    return list(linhas_csv(caminho, {"full_name", "tag_name", "corretiva", "metodo_corretiva"}))


def avaliar_previsoes(previsoes, consenso, *, limiar_f1=0.70):
    """Precisão, recall e F1 da classe positiva; ausentes não viram negativos.

    Métricas condicionam-se aos itens com consenso e previsão conclusiva.
    A cobertura informa quantos rótulos humanos puderam ser avaliados.
    """
    if not 0 <= limiar_f1 <= 1:
        raise ValueError("limiar_f1 deve estar entre 0 e 1")
    por_chave = {}
    for previsao in previsoes:
        chave = _chave(previsao)
        if chave in por_chave:
            raise ValueError(f"Previsão duplicada: {chave}")
        por_chave[chave] = booleano(previsao.get("corretiva"), campo="corretiva prevista")
    resultado = {"status": "pendente_consenso", "alvo": "corretiva_da_propria_release",
                 "n_consenso": 0, "n_rotulados": 0, "n_pendentes": 0, "n_avaliados": 0,
                 "n_ausentes": 0, "n_inconclusivas": 0, "n_previsoes": len(por_chave),
                 "precisao": None, "recall": None, "f1": None, "cobertura": None,
                 "limiar_f1": limiar_f1, "atingiu_meta": None,
                 "matriz_confusao": {"tp": 0, "fp": 0, "fn": 0, "tn": 0}}
    if consenso is None:
        return resultado
    vistas = set()
    for linha in consenso:
        chave = _chave(linha)
        if chave in vistas:
            raise ValueError(f"Consenso duplicado: {chave}")
        vistas.add(chave)
        resultado["n_consenso"] += 1
        metodo = str(linha.get("metodo_corretiva") or "").strip().lower()
        if metodo in {"", "pendente"}:
            resultado["n_pendentes"] += 1
            continue
        if metodo not in {"maioria", "reuniao", "reunião"}:
            raise ValueError(f"Método de consenso inválido: {metodo!r}")
        real = booleano(linha.get("corretiva"), campo="corretiva do consenso")
        if real is None:
            raise ValueError(f"Consenso {metodo} sem rótulo em {chave}")
        resultado["n_rotulados"] += 1
        if chave not in por_chave:
            resultado["n_ausentes"] += 1
            continue
        prevista = por_chave[chave]
        if prevista is None:
            resultado["n_inconclusivas"] += 1
            continue
        categoria = "tp" if real and prevista else "fn" if real else "fp" if prevista else "tn"
        resultado["matriz_confusao"][categoria] += 1
        resultado["n_avaliados"] += 1
    n = resultado["n_avaliados"]
    rotulados = resultado["n_rotulados"]
    resultado["cobertura"] = n / rotulados if rotulados else None
    if not rotulados:
        return resultado
    if not n:
        resultado["status"] = "pendente_previsoes_conclusivas"
        return resultado
    tp, fp, fn = (resultado["matriz_confusao"][campo] for campo in ("tp", "fp", "fn"))
    resultado["precisao"] = tp / (tp + fp) if tp + fp else None
    resultado["recall"] = tp / (tp + fn) if tp + fn else None
    resultado["f1"] = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
    if resultado["f1"] is None:
        resultado["status"] = "f1_indefinido_sem_positivos"
    elif resultado["f1"] < limiar_f1:
        resultado.update(status="requer_refinamento", atingiu_meta=False)
    else:
        completa = n == rotulados and resultado["n_pendentes"] == 0
        resultado.update(status="meta_atingida_na_amostra" if completa else "avaliacao_parcial",
                         atingiu_meta=True)
    return resultado


def avaliar_versoes(releases, consenso, inicio, fim, *, versoes=VERSOES, limiar_f1=0.70):
    """Produz uma avaliação por versão, com a previsão da própria release."""
    semanas_da_janela(inicio, fim)
    por_repo = defaultdict(list)
    for release in releases:
        por_repo[release["full_name"]].append(release)
    consenso = None if consenso is None else list(consenso)
    avaliacoes = []
    for versao in versoes:
        if versao not in DEFINICOES:
            raise ValueError(f"Versão desconhecida: {versao}")
        previsoes = []
        for nome, historico in sorted(por_repo.items()):
            analise = analisar_cfr_b(historico, inicio, fim, versao=versao)
            for linha in analise["releases"]:
                # Censura de falhou não invalida a classificação corretiva própria.
                if linha["na_janela"] and linha["estavel"]:
                    previsoes.append({**linha, "full_name": nome})
        avaliacoes.append({"versao": versao, "definicao": DEFINICOES[versao],
                           **avaliar_previsoes(previsoes, consenso, limiar_f1=limiar_f1)})
    return avaliacoes


def hash_arquivo(caminho):
    caminho = Path(caminho)
    if not caminho.exists():
        return {"caminho": str(caminho.resolve()), "presente": False, "sha256": None}
    resumo = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            resumo.update(bloco)
    return {"caminho": str(caminho.resolve()), "presente": True, "sha256": resumo.hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--releases", default="dados/releases.csv")
    parser.add_argument("--commits", help="CSV ou CSV.gz; se omitido, procura ao lado de releases")
    parser.add_argument("--consenso", default="validacao/consenso_releases.csv")
    parser.add_argument("--inicio")
    parser.add_argument("--fim")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--historico", default="validacao/historico_heuristica.jsonl")
    parser.add_argument("--saida", default="validacao/avaliacao_heuristica.json")
    args = parser.parse_args(argv)
    try:
        return _executar(args)
    except (OSError, ValueError, KeyError, csv.Error, yaml.YAMLError) as erro:
        parser.error(str(erro))


def _executar(args):
    inicio, fim = args.inicio, args.fim
    if inicio is None or fim is None:
        with Path(args.config).open(encoding="utf-8") as arquivo:
            config = yaml.safe_load(arquivo)
        if not isinstance(config, dict) or not isinstance(config.get("janela"), dict):
            raise ValueError("Configuração deve conter janela com inicio e fim")
        inicio = inicio or config["janela"]["inicio"]
        fim = fim or config["janela"]["fim"]
        if not inicio or not fim:
            raise ValueError("Configuração deve conter inicio e fim não vazios")
    if not all(isinstance(valor, (str, date)) for valor in (inicio, fim)):
        raise ValueError("inicio e fim devem ser datas no formato YYYY-MM-DD")
    semanas_da_janela(inicio, fim)
    commits = Path(args.commits) if args.commits else None
    if commits is None:
        pasta = Path(args.releases).parent
        commits = next((p for p in [pasta / "commits.csv", pasta / "commits.csv.gz"] if p.exists()), None)
    fontes = {Path(args.releases).resolve(), Path(args.consenso).resolve()}
    if commits is not None:
        fontes.add(commits.resolve())
    fontes.add(Path(args.config).resolve())
    saida, historico = Path(args.saida), Path(args.historico)
    if saida.resolve() in fontes or historico.resolve() in fontes or saida.resolve() == historico.resolve():
        raise ValueError("As saídas precisam ser distintas e não podem sobrescrever fontes")
    entradas = {"releases": hash_arquivo(args.releases), "consenso": hash_arquivo(args.consenso),
                "commits": hash_arquivo(commits) if commits else None,
                "codigo_cfr": hash_arquivo(Path(__file__).parents[1] / "metricas" / "cfr.py")}
    releases = carregar_releases(args.releases, commits)
    consenso = carregar_consenso(args.consenso)
    avaliacoes = avaliar_versoes(releases, consenso, inicio, fim)
    instante = datetime.now(timezone.utc).isoformat()
    parametros = {"inicio": str(inicio), "fim": str(fim), "limiar_f1": 0.70,
                  "limite_dias_corretiva": 7, "versoes": list(VERSOES)}
    registros = [{"executado_em_utc": instante, "entradas": entradas, "parametros": parametros,
                  **avaliacao} for avaliacao in avaliacoes]
    relatorio = {"executado_em_utc": instante, "entradas": entradas, "parametros": parametros,
                 "avaliacoes": avaliacoes, "versao_selecionada": None,
                 "observacao": "Amostra sintética não substitui consenso humano. "
                               "Métricas excluem previsões ausentes/inconclusivas; consulte a cobertura."}
    saida.parent.mkdir(parents=True, exist_ok=True)
    historico.parent.mkdir(parents=True, exist_ok=True)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=saida.parent,
                                         prefix=f".{saida.name}.", suffix=".tmp", delete=False) as arquivo:
            temporario = Path(arquivo.name)
            json.dump(relatorio, arquivo, ensure_ascii=False, indent=2, allow_nan=False)
            arquivo.write("\n")
            arquivo.flush()
            os.fsync(arquivo.fileno())
        with historico.open("a", encoding="utf-8") as arquivo:
            arquivo.write("".join(json.dumps(registro, ensure_ascii=False, allow_nan=False) + "\n"
                                  for registro in registros))
        os.replace(temporario, saida)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)
    for avaliacao in avaliacoes:
        print(f"{avaliacao['versao']}: {avaliacao['status']}; F1={avaliacao['f1']}; "
              f"avaliados={avaliacao['n_avaliados']}; cobertura={avaliacao['cobertura']}")
    return relatorio


if __name__ == "__main__":
    main()
