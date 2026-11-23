"""Pruebas del compilador. Quitan GEMINI_API_KEY para no llamar a la red.

Si se elimina setUp, una clave real haría que /explicar-error espere a Gemini
y la prueba dejaría de comprobar el texto de respaldo.
"""

import os
import unittest

from .lexer import tokenize
from .main import CompileRequest, compile_expression, explain_error


class CompilerTests(unittest.TestCase):
    def setUp(self):
        self._gemini_key = os.environ.pop("GEMINI_API_KEY", None)

    def tearDown(self):
        if self._gemini_key is not None:
            os.environ["GEMINI_API_KEY"] = self._gemini_key

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

    def test_zero_based_token_and_error_positions(self):
        result = compile_expression(CompileRequest(source="7 $ 3 & 2", zero_based=True))
        self.assertEqual(result["base_posiciones"], 0)
        self.assertIn("posición 2", result["errores"][0])
        self.assertIn("posición 6", result["errores"][1])

        valid = compile_expression(CompileRequest(source="10 + 4", zero_based=True))
        self.assertEqual(valid["tokens"][0]["position"], 0)
        self.assertEqual(valid["tokens"][1]["position"], 3)

    def test_error_response_contains_local_ia_explanation(self):
        response = explain_error(CompileRequest(source="7 $ 3 & 2", zero_based=False))
        self.assertIn("no pudo compilarse", response["explicacion_error"])
        self.assertIn("posición 3", response["explicacion_error"])


if __name__ == "__main__":
    unittest.main()
