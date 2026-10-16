"""Testes de consolidação da Pessoa C na Sprint 02."""
import csv
import json

import pytest

from pipeline.consolidar import booleano, consolidar, executar, ler_tabela, numero


def tabelas():
    return {
        'repositorios': {'dono/repo': {'full_name': 'dono/repo', 'default_branch': 'main',
            'releases_janela': '6', 'runs_validos_janela': '75', 'estrelas': '1500'}},
        'entrega': {'dono/repo': {'full_name': 'dono/repo', 'releases_status': 'ok',
            'frequencia_releases_semana': '1.5', 'lead_time_a_horas': '5',
            'lead_time_b_horas': '8'}},
        'ci': {'dono/repo': {'full_name': 'dono/repo', 'coleta_completa': 'True',
            'runs_validos': '75', 'cfr_a': '0.1', 'recuperacao_mediana_horas': '2'}},
        'cfr_b': {'dono/repo': {'full_name': 'dono/repo', 'coleta_status': 'ok', 'cfr_b': '0.25'}},
    }


def test_classifica_quatro_metricas_e_preserva_variantes():
    linhas, avisos = consolidar(tabelas())
    l = linhas[0]
    assert not avisos
    assert l['categoria_geral'] == 'High'
    assert l['classificacao_completa'] is True
    assert l['cfr_a'] == 0.1 and l['cfr_b'] == 0.25
    assert l['lead_time_a_horas'] == 5 and l['lead_time_b_horas'] == 8


def test_ausencia_de_recuperacao_nao_e_zero():
    t = tabelas()
    t['ci']['dono/repo']['recuperacao_mediana_horas'] = ''
    l = consolidar(t)[0][0]
    assert l['recuperacao_mediana_horas'] is None
    assert l['classificacao_completa'] is False
    assert l['metricas_disponiveis'] == 3


def test_coleta_incompleta_nao_produz_cfr_falso():
    t = tabelas()
    t['ci']['dono/repo']['coleta_completa'] = 'False'
    l = consolidar(t)[0][0]
    assert l['cfr_a'] is None and l['recuperacao_mediana_horas'] is None


def test_cfr_b_com_erro_nao_e_zero():
    t = tabelas()
    t['cfr_b']['dono/repo']['coleta_status'] = 'erro'
    assert consolidar(t)[0][0]['cfr_b'] is None


def test_ausencia_tabela_sinalizada():
    t = tabelas()
    t['cfr_b'] = {}
    linhas, avisos = consolidar(t)
    assert linhas[0]['cfr_b'] is None
    assert avisos


def test_nao_permite_repo_extra():
    t = tabelas()
    t['ci']['extra/repo'] = dict(t['ci']['dono/repo'])
    with pytest.raises(ValueError, match='sem repositório'):
        consolidar(t)


@pytest.mark.parametrize('campo,valor', [('releases_janela','4'), ('runs_validos_janela','49')])
def test_nao_inclui_repositorio_fora_do_funil(campo,valor):
    t = tabelas()
    t['repositorios']['dono/repo'][campo] = valor
    with pytest.raises(ValueError, match='não atende'):
        consolidar(t)


def test_rerun_menor_que_minimo_e_erro():
    t = tabelas()
    t['ci']['dono/repo']['runs_validos'] = '10'
    with pytest.raises(ValueError, match='contradiz'):
        consolidar(t)


@pytest.mark.parametrize('valor', ['NaN', 'inf', '-1', '1.2'])
def test_cfr_invalido(valor):
    t = tabelas()
    t['ci']['dono/repo']['cfr_a'] = valor
    with pytest.raises(ValueError):
        consolidar(t)


def test_csv_duplicado_gera_erro(tmp_path):
    p = tmp_path / 'duplicado.csv'
    p.write_text('full_name,valor\ndono/repo,1\ndono/repo,2\n', encoding='utf-8')
    with pytest.raises(ValueError, match='duplicado'):
        ler_tabela(p, {'full_name'})


def test_csv_sem_coluna_gera_erro(tmp_path):
    p = tmp_path / 'faltando.csv'
    p.write_text('valor\n1\n', encoding='utf-8')
    with pytest.raises(ValueError, match='cabeçalho'):
        ler_tabela(p, {'full_name'})


def test_booleano_false_string_e_false():
    assert booleano('False', 'coluna') is False
    with pytest.raises(ValueError):
        booleano('talvez', 'coluna')


def test_numero_inteiro_e_finito():
    assert numero('12', 'campo', inteiro=True) == 12
    with pytest.raises(ValueError):
        numero('12.5', 'campo', inteiro=True)
    with pytest.raises(ValueError):
        numero('Infinity', 'campo')


def test_saida_preserva_entradas(tmp_path):
    t = tabelas()
    nomes = {'repositorios': 'repositorios.csv', 'entrega': 'metricas_entrega.csv',
             'ci': 'metricas_ci.csv', 'cfr_b': 'metricas_cfr_b.csv'}
    originais = {}
    for chave, nome_arquivo in nomes.items():
        linhas = list(t[chave].values())
        with (tmp_path / nome_arquivo).open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(linhas[0])); w.writeheader(); w.writerows(linhas)
        originais[nome_arquivo] = (tmp_path / nome_arquivo).read_bytes()
    resumo = executar(tmp_path)
    assert resumo['repositorios'] == 1
    assert resumo['meta_atingida'] is False
    assert json.loads((tmp_path / 'resumo_consolidacao.json').read_text())['repositorios'] == 1
    with (tmp_path / 'metricas_consolidadas.csv').open(encoding='utf-8') as f:
        assert list(csv.DictReader(f))[0]['full_name'] == 'dono/repo'
    for arq, dados in originais.items():
        assert (tmp_path / arq).read_bytes() == dados
