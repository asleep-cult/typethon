import attr
from .initializer import TypeInitializer
from .. import asg


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
