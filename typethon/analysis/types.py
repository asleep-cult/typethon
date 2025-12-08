from __future__ import annotations

import attr
import typing

# TODO: __eq__ needs to resolve resursion issues
# that arise from cyclic references


@attr.s(kw_only=True, slots=True)
class AnalyzedType:
    name: str = attr.ib()

    def __str__(self) -> str:
        string = self.get_string()
        return f'type({string})'

    def get_string(self, *, top_level: bool = True) -> str:
        return str(self.name)

    def access_attribute(self, name: str) -> AnalyzedType:
        assert False, f'<{self} has no attribute {name}>'

    def to_instance(self, value: typing.Any = None) -> InstanceOfType:
        return InstanceOfType(name=self.name, type=self, known_value=value)


@attr.s(kw_only=True, slots=True)
class InstanceOfType(AnalyzedType):
    type: AnalyzedType = attr.ib()
    known_value: typing.Any = attr.ib()

    def __str__(self) -> str:
        return self.get_string()


UNKNOWN = AnalyzedType(name='unknown')

@attr.s(kw_only=True, slots=True)
class TypeParameter(AnalyzedType):
    owner: AnalyzedType = attr.ib(default=UNKNOWN, eq=False)  # False because of recursion
    constraint: typing.Optional[AnalyzedType] = attr.ib(default=None)

    def get_string(self, *, top_level: bool = True) -> str:
        if top_level:
            owner = self.owner.get_string(top_level=False)
            name = f'{self.name}@{owner}'
        else:
            name = self.name

        if self.constraint is not None:
            return f'|{name}: {self.constraint}|'

        return f'|{name}|'


@attr.s(kw_only=True, slots=True)
class PolymorphicType(AnalyzedType):
    initial_type: typing.Optional[PolymorphicType] = attr.ib(default=None)
    parameters: typing.List[AnalyzedType] = attr.ib(factory=list)

    def get_string(self, *, top_level: bool = True) -> str:
        parameters = ', '.join(
            parameter.get_string(top_level=False) for parameter in self.parameters
        )
        return f'{self.name}({parameters})'

    def get_initial_type(self) -> PolymorphicType:
        return self.initial_type if self.initial_type is not None else self

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
        initial_type = self.get_initial_type()
        return PolymorphicType(initial_type=initial_type, name=self.name, parameters=parameters)


@attr.s(kw_only=True, slots=True)
class FunctionType(PolymorphicType):
    propagated: bool = attr.ib()
    # PolymorphicType fields must be filled regardless of propagation
    fn_parameters: typing.Dict[str, AnalyzedType] = attr.ib(factory=dict)
    fn_returns: AnalyzedType = attr.ib(default=UNKNOWN)

    def get_string(self, *, top_level: bool = True) -> str:
        strings: typing.List[str] = []

        for name, type in self.fn_parameters.items():
            string = type.get_string(top_level=False)
            strings.append(f'{name}: {string}')

        parameters = ', '.join(strings)
        returns = self.fn_returns.get_string(top_level=False)
        return f'({parameters}) -> {returns}'

    def complete_propagation(self) -> None:
        self.propagated = True


@attr.s(kw_only=True, slots=True)
class ClassType(PolymorphicType):
    propagated: bool = attr.ib()
    cls_attributes: typing.Dict[str, AnalyzedType] = attr.ib(factory=dict)
    cls_functions: typing.Dict[str, FunctionType] = attr.ib(factory=dict)

    def complete_propagation(self) -> None:
        self.propagated = True


BOOL = AnalyzedType(name='bool')
INT = AnalyzedType(name='bool')
FLOAT = AnalyzedType(name='float')
COMPLEX = AnalyzedType(name='complex')
STRING = AnalyzedType(name='complex')
LIST = PolymorphicType(name='list', parameters=[TypeParameter(name='T')])
DICT = PolymorphicType(name='dict', parameters=[TypeParameter(name='K'), TypeParameter(name='V')])
SET = PolymorphicType(name='set', parameters=[TypeParameter(name='T')])
# TODO: Tuple(*|K|), Dict(|K: Hashable|, |V|)
