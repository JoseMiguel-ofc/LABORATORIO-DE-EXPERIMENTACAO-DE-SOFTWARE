"""Leitura offline dos CSVs de entrega, inclusive commits.csv.gz.

Mensagens são examinadas uma por vez; somente contagens e evidência da
heurística ficam na memória. SHAs são deduplicados em um SQLite temporário
em disco, que também identifica mensagens conflitantes para o mesmo commit.
"""

from contextlib import closing
import csv
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
from pathlib import Path
import sqlite3
import tempfile

from metricas.cfr import palavras_corretivas


VERSOES = ("v1", "v2")


def booleano(valor, *, campo="booleano", vazio=None):
    """Converte valores CSV explicitamente: a string 'False' não é verdadeira."""
    if valor is None or str(valor).strip() == "":
        return vazio
    if isinstance(valor, bool):
        return valor
    texto = str(valor).strip().lower()
    if texto in {"true", "1", "sim"}:
        return True
    if texto in {"false", "0", "nao", "não"}:
        return False
    raise ValueError(f"{campo}: booleano inválido {valor!r}")


def _quantidade(valor):
    if valor is None or str(valor).strip() == "":
        return None
    try:
        numero = Decimal(str(valor))
        if not numero.is_finite() or numero < 0 or numero != numero.to_integral_value():
            raise ValueError
        return int(numero)
    except (InvalidOperation, ValueError):
        raise ValueError(f"commits_novos inválido: {valor!r}") from None


def linhas_csv(caminho, obrigatorias):
    """Produz linhas sem carregar o arquivo (CSV padrão, UTF-8 e gzip)."""
    caminho = Path(caminho)
    abrir = gzip.open if caminho.suffix.lower() == ".gz" else open
    limite = csv.field_size_limit()
    csv.field_size_limit(max(limite, 64 * 1024 * 1024))
    try:
        with abrir(caminho, "rt", encoding="utf-8-sig", newline="") as arquivo:
            leitor = csv.DictReader(arquivo, strict=True)
            faltam = set(obrigatorias) - set(leitor.fieldnames or [])
            if faltam:
                raise ValueError(f"{caminho}: colunas ausentes: {', '.join(sorted(faltam))}")
            if len(leitor.fieldnames) != len(set(leitor.fieldnames)):
                raise ValueError(f"{caminho}: cabeçalho com colunas duplicadas")
            for linha in leitor:
                if None in linha or any(valor is None for valor in linha.values()):
                    raise ValueError(f"{caminho}, linha {leitor.line_num}: CSV incompleto")
                yield linha
    finally:
        csv.field_size_limit(limite)


def carregar_releases(caminho_releases, caminho_commits=None):
    """Retorna releases com evidência compacta e diagnóstico da comparação.

    Qualquer contagem divergente, mensagem ausente ou SHA conflitante torna
    a evidência de commits inconclusiva. Os demais campos preservam os dados
    necessários para verificar a sequência de tags e o intervalo temporal.
    """
    por_chave = {}
    obrigatorias = {"full_name", "tag_name", "published_at", "draft", "prerelease",
                    "commits_status", "commits_novos"}
    for original in linhas_csv(caminho_releases, obrigatorias):
        chave = (original["full_name"], original["tag_name"])
        if not all(chave):
            raise ValueError("Release sem full_name/tag_name")
        if chave in por_chave:
            if original != por_chave[chave]["original"]:
                raise ValueError(f"Release duplicada com dados conflitantes: {chave}")
            continue
        release = dict(original)
        for campo in ("draft", "prerelease", "na_janela"):
            if campo in release:
                release[campo] = booleano(release[campo], campo=campo)
                if campo != "na_janela" and release[campo] is None:
                    raise ValueError(f"{campo} ausente em {chave}")
        release["commits_novos"] = _quantidade(release["commits_novos"])
        por_chave[chave] = {"original": original, "release": release, "total": 0,
                           "incompletos": 0, "duplicados": 0, "conflitos": 0,
                           "comparacoes_divergentes": 0,
                           "evidencia": {versao: False for versao in VERSOES}}

    if caminho_commits is not None:
        with tempfile.TemporaryDirectory(prefix="lab03-commits-") as temporario:
            # closing(): fecha o arquivo antes de apagar a pasta (no Windows, aberto não apaga).
            with closing(sqlite3.connect(str(Path(temporario) / "vistos.sqlite"))) as banco:
                banco.execute("PRAGMA journal_mode=OFF")
                banco.execute("PRAGMA synchronous=OFF")
                banco.execute("CREATE TABLE vistos (repo TEXT, tag TEXT, sha TEXT, digest TEXT, "
                              "PRIMARY KEY (repo, tag, sha)) WITHOUT ROWID")
                for linha in linhas_csv(caminho_commits, {"full_name", "tag_name", "sha", "message"}):
                    chave = (linha["full_name"], linha["tag_name"])
                    if chave not in por_chave:
                        raise ValueError(f"Commit sem release correspondente: {chave}")
                    estado = por_chave[chave]
                    for campo in ("release_id", "tag_anterior"):
                        esperado = estado["release"].get(campo)
                        if esperado and campo in linha and linha[campo] != esperado:
                            estado["comparacoes_divergentes"] += 1
                    sha, mensagem = linha["sha"].strip(), linha["message"]
                    if not sha:
                        estado["incompletos"] += 1
                        continue
                    digest = hashlib.sha256(mensagem.encode("utf-8")).hexdigest()
                    anterior = banco.execute("SELECT digest FROM vistos WHERE repo=? AND tag=? AND sha=?",
                                             (*chave, sha)).fetchone()
                    if anterior:
                        estado["duplicados"] += 1
                        if anterior[0] != digest:
                            estado["conflitos"] += 1
                        continue
                    banco.execute("INSERT INTO vistos VALUES (?, ?, ?, ?)", (*chave, sha, digest))
                    estado["total"] += 1
                    if not mensagem.strip():
                        estado["incompletos"] += 1
                    for versao in VERSOES:
                        estado["evidencia"][versao] |= palavras_corretivas(mensagem, versao=versao)

    resultado = []
    for estado in por_chave.values():
        release = estado["release"]
        esperado, total = release["commits_novos"], estado["total"]
        problemas = []
        if release["commits_status"] not in {"ok", "sem_commits"}:
            problemas.append("compare_indisponivel")
        if release["commits_status"] == "sem_commits" and (esperado != 0 or total != 0):
            problemas.append("status_quantidade_divergente")
        if esperado is None:
            problemas.append("quantidade_esperada_ausente")
        elif esperado != total:
            problemas.append("quantidade_divergente")
        if caminho_commits is None and esperado != 0:
            problemas.append("arquivo_commits_ausente")
        if estado["incompletos"]:
            problemas.append("mensagem_ou_sha_ausente")
        if estado["conflitos"]:
            problemas.append("sha_conflitante")
        if estado["comparacoes_divergentes"]:
            problemas.append("comparacao_divergente")
        release.update(commits_coletados=total, commits_duplicados=estado["duplicados"],
                       commits_conflitantes=estado["conflitos"],
                       commits_integridade=";".join(problemas) if problemas else "ok",
                       evidencia_commits={**{v: None if problemas else estado["evidencia"][v]
                                             for v in VERSOES}, "total": total,
                                          "incompletos": estado["incompletos"] + estado["conflitos"]})
        resultado.append(release)
    return resultado
