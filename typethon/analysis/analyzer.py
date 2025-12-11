from __future__ import annotations

import typing

from . import types
from .context import AnalysisContext, ContextFlags
from ..syntax import ast
from .scope import Scope, Symbol, UNRESOLVED

T = typing.TypeVar('T', bound=ast.StatementNode)


class TypeAnalyzer:
    def __init__(
        self,
        module: ast.ModuleNode,
        *,
        ctx: typing.Optional[AnalysisContext] = None
    ) -> None:
        self.module = module
        self.module_scope = Scope()

        if ctx is None:
            ctx = AnalysisContext()

        self.ctx = ctx

    def initialize_builtin_symbols(self) -> None:
        builtins = (
            ('bool', types.BuiltinTypes.BOOL),
            ('int', types.BuiltinTypes.INT),
            ('float', types.BuiltinTypes.FLOAT),
            ('complex', types.BuiltinTypes.COMPLEX),
            ('str', types.BuiltinTypes.STR),
            ('list', types.BuiltinTypes.LIST),
            ('dict', types.BuiltinTypes.DICT),
            ('set', types.BuiltinTypes.SET),
        )

        for name, type in builtins:
            self.module_scope.add_symbol(Symbol(name=name, type=type))

    def initialize_types(
        self,
        scope: Scope,
        statements: typing.List[ast.StatementNode],
    ) -> None:
        # This function serves as the first pass, initializing all types
        # in the list of statements as a TypeParameter or PolymorphicType
        for statement in statements:
            if isinstance(statement, ast.FunctionDefNode):
                type = types.FunctionType(propagated=False, name=statement.name)
                parameters = self.walk_function_parameters(statement)

            elif isinstance(statement, ast.ClassDefNode):
                type = types.ClassType(propagated=False, name=statement.name)
                parameters = self.walk_class_parameters(statement)

            else:
                continue

            scope.add_symbol(Symbol(name=statement.name, type=type))
            child_scope = scope.create_child_scope(statement.name)

            for parameter in parameters:
                type_parameter = types.TypeParameter(name=parameter.name, owner=type)

                symbol = Symbol(name=parameter.name, type=type_parameter)
                child_scope.add_symbol(symbol)
                type.parameters.append(type_parameter)

            if statement.body is not None:
                self.initialize_types(child_scope, statement.body)

    def walk_function_parameters(
        self, statement: ast.FunctionDefNode,
    ) -> typing.Generator[ast.TypeParameterNode]:
        for parameter in statement.parameters:
            if parameter.annotation is not None:
                yield from self.walk_type_parameters(parameter.annotation)

    def walk_class_parameters(
        self, statement: ast.ClassDefNode
    ) -> typing.Generator[ast.TypeParameterNode]:
        assignments = self.filter_statements(statement.body, ast.AnnAssignNode)
        for assignment in assignments:
            yield from self.walk_type_parameters(assignment.annotation)

    def filter_statements(
        self,
        statements: typing.List[ast.StatementNode],
        type: typing.Type[T],
    ) -> typing.Iterator[T]:
        return (statement for statement in statements if isinstance(statement, type))

    def walk_type_parameters(
        self, expression: ast.TypeExpressionNode
    ) -> typing.Generator[ast.TypeParameterNode]:
        # TODO: Technically TypeAttributeNode.value and ast.TypeCallNode could
        # contain a type parameter (i.e |T|.x, |T|()), but as far as I know
        # (without thinking too hard about it), they are both meaningless
        # and should result in a syntax error
        match expression:
            case ast.TypeParameterNode():
                yield expression

                if expression.constraint is not None:
                    yield from self.walk_type_parameters(expression.constraint)

            case ast.TypeCallNode():
                for argument in expression.args:
                    yield from self.walk_type_parameters(argument)

            case ast.DictTypeNode():
                yield from self.walk_type_parameters(expression.key)
                yield from self.walk_type_parameters(expression.value)

            case ast.SetTypeNode():
                yield from self.walk_type_parameters(expression.elt)

            case ast.ListTypeNode():
                yield from self.walk_type_parameters(expression.elt)

    def propagate_types(
        self,
        scope: Scope,
        statements: typing.List[ast.StatementNode],
    ) -> None:
        # This function propagetes the fn_returns and fn_paramaters fields for
        # function types, and the cls_attributes and cls_functions fields for 
        # class types.
        for statement in statements:
            match statement:
                case ast.FunctionDefNode():
                    function = scope.get_symbol(statement.name).type
                    assert isinstance(function, types.FunctionType)

                    function_scope = scope.get_child_scope(statement.name)

                    for parameter in statement.parameters:
                        if parameter.annotation is None:
                            assert False, f'<Please provide annotation {parameter.name}>'

                        type = self.evaluate_annotation(
                            function_scope,
                            parameter.annotation,
                            function,
                        )
                        function.fn_parameters.append(
                            types.FunctionParameter(name=parameter.name, type=type)
                        )

                    if statement.returns is None:
                        assert False, f'<Please provide return value>'

                    function.fn_returns = self.evaluate_annotation(
                        function_scope,
                        statement.returns,
                        function,
                    )
                    function.complete_propagation()

                    if statement.body is not None:
                        self.propagate_types(function_scope, statement.body)

                case ast.ClassDefNode():
                    cls = scope.get_symbol(statement.name).type
                    assert isinstance(cls, types.ClassType)

                    class_scope = scope.get_child_scope(statement.name)

                    assignments = self.filter_statements(statement.body, ast.AnnAssignNode)
                    for assignment in assignments:
                        type = self.evaluate_type_expression(
                            class_scope, assignment.annotation, cls,
                        )
                        cls.cls_attributes.append(
                            types.ClassAttribute(name=assignment.target.value, type=type)
                        )

                    functions = self.filter_statements(statement.body, ast.FunctionDefNode)
                    for function in functions:
                        cls_function = class_scope.get_symbol(function.name).type
                        assert isinstance(cls_function, types.FunctionType)
                        cls.cls_functions.append(cls_function)

                    cls.complete_propagation()
                    self.propagate_types(class_scope, statement.body)

    def evaluate_annotation(
        self,
        scope: Scope,
        expression: ast.TypeExpressionNode,
        owner: types.AnalyzedType,
    ) -> types.AnalyzedType:
        type = self.evaluate_type_expression(scope, expression, owner)

        if isinstance(type, types.PolymorphicType):
            # If a type is polymorphic over T, the caller is responsible
            # for defining the type of T.
            for parameter in type.uninitialized_parameters():
                if parameter.owner is not owner:
                    assert False, f'<Use {type.name}(|T|)>'

        return type

    def evaluate_type_expression(
        self,
        scope: Scope,
        expression: ast.TypeExpressionNode,
        owner: typing.Optional[types.AnalyzedType],
    ) -> types.AnalyzedType:
        # FIXME: Passing the instance of owner isn't necessary
        # we just need to find somewhere reasonable to put Self that this
        # function can access
        match expression:
            case ast.TypeNameNode():
                if expression.value == 'Self':
                    if not isinstance(owner, types.FunctionType):
                        assert False, '<Use of Self outside of function>'

                    if owner.fn_self is None:
                        owner.fn_self = types.SelfType(name='Self')

                    return owner.fn_self

                symbol = scope.get_symbol(expression.value)
                if symbol is UNRESOLVED:
                    assert False, f'<Unresolved symbol {expression.value}>'

                return symbol.type

            case ast.TypeParameterNode():
                symbol = scope.get_symbol(expression.name)
                assert isinstance(symbol.type, types.TypeParameter)

                if expression.constraint is not None:
                    symbol.type.constraint = self.evaluate_type_expression(
                        scope,
                        expression.constraint,
                        owner,
                    )

                return symbol.type

            case ast.TypeCallNode():
                # TODO: Make Self(T) invalid except as first function argument
                # probably through the parser
                callee = self.evaluate_type_expression(
                    scope,
                    expression.type,
                    owner,
                )
                if isinstance(callee, types.SelfType):
                    if not expression.args:
                        return callee
                    elif len(expression.args) != 1:
                        assert False, 'Self type can only take one parameter'

                    callee.owner = self.evaluate_type_expression(
                        scope,
                        expression.args[0],
                        owner
                    )
                    return callee

                if not isinstance(callee, types.PolymorphicType):
                    assert False, f'<{callee} is not polymorphic>'

                if not callee.is_polymorphic():
                    assert False, f'<{callee} is already parameterized>'

                arguments: typing.List[types.AnalyzedType] = []
                for arg in expression.args:
                    argument = self.evaluate_type_expression(scope, arg, owner)
                    arguments.append(argument)

                return callee.with_parameters(arguments)

            case ast.TypeAttributeNode():
                type = self.evaluate_type_expression(scope, expression.value, owner)
                return type.access_attribute(expression.attr)

            case ast.DictTypeNode():
                key = self.evaluate_type_expression(scope, expression.key, owner)
                value = self.evaluate_type_expression(scope, expression.value, owner)

                return types.BuiltinTypes.DICT.with_parameters([key, value])

            case ast.SetTypeNode():
                elt = self.evaluate_type_expression(scope, expression.elt, owner)
                return types.BuiltinTypes.SET.with_parameters([elt])

            case ast.ListTypeNode():
                elt = self.evaluate_type_expression(scope, expression.elt, owner)
                return types.BuiltinTypes.LIST.with_parameters([elt])

    def check_type_compatibility(
        self,
        type: types.AnalyzedType,
        value: types.AnalyzedType, 
    ) -> None:
        if not isinstance(value, types.InstanceOfType):
            # TODO: Make def f(x: type(|T|)), f(int) valid
            assert False, f'<Expected instance, got {value}>'

        match type:
            case types.TypeParameter():
                if isinstance(value.type, types.TypeParameter):
                    # XXX: Should this ever be possible?
                    assert type is value.type, f'Incompatible type parameters {type}, {value}'

                # TODO: Check for constraints
            case types.FunctionType():
                assert False, 'Not implemented'
            case types.ClassType():
                assert False, 'Not implemented'
            case types.PolymorphicType():
                assert (
                    isinstance(value.type, types.PolymorphicType)
                    and type.get_initial_type() is value.type.get_initial_type()
                )

                parameters = zip(type.parameters, value.type.parameters)
                for parameter_type, parameter_value in parameters:
                    self.check_type_compatibility(parameter_type, parameter_value)
            case types.AnalyzedType():
                assert type is value.type

    def analyze_types(
        self,
        scope: Scope,
        ctx: AnalysisContext,
        statements: typing.List[ast.StatementNode],
    ) -> None:
        """
        WithNode,
        RaiseNode,
        TryNode, # RETAIN?
        AssertNode, # RETAIN?
        ImportNode,
        ImportFromNode,
        GlobalNode, # RETAIN?
        NonlocalNode, # RETAIN?
        ExprNode,
        """
        for statement in statements:
            match statement:
                case ast.FunctionDefNode() if statement.body is not None:
                    function_scope = scope.get_child_scope(statement.name)
                    function = scope.get_symbol(statement.name).type
                    assert (
                        isinstance(function, types.FunctionType)
                        and function.propagated
                    )

                    if function.fn_self is not None:
                        if function.fn_self.owner is types.UNKNOWN:
                            if not isinstance(ctx.outer_type, types.ClassType):
                                assert False, '<Unbound Self outside of class>'

                            function.fn_self.owner = ctx.outer_type

                        elif (
                            isinstance(ctx.outer_type, types.ClassType)
                            and function.fn_self.owner is not ctx.outer_type
                        ):
                            assert False, f'<Self({function.fn_self.owner}) is not {ctx.outer_type}>'

                    for parameter in function.fn_parameters:
                        symbol = Symbol(name=parameter.name, type=parameter.type.to_instance())
                        function_scope.add_symbol(symbol)

                    inner_ctx = ctx.create_inner_context(function)
                    inner_ctx.flags |= ContextFlags.ALLOW_RETURN
                    self.analyze_types(function_scope, inner_ctx, statement.body)

                case ast.ClassDefNode():
                    class_scope = scope.get_child_scope(statement.name)
                    cls = scope.get_symbol(statement.name).type
                    assert (
                        isinstance(cls, types.ClassType)
                        and cls.propagated
                    )

                    inner_ctx = ctx.create_inner_context(cls)
                    self.analyze_types(class_scope, inner_ctx, statement.body)

                case ast.ReturnNode():
                    if not ctx.flags & ContextFlags.ALLOW_RETURN:
                        assert False, '<Return is not valid in this context>'

                    if statement.value is not None:
                        type = self.analyze_type(scope, ctx, statement.value)
                        if not isinstance(ctx.outer_type, types.FunctionType):
                            assert False, '<unreachable>'

                        self.check_type_compatibility(ctx.outer_type.fn_returns, type)
                        ctx.return_hook(type, statement)

                case ast.DeleteNode():
                    assert False, '<Del is not implemented>'

                case ast.AssignNode():
                    value = self.analyze_type(scope, ctx, statement.value)
                    self.analyze_assignment(scope, statement, value)
                    ctx.assign_hook(value, statement)

                case ast.AugAssignNode():
                    value = self.analyze_type(scope, ctx, statement.value)
                    self.analyze_aug_assignment(scope, statement, value)
                    ctx.aug_assign_hook(value, statement)

                case ast.AnnAssignNode():
                    if statement.value is not None:
                        value = self.analyze_type(scope, ctx, statement.value)
                        self.analyze_ann_assignment(scope, statement, value)
                        ctx.ann_assign_hook(value, statement)

                case ast.ForNode():
                    initial_flags = ctx.flags
                    ctx.flags |= ContextFlags.ALLOW_LOOP_CONTROL

                    iterator = self.analyze_type(scope, ctx, statement.iterator)
                    # implementation = self.implementation_for(types.ITERATOR, iterator)
                    # next = implementation.functions['__next__']
                    # self.analyze_assignment(scope, statement.target, ...)
                    assert False, '<For loop is not implemented>'

                    self.analyze_types(scope, ctx, statement.body)
                    ctx.flags = initial_flags

                case ast.WhileNode():
                    initial_flags = ctx.flags
                    ctx.flags |= ContextFlags.ALLOW_LOOP_CONTROL

                    condition = self.analyze_type(scope, ctx, statement.condition)
                    self.analyze_types(scope, ctx, statement.body)

                    ctx.flags = initial_flags
                    ctx.while_hook(condition, statement)

                case ast.IfNode():
                    condition = self.analyze_type(scope, ctx, statement.condition)

                    self.analyze_types(scope, ctx, statement.body)
                    self.analyze_types(scope, ctx, statement.else_body)

                    ctx.if_hook(condition, statement)

                case ast.ExprNode():
                    # The expression is unused
                    expression = self.analyze_type(scope, ctx, statement.expr)
                    ctx.expr_hook(expression, statement)

                case ast.PassNode():
                    ctx.pass_hook(statement)

                case ast.BreakNode():
                    if not ctx.flags & ContextFlags.ALLOW_LOOP_CONTROL:
                        assert False, '<Break is not valid in this context>'

                    ctx.break_hook(statement)

                case ast.ContinueNode():
                    if not ctx.flags & ContextFlags.ALLOW_LOOP_CONTROL:
                        assert False, '<Continue is not valid in this context>'

                    ctx.continue_hook(statement)

    def analyze_assignment(
        self,
        scope: Scope,
        assignment: ast.AssignNode,
        value: types.AnalyzedType,
    ) -> None:
        for target in assignment.targets:
            if not isinstance(target, ast.NameNode):
                # TODO: Allow unpacking, the parser needs fixing here as well
                assert False, 'Non-variable assignment implemented'

            # TODO: check for type coherency
            scope.add_symbol(Symbol(name=target.value, type=value))

    def analyze_aug_assignment(
        self,
        scope: Scope,
        assignment: ast.AugAssignNode,
        value: types.AnalyzedType,
    ) -> None:
        assert False, '<Aug assignment is not implemented>'

    def analyze_ann_assignment(
        self,
        scope: Scope,
        assignment: ast.AnnAssignNode,
        value: types.AnalyzedType,
    ) -> None:
        assert False, '<Ann assignment is not implemented>'

    def analyze_type(
        self,
        scope: Scope,
        ctx: AnalysisContext,
        expression: ast.ExpressionNode,
    ) -> types.AnalyzedType:
        """
        UnaryOpNode,
        LambdaNode,
        IfExpNode,
        DictNode,
        SetNode,
        ListCompNode,
        SetCompNode,
        DictCompNode,
        GeneratorExpNode,
        AwaitNode,
        YieldNode,
        YieldFromNode,
        CompareNode,
        CallNode,
        FormattedValueNode,
        ConstantNode,
        AttributeNode,
        SubscriptNode,
        StarredNode,
        NameNode,
        ListNode,
        TupleNode,
        SliceNode,
        """
        match expression:
            case ast.BoolOpNode():
                operands = [self.analyze_type(scope, ctx, operand) for operand in expression.values]

                type = types.BuiltinTypes.BOOL.to_instance()
                ctx.bool_op_hook(type, expression)

            case ast.BinaryOpNode():
                left = self.analyze_type(scope, ctx, expression.left)
                right = self.analyze_type(scope, ctx, expression.right)
                assert left is right

                ctx.binary_op_hook(left, expression)
                return left

            case ast.NameNode():
                symbol = scope.get_symbol(expression.value)
                if symbol is UNRESOLVED:
                    assert False, f'<{symbol.name} is unresolved>'

                ctx.name_hook(symbol.type, expression)
                return symbol.type

            case ast.ConstantNode():
                type = self.analyze_constant(scope, expression)
                ctx.constant_hook(type, expression)
                return type

            case ast.CallNode():
                function = self.analyze_type(scope, ctx, expression.func)
                if isinstance(function, types.FunctionType):
                    type = self.analyze_function_call(scope, function, expression)
                    ctx.call_hook(type, expression)
                    return type

        assert False, f'<Unable to determine type of {expression}>'

    def analyze_constant(self, scope: Scope, constant: ast.ConstantNode) -> types.AnalyzedType:
        match constant.type:
            case ast.ConstantType.TRUE:
                return types.BuiltinTypes.TRUE

            case ast.ConstantType.FALSE:
                return types.BuiltinTypes.FALSE

            case ast.ConstantType.NONE:
                return types.BuiltinTypes.NONE

            case ast.ConstantType.ELLIPSIS:
                assert False, '<TODO>'

            case ast.ConstantType.INTEGER:
                assert isinstance(constant, ast.IntegerNode)
                return types.BuiltinTypes.INT.to_instance(constant.value)

            case ast.ConstantType.FLOAT:
                assert isinstance(constant, ast.FloatNode)
                return types.BuiltinTypes.FLOAT.to_instance(constant.value)

            case ast.ConstantType.COMPLEX:
                assert isinstance(constant, ast.ComplexNode)
                return types.BuiltinTypes.FLOAT.to_instance(constant.value)

            case ast.ConstantType.STRING | ast.ConstantType.BYTES:
                assert False, '<TODO>'

    def analyze_function_call(
        self,
        scope: Scope,
        function: types.FunctionType,
        node: ast.CallNode,
    ) -> types.AnalyzedType:
        return function.fn_returns.to_instance()

    def analyze_module(self) -> None:
        self.initialize_builtin_symbols()
        self.initialize_types(self.module_scope, self.module.body)
        self.propagate_types(self.module_scope, self.module.body)
        self.analyze_types(self.module_scope, self.ctx, self.module.body)
