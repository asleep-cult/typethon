from __future__ import annotations

import inspect
import typing
import types

from . import atoms
from .. import ast

__all__ = ('bridge_type', 'bridge_function', 'bridge_literal')


TYPES: typing.Dict[typing.Any, atoms.Atom] = {
    type: atoms.get_type(atoms.TypeAtom),
    object: atoms.get_type(atoms.ObjectAtom),
    bool: atoms.get_type(atoms.BoolAtom),
    types.NoneType: atoms.get_type(atoms.NoneAtom),
    types.EllipsisType: atoms.get_type(atoms.EllipsisAtom),
    str: atoms.get_type(atoms.StringAtom),
    int: atoms.get_type(atoms.IntegerAtom),
    float: atoms.get_type(atoms.FloatAtom),
    complex: atoms.get_type(atoms.ComplexAtom),
    slice: atoms.get_type(atoms.SliceAtom),
}


def bridge_type(atom: typing.Union[typing.Optional[type], typing.Type[atoms.Atom]]) -> atoms.Atom:
    if isinstance(atom, type) and issubclass(atom, atoms.Atom):
        return atoms.get_type(atom)

    tp = TYPES.get(atom)
    if tp is not None:
        return tp

    origin = typing.get_origin(atom)
    args = typing.get_args(atom)

    if origin is None:
        raise TypeError('origin should not be None')

    elif origin is dict:
        key = bridge_type(args[0]).instantiate()
        value = bridge_type(args[1]).instantiate()

        fields = atoms.DictFields(key=key, value=value)
        return atoms.DictAtom(fields, flags=atoms.AtomFlags.TYPE)

    elif origin is set:
        value = bridge_type(args[0]).instantiate()
        return atoms.SetAtom(value, flags=atoms.AtomFlags.TYPE)

    elif origin is tuple:
        values = [bridge_type(arg).instantiate() for arg in args]
        return atoms.TupleAtom(values, flags=atoms.AtomFlags.TYPE)

    elif origin is list:
        value = bridge_type(args[0]).instantiate()
        return atoms.ListAtom(value, flags=atoms.AtomFlags.TYPE)

    elif origin in (types.UnionType, typing.Union):
        return atoms.union(bridge_type(arg) for arg in args)

    return atoms.UnknownAtom()


def bridge_function(function: types.FunctionType, *, method: bool = True) -> atoms.FunctionAtom:
    parameters: typing.List[atoms.FunctionParameter] = []

    signature = inspect.signature(function)
    for name, param in signature.parameters.items():
        if method and name == 'self':
            continue

        if param.kind is param.POSITIONAL_ONLY:
            kind = ast.ParameterKind.POSONLY
        elif param.kind is param.POSITIONAL_OR_KEYWORD:
            kind = ast.ParameterKind.ARG
        elif param.kind is param.VAR_POSITIONAL:
            kind = ast.ParameterKind.VARARG
        elif param.kind is param.KEYWORD_ONLY:
            kind = ast.ParameterKind.KWONLY
        elif param.kind is param.VAR_KEYWORD:
            kind = ast.ParameterKind.VARKWARG
        else:
            raise TypeError(f'invalid parameter kind: {param.kind}')

        type = bridge_type(param.annotation)

        if param.default is not param.empty:
            default = bridge_type(param.default.__class__)
        else:
            default = None

        parameter = atoms.FunctionParameter(name=name, type=type, kind=kind, default=default)
        parameters.append(parameter)

    fields = atoms.FunctionFields(
        name=function.__name__,
        parameters=parameters,
        returns=bridge_type(signature.return_annotation),
    )
    return atoms.FunctionAtom(fields)


def bridge_literal(value: LiteralT) -> atoms.Atom:
    if isinstance(value, bool):
        return atoms.BoolAtom(value)
    elif value is None:
        return atoms.NoneAtom()
    elif isinstance(value, types.EllipsisType):
        return atoms.EllipsisAtom()
    elif isinstance(value, str):
        return atoms.StringAtom(value)
    elif isinstance(value, int):
        return atoms.IntegerAtom(value)
    elif isinstance(value, float):
        return atoms.FloatAtom(value)
    elif isinstance(value, complex):
        return atoms.ComplexAtom(value)
    else:
        return atoms.TupleAtom([bridge_literal(value) for value in value])


LiteralT = typing.Union[
    bool,
    None,
    types.EllipsisType,
    int,
    float,
    complex,
    str,
    typing.Tuple['LiteralT', ...],
]
