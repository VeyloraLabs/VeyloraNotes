import ast
import math
import operator
import re

BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
UNARY_OPERATORS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
FUNCTIONS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "log": math.log10,
    "ln": math.log,
    "exp": math.exp,
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
    "min": min,
    "max": max,
}
CONSTANTS = {"pi": math.pi, "e": math.e, "tau": math.tau}
MAX_EXPONENT = 10000
MAX_EXPRESSION_LENGTH = 400


class CalculationError(Exception):
    pass


def prepare_expression(expression):
    cleaned = expression.strip().replace("×", "*").replace("÷", "/").replace("^", "**").replace("−", "-")
    cleaned = re.sub(r"(\d)\s*,\s*(\d)", r"\1.\2", cleaned)
    cleaned = re.sub(r"(\d+(?:\.\d+)?)\s*%\s*(?=$|[)+\-*/])", r"(\1/100)", cleaned)
    return cleaned


def evaluate_node(node):
    if isinstance(node, ast.Expression):
        return evaluate_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name) and node.id.lower() in CONSTANTS:
        return CONSTANTS[node.id.lower()]
    if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY_OPERATORS:
        return UNARY_OPERATORS[type(node.op)](evaluate_node(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in BINARY_OPERATORS:
        left = evaluate_node(node.left)
        right = evaluate_node(node.right)
        if isinstance(node.op, ast.Pow) and (abs(right) > MAX_EXPONENT or abs(left) > 1e154):
            raise CalculationError("exponent")
        return BINARY_OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id.lower() in FUNCTIONS and not node.keywords:
        arguments = [evaluate_node(argument) for argument in node.args]
        return FUNCTIONS[node.func.id.lower()](*arguments)
    raise CalculationError("unsupported")


def evaluate(expression):
    cleaned = prepare_expression(expression)
    if not cleaned or len(cleaned) > MAX_EXPRESSION_LENGTH:
        raise CalculationError("empty")
    try:
        tree = ast.parse(cleaned, mode="eval")
        value = evaluate_node(tree)
    except CalculationError:
        raise
    except (SyntaxError, ValueError, ZeroDivisionError, OverflowError, TypeError, RecursionError, MemoryError) as error:
        raise CalculationError(str(error)) from error
    if isinstance(value, complex):
        raise CalculationError("complex")
    return value


def format_number(value):
    if isinstance(value, int):
        return str(value)
    if value != value or value in (math.inf, -math.inf):
        raise CalculationError("not finite")
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return f"{value:.10g}"


def calculate_line(line):
    body = line.rstrip()
    if not body.strip():
        return line, False
    left = body.rsplit("=", 1)[0] if "=" in body else body
    try:
        result = format_number(evaluate(left))
    except CalculationError:
        return line, False
    return f"{left.rstrip()} = {result}", True


def calculate_text(text):
    lines = text.split("\n")
    output = []
    changed = 0
    for line in lines:
        new_line, success = calculate_line(line)
        output.append(new_line)
        changed += 1 if success else 0
    return "\n".join(output), changed
