import attr

from .. import asg
from .initializer import TypeInitializer


@attr.s(kw_only=True, slots=True)
class TypeChecker:
    init: TypeInitializer = attr.ib()

    def check_body(self, body: asg.AsgBody) -> None:
        for statement in body.statements:
            self.check_statement(statement)

    def check_statement(self, statement: asg.Statement) -> None:
        match statement:
            case asg.Local():
                ...
            case asg.While():
                ...
            case asg.If():
                ...
            case asg.Expr():
                self.synthesize_expression(statement.expr)

    def synthesize_expression(self, expression: asg.Expression) -> None:
        match expression:
            case asg.Attribute():
                if expression.result is not None and isinstance(expression.result, asg.DefResult):
                    print(self.init.type_of(expression.result.def_id))
