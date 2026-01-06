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
    | term '*' factor  # terminals (tokens or keywords) are deonted in quotes
    | factor  # nonterminals can be referred to by name

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
    #[@sequence]
    | ε
    #[@sequence]
    | zero_or_more e

# Where @flatten is a builtin transformer that creates FlattenNode([e1, e2, ..., en])

# e+ means one or more e, this is equivalent to:
one_or_more:
    #[@prepend]
    | e e*

# Where @prepend is a builtin transformer that prepends e to SequenceNode
```

### Parser generator profiling info
```
CPython
DEBUG:typethon.syntax.typethon.parser:Generated tables after 39.15 seconds
         75221307 function calls (75220808 primitive calls) in 39.159 seconds

   Ordered by: standard name

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
      128    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.CaptureNode>:24(__init__)
       52    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.GroupNode>:24(__init__)
       20    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.KeywordNode>:24(__init__)
      100    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.NameNode>:24(__init__)
       11    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.OptionalNode>:24(__init__)
        6    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.PlusNode>:24(__init__)
       79    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.RuleItemNode>:25(__init__)
       33    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.RuleNode>:26(__init__)
        3    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.StarNode>:24(__init__)
       59    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.TokenNode>:24(__init__)
      125    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.frozen.FrozenProduction>:33(__init__)
   232176    0.064    0.000    0.064    0.000 <attrs generated methods typethon.grammar.frozen.FrozenSymbol>:16(__eq__)
   272964    0.093    0.000    0.144    0.000 <attrs generated methods typethon.grammar.frozen.FrozenSymbol>:23(__hash__)
   132888    0.023    0.000    0.023    0.000 <attrs generated methods typethon.grammar.frozen.FrozenSymbol>:29(__init__)
     1172    0.001    0.000    0.001    0.000 <attrs generated methods typethon.grammar.generator.ParserState>:23(__init__)
        1    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.generator.TableBuilder>:22(__init__)
       59    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.symbols.NonterminalSymbol>:1(__init__)
      125    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.symbols.Production>:16(__init__)
     8008    0.003    0.000    0.003    0.000 <attrs generated methods typethon.grammar.symbols.TerminalSymbol>:16(__eq__)
       83    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.symbols.TerminalSymbol>:23(__init__)
       31    0.000    0.000    0.000    0.000 <attrs generated methods typethon.syntax.tokens.DedentToken>:22(__init__)
       55    0.000    0.000    0.000    0.000 <attrs generated methods typethon.syntax.tokens.DirectiveToken>:22(__init__)
      146    0.000    0.000    0.000    0.000 <attrs generated methods typethon.syntax.tokens.IdentifierToken>:23(__init__)
       31    0.000    0.000    0.000    0.000 <attrs generated methods typethon.syntax.tokens.IndentToken>:22(__init__)
       66    0.000    0.000    0.000    0.000 <attrs generated methods typethon.syntax.tokens.StringToken>:23(__init__)
      388    0.000    0.000    0.000    0.000 <attrs generated methods typethon.syntax.tokens.TokenData>:22(__init__)
        8    0.000    0.000    0.000    0.000 <frozen _collections_abc>:439(__subclasshook__)
      837    0.001    0.000    0.004    0.000 <frozen abc>:117(__instancecheck__)
      8/1    0.000    0.000    0.000    0.000 <frozen abc>:121(__subclasscheck__)
        2    0.000    0.000    0.000    0.000 <frozen abc>:146(update_abstractmethods)
        1    0.000    0.000    0.000    0.000 <frozen codecs>:263(__init__)
      861    0.003    0.000    0.005    0.000 <frozen genericpath>:157(_splitext)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:1128(find_spec)
        4    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:1222(__enter__)
        4    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:1226(__exit__)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:124(setdefault)
        1    0.000    0.000    0.001    0.001 <frozen importlib._bootstrap>:1240(_find_spec)
        1    0.000    0.000    0.007    0.007 <frozen importlib._bootstrap>:1304(_find_and_load_unlocked)
        1    0.000    0.000    0.007    0.007 <frozen importlib._bootstrap>:1349(_find_and_load)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:158(__init__)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:162(__enter__)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:173(__exit__)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:232(__init__)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:304(acquire)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:372(release)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:412(__init__)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:416(__enter__)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:420(__exit__)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:426(_get_module_lock)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:445(cb)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:48(_new_module)
        2    0.000    0.000    0.004    0.002 <frozen importlib._bootstrap>:480(_call_with_frames_removed)
       16    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:491(_verbose_message)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:599(__init__)
        2    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:632(cached)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:645(parent)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:653(has_location)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:733(_init_module_attrs)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:74(__new__)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:79(__init__)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:806(module_from_spec)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:82(remove)
        1    0.000    0.000    0.006    0.006 <frozen importlib._bootstrap>:911(_load_unlocked)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:982(find_spec)
       15    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:101(_path_join)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:1017(create_module)
        1    0.000    0.000    0.005    0.005 <frozen importlib._bootstrap_external>:1020(exec_module)
        1    0.000    0.000    0.002    0.002 <frozen importlib._bootstrap_external>:1093(get_code)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:1184(__init__)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:1209(get_filename)
        1    0.000    0.000    0.001    0.001 <frozen importlib._bootstrap_external>:1214(get_data)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:1233(path_stats)
        2    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:137(_path_split)
        6    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:139(<genexpr>)
        5    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:145(_path_stat)
        4    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:1500(_path_importer_cache)
        1    0.000    0.000    0.001    0.001 <frozen importlib._bootstrap_external>:1522(_get_spec)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:155(_path_is_mode_type)
        1    0.000    0.000    0.001    0.001 <frozen importlib._bootstrap_external>:1551(find_spec)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:1619(_get_spec)
        3    0.000    0.000    0.001    0.000 <frozen importlib._bootstrap_external>:1624(find_spec)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:164(_path_isfile)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:177(_path_isabs)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:190(_path_abspath)
        2    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:513(cache_from_source)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:642(_get_cached)
        3    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:67(_relax_case)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:674(_check_name_wrapper)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:697(_classify_pyc)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:730(_validate_timestamp_pyc)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:782(_compile_bytecode)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:833(spec_from_file_location)
        3    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:89(_unpack_uint32)
      861    0.008    0.000    0.012    0.000 <frozen ntpath>:222(split)
      861    0.002    0.000    0.008    0.000 <frozen ntpath>:243(splitext)
      861    0.001    0.000    0.014    0.000 <frozen ntpath>:254(basename)
      861    0.001    0.000    0.001    0.000 <frozen ntpath>:34(_get_bothseps)
     2583    0.006    0.000    0.020    0.000 <frozen ntpath>:50(normcase)
        1    0.000    0.000    0.000    0.000 <frozen ntpath>:99(join)
        1    0.000    0.000    0.000    0.000 <string>:1(<module>)
        1    0.000    0.000    0.000    0.000 <string>:1(__create_fn__)
        1    0.000    0.000    0.000    0.000 __init__.py:101(find_spec)
      861    0.006    0.000    0.222    0.000 __init__.py:1011(handle)
        1    0.000    0.000    0.000    0.000 __init__.py:108(<lambda>)
      861    0.005    0.000    0.010    0.000 __init__.py:1131(flush)
      861    0.006    0.000    0.215    0.000 __init__.py:1139(emit)
      861    0.001    0.000    0.002    0.000 __init__.py:129(getLevelName)
        3    0.000    0.000    0.000    0.000 __init__.py:1354(disable)
      838    0.008    0.000    0.333    0.000 __init__.py:1498(debug)
       23    0.000    0.000    0.010    0.000 __init__.py:1510(info)
      861    0.007    0.000    0.037    0.000 __init__.py:1592(findCaller)
      861    0.003    0.000    0.061    0.000 __init__.py:1626(makeRecord)
      861    0.005    0.000    0.333    0.000 __init__.py:1641(_log)
      861    0.003    0.000    0.231    0.000 __init__.py:1667(handle)
      861    0.001    0.000    0.003    0.000 __init__.py:167(<lambda>)
      861    0.005    0.000    0.227    0.000 __init__.py:1721(callHandlers)
        3    0.000    0.000    0.000    0.000 __init__.py:1751(getEffectiveLevel)
      861    0.001    0.000    0.001    0.000 __init__.py:1765(isEnabledFor)
     2583    0.006    0.000    0.026    0.000 __init__.py:197(_is_internal_frame)
      861    0.019    0.000    0.058    0.000 __init__.py:298(__init__)
      861    0.004    0.000    0.004    0.000 __init__.py:391(getMessage)
      861    0.001    0.000    0.001    0.000 __init__.py:455(usesTime)
      861    0.005    0.000    0.005    0.000 __init__.py:463(_format)
      861    0.001    0.000    0.006    0.000 __init__.py:470(format)
      861    0.001    0.000    0.003    0.000 __init__.py:677(usesTime)
      861    0.001    0.000    0.007    0.000 __init__.py:683(formatMessage)
      861    0.002    0.000    0.016    0.000 __init__.py:699(format)
     1722    0.001    0.000    0.001    0.000 __init__.py:840(filter)
      861    0.001    0.000    0.017    0.000 __init__.py:988(format)
        2    0.000    0.000    0.000    0.000 _abc.py:130(with_segments)
        3    0.000    0.000    0.000    0.000 _local.py:117(__init__)
        1    0.000    0.000    0.000    0.000 _local.py:148(__truediv__)
        1    0.000    0.000    0.000    0.000 _local.py:166(__fspath__)
        1    0.000    0.000    0.000    0.000 _local.py:227(__str__)
        2    0.000    0.000    0.000    0.000 _local.py:237(_format_parsed_parts)
        1    0.000    0.000    0.000    0.000 _local.py:245(_from_parsed_parts)
        1    0.000    0.000    0.000    0.000 _local.py:252(_from_parsed_string)
        2    0.000    0.000    0.000    0.000 _local.py:257(_parse_path)
        2    0.000    0.000    0.000    0.000 _local.py:277(_raw_path)
        2    0.000    0.000    0.000    0.000 _local.py:289(drive)
        2    0.000    0.000    0.000    0.000 _local.py:298(root)
        2    0.000    0.000    0.000    0.000 _local.py:307(_tail)
        1    0.000    0.000    0.000    0.000 _local.py:329(parent)
        3    0.000    0.000    0.000    0.000 _local.py:498(__init__)
        3    0.000    0.000    0.000    0.000 _local.py:505(__new__)
        1    0.000    0.000    0.007    0.007 cProfile.py:42(print_stats)
        1    0.000    0.000    0.000    0.000 cProfile.py:54(create_stats)
        1    0.000    0.000    0.000    0.000 cp1252.py:22(decode)
       11    0.000    0.000    0.000    0.000 dataclasses.py:1111(<genexpr>)
       11    0.000    0.000    0.000    0.000 dataclasses.py:1172(<genexpr>)
        2    0.000    0.000    0.000    0.000 dataclasses.py:1277(dataclass)
        2    0.000    0.000    0.003    0.001 dataclasses.py:1294(wrap)
        9    0.000    0.000    0.000    0.000 dataclasses.py:288(__init__)
        2    0.000    0.000    0.000    0.000 dataclasses.py:351(__init__)
        9    0.000    0.000    0.000    0.000 dataclasses.py:383(field)
        2    0.000    0.000    0.000    0.000 dataclasses.py:407(_fields_in_init_order)
       11    0.000    0.000    0.000    0.000 dataclasses.py:411(<genexpr>)
        2    0.000    0.000    0.000    0.000 dataclasses.py:412(<genexpr>)
        2    0.000    0.000    0.000    0.000 dataclasses.py:416(_tuple_str)
        2    0.000    0.000    0.000    0.000 dataclasses.py:429(__init__)
        8    0.000    0.000    0.000    0.000 dataclasses.py:437(add_fn)
        2    0.000    0.000    0.001    0.001 dataclasses.py:470(add_fns_to_class)
        9    0.000    0.000    0.000    0.000 dataclasses.py:519(_field_assign)
        9    0.000    0.000    0.000    0.000 dataclasses.py:531(_field_init)
        9    0.000    0.000    0.000    0.000 dataclasses.py:591(_init_param)
        2    0.000    0.000    0.000    0.000 dataclasses.py:610(_init_fn)
        9    0.000    0.000    0.000    0.000 dataclasses.py:691(_is_classvar)
        9    0.000    0.000    0.000    0.000 dataclasses.py:699(_is_initvar)
        9    0.000    0.000    0.000    0.000 dataclasses.py:705(_is_kw_only)
        9    0.000    0.000    0.000    0.000 dataclasses.py:768(_get_field)
       10    0.000    0.000    0.000    0.000 dataclasses.py:865(_set_new_attribute)
        2    0.000    0.000    0.000    0.000 dataclasses.py:886(_hash_add)
        2    0.000    0.000    0.003    0.001 dataclasses.py:929(_process_class)
      204    0.000    0.000    0.000    0.000 enum.py:1156(__new__)
        9    0.000    0.000    0.000    0.000 enum.py:1217(__init__)
       22    0.000    0.000    0.000    0.000 enum.py:1277(__str__)
      556    0.000    0.000    0.000    0.000 enum.py:1312(__hash__)
       83    0.000    0.000    0.000    0.000 enum.py:1332(name)
      588    0.000    0.000    0.000    0.000 enum.py:1589(_get_value)
      196    0.000    0.000    0.001    0.000 enum.py:1607(__and__)
        1    0.000    0.000    0.000    0.000 enum.py:1737(_simple_enum)
        1    0.000    0.000    0.000    0.000 enum.py:1753(convert_class)
       83    0.000    0.000    0.000    0.000 enum.py:199(__get__)
        9    0.000    0.000    0.000    0.000 enum.py:37(_is_descriptor)
       14    0.000    0.000    0.000    0.000 enum.py:47(_is_dunder)
        1    0.000    0.000    0.000    0.000 enum.py:498(__new__)
        9    0.000    0.000    0.000    0.000 enum.py:58(_is_sunder)
      204    0.000    0.000    0.000    0.000 enum.py:695(__call__)
        9    0.000    0.000    0.000    0.000 enum.py:78(_is_private)
       13    0.000    0.000    0.000    0.000 enum.py:829(__setattr__)
        1    0.000    0.000    0.000    0.000 frozen.py:116(__init__)
        1    0.000    0.000    0.000    0.000 frozen.py:15(__init__)
   132829    0.157    0.000    0.279    0.000 frozen.py:34(get_frozen_terminal)
     3778    0.001    0.000    0.001    0.000 frozen.py:43(get_frozen_nonterminal)
       59    0.000    0.000    0.000    0.000 frozen.py:56(create_frozen_nonterminal)
      125    0.000    0.000    0.000    0.000 frozen.py:64(create_frozen_production)
      101    0.000    0.000    0.000    0.000 frozen.py:82(add_production_action)
   501255    0.561    0.000    0.830    0.000 generator.py:100(iter_symbols)
     1172    0.001    0.000    0.002    0.000 generator.py:115(iter_terminal_items_with_symbol)
   116321    0.035    0.000    0.035    0.000 generator.py:118(<genexpr>)
     1172    0.001    0.000    0.002    0.000 generator.py:146(iter_completed_items)
     7902    0.005    0.000    0.008    0.000 generator.py:156(get_effective_map)
  4592659    9.929    0.000   18.389    0.000 generator.py:177(add_item)
        1    0.000    0.000    0.000    0.000 generator.py:234(add_accept)
   115149    0.209    0.000    0.734    0.000 generator.py:250(add_shift)
    17679    0.030    0.000    0.112    0.000 generator.py:289(add_reduce)
     3653    0.005    0.000    0.012    0.000 generator.py:329(add_goto)
        1    0.000    0.000    0.000    0.000 generator.py:367(__init__)
        1    0.000    0.000    0.000    0.000 generator.py:413(initialize_nonterminals)
        1    0.000    0.000    0.002    0.002 generator.py:417(initialize_productions)
        1    0.000    0.000    0.002    0.002 generator.py:421(generate_symbols)
        1    0.000    0.000    0.001    0.001 generator.py:425(generate_frozen_symbols)
       15    0.000    0.000    0.000    0.000 generator.py:438(should_capture_uninlined_expression)
       30    0.000    0.000    0.000    0.000 generator.py:442(<genexpr>)
      125    0.000    0.000    0.000    0.000 generator.py:444(create_production)
       33    0.000    0.000    0.002    0.000 generator.py:454(initialize_productions_for_rule)
        9    0.000    0.000    0.000    0.000 generator.py:465(add_new_star_expression)
   395/79    0.001    0.000    0.002    0.000 generator.py:499(add_symbols_for_expression)
     7903    0.022    0.000    0.022    0.000 generator.py:53(__init__)
        1    0.000    0.000    0.000    0.000 generator.py:615(compute_epsilon_nonterminals)
      144    0.000    0.000    0.000    0.000 generator.py:618(<genexpr>)
      144    0.000    0.000    0.000    0.000 generator.py:628(<genexpr>)
        1    0.003    0.003    0.005    0.005 generator.py:635(compute_first_sets)
   694560    0.357    0.000    0.457    0.000 generator.py:65(__eq__)
     1307    0.004    0.000    0.006    0.000 generator.py:664(get_first_set)
     7903    2.985    0.000   20.977    0.003 generator.py:682(compute_closure)
     7902    0.287    0.000   22.827    0.003 generator.py:759(compute_goto)
     1172    0.007    0.000    0.009    0.000 generator.py:774(create_state)
        1    5.091    5.091   35.453   35.453 generator.py:793(compute_canonical_collection)
        1    0.179    0.179   39.108   39.108 generator.py:838(compute_tables)
  8884404    1.182    0.000    1.182    0.000 generator.py:868(<genexpr>)
        1    0.000    0.000   39.117   39.117 generator.py:873(generate)
        1    0.000    0.000   39.151   39.151 generator.py:896(generate_from_grammar)
     7903    0.015    0.000    0.015    0.000 generator.py:91(get_intern_items)
     9074    0.012    0.000    0.012    0.000 generator.py:94(iter_interned_items)
   326204    0.104    0.000    0.104    0.000 generator.py:98(<genexpr>)
        8    0.000    0.000    0.000    0.000 inspect.py:1436(formatannotation)
        3    0.000    0.000    0.000    0.000 inspect.py:176(get_annotations)
        2    0.000    0.000    0.000    0.000 inspect.py:1779(_check_class)
        1    0.000    0.000    0.000    0.000 inspect.py:1786(_shadowed_dict_from_weakref_mro_tuple)
        2    0.000    0.000    0.000    0.000 inspect.py:1805(_shadowed_dict)
        2    0.000    0.000    0.000    0.000 inspect.py:1818(getattr_static)
        3    0.000    0.000    0.000    0.000 inspect.py:2003(_signature_get_user_defined_method)
        1    0.000    0.000    0.000    0.000 inspect.py:2105(_signature_bound_method)
        1    0.000    0.000    0.000    0.000 inspect.py:2131(_signature_is_builtin)
        1    0.000    0.000    0.000    0.000 inspect.py:2145(_signature_is_functionlike)
        1    0.000    0.000    0.000    0.000 inspect.py:2383(_signature_from_function)
        1    0.000    0.000    0.000    0.000 inspect.py:2478(_descriptor_get)
      3/1    0.000    0.000    0.000    0.000 inspect.py:2487(_signature_from_callable)
        8    0.000    0.000    0.000    0.000 inspect.py:2754(__init__)
       15    0.000    0.000    0.000    0.000 inspect.py:2807(name)
        7    0.000    0.000    0.000    0.000 inspect.py:2811(default)
       23    0.000    0.000    0.000    0.000 inspect.py:2819(kind)
        7    0.000    0.000    0.000    0.000 inspect.py:2841(__str__)
        3    0.000    0.000    0.000    0.000 inspect.py:302(isclass)
        2    0.000    0.000    0.000    0.000 inspect.py:3042(__init__)
        9    0.000    0.000    0.000    0.000 inspect.py:3089(<genexpr>)
        1    0.000    0.000    0.000    0.000 inspect.py:3094(from_callable)
        1    0.000    0.000    0.000    0.000 inspect.py:310(ismethoddescriptor)
        2    0.000    0.000    0.000    0.000 inspect.py:3102(parameters)
        2    0.000    0.000    0.000    0.000 inspect.py:3106(return_annotation)
        1    0.000    0.000    0.000    0.000 inspect.py:3110(replace)
        1    0.000    0.000    0.000    0.000 inspect.py:3315(__str__)
        1    0.000    0.000    0.000    0.000 inspect.py:3318(format)
        1    0.000    0.000    0.000    0.000 inspect.py:3373(signature)
        3    0.000    0.000    0.000    0.000 inspect.py:386(isfunction)
        1    0.000    0.000    0.000    0.000 inspect.py:534(isbuiltin)
        6    0.000    0.000    0.000    0.000 inspect.py:764(unwrap)
        1    0.000    0.000    0.034    0.034 parser.py:101(parse_rules)
       33    0.001    0.000    0.034    0.001 parser.py:108(parse_rule)
      110    0.000    0.000    0.008    0.000 parser.py:187(parse_rule_action)
    88/79    0.000    0.000    0.017    0.000 parser.py:195(parse_expression)
    88/79    0.000    0.000    0.017    0.000 parser.py:212(parse_expression_group)
  316/169    0.001    0.000    0.014    0.000 parser.py:236(parse_expression_group_item)
        1    0.000    0.000    0.000    0.000 parser.py:24(__init__)
      325    0.000    0.000    0.005    0.000 parser.py:266(parse_expression_suffix)
      179    0.000    0.000    0.001    0.000 parser.py:295(parse_atom)
        1    0.000    0.000    0.034    0.034 parser.py:305(parse_from_source)
      113    0.000    0.000    0.000    0.000 parser.py:42(parse_identifier)
       66    0.000    0.000    0.000    0.000 parser.py:64(parse_string)
        1    0.000    0.000   39.152   39.152 parser.py:71(load_parser_tables)
      655    0.001    0.000    0.029    0.000 parser.py:75(scan_no_whitespace)
      654    0.000    0.000    0.001    0.000 parser.py:83(scan_token)
     1370    0.001    0.000    0.029    0.000 parser.py:95(peek_token)
        1    0.000    0.000    0.004    0.004 pstats.py:1(<module>)
        1    0.000    0.000    0.000    0.000 pstats.py:108(__init__)
        1    0.000    0.000    0.000    0.000 pstats.py:118(init)
        1    0.000    0.000    0.000    0.000 pstats.py:137(load_stats)
        1    0.000    0.000    0.000    0.000 pstats.py:36(SortKey)
        9    0.000    0.000    0.000    0.000 pstats.py:48(__new__)
        1    0.000    0.000    0.000    0.000 pstats.py:520(TupleComp)
        1    0.000    0.000    0.000    0.000 pstats.py:58(FunctionProfile)
        1    0.000    0.000    0.000    0.000 pstats.py:68(StatsProfile)
        1    0.000    0.000    0.000    0.000 pstats.py:74(Stats)
        2    0.000    0.000    0.000    0.000 reprlib.py:12(decorating_function)
        2    0.000    0.000    0.000    0.000 reprlib.py:9(recursive_repr)
        1    0.000    0.000    0.000    0.000 scanner.py:102(create_lookup_table)
     8420    0.003    0.000    0.004    0.000 scanner.py:127(is_eof)
    10416    0.003    0.000    0.005    0.000 scanner.py:130(char_at)
     6333    0.003    0.000    0.006    0.000 scanner.py:136(peek_char)
     4083    0.003    0.000    0.007    0.000 scanner.py:139(consume_char)
      959    0.004    0.000    0.014    0.000 scanner.py:147(consume_while)
       66    0.000    0.000    0.000    0.000 scanner.py:163(string_terminated)
      263    0.001    0.000    0.003    0.000 scanner.py:176(scan_indentation)
      146    0.000    0.000    0.007    0.000 scanner.py:235(identifier_or_string)
      203    0.000    0.000    0.001    0.000 scanner.py:339(newline)
      931    0.000    0.000    0.000    0.000 scanner.py:35(is_whitespace)
       66    0.000    0.000    0.002    0.000 scanner.py:351(string)
       60    0.000    0.000    0.006    0.000 scanner.py:388(comment)
      807    0.000    0.000    0.000    0.000 scanner.py:39(is_indent)
     1321    0.000    0.000    0.000    0.000 scanner.py:394(<lambda>)
      277    0.001    0.000    0.002    0.000 scanner.py:406(token)
      263    0.000    0.000    0.000    0.000 scanner.py:43(is_blank)
      717    0.002    0.000    0.028    0.000 scanner.py:438(scan)
      898    0.000    0.000    0.000    0.000 scanner.py:47(is_identifier_start)
     1297    0.000    0.000    0.000    0.000 scanner.py:51(is_identifier)
      606    0.000    0.000    0.000    0.000 scanner.py:61(is_digit)
        1    0.000    0.000    0.000    0.000 scanner.py:78(__init__)
       59    0.000    0.000    0.000    0.000 symbols.py:21(__attrs_post_init__)
  8687867    1.157    0.000    1.157    0.000 symbols.py:24(__hash__)
       22    0.000    0.000    0.000    0.000 symbols.py:60(__str__)
       83    0.000    0.000    0.000    0.000 symbols.py:63(__attrs_post_init__)
  6171119    0.860    0.000    0.860    0.000 symbols.py:66(__hash__)
  4602191    0.597    0.000    0.597    0.000 symbols.py:79(__hash__)
      215    0.000    0.000    0.000    0.000 symbols.py:82(add_symbol)
        9    0.000    0.000    0.000    0.000 symbols.py:88(insert_symbol)
      861    0.001    0.000    0.001    0.000 threading.py:1096(name)
      861    0.001    0.000    0.002    0.000 threading.py:1429(current_thread)
        2    0.000    0.000    0.000    0.000 typing.py:1207(_generic_class_getitem)
        6    0.000    0.000    0.000    0.000 typing.py:1221(<genexpr>)
       22    0.000    0.000    0.000    0.000 typing.py:1294(_is_dunder)
        3    0.000    0.000    0.000    0.000 typing.py:1307(__init__)
       27    0.000    0.000    0.000    0.000 typing.py:1313(__call__)
        2    0.000    0.000    0.000    0.000 typing.py:1358(__getattr__)
       20    0.000    0.000    0.000    0.000 typing.py:1368(__setattr__)
        3    0.000    0.000    0.000    0.000 typing.py:1423(__init__)
        9    0.000    0.000    0.000    0.000 typing.py:1427(<genexpr>)
        1    0.000    0.000    0.000    0.000 typing.py:1634(__getitem__)
        3    0.000    0.000    0.000    0.000 typing.py:1639(<genexpr>)
        6    0.000    0.000    0.000    0.000 typing.py:164(_type_convert)
        1    0.000    0.000    0.000    0.000 typing.py:1658(copy_with)
        2    0.000    0.000    0.000    0.000 typing.py:173(_type_check)
        3    0.000    0.000    0.000    0.000 typing.py:260(_collect_type_parameters)
        2    0.000    0.000    0.000    0.000 typing.py:310(_check_generic_specialization)
        1    0.000    0.000    0.000    0.000 typing.py:3794(__getattr__)
       29    0.000    0.000    0.000    0.000 typing.py:426(inner)
       14    0.000    0.000    0.000    0.000 {built-in method __new__ of type object at 0x00007FFBCEC398A0}
      837    0.003    0.000    0.003    0.000 {built-in method _abc._abc_instancecheck}
      8/1    0.000    0.000    0.000    0.000 {built-in method _abc._abc_subclasscheck}
        1    0.000    0.000    0.000    0.000 {built-in method _codecs.charmap_decode}
        1    0.000    0.000    0.000    0.000 {built-in method _imp._fix_co_filename}
        6    0.000    0.000    0.000    0.000 {built-in method _imp.acquire_lock}
        1    0.000    0.000    0.000    0.000 {built-in method _imp.find_frozen}
        1    0.000    0.000    0.000    0.000 {built-in method _imp.is_builtin}
        6    0.000    0.000    0.000    0.000 {built-in method _imp.release_lock}
        1    0.001    0.001    0.001    0.001 {built-in method _io.open_code}
        1    0.000    0.000    0.000    0.000 {built-in method _io.open}
        1    0.000    0.000    0.000    0.000 {built-in method _thread.allocate_lock}
     1724    0.001    0.000    0.001    0.000 {built-in method _thread.get_ident}
        1    0.000    0.000    0.000    0.000 {built-in method _weakref._remove_dead_weakref}
     2583    0.009    0.000    0.009    0.000 {built-in method _winapi.LCMapStringEx}
        5    0.000    0.000    0.000    0.000 {built-in method builtins.__build_class__}
     1305    1.298    0.001    2.480    0.002 {built-in method builtins.any}
        5    0.000    0.000    0.000    0.000 {built-in method builtins.callable}
      3/1    0.001    0.000    0.004    0.004 {built-in method builtins.exec}
       82    0.000    0.000    0.000    0.000 {built-in method builtins.getattr}
     1765    0.003    0.000    0.003    0.000 {built-in method builtins.hasattr}
   273662    0.051    0.000    0.051    0.000 {built-in method builtins.hash}
        6    0.000    0.000    0.000    0.000 {built-in method builtins.id}
  5155297    0.946    0.000    0.950    0.000 {built-in method builtins.isinstance}
        2    0.000    0.000    0.000    0.000 {built-in method builtins.issubclass}
 13815468    2.295    0.000    2.295    0.000 {built-in method builtins.len}
        1    0.000    0.000    0.000    0.000 {built-in method builtins.locals}
      863    0.001    0.000    0.001    0.000 {built-in method builtins.max}
        1    0.000    0.000    0.000    0.000 {built-in method builtins.repr}
       27    0.000    0.000    0.000    0.000 {built-in method builtins.setattr}
        2    0.000    0.000    0.000    0.000 {built-in method builtins.vars}
        3    0.000    0.000    0.000    0.000 {built-in method from_bytes}
        1    0.000    0.000    0.000    0.000 {built-in method marshal.loads}
      865    0.002    0.000    0.002    0.000 {built-in method nt._path_splitroot_ex}
        1    0.000    0.000    0.000    0.000 {built-in method nt._path_splitroot}
     4312    0.002    0.000    0.002    0.000 {built-in method nt.fspath}
      861    0.001    0.000    0.001    0.000 {built-in method nt.getpid}
        5    0.000    0.000    0.000    0.000 {built-in method nt.stat}
      861    0.002    0.000    0.002    0.000 {built-in method sys._getframe}
        6    0.000    0.000    0.000    0.000 {built-in method sys.getrecursionlimit}
       16    0.000    0.000    0.000    0.000 {built-in method sys.intern}
        2    0.000    0.000    0.000    0.000 {built-in method time.perf_counter}
      861    0.002    0.000    0.002    0.000 {built-in method time.time_ns}
        8    0.000    0.000    0.000    0.000 {method '__contains__' of 'frozenset' objects}
        2    0.000    0.000    0.000    0.000 {method '__exit__' of '_io._IOBase' objects}
     1727    0.001    0.000    0.001    0.000 {method '__exit__' of '_thread.RLock' objects}
        4    0.000    0.000    0.000    0.000 {method '__typing_prepare_subst__' of 'typing.TypeVar' objects}
  5189041    1.377    0.000    1.377    0.000 {method 'add' of 'set' objects}
    25887    0.009    0.000    0.009    0.000 {method 'append' of 'list' objects}
        1    0.000    0.000    0.000    0.000 {method 'disable' of '_lsprof.Profiler' objects}
       65    0.000    0.000    0.000    0.000 {method 'endswith' of 'str' objects}
  1150876    0.308    0.000    0.308    0.000 {method 'extend' of 'list' objects}
      981    0.001    0.000    0.001    0.000 {method 'find' of 'str' objects}
      861    0.002    0.000    0.002    0.000 {method 'flush' of '_io.TextIOWrapper' objects}
       10    0.000    0.000    0.000    0.000 {method 'format' of 'str' objects}
 12802517    8.143    0.000    9.825    0.000 {method 'get' of 'dict' objects}
       19    0.000    0.000    0.000    0.000 {method 'get' of 'mappingproxy' objects}
   132829    0.099    0.000    0.099    0.000 {method 'index' of 'list' objects}
        9    0.000    0.000    0.000    0.000 {method 'insert' of 'list' objects}
        8    0.000    0.000    0.000    0.000 {method 'isidentifier' of 'str' objects}
      105    0.000    0.000    0.000    0.000 {method 'issuperset' of 'set' objects}
     6388    0.004    0.000    0.004    0.000 {method 'items' of 'dict' objects}
        3    0.000    0.000    0.000    0.000 {method 'items' of 'mappingproxy' objects}
       48    0.000    0.000    0.000    0.000 {method 'join' of 'str' objects}
  1002512    0.270    0.000    0.270    0.000 {method 'keys' of 'dict' objects}
        1    0.000    0.000    0.000    0.000 {method 'pop' of 'dict' objects}
      713    0.000    0.000    0.000    0.000 {method 'pop' of 'list' objects}
        1    0.000    0.000    0.000    0.000 {method 'read' of '_io.BufferedReader' objects}
        1    0.000    0.000    0.000    0.000 {method 'read' of '_io.TextIOWrapper' objects}
        1    0.000    0.000    0.000    0.000 {method 'remove' of 'list' objects}
     2587    0.002    0.000    0.002    0.000 {method 'replace' of 'str' objects}
     2587    0.001    0.000    0.001    0.000 {method 'rfind' of 'str' objects}
        7    0.000    0.000    0.000    0.000 {method 'rpartition' of 'str' objects}
      908    0.001    0.000    0.001    0.000 {method 'rstrip' of 'str' objects}
        9    0.000    0.000    0.000    0.000 {method 'setdefault' of 'dict' objects}
        2    0.000    0.000    0.000    0.000 {method 'split' of 'str' objects}
       55    0.000    0.000    0.000    0.000 {method 'startswith' of 'str' objects}
       55    0.000    0.000    0.000    0.000 {method 'strip' of 'str' objects}
     5215    0.005    0.000    0.005    0.000 {method 'update' of 'dict' objects}
     1667    0.001    0.000    0.001    0.000 {method 'update' of 'set' objects}
     1200    0.000    0.000    0.000    0.000 {method 'values' of 'dict' objects}
        2    0.000    0.000    0.000    0.000 {method 'values' of 'mappingproxy' objects}
      861    0.183    0.000    0.183    0.000 {method 'write' of '_io.TextIOWrapper' objects}


