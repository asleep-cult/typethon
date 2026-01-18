import attr
import typing
import enum

from . import types
from .context import AnalysisContext, AnalysisFlags, TypeInstance, Symbol
from ..syntax.typethon import ast


class TypeAnalyzer:
    def __init__(self, module: ast.ModuleNode) -> None:
        self.module = module
        self.ctx = AnalysisContext()

    def initialize_types(
        self,
        ctx: AnalysisContext,
        statements: typing.List[ast.StatementNode],
    ) -> None:
        context_index = 0
        for statement in statements:
            context_index += 1

            match statement:
                case ast.FunctionDefNode():
                    function_ctx = ctx.create_child_context(
                        context_index,
                        flags=AnalysisFlags.NONE,
                        returnable_type=types.SingletonType.UNIT,
                    )
                    function_type = types.FunctionType(name=statement.name)

                    for parameter in statement.parameters:
                        self.initialize_type_parameters(function_ctx, parameter.annotation)

                    self.initialize_type_parameters(function_ctx, statement.returns)

                    if function_ctx.type_parameters:
                        function_type = types.PolymorphicType(
                            type=function_type,
                            parameters=list(function_ctx.type_parameters.values())
                        )

                    if statement.body is not None:
                        self.initialize_types(function_ctx, statement.body)

                    ctx.add_symbol(statement.name, function_type)

                case ast.ClassDefNode():
                    class_ctx = ctx.create_child_context(
                        context_index,
                        flags=AnalysisFlags.NONE,
                        returnable_type=types.SingletonType.UNIT,
                    )
                    type_class = types.TypeClass(name=statement.name)

                    for parameter in statement.parameters:
                        self.initialize_type_parameters(class_ctx, parameter)

                    if class_ctx.type_parameters:
                        type_class = types.PolymorphicType(
                            type=type_class,
                            parameters=list(class_ctx.type_parameters.values()),
                        )

                    self.initialize_types(class_ctx, statement.body)
                    ctx.add_symbol(statement.name, type_class)

                case ast.TypeDeclarationNode():
                    if (
                        isinstance(statement.type, ast.TupleTypeNode)
                        and not statement.type.elts
                    ):
                        ctx.add_symbol(statement.name, types.SingletonType.UNIT)
                        continue
 
                    child_ctx = ctx.create_child_context(
                        context_index,
                        flags=AnalysisFlags.NONE,
                        returnable_type=types.SingletonType.UNIT,
                    )

                    if isinstance(statement.type, ast.StructTypeNode):
                        type = types.StructType(name=statement.name)
                    elif isinstance(statement.type, ast.TupleTypeNode):
                        type = types.TupleType(name=statement.name)
                    else:
                        type = types.TypeAlias(name=statement.name)
 
                    self.initialize_type_parameters(child_ctx, statement.type)

                    if child_ctx.type_parameters:
                        type = types.PolymorphicType(
                            type=type,
                            parameters=list(child_ctx.type_parameters.values()),
                        )

                    ctx.add_symbol(statement.name, type)

                case ast.UseNode() | ast.UseForNode():
                    use_ctx = ctx.create_child_context(
                        context_index,
                        flags=AnalysisFlags.NONE,
                        returnable_type=types.SingletonType.UNIT,
                    )

                    self.initialize_type_parameters(use_ctx, statement.type)

                    if isinstance(statement, ast.UseForNode):
                        self.initialize_type_parameters(use_ctx, statement.type_class)

                    self.initialize_types(use_ctx, statement.body)

                case ast.ForNode() | ast.WhileNode() | ast.IfNode():
                    child_ctx = ctx.create_child_context(
                        context_index,
                        flags=ctx.flags,
                        returnable_type=ctx.returnable_type,
                    )
                    self.initialize_types(child_ctx, statement.body)

                    if isinstance(statement, ast.IfNode):
                        context_index += 1
                        else_ctx = ctx.create_child_context(
                            context_index,
                            flags=ctx.flags,
                            returnable_type=ctx.returnable_type,
                        )
                        self.initialize_types(else_ctx, statement.else_body)

    def initialize_type_parameters(
        self,
        ctx: AnalysisContext,
        type_expression: ast.TypeExpressionNode,
    ) -> None:
        match type_expression:
            case ast.TypeParameterNode():
                existing_parameter = ctx.get_type_parameter(type_expression.name)
                if existing_parameter is None:
                    ctx.add_type_parameter(types.TypeParameter(name=type_expression.name))

            case ast.TypeCallNode():
                self.initialize_type_parameters(ctx, type_expression.type)
                for argument in type_expression.args:
                    self.initialize_type_parameters(ctx, argument)

            case ast.TypeAttributeNode():
                self.initialize_type_parameters(ctx, type_expression.value)

            case ast.ListTypeNode():
                self.initialize_type_parameters(ctx, type_expression.elt)

            case ast.StructTypeNode():
                for field in type_expression.fields:
                    self.initialize_type_parameters(ctx, field.type)

            case ast.TupleTypeNode():
                for elt in type_expression.elts:
                    self.initialize_type_parameters(ctx, elt)

    def propagate_types(self, ctx: AnalysisContext, statements: typing.List[ast.StatementNode]) -> None:
        context_index = 0
        for statement in statements:
            context_index += 1

            match statement:
                case ast.FunctionDefNode():
                    function_type = ctx.get_symbol(statement.name)
                    if isinstance(function_type, types.PolymorphicType):
                        function_type = function_type.type

                    assert isinstance(function_type, types.FunctionType)
                    function_context = ctx.get_child_context(context_index)

                    for parameter in statement.parameters:
                        parameter_type = self.evaluate_concrete_type_expression(
                            function_context,
                            parameter.annotation,
                        )
                        function_type.parameters[parameter.name] = types.FunctionParameter(
                            name=parameter.name,
                            type=parameter_type,
                        )

                    function_type.returns = self.evaluate_concrete_type_expression(
                        function_context,
                        statement.returns,
                    )

                case ast.ClassDefNode():
                    type_class = ctx.get_symbol(statement.name)
                    if isinstance(type_class, types.PolymorphicType):
                        type_class = type_class.type

                    assert isinstance(type_class, types.TypeClass)
                    class_ctx = ctx.get_child_context(context_index)

                    for inner_statement in statement.body:
                        if not isinstance(inner_statement, ast.FunctionDefNode):
                            assert False, 'Only functions are allowed in class'

                        function_type = class_ctx.get_symbol(inner_statement.name)
                        assert isinstance(function_type, types.FunctionType)

                        type_class.functions[function_type.name] = function_type

                    self.propagate_types(class_ctx, statement.body)

                case ast.TypeDeclarationNode():
                    if isinstance(statement.type, ast.StructTypeNode):
                        struct_type = ctx.get_symbol(statement.name)
                        if isinstance(struct_type, types.PolymorphicType):
                            struct_type = struct_type.type

                        assert isinstance(struct_type, types.StructType)
                        struct_ctx = ctx.get_child_context(context_index)

                        for field in statement.type.fields:
                            field_type = self.evaluate_concrete_type_expression(
                                struct_ctx,
                                field.type,
                            )
                            struct_type.fields[field.name] = types.StructField(name=field.name, type=field_type)

                    elif isinstance(statement.type, ast.TupleTypeNode):
                        if not statement.type.elts:
                            continue

                        tuple_type = ctx.get_symbol(statement.name)
                        if isinstance(tuple_type, types.PolymorphicType):
                            tuple_type = tuple_type.type

                        assert isinstance(tuple_type, types.TupleType)
                        tuple_ctx = ctx.get_child_context(context_index)

                        for elt in statement.type.elts:
                            elt_type = self.evaluate_concrete_type_expression(tuple_ctx, elt)
                            tuple_type.fields.append(elt_type)

                    else:
                        alias_type = ctx.get_symbol(statement.name)
                        if isinstance(alias_type, types.PolymorphicType):
                            alias_type = alias_type.type

                        assert isinstance(alias_type, types.TypeAlias)
                        alias_ctx = ctx.get_child_context(context_index)

                        alias_type.type = self.evaluate_concrete_type_expression(
                            alias_ctx,
                            statement.type,
                        )

                case ast.UseNode() | ast.UseForNode():
                    use_ctx = ctx.get_child_context(context_index)
                    self.propagate_types(use_ctx, statement.body)

                case ast.ForNode() | ast.WhileNode() | ast.IfNode():
                    child_ctx = ctx.get_child_context(context_index)
                    self.propagate_types(child_ctx, statement.body)

                    if isinstance(statement, ast.IfNode):
                        context_index += 1
                        else_ctx = ctx.get_child_context(context_index)

                        self.propagate_types(else_ctx, statement.else_body)

    def evaluate_type_expression(
        self,
        ctx: AnalysisContext,
        type_expression: ast.TypeExpressionNode,
        *,
        allow_instance: bool = False,  # allow_module?
        allow_polymorphic: bool = False,
    ) -> Symbol:
        match type_expression:
            case ast.NameNode():
                symbol = ctx.get_symbol(type_expression.value)
                assert symbol is not None, f'undefined symbol, {type_expression.value}'

                if not allow_instance and isinstance(symbol, TypeInstance):
                    assert False, 'Instance not allowed here'

                if not allow_polymorphic and isinstance(symbol, types.PolymorphicType):
                    assert False, 'Polymorphic type noe allowed here'

                return symbol

            case ast.TypeAttributeNode():
                type = self.evaluate_type_expression(
                    ctx,
                    type_expression,
                    allow_instance=True,
                )
                assert False, 'Not Implemented'

            case ast.TypeCallNode():
                callee = self.evaluate_type_expression(ctx, type_expression.type, allow_polymorphic=True)
                if not isinstance(callee, types.PolymorphicType):
                    assert False, 'Calling non-polymorphic type...'

                arguments: typing.List[types.ConcreteType] = []
                for argument in type_expression.args:
                    arguments.append(self.evaluate_concrete_type_expression(ctx, argument))

                return callee.with_parameters(arguments)

            case ast.TypeParameterNode():
                parameter = ctx.get_type_parameter(type_expression.name)
                assert parameter is not None, 'impossible!'
                return parameter

            case ast.SelfTypeNode():
                return types.SingletonType.SELF

            case ast.ListTypeNode():
                elt = self.evaluate_concrete_type_expression(ctx, type_expression.elt)
                assert False, 'Not implemented'

            case ast.StructTypeNode():
                struct_type = types.StructType(name='inline struct')

                for field in type_expression.fields:
                    field_type = self.evaluate_concrete_type_expression(ctx, field.type)
                    struct_type.fields[field.name] = types.StructField(name=field.name, type=field_type)

                return struct_type

            case ast.TupleTypeNode():
                if not type_expression.elts:
                    return types.SingletonType.UNIT

                tuple_type = types.TupleType(name='inline tuple')

                for elt in type_expression.elts:
                    elt_type = self.evaluate_concrete_type_expression(ctx, elt)
                    tuple_type.fields.append(elt_type)

                return tuple_type

    def evaluate_concrete_type_expression(
        self,
        ctx: AnalysisContext,
        type_expression: ast.TypeExpressionNode,
        *,
        allow_self: bool = False,
    ) -> types.ConcreteType:
        type = self.evaluate_type_expression(ctx, type_expression)
        assert not isinstance(type, (types.PolymorphicType, TypeInstance))
        return type

    def check_type_compatibility(self, type1: types.ConcreteType, type2: types.ConcreteType) -> bool:
        if (
            type1 is types.SingletonType.UNKNOWN
            or type2 is types.SingletonType.UNKNOWN
        ):
            return False

        if type1 is type2:
            return True

        return False

    def analyze_types(
        self,
        ctx: AnalysisContext,
        statements: typing.List[ast.StatementNode],
    ) -> None:
        context_index = 0
        for statement in statements:
            context_index += 1

            match statement:
                case ast.FunctionDefNode():
                    if statement.body is None:
                        continue

                    function_type = ctx.get_symbol(statement.name)
                    if isinstance(function_type, types.PolymorphicType):
                        function_type = function_type.type

                    assert isinstance(function_type, types.FunctionType)
                    function_ctx = ctx.get_child_context(context_index)

                    for parameter in function_type.parameters.values():
                        function_ctx.add_symbol(parameter.name, TypeInstance(type=parameter.type))

                    function_ctx.flags |= AnalysisFlags.ALLOW_RETURN
                    function_ctx.returnable_type = function_type.returns
                    self.analyze_types(function_ctx, statement.body)

                case ast.ClassDefNode():
                    type_class = ctx.get_symbol(statement.name)
                    if isinstance(type_class, types.PolymorphicType):
                        type_class = type_class.type

                    assert isinstance(type_class, types.TypeClass)
                    class_ctx = ctx.get_child_context(context_index)
                    self.analyze_types(class_ctx, statement.body)

                case ast.DeclarationNode():
                    type = types.SingletonType.UNDECLARED
                    if statement.type is not None:
                        type = self.evaluate_concrete_type_expression(ctx, statement.type)

                    if statement.value is not None:
                        value = self.analyze_instance_of_expression(ctx, statement.value)

                        if type is types.SingletonType.UNDECLARED:
                            type = value.type
                        elif not self.check_type_compatibility(value.type, type):
                            assert False, 'Incompatibility.'

                    ctx.add_symbol(statement.target, TypeInstance(type=type))

                case ast.ReturnNode():
                    if not ctx.flags & AnalysisFlags.ALLOW_RETURN:
                        assert False, 'Return is not valid here'

                    if statement.value is None:
                        return_type = types.SingletonType.UNIT
                    else:
                        value = self.analyze_instance_of_expression(ctx, statement.value)
                        return_type = value.type

                    compatible = self.check_type_compatibility(return_type, ctx.returnable_type)
                    if not compatible:
                        assert False, f'incompatible return type, {return_type.to_string()}, {ctx.returnable_type.to_string()}'

                case ast.UseNode() | ast.UseForNode():
                    use_ctx = ctx.get_child_context(context_index)
                    self.analyze_types(use_ctx, statement.body)

                case ast.ForNode() | ast.WhileNode() | ast.IfNode():
                    child_ctx = ctx.get_child_context(context_index)
                    self.analyze_types(child_ctx, statement.body)

                    if isinstance(statement, ast.IfNode):
                        context_index += 1
                        else_ctx = ctx.get_child_context(context_index)
                        self.analyze_types(else_ctx, statement.else_body)

                case ast.ExprNode():
                    self.analyze_type_of_expression(ctx, statement.expr)

    def analyze_type_of_expression(
        self,
        ctx: AnalysisContext,
        expression: ast.ExpressionNode,
    ) -> Symbol:
        match expression:
            case ast.NameNode():
                symbol = ctx.get_symbol(expression.value)
                assert symbol is not None, f'symbol {expression.value} not defined'

                if symbol is types.SingletonType.UNDECLARED:
                    assert False, 'Cannot discern type of symbol before declaration'

                return symbol

            case ast.AttributeNode():
                symbol = self.analyze_type_of_expression(ctx, expression.value)
                assert not isinstance(symbol, types.PolymorphicType)

                if isinstance(symbol, TypeInstance):
                    type = self.get_type_attribute(symbol.type, expression.attr, is_instance=True)
                    return TypeInstance(type=type)  # This is wrong
                else:
                    return self.get_type_attribute(symbol, expression.attr)

            case ast.AssignNode():
                if not isinstance(expression.target, ast.NameNode):
                    assert False, 'Only names are supported for targets'

                symbol = ctx.get_symbol(expression.target.value)
                if not isinstance(symbol, TypeInstance):
                    assert False, f'Cannot assign to {symbol}'

                value = self.analyze_instance_of_expression(ctx, expression.value)
                if symbol.type is types.SingletonType.UNDECLARED:
                    ctx.add_symbol(expression.target.value, value)
                elif not self.check_type_compatibility(value.type, symbol.type):
                    assert False, 'Incompatible assignment'

                return types.SingletonType.UNIT

        assert False

    def analyze_instance_of_expression(
        self,
        ctx: AnalysisContext,
        expression: ast.ExpressionNode,
    ) -> TypeInstance:
        symbol = self.analyze_type_of_expression(ctx, expression)
        if not isinstance(symbol, TypeInstance):
            assert False, f'Expected a type instance {symbol}'

        return symbol

    def get_type_attribute(
        self,
        type: types.ConcreteType,
        name: str,
        *,
        is_instance: bool = False,
    ) -> types.ConcreteType:
        attribute = None
        match type:
            case types.ParameterizedType():
                attribute = self.get_type_attribute(type.type, name, is_instance=is_instance)
                if isinstance(attribute, types.TypeParameter) and attribute in type.type_map:
                    attribute = type.type_map[attribute]
                else:
                    attribute = types.ParameterizedType(type=attribute, type_map=type.type_map)
            case types.TypeAlias():
                attribute = self.get_type_attribute(type.type, name, is_instance=is_instance)
            case types.StructType() if is_instance:
                if name in type.fields:
                    attribute = type.fields[name].type
            case types.TypeClass():
                attribute = type.functions.get(name)

        assert attribute is not None, f'{type}.{name}'
        return attribute

    def analyze_module(self) -> None:
        self.initialize_types(self.ctx, self.module.body)
        self.propagate_types(self.ctx, self.module.body)
        self.analyze_types(self.ctx, self.module.body)
