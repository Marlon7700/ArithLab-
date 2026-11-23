"""Tablas semánticas, evaluación y código de la máquina de pila.

compile_expression usa build_tables, evaluate, generate_machine_code y
build_resolution_steps. Gemini recibe ese resultado y lo narra; no lo calcula.
Si se elimina este módulo, no hay direcciones, tipos, resultado ni instrucciones.
"""

from .sintactico import ASTNode

_OPERACIONES_MAQUINA = {"+": "ADD", "-": "SUB", "*": "MUL", "/": "DIV"}


def _format_number(valor: int | float) -> str:
    """Escribe un entero sin decimales y un decimal sin ceros de más."""
    return str(valor) if isinstance(valor, int) else f"{valor:.10g}"


def build_tables(arbol: ASTNode) -> tuple[list[dict], list[dict]]:
    """Arma la tabla de símbolos (dir_1, dir_2...) y la de tipos (entero).

    Un número repetido no gana otra dirección: _collect_numbers lo ignora.
    Si se elimina, las tablas 04 y 06 de la interfaz quedan vacías.
    Las claves symbol, address y type se conservan porque las lee App.jsx.
    """
    numeros: list[int] = []
    _collect_numbers(arbol, numeros)
    simbolos = [
        {"symbol": numero, "address": f"dir_{indice + 1}"}
        for indice, numero in enumerate(numeros)
    ]
    tipos = [{"symbol": numero, "type": "entero"} for numero in numeros]
    return simbolos, tipos


def _collect_numbers(nodo: ASTNode, numeros: list[int]) -> None:
    """Junta los enteros distintos en el orden en que aparecen en el árbol.

    Si se quita la condición «not in numeros», 10 + 25 * 10 crearía dos dir para el 10.
    """
    if isinstance(nodo.valor, int) and nodo.valor not in numeros:
        numeros.append(nodo.valor)
    if nodo.izquierda:
        _collect_numbers(nodo.izquierda, numeros)
    if nodo.derecha:
        _collect_numbers(nodo.derecha, numeros)


def evaluate(nodo: ASTNode) -> int | float:
    """Calcula el valor del árbol: primero los hijos y después el operador.

    El resultado 256 de 10 + 25 * 10 - 4 sale de aquí, no de Gemini.
    Si se elimina el caso de un operador, esa operación dejaría de resolverse.
    """
    if isinstance(nodo.valor, int):
        return nodo.valor
    izquierda = evaluate(nodo.izquierda)  # type: ignore[arg-type]
    derecha = evaluate(nodo.derecha)  # type: ignore[arg-type]
    if nodo.valor == "+":
        return izquierda + derecha
    if nodo.valor == "-":
        return izquierda - derecha
    if nodo.valor == "*":
        return izquierda * derecha
    if derecha == 0:
        raise ZeroDivisionError("No se puede dividir entre cero.")
    resultado = izquierda / derecha
    return int(resultado) if resultado.is_integer() else resultado


def generate_machine_code(nodo: ASTNode) -> list[str]:
    """Emite PUSH, ADD, SUB, MUL, DIV y STORE R0 en postorden.

    Visita el hijo izquierdo, el derecho y al final el operador.
    Si se quita STORE R0, la pila calcula el valor pero nadie lo guarda en R0.
    """
    instrucciones: list[str] = []

    def emitir(actual: ASTNode) -> None:
        if isinstance(actual.valor, int):
            instrucciones.append(f"PUSH {actual.valor}")
            return
        emitir(actual.izquierda)  # type: ignore[arg-type]
        emitir(actual.derecha)  # type: ignore[arg-type]
        instrucciones.append(_OPERACIONES_MAQUINA[str(actual.valor)])

    emitir(nodo)
    instrucciones.append("STORE R0")
    return instrucciones


def build_resolution_steps(nodo: ASTNode) -> list[dict[str, str]]:
    """Lista cada reducción de la fórmula, con la expresión que va quedando.

    Primero * y /, después + y - de izquierda a derecha. Gemini debe narrar
    estos pasos tal cual. Si se elimina el criterio de prioridad, el orden
    de los pasos dejaría de coincidir con el árbol.
    Las claves calculation, expression y priority se conservan para la interfaz.
    """
    valores: list[int | float] = []
    operadores: list[str] = []

    def aplanar(actual: ASTNode) -> None:
        if isinstance(actual.valor, int):
            valores.append(actual.valor)
            return
        aplanar(actual.izquierda)  # type: ignore[arg-type]
        operadores.append(str(actual.valor))
        aplanar(actual.derecha)  # type: ignore[arg-type]

    aplanar(nodo)
    pasos: list[dict[str, str]] = []

    def formatear_expresion() -> str:
        partes: list[str] = [_format_number(valores[0])]
        for indice, operador in enumerate(operadores):
            partes.extend([operador, _format_number(valores[indice + 1])])
        return " ".join(partes)

    while operadores:
        prioridad = max(2 if operador in "*/" else 1 for operador in operadores)
        indice_operador = next(
            indice
            for indice, operador in enumerate(operadores)
            if (2 if operador in "*/" else 1) == prioridad
        )
        izquierda, derecha = valores[indice_operador], valores[indice_operador + 1]
        operador = operadores[indice_operador]
        if operador == "+":
            resultado = izquierda + derecha
        elif operador == "-":
            resultado = izquierda - derecha
        elif operador == "*":
            resultado = izquierda * derecha
        elif derecha == 0:
            raise ZeroDivisionError("No se puede dividir entre cero.")
        else:
            resultado = izquierda / derecha
        if isinstance(resultado, float) and resultado.is_integer():
            resultado = int(resultado)
        calculo = (
            f"{_format_number(izquierda)} {operador} {_format_number(derecha)} "
            f"= {_format_number(resultado)}"
        )
        valores[indice_operador : indice_operador + 2] = [resultado]
        operadores.pop(indice_operador)
        pasos.append(
            {
                "calculation": calculo,
                "expression": formatear_expresion(),
                "priority": "prioritaria" if prioridad == 2 else "izquierda a derecha",
            }
        )
    return pasos
