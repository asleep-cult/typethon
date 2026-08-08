import attr

from . import types
from .. import asg


@attr.s(kw_only=True, slots=True)
class UnificationContext:
    type_environment: dict[int, types.Type] = attr.ib(factory=dict)
    type_substitutions: dict[int, types.Type] = attr.ib(factory=dict)
    rigid_types: dict[int, types.Type] = attr.ib(factory=dict)


@attr.s(kw_only=True, slots=True)
class TypeChecker:
    type_ctx: types.TypeContext = attr.ib()
    module: asg.ModuleDef = attr.ib()

    def get_asg_definitions(self) -> dict[int, asg.AsgDefinition]:
        return self.type_ctx.asg_ctx.definitions

    def get_asg_generics(self, definition_id: asg.DefinitionId) -> asg.Generics | None:
        return self.type_ctx.asg_ctx.generics.get(definition_id)

    def get_actual_type(self, definition_id: asg.DefinitionId) -> types.Type:
        type = self.type_ctx.types[definition_id]
        if isinstance(type, types.ConstructedType):
            type = type.body

        return type

    def get_fresh_constructor(self, body_id: int) -> types.ConstructedType:
        general_constructor = self.type_ctx.general_constructors[body_id]

        parameter_map: dict[int, types.Type] = {}
        for argument in general_constructor.arguments:
            assert isinstance(argument, types.TypeParameter)
            parameter_map[argument.id] = types.TypeParameter(name=argument.name)

        fresh_constructor = types.ConstructedType(
            body=general_constructor.body,
            arguments=list(parameter_map.values()),
            parameter_map=parameter_map,
        )
        return fresh_constructor

    def get_instantiated_constructor(
        self,
        body_id: int,
        arguments: list[types.Type],
    ) -> types.ConstructedType:
        general_constructor = self.type_ctx.general_constructors[body_id]

        parameter_map: dict[int, types.Type] = {}
        for type_parameter, argument in zip(general_constructor.arguments, arguments):
            assert isinstance(type_parameter, types.TypeParameter)
            parameter_map[type_parameter.id] = argument

        instantiated_constructor = types.ConstructedType(
            body=general_constructor.body,
            arguments=arguments,
            parameter_map=parameter_map,
        )
        return instantiated_constructor

    def create_types(self) -> None:
        for definition in self.get_asg_definitions().values():
            self.create_type_for_definition(definition)

    def create_type_for_definition(self, definition: asg.AsgDefinition) -> types.Type | types.ConstructedType:
        assert not isinstance(definition, asg.ModuleDef)
        match definition:
            case asg.StructDef():
                type = types.StructType(name=definition.name, structural=definition.is_definition)
            case asg.TupleDef():
                type = types.TupleType(name=definition.name, structural=definition.is_definition)
            case asg.SumDef():
                assert False, 'Not implemented'
            case asg.AliasDef():
                assert False, 'Not implemented'
            case asg.FunctionDef():
                type = types.FunctionType(name=definition.name)
            case asg.ClassDef():
                type = types.ClassType(name=definition.name)
            case asg.UseDef():
                assert False, 'Not implemented'

        generics = self.get_asg_generics(definition.id)
        if generics is not None and generics.parameters:
            type = types.ConstructedType(body=type)
            self.type_ctx.general_constructors[type.body.id] = type

            for parameter in generics.parameters.values():
                type_parameter = types.TypeParameter(name=parameter.name)
                self.type_ctx.types[parameter.id] = type_parameter
                type.arguments.append(type_parameter)

        self.type_ctx.types[definition.id] = type
        return type

    def initialize_types(self) -> None:
        for definition in self.get_asg_definitions().values():
            self.initialize_type(definition)

    def initialize_type(self, definition: asg.AsgDefinition) -> None:
        type = self.get_actual_type(definition.id)

        match definition:
            case asg.StructDef():
                assert isinstance(type, types.StructType)
                for field_name, field_type in definition.fields.items():
                    type.fields[field_name] = self.get_type_for_definition(field_type)

            case asg.TupleDef():
                assert isinstance(type, types.TupleType)
                for elt in definition.elts:
                    type.elts.append(self.get_type_for_definition(elt))

            case asg.FunctionDef():
                assert isinstance(type, types.FunctionType)
                for parameter_name, parameter in definition.parameters.items():
                    assert parameter.type is not None
                    if parameter.type != asg.INFERRED:
                        type.parameters[parameter_name] = self.get_type_for_definition(parameter.type)
                    else:
                        type.parameters[parameter_name] = None

                if definition.returns != asg.INFERRED:
                    type.returns = self.get_type_for_definition(definition.returns)

            case asg.ClassDef():
                assert isinstance(type, types.ClassType)

                for function in definition.functions.values():
                    function_type = self.type_ctx.types[function.id]
                    assert isinstance(function_type, (types.ConstructedType, types.FunctionType))
                    type.functions[function.name] = function_type

    def get_type_for_definition(self, definition: asg.AsgType) -> types.Type | types.ConstructedType:
        type_arguments: list[types.Type] | None = None
        if isinstance(definition, asg.Path):
            for segment in definition.segments[:-1]:
                if segment.arguments:
                    assert False, 'Only the final segment can have arguments'

            final_segment = definition.segments[-1]
            path_result = final_segment.result
            if isinstance(path_result, (asg.FunctionDef, asg.LocalDef)):
                assert False, f'{path_result!r} is not a valid type'

            definition = path_result
            if final_segment.arguments:
                type_arguments = [
                    self.get_type_for_definition(argument) for argument in final_segment.arguments
                ]

        match definition:
            case asg.AsgError():
                assert False, f'{definition!r}'
            case asg.ListType():
                elt = self.get_type_for_definition(definition.elt)
                return types.ConstructedType(body=types.LIST.body, arguments=[elt])
            case _:
                result = definition
                if result.id in self.type_ctx.types:
                    type = self.type_ctx.types[result.id]
                elif isinstance(result, asg.TypeParameter):
                    assert False, f'Failed to initialize type parameter {result!r}'
                else:
                    type = self.create_type_for_definition(result)

        if type_arguments:
            if not isinstance(type, types.ConstructedType):
                assert False, 'Unconstructable type'

            type = self.get_instantiated_constructor(type.body.id, type_arguments)

        return type

    def add_to_type_environment(
        self,
        definition: asg.LocalDef,
        type: types.Type,
        context: UnificationContext,
    ) -> None:
        if isinstance(type, types.ConstructedType) and type.parameter_map is None:
            type = self.get_fresh_constructor(type.body.id)

        context.type_environment[definition.id] = type

    def check_code(self, definition: asg.ModuleDef | asg.FunctionDef) -> None:
        if definition.body is not None:
            context = UnificationContext()

            generics = self.get_asg_generics(definition.id)
            if generics is not None:
                for parameter in generics.walk_type_parameters():
                    type_parameter = self.type_ctx.types[parameter.id]
                    context.rigid_types[type_parameter.id] = types.PrimitiveType(name=parameter.name)

            if isinstance(definition, asg.FunctionDef):
                function_type = self.get_actual_type(definition.id)
                assert isinstance(function_type, types.FunctionType)

                for parameter in definition.parameters.values():
                    assert parameter.type is not None
                    assert parameter.type != asg.INFERRED

                    parameter_type = self.get_type_for_definition(parameter.type)
                    self.add_to_type_environment(parameter.definition, parameter_type, context)

            for statement in definition.body.statements:
                self.check_statement(definition, statement, context)

    def check_statement(
        self,
        definition: asg.ModuleDef | asg.FunctionDef,
        statement: asg.Statement,
        context: UnificationContext,
    ) -> None:
        match statement:
            case asg.Local():
                if statement.type is not None:
                    type = self.get_type_for_definition(statement.type)

                    if statement.value is not None:
                        value_type = self.synthesize_expression(statement.value, context)
                        if not self.unify(type, value_type, context):
                            assert False, f'Assignment type and value are incompatible {type} != {value_type}'
                else:
                    assert statement.value is not None
                    type = self.synthesize_expression(statement.value, context)

                self.add_to_type_environment(statement.local_definition, type, context)
            case asg.For():
                ...
            case asg.While():
                ...
            case asg.If():
                ...
            case asg.Assignment():
                ...
            case asg.AugAssignment():
                ...
            case asg.Return():
                if not isinstance(definition, asg.FunctionDef):
                    assert False, 'Return only valid in function'

                function_type = self.get_actual_type(definition.id)
                assert isinstance(function_type, types.FunctionType)

                if statement.value is not None:
                    type = self.synthesize_expression(statement.value, context)
                else:
                    assert False

                assert function_type.returns is not None
                if not self.unify(type, function_type.returns, context):
                    assert False, f'{type} and {function_type.returns}'
            case asg.Break():
                ...
            case asg.Continue():
                ...
            case asg.Expr():
                self.synthesize_expression(statement.expr, context)

    def get_attribute(
        self,
        type: types.Type,
        name: str,
    ) -> types.Type:
        if isinstance(type, types.ConstructedType):
            return type.apply_substitution(self.get_attribute(type.body, name))

        match type:
            case types.StructType():
                result = type.fields.get(name)
            case types.ClassType():
                result = type.functions.get(name)
            case _:
                assert False, "Not Implemented"

        if result is None:
            # Look into use blocks
            assert False, "TODO"

        return result

    def get_return_type(self, type: types.FunctionType | types.ConstructedType) -> types.Type:
        if isinstance(type, types.ConstructedType):
            assert isinstance(type.body, types.FunctionType)
            return type.apply_substitution(self.get_return_type(type.body))

        assert type.returns is not None
        return type.returns

    def synthesize_expression(
        self,
        expression: asg.Expression,
        context: UnificationContext,
    ) -> types.Type:
        """
        | BoolOp
        | BinaryOp
        | UnaryOp
        | Compare
        | Integer
        | Float
        | Complex
        | String
        | Constant
        | Attribute
        | Subscript
        | Struct
        | Tuple
        | List
        | Slice
        """
        match expression:
            case asg.CoPath():
                result = expression.path.get_result()
                match result:
                    case asg.LocalDef():
                        return context.type_environment[result.id]
                    case asg.FunctionDef():
                        return self.type_ctx.types[result.id]
                    case _:
                        return self.get_type_for_definition(result)

            case asg.Annotated():
                value = self.synthesize_expression(expression.value, context)
                type = self.get_type_for_definition(expression.type)

                if not self.unify(value, type, context):
                    assert False, ""

            case asg.Call():
                callable = self.synthesize_expression(expression.callable, context)
                if not isinstance(callable, (types.FunctionType, types.ConstructedType)):
                    assert False, "TODO: Allow non function call"

                return self.get_return_type(callable)

            case asg.Attribute():
                value = self.synthesize_expression(expression.value, context)
                result = self.get_attribute(value, expression.attr)

                if result.id in context.type_substitutions:
                    result = context.type_substitutions[result.id]

                return result

    def unify(
        self,
        type1: types.Type,
        type2: types.Type,
        context: UnificationContext,
        *,
        flipped: bool = False,
    ) -> bool:
        print(f"Unify: {type1} {type2} {context.type_substitutions}")
        if isinstance(type1, types.TypeParameter):
            type1 = type1.resolve(context.type_substitutions)

        if isinstance(type2, types.TypeParameter):
            type2 = type2.resolve(context.type_substitutions)

        if type1.id == type2.id:
            return True

        if isinstance(type1, types.TypeParameter):
            if type2.has_type_parameter(type1, context.type_substitutions):
                return False

            if type1.id not in context.rigid_types:
                context.type_substitutions[type1.id] = type2
                return True

        if isinstance(type2, types.TypeParameter) and not flipped:
            return self.unify(type2, type1, context, flipped=True)

        if isinstance(type1, types.ConstructedType) and isinstance(type2, types.ConstructedType):
            if type1.body.id != type2.body.id:
                return False

            for parameter1, parameter2 in zip(type1.arguments, type2.arguments):
                if not self.unify(parameter1, parameter2, context):
                    return False

            return True

        return False

    def check_module(self) -> None:
        self.create_types()
        self.initialize_types()

        self.check_code(self.module)
        for definition in self.get_asg_definitions().values():
            if isinstance(definition, asg.FunctionDef):
                self.check_code(definition)
