from pathlib import Path

import typing

from ..syntax.typethon import ASTParser, ast
from ..analysis import TypeAnalyzer, PolymorphicType, TypeCache

OPERATORS_PATH = './operators.tpy'


def generate_operators(type_cache: TypeCache) -> typing.Dict[str, PolymorphicType]:
    path = Path(__file__).parent / OPERATORS_PATH

    with open(path, 'r') as fp:
        source = fp.read()

    parser = ASTParser(source, 'module')

    module = parser.parse()
    assert isinstance(module, ast.ModuleNode)

    analyzer = TypeAnalyzer(type_cache, module)
    analyzer.analyze_module()

    operator_classes: typing.Dict[str, PolymorphicType] = {}
    for name, symbol in analyzer.ctx.symbols.items():
        if isinstance(symbol, PolymorphicType):
            operator_classes[name] = symbol

    return operator_classes
