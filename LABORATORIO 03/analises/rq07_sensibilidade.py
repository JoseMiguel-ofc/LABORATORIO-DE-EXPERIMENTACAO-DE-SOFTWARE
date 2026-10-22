"""RQ07 — análise de sensibilidade offline sobre os CSVs da Sprint 02.

Uso: python -m analises.rq07_sensibilidade --config config.yaml
As comparações pareadas usam apenas repositórios com quatro métricas em AMBOS
os cenários; sem tags válidas, C3 fica indisponível, nunca é estimado.
"""
import argparse
import csv
from datetime import date
import json
from pathlib import Path
from collections import Counter, defaultdict

import yaml
from metricas.dora import classificar_repositorio, PONTOS

CATEGORIAS = ("Low", "Medium", "High", "Elite")
COLUNAS = ("full_name", "cenario", "frequencia_semana", "lead_time_horas", "cfr", "recuperacao_horas", "categoria_geral", "completa", "motivo")


def ler_csv(caminho):
    with Path(caminho).open(encoding="utf-8-sig", newline="") as f:
        leitor = csv.DictReader(f)
        if not leitor.fieldnames or "full_name" not in leitor.fieldnames:
            raise ValueError(f"CSV sem full_name: {caminho}")
        return list(leitor)


def numero(valor):
    if valor is None or str(valor).strip() == "":
        return None
    n = float(valor)
    import math
    if not math.isfinite(n) or n < 0:
        raise ValueError(f"Valor numérico inválido: {valor!r}")
    return n


def duracao_semanas(inicio, fim):
    a, b = date.fromisoformat(str(inicio)), date.fromisoformat(str(fim))
    if b < a:
        raise ValueError("Janela inválida")
    return ((b - a).days + 1) / 7


def frequencias_alternativas(releases, tags, inicio, fim):
    """Contagem por ID de release e por nome de tag (evita duplicidade na frequência)."""
    pre = defaultdict(set)
    for r in releases:
        d = (r.get("published_at") or "")[:10]
        if r.get("draft", "").lower() in ("false", "0") and inicio <= d <= fim:
            rid = r.get("release_id") or (r.get("tag_name"), r.get("published_at"))
            # Release e pré-release publicados; IDs distintos contam eventos distintos.
            pre[r["full_name"]].add(str(rid))
    tagset = defaultdict(set)
    for t in tags:
        if (t.get("status") or "").lower() != "ok":
            continue
        if (t.get("na_janela") or "").lower() not in ("true", "1"):
            continue
        tagset[t["full_name"]].add(t["tag_name"])
    semanas = duracao_semanas(inicio, fim)
    return {k: len(v)/semanas for k, v in pre.items()}, {k: len(v)/semanas for k, v in tagset.items()}


def kappa_linear(pares):
    """Kappa ponderado linear de Cohen, equivalente a weights='linear'."""
    if not pares:
        return None
    n = len(pares)
    a, b = Counter(x for x, _ in pares), Counter(y for _, y in pares)
    distancia = lambda x, y: abs(PONTOS[x] - PONTOS[y]) / 3
    observado = sum(distancia(x, y) for x, y in pares) / n
    esperado = sum(a[x]*b[y]*distancia(x, y) for x in CATEGORIAS for y in CATEGORIAS) / n**2
    if esperado == 0:
        return 1.0 if observado == 0 else None
    return 1 - observado/esperado