********************************************

PyPy
DEBUG:typethon.syntax.typethon.parser:Generated tables after 10.34 seconds
         80399001 function calls (80398503 primitive calls) in 10.300 seconds

   Ordered by: standard name

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
      128    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.CaptureNode>:24(__init__)
       52    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.GroupNode>:24(__init__)
       20    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.KeywordNode>:24(__init__)
      100    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.NameNode>:24(__init__)
       11    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.OptionalNode>:24(__init__)
        6    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.PlusNode>:24(__init__)
       79    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.RuleItemNode>:25(__init__)
       33    0.001    0.000    0.001    0.000 <attrs generated methods typethon.grammar.ast.RuleNode>:26(__init__)
        3    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.StarNode>:24(__init__)
       59    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.TokenNode>:24(__init__)
      125    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.frozen.FrozenProduction>:33(__init__)
   232176    0.130    0.000    0.130    0.000 <attrs generated methods typethon.grammar.frozen.FrozenSymbol>:16(__eq__)
   272964    0.038    0.000    0.051    0.000 <attrs generated methods typethon.grammar.frozen.FrozenSymbol>:23(__hash__)
   132888    0.012    0.000    0.012    0.000 <attrs generated methods typethon.grammar.frozen.FrozenSymbol>:29(__init__)
     1172    0.002    0.000    0.002    0.000 <attrs generated methods typethon.grammar.generator.ParserState>:23(__init__)
        1    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.generator.TableBuilder>:22(__init__)
       59    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.symbols.NonterminalSymbol>:1(__init__)
      125    0.001    0.000    0.001    0.000 <attrs generated methods typethon.grammar.symbols.Production>:16(__init__)
     9194    0.014    0.000    0.014    0.000 <attrs generated methods typethon.grammar.symbols.TerminalSymbol>:16(__eq__)
       83    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.symbols.TerminalSymbol>:23(__init__)
       31    0.000    0.000    0.000    0.000 <attrs generated methods typethon.syntax.tokens.DedentToken>:22(__init__)
       55    0.000    0.000    0.000    0.000 <attrs generated methods typethon.syntax.tokens.DirectiveToken>:22(__init__)
      146    0.001    0.000    0.001    0.000 <attrs generated methods typethon.syntax.tokens.IdentifierToken>:23(__init__)
       31    0.000    0.000    0.000    0.000 <attrs generated methods typethon.syntax.tokens.IndentToken>:22(__init__)
       66    0.000    0.000    0.000    0.000 <attrs generated methods typethon.syntax.tokens.StringToken>:23(__init__)
      388    0.001    0.000    0.001    0.000 <attrs generated methods typethon.syntax.tokens.TokenData>:22(__init__)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:100(acquire)
        4    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:1026(__enter__)
        4    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:1030(__exit__)
        1    0.000    0.000    0.001    0.001 <frozen importlib._bootstrap>:1054(_find_spec)
        2    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:1101(_sanity_check)
        1    0.000    0.000    0.008    0.008 <frozen importlib._bootstrap>:1120(_find_and_load_unlocked)
        2    0.000    0.000    0.008    0.004 <frozen importlib._bootstrap>:1165(_find_and_load)
        2    0.000    0.000    0.008    0.004 <frozen importlib._bootstrap>:1192(_gcd_import)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:125(release)
        1    0.000    0.000    0.008    0.008 <frozen importlib._bootstrap>:1271(__import__)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:165(__init__)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:169(__enter__)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:173(__exit__)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:179(_get_module_lock)
      211    0.002    0.000    0.002    0.000 <frozen importlib._bootstrap>:198(cb)
        2    0.000    0.000    0.005    0.003 <frozen importlib._bootstrap>:233(_call_with_frames_removed)
        9    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:244(_verbose_message)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:357(__init__)
        2    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:392(cached)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:405(parent)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:413(has_location)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:48(_new_module)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:493(_init_module_attrs)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:566(module_from_spec)
        1    0.000    0.000    0.007    0.007 <frozen importlib._bootstrap>:666(_load_unlocked)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:71(__init__)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:748(find_spec)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:920(find_spec)
        1    0.000    0.000    0.000    0.000 <string>:1(<module>)
        1    0.000    0.000    0.000    0.000 <string>:1(__create_fn__)
      861    0.007    0.000    0.030    0.000 __init__.py:1087(flush)
      861    0.013    0.000    0.445    0.001 __init__.py:1098(emit)
      861    0.002    0.000    0.003    0.000 __init__.py:123(getLevelName)
        3    0.000    0.000    0.000    0.000 __init__.py:1319(disable)
      838    0.013    0.000    0.770    0.001 __init__.py:1467(debug)
       23    0.000    0.000    0.019    0.001 __init__.py:1479(info)
      861    0.033    0.000    0.098    0.000 __init__.py:1561(findCaller)
      861    0.006    0.000    0.183    0.000 __init__.py:1595(makeRecord)
      861    0.010    0.000    0.771    0.001 __init__.py:1610(_log)
      861    0.003    0.000    0.480    0.001 __init__.py:1636(handle)
      861    0.007    0.000    0.009    0.000 __init__.py:164(<lambda>)
      861    0.014    0.000    0.473    0.001 __init__.py:1690(callHandlers)
        3    0.000    0.000    0.000    0.000 __init__.py:1720(getEffectiveLevel)
      861    0.004    0.000    0.004    0.000 __init__.py:1734(isEnabledFor)
     2583    0.023    0.000    0.056    0.000 __init__.py:194(_is_internal_frame)
        3    0.000    0.000    0.000    0.000 __init__.py:228(_acquireLock)
        3    0.000    0.000    0.000    0.000 __init__.py:237(_releaseLock)
      861    0.061    0.000    0.177    0.000 __init__.py:292(__init__)
      861    0.014    0.000    0.014    0.000 __init__.py:368(getMessage)
      861    0.003    0.000    0.005    0.000 __init__.py:432(usesTime)
      861    0.010    0.000    0.010    0.000 __init__.py:440(_format)
      861    0.001    0.000    0.011    0.000 __init__.py:447(format)
      861    0.002    0.000    0.007    0.000 __init__.py:652(usesTime)
      861    0.001    0.000    0.012    0.000 __init__.py:658(formatMessage)
      861    0.004    0.000    0.037    0.000 __init__.py:674(format)
     1722    0.004    0.000    0.004    0.000 __init__.py:815(filter)
        1    0.000    0.000    0.000    0.000 __init__.py:89(find_spec)
     1722    0.009    0.000    0.015    0.000 __init__.py:922(acquire)
     1722    0.005    0.000    0.007    0.000 __init__.py:929(release)
      861    0.003    0.000    0.040    0.000 __init__.py:942(format)
        1    0.000    0.000    0.000    0.000 __init__.py:96(<lambda>)
      861    0.004    0.000    0.459    0.001 __init__.py:965(handle)
        8    0.000    0.000    0.000    0.000 _collections_abc.py:409(__subclasshook__)
        1    0.000    0.000    0.000    0.000 _winapi.py:416(CloseHandle)
        1    0.000    0.000    0.000    0.000 _winapi.py:53(_int2handle)
      837    0.028    0.000    0.028    0.000 abc.py:117(__instancecheck__)
      8/1    0.000    0.000    0.000    0.000 abc.py:121(__subclasscheck__)
        2    0.000    0.000    0.000    0.000 abc.py:146(update_abstractmethods)
        1    0.000    0.000    0.008    0.008 cProfile.py:41(print_stats)
        1    0.000    0.000    0.000    0.000 cProfile.py:51(create_stats)
        1    0.000    0.000    0.000    0.000 codecs.py:260(__init__)
        1    0.000    0.000    0.000    0.000 codecs.py:309(__init__)
        1    0.000    0.000    0.000    0.000 codecs.py:319(decode)
        2    0.000    0.000    0.000    0.000 dataclasses.py:1017(<listcomp>)
        2    0.000    0.000    0.000    0.000 dataclasses.py:1043(<listcomp>)
        2    0.000    0.000    0.000    0.000 dataclasses.py:1046(<listcomp>)
        2    0.000    0.000    0.000    0.000 dataclasses.py:1052(<listcomp>)
       11    0.000    0.000    0.000    0.000 dataclasses.py:1106(<genexpr>)
        2    0.000    0.000    0.000    0.000 dataclasses.py:1204(dataclass)
        2    0.000    0.000    0.004    0.002 dataclasses.py:1221(wrap)
        2    0.000    0.000    0.000    0.000 dataclasses.py:228(_recursive_repr)
        9    0.000    0.000    0.000    0.000 dataclasses.py:287(__init__)
        2    0.000    0.000    0.000    0.000 dataclasses.py:346(__init__)
        9    0.000    0.000    0.000    0.000 dataclasses.py:368(field)
        2    0.000    0.000    0.000    0.000 dataclasses.py:392(_fields_in_init_order)
       11    0.000    0.000    0.000    0.000 dataclasses.py:396(<genexpr>)
        2    0.000    0.000    0.000    0.000 dataclasses.py:397(<genexpr>)
        6    0.000    0.000    0.000    0.000 dataclasses.py:401(_tuple_str)
        6    0.000    0.000    0.000    0.000 dataclasses.py:410(<listcomp>)
        8    0.000    0.000    0.002    0.000 dataclasses.py:413(_create_fn)
       27    0.000    0.000    0.000    0.000 dataclasses.py:425(<genexpr>)
        9    0.000    0.000    0.000    0.000 dataclasses.py:437(_field_assign)
        9    0.000    0.000    0.000    0.000 dataclasses.py:449(_field_init)
        9    0.000    0.000    0.000    0.000 dataclasses.py:509(_init_param)
        2    0.000    0.000    0.001    0.000 dataclasses.py:528(_init_fn)
        2    0.000    0.000    0.000    0.000 dataclasses.py:548(<dictcomp>)
        2    0.000    0.000    0.000    0.000 dataclasses.py:573(<listcomp>)
        2    0.000    0.000    0.001    0.000 dataclasses.py:588(_repr_fn)
        2    0.000    0.000    0.000    0.000 dataclasses.py:592(<listcomp>)
        2    0.000    0.000    0.000    0.000 dataclasses.py:624(_cmp_fn)
        2    0.000    0.000    0.000    0.000 dataclasses.py:638(_hash_fn)
        9    0.000    0.000    0.000    0.000 dataclasses.py:646(_is_classvar)
        9    0.000    0.000    0.000    0.000 dataclasses.py:654(_is_initvar)
        9    0.000    0.000    0.000    0.000 dataclasses.py:660(_is_kw_only)
        9    0.000    0.000    0.000    0.000 dataclasses.py:723(_get_field)
       10    0.000    0.000    0.000    0.000 dataclasses.py:820(_set_qualname)
        8    0.000    0.000    0.000    0.000 dataclasses.py:827(_set_new_attribute)
        2    0.000    0.000    0.000    0.000 dataclasses.py:845(_hash_add)
        2    0.000    0.000    0.000    0.000 dataclasses.py:846(<listcomp>)
        2    0.000    0.000    0.004    0.002 dataclasses.py:884(_process_class)
      204    0.000    0.000    0.000    0.000 enum.py:1095(__new__)
        9    0.000    0.000    0.000    0.000 enum.py:1151(__init__)
       22    0.000    0.000    0.000    0.000 enum.py:1197(__str__)
      556    0.000    0.000    0.001    0.000 enum.py:1232(__hash__)
       83    0.000    0.000    0.000    0.000 enum.py:1252(name)
      588    0.001    0.000    0.001    0.000 enum.py:1507(_get_value)
      196    0.001    0.000    0.002    0.000 enum.py:1525(__and__)
        1    0.000    0.000    0.000    0.000 enum.py:1652(_simple_enum)
        1    0.000    0.000    0.001    0.001 enum.py:1668(convert_class)
       83    0.000    0.000    0.000    0.000 enum.py:193(__get__)
        9    0.000    0.000    0.000    0.000 enum.py:229(__set_name__)
        9    0.000    0.000    0.000    0.000 enum.py:38(_is_descriptor)
       12    0.000    0.000    0.000    0.000 enum.py:48(_is_dunder)
        1    0.000    0.000    0.000    0.000 enum.py:499(__new__)
        9    0.000    0.000    0.000    0.000 enum.py:59(_is_sunder)
      204    0.000    0.000    0.001    0.000 enum.py:688(__call__)
        9    0.000    0.000    0.000    0.000 enum.py:79(_is_private)
       13    0.000    0.000    0.000    0.000 enum.py:828(__setattr__)
        1    0.000    0.000    0.001    0.001 frozen importlib._bootstrap_external:1022(get_code)
        1    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:1112(__init__)
        1    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:1137(get_filename)
        1    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:1142(get_data)
        1    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:1161(path_stats)
        8    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:119(<listcomp>)
        2    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:132(_path_split)
        6    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:134(<genexpr>)
        4    0.000    0.000    0.001    0.000 frozen importlib._bootstrap_external:140(_path_stat)
        2    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:1439(_path_importer_cache)
        1    0.000    0.000    0.001    0.001 frozen importlib._bootstrap_external:1482(_get_spec)
        1    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:150(_path_is_mode_type)
        1    0.000    0.000    0.001    0.001 frozen importlib._bootstrap_external:1514(find_spec)
        1    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:159(_path_isfile)
        1    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:1617(_get_spec)
        2    0.000    0.000    0.001    0.000 frozen importlib._bootstrap_external:1622(find_spec)
        1    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:172(_path_isabs)
        2    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:452(cache_from_source)
        1    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:582(_get_cached)
        1    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:614(_check_name_wrapper)
        1    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:657(_classify_pyc)
        2    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:67(_relax_case)
        1    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:690(_validate_timestamp_pyc)
        1    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:742(_compile_bytecode)
        1    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:793(spec_from_file_location)
        3    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:84(_unpack_uint32)
        1    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:946(create_module)
        1    0.000    0.000    0.006    0.006 frozen importlib._bootstrap_external:949(exec_module)
        8    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:96(_path_join)
        1    0.000    0.000    0.000    0.000 frozen.py:116(__init__)
        1    0.000    0.000    0.000    0.000 frozen.py:15(__init__)
   132829    0.041    0.000    0.124    0.000 frozen.py:34(get_frozen_terminal)
     3778    0.001    0.000    0.001    0.000 frozen.py:43(get_frozen_nonterminal)
       59    0.000    0.000    0.000    0.000 frozen.py:56(create_frozen_nonterminal)
      125    0.000    0.000    0.001    0.000 frozen.py:64(create_frozen_production)
      101    0.000    0.000    0.000    0.000 frozen.py:82(add_production_action)
        5    0.000    0.000    0.000    0.000 functools.py:289(__new__)
        2    0.000    0.000    0.000    0.000 functools.py:39(update_wrapper)
     6636    0.016    0.000    0.043    0.000 functools.py:453(__init__)
     7949    0.005    0.000    0.005    0.000 functools.py:457(__hash__)
     6636    0.046    0.000    0.091    0.000 functools.py:460(_make_key)
        2    0.000    0.000    0.000    0.000 functools.py:69(wraps)
   501256    0.100    0.000    0.148    0.000 generator.py:100(iter_symbols)
     1172    0.006    0.000    0.008    0.000 generator.py:115(iter_terminal_items_with_symbol)
   116321    0.019    0.000    0.019    0.000 generator.py:118(<genexpr>)
     1172    0.002    0.000    0.011    0.000 generator.py:146(iter_completed_items)
     7902    0.005    0.000    0.011    0.000 generator.py:156(get_effective_map)
  5142669    1.047    0.000    3.211    0.000 generator.py:177(add_item)
        1    0.000    0.000    0.001    0.001 generator.py:234(add_accept)
   115149    0.114    0.000    0.448    0.000 generator.py:250(add_shift)
    17679    0.041    0.000    0.122    0.000 generator.py:289(add_reduce)
     3653    0.004    0.000    0.008    0.000 generator.py:329(add_goto)
        1    0.000    0.000    0.000    0.000 generator.py:367(__init__)
        1    0.000    0.000    0.000    0.000 generator.py:413(initialize_nonterminals)
        1    0.000    0.000    0.007    0.007 generator.py:417(initialize_productions)
        1    0.000    0.000    0.008    0.008 generator.py:421(generate_symbols)
        1    0.001    0.001    0.002    0.002 generator.py:425(generate_frozen_symbols)
       15    0.000    0.000    0.000    0.000 generator.py:438(should_capture_uninlined_expression)
       30    0.000    0.000    0.000    0.000 generator.py:442(<genexpr>)
      125    0.000    0.000    0.001    0.000 generator.py:444(create_production)
       33    0.000    0.000    0.007    0.000 generator.py:454(initialize_productions_for_rule)
        9    0.000    0.000    0.001    0.000 generator.py:465(add_new_star_expression)
   395/79    0.003    0.000    0.006    0.000 generator.py:499(add_symbols_for_expression)
     7903    0.079    0.000    0.079    0.000 generator.py:53(__init__)
        1    0.000    0.000    0.001    0.001 generator.py:615(compute_epsilon_nonterminals)
      144    0.000    0.000    0.000    0.000 generator.py:618(<genexpr>)
      144    0.000    0.000    0.000    0.000 generator.py:628(<genexpr>)
        1    0.025    0.025    0.032    0.032 generator.py:635(compute_first_sets)
  1099370    0.186    0.000    0.210    0.000 generator.py:65(__eq__)
     1307    0.008    0.000    0.013    0.000 generator.py:664(get_first_set)
     7903    0.699    0.000    3.929    0.000 generator.py:682(compute_closure)
     7902    0.350    0.000    4.694    0.001 generator.py:759(compute_goto)
     1172    0.004    0.000    0.008    0.000 generator.py:774(create_state)
        1    1.290    1.290    8.968    8.968 generator.py:793(compute_canonical_collection)
        1    0.420    0.420   10.206   10.206 generator.py:838(compute_tables)
  8884422    0.151    0.000    0.151    0.000 generator.py:868(<genexpr>)
        1    0.000    0.000   10.248   10.248 generator.py:873(generate)
        1    0.000    0.000   10.338   10.338 generator.py:896(generate_from_grammar)
     7903    0.018    0.000    0.018    0.000 generator.py:91(get_intern_items)
     9074    0.018    0.000    0.018    0.000 generator.py:94(iter_interned_items)
   326204    0.029    0.000    0.029    0.000 generator.py:98(<genexpr>)
      861    0.007    0.000    0.012    0.000 genericpath.py:121(_splitext)
        8    0.000    0.000    0.000    0.000 inspect.py:1447(formatannotation)
        1    0.000    0.000    0.000    0.000 inspect.py:171(get_annotations)
        6    0.000    0.000    0.000    0.000 inspect.py:1774(_static_getmro)
        2    0.000    0.000    0.000    0.000 inspect.py:1786(_check_class)
        2    0.000    0.000    0.000    0.000 inspect.py:1795(_is_type)
        2    0.000    0.000    0.000    0.000 inspect.py:1802(_shadowed_dict)
        2    0.000    0.000    0.000    0.000 inspect.py:1816(getattr_static)
        3    0.000    0.000    0.000    0.000 inspect.py:1959(_signature_get_user_defined_method)
        1    0.000    0.000    0.000    0.000 inspect.py:2058(_signature_bound_method)
        1    0.000    0.000    0.000    0.000 inspect.py:2084(_signature_is_builtin)
        1    0.000    0.000    0.000    0.000 inspect.py:2100(_signature_is_functionlike)
        1    0.000    0.000    0.000    0.000 inspect.py:2366(_signature_from_function)
        1    0.000    0.000    0.000    0.000 inspect.py:2464(_descriptor_get)
      3/1    0.000    0.000    0.001    0.001 inspect.py:2473(_signature_from_callable)
        8    0.000    0.000    0.000    0.000 inspect.py:2709(__init__)
       15    0.000    0.000    0.000    0.000 inspect.py:2762(name)
        7    0.000    0.000    0.000    0.000 inspect.py:2766(default)
       23    0.000    0.000    0.000    0.000 inspect.py:2774(kind)
        7    0.000    0.000    0.000    0.000 inspect.py:2796(__str__)
        3    0.000    0.000    0.000    0.000 inspect.py:296(isclass)
        2    0.000    0.000    0.000    0.000 inspect.py:2995(__init__)
        9    0.000    0.000    0.000    0.000 inspect.py:3042(<genexpr>)
        1    0.000    0.000    0.001    0.001 inspect.py:3047(from_callable)
        2    0.000    0.000    0.000    0.000 inspect.py:3055(parameters)
        2    0.000    0.000    0.000    0.000 inspect.py:3059(return_annotation)
        1    0.000    0.000    0.000    0.000 inspect.py:3063(replace)
        1    0.000    0.000    0.000    0.000 inspect.py:314(ismethoddescriptor)
        1    0.000    0.000    0.000    0.000 inspect.py:3255(__str__)
        1    0.000    0.000    0.001    0.001 inspect.py:3301(signature)
        3    0.000    0.000    0.000    0.000 inspect.py:382(isfunction)
        1    0.000    0.000    0.000    0.000 inspect.py:509(isbuiltin)
        2    0.000    0.000    0.000    0.000 inspect.py:739(unwrap)
      861    0.012    0.000    0.015    0.000 ntpath.py:155(splitdrive)
      861    0.021    0.000    0.040    0.000 ntpath.py:209(split)
      861    0.006    0.000    0.019    0.000 ntpath.py:232(splitext)
      861    0.002    0.000    0.042    0.000 ntpath.py:243(basename)
      861    0.001    0.000    0.002    0.000 ntpath.py:36(_get_bothseps)
     2583    0.017    0.000    0.033    0.000 ntpath.py:71(normcase)
        1    0.000    0.000    0.089    0.089 parser.py:101(parse_rules)
       33    0.001    0.000    0.089    0.003 parser.py:108(parse_rule)
      110    0.000    0.000    0.015    0.000 parser.py:187(parse_rule_action)
    88/79    0.000    0.000    0.045    0.001 parser.py:195(parse_expression)
    88/79    0.002    0.000    0.045    0.001 parser.py:212(parse_expression_group)
  316/169    0.002    0.000    0.036    0.000 parser.py:236(parse_expression_group_item)
        1    0.000    0.000    0.000    0.000 parser.py:24(__init__)
      325    0.001    0.000    0.010    0.000 parser.py:266(parse_expression_suffix)
      179    0.000    0.000    0.002    0.000 parser.py:295(parse_atom)
        1    0.000    0.000    0.089    0.089 parser.py:305(parse_from_source)
      113    0.001    0.000    0.001    0.000 parser.py:42(parse_identifier)
       66    0.000    0.000    0.001    0.000 parser.py:64(parse_string)
        1    0.000    0.000   10.340   10.340 parser.py:71(load_parser_tables)
      655    0.006    0.000    0.072    0.000 parser.py:75(scan_no_whitespace)
      654    0.001    0.000    0.003    0.000 parser.py:83(scan_token)
     1370    0.005    0.000    0.076    0.000 parser.py:95(peek_token)
        2    0.000    0.000    0.000    0.000 pathlib.py:147(splitroot)
        2    0.000    0.000    0.000    0.000 pathlib.py:484(_parse_args)
        1    0.000    0.000    0.000    0.000 pathlib.py:504(_from_parts)
        2    0.000    0.000    0.000    0.000 pathlib.py:515(_from_parsed_parts)
        1    0.000    0.000    0.000    0.000 pathlib.py:523(_format_parsed_parts)
        1    0.000    0.000    0.000    0.000 pathlib.py:530(_make_child)
        1    0.000    0.000    0.000    0.000 pathlib.py:536(__str__)
        1    0.000    0.000    0.000    0.000 pathlib.py:546(__fspath__)
        2    0.000    0.000    0.000    0.000 pathlib.py:56(parse_parts)
        1    0.000    0.000    0.000    0.000 pathlib.py:765(__truediv__)
        1    0.000    0.000    0.000    0.000 pathlib.py:777(parent)
        1    0.000    0.000    0.000    0.000 pathlib.py:868(__new__)
        1    0.000    0.000    0.000    0.000 pathlib.py:94(join_parsed_parts)
        1    0.000    0.000    0.005    0.005 pstats.py:1(<module>)
        1    0.000    0.000    0.000    0.000 pstats.py:108(__init__)
        1    0.000    0.000    0.000    0.000 pstats.py:118(init)
        1    0.000    0.000    0.000    0.000 pstats.py:137(load_stats)
        1    0.000    0.000    0.000    0.000 pstats.py:36(SortKey)
        9    0.000    0.000    0.000    0.000 pstats.py:48(__new__)
        1    0.000    0.000    0.000    0.000 pstats.py:522(TupleComp)
        1    0.000    0.000    0.000    0.000 pstats.py:58(FunctionProfile)
        1    0.000    0.000    0.000    0.000 pstats.py:68(StatsProfile)
        1    0.000    0.000    0.000    0.000 pstats.py:74(Stats)
        1    0.000    0.000    0.000    0.000 scanner.py:102(create_lookup_table)
     8420    0.006    0.000    0.007    0.000 scanner.py:127(is_eof)
    10416    0.006    0.000    0.007    0.000 scanner.py:130(char_at)
     6333    0.005    0.000    0.008    0.000 scanner.py:136(peek_char)
     4083    0.007    0.000    0.015    0.000 scanner.py:139(consume_char)
      959    0.019    0.000    0.040    0.000 scanner.py:147(consume_while)
       66    0.000    0.000    0.000    0.000 scanner.py:163(string_terminated)
      263    0.002    0.000    0.005    0.000 scanner.py:176(scan_indentation)
      146    0.001    0.000    0.020    0.000 scanner.py:235(identifier_or_string)
      203    0.001    0.000    0.001    0.000 scanner.py:339(newline)
      931    0.000    0.000    0.000    0.000 scanner.py:35(is_whitespace)
       66    0.001    0.000    0.004    0.000 scanner.py:351(string)
       60    0.001    0.000    0.021    0.000 scanner.py:388(comment)
      807    0.000    0.000    0.000    0.000 scanner.py:39(is_indent)
     1321    0.001    0.000    0.001    0.000 scanner.py:394(<lambda>)
      277    0.002    0.000    0.004    0.000 scanner.py:406(token)
      263    0.000    0.000    0.000    0.000 scanner.py:43(is_blank)
      717    0.004    0.000    0.066    0.000 scanner.py:438(scan)
      898    0.001    0.000    0.001    0.000 scanner.py:47(is_identifier_start)
     1297    0.002    0.000    0.002    0.000 scanner.py:51(is_identifier)
      606    0.000    0.000    0.000    0.000 scanner.py:61(is_digit)
        1    0.000    0.000    0.000    0.000 scanner.py:78(__init__)
        1    0.000    0.000    0.000    0.000 subprocess.py:1120(__del__)
        1    0.000    0.000    0.000    0.000 subprocess.py:1576(_internal_poll)
        6    0.000    0.000    0.000    0.000 subprocess.py:218(Close)
       59    0.000    0.000    0.000    0.000 symbols.py:21(__attrs_post_init__)
  9133262    0.163    0.000    0.163    0.000 symbols.py:24(__hash__)
       22    0.000    0.000    0.000    0.000 symbols.py:60(__str__)
       83    0.000    0.000    0.000    0.000 symbols.py:63(__attrs_post_init__)
  6281911    0.128    0.000    0.128    0.000 symbols.py:66(__hash__)
  5152201    0.074    0.000    0.074    0.000 symbols.py:79(__hash__)
      215    0.000    0.000    0.001    0.000 symbols.py:82(add_symbol)
        9    0.000    0.000    0.000    0.000 symbols.py:88(insert_symbol)
      861    0.002    0.000    0.002    0.000 threading.py:1163(name)
      861    0.002    0.000    0.002    0.000 threading.py:1464(current_thread)
        9    0.000    0.000    0.000    0.000 types.py:168(__init__)
       25    0.000    0.000    0.000    0.000 typing.py:1266(_is_dunder)
        3    0.000    0.000    0.000    0.000 typing.py:1279(__init__)
       27    0.000    0.000    0.000    0.000 typing.py:1285(__call__)
        2    0.000    0.000    0.000    0.000 typing.py:1310(__getattr__)
       23    0.000    0.000    0.000    0.000 typing.py:1320(__setattr__)
        3    0.000    0.000    0.000    0.000 typing.py:1376(__init__)
        9    0.000    0.000    0.000    0.000 typing.py:1381(<genexpr>)
        1    0.000    0.000    0.000    0.000 typing.py:1586(__getitem__)
        6    0.000    0.000    0.000    0.000 typing.py:159(_type_convert)
        3    0.000    0.000    0.000    0.000 typing.py:1591(<genexpr>)
        1    0.000    0.000    0.000    0.000 typing.py:1595(copy_with)
        2    0.000    0.000    0.000    0.000 typing.py:168(_type_check)
        2    0.000    0.000    0.001    0.000 typing.py:1830(__class_getitem__)
        6    0.000    0.000    0.000    0.000 typing.py:1844(<genexpr>)
        3    0.000    0.000    0.000    0.000 typing.py:251(_collect_parameters)
        3    0.000    0.000    0.000    0.000 typing.py:284(_check_generic)
       29    0.000    0.000    0.002    0.000 typing.py:373(inner)
      861    0.009    0.000    0.010    0.000 utf_8.py:19(encode)
        5    0.000    0.000    0.000    0.000 {built-in function __build_class__}
        1    0.000    0.000    0.000    0.000 {built-in function _codecs.utf_8_decode}
      861    0.002    0.000    0.002    0.000 {built-in function _codecs.utf_8_encode}
        1    0.000    0.000    0.000    0.000 {built-in function _imp._fix_co_filename}
      216    0.000    0.000    0.000    0.000 {built-in function _imp.acquire_lock}
        1    0.000    0.000    0.000    0.000 {built-in function _imp.find_frozen}
        1    0.000    0.000    0.000    0.000 {built-in function _imp.is_builtin}
      216    0.000    0.000    0.000    0.000 {built-in function _imp.release_lock}
        1    0.000    0.000    0.000    0.000 {built-in function _io.open_code}
        1    0.000    0.000    0.000    0.000 {built-in function _io.open}
        2    0.000    0.000    0.000    0.000 {built-in function _thread.allocate_lock}
     1724    0.001    0.000    0.001    0.000 {built-in function _thread.get_ident}
       10    0.000    0.000    0.000    0.000 {built-in function callable}
        1    0.000    0.000    0.000    0.000 {built-in function cpyext.is_cpyext_function}
      9/1    0.001    0.000    0.005    0.005 {built-in function exec}
       90    0.000    0.000    0.000    0.000 {built-in function getattr}
     1761    0.006    0.000    0.006    0.000 {built-in function hasattr}
   280298    0.037    0.000    0.040    0.000 {built-in function hash}
        2    0.000    0.000    0.000    0.000 {built-in function id}
  6109118    0.135    0.000    0.163    0.000 {built-in function isinstance}
        2    0.000    0.000    0.000    0.000 {built-in function issubclass}
 15472971    0.251    0.000    0.251    0.000 {built-in function len}
        1    0.000    0.000    0.000    0.000 {built-in function locals}
        1    0.000    0.000    0.000    0.000 {built-in function marshal.loads}
      863    0.001    0.000    0.001    0.000 {built-in function max}
        1    0.000    0.000    0.000    0.000 {built-in function nt._path_splitroot}
     5171    0.004    0.000    0.004    0.000 {built-in function nt.fspath}
      861    0.004    0.000    0.004    0.000 {built-in function nt.getpid}
        4    0.000    0.000    0.000    0.000 {built-in function nt.stat}
        1    0.000    0.000    0.000    0.000 {built-in function repr}
       33    0.000    0.000    0.000    0.000 {built-in function setattr}
      861    0.002    0.000    0.002    0.000 {built-in function sys._getframe}
        2    0.000    0.000    0.000    0.000 {built-in function sys.getrecursionlimit}
        9    0.000    0.000    0.000    0.000 {built-in function sys.intern}
        2    0.000    0.000    0.000    0.000 {built-in function time.perf_counter}
      861    0.007    0.000    0.007    0.000 {built-in function time.time}
        8    0.000    0.000    0.000    0.000 {method '__contains__' of 'frozenset' objects}
        1    0.000    0.000    0.000    0.000 {method '__exit__' of '_io._IOBase' objects}
        2    0.000    0.000    0.000    0.000 {method '__exit__' of '_thread.lock' objects}
        1    0.000    0.000    0.000    0.000 {method '__get__' of 'function' objects}
       10    0.000    0.000    0.000    0.000 {method '__get__' of 'getset_descriptor' objects}
        9    0.000    0.000    0.000    0.000 {method '__new__' of 'EnumType' objects}
        1    0.000    0.000    0.000    0.000 {method '__new__' of 'type' objects}
       13    0.000    0.000    0.000    0.000 {method '__setattr__' of 'EnumType' objects}
       23    0.000    0.000    0.000    0.000 {method '__setattr__' of '_BaseGenericAlias' objects}
     1725    0.006    0.000    0.006    0.000 {method 'acquire' of '_thread.RLock' objects}
  5795365    0.197    0.000    0.198    0.000 {method 'add' of 'set' objects}
    25862    0.013    0.000    0.013    0.000 {method 'append' of 'list' objects}
        1    0.000    0.000    0.000    0.000 {method 'cast' of '_cffi_backend.FFI' objects}
        1    0.000    0.000    0.000    0.000 {method 'disable' of '_lsprof.Profiler' objects}
       44    0.000    0.000    0.000    0.000 {method 'endswith' of 'str' objects}
  1307689    0.056    0.000    0.056    0.000 {method 'extend' of 'list' objects}
      981    0.002    0.000    0.002    0.000 {method 'find' of 'str' objects}
      861    0.006    0.000    0.006    0.000 {method 'flush' of '_io.TextIOWrapper' objects}
       10    0.000    0.000    0.000    0.000 {method 'format' of 'str' objects}
        3    0.000    0.000    0.000    0.000 {method 'from_bytes' of 'type' objects}
 13508620    3.364    0.000    3.668    0.000 {method 'get' of 'dict' objects}
       19    0.000    0.000    0.000    0.000 {method 'get' of 'mappingproxy' objects}
   132829    0.072    0.000    0.072    0.000 {method 'index' of 'list' objects}
        9    0.000    0.000    0.000    0.000 {method 'insert' of 'list' objects}
        8    0.000    0.000    0.000    0.000 {method 'isidentifier' of 'str' objects}
      105    0.000    0.000    0.000    0.000 {method 'issuperset' of 'set' objects}
     7607    0.002    0.000    0.002    0.000 {method 'items' of 'dict' objects}
        3    0.000    0.000    0.000    0.000 {method 'items' of 'mappingproxy' objects}
       44    0.000    0.000    0.000    0.000 {method 'join' of 'str' objects}
        8    0.000    0.000    0.000    0.000 {method 'keys' of 'dict' objects}
     2583    0.004    0.000    0.004    0.000 {method 'lower' of 'str' objects}
        1    0.000    0.000    0.000    0.000 {method 'lstrip' of 'str' objects}
        1    0.000    0.000    0.000    0.000 {method 'partition' of 'str' objects}
        1    0.000    0.000    0.000    0.000 {method 'pop' of 'dict' objects}
      712    0.000    0.000    0.000    0.000 {method 'pop' of 'list' objects}
        1    0.000    0.000    0.000    0.000 {method 'read' of '_io.BufferedReader' objects}
        1    0.000    0.000    0.000    0.000 {method 'read' of '_io.TextIOWrapper' objects}
     1725    0.002    0.000    0.002    0.000 {method 'release' of '_thread.RLock' objects}
     3448    0.005    0.000    0.005    0.000 {method 'replace' of 'str' objects}
        2    0.000    0.000    0.000    0.000 {method 'reverse' of 'list' objects}
     2587    0.004    0.000    0.004    0.000 {method 'rfind' of 'str' objects}
        6    0.000    0.000    0.000    0.000 {method 'rpartition' of 'str' objects}
      887    0.001    0.000    0.001    0.000 {method 'rstrip' of 'str' objects}
        2    0.000    0.000    0.000    0.000 {method 'split' of 'str' objects}
       44    0.000    0.000    0.000    0.000 {method 'startswith' of 'str' objects}
       55    0.000    0.000    0.000    0.000 {method 'strip' of 'str' objects}
     6439    0.009    0.000    0.009    0.000 {method 'update' of 'dict' objects}
     1667    0.001    0.000    0.001    0.000 {method 'update' of 'set' objects}
     1200    0.000    0.000    0.000    0.000 {method 'values' of 'dict' objects}
        2    0.000    0.000    0.000    0.000 {method 'values' of 'mappingproxy' objects}
      861    0.352    0.000    0.362    0.000 {method 'write' of '_io.TextIOWrapper' objects}


********************************************
```
