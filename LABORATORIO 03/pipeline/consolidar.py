"""Sprint 02 (Pessoa C): consolidação offline, auditável, das métricas DORA.

Uso: python -m pipeline.consolidar --config config.yaml
Não altera os CSVs de entrada e não consulta a API GitHub.
"""
import argparse
import csv
from datetime import date
import json
import math
from pathlib import Path

import yaml

from metricas.dora import classificar_repositorio

FONTES = {
    'repositorios': ('repositorios.csv', {'full_name', 'default_branch', 'releases_janela', 'runs_validos_janela'}),
    'entrega': ('metricas_entrega.csv', {'full_name', 'releases_status', 'frequencia_releases_semana', 'lead_time_a_horas', 'lead_time_b_horas'}),
    'ci': ('metricas_ci.csv', {'full_name', 'coleta_completa', 'runs_validos', 'cfr_a', 'recuperacao_mediana_horas'}),
    'cfr_b': ('metricas_cfr_b.csv', {'full_name', 'coleta_status', 'cfr_b'}),
}
COLUNAS = [
    'full_name', 'default_branch', 'estrelas', 'linguagem', 'idade_anos', 'contribuidores',
    'releases_janela', 'runs_validos_janela', 'releases_status', 'coleta_ci_completa',
    'coleta_cfr_b_status', 'frequencia_releases_semana', 'lead_time_a_horas', 'lead_time_b_horas',
    'cfr_a', 'cfr_b', 'recuperacao_mediana_horas',
    # Variantes de unidade de deploy (RQ 07) e casos censurados.
    'frequencia_releases_prerelease_semana', 'tags_status', 'frequencia_tags_semana',
    'episodios_resolvidos', 'episodios_censurados', 'proporcao_episodios_censurados',
    'cfr_b_falhas', 'cfr_b_denominador', 'cfr_b_censuradas', 'cfr_b_inconclusivas',
    'categoria_frequencia',
    'categoria_lead_time', 'categoria_cfr', 'categoria_recuperacao', 'categoria_geral',
    'metricas_disponiveis', 'classificacao_completa',
]


def ler_tabela(arquivo, obrigatorias):
    """Lê CSV validando chave única, cabeçalho e integridade das linhas."""
    with Path(arquivo).open(encoding='utf-8-sig', newline='') as fluxo:
        leitor = csv.DictReader(fluxo, strict=True)
        campos = leitor.fieldnames or []
        if len(campos) != len(set(campos)) or not obrigatorias <= set(campos):
            raise ValueError(f'{arquivo}: cabeçalho inválido/colunas faltantes: {sorted(obrigatorias - set(campos))}')
        resultado = {}
        for linha in leitor:
            if None in linha or any(v is None for v in linha.values()):
                raise ValueError(f'{arquivo}: linha CSV incompleta ({leitor.line_num})')
            nome = linha['full_name'].strip()
            if not nome or nome in resultado:
                raise ValueError(f'{arquivo}: full_name vazio ou duplicado: {nome!r}')
            resultado[nome] = linha
        return resultado


def numero(valor, campo, *, inteiro=False, minimo=0, maximo=None):
    if valor is None or str(valor).strip() == '':
        return None
    try:
        n = float(valor)
    except (ValueError, TypeError) as erro:
        raise ValueError(f'{campo}: valor numérico inválido {valor!r}') from erro
    if not math.isfinite(n) or n < minimo or (maximo is not None and n > maximo):
        raise ValueError(f'{campo}: valor fora dos limites: {valor!r}')
    if inteiro and not n.is_integer():
        raise ValueError(f'{campo}: esperado inteiro: {valor!r}')
    return int(n) if inteiro else n


def booleano(valor, campo):
    if isinstance(valor, bool):
        return valor
    v = str(valor).strip().lower()
    if v in ('true', '1'):
        return True
    if v in ('false', '0'):
        return False
    raise ValueError(f'{campo}: booleano inválido: {valor!r}')


def contar_releases_com_prerelease(arquivo):
    """Releases publicadas na janela por repositório, incluindo pré-releases (sem drafts)."""
    contagem = {}
    with Path(arquivo).open(encoding='utf-8-sig', newline='') as fluxo:
        for linha in csv.DictReader(fluxo):
            if booleano(linha['na_janela'], 'na_janela') and not booleano(linha['draft'], 'draft'):
                contagem[linha['full_name']] = contagem.get(linha['full_name'], 0) + 1
    return contagem


