"""API FastAPI del simulador de compilador aritmético."""

import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .lexer import Token, token_as_dict, tokenize
from .parser import Parser, ast_to_text
from .semantic import build_tables, evaluate, generate_machine_code, build_resolution_steps
from .gemini import build_local_explanations, generate_explanation

app = FastAPI(title="ArithLab+ API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r"(https?://(localhost|127\.0\.0\.1)(:\d+)?|https://([a-z0-9-]+\.)*vercel\.app)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "arithlab-backend"}


class CompileRequest(BaseModel):
    source: str = Field(default="", max_length=2000)
    zero_based: bool = Field(default=False)


def _convert_error_positions(errors: list[str], zero_based: bool) -> list[str]:
    if not zero_based:
        return errors

    converted: list[str] = []
    for error in errors:
        def replace(match: re.Match[str]) -> str:
            return f"posición {int(match.group(1)) - 1}"

        converted.append(re.sub(r"posición (\d+)", replace, error))
    return converted


@app.post("/compilar")
def compile_expression(request: CompileRequest) -> dict:
    tokens, lexical_errors = tokenize(request.source)
    if request.zero_based:
        tokens = [
            Token(token.type, token.value, token.position - 1)
            for token in tokens
        ]
        lexical_errors = _convert_error_positions(lexical_errors, True)
    response = {
        "tokens": [token_as_dict(token) for token in tokens],
        "ast": None,
        "ast_text": "",
        "simbolos": [],
        "tipos": [],
        "errores": lexical_errors,
        "resultado": None,
        "codigo_maquina": [],
        "pasos_resolucion": [],
        "explicacion_ia": "",
        "explicacion_semantica": "",
        "explicacion_codigo_maquina": "",
        "modelo_ia": "determinista",
        "base_posiciones": 0 if request.zero_based else 1,
    }

    if not request.source.strip():
        response["errores"] = ["La entrada está vacía. Escribe una expresión aritmética."]
        return response
    if lexical_errors:
        return response

    try:
        ast = Parser(tokens).parse()
        symbols, types = build_tables(ast)
        response.update(
            ast=ast.to_dict(),
            ast_text=ast_to_text(ast),
            simbolos=symbols,
            tipos=types,
            resultado=evaluate(ast),
            codigo_maquina=generate_machine_code(ast),
            pasos_resolucion=build_resolution_steps(ast),
        )
        response.update(build_local_explanations(request.source, response))
    except (ValueError, ZeroDivisionError) as error:
        response["errores"] = [str(error)]
    return response


@app.post("/explicar")
def explain_expression(request: CompileRequest) -> dict:
    compiled = compile_expression(request)
    if compiled.get("errores") or compiled.get("ast") is None:
        return {
            "explicacion_ia": "",
            "explicacion_semantica": "",
            "explicacion_codigo_maquina": "",
        }
    return generate_explanation(request.source, compiled)
