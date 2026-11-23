"""Pruebas del compilador. Quitan GEMINI_API_KEY para no llamar a la red.

Si se elimina setUp, una clave real haría que /explicar-error espere a Gemini
y la prueba dejaría de comprobar el texto de respaldo.
"""

import os
import unittest

from .lexico import tokenize
from .principal import CompileRequest, compile_expression, explain_error


class CompilerTests(unittest.TestCase):
    def setUp(self):
        self._clave_gemini = os.environ.pop("GEMINI_API_KEY", None)

    def tearDown(self):
        if self._clave_gemini is not None:
            os.environ["GEMINI_API_KEY"] = self._clave_gemini

    def test_precedence_and_unique_symbols(self):
        resultado = compile_expression(CompileRequest(fuente="10 + 25 * 10 - 4"))
        self.assertEqual(len(resultado["tokens"]), 7)
        self.assertEqual(resultado["resultado"], 256)
        self.assertEqual(
            [elemento["symbol"] for elemento in resultado["simbolos"]], [10, 25, 4]
        )

    def test_left_associative_subtraction_and_division(self):
        self.assertEqual(
            compile_expression(CompileRequest(fuente="100 - 20 - 5"))["resultado"], 75
        )
        self.assertEqual(
            compile_expression(CompileRequest(fuente="8 / 2 / 2"))["resultado"], 2
        )

    def test_all_lexical_errors_are_reported(self):
        _, errores = tokenize("7 $ 3 & 2")
        self.assertEqual(len(errores), 2)
        self.assertIn("posición 3", errores[0])
        self.assertIn("posición 7", errores[1])

    def test_machine_code_follows_ast_order(self):
        resultado = compile_expression(CompileRequest(fuente="10 + 25 * 10 - 4"))
        self.assertEqual(
            resultado["codigo_maquina"],
            [
                "PUSH 10",
                "PUSH 25",
                "PUSH 10",
                "MUL",
                "ADD",
                "PUSH 4",
                "SUB",
                "STORE R0",
            ],
        )

    def test_resolution_steps_prioritize_division(self):
        resultado = compile_expression(
            CompileRequest(fuente="25 - 24 - 26 + 36 + 96 / 25")
        )
        self.assertEqual(resultado["resultado"], 14.84)
        self.assertEqual(
            resultado["pasos_resolucion"][0]["calculation"], "96 / 25 = 3.84"
        )
        self.assertEqual(resultado["pasos_resolucion"][-1]["expression"], "14.84")

    def test_zero_based_token_and_error_positions(self):
        resultado = compile_expression(
            CompileRequest(fuente="7 $ 3 & 2", base_cero=True)
        )
        self.assertEqual(resultado["base_posiciones"], 0)
        self.assertIn("posición 2", resultado["errores"][0])
        self.assertIn("posición 6", resultado["errores"][1])

        valida = compile_expression(CompileRequest(fuente="10 + 4", base_cero=True))
        self.assertEqual(valida["tokens"][0]["position"], 0)
        self.assertEqual(valida["tokens"][1]["position"], 3)

    def test_error_response_contains_local_ia_explanation(self):
        respuesta = explain_error(CompileRequest(fuente="7 $ 3 & 2", base_cero=False))
        self.assertIn("no pudo compilarse", respuesta["explicacion_error"])
        self.assertIn("posición 3", respuesta["explicacion_error"])


if __name__ == "__main__":
    unittest.main()
