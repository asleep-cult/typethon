import inspect
import typing
from types import FunctionType, MethodType

from . import types
from .bridge import bridge_function, bridge_literal

ParamsT = typing.ParamSpec('ParamsT')


def define(
    name: str, *, method: bool = True
) -> typing.Callable[[typing.Callable[ParamsT, types.Type]], typing.Callable[ParamsT, types.Type]]:

    def wrapped(
        function: typing.Callable[ParamsT, types.Type]
    ) -> typing.Callable[ParamsT, types.Type]:
        assert isinstance(function, FunctionType)
        bridged = bridge_function(function, method=method)

        fields = bridged.get_fields()
        builtin_fields = types.FunctionFields(
            name=name, parameters=fields.parameters, returns=fields.returns
        )

        builtin = types.BuiltinFunctionType(
            flags=bridged.flags, fields=builtin_fields, function=function,
        )
        setattr(function, '__plugin_function__', builtin)

        return function

    return wrapped


class TypePlugin:
    definitions: typing.ClassVar[typing.Dict[str, types.Type]]

    def __init_subclass__(cls) -> None:
        cls.definitions = {}

        for member in inspect.getmembers(cls, inspect.isfunction):
            function: typing.Optional[types.BuiltinFunctionType] = getattr(
                member[1], '__plugin_function__', None
            )

            if function is not None:
                fields = function.get_fields()
                cls.definitions[fields.name] = function

    def getattribute(self, name: str) -> typing.Optional[types.Type]:
        definition = self.definitions.get(name)

        if isinstance(definition, types.BuiltinFunctionType):
            return types.BuiltinFunctionType(
                fields=definition.fields,
                function=MethodType(definition.function, self),
            )

        return definition


class FunctionPlugin(TypePlugin):
    @define('__get__')
    def get(
        self,
        function: types.FunctionType,
        instance: types.ObjectType,
        owner: types.TypeInstance,
    ) -> types.MethodType:
        fields = types.MethodFields(instance=instance.get_value(), function=function)
        return types.MethodType(fields=fields)


class IntegerPlugin(TypePlugin):
    @define('__pos__')
    def pos(self, number: types.IntegerType) -> types.IntegerType:
        if number.value is None:
            return number

        return bridge_literal(+number.value)

    @define('__neg__')
    def neg(self, number: types.IntegerType) -> types.IntegerType:
        if number.value is None:
            return number

        return bridge_literal(-number.value)

    @define('__add__')
    def add(
        self,
        left: types.IntegerType,
        right: typing.Union[types.IntegerType, types.FloatType],
    ) -> typing.Union[types.IntegerType, types.FloatType]:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value + right.value)

    @define('__sub__')
    def sub(
        self,
        left: types.IntegerType,
        right: typing.Union[types.IntegerType, types.FloatType],
    ) -> typing.Union[types.IntegerType, types.FloatType]:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value - right.value)

    @define('__mult__')
    def mult(
        self,
        left: types.IntegerType,
        right: typing.Union[types.IntegerType, types.FloatType],
    ) -> typing.Union[types.IntegerType, types.FloatType]:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value * right.value)

    @define('__truediv__')
    def truediv(
        self,
        left: types.IntegerType,
        right: typing.Union[types.IntegerType, types.FloatType],
    ) -> types.FloatType:
        if left.value is None or right.value is None:
            return types.FloatType()

        return bridge_literal(left.value / right.value)

    @define('__floordiv__')
    def floordiv(
        self,
        left: types.IntegerType,
        right: typing.Union[types.IntegerType, types.FloatType],
    ) -> typing.Union[types.IntegerType, types.FloatType]:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value // right.value)

    @define('__mod__')
    def mod(
        self,
        left: types.IntegerType,
        right: typing.Union[types.IntegerType, types.FloatType],
    ) -> typing.Union[types.IntegerType, types.FloatType]:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value % right.value)

    @define('__pow__')
    def pow(
        self,
        left: types.IntegerType,
        right: typing.Union[types.IntegerType, types.FloatType],
    ) -> typing.Union[types.IntegerType, types.FloatType]:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value ** right.value)

    @define('__or__')
    def bitor(self, left: types.IntegerType, right: types.IntegerType) -> types.IntegerType:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value | right.value)

    @define('__xor__')
    def bitxor(self, left: types.IntegerType, right: types.IntegerType) -> types.IntegerType:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value ^ right.value)

    @define('__and__')
    def bitand(self, left: types.IntegerType, right: types.IntegerType) -> types.IntegerType:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value & right.value)

    @define('__lshift__')
    def lshift(self, left: types.IntegerType, right: types.IntegerType) -> types.IntegerType:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value << right.value)

    @define('__rshift__')
    def rshift(self, left: types.IntegerType, right: types.IntegerType) -> types.IntegerType:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value >> right.value)

    @define('bit_length')
    def bit_length(self, number: types.IntegerType) -> types.IntegerType:
        if number.value is None:
            return number

        return bridge_literal(number.value.bit_length())

    @define('bit_count')
    def bit_count(self, number: types.IntegerType) -> types.IntegerType:
        if number.value is None:
            return number

        return bridge_literal(number.value.bit_count())

    @define('as_integer_ratio')
    def as_integer_ratio(self, number: types.IntegerType) -> types.TupleType:
        if number.value is None:
            return types.TupleType(values=[types.IntegerType(), types.IntegerType(value=1)])

        return bridge_literal(number.value.as_integer_ratio())
