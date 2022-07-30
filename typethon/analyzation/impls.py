import inspect
import typing
from types import FunctionType, MethodType

from . import atoms
from .bridge import bridge_function, bridge_literal

ParamsT = typing.ParamSpec('ParamsT')


def define(
    name: str, *, method: bool = True
) -> typing.Callable[[typing.Callable[ParamsT, atoms.Atom]], typing.Callable[ParamsT, atoms.Atom]]:
    def wrapped(
        function: typing.Callable[ParamsT, atoms.Atom]
    ) -> typing.Callable[ParamsT, atoms.Atom]:
        assert isinstance(function, FunctionType)
        bridged = bridge_function(function, method=method)

        fields = bridged.get_fields()
        builtin_fields = atoms.FunctionFields(
            name=name, parameters=fields.parameters, returns=fields.returns
        )

        builtin = atoms.BuiltinFunctionAtom(builtin_fields, function=function, flags=bridged.flags)
        setattr(function, '__plugin_function__', builtin)

        return function

    return wrapped


class AtomImpl:
    definitions: typing.ClassVar[typing.Dict[str, atoms.Atom]]

    def __init_subclass__(cls) -> None:
        cls.definitions = {}

        for member in inspect.getmembers(cls, inspect.isfunction):
            function: typing.Optional[atoms.BuiltinFunctionAtom] = getattr(
                member[1], '__plugin_function__', None
            )

            if function is not None:
                fields = function.get_fields()
                cls.definitions[fields.name] = function

    def get_attribute(self, name: str) -> typing.Optional[atoms.Atom]:
        definition = self.definitions.get(name)

        if isinstance(definition, atoms.BuiltinFunctionAtom):
            return atoms.BuiltinFunctionAtom(
                definition.fields,
                function=MethodType(definition.function, self),
            )

        return definition


class TypeImpl(AtomImpl):
    @define('__or__')
    def bitor(
        self, left: atoms.TypeAtom, right: atoms.TypeAtom
    ) -> atoms.TypeAtom:
        if left.value is None or right.value is None:
            raise RuntimeError('type atom is missing value')

        union = atoms.union((left.value.instantiate(), right.value.instantiate()))
        return atoms.TypeAtom(union)


