import attr
import typing
import enum

from . import types
from .scope import Scope, TypeInstance, Symbol
from ..syntax.typethon import ast


class AnalysisFlags(enum.Flag):
    NONE = 0
    ALLOW_RETURN = enum.auto()
    ALLOW_BREAK = enum.auto()
    ALLOW_CONTINUE = enum.auto()


@attr.s(kw_only=True, slots=True)
class AnalysisContext:
    scope: Scope = attr.ib()
    flags: AnalysisFlags = attr.ib()
    returnable_type: types.ConcreteType = attr.ib(default=types.SingletonType.UNIT)


class TypeAnalyzer:
    def __init__(self, module: ast.ModuleNode) -> None:
        self.module = module
        self.scope = Scope()

    def initialize_types(self, scope: Scope, statements: typing.List[ast.StatementNode]) -> None:
        for statement in statements:
            match statement:
                case ast.FunctionDefNode():
                    function_scope = scope.create_child_scope()
                    function_type = types.FunctionType(name=statement.name, scope=function_scope)

                    for parameter in statement.parameters:
                        self.initialize_type_parameters(function_scope, parameter.annotation)

                    self.initialize_type_parameters(function_scope, statement.returns)

                    if function_scope.type_parameters:
                        function_type = types.PolymorphicType(
                            type=function_type,
                            parameters=list(function_scope.type_parameters.values())
                        )

                    if statement.body is not None:
                        self.initialize_types(function_scope, statement.body)

                    scope.add_symbol(statement.name, function_type)

                case ast.ClassDefNode():
                    class_scope = scope.create_child_scope()
                    type_class = types.TypeClass(name=statement.name, scope=class_scope)

                    for parameter in statement.parameters:
                        self.initialize_type_parameters(class_scope, parameter)

                    if class_scope.type_parameters:
                        type_class = types.PolymorphicType(
                            type=type_class,
                            parameters=list(class_scope.type_parameters.values()),
                        )

                    self.initialize_types(class_scope, statement.body)
                    scope.add_symbol(statement.name, type_class)

                case ast.TypeDeclarationNode():
                    if (
                        isinstance(statement.type, ast.TupleTypeNode)
                        and not statement.type.elts
                    ):
                        scope.add_symbol(statement.name, types.SingletonType.UNIT)
                        continue
 
                    child_scope = scope.create_child_scope()

                    if isinstance(statement.type, ast.StructTypeNode):
                        type = types.StructType(name=statement.name, scope=child_scope)
                    elif isinstance(statement.type, ast.TupleTypeNode):
                        type = types.TupleType(name=statement.name, scope=child_scope)
                    else:
                        type = types.TypeAlias(name=statement.name, scope=child_scope)
 
                    self.initialize_type_parameters(child_scope, statement.type)

                    if child_scope.type_parameters:
                        type = types.PolymorphicType(
                            type=type,
                            parameters=list(child_scope.type_parameters.values()),
                        )

                    scope.add_symbol(statement.name, type)

                case ast.UseNode() | ast.UseForNode():
                    assert False, 'Not implemented'
                    self.initialize_types(scope, statement.body)

    def initialize_type_parameters(
        self,
        scope: Scope,
        type_expression: ast.TypeExpressionNode,
    ) -> None:
        match type_expression:
            case ast.TypeParameterNode():
                existing_parameter = scope.get_type_parameter(type_expression.name)
                if existing_parameter is None:
                    scope.add_type_parameter(types.TypeParameter(name=type_expression.name))

            case ast.TypeCallNode():
                self.initialize_type_parameters(scope, type_expression.type)
                for argument in type_expression.args:
                    self.initialize_type_parameters(scope, argument)

            case ast.TypeAttributeNode():
                self.initialize_type_parameters(scope, type_expression.value)

            case ast.ListTypeNode():
                self.initialize_type_parameters(scope, type_expression.elt)

            case ast.StructTypeNode():
                for field in type_expression.fields:
                    self.initialize_type_parameters(scope, field.type)

            case ast.TupleTypeNode():
                for elt in type_expression.elts:
                    self.initialize_type_parameters(scope, elt)

    def propagate_types(self, scope: Scope, statements: typing.List[ast.StatementNode]) -> None:
        for statement in statements:
            match statement:
                case ast.FunctionDefNode():
                    function_type = scope.get_symbol(statement.name)
                    if isinstance(function_type, types.PolymorphicType):
                        function_type = function_type.type

                    assert isinstance(function_type, types.FunctionType)

                    for parameter in statement.parameters:
                        parameter_type = self.evaluate_concrete_type_expression(
                            function_type.scope,
                            parameter.annotation,
                        )
                        function_type.parameters[parameter.name] = types.FunctionParameter(
                            name=parameter.name,
                            type=parameter_type,
                        )

                    function_type.returns = self.evaluate_concrete_type_expression(function_type.scope, statement.returns)

                case ast.ClassDefNode():
                    type_class = scope.get_symbol(statement.name)
                    if isinstance(type_class, types.PolymorphicType):
                        type_class = type_class.type

                    assert isinstance(type_class, types.TypeClass)

                    for inner_statement in statement.body:
                        if not isinstance(inner_statement, ast.FunctionDefNode):
                            continue

                        function_type = type_class.scope.get_symbol(inner_statement.name)
                        assert isinstance(function_type, types.FunctionType)

                        type_class.functions[function_type.name] = function_type

                    self.propagate_types(type_class.scope, statement.body)

                case ast.TypeDeclarationNode():
                    if isinstance(statement.type, ast.StructTypeNode):
                        struct_type = scope.get_symbol(statement.name)
                        if isinstance(struct_type, types.PolymorphicType):
                            struct_type = struct_type.type

                        assert isinstance(struct_type, types.StructType)

                        for field in statement.type.fields:
                            field_type = self.evaluate_concrete_type_expression(struct_type.scope, field.type)
                            struct_type.fields[field.name] = types.StructField(name=field.name, type=field_type)

                    elif isinstance(statement.type, ast.TupleTypeNode):
                        if not statement.type.elts:
                            continue

                        tuple_type = scope.get_symbol(statement.name)
                        if isinstance(tuple_type, types.PolymorphicType):
                            tuple_type = tuple_type.type

                        assert isinstance(tuple_type, types.TupleType)

                        for elt in statement.type.elts:
                            elt_type = self.evaluate_concrete_type_expression(tuple_type.scope, elt)
                            tuple_type.fields.append(elt_type)

                    else:
                        alias_type = scope.get_symbol(statement.name)
                        if isinstance(alias_type, types.PolymorphicType):
                            alias_type = alias_type.type

                        assert isinstance(alias_type, types.TypeAlias)

                        alias_type.type = self.evaluate_concrete_type_expression(alias_type.scope, statement.type)

    def evaluate_type_expression(
        self,
        scope: Scope,
        type_expression: ast.TypeExpressionNode,
        *,
        allow_instance: bool = False,  # allow_module?
        allow_polymorphic: bool = False,
    ) -> Symbol:
        match type_expression:
            case ast.NameNode():
                symbol = scope.get_symbol(type_expression.value)
                assert symbol is not None, 'undefined symbol'

                if not allow_instance and isinstance(symbol, TypeInstance):
                    assert False, 'Instance not allowed here'

                if not allow_polymorphic and isinstance(symbol, types.PolymorphicType):
                    assert False, 'Polymorphic type noe allowed here'

                return symbol

            case ast.TypeAttributeNode():
                type = self.evaluate_type_expression(
                    scope,
                    type_expression,
                    allow_instance=True,
                )
                assert False, 'Not Implemented'

            case ast.TypeCallNode():
                callee = self.evaluate_type_expression(scope, type_expression.type, allow_polymorphic=True)
                if not isinstance(callee, types.PolymorphicType):
                    assert False, 'Calling non-polymorphic type...'

                arguments: typing.List[types.ConcreteType] = []
                for argument in type_expression.args:
                    arguments.append(self.evaluate_concrete_type_expression(scope, argument))

                return callee.with_parameters(arguments)

            case ast.TypeParameterNode():
                parameter = scope.get_type_parameter(type_expression.name)
                assert parameter is not None, 'impossible!'
                return parameter

            case ast.SelfTypeNode():
                return types.SingletonType.SELF

            case ast.ListTypeNode():
                elt = self.evaluate_concrete_type_expression(scope, type_expression.elt)
                assert False, 'Not implemented'

            case ast.StructTypeNode():
                struct_type = types.StructType(name='inline struct', scope=scope)

                for field in type_expression.fields:
                    field_type = self.evaluate_concrete_type_expression(scope, field.type)
                    struct_type.fields[field.name] = types.StructField(name=field.name, type=field_type)

                return struct_type

            case ast.TupleTypeNode():
                if not type_expression.elts:
                    return types.SingletonType.UNIT

                tuple_type = types.TupleType(name='inline tuple', scope=scope)

                for elt in type_expression.elts:
                    elt_type = self.evaluate_concrete_type_expression(scope, elt)
                    tuple_type.fields.append(elt_type)

                return tuple_type

    def evaluate_concrete_type_expression(
        self,
        scope: Scope,
        type_expression: ast.TypeExpressionNode,
        *,
        allow_self: bool = False,
    ) -> types.ConcreteType:
        type = self.evaluate_type_expression(scope, type_expression)
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
        for statement in statements:
            match statement:
                case ast.FunctionDefNode():
                    if statement.body is None:
                        continue

                    function_type = ctx.scope.get_symbol(statement.name)
                    if isinstance(function_type, types.PolymorphicType):
                        function_type = function_type.type

                    assert isinstance(function_type, types.FunctionType)
                    for parameter in function_type.parameters.values():
                        function_type.scope.add_symbol(parameter.name, TypeInstance(type=parameter.type))

                    inner_ctx = AnalysisContext(
                        scope=function_type.scope,
                        flags=AnalysisFlags.ALLOW_RETURN,
                        returnable_type=function_type.returns,
                    )
                    self.analyze_types(inner_ctx, statement.body)

                case ast.ClassDefNode():
                    type_class = ctx.scope.get_symbol(statement.name)
                    if isinstance(type_class, types.PolymorphicType):
                        type_class = type_class.type

                    assert isinstance(type_class, types.TypeClass)

                    inner_ctx = AnalysisContext(
                        scope=type_class.scope,
                        flags=AnalysisFlags.NONE,
                    )
                    self.analyze_types(inner_ctx, statement.body)

                case ast.DeclarationNode():
                    type = types.SingletonType.UNDECLARED
                    if statement.type is not None:
                        type = self.evaluate_concrete_type_expression(ctx.scope, statement.type)

                    if statement.value is not None:
                        value = self.analyze_instance_of_expression(ctx, statement.value)

                        if type is types.SingletonType.UNDECLARED:
                            type = value.type
                        elif not self.check_type_compatibility(value.type, type):
                            assert False, 'Incompatibility.'

                    ctx.scope.add_symbol(statement.target, TypeInstance(type=type))

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

                case ast.ExprNode():
                    self.analyze_type_of_expression(ctx, statement.expr)

    def analyze_type_of_expression(
        self,
        ctx: AnalysisContext,
        expression: ast.ExpressionNode,
    ) -> Symbol:
        match expression:
            case ast.NameNode():
                symbol = ctx.scope.get_symbol(expression.value)
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

                symbol = ctx.scope.get_symbol(expression.target.value)
                if not isinstance(symbol, TypeInstance):
                    assert False, f'Cannot assign to {symbol}'

                value = self.analyze_instance_of_expression(ctx, expression.value)
                if symbol.type is types.SingletonType.UNDECLARED:
                    ctx.scope.add_symbol(expression.target.value, value)
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
        self.initialize_types(self.scope, self.module.body)
        self.propagate_types(self.scope, self.module.body)
        self.analyze_types(AnalysisContext(scope=self.scope, flags=AnalysisFlags.NONE), self.module.body)
