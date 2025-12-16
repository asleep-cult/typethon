from __future__ import annotations

import typing

from . import types
from .builder import Types, Traits
from .context import AnalysisContext, ContextFlags
from ..diagnostics import DiagnosticReporter
from ..syntax import ast
from .scope import Scope, Symbol, UNRESOLVED

T = typing.TypeVar('T', bound=ast.StatementNode)


class TypeAnalyzer:
    def __init__(
        self,
        module: ast.ModuleNode,
        diagnostics: DiagnosticReporter,
        *,
        ctx: typing.Optional[AnalysisContext] = None
    ) -> None:
        self.module = module
        self.diagnostics = diagnostics
        self.module_scope = Scope()

        if ctx is None:
            ctx = AnalysisContext()

        self.ctx = ctx

    def report_error(
        self,
        node: ast.Node,
        message: str,
        *format: str,
    ) -> None:
        self.diagnostics.report_error(
            (node.startpos, node.endpos),
            message,
            *format
        )

    def report_type_incompatibility(
        self,
        node: ast.Node,
        type1: types.AnalyzedType,
        type2: types.AnalyzedType,
        message: str,
        *format: str
    ) -> None:
        # TODO: Tell me why
        message = '{0}: {1} is incompatible with {2}'.format(
            message, type1.get_string(), type2.get_string()
        )
        self.diagnostics.report_error(
            (node.startpos, node.endpos),
            message,
            *format
        )

    def initialize_builtin_symbols(self) -> None:
        builtins = (
            ('bool', Types.BOOL),
            ('int', Types.INT),
            ('float', Types.FLOAT),
            ('complex', Types.COMPLEX),
            ('str', Types.STR),
            ('list', Types.LIST),
            #('dict', Types.DICT),
            #('set', Types.SET),
        )

        for name, type in builtins:
            self.module_scope.add_symbol(Symbol(name=name, content=type))

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

            scope.add_symbol(Symbol(name=statement.name, content=type))
            child_scope = scope.create_child_scope(statement.name)

            for parameter in parameters:
                type_parameter = types.TypeParameter(name=parameter.name, owner=type)

                symbol = Symbol(name=parameter.name, content=type_parameter)
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
                    function = scope.get_type(statement.name)
                    assert isinstance(function, types.FunctionType)

                    function_scope = scope.get_child_scope(statement.name)

                    for parameter in statement.parameters:
                        if parameter.annotation is None:
                            self.report_error(
                                parameter,
                                'Parameter {0} in {1} is missing an annotation',
                                parameter.name,
                                function.name,
                            )
                            type = types.UNKNOWN
                        else:
                            type = self.evaluate_annotation(
                                function_scope,
                                parameter.annotation,
                                function,
                            )

                        function.fn_parameters[parameter.name] = (
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
                    cls = scope.get_type(statement.name)
                    assert isinstance(cls, types.ClassType)

                    class_scope = scope.get_child_scope(statement.name)

                    assignments = self.filter_statements(statement.body, ast.AnnAssignNode)
                    for assignment in assignments:
                        type = self.evaluate_type_expression(
                            class_scope, assignment.annotation, cls,
                        )
                        cls.cls_attributes[assignment.target.value] = (
                            types.ClassAttribute(name=assignment.target.value, type=type)
                        )

                    functions = self.filter_statements(statement.body, ast.FunctionDefNode)
                    for function in functions:
                        cls_function = class_scope.get_type(function.name)
                        assert isinstance(cls_function, types.FunctionType)
                        cls.cls_functions[function.name] = cls_function

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
                    # TODO; Invalid Syntax
                    assert isinstance(owner, types.FunctionType)

                    if owner.fn_self is None:
                        owner.fn_self = types.SelfType()

                    return owner.fn_self

                return scope.get_type(expression.value)

            case ast.TypeParameterNode():
                type = scope.get_type(expression.name)
                assert isinstance(type, types.TypeParameter)

                if expression.constraint is not None:
                    type.constraint = self.evaluate_type_expression(
                        scope,
                        expression.constraint,
                        owner,
                    )

                return type

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

                    callee.owner = self.evaluate_type_expression(
                        scope,
                        expression.args[0],
                        owner
                    )
                    return callee

                if not isinstance(callee, types.PolymorphicType):
                    self.report_error(
                        expression,
                        'Cannot pass parameters to {0} because it is not polymorphic',
                        callee.get_string(),
                    )
                    return types.UNKNOWN

                if not callee.has_uninitialized_parameters():
                    self.report_error(
                        expression,
                        'Cannot pass parameters to {0} because it has no uninitialized parameters',
                        callee.get_string(),
                    )
                    return types.UNKNOWN

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

                return Types.DICT.with_parameters([key, value])

            case ast.SetTypeNode():
                elt = self.evaluate_type_expression(scope, expression.elt, owner)
                return Types.SET.with_parameters([elt])

            case ast.ListTypeNode():
                elt = self.evaluate_type_expression(scope, expression.elt, owner)
                return Types.LIST.with_parameters([elt])

    def analyze_types(
        self,
        scope: Scope,
        ctx: AnalysisContext,
        statements: typing.List[ast.StatementNode],
    ) -> None:
        for statement in statements:
            match statement:
                case ast.FunctionDefNode() if statement.body is not None:
                    function_scope = scope.get_child_scope(statement.name)
                    function = scope.get_type(statement.name)
                    assert (
                        isinstance(function, types.FunctionType)
                        and function.propagated
                    )

                    if function.fn_self is not None:
                        if function.fn_self.owner is types.UNKNOWN:
                            if not isinstance(ctx.outer_type, types.ClassType):
                                self.report_error(
                                    statement.parameters[0],
                                    'Function {0} uses unbound Self outside of class. '
                                    'Please bind Self using Self(T).',
                                    function.name,
                                )
                            else:
                                function.fn_self.owner = ctx.outer_type
                        elif (
                            isinstance(ctx.outer_type, types.ClassType)
                            and function.fn_self.owner is not ctx.outer_type
                        ):
                            self.report_error(
                                statement.parameters[0],
                                'Self in function {0} is bound to the wrong type. '
                                'Expected {1}, got {2}',
                                function.name,
                                ctx.outer_type.get_string(),
                                function.fn_self.owner.get_string()
                            )

                    for parameter in function.fn_parameters.values():
                        symbol = Symbol(
                            name=parameter.name,
                            content=parameter.type.to_instance(),
                        )
                        function_scope.add_symbol(symbol)

                    inner_ctx = ctx.create_inner_context(function)
                    inner_ctx.flags |= ContextFlags.ALLOW_RETURN
                    self.analyze_types(function_scope, inner_ctx, statement.body)

                case ast.ClassDefNode():
                    class_scope = scope.get_child_scope(statement.name)
                    cls = scope.get_type(statement.name)
                    assert (
                        isinstance(cls, types.ClassType)
                        and cls.propagated
                    )

                    inner_ctx = ctx.create_inner_context(cls)
                    self.analyze_types(class_scope, inner_ctx, statement.body)

                case ast.ReturnNode():
                    if not ctx.flags & ContextFlags.ALLOW_RETURN:
                        return self.report_error(
                            statement,
                            'Return is only valid within functions'
                        )

                    if statement.value is not None:
                        assert isinstance(ctx.outer_type, types.FunctionType)

                        value = self.analyze_type(scope, ctx, statement.value)
                        if not isinstance(value, types.InstanceOfType):
                            return self.report_error(
                                statement,
                                'Return must provide a value, not {0}',
                                value.get_string(),
                            )

                        if not ctx.outer_type.fn_returns.is_compatible_with(value.type):
                            return self.report_type_incompatibility(
                                statement,
                                ctx.outer_type.fn_returns,
                                value.type,
                                'Incompatible return type in {0}',
                                ctx.outer_type.name,
                            )

                        ctx.return_hook(value, statement)

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

                    iterator = self.analyze_instance_type(scope, ctx, statement.iterator)
                    trait_table = iterator.type.get_trait_table(
                        Traits.ITER.with_parameters([types.ANY])
                    )
                    if trait_table is None:
                        return self.report_error(
                            statement,
                            '{0} does not implement the Iter trait',
                            iterator.type.get_string(),
                        )

                    if not isinstance(statement.target, ast.NameNode):
                        assert False, '<Non-name assign not implemented>'

                    function = trait_table.functions['next']
                    return_type = function.get_return_type()

                    symbol = Symbol(
                        name=statement.target.value,
                        content=return_type.to_instance()
                    )
                    scope.add_symbol(symbol)

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
                        return self.report_error(statement, 'Break is only valid within loops')

                    ctx.break_hook(statement)

                case ast.ContinueNode():
                    if not ctx.flags & ContextFlags.ALLOW_LOOP_CONTROL:
                        return self.report_error(statement, 'Continue is only valid within loops')

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
            scope.add_symbol(Symbol(name=target.value, content=value))

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
    ) -> types.AnalysisUnit:
        match expression:
            case ast.BoolOpNode():
                operands = [self.analyze_type(scope, ctx, operand) for operand in expression.values]

                type = Types.BOOL.to_instance()
                ctx.bool_op_hook(type, expression)

            case ast.BinaryOpNode():
                left = self.analyze_instance_type(scope, ctx, expression.left)
                right = self.analyze_instance_type(scope, ctx, expression.right)

                match expression.op:
                    case ast.Operator.ADD:
                        trait = Traits.ADD
                        name = 'add'
                    case ast.Operator.SUB:
                        trait = Traits.SUB
                        name = 'sub'
                    case ast.Operator.MULT:
                        trait = Traits.MULT
                        name = 'mult'
                    case ast.Operator.MATMULT:
                        trait = Traits.MATMULT
                        name = 'matmult'
                    case ast.Operator.DIV:
                        trait = Traits.DIV
                        name = 'div'
                    case ast.Operator.MOD:
                        trait = Traits.MOD
                        name = 'mod'
                    case ast.Operator.POW:
                        trait = Traits.POW
                        name = 'pow'
                    case ast.Operator.LSHIFT:
                        trait = Traits.LSHIFT
                        name = 'lshift'
                    case ast.Operator.RSHIFT:
                        trait = Traits.RSHIFT
                        name = 'rshift'
                    case ast.Operator.BITOR:
                        trait = Traits.BITOR
                        name = 'bitor'
                    case ast.Operator.BITXOR:
                        trait = Traits.BITXOR
                        name = 'bitxor'
                    case ast.Operator.BITAND:
                        trait = Traits.BITAND
                        name = 'bitand'
                    case ast.Operator.FLOORDIV:
                        trait = Traits.FLOORDIV
                        name = 'floordiv'

                trait_table = left.type.get_trait_table(
                    trait.with_parameters([right.type, types.ANY])
                )
                if trait_table is None:
                    assert False, '<The left expression does not implement add>'

                function = trait_table.functions[name]
                return function.get_return_type().to_instance()

            case ast.UnaryOpNode():
                operand = self.analyze_instance_type(scope, ctx, expression.operand)

                match expression.op:
                    case ast.UnaryOperator.INVERT:
                        trait = Traits.INVERT
                        name = 'invert'
                    case ast.UnaryOperator.NOT:
                        return Types.BOOL.to_instance()
                    case ast.UnaryOperator.UADD:
                        trait = Traits.UADD
                        name = 'uadd'
                    case ast.UnaryOperator.USUB:
                        trait = Traits.USUB
                        name = 'usub'

                # XXX: This is essentially saying that the expression is polymorphic
                # over the output type
                trait_table = operand.type.get_trait_table(
                    trait.with_parameters([types.ANY])
                )
                if trait_table is None:
                    assert False, '<The operand does not implement the operation>'

                function = trait_table.functions[name]
                return function.get_return_type().to_instance()

            case ast.ConstantNode():
                value = self.analyze_constant(expression)
                ctx.constant_hook(value, expression)
                return value

            case ast.AttributeNode():
                type = self.analyze_type(scope, ctx, expression.value)
                match type:
                    case types.AnalyzedType():
                        return type.access_attribute(type.name)
                    case types.InstanceOfType():
                        return self.analyze_attribute(type.type, expression)

            case ast.CallNode():
                function = self.analyze_type(scope, ctx, expression.func)
                match function:
                    case types.FunctionType() | types.OwnedFunciton():
                        value = self.analyze_function_call(scope, ctx, function, expression)
                    case types.PolymorphicType():
                        assert False, '<Not yet implemented>'
                    case types.AnalyzedType():
                        assert False, '<Cannot call this type>'
                    case types.InstanceOfType():
                        assert False, '<Cannot call a value>'

                ctx.call_hook(value, expression)
                return value

            case ast.NameNode():
                symbol = scope.get_symbol(expression.value)
                if symbol is UNRESOLVED:
                    assert False, f'<{symbol.name} is unresolved>'

                ctx.name_hook(symbol.content, expression)
                return symbol.content

            case ast.ListNode():
                assert False, '<NotImplemented>'

        assert False, f'<Unable to determine type of {expression}>'

    def analyze_attribute(
        self,
        type: types.AnalyzedType,
        attribute: ast.AttributeNode,
    ) -> types.AnalysisUnit:
        match type:
            case types.ClassType():
                if attribute.attr in type.cls_functions:
                    return type.get_function(attribute.attr)

                if attribute.attr in type.cls_attributes:
                    return type.get_attribute(attribute.attr).to_instance()

                assert False, f'<{type} has no attribute {attribute.attr}>'
            case types.FunctionType():
                assert False, '<Cannot get function attribute>'

            case types.AnalyzedType():
                assert False, '<Cannot get attribute on type>'

    def analyze_instance_type(
        self,
        scope: Scope,
        ctx: AnalysisContext,
        expression: ast.ExpressionNode,
    ) -> types.InstanceOfType:
        type = self.analyze_type(scope, ctx, expression)
        if not isinstance(type, types.InstanceOfType):
            assert False, f'<{type} is not allowed in this context>'

        return type

    def analyze_constant(self, constant: ast.ConstantNode) -> types.InstanceOfType:
        match constant.type:
            case ast.ConstantType.TRUE:
                return Types.TRUE

            case ast.ConstantType.FALSE:
                return Types.FALSE

            case ast.ConstantType.NONE:
                return Types.NONE

            case ast.ConstantType.ELLIPSIS:
                assert False, '<TODO>'

            case ast.ConstantType.INTEGER:
                assert isinstance(constant, ast.IntegerNode)
                return Types.INT.to_instance(constant.value)

            case ast.ConstantType.FLOAT:
                assert isinstance(constant, ast.FloatNode)
                return Types.FLOAT.to_instance(constant.value)

            case ast.ConstantType.COMPLEX:
                assert isinstance(constant, ast.ComplexNode)
                return Types.FLOAT.to_instance(constant.value)

            case ast.ConstantType.STRING | ast.ConstantType.BYTES:
                assert False, '<TODO>'

    def analyze_function_call(
        self,
        scope: Scope,
        ctx: AnalysisContext,
        function: types.FunctionLike,
        node: ast.CallNode,
    ) -> types.InstanceOfType:
        parameters = function.get_parameter_types()

        for argument in node.args:
            value = self.analyze_instance_type(scope, ctx, argument)
            if not parameters:
                assert False, '<Got too many arguments>'

            type = parameters.pop(0)
            if not type.is_compatible_with(value.type):
                assert False, '<Incompatible types>'

        return function.get_return_type().to_instance()

    def analyze_module(self) -> None:
        self.initialize_builtin_symbols()
        self.initialize_types(self.module_scope, self.module.body)
        self.propagate_types(self.module_scope, self.module.body)
        self.analyze_types(self.module_scope, self.ctx, self.module.body)
