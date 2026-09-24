"""Verifica desfecho binário, pareamento e probabilidade exata de H2."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "analise_h2_correcao.py"
spec = importlib.util.spec_from_file_location("analise_h2_correcao", SCRIPT)
h2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h2)


def trial(integrante, kata, tratamento, concluiu=True):
    return {
        "integrante": integrante, "kata": kata, "tratamento": tratamento,
        "tempo_tempo_segundos": "100" if concluiu else "2100",
        "tempo_censurado": "False" if concluiu else "True",
        "avaliacao_concluido": "True" if concluiu else "False",
        "avaliacao_casos_aprovados": "26" if concluiu else "25",
        "avaliacao_total_casos": "26",
        "avaliacao_status_testes": "APROVADO" if concluiu else "REPROVADO",
    }


class AnaliseH2Test(unittest.TestCase):
    def test_mcnemar_exato_unilateral(self):
        pares = ([{"com_ia": 1, "sem_ia": 0}] * 3
                 + [{"com_ia": 0, "sem_ia": 1}])
        self.assertEqual(h2.mcnemar_exato(pares), (3, 1, 4, 0.3125))
        self.assertEqual(h2.mcnemar_exato([]), (0, 0, 0, None))

    def test_aprovacao_posterior_ao_limite_nao_e_conclusao(self):
        posterior = trial("A", "ExcessoBagagem", "COM_IA", False)
        posterior.update(avaliacao_casos_aprovados="26", avaliacao_status_testes="APROVADO")
        self.assertEqual(h2.classificar(posterior), (0, ""))
        posterior["avaliacao_concluido"] = "True"
        self.assertIsNone(h2.classificar(posterior)[0])

    def test_pareia_por_integrante_e_familia_sem_imputar_ausencias(self):
        linhas = [
            trial("A", "ReposicaoEstoque", "COM_IA"),
            trial("A", "MetaProducao", "SEM_IA", False),
            trial("A", "ExcessoBagagem", "COM_IA", False),
            trial("A", "ConsumoEnergetico", "SEM_IA"),
            trial("B", "ReposicaoEstoque", "COM_IA"),
        ]
        with tempfile.TemporaryDirectory() as pasta:
            resumo, teste = h2.analisar(linhas, Path(pasta))
            self.assertEqual((resumo[0]["n_validos"], resumo[1]["n_validos"]), (3, 2))
            self.assertEqual((teste["n_pares"], teste["pares_incompletos"]), (2, 1))
            self.assertEqual((teste["so_com_ia"], teste["so_sem_ia"]), (1, 1))
            self.assertEqual(teste["p_exato_unilateral_com_ia_maior"], 0.75)
            self.assertTrue((Path(pasta) / "h2_proporcao_conclusao.svg").exists())


if __name__ == "__main__":
    unittest.main()
