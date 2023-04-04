import inspect
import itertools
import types
import typing

from . import atoms
from .bridge import bridge_function, bridge_literal

if typing.TYPE_CHECKING:
    from .atomizer import Atomizer
else:
    Atomizer = typing.NewType('Atomizer', typing.Any)

ParamsT = typing.ParamSpec('ParamsT')


def define(
    name: str, *, method: bool = True
) -> typing.Callable[[typing.Callable[ParamsT, atoms.Atom]], typing.Callable[ParamsT, atoms.Atom]]:
    def wrapped(
        function: typing.Callable[ParamsT, atoms.Atom]
    ) -> typing.Callable[ParamsT, atoms.Atom]:
        assert isinstance(function, types.FunctionType)
        bridged = bridge_function(function, method=method)

        fields = bridged.get_fields()
        builtin_fields = atoms.FunctionFields(
            name=name, parameters=fields.parameters, returns=fields.returns
        )

        builtin = atoms.BuiltinFunctionAtom(builtin_fields, function=function, flags=bridged.flags)
        setattr(function, '__impl_function__', builtin)

        return function

    return wrapped


def returns(
    atom: atoms.Atom
) -> typing.Callable[[typing.Callable[ParamsT, atoms.Atom]], typing.Callable[ParamsT, atoms.Atom]]:
    def wrapped(
        function: typing.Callable[ParamsT, atoms.Atom]
    ) -> typing.Callable[ParamsT, atoms.Atom]:
        assert isinstance(function, types.FunctionType)

        setattr(function, '__impl_returns__', atom)
        return function

    return wrapped


class AtomImpl:
    definitions: typing.ClassVar[typing.Dict[str, atoms.Atom]]

    def __init__(self, atomizer: Atomizer) -> None:
        self.atomizer = atomizer

    def __init_subclass__(cls) -> None:
        cls.definitions = {}

        for member in inspect.getmembers(cls, inspect.isfunction):
            function: typing.Optional[atoms.BuiltinFunctionAtom] = getattr(
                member[1], '__impl_function__', None
            )

            if function is not None:
                fields = function.get_fields()
                cls.definitions[fields.name] = function

    def get_attribute(self, name: str) -> atoms.Atom:
        definition = self.definitions.get(name, atoms.UNKNOWN)

        if isinstance(definition, atoms.BuiltinFunctionAtom):
            return atoms.BuiltinFunctionAtom(
                definition.fields,
                function=types.MethodType(definition.function, self),
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
    @returns(atoms.TupleAtom([atoms.IntegerAtom(), atoms.IntegerAtom(value=1)]))
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

    @define('__call__')
    def call(
        self,
        function: atoms.FunctionAtom,
        *arguments: atoms.Atom,
        **keywords: atoms.Atom,
    ) -> atoms.Atom:
        errors: typing.List[atoms.ErrorAtom] = []

        final_arguments: typing.List[atoms.Atom] = []
        final_keywords: typing.Dict[str, atoms.Atom] = {}

        fields = function.get_fields()
        parameters = fields.parameters.copy()

        varpositional_parameter = None
        varkeyword_parameter = None

        for parameter in fields.parameters:
            if parameter.kind is atoms.ParameterKind.VARARG:
                varpositional_parameter = parameter
                parameters.remove(parameter)

            elif parameter.kind is atoms.ParameterKind.VARKWARG:
                varkeyword_parameter = parameter
                parameters.remove(parameter)

        positional_parameters = [
            parameter for parameter in parameters
            if parameter.kind in (atoms.ParameterKind.POSONLY, atoms.ParameterKind.ARG)
        ]

        for index, argument in enumerate(arguments):
            if parameters:
                parameter = positional_parameters.pop(0)
                parameters.remove(parameter)
            else:
                parameter = varpositional_parameter

            if parameter is not None:
                if parameter.kind is atoms.AtomKind.OBJECT:
                    argument = atoms.ObjectAtom(argument)

                final_arguments.append(argument)
            else:
                msg = f'argument {index} has no matching parameter'
                errors.append(atoms.ErrorAtom(atoms.ErrorCategory.TYPE_ERROR, msg))

        keyword_parameters = {
            parameter.name: parameter for parameter in parameters
            if parameter.kind in (atoms.ParameterKind.ARG, atoms.ParameterKind.KWONLY)
        }

        for name, argument in keywords.items():
            if name in keyword_parameters:
                parameter = keyword_parameters.pop(name)
                parameters.remove(parameter)
            else:
                parameter = varkeyword_parameter

            if parameter is not None:
                if parameter.kind is atoms.AtomKind.OBJECT:
                    argument = atoms.ObjectAtom(argument)

                final_keywords[name] = argument
            else:
                msg = f'argument {name!r} has no matching parameter'
                errors.append(atoms.ErrorAtom(atoms.ErrorCategory.TYPE_ERROR, msg))

        iterator = (parameter for parameter in parameters if parameter.default is not None)
        for parameter in iterator:
            msg = f'missing argument for parameter {parameter.name!r}'
            errors.append(atoms.ErrorAtom(atoms.ErrorCategory.TYPE_ERROR, msg))

        iterator = itertools.chain(final_arguments, final_keywords.values())
        invalid = errors or any(atoms.is_unknown(atom) for atom in iterator)

        if not invalid and isinstance(function, atoms.BuiltinFunctionAtom):
            result = function.function(*final_arguments, **final_keywords)
        else:
            result = fields.returns if fields.returns is not None else atoms.UnknownAtom()

        return atoms.union((result, *errors))


class MethodImpl(TypeImpl):
    @define('__call__')
    def call(
        self,
        method: atoms.MethodAtom,
        *arguments: atoms.Atom,
        **keywords: atoms.Atom,
    ) -> atoms.Atom:
        fields = method.get_fields()

        arguments = (fields.instance, *arguments)
        return self.atomizer.call(fields.function, arguments, keywords)
