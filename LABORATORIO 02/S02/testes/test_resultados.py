import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def carregar(nome):
    spec = importlib.util.spec_from_file_location(nome, SCRIPTS / f"{nome}.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


consolidacao = carregar("consolidar_trials")
validacao = carregar("executar_validacao")


class TestConsolidacao(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.pasta = Path(self.temporario.name)

    def escrever(self, nome, campos, linhas):
        with (self.pasta / nome).open("w", newline="", encoding="utf-8") as arquivo:
            escritor = csv.writer(arquivo)
            escritor.writerow([*consolidacao.CHAVE, *campos])
            escritor.writerows(linhas)

    def test_relaciona_por_chave_e_preserva_faltantes(self):
        self.escrever("tempos_trials.csv", ["tempo_segundos"], [
            ["Pessoa", "ReposicaoEstoque", "COM_IA", "123.4"],
        ])
        self.escrever("avaliacao_trials.csv", ["status_testes"], [
            ["Pessoa", "ExcessoBagagem", "SEM_IA", "REPROVADO"],
            ["Pessoa", "ReposicaoEstoque", "COM_IA", "APROVADO"],
        ])
        _, linhas, excluidos, _ = consolidacao.consolidar(self.pasta)
        por_kata = {linha["kata"]: linha for linha in linhas}
        self.assertEqual(len(linhas), 2)
        self.assertEqual(por_kata["ReposicaoEstoque"]["tempo_tempo_segundos"], "123.4")
        self.assertEqual(por_kata["ReposicaoEstoque"]["avaliacao_status_testes"], "APROVADO")
        self.assertNotIn("tempo_tempo_segundos", por_kata["ExcessoBagagem"])
        self.assertIn("tempo", por_kata["ExcessoBagagem"]["fontes_pendentes"])
        self.assertEqual(excluidos, [])

    def test_rejeita_duplicata_em_vez_de_sobrescrever(self):
        linha = ["Pessoa", "ReposicaoEstoque", "COM_IA", "123"]
        self.escrever("tempos_trials.csv", ["tempo_segundos"], [linha, linha])
        with self.assertRaisesRegex(ValueError, "duplicada"):
            consolidacao.consolidar(self.pasta)

    def test_exclui_apenas_instrumentacao_conhecida(self):
        self.escrever("tempos_trials.csv", ["tempo_segundos"], [
            ["Pedro", "Teste", "COM_IA", "21.01"],
        ])
        _, linhas, excluidos, _ = consolidacao.consolidar(self.pasta)
        self.assertEqual(linhas, [])
        self.assertEqual(len(excluidos), 1)
        self.assertEqual(excluidos[0]["linha"], 2)

    def test_kata_desconhecido_nao_some_silenciosamente(self):
        self.escrever("tempos_trials.csv", ["tempo_segundos"], [
            ["Pessoa", "DigitadoErrado", "COM_IA", "123"],
        ])
        with self.assertRaisesRegex(ValueError, "inválida"):
            consolidacao.consolidar(self.pasta)

    def test_falta_de_dados_nao_cria_trials(self):
        _, linhas, excluidos, ausentes = consolidacao.consolidar(self.pasta)
        self.assertEqual(linhas, [])
        self.assertEqual(excluidos, [])
        self.assertEqual(len(ausentes), 4)


class TestResumoTestes(unittest.TestCase):
    def test_aprovacao_exige_resumo_e_codigo_zero(self):
        texto = "ReposicaoEstoque: 26/26 casos aprovados.\n"
        self.assertEqual(validacao.resumir_teste("ReposicaoEstoque", 0, texto), ("APROVADO", 26, 26))
        self.assertEqual(validacao.resumir_teste("ReposicaoEstoque", 1, texto)[0], "REPROVADO")
        self.assertEqual(validacao.resumir_teste("ReposicaoEstoque", 0, "")[0], "ERRO_EXECUTOR")

    def test_falhas_e_timeout(self):
        self.assertEqual(validacao.resumir_teste("MetaProducao", 1, "MetaProducao: 20/26 casos aprovados.\n"), ("REPROVADO", 20, 26))
        self.assertEqual(validacao.resumir_teste("MetaProducao", 1, "Tempo limite dos testes excedido"), ("TIMEOUT", "", ""))


if __name__ == "__main__":
    unittest.main()
