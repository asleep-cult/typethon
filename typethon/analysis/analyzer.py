from __future__ import annotations

import typing
# import prettyprinter

from . import types
from .builder import Types, Traits
from .context import AnalysisContext, ContextFlags
from ..diagnostics import DiagnosticReporter
from ..syntax import ast
from .scope import Scope, Symbol, UNRESOLVED

T = typing.TypeVar('T', bound=ast.StatementNode)
# XXX: Unknown proagates outwards, so any name that is defined as unknown
# will result in an diagnostic error every time it is used anywhere,
# which will also make the expression it is used in unknown and the error
# messages will begin the multiply. This might not be ideal.


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
        message = '{0}: `{1}` is incompatible with `{2}`'.format(
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
            ('dict', Types.DICT),
            ('set', Types.SET),
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
                symbol = Symbol(name=statement.name, content=type.to_instance())
                parameters = self.walk_function_parameters(statement)

            elif isinstance(statement, ast.ClassDefNode):
                type = types.ClassType(propagated=False, name=statement.name)
                symbol = Symbol(name=statement.name, content=type)
                parameters = self.walk_class_parameters(statement)

            else:
                continue

            scope.add_symbol(symbol)
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
                    instance = scope.get_instance(statement.name)

                    function = instance.type
                    assert isinstance(function, types.FunctionType)

                    function_scope = scope.get_child_scope(statement.name)

                    for parameter in statement.parameters:
                        if parameter.annotation is None:
                            self.report_error(
                                parameter,
                                'Parameter `{0}` in `{1}` is missing an annotation',
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

                    if statement.returns is not None:
                        function.fn_returns = self.evaluate_annotation(
                            function_scope,
                            statement.returns,
                            function,
                        )
                    else:
                        self.report_error(
                            statement,
                            '`{0}` is missing a return type annotation',
                            function.name
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
                        if not isinstance(assignment.target, ast.NameNode):
                            assert False, '<Not implemented>'

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
        owner: typing.Optional[types.AnalyzedType],
    ) -> types.AnalyzedType:
        type = self.evaluate_type_expression(scope, expression, owner)

        if isinstance(type, types.PolymorphicType):
            # If a type is polymorphic over T, the caller is responsible
            # for defining the type of T.
            for parameter in type.uninitialized_parameters():
                if parameter.owner is not owner:
                    self.report_error(
                        expression,
                        '`{0}` cannot be used as an annotation because is it requires parameters',
                        type.get_string(),
                    )
                    return type.with_parameters([types.UNKNOWN] * len(type.parameters))

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

                symbol = scope.get_symbol(expression.value)
                if symbol is UNRESOLVED:
                    self.report_error(
                        expression,
                        'Symbol `{0}` is not defined',
                        expression.value,
                    )

                if not isinstance(symbol.content, types.AnalyzedType):
                    self.report_error(
                        expression,
                        '`{0}` is not a type',
                        expression.value,
                    )
                    return types.UNKNOWN

                return symbol.content

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
                        'Cannot pass type parameters to `{0}` because it is not polymorphic',
                        callee.get_string(),
                    )
                    return callee

                if not callee.has_uninitialized_parameters():
                    self.report_error(
                        expression,
                        'Cannot pass type parameters to `{0}` because '
                        'it has no uninitialized parameters',
                        callee.get_string(),
                    )
                    return callee

                arguments: typing.List[types.AnalyzedType] = []
                for arg in expression.args:
                    argument = self.evaluate_type_expression(scope, arg, owner)
                    arguments.append(argument)

                if len(arguments) > len(callee.parameters):
                    self.report_error(
                        expression,
                        '`{0}` got too many parameters, expected {1}, got {2}',
                        callee.get_string(),
                        str(len(callee.parameters)),
                        str(len(arguments)),
                    )
                    arguments = arguments[:len(callee.parameters)]

                elif len(arguments) < len(callee.parameters):
                    self.report_error(
                        expression,
                        '`{0}` got too few parameters, expected {1}, got {2}',
                        callee.get_string(),
                        str(len(callee.parameters)),
                        str(len(arguments)),
                    )

                    while len(arguments) < len(callee.parameters):
                        arguments.append(types.UNKNOWN)

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

                    instance = scope.get_instance(statement.name)
                    function = instance.type
                    assert (
                        isinstance(function, types.FunctionType)
                        and function.propagated
                    )

                    if function.fn_self is not None:
                        if function.fn_self.owner is types.UNKNOWN:
                            if not isinstance(ctx.outer_type, types.ClassType):
                                self.report_error(
                                    statement.parameters[0],
                                    'Function `{0}` uses unbound Self outside of class. '
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
                                'Self in function `{0}` is bound to the wrong type. '
                                'Expected `{1}`, got `{2}`',
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

                        instance = self.analyze_type(scope, ctx, statement.value)
                        if not isinstance(instance, types.InstanceOfType):
                            return self.report_error(
                                statement,
                                '`{0}` is not a valid return value',
                                instance.get_string(),
                            )

                        if not ctx.outer_type.fn_returns.is_compatible_with(instance.type):
                            return self.report_type_incompatibility(
                                statement,
                                instance.type,
                                ctx.outer_type.fn_returns,
                                'Incompatible return type in `{0}`',
                                ctx.outer_type.name,
                            )

                        ctx.return_hook(instance, statement)

                case ast.AssignNode():
                    instance = self.analyze_instance_type(scope, ctx, statement.value)
                    self.analyze_assignment(scope, statement, instance)
                    ctx.assign_hook(instance, statement)

                case ast.AugAssignNode():
                    instance = self.analyze_instance_type(scope, ctx, statement.value)
                    self.analyze_aug_assignment(scope, statement, instance)
                    ctx.aug_assign_hook(instance, statement)

                case ast.AnnAssignNode():
                    if statement.value is not None:
                        instance = self.analyze_instance_type(scope, ctx, statement.value)
                        self.analyze_ann_assignment(scope, statement, instance, ctx.outer_type)
                        ctx.ann_assign_hook(instance, statement)

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
                            '`{0}` does not implement the Iter trait',
                            iterator.type.get_string(),
                        )

                    if not isinstance(statement.target, ast.NameNode):
                        assert False, '<Non-name assign not implemented>'

                    function = trait_table.get_function('next')
                    return_type = function.get_return_type()

                    self.assign_to_name(
                        scope,
                        statement.target,
                        return_type.to_instance()
                    )

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

    def assign_to_name(
        self,
        scope: Scope,
        node: ast.NameNode,
        instance: types.InstanceOfType,
    ) -> None:
        if scope.has_symbol(node.value):
            symbol = scope.get_symbol(node.value)
            if not isinstance(symbol.content, types.InstanceOfType):
                self.report_error(
                    node,
                    '`{0}` was previously defined as a type in this scope',
                    node.value,
                ) 
            else:
                type = symbol.content.type
                if not type.is_compatible_with(instance.type):
                    self.report_type_incompatibility(
                        node,
                        instance.type,
                        type,
                        '`{0}` cannot be assigned `{1}`',
                        instance.type.get_string(),
                        node.value,
                    )
        else:
            scope.add_symbol(Symbol(name=node.value, content=instance))

    def analyze_assignment(
        self,
        scope: Scope,
        assignment: ast.AssignNode,
        instance: types.InstanceOfType,
    ) -> None:
        for target in assignment.targets:
            if not isinstance(target, ast.NameNode):
                # TODO: Allow unpacking, the parser needs fixing here as well
                assert False, 'Non-variable assignment implemented'

            self.assign_to_name(scope, target, instance)

    def analyze_aug_assignment(
        self,
        scope: Scope,
        assignment: ast.AugAssignNode,
        instance: types.InstanceOfType,
    ) -> None:
        assert False, '<Aug assignment is not implemented>'

    def analyze_ann_assignment(
        self,
        scope: Scope,
        assignment: ast.AnnAssignNode,
        instance: types.InstanceOfType,
        owner: typing.Optional[types.AnalyzedType],
    ) -> None:
        # TODO: Just how strict should scoping and assignment types be?
        # Do we want to allow narrowing on Symbols within certain scopes
        # or force pattern matching with new assignments?
        if not isinstance(assignment.target, ast.NameNode):
            assert False, 'Non-variable assignment not implemented'

        type = self.evaluate_annotation(
            scope,
            assignment.annotation,
            owner,
        )
        if not type.is_compatible_with(instance.type):
            self.report_type_incompatibility(
                assignment,
                instance.type,
                type,
                'Assignment to `{0}` does not match the annotation',
                assignment.target.value,
            )

        self.assign_to_name(scope, assignment.target, type.to_instance())

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
                    self.report_error(
                        expression,
                        '`{0}` does not implement the `{1}` trait for `{2}`',
                        left.type.get_string(),
                        trait.name,
                        right.type.get_string(),
                    )
                    return types.UNKNOWN

                function = trait_table.get_function(name)
                lhs_type = function.get_return_type()

                trait_table = right.type.get_trait_table(
                    trait.with_parameters([left.type, types.ANY])
                )
                if trait_table is None:
                    return lhs_type.to_instance()

                function = trait_table.get_function(name)
                rhs_type = function.get_return_type()

                if not lhs_type.is_compatible_with(rhs_type):
                    self.report_type_incompatibility(
                        expression,
                        lhs_type,
                        rhs_type,
                        'Incompatible return types for `{0}` trait',
                        trait.name,
                    )
                    return types.UNKNOWN

                return lhs_type.to_instance()

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

                trait_table = operand.type.get_trait_table(
                    trait.with_parameters([types.ANY])
                )
                if trait_table is None:
                    self.report_error(
                        expression,
                        '`{0}` does not implement `{1}` trait',
                        operand.type.get_string(),
                        trait.name,
                    )
                    return types.UNKNOWN

                function = trait_table.get_function(name)
                instance = function.get_return_type().to_instance()

                ctx.unary_op_hook(instance, expression)
                return instance

            case ast.ConstantNode():
                instance = self.analyze_constant(expression)
                ctx.constant_hook(instance, expression)
                return instance

            case ast.AttributeNode():
                unit = self.analyze_type(scope, ctx, expression.value)
                return self.analyze_attribute(unit, expression)

            case ast.CallNode():
                unit = self.analyze_type(scope, ctx, expression.func)
                match unit:
                    case types.FunctionType():
                        assert False, '<Cannot call a function type>'
                    case types.PolymorphicType():
                        assert False, '<Not yet implemented>'
                    case types.AnalyzedType():
                        assert False, '<Cannot call this type>'
                    case types.InstanceOfType():
                        if isinstance(unit.type, types.FunctionType):
                            return self.analyze_function_call(scope, ctx, unit.type, expression)
                        else:
                            assert False, '<Cannot call a value>'

            case ast.NameNode():
                symbol = scope.get_symbol(expression.value)
                if symbol is UNRESOLVED:
                    self.report_error(
                        expression,
                        'Symbol `{0}` is not defined',
                        symbol.name,
                    )

                ctx.name_hook(symbol.content, expression)
                return symbol.content

            case ast.ListNode():
                assert False, '<NotImplemented>'

        assert False, f'<Unable to determine type of {expression}>'

    def analyze_attribute(
        self,
        unit: types.AnalysisUnit,
        attribute: ast.AttributeNode,
    ) -> types.AnalysisUnit:
        if not isinstance(unit, types.InstanceOfType):
            self.report_error(
                attribute,
                'Cannot get attribute `{0}` on `{1}` because it is not an instance',
                unit.get_string(),
                attribute.attr,
            )
            return types.UNKNOWN

        type = unit.type
        match type:
            case types.ClassType():
                if attribute.attr in type.cls_functions:
                    return type.get_function(attribute.attr)

                if attribute.attr in type.cls_attributes:
                    return type.get_attribute(attribute.attr).to_instance()

                self.report_error(
                    attribute,
                    '`{0}` has no attribute named `{1}`',
                    type.get_string(),
                    attribute.attr,
                )
                return types.UNKNOWN
            case types.FunctionType():
                assert False, '<Cannot get function attribute>'

        self.report_error(
            attribute,
            '`{0}` has no attribute `{1}`',
            type.get_string(),
            attribute.attr,
        )
        return types.UNKNOWN

    def analyze_instance_type(
        self,
        scope: Scope,
        ctx: AnalysisContext,
        expression: ast.ExpressionNode,
    ) -> types.InstanceOfType:
        type = self.analyze_type(scope, ctx, expression)
        if not isinstance(type, types.InstanceOfType):
            self.report_error(
                expression,
                '`{0}` is not valid in this context',
                type.get_string(),
            )
            return types.UNKNOWN.to_instance()

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
                assert False, '<TODO>'  # XXX: Does this really need to exist...

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

    def type_parameters_from_arguments(
        self,
        function: types.FunctionType,
        arguments: typing.List[types.InstanceOfType],
    ) -> typing.List[typing.Tuple[types.TypeParameter, types.AnalyzedType]]:
        parameter_map: typing.List[typing.Tuple[types.TypeParameter, types.AnalyzedType]] = []

        for parameter, argument in zip(function.fn_parameters.values(), arguments):
            if isinstance(parameter.type, types.TypeParameter):
                # Given a function f(x: |T|), f(U) gives {T: U}
                parameter_map.append((parameter.type, argument.type))
            elif isinstance(parameter.type, types.PolymorphicType):
                # Given a function f(x: T(|U|)), f(T(V)) gives {U: V}
                if (
                    not isinstance(argument.type, types.PolymorphicType)
                    or parameter.type.get_initial_type() is not argument.type.get_initial_type()
                ):
                    # There is a type incompatibility, we will report it later
                    continue

                mapped_parameters = zip(
                    parameter.type.given_parameters,
                    argument.type.given_parameters,
                )
                for parameter, given_parameter in mapped_parameters:
                    if isinstance(parameter, types.TypeParameter):
                        parameter_map.append((parameter, given_parameter))

        return parameter_map

    def analyze_function_call(
        self,
        scope: Scope,
        ctx: AnalysisContext,
        function: types.FunctionType,
        node: ast.CallNode,
    ) -> types.InstanceOfType:
        arguments = [self.analyze_instance_type(scope, ctx, argument) for argument in node.args]

        parameter_map = self.type_parameters_from_arguments(function, arguments)
        parameters: typing.List[types.AnalyzedType] = []

        for parameter in function.parameters:
            mapped = [type for param, type in parameter_map if param is parameter]

            if not mapped:
                self.report_error(
                    node,
                    'Unable to resolve type parameter `{0}` of `{1}`',
                    parameter.name,
                    function.name
                )
                parameters.append(types.UNKNOWN)
                continue

            for type in mapped[1:]:
                if not type.is_compatible_with(mapped[0]):
                    self.report_type_incompatibility(
                        node,
                        type,
                        mapped[0],
                        'Resolved types for parameter `{0}` of `{1}` are different',
                        parameter.name,
                        function.name
                    )

            parameters.append(mapped[0])

        function = function.with_parameters(parameters)
        parameter_types = function.get_parameter_types()

        for i, instance in enumerate(arguments):
            if not parameter_types:
                self.report_error(
                    node.args[i],
                    '`{0}` received too many arguments, expected {1}, '
                    'received {2}',
                    function.name,
                    str(len(function.fn_parameters)),
                    str(len(node.args)),
                )
                break

            type = parameter_types.pop(0)
            if not type.is_compatible_with(instance.type):
                # TODO: What is the parameter name?
                # fn_parameters is not technically ordered
                self.report_type_incompatibility(
                    node.args[i],
                    instance.type,
                    type,
                    'Incompatible type for parameter of `{0}`',
                    function.name,
                )

        if parameter_types:
            self.report_error(
                node,
                '`{0}` received too few arguments, expected {1}, '
                'received {2}',
                function.name,
                str(len(function.fn_parameters)),
                str(len(node.args)),
            )

        return function.get_return_type().to_instance()

    def analyze_module(self) -> None:
        self.initialize_builtin_symbols()
        self.initialize_types(self.module_scope, self.module.body)
        self.propagate_types(self.module_scope, self.module.body)
        self.analyze_types(self.module_scope, self.ctx, self.module.body)
