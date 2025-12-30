from __future__ import annotations

import attr
import enum
import typing
from collections import defaultdict

from . import ast
from .symbols import (
    Production,
    TerminalSymbol,
    NonterminalSymbol,
    Symbol,
    EPSILON,
    EOF,
)

KeywordT = typing.TypeVar('KeywordT', bound=enum.IntEnum)
ExpressionT = typing.TypeVar('ExpressionT', bound=ast.ExpressionNode[typing.Any])


@attr.s(kw_only=True, slots=True, hash=True, eq=True)
class ParserItem:
    production: Production = attr.ib(repr=False)
    position: int = attr.ib()
    lookahead: TerminalSymbol = attr.ib()

    def __str__(self) -> str:
        parts: typing.List[str] = []

        for symbol in self.production.rhs:
            if isinstance(symbol, NonterminalSymbol):
                parts.append(symbol.name)
            else:
                parts.append(str(symbol))

        parts.insert(self.position, '*')
        string = ' '.join(parts)
        return f'[{self.production.lhs.name} -> {string}], {self.lookahead}'

    def current_symbol(self) -> typing.Optional[Symbol]:
        if len(self.production.rhs) > self.position:
            return self.production.rhs[self.position]


class Generator(typing.Generic[KeywordT]):
    def __init__(self, rules: typing.List[ast.RuleNode[KeywordT]]) -> None:
        self.rules = rules
        self.nonterminals: typing.Dict[str, NonterminalSymbol] = {}
        self.epsilon_nonterminals: typing.Set[NonterminalSymbol] = set()
        self.first_sets: typing.Dict[NonterminalSymbol, typing.Set[TerminalSymbol]] = {}

        self.transitions: typing.Dict[
            Symbol, typing.List[typing.Tuple[typing.Set[ParserItem], typing.Set[ParserItem]]]
        ] = defaultdict(list)

    def initialize_nonterminals(self) -> None:
        for rule in self.rules:
            nonterminal = NonterminalSymbol(name=rule.name, entrypoint=rule.entrypoint)
            self.nonterminals[nonterminal.name] = nonterminal

    def initialize_productions(self) -> None:
        for rule in self.rules:
            self.initialize_productions_for_rule(rule)

    def initialize_productions_for_rule(self, rule: ast.RuleNode[KeywordT]) -> None:
        nonterminal = self.nonterminals[rule.name]

        for item in rule.items:
            production = Production(lhs=nonterminal)
            self.add_symbols_for_expression(production.rhs, item.expression)
            nonterminal.productions.append(production)

    def add_symbols_for_expression(
        self,
        symbols: typing.List[Symbol],
        expression: ast.ExpressionNode[KeywordT],
    ) -> None:
        match expression:
            case ast.StarNode():
                # star-a:b = nonterminal
                nonterminal = NonterminalSymbol(
                    name=f'star-{expression.startpos}:{expression.endpos}'
                )
                self.nonterminals[nonterminal.name] = nonterminal
                symbols.append(nonterminal)
                # | ()
                empty_production = Production(lhs=nonterminal, rhs=[EPSILON])
                nonterminal.productions.append(empty_production)
                # | expr
                production = Production(lhs=nonterminal)
                self.add_symbols_for_expression(production.rhs, expression.expression)
                nonterminal.productions.append(production)
                # | nonterminal
                production = Production(lhs=nonterminal, rhs=[nonterminal])
                nonterminal.productions.append(production)

            case ast.PlusNode():
                # plus-a:b = nonterminal
                nonterminal = NonterminalSymbol(
                    name=f'plus-{expression.startpos}-{expression.endpos}'
                )
                self.nonterminals[nonterminal.name] = nonterminal
                symbols.append(nonterminal)
                # | expr
                production = Production(lhs=nonterminal)
                self.add_symbols_for_expression(production.rhs, expression.expression)
                nonterminal.productions.append(production)
                # | nonterminal
                production = Production(lhs=nonterminal, rhs=[nonterminal])
                nonterminal.productions.append(production)

            case ast.OptionalNode():
                # optional-a:b = nonterminal
                nonterminal = NonterminalSymbol(
                    name=f'optional-{expression.startpos}-{expression.endpos}'
                )
                self.nonterminals[nonterminal.name] = nonterminal
                symbols.append(nonterminal)
                # | ()
                empty_production = Production(lhs=nonterminal, rhs=[EPSILON])
                nonterminal.productions.append(empty_production)
                # | expr
                production = Production(lhs=nonterminal)
                self.add_symbols_for_expression(production.rhs, expression.expression)
                nonterminal.productions.append(production)

            case ast.AlternativeNode():
                # plus-a:b = nonterminal
                nonterminal = NonterminalSymbol(
                    name=f'alternative-{expression.startpos}-{expression.endpos}'
                )
                self.nonterminals[nonterminal.name] = nonterminal
                symbols.append(nonterminal)
                # | lhs
                production = Production(lhs=nonterminal)
                self.add_symbols_for_expression(production.rhs, expression.lhs)
                nonterminal.productions.append(production)
                # | rhs
                production = Production(lhs=nonterminal)
                self.add_symbols_for_expression(production.rhs, expression.rhs)
                nonterminal.productions.append(production)

            case ast.GroupNode():
                for expression in expression.expressions:
                    self.add_symbols_for_expression(symbols, expression)

            case ast.KeywordNode():
                symbols.append(TerminalSymbol(kind=expression.keyword))

            case ast.TokenNode():
                symbols.append(TerminalSymbol(kind=expression.kind))

            case ast.NameNode():
                if expression.value not in self.nonterminals:
                    raise ValueError(f'{expression.value!r} is not a valid nonterminal symbol')

                symbols.append(self.nonterminals[expression.value])

    def compute_epsilon_nonterminals(self, nonterminals: typing.Set[NonterminalSymbol]) -> None:
        # First, add every nonterminal with at least one production containing epsilon
        for nonterminal in self.nonterminals.values():
            if any(EPSILON in production.rhs for production in nonterminal.productions):
                nonterminals.add(nonterminal)

        changed = True
        while changed:
            changed = False

            for nonterminal in self.nonterminals.values():
                # Next, add every nonterminal with at least one production such that all symbols
                # in the production are already within the epsilon nonterminals set
                if any(nonterminals.issuperset(production.rhs) for production in nonterminal.productions):
                    changed = nonterminal not in nonterminals
                    nonterminals.add(nonterminal)

    def compute_first_sets(
        self,
        first_sets: typing.Dict[NonterminalSymbol, typing.Set[TerminalSymbol]],
    ) -> None:
        for nonterminal in self.nonterminals.values():
            first_set: typing.Set[TerminalSymbol] = set()
            first_sets[nonterminal] = first_set

            for production in nonterminal.productions:
                for symbol in production.rhs:
                    if isinstance(symbol, TerminalSymbol):
                        first_set.add(symbol)

                    if symbol not in self.epsilon_nonterminals:
                        break

        changed = True
        while changed:
            changed = False
            for nonterminal in self.nonterminals.values():
                first_set = first_sets[nonterminal]

                for production in nonterminal.productions:
                    for symbol in production.rhs:
                        if isinstance(symbol, NonterminalSymbol):
                            length = len(first_set)
                            first_set.update(first_sets[symbol])
                            changed |= length != len(first_set)

                        if symbol not in self.epsilon_nonterminals:
                            break

    def get_first_set(self, symbols: typing.List[Symbol]) -> typing.Set[TerminalSymbol]:
        result: typing.Set[TerminalSymbol] = set()

        for symbol in symbols:
            if isinstance(symbol, TerminalSymbol):
                result.add(symbol)
            else:
                result.update(self.first_sets[symbol])

            if symbol not in self.epsilon_nonterminals:
                break

        return result

    def compute_follow_set(self, follow: typing.Set[TerminalSymbol], symbol: Symbol) -> None:
        if (
            isinstance(symbol, NonterminalSymbol)
            and symbol.entrypoint
        ):
            follow.add(EOF)

        for nonterminal in self.nonterminals.values():
            for production in nonterminal.productions:
                if symbol not in production.rhs:
                    continue

                index = production.rhs.index(symbol)
                if len(production.rhs) > index + 1:
                    following_symbol = production.rhs[index + 1]
                    first_rhsi = self.get_first_set([following_symbol])

                    if EPSILON in first_rhsi:
                        first_rhsi.remove(EPSILON)
                        self.compute_follow_set(follow, nonterminal)

                    follow.update(first_rhsi)
                else:
                    self.compute_follow_set(follow, nonterminal)

    def compute_closure(self, items: typing.Set[ParserItem]) -> typing.Set[ParserItem]:
        # https://web.cecs.pdx.edu/~harry/compilers/slides/SyntaxPart3.pdf
        # items: {S -> * E EOF}
        result = items.copy()

        changed = True
        while changed:
            changed = False
            for item in result.copy():
                current_symbol = item.current_symbol()
                if not isinstance(current_symbol, NonterminalSymbol):
                    continue

                for production in current_symbol.productions:
                    trailing_symbols = item.production.rhs[item.position + 1:]
                    trailing_symbols.append(item.lookahead)

                    first_lookahead = self.get_first_set(trailing_symbols)
                    for lookahead in first_lookahead:
                        inner_item = ParserItem(production=production, position=0, lookahead=lookahead)
                        length = len(result)
                        result.add(inner_item)
                        changed |= length != len(result)

        return result

    def compute_goto(self, closure: typing.Set[ParserItem], symbol: Symbol) -> typing.Set[ParserItem]:
        result: typing.Set[ParserItem] = set()

        for item in closure:
            current_symbol = item.current_symbol()
            if current_symbol is symbol:
                updated_item = ParserItem(
                    production=item.production,
                    position=item.position + 1,
                    lookahead=item.lookahead,
                )
                result.add(updated_item)

        return self.compute_closure(result)

    def generate_canonical_collection(
        self,
        entrypoint: typing.Set[ParserItem],
    ) -> typing.List[typing.Set[ParserItem]]:
        canonical_collection: typing.List[typing.Set[ParserItem]] = []
        canonical_collection.append(self.compute_closure(entrypoint))

        changed = True
        while changed:
            changed = False

            for collection in canonical_collection:
                for item in collection:
                    current_symbol = item.current_symbol()
                    if current_symbol is None:
                        continue

                    tempoaray_closure = self.compute_goto(collection, current_symbol)
                    if tempoaray_closure not in canonical_collection:
                        canonical_collection.append(tempoaray_closure)

                        transitions = self.transitions[current_symbol]
                        transitions.append((collection, tempoaray_closure))
                        changed = True

        return canonical_collection

    def generate_symbols(self) -> None:
        self.initialize_nonterminals()
        self.initialize_productions()
