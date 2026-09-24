#!/usr/bin/env python3
"""H2: proporção de trials concluídos em 35 minutos e McNemar exato.

Os pares são formados por integrante e família de kata (déficit ou excesso).
Dois pares do mesmo integrante não são independentes; o p-valor combinado é
exploratório e não deve ser interpretado como evidência confirmatória.
"""

import argparse
import csv
from collections import Counter, defaultdict
from html import escape
from math import comb, isfinite
from pathlib import Path


LAB = Path(__file__).resolve().parents[2]
CONSOLIDACOES = LAB / "S02" / "resultados" / "consolidacoes"
SAIDA_PADRAO = LAB / "S03" / "resultados"
LIMITE_SEGUNDOS = 35 * 60
TRATAMENTOS = ("COM_IA", "SEM_IA")
FAMILIAS = {
    "ReposicaoEstoque": "deficit",
    "MetaProducao": "deficit",
    "ExcessoBagagem": "excesso",
    "ConsumoEnergetico": "excesso",
}
CAMPOS_OBRIGATORIOS = {
    "integrante", "kata", "tratamento", "tempo_tempo_segundos",
    "tempo_censurado", "avaliacao_concluido", "avaliacao_casos_aprovados",
    "avaliacao_total_casos", "avaliacao_status_testes",
}
CAMPOS_TRIAL = [
    "integrante", "kata", "familia", "tratamento", "periodo", "tempo_segundos",
    "censurado", "status_testes", "casos_aprovados", "concluido_no_limite",
    "situacao", "motivo",
]
CAMPOS_PAR = [
    "integrante", "familia", "kata_com_ia", "kata_sem_ia", "com_ia", "sem_ia",
]


def consolidado_mais_recente():
    candidatos = list(CONSOLIDACOES.glob("*/trials_consolidados.csv"))
    if not candidatos:
        raise FileNotFoundError(f"Nenhum trials_consolidados.csv em {CONSOLIDACOES}")
    return max(candidatos, key=lambda p: (p.stat().st_mtime_ns, str(p)))


def ler_consolidado(caminho):
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        faltantes = CAMPOS_OBRIGATORIOS - set(leitor.fieldnames or [])
        if faltantes:
            raise ValueError(f"Consolidado sem colunas: {', '.join(sorted(faltantes))}")
        linhas = list(leitor)
    chaves = set()
    for numero, linha in enumerate(linhas, start=2):
        chave = tuple(linha[c].strip() for c in ("integrante", "kata", "tratamento"))
        if not chave[0] or chave[1] not in FAMILIAS or chave[2] not in TRATAMENTOS:
            raise ValueError(f"Linha {numero}: chave de trial inválida: {chave}")
        if chave in chaves:
            raise ValueError(f"Linha {numero}: chave de trial duplicada: {chave}")
        chaves.add(chave)
    return linhas


def classificar(linha):
    """Retorna (0/1, motivo); None indica desfecho não verificável."""
    def valor(campo):
        return (linha.get(campo) or "").strip()

    if not all(valor(c) for c in CAMPOS_OBRIGATORIOS - {"integrante", "kata", "tratamento"}):
        return None, "tempo ou avaliação ausente"
    if valor("avaliacao_concluido") not in ("True", "False"):
        return None, "avaliacao_concluido inválido"
    if valor("tempo_censurado") not in ("True", "False"):
        return None, "tempo_censurado inválido"
    try:
        tempo = float(valor("tempo_tempo_segundos"))
        aprovados = int(valor("avaliacao_casos_aprovados"))
        total = int(valor("avaliacao_total_casos"))
    except ValueError:
        return None, "tempo ou contagem de casos inválida"
    if not isfinite(tempo) or not 0 <= tempo <= LIMITE_SEGUNDOS:
        return None, "tempo fora do intervalo de 0 a 2100 segundos"
    if total != 26 or not 0 <= aprovados <= 26:
        return None, "contagem da suíte diferente de 26 casos"
    censurado = valor("tempo_censurado") == "True"
    if censurado != (tempo == LIMITE_SEGUNDOS):
        return None, "censura incompatível com o limite de 35 minutos"
    status = valor("avaliacao_status_testes")
    if status not in {"APROVADO", "REPROVADO", "ERRO_CARGA", "TIMEOUT", "ERRO_EXECUTOR"}:
        return None, "status da suíte inválido"
    if (status == "APROVADO") != (aprovados == 26):
        return None, "status e quantidade de casos aprovados divergem"
    aprovado = status == "APROVADO"
    concluiu = valor("avaliacao_concluido") == "True"
    if concluiu and (not aprovado or censurado):
        return None, "conclusão incompatível com suíte, tempo ou censura"
    if not concluiu and aprovado and not censurado:
        return None, "suíte aprovada antes do limite, mas conclusão marcada False"
    return int(concluiu), ""


