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


def tabelas_com_variantes():
    t = tabelas()
    t['entrega']['dono/repo'].update(semanas_janela='52', tags_status='ok', tags_janela='26')
    t['ci']['dono/repo'].update(episodios_resolvidos='3', episodios_censurados='1')
    t['cfr_b']['dono/repo'].update(falhas='2', denominador='8', censuradas='1', inconclusivas='3')
    return t


def test_variantes_de_deploy_e_censura():
    linha = consolidar(tabelas_com_variantes(), releases_com_prerelease={'dono/repo': 13})[0][0]
    assert linha['frequencia_releases_prerelease_semana'] == 0.25    # 13 / 52
    assert linha['frequencia_tags_semana'] == 0.5                    # 26 / 52
    assert linha['episodios_censurados'] == 1 and linha['episodios_resolvidos'] == 3
    assert linha['proporcao_episodios_censurados'] == 0.25
    assert (linha['cfr_b_falhas'], linha['cfr_b_denominador'], linha['cfr_b_censuradas'],
            linha['cfr_b_inconclusivas']) == (2, 8, 1, 3)


def test_variantes_ausentes_nao_viram_zero():
    t = tabelas_com_variantes()
    t['entrega']['dono/repo']['tags_status'] = 'nao_coletado'
    t['ci']['dono/repo']['coleta_completa'] = 'False'
    t['cfr_b']['dono/repo']['coleta_status'] = 'erro'
    linha = consolidar(t)[0][0]  # sem releases.csv: variante com pré-release indisponível
    assert linha['frequencia_releases_prerelease_semana'] is None
    assert linha['tags_status'] == 'nao_coletado' and linha['frequencia_tags_semana'] is None
    assert linha['episodios_censurados'] is None and linha['proporcao_episodios_censurados'] is None
    assert linha['cfr_b_censuradas'] is None


def test_sem_episodios_proporcao_censurada_e_ausente():
    t = tabelas_com_variantes()
    t['ci']['dono/repo'].update(episodios_resolvidos='0', episodios_censurados='0')
    assert consolidar(t)[0][0]['proporcao_episodios_censurados'] is None


def test_contagem_de_releases_com_prerelease(tmp_path):
    from pipeline.consolidar import contar_releases_com_prerelease
    linhas = [
        'full_name,tag_name,na_janela,draft,prerelease',
        'o/r,v1,True,False,False',
        'o/r,v2-rc,True,False,True',      # pré-release entra
        'o/r,rascunho,True,True,False',   # draft não entra
        'o/r,v0,False,False,False',       # fora da janela não entra
        'o/s,v1,True,False,True',
    ]
    arquivo = tmp_path / 'releases.csv'
    arquivo.write_text(chr(10).join(linhas) + chr(10), encoding='utf-8')
    assert contar_releases_com_prerelease(arquivo) == {'o/r': 2, 'o/s': 1}
