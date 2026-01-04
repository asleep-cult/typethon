### Grammar
This directory contains the source for the LR(1) parser generator.
* `./parser.py`: Converts an LR grammar into an abstract syntax tree. Each rule in the grammar is represented by a rule node with an item for each production.
* `./generator.py`: Transforms the AST into terminal and nonterminal symbols and creates a parse table for each entrypoint. The parser generator works by mapping every possible terminal in a given state to a SHIFT, REDUCE, or ACCEPT action. The table is indexed by a tuple containing a state number and a terminal symbol, and returns tuple containing an action and a number. For a SHIFT action, the number represents the next state to shift to. For a REDUCE action, the number represents the id of the production to reduce by, and the next state can be found in the goto table.
* `./frozen.py`: Drastically simplified immutable versions of terminals, symbols, and productions that are used by the parse table. This allows the table to be dumped and loaded if necessary.
* `./automaton.py`: A pushdown automaton that parses a source text based on the parse table provided.

#### Grammar Syntax
```
@start: expr  # entrypoint is denoted with @ before nonterminal name

expr:
    | expr '+' term  # multiple productions are denoted by a newline and an expression
    | term           # the | before the first production is optional

term:
    | term '*' factor  # nonterminals (tokens or keywords) are deonted in quotes
    | factor  # terminals can be referred to by name

factor:
    | '(' expr ')'
    | IDENTIFIER  # standard terminals are fully capitalized

# By default, the automaton discards everything from the resulting parse tree.
# To capture a node, the ! prefix must be used.

@start: !'+'  # For example, this would result in Node([PLUS])

# A transformer for a production can be specified using a directive before
# the rule item.
term:
    #[create_constant]
    | !'True'  # This would call the transformer named create_constant

# Each captured item is passed to the transformer function as an individual argument
# If no transformer is specified for a group of items, the default behavior depends on
# how many captued items there are:
# * If there is only one captured item, the item itself is used
# * If there are multiple items, a new node is created using the list of items

# e? means optional e, this is equivalent to:
option:
    #[@option]
    | ε
    #[@option]
    | e
# Where @option is a builtin transformer that creates OptionNode(None)
# or OptionNode(e)

# e* means zero or more e, this is equivalent to:
zero_or_more:
    #[@flatten]
    | ε
    #[@flatten]
    | zero_or_more e

# e+ means one or more e, this is equivalent to:
one_or_more:
    #[@flatten]
    | e
    #[@flatten]
    | one_or_more e

# Where @flatten is a builtin transformer that creates FlattenNode([e1, e2, en])
```
