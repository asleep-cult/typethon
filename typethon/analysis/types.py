from __future__ import annotations

import attr
import typing

# TODO: __eq__ needs to resolve resursion issues
# that arise from cyclic references


@attr.s(kw_only=True, slots=True, hash=True)
class AnalyzedType:
    name: str = attr.ib()
    trait_implementations: typing.List[TypeTrait] = attr.ib(factory=list, repr=False)

    def __str__(self) -> str:
        string = self.get_string()
        return f'type({string})'

    def is_compatible_with(self, type: AnalyzedType) -> bool:
        if self is UNKNOWN or type is UNKNOWN:
            return False

        if self is ANY or type is ANY:
            return True

        if isinstance(type, TypeTrait):
            return self.get_trait_implementation(type) is not None

        return self is type

    def add_trait_implementation(self, trait: TypeTrait) -> None:
        if trait.has_uninitialized_parameters():
            raise ValueError(f'{trait} has uninitialized parameters')

        self.trait_implementations.append(trait)

    def get_trait_implementation(self, trait: TypeTrait) -> typing.Optional[TypeTrait]:
        if trait.has_uninitialized_parameters():
            raise ValueError(f'{trait} has uninitialized parameters')

        for implementation in self.trait_implementations:
            if implementation.is_compatible_with(trait):
                return implementation

    def get_string(self, *, top_level: bool = True) -> str:
        return str(self.name)

    def access_attribute(self, name: str) -> AnalyzedType:
        assert False, f'<{self} has no attribute {name}>'

    def to_instance(self, value: typing.Any = None) -> InstanceOfType:
        return InstanceOfType(type=self, known_value=value)

    def bind_with_parameters(self, type: PolymorphicType) -> AnalyzedType:
        # Called when a PolymorphicType wants us to replace our references to
        # their TypeParameters with its GivenTypeParameters
        return self


UNKNOWN = AnalyzedType(name='unknown')  # Internal type compatible with nothing
ANY = AnalyzedType(name='any')  # Internal type compatible with exerything


@attr.s(kw_only=True, slots=True)
class UnionType(AnalyzedType):
    # XXX: This will probably be a compiler only type
    types: typing.List[AnalyzedType] = attr.ib(factory=list)


@attr.s(kw_only=True, slots=True)
class InstanceOfType:
    type: AnalyzedType = attr.ib()
    known_value: typing.Any = attr.ib()


@attr.s(kw_only=True, slots=True, hash=True)
class TypeParameter(AnalyzedType):
    owner: AnalyzedType = attr.ib(default=UNKNOWN, eq=False, repr=False)
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

    def bind_with_parameters(self, type: PolymorphicType) -> AnalyzedType:
        for parameter, given_type in type.map_given_parameters():
            if parameter is self:
                return given_type

        return self


