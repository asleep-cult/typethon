from __future__ import annotations

import typing
import prettyprinter

from . import types
from .builder import Types, Ops, Classes, DEBUG
from .context import AnalysisContext, ContextFlags
from ..diagnostics import DiagnosticReporter
from ..syntax.typethon import ast
from .scope import Scope, Symbol, UNRESOLVED

T = typing.TypeVar('T', bound=ast.StatementNode)
# XXX: Unknown proagates outwards, so any name that is defined as unknown
# will result in an diagnostic error every time it is used anywhere,
# which will also make the expression it is used in unknown and the error
# messages will begin the multiply. This might not be ideal.

# TODO: All calls to get_class_implementation could break if we do not
# check for uninitialized parameters
# In general, this really needs tests to find any edge cases
# Sometimes we return UNKNOWN after reporting an error but it might be
# more graceful to use UNKNOWN.to_instance() because it's often in areas
# where only instances are valid


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
            (node.start, node.end),
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
            (node.start, node.end),
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
            ('debug', DEBUG.to_instance()),
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

            elif (
                isinstance(statement, ast.TypeAssignmentNode)
                and isinstance(statement.type, ast.StructTypeNode)
            ):
                type = types.StructType(propagated=False, name=statement.name)
                symbol = Symbol(name=statement.name, content=type)
                parameters = self.walk_struct_parameters(statement.type)

            else:
                continue

            scope.add_symbol(symbol)
            child_scope = scope.create_child_scope(statement.name)

            for parameter in parameters:
                if child_scope.has_symbol(parameter.name):
                    continue

                type_parameter = types.TypeParameter(name=parameter.name, owner=type)

                symbol = Symbol(name=parameter.name, content=type_parameter)
                child_scope.add_symbol(symbol)
                type.parameters.append(type_parameter)

            if (
                isinstance(statement, ast.FunctionDefNode)
                and statement.body is not None
            ):
                self.initialize_types(child_scope, statement.body)

    def walk_function_parameters(
        self, statement: ast.FunctionDefNode,
    ) -> typing.Generator[ast.TypeParameterNode]:
        for parameter in statement.parameters:
            yield from self.walk_type_parameters(parameter.annotation)

        yield from self.walk_type_parameters(statement.returns)

    def walk_struct_parameters(
        self, statement: ast.StructTypeNode
    ) -> typing.Generator[ast.TypeParameterNode]:
        for field in statement.fields:
            yield from self.walk_type_parameters(field.type)

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

            case ast.ListTypeNode():
                yield from self.walk_type_parameters(expression.elt)

            case ast.StructTypeNode():
                for field in expression.fields:
                    yield from self.walk_type_parameters(field.type)

            case ast.TupleTypeNode():
                for elt in expression.elts:
                    yield from self.walk_type_parameters(elt)

            case ast.SelfTypeNode() if expression.arg is not None:
                yield from self.walk_type_parameters(expression.arg)

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
                        type = self.evaluate_annotation(
                            function_scope,
                            parameter.annotation,
                            function,
                        )

                        function.fn_parameters[parameter.name] = (
                            types.FunctionParameter(name=parameter.name, type=type)
                        )

                    function.fn_returns = self.evaluate_annotation(
                        function_scope,
                        statement.returns,
                        function,
                    )

                    function.complete_propagation()

                    if statement.body is not None:
                        self.propagate_types(function_scope, statement.body)

                case ast.TypeAssignmentNode() if isinstance(statement.type, ast.StructTypeNode):
                    struct_scope = scope.get_child_scope(statement.name)

                    struct = scope.get_type(statement.name)
                    assert isinstance(struct, types.StructType)

                    for field in statement.type.fields:
                        type = self.evaluate_type_expression(
                            struct_scope, field.type, struct,
                        )
                        struct.struct_fields[field.name] = types.StructField(name=field.name, type=type)

                    struct.complete_propagation()

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
        match expression:
            case ast.NameNode():
                symbol = scope.get_symbol(expression.value)
                if symbol is UNRESOLVED:
                    self.report_error(
                        expression,
                        'Unresolved reference to symbol `{0}`',
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

            case ast.SelfTypeNode():
                type = types.SelfType()

                if expression.arg is not None:
                    type.owner = self.evaluate_type_expression(scope, expression.arg, owner)

                if isinstance(owner, types.FunctionType):
                    owner.fn_self = type

                return type

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
                callee = self.evaluate_type_expression(
                    scope,
                    expression.type,
                    owner,
                )

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

            case ast.ListTypeNode():
                elt = self.evaluate_type_expression(scope, expression.elt, owner)
                return Types.LIST.with_parameters([elt])

            case ast.StructTypeNode():
                struct = types.StructType(name='<anonymous struct>')
                for field in expression.fields:
                    type = self.evaluate_type_expression(scope, field.type, owner)

                    struct.struct_fields[field.name] = types.StructField(
                        name=field.name, type=type,
                    )

                return struct

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
                            if not isinstance(ctx.outer_type, types.TypeClass):
                                self.report_error(
                                    statement.parameters[0],
                                    'Function `{0}` uses unbound Self outside of class. '
                                    'Please bind Self using Self(T).',
                                    function.name,
                                )
                            else:
                                function.fn_self.owner = ctx.outer_type
                        elif (
                            isinstance(ctx.outer_type, types.TypeClass)
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
                    type_class = scope.get_type(statement.name)
                    assert (
                        isinstance(type_class, types.TypeClass)
                        and type_class.propagated
                    )

                    inner_ctx = ctx.create_inner_context(type_class)
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

                        if not instance.type.is_compatible_with(ctx.outer_type.fn_returns):
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
                    implementation = iterator.type.get_class_implementation(
                        Classes.ITER.with_parameters([types.ANY])
                    )
                    if implementation is None:
                        return self.report_error(
                            statement,
                            '`{0}` does not implement the Iter class',
                            iterator.type.get_string(),
                        )

                    if not isinstance(statement.target, ast.NameNode):
                        assert False, '<Non-name assign not implemented>'

                    function = implementation.get_function('next')
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
                if not instance.type.is_compatible_with(type):
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
        if not isinstance(assignment.target, ast.NameNode):
            assert False, '<Non-name assignment>'

        target = scope.get_instance(assignment.target.value)
        if target.type is types.UNKNOWN:
            return self.report_error(
                assignment,
                'Unresolved reference to name `{0}`',
                assignment.target.value,
            )

        result = self.analyze_binary_operation(assignment, target, instance)
        self.assign_to_name(scope, assignment.target, result)

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
        if not instance.type.is_compatible_with(type):
            self.report_type_incompatibility(
                assignment,
                instance.type,
                type,
                'Assignment to `{0}` does not match the annotation',
                assignment.target.value,
            )

        self.assign_to_name(scope, assignment.target, type.to_instance())

    def analyze_binary_operation(
        self,
        node: typing.Union[ast.BinaryOpNode, ast.AugAssignNode],
        left: types.InstanceOfType,
        right: types.InstanceOfType,
    ) -> types.InstanceOfType:
        match node.op:
            case ast.OperatorKind.ADD:
                type_class = Ops.ADD
                name = 'add'
            case ast.OperatorKind.SUB:
                type_class = Ops.SUB
                name = 'sub'
            case ast.OperatorKind.MULT:
                type_class = Ops.MULT
                name = 'mult'
            case ast.OperatorKind.MATMULT:
                type_class = Ops.MATMULT
                name = 'matmult'
            case ast.OperatorKind.DIV:
                type_class = Ops.DIV
                name = 'div'
            case ast.OperatorKind.MOD:
                type_class = Ops.MOD
                name = 'mod'
            case ast.OperatorKind.POW:
                type_class = Ops.POW
                name = 'pow'
            case ast.OperatorKind.LSHIFT:
                type_class = Ops.LSHIFT
                name = 'lshift'
            case ast.OperatorKind.RSHIFT:
                type_class = Ops.RSHIFT
                name = 'rshift'
            case ast.OperatorKind.BITOR:
                type_class = Ops.BITOR
                name = 'bitor'
            case ast.OperatorKind.BITXOR:
                type_class = Ops.BITXOR
                name = 'bitxor'
            case ast.OperatorKind.BITAND:
                type_class = Ops.BITAND
                name = 'bitand'
            case ast.OperatorKind.FLOORDIV:
                type_class = Ops.FLOORDIV
                name = 'floordiv'

        implementation = left.type.get_class_implementation(
            type_class.with_parameters([right.type, types.ANY])
        )
        if implementation is None:
            self.report_error(
                node,
                '`{0}` does not implement the `{1}` class for `{2}`',
                left.type.get_string(),
                type_class.name,
                right.type.get_string(),
            )
            return types.UNKNOWN.to_instance()

        function = implementation.get_function(name)
        lhs_type = function.get_return_type()

        implementation = right.type.get_class_implementation(
            type_class.with_parameters([left.type, types.ANY])
        )
        if implementation is None:
            return lhs_type.to_instance()

        function = implementation.get_function(name)
        rhs_type = function.get_return_type()

        if not lhs_type.is_compatible_with(rhs_type):
            self.report_type_incompatibility(
                node,
                lhs_type,
                rhs_type,
                'Incompatible types for `{0}` class',
                type_class.name,
            )
            return types.UNKNOWN.to_instance()

        return lhs_type.to_instance()

    def analyze_type(
        self,
        scope: Scope,
        ctx: AnalysisContext,
        expression: ast.ExpressionNode,
    ) -> types.AnalysisUnit:
        match expression:
            case ast.BoolOpNode():
                operands = [self.analyze_instance_type(scope, ctx, operand) for operand in expression.values]

                type = self.unionize_multiple_types([operand.type for operand in operands])
                instance = type.to_instance()

                ctx.bool_op_hook(instance, expression)
                return instance

            case ast.BinaryOpNode():
                left = self.analyze_instance_type(scope, ctx, expression.left)
                right = self.analyze_instance_type(scope, ctx, expression.right)

                return self.analyze_binary_operation(expression, left, right)

            case ast.UnaryOpNode():
                operand = self.analyze_instance_type(scope, ctx, expression.operand)

                match expression.op:
                    case ast.UnaryOperatorKind.INVERT:
                        type_class = Ops.INVERT
                        name = 'invert'
                    case ast.UnaryOperatorKind.NOT:
                        return Types.BOOL.to_instance()
                    case ast.UnaryOperatorKind.UADD:
                        type_class = Ops.UADD
                        name = 'uadd'
                    case ast.UnaryOperatorKind.USUB:
                        type_class = Ops.USUB
                        name = 'usub'

                implementation = operand.type.get_class_implementation(
                    type_class.with_parameters([types.ANY])
                )
                if implementation is None:
                    self.report_error(
                        expression,
                        '`{0}` does not implement `{1}` class',
                        operand.type.get_string(),
                        type_class.name,
                    )
                    return types.UNKNOWN

                function = implementation.get_function(name)
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

            case ast.SubscriptNode():
                instance = self.analyze_instance_type(scope, ctx, expression.value)

                assert len(expression.slices) == 0, 'TODO Maybe'
                slice = self.analyze_instance_type(scope, ctx, expression.slices[0])

                implementation = instance.type.get_class_implementation(
                    Classes.INDEX.with_parameters([slice.type, types.ANY])
                )
                if implementation is None:
                    self.report_error(
                        expression,
                        '`{0}` does not implement the Index class for {1}',
                        instance.type.get_string(),
                        slice.type.get_string(),
                    )
                    return types.UNKNOWN

                function = implementation.get_function('get_item')
                instance = function.get_return_type().to_instance()

                ctx.subscript_hook(instance, expression)
                return instance

            case ast.CallNode():
                unit = self.analyze_type(scope, ctx, expression.callee)
                match unit:
                    case types.FunctionType():
                        assert False, '<Cannot call a function type>'
                    case types.StructType():
                        return self.analyze_struct_initialization(scope, ctx, unit, expression)
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
                        'Unresolved reference to name `{0}`',
                        expression.value,
                    )

                ctx.name_hook(symbol.content, expression)
                return symbol.content

            case ast.ListNode():
                elts = [self.analyze_instance_type(scope, ctx, elt) for elt in expression.elts]

                if elts:
                    elt_types = self.unionize_multiple_types([elt.type for elt in elts])
                    instance = Types.LIST.with_parameters([elt_types]).to_instance()
                else:
                    instance = Types.LIST.to_partially_unknown().to_instance()

                ctx.list_hook(instance, expression)
                return instance

        assert False, f'<Unable to determine type of {expression}>'

    def unionize_multiple_types(
        self, type_list: typing.List[types.AnalyzedType]
    ) -> types.AnalyzedType:
        # NOTE: This will fail if type_list is empty.
        flattened_types: typing.List[types.AnalyzedType] = []

        # XXX: Maybe we just need to do this recursively, but it wont be a problem
        # if every union is created with this function (I think?)
        for type in type_list:
            if isinstance(type, types.UnionType):
                flattened_types.extend(type.types)
            else:
                flattened_types.append(type)

        unique_types: typing.List[types.AnalyzedType] = [flattened_types[0]]

        for type in flattened_types:
            if not any(type.is_compatible_with(unique_type) for unique_type in unique_types):
                unique_types.append(type)

        if len(unique_types) > 1:
            return types.UnionType(types=unique_types)

        return unique_types[0]

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
            case types.StructType():
                if attribute.attr in type.struct_fields:
                    return type.get_field_type(attribute.attr).to_instance()

                self.report_error(
                    attribute,
                    '`{0}` has no field named `{1}`',
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
        match constant.kind:
            case ast.ConstantKind.TRUE:
                return Types.TRUE

            case ast.ConstantKind.FALSE:
                return Types.FALSE

            case ast.ConstantKind.ELLIPSIS:
                assert False, '<TODO>'  # XXX: Does this really need to exist...

            case ast.ConstantKind.INTEGER:
                assert isinstance(constant, ast.IntegerNode)
                return Types.INT.to_instance(constant.value)

            case ast.ConstantKind.FLOAT:
                assert isinstance(constant, ast.FloatNode)
                return Types.FLOAT.to_instance(constant.value)

            case ast.ConstantKind.COMPLEX:
                assert isinstance(constant, ast.ComplexNode)
                return Types.FLOAT.to_instance(constant.value)

            case ast.ConstantKind.STRING | ast.ConstantKind.BYTES:
                assert False, '<TODO>'

    def resolve_type_parameters_from_arguments(
        self,
        node: ast.CallNode,
        type: typing.Union[types.FunctionType, types.StructType],
        arguments: typing.List[types.InstanceOfType],
    ) -> typing.List[types.AnalyzedType]:
        # XXX: For a function such as f(x: [|T|]), f([]) -> T; will rightfully fail
        # to resolve T, but it could potentially be resolved by using the outside
        # context (i.e x: int = f([]) should resolve T to int).
        parameter_map: typing.List[typing.Tuple[types.TypeParameter, types.AnalyzedType]] = []

        if isinstance(type, types.FunctionType):
            required_parameters = type.fn_parameters.values()
        else:
            required_parameters = type.struct_fields.values()

        for required_parameter, argument in zip(required_parameters, arguments):
            if isinstance(required_parameter.type, types.TypeParameter):
                # Given a function f(x: |T|), f(U) gives {T: U}
                parameter_map.append((required_parameter.type, argument.type))
            elif isinstance(required_parameter.type, types.PolymorphicType):
                # Given a function f(x: T(|U|)), f(T(V)) gives {U: V}
                if (
                    not isinstance(argument.type, types.PolymorphicType)
                    or required_parameter.type.get_initial_type() is not argument.type.get_initial_type()
                ):
                    # There is a type incompatibility, we will report it later
                    continue

                mapped_parameters = zip(
                    required_parameter.type.given_parameters,
                    argument.type.given_parameters,
                )
                for given_parameter1, given_parameter2 in mapped_parameters:
                    if isinstance(given_parameter1, types.TypeParameter):
                        parameter_map.append((given_parameter1, given_parameter2))

        parameters: typing.List[types.AnalyzedType] = []

        for parameter in type.parameters:
            mapped = [given_type for param, given_type in parameter_map if param is parameter]

            if not mapped:
                self.report_error(
                    node,
                    'Unable to resolve type parameter `{0}` of `{1}`',
                    parameter.name,
                    type.name
                )
                parameters.append(types.UNKNOWN)
                continue

            for given_type in mapped[1:]:
                if not given_type.is_compatible_with(mapped[0]):
                    self.report_type_incompatibility(
                        node,
                        given_type,
                        mapped[0],
                        'Resolved types for parameter `{0}` of `{1}` are different',
                        parameter.name,
                        type.name
                    )

            parameters.append(mapped[0])
        
        return parameters

    def analyze_function_call(
        self,
        scope: Scope,
        ctx: AnalysisContext,
        function: types.FunctionType,
        node: ast.CallNode,
    ) -> types.InstanceOfType:
        arguments = [self.analyze_instance_type(scope, ctx, argument) for argument in node.args]

        if function is DEBUG:
            prettyprinter.cpprint(arguments)
            return function.fn_returns.to_instance()

        parameters = self.resolve_type_parameters_from_arguments(node, function, arguments)
        function = function.with_parameters(parameters)
        parameter_types = function.get_parameter_types()

        for arg, instance in zip(node.args, arguments):
            if not parameter_types:
                self.report_error(
                    arg,
                    '`{0}` received too many arguments, expected {1}, received {2}',
                    function.name,
                    str(len(function.fn_parameters)),
                    str(len(node.args)),
                )
                break

            type = parameter_types.pop(0)
            if not instance.type.is_compatible_with(type):
                # TODO: What is it named??
                self.report_type_incompatibility(
                    arg,
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

    def analyze_struct_initialization(
        self,
        scope: Scope,
        ctx: AnalysisContext,
        struct: types.StructType,
        node: ast.CallNode,
    ) -> types.InstanceOfType:
        arguments = [self.analyze_instance_type(scope, ctx, argument) for argument in node.args]

        parameters = self.resolve_type_parameters_from_arguments(node, struct, arguments)
        struct = struct.with_parameters(parameters)
        field_types = struct.get_field_types()

        for arg, instance in zip(node.args, arguments):
            if not field_types:
                self.report_error(
                    arg,
                    '`{0}` received too many arguments, expected {1}, got {2}',
                    struct.name,
                    str(len(struct.struct_fields)),
                    str(len(node.args)),
                )
                break

            type = field_types.pop(0)
            if not instance.type.is_compatible_with(type):
                # TODO: What is it named??
                self.report_type_incompatibility(
                    arg,
                    instance.type,
                    type,
                    'Incompatible type for parameter of `{0}`',
                    struct.name,
                )

        if field_types:
            self.report_error(
                node,
                '`{0}` received too few arguments, expected {1}, got {2}',
                struct.name,
                str(len(struct.struct_fields)),
                str(len(node.args)),
            )

        return struct.to_instance()

    def analyze_module(self) -> None:
        self.initialize_builtin_symbols()
        self.initialize_types(self.module_scope, self.module.body)
        self.propagate_types(self.module_scope, self.module.body)
        self.analyze_types(self.module_scope, self.ctx, self.module.body)
