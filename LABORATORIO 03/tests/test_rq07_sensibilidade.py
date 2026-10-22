from analises.rq07_sensibilidade import analisar, kappa_linear, duracao_semanas


def repo(**kwargs):
    r = dict(full_name='a/b', releases_status='ok', coleta_cfr_b_status='ok',
             frequencia_releases_semana='1', lead_time_a_horas='5', lead_time_b_horas='600',
             cfr_a='0.10', cfr_b='0.60', recuperacao_mediana_horas='0.5')
    r.update(kwargs)
    return r


def test_kappa_identico_e_concordancia_parcial():
    assert kappa_linear([('Elite','Elite'), ('Low','Low')]) == 1.0
    assert kappa_linear([]) is None
    assert kappa_linear([('Elite','Low'), ('Low','Elite')]) == -1.0


def test_janela_inclusiva():
    assert duracao_semanas('2026-01-01', '2026-01-07') == 1.0


def test_c3_nao_estima_tags_ausentes():
    linhas, comps = analisar([repo()], [], [], '2026-01-01', '2026-01-07')
    assert len(linhas) == 3
    assert linhas[2]['categoria_geral'] is None
    assert comps[1]['comparaveis'] == 0
    assert comps[0]['comparaveis'] == 1


def test_falta_recuperacao_exclui_pares():
    _, comps = analisar([repo(recuperacao_mediana_horas='')], [], [], '2026-01-01', '2026-01-07')
    assert all(c['comparaveis'] == 0 for c in comps)


def test_tags_coletadas_permite_c3():
    tags = [dict(full_name='a/b', tag_name='v1', status='ok', na_janela='True')]
    linhas, comps = analisar([repo()], [], tags, '2026-01-01', '2026-01-07', tags_completas=True)
    assert linhas[2]['categoria_geral'] is not None
    assert comps[1]['comparaveis'] == 1
