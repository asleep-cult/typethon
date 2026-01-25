from . import hir
from .resolution import SymbolResolver, ScopeKind
from ..syntax.typethon import ast


class HirLowering:
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

    def evaluate_type_expression(
        self,
        type_expression: ast.TypeExpressionNode,
    ) -> hir.Type:
        match type_expression:
            case ast.NameNode():
                symbol = self.resolver.resolve_symbol(
                    type_expression.value,
                    include_local_declarations=False,
                    include_functions=False,
                    include_type_parameters=False,
                )
                if symbol is None:
                    self.report_error(
                        type_expression,
                        'Unable to resolve type symbol `{0}`',
                        type_expression.value,
                    )
                    return hir.INVALID

                assert not isinstance(symbol, (hir.FunctionDef, hir.LocalDeclaration))
                return symbol

            case ast.TypeParameterNode():
                symbol = self.resolver.resolve_symbol(
                    type_expression.name,
                    include_local_declarations=False,
                    include_functions=False,
                )
                assert isinstance(symbol, hir.TypeParameter)
                return symbol

            case ast.TypeCallNode():
                type = self.evaluate_type_expression(type_expression.type)

            case ast.TypeAttributeNode():
                type = self.evaluate_type_expression(type_expression.type)
                symbol = self.resolver.resolve_attribute(type, type_expression.attr)
                if symbol is None:
                    self.report_error(
                        type_expression,
                        'Unable to resolve type symbol `{0}`',
                        type_expression.attr,
                    )
                    return hir.INVALID

                assert not isinstance(symbol, hir.FunctionDef)
                return symbol

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
                    type = self.evaluate_type_expression(parameter.annotation)
                    function_def.parameters[parameter.name] = type

                function_def.returns = self.evaluate_type_expression(statement.returns)
                self.resolver.exit_node(statement)

    def lower_module(self) -> None:
        module = hir.ModuleDef()
        scope = self.resolver.create_scope(self.module.id, ScopeKind.MODULE)
        self.resolver.initialize_symbols_for_block(module, scope, self.module.body)

        self.resolver.enter_node(self.module)
        self.lower_block(self.module.body)
        self.resolver.exit_node(self.module)
