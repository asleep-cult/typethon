from __future__ import annotations

import attr
import typing

@attr.s(kw_only=True, slots=True)
class AnalyzedType:
    name: str = attr.ib()

    def access_attribute(self, name: str) -> AnalyzedType:
        assert False, f'<{self} has no attribute {name}>'


@attr.s(kw_only=True, slots=True)
class TypeParameter(AnalyzedType):
    constraint: typing.Optional[AnalyzedType] = attr.ib(default=None)


@attr.s(kw_only=True, slots=True)
class PolymorphicType(AnalyzedType):
    parameters: typing.List[AnalyzedType] = attr.ib()

    def is_polymorphic(self) -> bool:
        return any(self.uninitialized_parameters())

    def is_hollow(self) -> bool:
        # type X = |T|
        # type Y = X (is_hollow = True), type Y = X(|T|) (is_hollow = False)
        return any(child not in self.parameters for child in self.uninitialized_parameters())

    def uninitialized_parameters(self) -> typing.Generator[TypeParameter]:
        for parameter in self.parameters:
            match parameter:
                case TypeParameter():
                    yield parameter
                case PolymorphicType():
                    yield from parameter.uninitialized_parameters()

    def with_parameters(self, parameters: typing.List[AnalyzedType]) -> PolymorphicType:
        return PolymorphicType(name=self.name, parameters=parameters)


@attr.s(kw_only=True, slots=True)
class FunctionType(PolymorphicType):
    # paramaters: typing.List[...] = attr.ib()
    returns: AnalyzedType = attr.ib()


LIST = PolymorphicType(name='list', parameters=[TypeParameter(name='T')])
DICT = PolymorphicType(name='dict', parameters=[TypeParameter(name='K'), TypeParameter(name='V')])
SET = PolymorphicType(name='set', parameters=[TypeParameter(name='T')])
# TODO: Tuple(*|K|), Dict(|K: Hashable|, |V|)
