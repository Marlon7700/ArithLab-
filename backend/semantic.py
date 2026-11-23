"""Tablas semánticas, evaluación y código de la máquina de pila.

compile_expression usa build_tables, evaluate, generate_machine_code y
build_resolution_steps. Gemini recibe ese resultado y lo narra; no lo calcula.
Si se elimina este módulo, no hay direcciones, tipos, resultado ni instrucciones.
"""

from .parser import ASTNode

_MACHINE_OPS = {"+": "ADD", "-": "SUB", "*": "MUL", "/": "DIV"}


def _format_number(value: int | float) -> str:
    """Escribe un entero sin decimales y un decimal sin ceros de más."""
    return str(value) if isinstance(value, int) else f"{value:.10g}"


def build_tables(ast: ASTNode) -> tuple[list[dict], list[dict]]:
    """Arma la tabla de símbolos (dir_1, dir_2...) y la de tipos (entero).

    Un número repetido no gana otra dirección: _collect_numbers lo ignora.
    Si se elimina, las tablas 04 y 06 de la interfaz quedan vacías.
    """
    numbers: list[int] = []
    _collect_numbers(ast, numbers)
    symbols = [
        {"symbol": number, "address": f"dir_{index + 1}"}
        for index, number in enumerate(numbers)
    ]
    types = [{"symbol": number, "type": "entero"} for number in numbers]
    return symbols, types


def _collect_numbers(node: ASTNode, numbers: list[int]) -> None:
    """Junta los enteros distintos en el orden en que aparecen en el árbol.

    Si se quita la condición «not in numbers», 10 + 25 * 10 crearía dos dir para el 10.
    """
    if isinstance(node.value, int) and node.value not in numbers:
        numbers.append(node.value)
    if node.left:
        _collect_numbers(node.left, numbers)
    if node.right:
        _collect_numbers(node.right, numbers)


def evaluate(node: ASTNode) -> int | float:
    """Calcula el valor del árbol: primero los hijos y después el operador.

    El resultado 256 de 10 + 25 * 10 - 4 sale de aquí, no de Gemini.
    Si se elimina el caso de un operador, esa operación dejaría de resolverse.
    """
    if isinstance(node.value, int):
        return node.value
    left = evaluate(node.left)  # type: ignore[arg-type]
    right = evaluate(node.right)  # type: ignore[arg-type]
    if node.value == "+":
        return left + right
    if node.value == "-":
        return left - right
    if node.value == "*":
        return left * right
    if right == 0:
        raise ZeroDivisionError("No se puede dividir entre cero.")
    result = left / right
    return int(result) if result.is_integer() else result


def generate_machine_code(node: ASTNode) -> list[str]:
    """Emite PUSH, ADD, SUB, MUL, DIV y STORE R0 en postorden.

    Visita el hijo izquierdo, el derecho y al final el operador.
    Si se quita STORE R0, la pila calcula el valor pero nadie lo guarda en R0.
    """
    instructions: list[str] = []

    def emit(current: ASTNode) -> None:
        if isinstance(current.value, int):
            instructions.append(f"PUSH {current.value}")
            return
        emit(current.left)  # type: ignore[arg-type]
        emit(current.right)  # type: ignore[arg-type]
        instructions.append(_MACHINE_OPS[str(current.value)])

    emit(node)
    instructions.append("STORE R0")
    return instructions


def build_resolution_steps(node: ASTNode) -> list[dict[str, str]]:
    """Lista cada reducción de la fórmula, con la expresión que va quedando.

    Primero * y /, después + y - de izquierda a derecha. Gemini debe narrar
    estos pasos tal cual. Si se elimina el criterio de prioridad, el orden
    de los pasos dejaría de coincidir con el árbol.
    """
    values: list[int | float] = []
    operators: list[str] = []

    def flatten(current: ASTNode) -> None:
        if isinstance(current.value, int):
            values.append(current.value)
            return
        flatten(current.left)  # type: ignore[arg-type]
        operators.append(str(current.value))
        flatten(current.right)  # type: ignore[arg-type]

    flatten(node)
    steps: list[dict[str, str]] = []

    def format_expression() -> str:
        parts: list[str] = [_format_number(values[0])]
        for index, operator in enumerate(operators):
            parts.extend([operator, _format_number(values[index + 1])])
        return " ".join(parts)

    while operators:
        priority = max(2 if operator in "*/" else 1 for operator in operators)
        operator_index = next(
            index for index, operator in enumerate(operators)
            if (2 if operator in "*/" else 1) == priority
        )
        left, right = values[operator_index], values[operator_index + 1]
        operator = operators[operator_index]
        if operator == "+":
            result = left + right
        elif operator == "-":
            result = left - right
        elif operator == "*":
            result = left * right
        elif right == 0:
            raise ZeroDivisionError("No se puede dividir entre cero.")
        else:
            result = left / right
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        calculation = (
            f"{_format_number(left)} {operator} {_format_number(right)} "
            f"= {_format_number(result)}"
        )
        values[operator_index:operator_index + 2] = [result]
        operators.pop(operator_index)
        steps.append({
            "calculation": calculation,
            "expression": format_expression(),
            "priority": "prioritaria" if priority == 2 else "izquierda a derecha",
        })
    return steps
