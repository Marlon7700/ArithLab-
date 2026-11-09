"""Construcción de tablas semánticas y evaluación del AST."""

from .parser import ASTNode


def build_tables(ast: ASTNode) -> tuple[list[dict], list[dict]]:
    numbers: list[int] = []
    _collect_numbers(ast, numbers)
    symbols = [
        {"symbol": number, "address": f"dir_{index + 1}"}
        for index, number in enumerate(numbers)
    ]
    types = [{"symbol": number, "type": "entero"} for number in numbers]
    return symbols, types


def _collect_numbers(node: ASTNode, numbers: list[int]) -> None:
    if isinstance(node.value, int) and node.value not in numbers:
        numbers.append(node.value)
    if node.left:
        _collect_numbers(node.left, numbers)
    if node.right:
        _collect_numbers(node.right, numbers)


def evaluate(node: ASTNode) -> int | float:
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
    """Genera instrucciones de una máquina de pila para ejecutar el AST."""
    instructions: list[str] = []

    def emit(current: ASTNode) -> None:
        if isinstance(current.value, int):
            instructions.append(f"PUSH {current.value}")
            return
        emit(current.left)  # type: ignore[arg-type]
        emit(current.right)  # type: ignore[arg-type]
        operation = {
            "+": "ADD",
            "-": "SUB",
            "*": "MUL",
            "/": "DIV",
        }[current.value]
        instructions.append(operation)

    emit(node)
    instructions.append("STORE R0")
    return instructions


def build_resolution_steps(node: ASTNode) -> list[dict[str, str]]:
    """Reduce la expresión respetando precedencia y asociatividad izquierda."""
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

    def format_number(value: int | float) -> str:
        return str(value) if isinstance(value, int) else f"{value:.10g}"

    def format_expression() -> str:
        parts: list[str] = [format_number(values[0])]
        for index, operator in enumerate(operators):
            parts.extend([operator, format_number(values[index + 1])])
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
        calculation = f"{format_number(left)} {operator} {format_number(right)} = {format_number(result)}"
        values[operator_index:operator_index + 2] = [result]
        operators.pop(operator_index)
        steps.append({
            "calculation": calculation,
            "expression": format_expression(),
            "priority": "prioritaria" if priority == 2 else "izquierda a derecha",
        })
    return steps
