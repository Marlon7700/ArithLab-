import unittest

from .lexer import tokenize
from .main import compile_expression, CompileRequest


class CompilerTests(unittest.TestCase):
    def test_precedence_and_unique_symbols(self):
        result = compile_expression(CompileRequest(source="10 + 25 * 10 - 4"))
        self.assertEqual(len(result["tokens"]), 7)
        self.assertEqual(result["resultado"], 256)
        self.assertEqual([item["symbol"] for item in result["simbolos"]], [10, 25, 4])

    def test_left_associative_subtraction_and_division(self):
        self.assertEqual(compile_expression(CompileRequest(source="100 - 20 - 5"))["resultado"], 75)
        self.assertEqual(compile_expression(CompileRequest(source="8 / 2 / 2"))["resultado"], 2)

    def test_all_lexical_errors_are_reported(self):
        _, errors = tokenize("7 $ 3 & 2")
        self.assertEqual(len(errors), 2)
        self.assertIn("posición 3", errors[0])
        self.assertIn("posición 7", errors[1])

    def test_machine_code_follows_ast_order(self):
        result = compile_expression(CompileRequest(source="10 + 25 * 10 - 4"))
        self.assertEqual(
            result["codigo_maquina"],
            ["PUSH 10", "PUSH 25", "PUSH 10", "MUL", "ADD", "PUSH 4", "SUB", "STORE R0"],
        )

    def test_resolution_steps_prioritize_division(self):
        result = compile_expression(CompileRequest(source="25 - 24 - 26 + 36 + 96 / 25"))
        self.assertEqual(result["resultado"], 14.84)
        self.assertEqual(result["pasos_resolucion"][0]["calculation"], "96 / 25 = 3.84")
        self.assertEqual(result["pasos_resolucion"][-1]["expression"], "14.84")


if __name__ == "__main__":
    unittest.main()
