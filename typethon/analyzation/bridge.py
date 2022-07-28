import builtins
import typing
import inspect
from types import EllipsisType, FunctionType, NoneType, UnionType

from . import types
from ..ast import ParameterKind

LiteralT = typing.Union[
    bool, None, EllipsisType, int, float, complex, str, typing.Tuple['LiteralT', ...]
]

TYPE_INSTANCES: typing.Dict[typing.Type[types.Type], types.Type] = {
    types.TypeInstance: types.TypeInstance(flags=types.TypeFlags.TYPE),
    types.ObjectType: types.ObjectType(flags=types.TypeFlags.TYPE),
    types.BoolType: types.BoolType(flags=types.TypeFlags.TYPE),
    types.NoneType: types.NoneType(flags=types.TypeFlags.TYPE),
    types.EllipsisType: types.EllipsisType(flags=types.TypeFlags.TYPE),
    types.StringType: types.StringType(flags=types.TypeFlags.TYPE),
    types.IntegerType: types.IntegerType(flags=types.TypeFlags.TYPE),
    types.FloatType: types.FloatType(flags=types.TypeFlags.TYPE),
    types.ComplexType: types.ComplexType(flags=types.TypeFlags.TYPE),
    types.SliceType: types.SliceType(flags=types.TypeFlags.TYPE),
    types.FunctionType: types.FunctionType(flags=types.TypeFlags.TYPE),
    types.MethodType: types.MethodType(flags=types.TypeFlags.TYPE),
    types.DictType: types.DictType(flags=types.TypeFlags.TYPE),
    types.SetType: types.SetType(flags=types.TypeFlags.TYPE),
    types.TupleType: types.TupleType(flags=types.TypeFlags.TYPE),
    types.ListType: types.ListType(flags=types.TypeFlags.TYPE),
}

TYPES: typing.Dict[typing.Any, types.Type] = {
    type: TYPE_INSTANCES[types.TypeInstance],
    object: TYPE_INSTANCES[types.ObjectType],
    bool: TYPE_INSTANCES[types.BoolType],
    NoneType: TYPE_INSTANCES[types.NoneType],
    EllipsisType: TYPE_INSTANCES[types.EllipsisType],
    str: TYPE_INSTANCES[types.StringType],
    int: TYPE_INSTANCES[types.IntegerType],
    float: TYPE_INSTANCES[types.FloatType],
    complex: TYPE_INSTANCES[types.ComplexType],
    slice: TYPE_INSTANCES[types.SliceType],
}


def bridge_type(type: typing.Union[typing.Optional[type], typing.Type[types.Type]]) -> types.Type:
    if isinstance(type, builtins.type) and issubclass(type, types.Type):
        return TYPE_INSTANCES[type]

    tp = TYPES.get(type)
    if tp is not None:
        return tp

    origin = typing.get_origin(type)
    args = typing.get_args(type)

    if origin is None:
        raise TypeError('origin should not be None')

    elif origin is dict:
        key = bridge_type(args[0]).to_instance()
        value = bridge_type(args[1]).to_instance()

        fields = types.DictFields(key=key, value=value)
        return types.DictType(fields=fields, flags=types.TypeFlags.TYPE)

    elif origin is set:
        value = bridge_type(args[0]).to_instance()
        return types.SetType(value=value, flags=types.TypeFlags.TYPE)

    elif origin is tuple:
        values = [bridge_type(arg).to_instance() for arg in args]
        return types.TupleType(values=values, flags=types.TypeFlags.TYPE)

    elif origin is list:
        value = bridge_type(args[0]).to_instance()
        return types.ListType(value=value, flags=types.TypeFlags.TYPE)

    elif origin in (UnionType, typing.Union):
        return types.union(bridge_type(arg) for arg in args)

    return types.UnknownType()


def bridge_function(function: FunctionType, *, method: bool = True) -> types.FunctionType:
    parameters: typing.List[types.FunctionParameter] = []

    signature = inspect.signature(function)
    for name, param in signature.parameters.items():
        if method and name == 'self':
            continue

        if param.kind is param.POSITIONAL_ONLY:
            kind = ParameterKind.POSONLY
        elif param.kind is param.POSITIONAL_OR_KEYWORD:
            kind = ParameterKind.ARG
        elif param.kind is param.VAR_POSITIONAL:
            kind = ParameterKind.VARARG
        elif param.kind is param.KEYWORD_ONLY:
            kind = ParameterKind.KWONLY
        elif param.kind is param.VAR_KEYWORD:
            kind = ParameterKind.VARKWARG
        else:
            raise TypeError(f'invalid parameter kind: {param.kind}')

        type = bridge_type(param.annotation)
        default = bridge_type(param.default.__class__)

        parameter = types.FunctionParameter(name=name, type=type, kind=kind, default=default)
        parameters.append(parameter)

    information = types.FunctionFields(
        name=function.__name__,
        parameters=parameters,
        returns=bridge_type(signature.return_annotation),
    )
    return types.FunctionType(fields=information)


# XXX: This returns Any because bools, ints, floats,
# and complexes "overlap" in an overloaded funciton
def bridge_literal(value: LiteralT) -> typing.Any:
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
    else:
        values = [bridge_literal(value) for value in value]
        return types.TupleType(values=values)
