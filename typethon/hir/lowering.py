from . import hir
from .resolution import SymbolResolver, ScopeKind
from ..syntax.typethon import ast


class HirLowering:
    resolver: SymbolResolver
    module: ast.ModuleNode
    resolver: SymbolResolver

    def __init__(
        self,
        hir_ctx: hir.HirContext,
        module: ast.ModuleNode,
    ) -> None:
        self.hir_ctx = hir_ctx
        self.module = module
        self.resolver = SymbolResolver(hir_ctx, module)

    def report_error(
        self,
        node: ast.Node,
        message: str,
        *format: str,
    ) -> None:
        self.hir_ctx.diagnostics.report_error((node.start, node.end), message, *format)

    def create_path_resursive(
        self,
        path: hir.Path,
        type_expression: ast.TypeAttributeNode | ast.TypeCallNode | ast.NameNode,
    ) -> hir.HirPathResult:
        match type_expression:
            case ast.TypeAttributeNode():
                match type_expression.type:
                    case ast.TypeAttributeNode() | ast.TypeCallNode() | ast.NameNode():
                        field = self.create_path_resursive(path, type_expression.type)
                    case _:
                        field = self.lower_type_expression(type_expression.type)
                        # If it could've been a path, it must've been matched by the previous case
                        assert not isinstance(field, hir.Path)

                        if isinstance(field, hir.TypeParameter):
                            self.report_error(type_expression, 'Cannot access attribute of type parameter')
                            return hir.INVALID

                result = self.resolver.resolve_attribute(field, type_expression.attr)
                if result is None:
                    self.report_error(
                        type_expression,
                        "Cannot access attribute `{0}` of `{1}`",
                        type_expression.attr,
                        str(field),
                    )
                    result = hir.INVALID

                segment = hir.PathSegment(name=type_expression.attr, result=result)
                path.segments.append(segment)
                return result

            case ast.TypeCallNode():
                match type_expression.type:
                    case ast.TypeAttributeNode() | ast.TypeCallNode() | ast.NameNode():
                        field = self.create_path_resursive(path, type_expression.type)
                    case _:
                        field = self.lower_type_expression(type_expression.type)
                        assert not isinstance(field, hir.Path)

                        if isinstance(field, hir.TypeParameter):
                            self.report_error(type_expression, 'Cannot call type parameter')
                            return hir.INVALID

                segment = path.segments[-1]
                for argument in type_expression.args:
                    type = self.lower_type_expression(argument)
                    segment.arguments.append(type)

                return field

            case ast.NameNode():
                result = self.resolver.resolve_symbol(
                    type_expression.value,
                    include_local_declarations=False,
                    include_functions=False,
                    include_type_parameters=False,
                )
                if result is None:
                    self.report_error(
                        type_expression,
                        "Unable to resolve symbol {0}",
                        type_expression.value,
                    )
                    result = hir.INVALID

                assert not isinstance(
                    result, (hir.FunctionDef, hir.LocalDeclaration, hir.TypeParameter)
                )
                segment = hir.PathSegment(name=type_expression.value, result=result)
                path.segments.append(segment)
                return result

    def lower_type_expression(
        self,
        type_expression: ast.TypeExpressionNode,
    ) -> hir.HirType:
        match type_expression:
            case ast.TypeParameterNode():
                symbol = self.resolver.resolve_symbol(
                    type_expression.name,
                    include_local_declarations=False,
                    include_functions=False,
                )
                assert isinstance(symbol, hir.TypeParameter)
                return symbol

            case ast.TypeCallNode() | ast.TypeAttributeNode() | ast.NameNode():
                path = hir.Path()
                self.create_path_resursive(path, type_expression)
                return path

            case ast.ListTypeNode():
                elt = self.lower_type_expression(type_expression.elt)
                return hir.ListType(elt=elt)

    def lower_block(self, block: list[ast.StatementNode]) -> None:
        for statement in block:
            self.lower_statement(statement)

    def lower_statement(self, statement: ast.StatementNode) -> None:
        match statement:
            case ast.FunctionDefNode():
                function_def = self.hir_ctx.fields[statement.id]
                assert isinstance(function_def, hir.FunctionDef)
                self.resolver.enter_node(statement)

                for parameter in statement.parameters:
                    type = self.lower_type_expression(parameter.annotation)
                    function_def.parameters[parameter.name] = type

                function_def.returns = self.lower_type_expression(statement.returns)
                self.resolver.exit_node(statement)

    def lower_module(self) -> None:
        module = hir.ModuleDef()
        scope = self.resolver.create_scope(self.module.id, ScopeKind.MODULE)
        self.resolver.initialize_symbols_for_block(module, scope, self.module.body)

        self.resolver.enter_node(self.module)
        self.lower_block(self.module.body)
        self.resolver.exit_node(self.module)