def mcnemar_exato(pares):
    favor_ia = sum(p["com_ia"] == 1 and p["sem_ia"] == 0 for p in pares)
    favor_sem_ia = sum(p["com_ia"] == 0 and p["sem_ia"] == 1 for p in pares)
    discordantes = favor_ia + favor_sem_ia
    # H0: a direção de cada discordância tem probabilidade 1/2.
    p_unilateral = (
        sum(comb(discordantes, k) for k in range(favor_ia, discordantes + 1))
        / 2 ** discordantes if discordantes else None
    )
    return favor_ia, favor_sem_ia, discordantes, p_unilateral


def salvar_csv(caminho, campos, linhas):
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(linhas)


def grafico_svg(resumos, caminho):
    partes = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="760" height="430" viewBox="0 0 760 430" role="img" aria-labelledby="titulo descricao">',
        '<title id="titulo">H2: conclusão dentro de 35 minutos por tratamento</title>',
        '<desc id="descricao">Proporção de trials avaliáveis com 26 casos aprovados no prazo.</desc>',
        '<rect width="760" height="430" fill="white"/>',
        '<text x="45" y="40" font-family="sans-serif" font-size="22" font-weight="bold">H2 — conclusão em 35 minutos</text>',
        '<text x="45" y="67" font-family="sans-serif" font-size="14" fill="#555">26/26 casos aprovados no prazo</text>',
    ]
    if not any(r["n_validos"] for r in resumos):
        partes.append('<text x="45" y="205" font-family="sans-serif" font-size="20" fill="#555">Sem trials avaliáveis no consolidado.</text>')
    else:
        for marca in range(0, 101, 25):
            y = 335 - 2.25 * marca
            partes.append(f'<line x1="200" y1="{y}" x2="650" y2="{y}" stroke="#ddd"/>')
            partes.append(f'<text x="163" y="{y + 5}" font-family="sans-serif" font-size="12" fill="#555">{marca}%</text>')
        for i, resumo in enumerate(resumos):
            x = 270 + i * 230
            n = resumo["n_validos"]
            taxa = resumo["proporcao"] if n else 0
            altura = 225 * taxa
            cor = "#2563a6" if i == 0 else "#b76b2a"
            partes.append(f'<rect x="{x}" y="{335 - altura:.1f}" width="100" height="{altura:.1f}" fill="{cor}"/>')
            rotulo = f'{resumo["concluidos"]}/{n} ({taxa:.1%})' if n else "sem dados"
            partes.append(f'<text x="{x + 50}" y="{320 - altura:.1f}" text-anchor="middle" font-family="sans-serif" font-size="14">{escape(rotulo)}</text>')
            partes.append(f'<text x="{x + 50}" y="360" text-anchor="middle" font-family="sans-serif" font-size="14">{resumo["tratamento"]}</text>')
    partes.append('<text x="45" y="405" font-family="sans-serif" font-size="12" fill="#555">Unidade descritiva: trial; pares de McNemar por integrante e família de kata.</text>')
    partes.append('</svg>')
    caminho.write_text("\n".join(partes) + "\n", encoding="utf-8")