class IntegerImpl(AtomImpl):
    @define('__pos__')
    def pos(self, number: atoms.IntegerAtom) -> atoms.IntegerAtom:
        if number.value is None:
            return number

        return bridge_literal(+number.value).unwrap_as(atoms.IntegerAtom)

    @define('__neg__')
    def neg(self, number: atoms.IntegerAtom) -> atoms.IntegerAtom:
        if number.value is None:
            return number

        return bridge_literal(-number.value).unwrap_as(atoms.IntegerAtom)

    @define('__add__')
    def add(
        self,
        left: atoms.IntegerAtom,
        right: typing.Union[atoms.IntegerAtom, atoms.FloatAtom],
    ) -> typing.Union[atoms.IntegerAtom, atoms.FloatAtom]:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value + right.value).unwrap_as(
            typing.Union[atoms.IntegerAtom, atoms.FloatAtom]
        )

    @define('__sub__')
    def sub(
        self,
        left: atoms.IntegerAtom,
        right: typing.Union[atoms.IntegerAtom, atoms.FloatAtom],
    ) -> typing.Union[atoms.IntegerAtom, atoms.FloatAtom]:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value - right.value).unwrap_as(
            typing.Union[atoms.IntegerAtom, atoms.FloatAtom]
        )

    @define('__mult__')
    def mult(
        self,
        left: atoms.IntegerAtom,
        right: typing.Union[atoms.IntegerAtom, atoms.FloatAtom],
    ) -> typing.Union[atoms.IntegerAtom, atoms.FloatAtom]:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value * right.value).unwrap_as(
            typing.Union[atoms.IntegerAtom, atoms.FloatAtom]
        )

    @define('__truediv__')
    def truediv(
        self,
        left: atoms.IntegerAtom,
        right: typing.Union[atoms.IntegerAtom, atoms.FloatAtom],
    ) -> atoms.FloatAtom:
        if left.value is None or right.value is None:
            return atoms.FloatAtom()

        return bridge_literal(left.value / right.value).unwrap_as(atoms.FloatAtom)

    @define('__floordiv__')
    def floordiv(
        self,
        left: atoms.IntegerAtom,
        right: typing.Union[atoms.IntegerAtom, atoms.FloatAtom],
    ) -> typing.Union[atoms.IntegerAtom, atoms.FloatAtom]:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value // right.value).unwrap_as(
            typing.Union[atoms.IntegerAtom, atoms.FloatAtom]
        )

    @define('__mod__')
    def mod(
        self,
        left: atoms.IntegerAtom,
        right: typing.Union[atoms.IntegerAtom, atoms.FloatAtom],
    ) -> typing.Union[atoms.IntegerAtom, atoms.FloatAtom]:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value % right.value).unwrap_as(
            typing.Union[atoms.IntegerAtom, atoms.FloatAtom]
        )

    @define('__pow__')
    def pow(
        self,
        left: atoms.IntegerAtom,
        right: typing.Union[atoms.IntegerAtom, atoms.FloatAtom],
    ) -> typing.Union[atoms.IntegerAtom, atoms.FloatAtom]:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value**right.value).unwrap_as(
            typing.Union[atoms.IntegerAtom, atoms.FloatAtom]
        )

    @define('__or__')
    def bitor(self, left: atoms.IntegerAtom, right: atoms.IntegerAtom) -> atoms.IntegerAtom:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value | right.value).unwrap_as(atoms.IntegerAtom)

    @define('__xor__')
    def bitxor(self, left: atoms.IntegerAtom, right: atoms.IntegerAtom) -> atoms.IntegerAtom:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value ^ right.value).unwrap_as(atoms.IntegerAtom)

    @define('__and__')
    def bitand(self, left: atoms.IntegerAtom, right: atoms.IntegerAtom) -> atoms.IntegerAtom:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value & right.value).unwrap_as(atoms.IntegerAtom)

    @define('__lshift__')
    def lshift(self, left: atoms.IntegerAtom, right: atoms.IntegerAtom) -> atoms.IntegerAtom:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value << right.value).unwrap_as(atoms.IntegerAtom)

    @define('__rshift__')
    def rshift(self, left: atoms.IntegerAtom, right: atoms.IntegerAtom) -> atoms.IntegerAtom:
        if left.value is None or right.value is None:
            return right

        return bridge_literal(left.value >> right.value).unwrap_as(atoms.IntegerAtom)

    @define('bit_length')
    def bit_length(self, number: atoms.IntegerAtom) -> atoms.IntegerAtom:
        if number.value is None:
            return number

        return bridge_literal(number.value.bit_length()).unwrap_as(atoms.IntegerAtom)

    @define('bit_count')
    def bit_count(self, number: atoms.IntegerAtom) -> atoms.IntegerAtom:
        if number.value is None:
            return number

        return bridge_literal(number.value.bit_count()).unwrap_as(atoms.IntegerAtom)

    @define('as_integer_ratio')
    def as_integer_ratio(self, number: atoms.IntegerAtom) -> atoms.TupleAtom:
        if number.value is None:
            return atoms.TupleAtom([atoms.IntegerAtom(), atoms.IntegerAtom(value=1)])

        return bridge_literal(number.value.as_integer_ratio()).unwrap_as(atoms.TupleAtom)


class FunctionImpl(TypeImpl):
    @define('__get__')
    def get(
        self,
        function: atoms.FunctionAtom,
        instance: typing.Union[atoms.ObjectAtom, atoms.NoneAtom],
        owner: atoms.TypeAtom,
    ) -> typing.Union[atoms.MethodAtom, atoms.FunctionAtom]:
        if isinstance(instance, atoms.NoneAtom):
            return function

        if instance.value is None:
            raise RuntimeError('type atom is missing value')

        fields = atoms.MethodFields(instance=instance.value, function=function)
        return atoms.MethodAtom(fields)
