"""Regressões do avaliador, sem publicar implementações dos katas."""

import importlib.util
from pathlib import Path
import unittest


CAMINHO = Path(__file__).resolve().parents[1] / "scripts" / "executar_testes.py"
SPEC = importlib.util.spec_from_file_location("executor", CAMINHO)
executor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(executor)


class TestExecutor(unittest.TestCase):
    def avaliar(self, funcao, caso):
        resultado = unittest.TestResult()
        executor.criar_teste(funcao, caso).run(resultado)
        return resultado

    def test_aceita_resultado_e_repete_chamada(self):
        chamadas = []

        def funcao(registros, limite):
            chamadas.append(1)
            return [("a", 3)]

        resultado = self.avaliar(funcao, {
            "nome": "valido", "registros": [["a", 2]],
            "limite": 5, "esperado": [["a", 3]],
        })
        self.assertTrue(resultado.wasSuccessful())
        self.assertEqual(len(chamadas), 2)

    def test_detecta_mutacao_antes_que_segunda_chamada_a_desfaca(self):
        def funcao(registros, limite):
            registros.reverse()
            return []

        resultado = self.avaliar(funcao, {
            "nome": "mutacao", "registros": [["a", 2], ["b", 3]],
            "limite": 0, "esperado": [],
        })
        self.assertEqual(len(resultado.failures), 1)
        self.assertIn("A entrada foi alterada", resultado.failures[0][1])

    def test_detecta_mutacao_mesmo_quando_excecao_e_esperada(self):
        def funcao(registros, limite):
            registros.clear()
            raise ValueError()

        resultado = self.avaliar(funcao, {
            "nome": "erro_com_mutacao", "registros": [["a", -1]],
            "limite": 5, "erro": "ValueError",
        })
        self.assertEqual(len(resultado.failures), 1)

    def test_aceita_value_error_sem_mutacao(self):
        def funcao(registros, limite):
            raise ValueError()

        resultado = self.avaliar(funcao, {
            "nome": "erro", "registros": [], "limite": -1, "erro": "ValueError",
        })
        self.assertTrue(resultado.wasSuccessful())

    def test_rejeita_tipos_que_comparam_iguais(self):
        for retorno in [[("a", 1.0)], [("a", True)], [["a", 1]], (("a", 1),)]:
            with self.subTest(retorno=retorno):
                resultado = self.avaliar(lambda registros, limite: retorno, {
                    "nome": "tipos", "registros": [["a", 0]],
                    "limite": 1, "esperado": [["a", 1]],
                })
                self.assertEqual(len(resultado.failures), 1)

    def test_rejeita_ordem_incorreta(self):
        resultado = self.avaliar(lambda registros, limite: [("b", 2), ("a", 3)], {
            "nome": "ordem", "registros": [["a", 2], ["b", 3]],
            "limite": 5, "esperado": [["a", 3], ["b", 2]],
        })
        self.assertEqual(len(resultado.failures), 1)


if __name__ == "__main__":
    unittest.main()
