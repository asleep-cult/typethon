import pathlib
import typing
import inspect
from types import EllipsisType

from ..parser import Parser
from . import types
from .evaluator import TypeEvaluator

ParamsT = typing.ParamSpec('ParamsT')
ReturnT = typing.TypeVar('ReturnT')
LiteralT = typing.Union[
    bool, None, EllipsisType, int, float, complex, str, typing.Tuple['LiteralT', ...]
]

BUILTINS: typing.Dict[str, types.ClassType] = {}


def callinline(function: typing.Callable[[], ReturnT]) -> ReturnT:
    return function()


@callinline
def load_builtins() -> None:
    path = pathlib.Path(__file__).parent.parent / 'builtins'

    for path in path.iterdir():
        filename = path.stem.removesuffix('.d')
        if not filename.endswith('object'):
            continue

        module = Parser.parse_module(path.read_text())
        module = TypeEvaluator.evaluate_module(module, definitions=True)

        type = filename.removesuffix('object')
        symbol = module.scope.get_symbol(type)

        if symbol is None:
            raise TypeError(f'{type} is not defined')

        assert isinstance(symbol.type, types.ClassType)
        BUILTINS[type] = symbol.type


def define(
    name: str
) -> typing.Callable[[typing.Callable[ParamsT, types.Type]], typing.Callable[ParamsT, types.Type]]:

    def wrapped(
        function: typing.Callable[ParamsT, types.Type]
    ) -> typing.Callable[ParamsT, types.Type]:
        type, method = name.split('.')

        symbol = BUILTINS[type].scope.get_symbol(method)
        if symbol is None:
            raise TypeError(f'{type} has no attribute {method}')

        assert isinstance(symbol.type, types.FunctionType)

        setattr(function, '__is_definition__', True)
        setattr(function, '__builtin_name__', name)
        setattr(function, '__builtin_function__', symbol.type)

        return function

    return wrapped


class BuiltinDefs:
    definitions: typing.Dict[str, types.Type]

    def __init_subclass__(cls) -> None:
        cls.definitions = {}

        for member in inspect.getmembers(cls, inspect.ismethod):
            function = member[1]
            is_definition = getattr(function, '__is_definition__', False)

            if is_definition:
                name: str = function.__builtin_name__
                builtin: types.FunctionType = function.__builtin_function__

                cls.definitions[name] = types.BuiltinFunctionType(
                    parameters=builtin.parameters,
                    returns=builtin.returns,
                    function=function,
                )

    def from_value(self, value: LiteralT) -> types.Type:
        if isinstance(value, bool):
            return types.BoolType(value=value)
        elif value is None:
            return types.NoneType()
        elif isinstance(value, EllipsisType):
            return types.EllipsisType()
        elif isinstance(value, str):
            return types.StringType(value=value)
        elif isinstance(value, int):
            return types.IntegerType(value=value)
        elif isinstance(value, float):
            return types.FloatType(value=value)
        elif isinstance(value, complex):
            return types.ComplexType(value=value)
        elif isinstance(value, tuple):
            values = [self.from_value(value) for value in value]
            return types.TupleType(values=values)

    def getattribute(self, evaluator: TypeEvaluator, name: str) -> types.Type:
        definition = self.definitions.get(name)
        if definition is None:
            return evaluator.unknown_type

        return definition


class IntegerDefs(BuiltinDefs):
    @define('int.__pos__')
    def pos(self, number: types.IntegerType) -> types.Type:
        assert number.value is not None
        return self.from_value(+number.value)

    @define('int.__neg__')
    def neg(self, number: types.IntegerType) -> types.Type:
        assert number.value is not None
        return self.from_value(-number.value)

    @define('int.__add__')
    def add(
        self,
        left: types.IntegerType,
        right: typing.Union[types.IntegerType, types.FloatType],
    ) -> types.Type:
        assert left.value is not None and right.value is not None
        return self.from_value(left.value + right.value)

    @define('int.__sub__')
    def sub(
        self,
        left: types.IntegerType,
        right: typing.Union[types.IntegerType, types.FloatType],
    ) -> types.Type:
        assert left.value is not None and right.value is not None
        return self.from_value(left.value - right.value)

    @define('int.__mult__')
    def mult(
        self,
        left: types.IntegerType,
        right: typing.Union[types.IntegerType, types.FloatType],
    ) -> types.Type:
        assert left.value is not None and right.value is not None
        return self.from_value(left.value * right.value)

    @define('int.__truediv__')
    def truediv(
        self,
        left: types.IntegerType,
        right: typing.Union[types.IntegerType, types.FloatType],
    ) -> types.Type:
        assert left.value is not None and right.value is not None
        return self.from_value(left.value / right.value)

    @define('int.__floordiv__')
    def floordiv(
        self,
        left: types.IntegerType,
        right: typing.Union[types.IntegerType, types.FloatType],
    ) -> types.Type:
        assert left.value is not None and right.value is not None
        return self.from_value(left.value // right.value)

    @define('int.__mod__')
    def mod(
        self,
        left: types.IntegerType,
        right: typing.Union[types.IntegerType, types.FloatType],
    ) -> types.Type:
        assert left.value is not None and right.value is not None
        return self.from_value(left.value % right.value)

    @define('int.__pow__')
    def pow(
        self,
        left: types.IntegerType,
        right: typing.Union[types.IntegerType, types.FloatType],
    ) -> types.Type:
        assert left.value is not None and right.value is not None
        return self.from_value(left.value ** right.value)

    @define('int.__or__')
    def bitor(self, left: types.IntegerType, right: types.IntegerType) -> types.Type:
        assert left.value is not None and right.value is not None
        return types.IntegerType(value=left.value | right.value)

    @define('int.__xor__')
    def bitxor(self, left: types.IntegerType, right: types.IntegerType) -> types.Type:
        assert left.value is not None and right.value is not None
        return types.IntegerType(value=left.value ^ right.value)

    @define('int.__and__')
    def bitand(self, left: types.IntegerType, right: types.IntegerType) -> types.Type:
        assert left.value is not None and right.value is not None
        return self.from_value(left.value & right.value)

    @define('int.__lshift__')
    def lshift(self, left: types.IntegerType, right: types.IntegerType) -> types.Type:
        assert left.value is not None and right.value is not None
        return self.from_value(left.value << right.value)

    @define('int.__rshift__')
    def rshift(self, left: types.IntegerType, right: types.IntegerType) -> types.Type:
        assert left.value is not None and right.value is not None
        return self.from_value(left.value >> right.value)

    @define('int.bit_length')
    def bit_length(self, number: types.IntegerType) -> types.Type:
        assert number.value is not None
        return self.from_value(number.value.bit_length())

    @define('int.bit_count')
    def bit_count(self, number: types.IntegerType) -> types.Type:
        assert number.value is not None
        return self.from_value(number.value.bit_count())

    @define('int.as_integer_ratio')
    def as_integer_ratio(self, number: types.IntegerType) -> types.Type:
        assert number.value is not None
        return self.from_value(number.value.as_integer_ratio())
