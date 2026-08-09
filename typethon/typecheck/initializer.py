import attr

from . import typeinfo
from . import types
from .. import asg


@attr.s(kw_only=True, slots=True)
class InitializationStore:
    adts: dict[asg.DefinitionId, typeinfo.AdtInfo] = attr.ib(factory=dict)
    generics: dict[asg.DefinitionId, typeinfo.GenericsInfo] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class TypeInitializer:
    asg_ctx: asg.AsgContext = attr.ib()
    store: InitializationStore = attr.ib()

    def lower_type(self, type: asg.AsgType) -> types.Type:
        ...

    def get_identity_parameters(self, def_id: asg.DefinitionId) -> list[types.Parameter]:
        if def_id not in self.store.generics:
            return []

        return self.store.generics[def_id].parameters

    def type_of(self, def_id: asg.DefinitionId) -> types.Constructor:
        definition = self.asg_ctx.definitions[def_id]

        match definition:
            case asg.StructDef() | asg.TupleDef() | asg.SumDef():
                adt = self.store.adts[def_id]
                type = types.Adt(info=adt, args=self.get_identity_parameters(def_id))
            case asg.StructField() | asg.TupleElt():
                type = self.lower_type(definition.type)
            case asg.AliasDef():
                type = self.lower_type(definition.type)
            case asg.FunctionDef():
                assert False, 'Not implemented'
            case _:
                assert False, f"{definition!r}"

        return types.Constructor(type=type)

    def initialize_generics(self, generics: asg.Generics) -> typeinfo.GenericsInfo:
        if generics.def_id in self.asg_ctx.generics:
            return self.asg_ctx.generics[generics.def_id]

        parent_id = None
        parent_count = 0
        if generics.parent is not None:
            parent_generics = self.initialize_generics(generics.parent)
            parent_id = parent_generics.def_id
            parent_count = parent_generics.get_count()

        parameters: list[types.Parameter] = []
        index_map: dict[asg.DefinitionId, int] = {}
        for i, parameter in enumerate(generics.parameters.values()):
            parameter_type = types.Parameter(
                name=parameter.name,
                index=parent_count + i,
            )
            parameters.append(parameter_type)
            index_map[parameter.def_id] = i

        generics_info = typeinfo.GenericsInfo(
            def_id=generics.def_id,
            parent_id=parent_id,
            parent_count=parent_count,
            parameters=parameters,
            index_map=index_map,
        )
        self.store.generics[generics.def_id] = generics_info
        return generics_info

    def initialize_struct_variant(self, struct_def: asg.StructDef) -> typeinfo.AdtVariant:
        variant = typeinfo.AdtVariant(def_id=struct_def.def_id, name=struct_def.name)
        for field in struct_def.fields.values():
            variant.fields.append(typeinfo.VariantField(def_id=field.def_id, name=field.name))

        return variant

    def initialize_tuple_variant(self, tuple_def: asg.TupleDef) -> typeinfo.AdtVariant:
        variant = typeinfo.AdtVariant(def_id=tuple_def.def_id, name=tuple_def.name)
        for elt in tuple_def.elts:
            variant.fields.append(typeinfo.VariantField(def_id=elt.def_id, name=None))

        return variant

    def initialize_struct(self, struct_def: asg.StructDef) -> typeinfo.AdtInfo:
        variant = self.initialize_struct_variant(struct_def)
        adt = typeinfo.AdtInfo(def_id=struct_def.def_id, variants=[variant])

        self.store.adts[adt.def_id] = adt
        return adt

    def initialize_tuple(self, tuple_def: asg.TupleDef) -> typeinfo.AdtInfo:
        variant = self.initialize_tuple_variant(tuple_def)
        adt = typeinfo.AdtInfo(def_id=tuple_def.def_id, variants=[variant])

        self.store.adts[adt.def_id] = adt
        return adt

    def initialize_sum_type(self, sum_def: asg.SumDef) -> typeinfo.AdtInfo:
        adt = typeinfo.AdtInfo(def_id=sum_def.def_id)

        for type in sum_def.types.values():
            match type:
                case asg.StructDef():
                    adt.variants.append(self.initialize_struct_variant(type))
                case asg.TupleDef():
                    adt.variants.append(self.initialize_tuple_variant(type))
                case asg.AliasDef():
                    adt.variants.append(typeinfo.AdtVariant(def_id=type.def_id, name=type.name))

        self.store.adts[adt.def_id] = adt
        return adt

    def initialize_types(self) -> None:
        for generics in self.asg_ctx.generics.values():
            self.initialize_generics(generics)

        for definition in self.asg_ctx.definitions.values():
            match definition:
                case asg.StructDef():
                    self.initialize_struct(definition)
                case asg.TupleDef():
                    self.initialize_tuple(definition)
                case asg.SumDef():
                    self.initialize_sum_type(definition)