@attr.s(kw_only=True, slots=True)
class PolymorphicType(AnalyzedType):
    initial_type: typing.Optional[typing.Self] = attr.ib(default=None, repr=False)
    parameters: typing.List[TypeParameter] = attr.ib(factory=list)
    given_parameters: typing.List[AnalyzedType] = attr.ib(factory=list)

    def map_given_parameters(self) -> typing.Iterator[typing.Tuple[TypeParameter, AnalyzedType]]:
        return zip(self.parameters, self.given_parameters)

    def add_trait_implementation(self, trait: TypeTrait) -> None:
        for parameter in trait.uninitialized_parameters():
            # TODO: Do we need to re-map given_parameters to parameters???
            if (
                parameter not in self.parameters
                and parameter not in self.given_parameters
            ):
                raise ValueError(f'{trait} has foreign uninitialized parameter {parameter}')

        initial_type = self.get_initial_type()
        initial_type.trait_implementations.append(trait)

    def get_trait_implementation(self, trait: TypeTrait) -> typing.Optional[TypeTrait]:
        for parameter in trait.uninitialized_parameters():
            if (
                parameter not in self.parameters
                and parameter not in self.given_parameters
            ):
                raise ValueError(f'{trait} has foreign uninitialized parameter {parameter}')

        initial_type = self.get_initial_type()
        for implementation in initial_type.trait_implementations:
            if implementation.get_initial_type() is not trait.get_initial_type():
                continue

            bound_trait = implementation.bind_with_parameters(self)
            if bound_trait.is_compatible_with(trait):
                return bound_trait

    def is_compatible_with(self, type: AnalyzedType) -> bool:
        if type is UNKNOWN:
            return False

        if type is ANY:
            return True

        if isinstance(type, TypeTrait):
            return self.get_trait_implementation(type) is not None

        if not isinstance(type, PolymorphicType):
            return False

        if self.get_initial_type() is not type.get_initial_type():
            return False

        if len(self.given_parameters) != len(type.given_parameters):
            return False

        parameters = zip(self.given_parameters, type.given_parameters)
        for parameter1, parameter2 in parameters:
            if not parameter1.is_compatible_with(parameter2):
                return False

        return True

    def get_string(self, *, top_level: bool = True) -> str:
        if not self.given_parameters:
            return self.name

        parameters = ', '.join(
            parameter.get_string(top_level=False) for parameter in self.given_parameters
        )
        return f'{self.name}({parameters})'

    def get_initial_type(self) -> typing.Self:
        return self.initial_type if self.initial_type is not None else self

    def has_uninitialized_parameters(self) -> bool:
        return any(self.uninitialized_parameters())

    def uninitialized_parameters(self) -> typing.Generator[TypeParameter]:
        if not self.given_parameters:
            yield from self.parameters
        else:
            for parameter in self.given_parameters:
                if isinstance(parameter, TypeParameter):
                    yield parameter

    def with_parameters(self, parameters: typing.List[AnalyzedType]) -> typing.Self:
        initial_type = self.get_initial_type()
        if len(parameters) != len(initial_type.parameters):
            raise ValueError(
                'Expected {0} parameter(s), reveived {1}'.format(
                    len(initial_type.parameters), len(parameters)
                )
            )

        for parameter in parameters:
            if (
                isinstance(parameter, PolymorphicType)
                and parameter.has_uninitialized_parameters()
            ):
                raise ValueError(f'Received an uninitialized parameter in {parameters}')

        cls = type(self)
        return cls(
            initial_type=initial_type,
            name=self.name,
            parameters=self.parameters,
            given_parameters=parameters,
        )

    def bind_with_parameters(self, type: PolymorphicType) -> typing.Self:
        parameters = [parameter.bind_with_parameters(type) for parameter in self.given_parameters]
        return self.with_parameters(parameters)


@attr.s(kw_only=True, slots=True)
class SelfType(AnalyzedType):
    name: str = attr.ib(default='Self', init=False)
    owner: AnalyzedType = attr.ib(default=UNKNOWN, repr=str)


@attr.s(kw_only=True, slots=True)
class TypeTrait(PolymorphicType):
    tr_functions: typing.Dict[str, FunctionType] = attr.ib(factory=dict)

    def is_compatible_with(self, type: AnalyzedType) -> bool:
        if type is UNKNOWN:
            return False

        if type is ANY:
            return True

        if not isinstance(type, TypeTrait):
            return type.get_trait_implementation(self) is not None

        if self.get_initial_type() is not type.get_initial_type():
            return False

        if len(self.given_parameters) != len(type.given_parameters):
            return False

        parameters = zip(self.given_parameters, type.given_parameters)
        for parameter1, parameter2 in parameters:
            if not parameter1.is_compatible_with(parameter2):
                return False

        return True

    def get_function(self, name: str) -> FunctionType:
        if name not in self.tr_functions:
            raise ValueError(f'{self} has no function named {name}')

        function = self.tr_functions[name]
        return function.with_owner(self)

    def with_parameters(self, parameters: typing.List[AnalyzedType]) -> TypeTrait:
        trait = super().with_parameters(parameters)
        trait.tr_functions = self.tr_functions
        return trait


@attr.s(kw_only=True, slots=True)
class FunctionParameter:
    name: str = attr.ib()
    type: AnalyzedType = attr.ib()
    # TODO: default
    # kw_only, etc.


