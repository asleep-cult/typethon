from pathlib import Path

from ..syntax.typethon import ASTParser, ast
from ..analysis import TypeAnalyzer, ImplementationMap
from ..analysis import types

OPERATORS_PATH = './operators.tpy'


def generate_operators() -> ImplementationMap:
    path = Path(__file__).parent / OPERATORS_PATH

    with open(path, 'r') as fp:
        source = fp.read()

    parser = ASTParser(source, 'module')

    module = parser.parse()
    assert isinstance(module, ast.ModuleNode)

    analyzer = TypeAnalyzer(module)
    analyzer.analyze_module()

    return analyzer.implementations