def _contagem(linha, coluna, valida):
    return numero(linha.get(coluna), coluna, inteiro=True) if valida else None


def _por_semana(quantidade, semanas):
    return None if quantidade is None or not semanas else quantidade / semanas


def consolidar(tabelas, *, min_releases=5, min_runs=50, releases_com_prerelease=None):
    """Usa os repositórios aprovados como fonte canônica e valida joins 1:1.

    ``releases_com_prerelease`` (de ``releases.csv``) habilita a variante de
    frequência com pré-releases; sem ela, a coluna fica ausente, nunca zero.
    """
    nomes = set(tabelas['repositorios'])
    for fonte in ('entrega', 'ci', 'cfr_b'):
        extras = set(tabelas[fonte]) - nomes
        if extras:
            raise ValueError(f'{fonte}: registros sem repositório aprovado: {sorted(extras)[:5]}')
    resultado = []
    avisos = []
    for nome in sorted(nomes):
        repo = tabelas['repositorios'][nome]
        entrega = tabelas['entrega'].get(nome)
        ci = tabelas['ci'].get(nome)
        cfr = tabelas['cfr_b'].get(nome)
        for fonte, linha in [('entrega', entrega), ('ci', ci), ('cfr_b', cfr)]:
            if linha is None:
                avisos.append(f'{nome}: faltam dados de {fonte}')
        nr = numero(repo['releases_janela'], 'releases_janela', inteiro=True)
        nc = numero(repo['runs_validos_janela'], 'runs_validos_janela', inteiro=True)
        if nr is None or nc is None or nr < min_releases or nc < min_runs:
            raise ValueError(f'{nome}: não atende ao funil mínimo de {min_releases} releases e {min_runs} runs')
        entrega_ok = entrega is not None and entrega['releases_status'] == 'ok'
        ci_ok = ci is not None and booleano(ci['coleta_completa'], 'coleta_completa')
        cfr_b_ok = cfr is not None and cfr['coleta_status'] == 'ok'
        if ci_ok:
            run_cont = numero(ci['runs_validos'], 'runs_validos', inteiro=True)
            if run_cont is None or run_cont < min_runs:
                raise ValueError(f'{nome}: coleta detalhada de CI contradiz filtro de runs ({run_cont})')
        freq = numero(entrega['frequencia_releases_semana'], 'frequencia', minimo=0) if entrega_ok else None
        lead_a = numero(entrega['lead_time_a_horas'], 'lead_time_a_horas') if entrega_ok else None
        lead_b = numero(entrega['lead_time_b_horas'], 'lead_time_b_horas') if entrega_ok else None
        cfr_a = numero(ci['cfr_a'], 'cfr_a', maximo=1) if ci_ok else None
        rec = numero(ci['recuperacao_mediana_horas'], 'recuperacao_mediana_horas') if ci_ok else None
        cfr_b_val = numero(cfr['cfr_b'], 'cfr_b', maximo=1) if cfr_b_ok else None
        semanas = numero(entrega.get('semanas_janela'), 'semanas_janela') if entrega_ok else None
        freq_pre = None
        if entrega_ok and releases_com_prerelease is not None:
            freq_pre = _por_semana(releases_com_prerelease.get(nome, 0), semanas)
        tags_status = (entrega.get('tags_status') or 'ausente') if entrega else 'ausente'
        freq_tags = None
        if tags_status == 'ok':
            freq_tags = _por_semana(numero(entrega.get('tags_janela'), 'tags_janela', inteiro=True),
                                    semanas)
        resolvidos = numero(ci.get('episodios_resolvidos'), 'episodios_resolvidos', inteiro=True) if ci_ok else None
        censurados = numero(ci.get('episodios_censurados'), 'episodios_censurados', inteiro=True) if ci_ok else None
        episodios = (resolvidos or 0) + (censurados or 0)
        prop_censurados = censurados / episodios if censurados is not None and episodios else None
        categorias = classificar_repositorio(freq, lead_a, cfr_a, rec)
        quantidade = sum(x is not None for x in (freq, lead_a, cfr_a, rec))
        resultado.append({
            'full_name': nome, 'default_branch': repo['default_branch'],
            'estrelas': repo.get('estrelas', ''), 'linguagem': repo.get('linguagem', ''),
            'idade_anos': repo.get('idade_anos', ''), 'contribuidores': repo.get('contribuidores', ''),
            'releases_janela': nr, 'runs_validos_janela': nc,
            'releases_status': entrega['releases_status'] if entrega else 'ausente',
            'coleta_ci_completa': ci_ok, 'coleta_cfr_b_status': cfr['coleta_status'] if cfr else 'ausente',
            'frequencia_releases_semana': freq, 'lead_time_a_horas': lead_a,
            'lead_time_b_horas': lead_b, 'cfr_a': cfr_a, 'cfr_b': cfr_b_val,
            'recuperacao_mediana_horas': rec,
            'frequencia_releases_prerelease_semana': freq_pre,
            'tags_status': tags_status, 'frequencia_tags_semana': freq_tags,
            'episodios_resolvidos': resolvidos, 'episodios_censurados': censurados,
            'proporcao_episodios_censurados': prop_censurados,
            'cfr_b_falhas': _contagem(cfr, 'falhas', cfr_b_ok), 'cfr_b_denominador': _contagem(cfr, 'denominador', cfr_b_ok),
            'cfr_b_censuradas': _contagem(cfr, 'censuradas', cfr_b_ok),
            'cfr_b_inconclusivas': _contagem(cfr, 'inconclusivas', cfr_b_ok),
            'categoria_frequencia': categorias['frequencia'],
            'categoria_lead_time': categorias['lead_time'],
            'categoria_cfr': categorias['cfr'],
            'categoria_recuperacao': categorias['recuperacao'],
            'categoria_geral': categorias['geral'],
            'metricas_disponiveis': quantidade, 'classificacao_completa': quantidade == 4,
        })
    return resultado, avisos


