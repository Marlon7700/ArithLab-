"""API FastAPI del simulador de compilador aritmético."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .lexer import token_as_dict, tokenize
from .parser import Parser, ast_to_text
from .semantic import build_tables, evaluate, generate_machine_code, build_resolution_steps

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


@app.post("/compilar")
def compile_expression(request: CompileRequest) -> dict:
    tokens, lexical_errors = tokenize(request.source)
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
    except (ValueError, ZeroDivisionError) as error:
        response["errores"] = [str(error)]
    return response