@attr.s(kw_only=True, slots=True)
class FunctionType(PolymorphicType):
    propagated: bool = attr.ib(default=True)
    # PolymorphicType fields must be filled regardless of propagation
    owner: typing.Optional[PolymorphicType] = attr.ib(default=None)
    # The following attributes are static after propagation and they can
    # exist on multiple FunctionTypes (i.e. with_owner, with_parameters)
    # Possibly with the exception of fn_self? which needs to be fixed
    fn_self: typing.Optional[SelfType] = attr.ib(default=None)
    fn_parameters: typing.Dict[str, FunctionParameter] = attr.ib(factory=dict)
    fn_returns: AnalyzedType = attr.ib(default=UNKNOWN)

    def get_string(self, *, top_level: bool = True) -> str:
        strings: typing.List[str] = []

        for parameter in self.fn_parameters.values():
            string = parameter.type.get_string(top_level=False)
            strings.append(f'{parameter.name}: {string}')

        parameters = ', '.join(strings)
        returns = self.fn_returns.get_string(top_level=False)
        return f'({parameters}) -> {returns}'

    def complete_propagation(self) -> None:
        self.propagated = True

    def check_owner_compatibility(self, owner: PolymorphicType) -> None:
        # TODO: Figure out if fn_self and owner can be combined
        if self.owner is not None:
            if not self.owner.is_compatible_with(owner):
                raise ValueError(f'Incompatible function owners: {owner}, {self.owner}')

    def get_parameter_types(
        self, owner: typing.Optional[PolymorphicType] = None,
    ) -> typing.List[AnalyzedType]:
        return [self.get_parameter_type(name, owner) for name in self.fn_parameters]

    def get_parameter_type(
        self,
        name: str,
        owner: typing.Optional[PolymorphicType] = None,
    ) -> AnalyzedType:
        if owner is not None:
            self.check_owner_compatibility(owner)
        else:
            owner = self.owner

        if name not in self.fn_parameters:
            raise ValueError(f'{self} has no parameter named {name}')

        parameter_type = self.fn_parameters[name].type
        type = parameter_type.bind_with_parameters(self)

        if owner is not None:
            type = type.bind_with_parameters(owner)

        return type

    def get_return_type(
        self,
        owner: typing.Optional[PolymorphicType] = None,
    ) -> AnalyzedType:
        if owner is not None:
            self.check_owner_compatibility(owner)
        else:
            owner = self.owner

        type = self.fn_returns.bind_with_parameters(self)
        if owner is not None:
            type = type.bind_with_parameters(owner)

        return type

    def with_parameters(self, parameters: typing.List[AnalyzedType]) -> FunctionType:
        function = super().with_parameters(parameters)

        function.fn_self = self.fn_self
        function.fn_parameters = self.fn_parameters
        function.fn_returns = self.fn_returns

        return function

    def with_owner(self, owner: PolymorphicType) -> FunctionType:
        self.check_owner_compatibility(owner)

        return FunctionType(
            name=self.name,
            initial_type=self.initial_type,
            parameters=self.parameters,
            propagated=self.propagated,
            owner=owner,
            fn_self=self.fn_self,
            fn_parameters=self.fn_parameters,
            fn_returns=self.fn_returns,
        )


@attr.s(kw_only=True, slots=True)
class ClassAttribute:
    name: str = attr.ib()
    type: AnalyzedType = attr.ib()
    # TODO: default?, kw_only?


@attr.s(kw_only=True, slots=True)
class ClassType(PolymorphicType):
    propagated: bool = attr.ib(default=True)
    # The following attributes are static after propagation and they can
    # exist on multiple ClassTypes (i.e. with_parameters)
    cls_attributes: typing.Dict[str, ClassAttribute] = attr.ib(factory=dict)
    cls_functions: typing.Dict[str, FunctionType] = attr.ib(factory=dict)

    def complete_propagation(self) -> None:
        self.propagated = True

    def get_attribute(self, name: str) -> AnalyzedType:
        if name not in self.cls_attributes:
            raise ValueError(f'{self} has no attribute named {name}')

        type = self.cls_attributes[name].type
        return type.bind_with_parameters(self)

    def get_function(self, name: str) -> FunctionType:
        if name not in self.cls_functions:
            raise ValueError(f'{self} has not attribute named {name}')

        function = self.cls_functions[name]
        return function.with_owner(self)

    def with_parameters(self, parameters: typing.List[AnalyzedType]) -> ClassType:
        cls = super().with_parameters(parameters)

        cls.cls_attributes = self.cls_attributes
        cls.cls_functions = self.cls_functions
        
        return cls


AnalysisUnit = typing.Union[
    AnalyzedType,
    InstanceOfType,
]
