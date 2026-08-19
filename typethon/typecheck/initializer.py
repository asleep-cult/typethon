import attr

from .. import asg
from . import typeinfo, types


@attr.s(kw_only=True, slots=True)
class InitializationStore:
    adts: dict[asg.DefinitionId, typeinfo.AdtInfo] = attr.ib(factory=dict)
    generics: dict[asg.DefinitionId, typeinfo.GenericsInfo] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class TypeInitializer:
    asg_ctx: asg.AsgContext = attr.ib()
    store: InitializationStore = attr.ib()

    def lower_type_path_segment(
        self,
        def_id: asg.DefinitionId,
        segment: asg.PathSegment,
    ) -> types.Type:
        # Asg lowering only creates paths for type annotations.
        # The paths are still structured to allow them to represent segments
        # in code (i.e local definitions and functions can be a segment result.)
        # Asg lowering cannot lower paths in code because there is ambiguity
        # in something like Type1.AssociatedType(Type2).function()
        # where it would be impossible to determine if AssociatedType is a function
        # without the type checker.
        # I can consider adding a path promotion phase before type checking to
        # make things easier. In which case the flow would be:
        #   ast -> asg lowering -> type initialization -> path promotion -> type checking
        arguments: list[types.Type] = []
        for argument in segment.arguments:
            arguments.append(self.lower_type(def_id, argument))

        match segment.result:
            case asg.LocalDef() | asg.FunctionDef():
                assert False, "Invalid type segment"
            case asg.ClassDef():
                assert False, "Not implemented"
            case asg.SumDef() | asg.NewTypeDef():
                info = self.store.adts[segment.result.def_id]
                return types.Adt(info=info, structural=False, args=arguments)
            case _:
                if arguments:
                    assert False, "Cannot parameterize this type"

                return self.lower_type(def_id, segment.result)

    def lower_type_path(self, def_id: asg.DefinitionId, path: asg.Path) -> types.Type:
        for segment in path.segments:
            if isinstance(segment, asg.DynamicPathSegment):
                assert False, "You must implement path promotion :("

            # TODO: When can/can't args leak into the next segment?
            result = self.lower_type_path_segment(def_id, segment)

        return result

    def lower_type(self, def_id: asg.DefinitionId, type: asg.AsgType) -> types.Type:
        assert not isinstance(type, asg.AsgError)
        match type:
            case asg.Path():
                return self.lower_type_path(def_id, type)
            case asg.TypeParameterDef():
                generics = self.generics_of(def_id)
                index = generics.index_map[type.def_id]
                return types.Parameter(name=type.name, index=index)
            case asg.ListType():
                return types.List(elt=self.lower_type(def_id, type.elt))
            case asg.StructDef() | asg.TupleDef():
                assert not type.is_definition
                adt = self.store.adts[type.def_id]
                return types.Adt(info=adt, structural=True, args=[])

    def get_identity_parameters(self, def_id: asg.DefinitionId) -> list[types.Parameter]:
        generics = self.generics_of(def_id)
        if generics.parent_id is None:
            return [
                types.Parameter(name=parameter.name, index=parameter.index)
                for parameter in generics.parameters
            ]

        parameters = self.get_identity_parameters(generics.parent_id)
        for parameter in generics.parameters:
            parameters.append(types.Parameter(name=parameter.name, index=parameter.index))

        return parameters

    def type_of(self, def_id: asg.DefinitionId) -> types.Constructor:
        definition = self.asg_ctx.definition(def_id)

        match definition:
            case asg.StructDef() | asg.TupleDef() | asg.SumDef():
                adt = self.store.adts[def_id]
                type = types.Adt(
                    structural=False,
                    info=adt,
                    args=self.get_identity_parameters(def_id),
                )
            case asg.StructField() | asg.TupleElt():
                type = self.lower_type(def_id, definition.type)
            case asg.NewTypeDef():
                assert definition.type is not None
                type = self.lower_type(def_id, definition.type)
            case asg.FunctionDef():
                assert False, "Not implemented"
            case _:
                assert False, f"{definition!r}"

        return types.Constructor(type=type)

    def generics_of(self, def_id: asg.DefinitionId) -> typeinfo.GenericsInfo:
        if def_id in self.store.generics:
            return self.store.generics[def_id]

        parent_id = None
        parent_count = 0
        index_map: dict[asg.DefinitionId, int] = {}

        parent_id = self.asg_ctx.parent(def_id)
        parent = self.asg_ctx.definition(parent_id) if parent_id is not None else None
        if isinstance(parent, (asg.StructDef, asg.TupleDef, asg.SumDef, asg.ClassDef, asg.UseDef)):
            parent_id = parent.def_id
            parent_generics = self.generics_of(parent_id)
            parent_count = parent_generics.get_count()
            index_map |= parent_generics.index_map

        parameters: list[typeinfo.ParameterInfo] = []
        own_generics = self.asg_ctx.generics.get(def_id)
        if own_generics is not None:
            for i, parameter in enumerate(own_generics.parameters.values()):
                parameter_type = typeinfo.ParameterInfo(
                    def_id=parameter.def_id,
                    name=parameter.name,
                    index=parent_count + i,
                )
                parameters.append(parameter_type)
                index_map[parameter.def_id] = i

        generics_info = typeinfo.GenericsInfo(
            def_id=def_id,
            parent_id=parent_id,
            parent_count=parent_count,
            parameters=parameters,
            index_map=index_map,
        )
        self.store.generics[def_id] = generics_info
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
                case asg.NewTypeDef():
                    adt.variants.append(typeinfo.AdtVariant(def_id=type.def_id, name=type.name))

        self.store.adts[adt.def_id] = adt
        return adt

    def initialize_types(self) -> None:
        for definition in self.asg_ctx.defs.values():
            parent_id = self.asg_ctx.parent(definition.def_id)
            if parent_id is None:
                continue

            parent_def = self.asg_ctx.definition(parent_id)
            if not isinstance(parent_def, asg.SumDef):
                # Children of a sum def become variants of the adt, skip them
                match definition:
                    case asg.StructDef():
                        self.initialize_struct(definition)
                    case asg.TupleDef():
                        self.initialize_tuple(definition)
                    case asg.SumDef():
                        self.initialize_sum_type(definition)
