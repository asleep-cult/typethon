from __future__ import annotations

import attr
import typing


@attr.s(kw_only=True, slots=True)
class AnalyzedType:
    name: str = attr.ib()

    def __str__(self) -> str:
        return f'{self.name}'

    def access_attribute(self, name: str) -> AnalyzedType:
        assert False, f'<{self} has no attribute {name}>'


UNKNOWN = AnalyzedType(name='unknown')

@attr.s(kw_only=True, slots=True)
class TypeParameter(AnalyzedType):
    owner: AnalyzedType = attr.ib(default=UNKNOWN)
    constraint: typing.Optional[AnalyzedType] = attr.ib(default=None)

    def __str__(self) -> str:
        return f'|{self.name}: {self.constraint}|'


@attr.s(kw_only=True, slots=True)
class PolymorphicType(AnalyzedType):
    parameters: typing.List[AnalyzedType] = attr.ib(factory=list)

    def __str__(self) -> str:
        parameters = ', '.join(repr(parameter) for parameter in self.parameters)
        return f'{self.name}({parameters})'

    def is_polymorphic(self) -> bool:
        return any(self.uninitialized_parameters())

    def uninitialized_parameters(self) -> typing.Generator[TypeParameter]:
        for parameter in self.parameters:
            match parameter:
                case TypeParameter():
                    yield parameter
                case PolymorphicType():
                    # This should always be nothing theoretically
                    # So this function is useless
                    yield from parameter.uninitialized_parameters()

    def with_parameters(self, parameters: typing.List[AnalyzedType]) -> PolymorphicType:
        return PolymorphicType(name=self.name, parameters=parameters)


@attr.s(kw_only=True, slots=True)
class FunctionType(PolymorphicType):
    propagated: bool = attr.ib()
    # PolymorphicType fields must be filled regardless of propagation
    fn_parameters: typing.Dict[str, AnalyzedType] = attr.ib(factory=dict)
    fn_returns: AnalyzedType = attr.ib(default=UNKNOWN)

    def complete_propagation(self) -> None:
        self.propagated = True


@attr.s(kw_only=True, slots=True)
class ClassType(PolymorphicType):
    propagated: bool = attr.ib()
    cls_attributes: typing.Dict[str, AnalyzedType] = attr.ib(factory=dict)
    cls_functions: typing.Dict[str, FunctionType] = attr.ib(factory=dict)

    def complete_propagation(self) -> None:
        self.propagated = True


@attr.s(kw_only=True, slots=True)
class IntegerConstantType(AnalyzedType):
    value: int = attr.ib()


@attr.s(kw_only=True, slots=True)
class FloatConstantType(AnalyzedType):
    value: float = attr.ib()


@attr.s(kw_only=True, slots=True)
class ComplexConstantType(AnalyzedType):
    value: complex = attr.ib()


@attr.s(kw_only=True, slots=True)
class StringConstantType(AnalyzedType):
    value: str = attr.ib()


LIST = PolymorphicType(name='list', parameters=[TypeParameter(name='T')])
DICT = PolymorphicType(name='dict', parameters=[TypeParameter(name='K'), TypeParameter(name='V')])
SET = PolymorphicType(name='set', parameters=[TypeParameter(name='T')])
# TODO: Tuple(*|K|), Dict(|K: Hashable|, |V|)