def analisar(consolidadas, releases, tags, inicio, fim, tags_completas=False):
    freq_pre, freq_tag = frequencias_alternativas(releases, tags, inicio, fim)
    linhas = []
    por_cenario = defaultdict(dict)
    for repo in consolidadas:
        nome = repo["full_name"]
        if nome in por_cenario["C1"]:
            raise ValueError(f"Repositório duplicado: {nome}")
        alternativas = {
            "C1": (numero(repo.get("frequencia_releases_semana")), numero(repo.get("lead_time_a_horas")), numero(repo.get("cfr_a"))),
            "C2": (freq_pre.get(nome, 0.0) if repo.get("releases_status") == "ok" else None, numero(repo.get("lead_time_b_horas")), numero(repo.get("cfr_b")) if repo.get("coleta_cfr_b_status") == "ok" else None),
            "C3": (freq_tag.get(nome, 0.0) if tags_completas else None, numero(repo.get("lead_time_b_horas")), numero(repo.get("cfr_a"))),
        }
        rec = numero(repo.get("recuperacao_mediana_horas"))
        for cenario, (freq, lead, cfr) in alternativas.items():
            valores = (freq, lead, cfr, rec)
            faltantes = [campo for campo, valor in zip(("frequencia", "lead_time", "cfr", "recuperacao"), valores) if valor is None]
            motivo = ";".join(faltantes)
            if cenario == "C3" and not tags_completas:
                motivo = "tags_nao_coletadas"
            categoria = classificar_repositorio(*valores)["geral"] if not motivo else None
            linha = dict(full_name=nome, cenario=cenario, frequencia_semana=freq, lead_time_horas=lead,
                         cfr=cfr, recuperacao_horas=rec, categoria_geral=categoria,
                         completa=categoria is not None, motivo=motivo)
            linhas.append(linha)
            por_cenario[cenario][nome] = categoria
    comparacoes = []
    for a,b in (("C1","C2"),("C1","C3"),("C2","C3")):
        comuns = [(por_cenario[a][nome], por_cenario[b][nome]) for nome in por_cenario[a]
                  if por_cenario[a][nome] and por_cenario[b][nome]]
        n = len(comuns)
        mudaram = sum(x != y for x,y in comuns)
        comparacoes.append(dict(comparacao=f"{a}x{b}", comparaveis=n,
                                excluidos=len(consolidadas)-n, mudaram=mudaram,
                                percentual_mudanca=(100*mudaram/n if n else None),
                                kappa_linear=kappa_linear(comuns)))
    return linhas, comparacoes


def escrever_csv(caminho, linhas, colunas):
    with Path(caminho).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colunas)
        w.writeheader()
        w.writerows(linhas)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--dados", help="Diretório de dados (padrão: config.yaml)")
    args = p.parse_args(argv)
    cfg_path = Path(args.config).resolve()
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    dados = Path(args.dados) if args.dados else cfg_path.parent / cfg["saida"]["dir"]
    inicio, fim = str(cfg["janela"]["inicio"]), str(cfg["janela"]["fim"])
    consolidadas = ler_csv(dados / "metricas_consolidadas.csv")
    releases = ler_csv(dados / "releases.csv")
    tags_file = dados / "tags.csv"
    tags = ler_csv(tags_file) if tags_file.exists() else []
    # Tags só são completas se TODAS as linhas de status por repositório confirmarem coleta.
    # Não basta existir o CSV; no estado inicial a coleta de tags está desativada.
    status_file = dados / "status_tags_rq07.csv"
    if status_file.exists():
        estados = ler_csv(status_file)
        esperados = {r["full_name"] for r in consolidadas}
        por_repo = {e["full_name"]: e.get("tags_status") for e in estados}
        tags_completas = (bool(esperados) and len(estados) == len(esperados)
                          and set(por_repo) == esperados
                          and all(status == "ok" for status in por_repo.values()))
    else:
        status_file = dados / "metricas_entrega.csv"
        estados = ler_csv(status_file) if status_file.exists() else []
        tags_completas = bool(estados) and len(estados) == len(consolidadas) and all(
            e.get("tags_status") == "ok" for e in estados)
    linhas, pares = analisar(consolidadas, releases, tags, inicio, fim, tags_completas=tags_completas)
    escrever_csv(dados / "rq07_classificacoes.csv", linhas, COLUNAS)
    escrever_csv(dados / "rq07_comparacoes.csv", pares,
                 ("comparacao", "comparaveis", "excluidos", "mudaram", "percentual_mudanca", "kappa_linear"))
    resumo = {"repositorios": len(consolidadas), "tags_completas": tags_completas,
              "observacao": "Pares calculados apenas sobre repositórios com 4 métricas nos dois cenários",
              "comparacoes": pares}
    (dados / "rq07_resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    for x in pares:
        print(f"{x['comparacao']}: n={x['comparaveis']}, mudança={x['percentual_mudanca']}, kappa={x['kappa_linear']}")
    if not tags_completas:
        print("AVISO: C3 indisponível — é necessário coletar tags dos 300 repositórios.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