def executar(diretorio, *, min_releases=5, min_runs=50, minimo_amostra=300):
    diretorio = Path(diretorio)
    tabelas = {chave: ler_tabela(diretorio / arquivo, campos)
               for chave, (arquivo, campos) in FONTES.items()}
    caminho_releases = diretorio / 'releases.csv'
    com_prerelease = (contar_releases_com_prerelease(caminho_releases)
                      if caminho_releases.exists() else None)
    linhas, avisos = consolidar(tabelas, min_releases=min_releases, min_runs=min_runs,
                                releases_com_prerelease=com_prerelease)
    destino = diretorio / 'metricas_consolidadas.csv'
    temporario = destino.with_suffix('.csv.tmp')
    with temporario.open('w', encoding='utf-8', newline='') as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
        escritor.writeheader()
        escritor.writerows(linhas)
    temporario.replace(destino)
    total = len(linhas)
    resumo = {'repositorios': total, 'meta_sprint2': minimo_amostra,
              'meta_atingida': total >= minimo_amostra,
              'classificacao_completa': sum(l['classificacao_completa'] for l in linhas),
              'sem_tempo_recuperacao': sum(l['recuperacao_mediana_horas'] is None for l in linhas),
              'episodios_censurados': sum(l['episodios_censurados'] or 0 for l in linhas),
              'episodios_resolvidos': sum(l['episodios_resolvidos'] or 0 for l in linhas),
              'releases_censuradas_cfr_b': sum(l['cfr_b_censuradas'] or 0 for l in linhas),
              'categorias_gerais': {c: sum(l['categoria_geral'] == c for l in linhas)
                                    for c in ('Elite', 'High', 'Medium', 'Low')},
              'avisos': avisos}
    (diretorio / 'resumo_consolidacao.json').write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return resumo


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('config.yaml'))
    parser.add_argument('--saida', type=Path, help='Diretório dos CSVs; padrão: config.saida.dir')
    parser.add_argument('--exigir-300', action='store_true', help='Retorna erro se a amostra estiver abaixo da meta')
    args = parser.parse_args(argv)
    config = yaml.safe_load(args.config.read_text(encoding='utf-8'))
    pasta = args.saida or args.config.resolve().parent / config['saida']['dir']
    resumo = executar(pasta, min_releases=config['filtros']['releases'],
                      min_runs=config['filtros']['runs'])
    print(f"Consolidados {resumo['repositorios']} repositórios; "
          f"{resumo['classificacao_completa']} com 4 métricas disponíveis. Saída: {pasta}")
    if not resumo['meta_atingida']:
        print('PENDENTE: a Sprint 02 exige pelo menos 300 repositórios reais.')
        if args.exigir_300:
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
