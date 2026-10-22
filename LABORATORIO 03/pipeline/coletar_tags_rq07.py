"""Coleta somente tags para RQ07 sem reexecutar o pipeline completo.

Uso: python -m pipeline.coletar_tags_rq07 --config config.yaml
Lê dados/repositorios.csv; guarda checkpoints por repositório; escreve tags.csv e
status_tags_rq07.csv de forma atômica; preserva releases/commits/metricas_entrega.
"""
import argparse
import csv
import json
import logging
import os
from pathlib import Path
import re

import yaml

from pipeline.api_client import ClienteGitHub
from pipeline.releases import COLUNAS_TAGS, coletar_tags

LOG = logging.getLogger(__name__)
COLUNAS_STATUS = ('full_name', 'tags_status', 'quantidade_tags', 'na_janela')


def _arquivo_seguro(nome):
    # Cada repo tem owner/repo único: evita colisões e paths escapando do cache.
    from hashlib import sha256
    return sha256(nome.encode('utf-8')).hexdigest() + '.json'


def _csv_atomico(caminho, linhas, colunas):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temp = caminho.with_name(caminho.name + '.tmp')
    with temp.open('w', newline='', encoding='utf-8') as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=colunas, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(linhas)
    temp.replace(caminho)


def _repositorios(caminho):
    with Path(caminho).open(newline='', encoding='utf-8-sig') as arquivo:
        rows = list(csv.DictReader(arquivo))
    if not rows or any(not row.get('full_name') for row in rows):
        raise ValueError('repositorios.csv vazio ou sem full_name')
    nomes = [row['full_name'] for row in rows]
    if len(set(nomes)) != len(nomes):
        raise ValueError('repositorios.csv contém repositórios duplicados')
    return nomes


def _checkpoint_ler(arquivo, inicio, fim):
    if not arquivo.exists():
        return None
    try:
        data = json.loads(arquivo.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if (data.get('inicio'), data.get('fim')) != (str(inicio), str(fim)):
        return None
    if not isinstance(data.get('tags'), list):
        return None
    return data


def coletar_apenas_tags(cliente, repositorios, inicio, fim, checkpoint_dir, saida):
    checkpoint_dir = Path(checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    linhas_tags, linhas_status = [], []
    for indice, repo in enumerate(repositorios, 1):
        checkpoint = checkpoint_dir / _arquivo_seguro(repo)
        dados = _checkpoint_ler(checkpoint, inicio, fim)
        if dados is not None and dados.get('full_name') != repo:
            dados = None
        if dados is None or dados.get('status') != 'ok':
            try:
                tags, status = coletar_tags(cliente, repo, inicio, fim)
            except (OSError, ValueError, RuntimeError) as erro:
                LOG.warning('[%s/%s] %s: falha: %s', indice, len(repositorios), repo, erro)
                tags, status = [], 'erro_coleta'
            dados = {'full_name': repo, 'inicio': str(inicio), 'fim': str(fim),
                     'tags': tags, 'status': status}
            tmp = checkpoint.with_suffix('.tmp')
            tmp.write_text(json.dumps(dados, ensure_ascii=False), encoding='utf-8')
            tmp.replace(checkpoint)
        linhas_tags.extend(dados['tags'])
        linhas_status.append({'full_name': repo, 'tags_status': dados['status'],
                              'quantidade_tags': len(dados['tags']),
                              'na_janela': sum(str(t.get('na_janela')).lower() == 'true' for t in dados['tags'])})
        LOG.info('[%d/%d] %s: %s, %d tags', indice, len(repositorios), repo,
                 dados['status'], len(dados['tags']))
    saida = Path(saida)
    _csv_atomico(saida / 'tags.csv', linhas_tags, COLUNAS_TAGS)
    _csv_atomico(saida / 'status_tags_rq07.csv', linhas_status, COLUNAS_STATUS)
    return linhas_status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='config.yaml')
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    config_path = Path(args.config).resolve()
    cfg = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    saida = config_path.parent / cfg['saida']['dir']
    token = os.environ.get(cfg['github'].get('token_env', 'GITHUB_TOKEN'))
    if not token:
        parser.error('Configure GITHUB_TOKEN no PowerShell antes da coleta')
    repos = _repositorios(saida / 'repositorios.csv')
    cliente = ClienteGitHub(token, config_path.parent / cfg['saida']['cache_dir'])
    checkpoints = saida / 'checkpoints_tags_rq07'
    estados = coletar_apenas_tags(cliente, repos, cfg['janela']['inicio'],
                                  cfg['janela']['fim'], checkpoints, saida)
    ok = sum(e['tags_status'] == 'ok' for e in estados)
    print(f'Tags coletadas: {ok}/{len(repos)} repositórios com status ok; saídas em {saida}')
    if ok != len(repos):
        print('ATENÇÃO: coleta parcial, rode novamente para tentar os repositórios com falha.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
