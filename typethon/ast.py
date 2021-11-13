from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Iterable, Optional, Union


@dataclass
class Module:
    body: list[Statement]


@dataclass
class FunctionDef:
    is_async: bool
    name: str
    params: Parameters
    body: list[Statement]
    decorators: list[Expression]
    returns: Expression


@dataclass
class ClassDef:
    name: str
    bases: list[Expression]
    kwargs: list[KwArgument]
    body: list[Statement]
    decorators: list[Expression]


@dataclass
class Return:
    value: Optional[Expression]


@dataclass
class Delete:
    targets: list[Expression]


@dataclass
class Assign:
    targets: list[Expression]
    value: Expression


@dataclass
class AugAssign:
    target: Expression
    op: Operator
    value: Expression


@dataclass
class AnnAssign:
    target: Expression
    annotation: Expression
    value: Optional[Expression]


@dataclass
class For:
    is_async: bool
    target: Expression
    iterator: Expression
    body: list[Statement]
    elsebody: list[Statement]


@dataclass
class While:
    condition: Expression
    body: list[Statement]
    elsebody: list[Statement]


@dataclass
class If:
    condition: Expression
    body: list[Statement]
    elsebody: list[Statement]


@dataclass
class With:
    is_async: bool
    items: list[WithItem]
    body: list[Statement]


@dataclass
class Raise:
    exc: Expression
    cause: Expression


@dataclass
class Try:
    body: list[Statement]
    handlers: list[ExceptHandler]
    elsebody: list[Statement]
    finalbody: list[Statement]


@dataclass
class Assert:
    condition: Expression
    msg: Optional[str]


@dataclass
class Import:
    names: list[Alias]


@dataclass
class ImportFrom:
    module: Optional[str]
    names: list[Alias]
    level: Optional[int]


@dataclass
class Global:
    names: list[str]


@dataclass
class Nonlocal:
    names: list[str]


@dataclass
class Expr:
    value: Expression


Statement = Union[FunctionDef, ClassDef, Return, Delete, Assign, AugAssign, AnnAssign, For, While,
                  If, With, Raise, Try, Assert, Import, ImportFrom, Global, Nonlocal, Expr]


@dataclass
class BoolOp:
    op: BoolOperator
    values: list[Expression]


@dataclass
class BinOp:
    left: Expression
    op: Operator
    right: Expression


@dataclass
class UnaryOp:
    op: UnaryOperator
    operand: Expression


@dataclass
class Lambda:
    params: Parameters
    body: Expression


@dataclass
class IfExp:
    condition: Expr
    body: Expr
    elsebody: Expr


@dataclass
class Dict:
    elts: list[DictElt]


@dataclass
class Set:
    elts: list[Expression]


@dataclass
class ListComp:
    elt: Expression
    generators: list[Comprehension]


@dataclass
class SetComp:
    elt: Expression
    generators: list[Comprehension]


@dataclass
class DictComp:
    elt: DictElt
    generators: list[Comprehension]


@dataclass
class GeneratorExp:
    elt: Expression
    generators: list[Comprehension]


@dataclass
class Await:
    value: Expression


@dataclass
class Yield:
    value: Optional[Expression]


@dataclass
class YieldFrom:
    value: Expression


@dataclass
class Compare:
    left: Expression
    ops: list[CmpOperator]
    comparators: list[Expression]


@dataclass
class Call:
    func: Expr
    args: list[Expr]
    kwargs: list[KwArgument]


@dataclass
class FormattedValue:
    value: Expression
    conversion: Optional[int]
    spec: Optional[Expression]


@dataclass
class JoinedStr:
    values: list[Expression]


@dataclass
class Constant:
    value: ConstantValueT


ConstantValueT = Union[None, Ellipsis, int, float, complex, bool, str, bytes,
                       Iterable['ConstantValueT']]


@dataclass
class Attribute:
    value: Expression
    attr: str
    ctx: ExprContext


@dataclass
class Subscript:
    value: Expression
    slice: Expression
    ctx: ExprContext


@dataclass
class Starred:
    value: Expression
    ctx: ExprContext


@dataclass
class Name:
    id: str
    ctx: ExprContext


@dataclass
class List:
    elts: list[Expression]
    ctx: ExprContext


@dataclass
class Tuple:
    elts: list[Expression]
    ctx: ExprContext


@dataclass
class Slice:
    start: Optional[int]
    stop: Optional[int]
    step: Optional[int]


Expression = Union[BoolOp, BinOp, UnaryOp, Lambda, IfExp, Dict, Set, ListComp, SetComp, DictComp,
                   GeneratorExp, Await, Yield, YieldFrom, Compare, Call, FormattedValue, JoinedStr,
                   Constant, Attribute, Subscript, Starred, Name, List, Tuple, Slice]


@dataclass
class Parameter:
    name: str
    annotation: Optional[Expression]
    default: Optional[Expression]


@dataclass
class Parameters:
    posonlyargs: list[Parameter]
    args: list[Parameter]
    vararg: Optional[Parameter]
    kwonlyargs: list[Parameter]
    kwarg: Optional[Parameter]


@dataclass
class KwArgument:
    name: Optional[str]
    value: Expression


@dataclass
class WithItem:
    contextmanager: Expression
    targets: list[Expression]


@dataclass
class ExceptHandler:
    type: Optional[Expression]
    target: Optional[str]
    body: list[Statement]


@dataclass
class Comprehension:
    is_async: bool
    target: Expression
    iterator: Expression
    ifs: list[Expression]


@dataclass
class Alias:
    name: str
    asname: str


@dataclass
class DictElt:
    key: Expression
    value: Expression


class ExprContext(enum.IntEnum):
    LOAD = enum.auto()
    STORE = enum.auto()
    DELETE = enum.auto()


class BoolOperator(enum.IntEnum):
    AND = enum.auto()
    OR = enum.auto()


class Operator(enum.IntEnum):
    ADD = enum.auto()
    SUB = enum.auto()
    MULT = enum.auto()
    MATMULT = enum.auto()
    DIV = enum.auto()
    MOD = enum.auto()
    POW = enum.auto()
    LSHIFT = enum.auto()
    RSHIFT = enum.auto()
    BITOR = enum.auto()
    BITXOR = enum.auto()
    BITAND = enum.auto()
    FLOORDIV = enum.auto()


class UnaryOperator(enum.IntEnum):
    INVERT = enum.auto()
    NOT = enum.auto()
    UADD = enum.auto()
    USUB = enum.auto()


class CmpOperator(enum.IntEnum):
    EQ = enum.auto()
    NOTEQ = enum.auto()
    LT = enum.auto()
    LTE = enum.auto()
    GT = enum.auto()
    GTE = enum.auto()
    IS = enum.auto()
    ISNOT = enum.auto()
    IN = enum.auto()
    NOTIN = enum.auto()