def analisar(linhas, saida):
    grupos = defaultdict(dict)
    trials = []
    for linha in linhas:
        integrante, kata, tratamento = (linha[c].strip() for c in ("integrante", "kata", "tratamento"))
        familia = FAMILIAS[kata]
        chave = (integrante, familia)
        if tratamento in grupos[chave]:
            raise ValueError(f"{integrante}/{familia}: mais de um trial {tratamento}")
        concluido, motivo = classificar(linha)
        registro = {
            "integrante": integrante, "kata": kata, "familia": familia,
            "tratamento": tratamento,
            "periodo": (linha.get("avaliacao_periodo") or "").strip(),
            "tempo_segundos": (linha.get("tempo_tempo_segundos") or "").strip(),
            "censurado": (linha.get("tempo_censurado") or "").strip(),
            "status_testes": (linha.get("avaliacao_status_testes") or "").strip(),
            "casos_aprovados": (linha.get("avaliacao_casos_aprovados") or "").strip(),
            "concluido_no_limite": "" if concluido is None else concluido,
            "situacao": "valido" if concluido is not None else "nao_avaliavel",
            "motivo": motivo,
        }
        grupos[chave][tratamento] = registro
        trials.append(registro)

    resumos = []
    for tratamento in TRATAMENTOS:
        itens = [r for r in trials if r["tratamento"] == tratamento]
        validos = [r for r in itens if r["situacao"] == "valido"]
        concluidos = sum(r["concluido_no_limite"] == 1 for r in validos)
        resumos.append({
            "tratamento": tratamento, "n_registrados": len(itens),
            "n_validos": len(validos), "n_nao_avaliaveis": len(itens) - len(validos),
            "concluidos": concluidos, "nao_concluidos": len(validos) - concluidos,
            "proporcao": concluidos / len(validos) if validos else "",
        })

    pares = []
    incompletos = 0
    for (integrante, familia), registros in sorted(grupos.items()):
        if any(t not in registros or registros[t]["situacao"] != "valido" for t in TRATAMENTOS):
            incompletos += 1
            continue
        com, sem = (registros[t] for t in TRATAMENTOS)
        pares.append({
            "integrante": integrante, "familia": familia,
            "kata_com_ia": com["kata"], "kata_sem_ia": sem["kata"],
            "com_ia": com["concluido_no_limite"], "sem_ia": sem["concluido_no_limite"],
        })
    b, c, discordantes, p_valor = mcnemar_exato(pares)
    tabela = Counter((p["com_ia"], p["sem_ia"]) for p in pares)
    teste = {
        "n_pares": len(pares), "n_integrantes": len({p["integrante"] for p in pares}),
        "pares_incompletos": incompletos,
        "ambos_concluiram": tabela[1, 1], "so_com_ia": b,
        "so_sem_ia": c, "nenhum_concluiu": tabela[0, 0],
        "discordantes": discordantes,
        "p_exato_unilateral_com_ia_maior": "" if p_valor is None else p_valor,
        "interpretacao": (
            "Sem pares discordantes; teste não informativo" if not discordantes else
            "Exploratório: dois pares por integrante não são independentes"
        ),
    }
    saida.mkdir(parents=True, exist_ok=True)
    salvar_csv(saida / "h2_trials.csv", CAMPOS_TRIAL, trials)
    salvar_csv(saida / "h2_resumo_tratamentos.csv", list(resumos[0]), resumos)
    salvar_csv(saida / "h2_pares.csv", CAMPOS_PAR, pares)
    salvar_csv(saida / "h2_mcnemar.csv", list(teste), [teste])
    grafico_svg(resumos, saida / "h2_proporcao_conclusao.svg")
    return resumos, teste


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--consolidado", type=Path, help="CSV consolidado; padrão: o mais recente por data de modificação")
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO, help="Pasta dos CSVs e do gráfico")
    args = parser.parse_args()
    try:
        caminho = args.consolidado or consolidado_mais_recente()
        resumos, teste = analisar(ler_consolidado(caminho), args.saida)
    except (OSError, ValueError) as erro:
        parser.error(str(erro))
    print(f"Consolidado: {caminho}")
    for r in resumos:
        print(f'{r["tratamento"]}: {r["concluidos"]}/{r["n_validos"]} trials válidos concluídos; {r["n_nao_avaliaveis"]} não avaliáveis')
    p = teste["p_exato_unilateral_com_ia_maior"]
    print(f'McNemar: {teste["n_pares"]} pares, {teste["discordantes"]} discordantes, p unilateral = {p if p != "" else "não calculável"}')
    print(f"Arquivos salvos em {args.saida}")


if __name__ == "__main__":
    main()
