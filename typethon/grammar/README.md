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
    #[@sequence]
    | ε
    #[@sequence]
    | zero_or_more e

# Where @sequence is a builtin transformer that creates SequenceNode([e1, e2, ..., en])

# e+ means one or more e, this is equivalent to:
one_or_more:
    #[@prepend]
    | e e*

# Where @prepend is a builtin transformer that prepends e to SequenceNode
```

### Parser generator profiling info
```
CPython
DEBUG:typethon.syntax.typethon.parser:Generated tables after 139.31 seconds
         209192130 function calls (196225837 primitive calls) in 139.376 seconds

   Ordered by: standard name

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
      127    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.CaptureNode>:24(__init__)
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
   232176    0.087    0.000    0.087    0.000 <attrs generated methods typethon.grammar.frozen.FrozenSymbol>:16(__eq__)
   272964    0.131    0.000    0.203    0.000 <attrs generated methods typethon.grammar.frozen.FrozenSymbol>:23(__hash__)
   132888    0.032    0.000    0.032    0.000 <attrs generated methods typethon.grammar.frozen.FrozenSymbol>:29(__init__)
     1172    0.001    0.000    0.001    0.000 <attrs generated methods typethon.grammar.generator.ParserState>:23(__init__)
        1    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.generator.TableBuilder>:22(__init__)
 15731129    8.062    0.000   12.334    0.000 <attrs generated methods typethon.grammar.symbols.NonterminalSymbol>:1(__hash__)
       59    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.symbols.NonterminalSymbol>:7(__init__)
 11668667    5.640    0.000    8.755    0.000 <attrs generated methods typethon.grammar.symbols.Production>:16(__hash__)
      125    0.001    0.000    0.001    0.000 <attrs generated methods typethon.grammar.symbols.Production>:21(__init__)
   386048    0.117    0.000    0.117    0.000 <attrs generated methods typethon.grammar.symbols.TerminalSymbol>:16(__eq__)
 12965796    6.446    0.000   24.088    0.000 <attrs generated methods typethon.grammar.symbols.TerminalSymbol>:22(__hash__)
       83    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.symbols.TerminalSymbol>:27(__init__)
       31    0.000    0.000    0.000    0.000 <attrs generated methods typethon.syntax.tokens.DedentToken>:22(__init__)
       55    0.000    0.000    0.000    0.000 <attrs generated methods typethon.syntax.tokens.DirectiveToken>:22(__init__)
      146    0.000    0.000    0.000    0.000 <attrs generated methods typethon.syntax.tokens.IdentifierToken>:23(__init__)
       31    0.000    0.000    0.000    0.000 <attrs generated methods typethon.syntax.tokens.IndentToken>:22(__init__)
       66    0.000    0.000    0.000    0.000 <attrs generated methods typethon.syntax.tokens.StringToken>:23(__init__)
      387    0.000    0.000    0.000    0.000 <attrs generated methods typethon.syntax.tokens.TokenData>:22(__init__)
        8    0.000    0.000    0.000    0.000 <frozen _collections_abc>:439(__subclasshook__)
      837    0.002    0.000    0.005    0.000 <frozen abc>:117(__instancecheck__)
      8/1    0.000    0.000    0.000    0.000 <frozen abc>:121(__subclasscheck__)
        2    0.000    0.000    0.000    0.000 <frozen abc>:146(update_abstractmethods)
        1    0.000    0.000    0.000    0.000 <frozen codecs>:263(__init__)
      860    0.004    0.000    0.007    0.000 <frozen genericpath>:157(_splitext)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:1128(find_spec)
        4    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:1222(__enter__)
        4    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:1226(__exit__)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:124(setdefault)
        1    0.000    0.000    0.001    0.001 <frozen importlib._bootstrap>:1240(_find_spec)
        1    0.000    0.000    0.016    0.016 <frozen importlib._bootstrap>:1304(_find_and_load_unlocked)
        1    0.000    0.000    0.016    0.016 <frozen importlib._bootstrap>:1349(_find_and_load)
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
        2    0.000    0.000    0.011    0.006 <frozen importlib._bootstrap>:480(_call_with_frames_removed)
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
        1    0.000    0.000    0.015    0.015 <frozen importlib._bootstrap>:911(_load_unlocked)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap>:982(find_spec)
       15    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:101(_path_join)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:1017(create_module)
        1    0.000    0.000    0.015    0.015 <frozen importlib._bootstrap_external>:1020(exec_module)
        1    0.000    0.000    0.003    0.003 <frozen importlib._bootstrap_external>:1093(get_code)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:1184(__init__)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:1209(get_filename)
        1    0.000    0.000    0.003    0.003 <frozen importlib._bootstrap_external>:1214(get_data)
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
        1    0.000    0.000    0.001    0.001 <frozen importlib._bootstrap_external>:782(_compile_bytecode)
        1    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:833(spec_from_file_location)
        3    0.000    0.000    0.000    0.000 <frozen importlib._bootstrap_external>:89(_unpack_uint32)
      860    0.011    0.000    0.017    0.000 <frozen ntpath>:222(split)
      860    0.003    0.000    0.010    0.000 <frozen ntpath>:243(splitext)
      860    0.002    0.000    0.019    0.000 <frozen ntpath>:254(basename)
      860    0.001    0.000    0.001    0.000 <frozen ntpath>:34(_get_bothseps)
     2580    0.009    0.000    0.028    0.000 <frozen ntpath>:50(normcase)
        1    0.000    0.000    0.000    0.000 <frozen ntpath>:99(join)
        1    0.000    0.000    0.000    0.000 <string>:1(<module>)
        1    0.000    0.000    0.000    0.000 <string>:1(__create_fn__)
        1    0.000    0.000    0.000    0.000 __init__.py:101(find_spec)
      860    0.008    0.000    0.371    0.000 __init__.py:1011(handle)
        1    0.000    0.000    0.000    0.000 __init__.py:108(<lambda>)
      860    0.006    0.000    0.012    0.000 __init__.py:1131(flush)
      860    0.009    0.000    0.361    0.000 __init__.py:1139(emit)
      860    0.002    0.000    0.003    0.000 __init__.py:129(getLevelName)
        3    0.000    0.000    0.000    0.000 __init__.py:1354(disable)
      838    0.012    0.000    0.532    0.001 __init__.py:1498(debug)
       22    0.000    0.000    0.013    0.001 __init__.py:1510(info)
      860    0.011    0.000    0.053    0.000 __init__.py:1592(findCaller)
      860    0.005    0.000    0.088    0.000 __init__.py:1626(makeRecord)
      860    0.007    0.000    0.531    0.001 __init__.py:1641(_log)
      860    0.004    0.000    0.383    0.000 __init__.py:1667(handle)
      860    0.002    0.000    0.005    0.000 __init__.py:167(<lambda>)
      860    0.007    0.000    0.378    0.000 __init__.py:1721(callHandlers)
        3    0.000    0.000    0.000    0.000 __init__.py:1751(getEffectiveLevel)
      860    0.001    0.000    0.001    0.000 __init__.py:1765(isEnabledFor)
     2580    0.009    0.000    0.037    0.000 __init__.py:197(_is_internal_frame)
      860    0.029    0.000    0.083    0.000 __init__.py:298(__init__)
      860    0.009    0.000    0.009    0.000 __init__.py:391(getMessage)
      860    0.002    0.000    0.002    0.000 __init__.py:455(usesTime)
      860    0.007    0.000    0.007    0.000 __init__.py:463(_format)
      860    0.001    0.000    0.008    0.000 __init__.py:470(format)
      860    0.002    0.000    0.004    0.000 __init__.py:677(usesTime)
      860    0.001    0.000    0.009    0.000 __init__.py:683(formatMessage)
      860    0.004    0.000    0.026    0.000 __init__.py:699(format)
     1720    0.002    0.000    0.002    0.000 __init__.py:840(filter)
      860    0.002    0.000    0.028    0.000 __init__.py:988(format)
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
        1    0.000    0.000    0.016    0.016 cProfile.py:42(print_stats)
        1    0.000    0.000    0.000    0.000 cProfile.py:54(create_stats)
        1    0.000    0.000    0.000    0.000 cp1252.py:22(decode)
       11    0.000    0.000    0.000    0.000 dataclasses.py:1111(<genexpr>)
       11    0.000    0.000    0.000    0.000 dataclasses.py:1172(<genexpr>)
        2    0.000    0.000    0.000    0.000 dataclasses.py:1277(dataclass)
        2    0.000    0.000    0.010    0.005 dataclasses.py:1294(wrap)
        9    0.000    0.000    0.000    0.000 dataclasses.py:288(__init__)
        2    0.000    0.000    0.000    0.000 dataclasses.py:351(__init__)
        9    0.000    0.000    0.000    0.000 dataclasses.py:383(field)
        2    0.000    0.000    0.000    0.000 dataclasses.py:407(_fields_in_init_order)
       11    0.000    0.000    0.000    0.000 dataclasses.py:411(<genexpr>)
        2    0.000    0.000    0.000    0.000 dataclasses.py:412(<genexpr>)
        2    0.000    0.000    0.000    0.000 dataclasses.py:416(_tuple_str)
        2    0.000    0.000    0.000    0.000 dataclasses.py:429(__init__)
        8    0.000    0.000    0.000    0.000 dataclasses.py:437(add_fn)
        2    0.000    0.000    0.008    0.004 dataclasses.py:470(add_fns_to_class)
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
        2    0.001    0.000    0.010    0.005 dataclasses.py:929(_process_class)
      204    0.000    0.000    0.000    0.000 enum.py:1156(__new__)
        9    0.000    0.000    0.000    0.000 enum.py:1217(__init__)
       22    0.000    0.000    0.000    0.000 enum.py:1277(__str__)
 12966350    6.207    0.000    9.462    0.000 enum.py:1312(__hash__)
      588    0.000    0.000    0.001    0.000 enum.py:1589(_get_value)
      196    0.001    0.000    0.002    0.000 enum.py:1607(__and__)
        1    0.000    0.000    0.000    0.000 enum.py:1737(_simple_enum)
        1    0.000    0.000    0.000    0.000 enum.py:1753(convert_class)
        9    0.000    0.000    0.000    0.000 enum.py:37(_is_descriptor)
       14    0.000    0.000    0.000    0.000 enum.py:47(_is_dunder)
        1    0.000    0.000    0.000    0.000 enum.py:498(__new__)
        9    0.000    0.000    0.000    0.000 enum.py:58(_is_sunder)
      204    0.000    0.000    0.001    0.000 enum.py:695(__call__)
        9    0.000    0.000    0.000    0.000 enum.py:78(_is_private)
       13    0.000    0.000    0.000    0.000 enum.py:829(__setattr__)
        1    0.000    0.000    0.000    0.000 frozen.py:116(__init__)
        1    0.000    0.000    0.000    0.000 frozen.py:15(__init__)
   132829    0.224    0.000    0.392    0.000 frozen.py:34(get_frozen_terminal)
     3778    0.001    0.000    0.001    0.000 frozen.py:43(get_frozen_nonterminal)
       59    0.000    0.000    0.000    0.000 frozen.py:56(create_frozen_nonterminal)
      125    0.001    0.000    0.001    0.000 frozen.py:64(create_frozen_production)
      101    0.000    0.000    0.000    0.000 frozen.py:82(add_production_action)
 11668667   27.674    0.000   68.162    0.000 generator.py:120(add_item)
        1    0.000    0.000    0.000    0.000 generator.py:167(add_accept)
   115149    0.291    0.000    1.031    0.000 generator.py:183(add_shift)
    17679    0.040    0.000    0.150    0.000 generator.py:222(add_reduce)
     3653    0.007    0.000    0.018    0.000 generator.py:262(add_goto)
        1    0.000    0.000    0.000    0.000 generator.py:292(__init__)
        1    0.000    0.000    0.000    0.000 generator.py:321(initialize_nonterminals)
        1    0.000    0.000    0.003    0.003 generator.py:325(initialize_productions)
        1    0.000    0.000    0.003    0.003 generator.py:329(generate_symbols)
        1    0.001    0.001    0.002    0.002 generator.py:333(generate_frozen_symbols)
       15    0.000    0.000    0.000    0.000 generator.py:346(should_capture_uninlined_expression)
       30    0.000    0.000    0.000    0.000 generator.py:350(<genexpr>)
      125    0.000    0.000    0.001    0.000 generator.py:352(create_production)
       33    0.000    0.000    0.003    0.000 generator.py:362(initialize_productions_for_rule)
        9    0.000    0.000    0.000    0.000 generator.py:373(add_new_star_expression)
   394/79    0.001    0.000    0.002    0.000 generator.py:407(add_symbols_for_expression)
     7903    0.028    0.000    0.028    0.000 generator.py:52(__init__)
        1    0.000    0.000    0.001    0.001 generator.py:523(compute_epsilon_nonterminals)
      144    0.000    0.000    0.000    0.000 generator.py:526(<genexpr>)
      144    0.000    0.000    0.001    0.000 generator.py:536(<genexpr>)
        1    0.006    0.006    0.014    0.014 generator.py:543(compute_first_sets)
  3384047    2.216    0.000    2.840    0.000 generator.py:57(__eq__)
     1307    0.005    0.000    0.012    0.000 generator.py:572(get_first_set)
     7903   17.089    0.002   95.947    0.012 generator.py:590(compute_closure)
     7902    0.385    0.000  102.238    0.013 generator.py:616(compute_goto)
     1172    0.010    0.000    0.013    0.000 generator.py:637(create_state)
     7902    1.449    0.000    4.288    0.001 generator.py:648(get_equivalent_state)
   501236    0.771    0.000    1.173    0.000 generator.py:65(iter_symbols)
        1    7.185    7.185  133.676  133.676 generator.py:656(compute_canonical_collection)
        1    0.254    0.254  139.222  139.222 generator.py:695(compute_tables)
    21439    0.066    0.000    0.083    0.000 generator.py:71(iter_nonterminal_items)
  8884063    1.758    0.000    1.758    0.000 generator.py:725(<genexpr>)
        1    0.000    0.000  139.242  139.242 generator.py:730(generate)
  3148795    0.987    0.000    0.987    0.000 generator.py:74(<genexpr>)
        1    0.000    0.000  139.305  139.305 generator.py:753(generate_from_grammar)
     1172    0.002    0.000    0.003    0.000 generator.py:79(iter_terminal_items)
   116321    0.054    0.000    0.054    0.000 generator.py:82(<genexpr>)
     7902    0.005    0.000    0.009    0.000 generator.py:99(get_effective_map)
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
      3/1    0.000    0.000    0.001    0.001 inspect.py:2487(_signature_from_callable)
        8    0.000    0.000    0.000    0.000 inspect.py:2754(__init__)
       15    0.000    0.000    0.000    0.000 inspect.py:2807(name)
        7    0.000    0.000    0.000    0.000 inspect.py:2811(default)
       23    0.000    0.000    0.000    0.000 inspect.py:2819(kind)
        7    0.000    0.000    0.000    0.000 inspect.py:2841(__str__)
        3    0.000    0.000    0.000    0.000 inspect.py:302(isclass)
        2    0.000    0.000    0.000    0.000 inspect.py:3042(__init__)
        9    0.000    0.000    0.000    0.000 inspect.py:3089(<genexpr>)
        1    0.000    0.000    0.001    0.001 inspect.py:3094(from_callable)
        1    0.000    0.000    0.000    0.000 inspect.py:310(ismethoddescriptor)
        2    0.000    0.000    0.000    0.000 inspect.py:3102(parameters)
        2    0.000    0.000    0.000    0.000 inspect.py:3106(return_annotation)
        1    0.000    0.000    0.000    0.000 inspect.py:3110(replace)
        1    0.000    0.000    0.000    0.000 inspect.py:3315(__str__)
        1    0.000    0.000    0.000    0.000 inspect.py:3318(format)
        1    0.000    0.000    0.001    0.001 inspect.py:3373(signature)
        3    0.000    0.000    0.000    0.000 inspect.py:386(isfunction)
        1    0.000    0.000    0.000    0.000 inspect.py:534(isbuiltin)
        6    0.000    0.000    0.000    0.000 inspect.py:764(unwrap)
        1    0.000    0.000    0.063    0.063 parser.py:101(parse_rules)
       33    0.001    0.000    0.062    0.002 parser.py:108(parse_rule)
      110    0.000    0.000    0.014    0.000 parser.py:187(parse_rule_action)
    88/79    0.000    0.000    0.031    0.000 parser.py:195(parse_expression)
    88/79    0.001    0.000    0.031    0.000 parser.py:212(parse_expression_group)
  315/169    0.001    0.000    0.024    0.000 parser.py:236(parse_expression_group_item)
        1    0.000    0.000    0.000    0.000 parser.py:24(__init__)
      324    0.000    0.000    0.008    0.000 parser.py:266(parse_expression_suffix)
      179    0.000    0.000    0.002    0.000 parser.py:295(parse_atom)
        1    0.000    0.000    0.063    0.063 parser.py:305(parse_from_source)
      113    0.000    0.000    0.000    0.000 parser.py:42(parse_identifier)
       66    0.000    0.000    0.000    0.000 parser.py:64(parse_string)
        1    0.053    0.053  139.360  139.360 parser.py:71(load_parser_tables)
      654    0.001    0.000    0.052    0.000 parser.py:75(scan_no_whitespace)
      653    0.001    0.000    0.003    0.000 parser.py:83(scan_token)
     1368    0.002    0.000    0.053    0.000 parser.py:95(peek_token)
        1    0.000    0.000    0.011    0.011 pstats.py:1(<module>)
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
     8417    0.004    0.000    0.006    0.000 scanner.py:127(is_eof)
    10411    0.006    0.000    0.008    0.000 scanner.py:130(char_at)
     6329    0.005    0.000    0.010    0.000 scanner.py:136(peek_char)
     4082    0.005    0.000    0.012    0.000 scanner.py:139(consume_char)
      958    0.007    0.000    0.025    0.000 scanner.py:147(consume_while)
       66    0.000    0.000    0.000    0.000 scanner.py:163(string_terminated)
      263    0.003    0.000    0.006    0.000 scanner.py:176(scan_indentation)
      146    0.001    0.000    0.012    0.000 scanner.py:235(identifier_or_string)
      203    0.000    0.000    0.001    0.000 scanner.py:339(newline)
      930    0.000    0.000    0.000    0.000 scanner.py:35(is_whitespace)
       66    0.001    0.000    0.005    0.000 scanner.py:351(string)
       60    0.001    0.000    0.011    0.000 scanner.py:388(comment)
      807    0.000    0.000    0.000    0.000 scanner.py:39(is_indent)
     1321    0.000    0.000    0.000    0.000 scanner.py:394(<lambda>)
      276    0.002    0.000    0.004    0.000 scanner.py:406(token)
      263    0.000    0.000    0.000    0.000 scanner.py:43(is_blank)
      716    0.004    0.000    0.051    0.000 scanner.py:438(scan)
      897    0.001    0.000    0.001    0.000 scanner.py:47(is_identifier_start)
     1297    0.001    0.000    0.001    0.000 scanner.py:51(is_identifier)
      605    0.000    0.000    0.000    0.000 scanner.py:61(is_digit)
        1    0.000    0.000    0.000    0.000 scanner.py:78(__init__)
       22    0.000    0.000    0.000    0.000 symbols.py:52(__str__)
      215    0.000    0.000    0.000    0.000 symbols.py:65(add_symbol)
        9    0.000    0.000    0.000    0.000 symbols.py:71(insert_symbol)
      860    0.002    0.000    0.002    0.000 threading.py:1096(name)
      860    0.002    0.000    0.002    0.000 threading.py:1429(current_thread)
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
       29    0.000    0.000    0.001    0.000 typing.py:426(inner)
       14    0.000    0.000    0.000    0.000 {built-in method __new__ of type object at 0x00007FFBCEC398A0}
      837    0.003    0.000    0.003    0.000 {built-in method _abc._abc_instancecheck}
      8/1    0.000    0.000    0.000    0.000 {built-in method _abc._abc_subclasscheck}
        1    0.000    0.000    0.000    0.000 {built-in method _codecs.charmap_decode}
        1    0.000    0.000    0.000    0.000 {built-in method _imp._fix_co_filename}
        6    0.000    0.000    0.000    0.000 {built-in method _imp.acquire_lock}
        1    0.000    0.000    0.000    0.000 {built-in method _imp.find_frozen}
        1    0.000    0.000    0.000    0.000 {built-in method _imp.is_builtin}
        6    0.000    0.000    0.000    0.000 {built-in method _imp.release_lock}
        1    0.002    0.002    0.002    0.002 {built-in method _io.open_code}
        1    0.000    0.000    0.000    0.000 {built-in method _io.open}
        1    0.000    0.000    0.000    0.000 {built-in method _thread.allocate_lock}
     1722    0.002    0.000    0.002    0.000 {built-in method _thread.get_ident}
        1    0.000    0.000    0.000    0.000 {built-in method _weakref._remove_dead_weakref}
     2580    0.013    0.000    0.013    0.000 {built-in method _winapi.LCMapStringEx}
        5    0.000    0.000    0.001    0.000 {built-in method builtins.__build_class__}
     1305    1.906    0.001    3.665    0.003 {built-in method builtins.any}
        5    0.000    0.000    0.000    0.000 {built-in method builtins.callable}
      3/1    0.007    0.002    0.011    0.011 {built-in method builtins.exec}
       82    0.000    0.000    0.000    0.000 {built-in method builtins.getattr}
     1763    0.003    0.000    0.003    0.000 {built-in method builtins.hasattr}
53604906/40639110   18.896    0.000   25.102    0.000 {built-in method builtins.hash}
        6    0.000    0.000    0.000    0.000 {built-in method builtins.id}
 14919710    3.247    0.000    3.252    0.000 {built-in method builtins.isinstance}
        2    0.000    0.000    0.000    0.000 {built-in method builtins.issubclass}
 35033945    7.785    0.000    7.785    0.000 {built-in method builtins.len}
        1    0.000    0.000    0.000    0.000 {built-in method builtins.locals}
      862    0.001    0.000    0.001    0.000 {built-in method builtins.max}
        1    0.000    0.000    0.000    0.000 {built-in method builtins.repr}
       27    0.000    0.000    0.000    0.000 {built-in method builtins.setattr}
        2    0.000    0.000    0.000    0.000 {built-in method builtins.vars}
        3    0.000    0.000    0.000    0.000 {built-in method from_bytes}
        1    0.001    0.001    0.001    0.001 {built-in method marshal.loads}
      864    0.002    0.000    0.002    0.000 {built-in method nt._path_splitroot_ex}
        1    0.000    0.000    0.000    0.000 {built-in method nt._path_splitroot}
     4307    0.002    0.000    0.002    0.000 {built-in method nt.fspath}
      860    0.002    0.000    0.002    0.000 {built-in method nt.getpid}
        5    0.000    0.000    0.000    0.000 {built-in method nt.stat}
      860    0.003    0.000    0.003    0.000 {built-in method sys._getframe}
        6    0.000    0.000    0.000    0.000 {built-in method sys.getrecursionlimit}
       16    0.000    0.000    0.000    0.000 {built-in method sys.intern}
        2    0.000    0.000    0.000    0.000 {built-in method time.perf_counter}
      860    0.004    0.000    0.004    0.000 {built-in method time.time_ns}
        8    0.000    0.000    0.000    0.000 {method '__contains__' of 'frozenset' objects}
        2    0.000    0.000    0.000    0.000 {method '__exit__' of '_io._IOBase' objects}
     1725    0.002    0.000    0.002    0.000 {method '__exit__' of '_thread.RLock' objects}
        4    0.000    0.000    0.000    0.000 {method '__typing_prepare_subst__' of 'typing.TypeVar' objects}
 11669924   10.125    0.000   18.985    0.000 {method 'add' of 'set' objects}
  3250109    1.054    0.000    1.054    0.000 {method 'append' of 'list' objects}
        1    0.000    0.000    0.000    0.000 {method 'disable' of '_lsprof.Profiler' objects}
       65    0.000    0.000    0.000    0.000 {method 'endswith' of 'str' objects}
        1    0.000    0.000    0.000    0.000 {method 'extend' of 'list' objects}
      980    0.001    0.000    0.001    0.000 {method 'find' of 'str' objects}
      860    0.003    0.000    0.003    0.000 {method 'flush' of '_io.TextIOWrapper' objects}
       10    0.000    0.000    0.000    0.000 {method 'format' of 'str' objects}
  7047232    7.908    0.000   18.164    0.000 {method 'get' of 'dict' objects}
       19    0.000    0.000    0.000    0.000 {method 'get' of 'mappingproxy' objects}
   132829    0.137    0.000    0.137    0.000 {method 'index' of 'list' objects}
        9    0.000    0.000    0.000    0.000 {method 'insert' of 'list' objects}
        8    0.000    0.000    0.000    0.000 {method 'isidentifier' of 'str' objects}
      105    0.000    0.000    0.001    0.000 {method 'issuperset' of 'set' objects}
    22616    0.017    0.000    0.017    0.000 {method 'items' of 'dict' objects}
        3    0.000    0.000    0.000    0.000 {method 'items' of 'mappingproxy' objects}
       48    0.000    0.000    0.000    0.000 {method 'join' of 'str' objects}
  1002474    0.403    0.000    0.403    0.000 {method 'keys' of 'dict' objects}
        1    0.000    0.000    0.000    0.000 {method 'pop' of 'dict' objects}
      712    0.000    0.000    0.000    0.000 {method 'pop' of 'list' objects}
        1    0.001    0.001    0.001    0.001 {method 'read' of '_io.BufferedReader' objects}
        1    0.000    0.000    0.000    0.000 {method 'read' of '_io.TextIOWrapper' objects}
        1    0.000    0.000    0.000    0.000 {method 'remove' of 'list' objects}
     2584    0.003    0.000    0.003    0.000 {method 'replace' of 'str' objects}
     2584    0.002    0.000    0.002    0.000 {method 'rfind' of 'str' objects}
        7    0.000    0.000    0.000    0.000 {method 'rpartition' of 'str' objects}
      907    0.002    0.000    0.002    0.000 {method 'rstrip' of 'str' objects}
        9    0.000    0.000    0.000    0.000 {method 'setdefault' of 'dict' objects}
        2    0.000    0.000    0.000    0.000 {method 'split' of 'str' objects}
       55    0.000    0.000    0.000    0.000 {method 'startswith' of 'str' objects}
       55    0.000    0.000    0.000    0.000 {method 'strip' of 'str' objects}
        4    0.000    0.000    0.000    0.000 {method 'update' of 'dict' objects}
     1667    0.001    0.000    0.001    0.000 {method 'update' of 'set' objects}
     1200    0.001    0.000    0.001    0.000 {method 'values' of 'dict' objects}
        2    0.000    0.000    0.000    0.000 {method 'values' of 'mappingproxy' objects}
      860    0.313    0.000    0.313    0.000 {method 'write' of '_io.TextIOWrapper' objects}


********************************************

PyPy
DEBUG:typethon.syntax.typethon.parser:Generated tables after 28.13 seconds
         225055939 function calls (205213675 primitive calls) in 28.020 seconds

   Ordered by: standard name

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
      127    0.001    0.000    0.001    0.000 <attrs generated methods typethon.grammar.ast.CaptureNode>:24(__init__)
       52    0.003    0.000    0.003    0.000 <attrs generated methods typethon.grammar.ast.GroupNode>:24(__init__)
       20    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.KeywordNode>:24(__init__)
      100    0.014    0.000    0.014    0.000 <attrs generated methods typethon.grammar.ast.NameNode>:24(__init__)
       11    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.OptionalNode>:24(__init__)
        6    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.PlusNode>:24(__init__)
       79    0.001    0.000    0.001    0.000 <attrs generated methods typethon.grammar.ast.RuleItemNode>:25(__init__)
       33    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.RuleNode>:26(__init__)
        3    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.ast.StarNode>:24(__init__)
       59    0.001    0.000    0.001    0.000 <attrs generated methods typethon.grammar.ast.TokenNode>:24(__init__)
      125    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.frozen.FrozenProduction>:33(__init__)
   232176    0.128    0.000    0.128    0.000 <attrs generated methods typethon.grammar.frozen.FrozenSymbol>:16(__eq__)
   272964    0.041    0.000    0.053    0.000 <attrs generated methods typethon.grammar.frozen.FrozenSymbol>:23(__hash__)
   132888    0.013    0.000    0.013    0.000 <attrs generated methods typethon.grammar.frozen.FrozenSymbol>:29(__init__)
     1172    0.017    0.000    0.017    0.000 <attrs generated methods typethon.grammar.generator.ParserState>:23(__init__)
        1    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.generator.TableBuilder>:22(__init__)
 15793144    0.972    0.000    1.245    0.000 <attrs generated methods typethon.grammar.symbols.NonterminalSymbol>:1(__hash__)
       59    0.000    0.000    0.000    0.000 <attrs generated methods typethon.grammar.symbols.NonterminalSymbol>:7(__init__)
 11668667    0.622    0.000    0.778    0.000 <attrs generated methods typethon.grammar.symbols.Production>:16(__hash__)
      125    0.001    0.000    0.001    0.000 <attrs generated methods typethon.grammar.symbols.Production>:21(__init__)
   386048    0.271    0.000    0.271    0.000 <attrs generated methods typethon.grammar.symbols.TerminalSymbol>:16(__eq__)
 13090138    0.951    0.000    2.384    0.000 <attrs generated methods typethon.grammar.symbols.TerminalSymbol>:22(__hash__)
       83    0.001    0.000    0.001    0.000 <attrs generated methods typethon.grammar.symbols.TerminalSymbol>:27(__init__)
       31    0.001    0.000    0.001    0.000 <attrs generated methods typethon.syntax.tokens.DedentToken>:22(__init__)
       55    0.019    0.000    0.019    0.000 <attrs generated methods typethon.syntax.tokens.DirectiveToken>:22(__init__)
      146    0.005    0.000    0.005    0.000 <attrs generated methods typethon.syntax.tokens.IdentifierToken>:23(__init__)
       31    0.001    0.000    0.001    0.000 <attrs generated methods typethon.syntax.tokens.IndentToken>:22(__init__)
       66    0.002    0.000    0.002    0.000 <attrs generated methods typethon.syntax.tokens.StringToken>:23(__init__)
      387    0.011    0.000    0.011    0.000 <attrs generated methods typethon.syntax.tokens.TokenData>:22(__init__)
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
      211    0.001    0.000    0.002    0.000 <frozen importlib._bootstrap>:198(cb)
        2    0.000    0.000    0.006    0.003 <frozen importlib._bootstrap>:233(_call_with_frames_removed)
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
      860    0.011    0.000    0.043    0.000 __init__.py:1087(flush)
      860    0.017    0.000    0.760    0.001 __init__.py:1098(emit)
      860    0.003    0.000    0.004    0.000 __init__.py:123(getLevelName)
        3    0.000    0.000    0.000    0.000 __init__.py:1319(disable)
      838    0.015    0.000    1.242    0.001 __init__.py:1467(debug)
       22    0.000    0.000    0.028    0.001 __init__.py:1479(info)
      860    0.023    0.000    0.154    0.000 __init__.py:1561(findCaller)
      860    0.010    0.000    0.269    0.000 __init__.py:1595(makeRecord)
      860    0.012    0.000    1.248    0.001 __init__.py:1610(_log)
      860    0.005    0.000    0.814    0.001 __init__.py:1636(handle)
      860    0.011    0.000    0.077    0.000 __init__.py:164(<lambda>)
      860    0.024    0.000    0.804    0.001 __init__.py:1690(callHandlers)
        3    0.000    0.000    0.000    0.000 __init__.py:1720(getEffectiveLevel)
      860    0.006    0.000    0.006    0.000 __init__.py:1734(isEnabledFor)
     2580    0.019    0.000    0.053    0.000 __init__.py:194(_is_internal_frame)
        3    0.000    0.000    0.000    0.000 __init__.py:228(_acquireLock)
        3    0.000    0.000    0.000    0.000 __init__.py:237(_releaseLock)
      860    0.092    0.000    0.260    0.000 __init__.py:292(__init__)
      860    0.021    0.000    0.021    0.000 __init__.py:368(getMessage)
      860    0.005    0.000    0.007    0.000 __init__.py:432(usesTime)
      860    0.013    0.000    0.013    0.000 __init__.py:440(_format)
      860    0.001    0.000    0.014    0.000 __init__.py:447(format)
      860    0.002    0.000    0.009    0.000 __init__.py:652(usesTime)
      860    0.005    0.000    0.020    0.000 __init__.py:658(formatMessage)
      860    0.006    0.000    0.056    0.000 __init__.py:674(format)
     1720    0.008    0.000    0.008    0.000 __init__.py:815(filter)
        1    0.000    0.000    0.000    0.000 __init__.py:89(find_spec)
     1720    0.012    0.000    0.022    0.000 __init__.py:922(acquire)
     1720    0.004    0.000    0.006    0.000 __init__.py:929(release)
      860    0.022    0.000    0.077    0.000 __init__.py:942(format)
        1    0.000    0.000    0.000    0.000 __init__.py:96(<lambda>)
      860    0.005    0.000    0.780    0.001 __init__.py:965(handle)
        8    0.000    0.000    0.000    0.000 _collections_abc.py:409(__subclasshook__)
        1    0.000    0.000    0.000    0.000 _winapi.py:416(CloseHandle)
        1    0.000    0.000    0.000    0.000 _winapi.py:53(_int2handle)
      837    0.041    0.000    0.042    0.000 abc.py:117(__instancecheck__)
      8/1    0.001    0.000    0.001    0.001 abc.py:121(__subclasscheck__)
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
        6    0.000    0.000    0.001    0.000 dataclasses.py:401(_tuple_str)
        6    0.000    0.000    0.000    0.000 dataclasses.py:410(<listcomp>)
        8    0.000    0.000    0.001    0.000 dataclasses.py:413(_create_fn)
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
        2    0.000    0.000    0.001    0.001 dataclasses.py:638(_hash_fn)
        9    0.000    0.000    0.000    0.000 dataclasses.py:646(_is_classvar)
        9    0.000    0.000    0.000    0.000 dataclasses.py:654(_is_initvar)
        9    0.000    0.000    0.000    0.000 dataclasses.py:660(_is_kw_only)
        9    0.000    0.000    0.000    0.000 dataclasses.py:723(_get_field)
       10    0.000    0.000    0.000    0.000 dataclasses.py:820(_set_qualname)
        8    0.000    0.000    0.000    0.000 dataclasses.py:827(_set_new_attribute)
        2    0.000    0.000    0.001    0.001 dataclasses.py:845(_hash_add)
        2    0.000    0.000    0.000    0.000 dataclasses.py:846(<listcomp>)
        2    0.000    0.000    0.004    0.002 dataclasses.py:884(_process_class)
      204    0.001    0.000    0.001    0.000 enum.py:1095(__new__)
        9    0.000    0.000    0.000    0.000 enum.py:1151(__init__)
       22    0.000    0.000    0.000    0.000 enum.py:1197(__str__)
 13090692    0.477    0.000    0.678    0.000 enum.py:1232(__hash__)
      588    0.002    0.000    0.003    0.000 enum.py:1507(_get_value)
      196    0.017    0.000    0.022    0.000 enum.py:1525(__and__)
        1    0.000    0.000    0.000    0.000 enum.py:1652(_simple_enum)
        1    0.000    0.000    0.001    0.001 enum.py:1668(convert_class)
        9    0.000    0.000    0.000    0.000 enum.py:229(__set_name__)
        9    0.000    0.000    0.000    0.000 enum.py:38(_is_descriptor)
       12    0.000    0.000    0.000    0.000 enum.py:48(_is_dunder)
        1    0.000    0.000    0.000    0.000 enum.py:499(__new__)
        9    0.000    0.000    0.000    0.000 enum.py:59(_is_sunder)
      204    0.002    0.000    0.003    0.000 enum.py:688(__call__)
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
        1    0.000    0.000    0.007    0.007 frozen importlib._bootstrap_external:949(exec_module)
        8    0.000    0.000    0.000    0.000 frozen importlib._bootstrap_external:96(_path_join)
        1    0.000    0.000    0.000    0.000 frozen.py:116(__init__)
        1    0.000    0.000    0.000    0.000 frozen.py:15(__init__)
   132829    0.038    0.000    0.116    0.000 frozen.py:34(get_frozen_terminal)
     3778    0.001    0.000    0.001    0.000 frozen.py:43(get_frozen_nonterminal)
       59    0.003    0.000    0.003    0.000 frozen.py:56(create_frozen_nonterminal)
      125    0.001    0.000    0.001    0.000 frozen.py:64(create_frozen_production)
      101    0.000    0.000    0.000    0.000 frozen.py:82(add_production_action)
        5    0.000    0.000    0.000    0.000 functools.py:289(__new__)
        2    0.000    0.000    0.000    0.000 functools.py:39(update_wrapper)
  3246999    0.119    0.000    1.660    0.000 functools.py:453(__init__)
  3248312    0.044    0.000    0.044    0.000 functools.py:457(__hash__)
  3246999    0.181    0.000    1.898    0.000 functools.py:460(_make_key)
        2    0.000    0.000    0.000    0.000 functools.py:69(wraps)
 11668667    2.038    0.000    9.142    0.000 generator.py:120(add_item)
        1    0.000    0.000    0.000    0.000 generator.py:167(add_accept)
   115149    0.121    0.000    0.453    0.000 generator.py:183(add_shift)
    17679    0.040    0.000    0.125    0.000 generator.py:222(add_reduce)
     3653    0.004    0.000    0.007    0.000 generator.py:262(add_goto)
        1    0.000    0.000    0.000    0.000 generator.py:292(__init__)
        1    0.000    0.000    0.000    0.000 generator.py:321(initialize_nonterminals)
        1    0.000    0.000    0.013    0.013 generator.py:325(initialize_productions)
        1    0.000    0.000    0.013    0.013 generator.py:329(generate_symbols)
        1    0.001    0.001    0.006    0.006 generator.py:333(generate_frozen_symbols)
       15    0.000    0.000    0.000    0.000 generator.py:346(should_capture_uninlined_expression)
       30    0.000    0.000    0.000    0.000 generator.py:350(<genexpr>)
      125    0.001    0.000    0.002    0.000 generator.py:352(create_production)
       33    0.000    0.000    0.013    0.000 generator.py:362(initialize_productions_for_rule)
        9    0.000    0.000    0.002    0.000 generator.py:373(add_new_star_expression)
   394/79    0.006    0.000    0.011    0.000 generator.py:407(add_symbols_for_expression)
     7903    0.219    0.000    0.219    0.000 generator.py:52(__init__)
        1    0.001    0.001    0.002    0.002 generator.py:523(compute_epsilon_nonterminals)
      144    0.000    0.000    0.000    0.000 generator.py:526(<genexpr>)
      144    0.000    0.000    0.001    0.000 generator.py:536(<genexpr>)
        1    0.078    0.078    0.122    0.122 generator.py:543(compute_first_sets)
  3384957    1.390    0.000    1.556    0.000 generator.py:57(__eq__)
     1307    0.039    0.000    0.056    0.000 generator.py:572(get_first_set)
     7903    3.924    0.000   14.953    0.002 generator.py:590(compute_closure)
     7902    0.407    0.000   17.658    0.002 generator.py:616(compute_goto)
     1172    0.037    0.000    0.067    0.000 generator.py:637(create_state)
     7902    0.547    0.000    2.103    0.000 generator.py:648(get_equivalent_state)
   501256    0.195    0.000    0.315    0.000 generator.py:65(iter_symbols)
        1    1.622    1.622   25.832   25.832 generator.py:656(compute_canonical_collection)
        1    0.451    0.451   27.134   27.134 generator.py:695(compute_tables)
    21439    0.027    0.000    0.029    0.000 generator.py:71(iter_nonterminal_items)
  8884422    0.144    0.000    0.144    0.000 generator.py:725(<genexpr>)
        1    0.000    0.000   27.278   27.278 generator.py:730(generate)
  3148795    0.173    0.000    0.173    0.000 generator.py:74(<genexpr>)
        1    0.000    0.000   28.109   28.109 generator.py:753(generate_from_grammar)
     1172    0.007    0.000    0.007    0.000 generator.py:79(iter_terminal_items)
   116321    0.016    0.000    0.016    0.000 generator.py:82(<genexpr>)
     7902    0.015    0.000    0.027    0.000 generator.py:99(get_effective_map)
      860    0.008    0.000    0.018    0.000 genericpath.py:121(_splitext)
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
      860    0.015    0.000    0.018    0.000 ntpath.py:155(splitdrive)
      860    0.032    0.000    0.058    0.000 ntpath.py:209(split)
      860    0.006    0.000    0.025    0.000 ntpath.py:232(splitext)
      860    0.005    0.000    0.063    0.000 ntpath.py:243(basename)
      860    0.004    0.000    0.005    0.000 ntpath.py:36(_get_bothseps)
     2580    0.016    0.000    0.034    0.000 ntpath.py:71(normcase)
        1    0.000    0.000    0.791    0.791 parser.py:101(parse_rules)
       33    0.006    0.000    0.791    0.024 parser.py:108(parse_rule)
      110    0.001    0.000    0.130    0.001 parser.py:187(parse_rule_action)
    88/79    0.001    0.000    0.328    0.004 parser.py:195(parse_expression)
    88/79    0.006    0.000    0.327    0.004 parser.py:212(parse_expression_group)
  315/169    0.016    0.000    0.241    0.001 parser.py:236(parse_expression_group_item)
        1    0.000    0.000    0.001    0.001 parser.py:24(__init__)
      324    0.003    0.000    0.073    0.000 parser.py:266(parse_expression_suffix)
      179    0.008    0.000    0.034    0.000 parser.py:295(parse_atom)
        1    0.000    0.000    0.792    0.792 parser.py:305(parse_from_source)
      113    0.004    0.000    0.019    0.000 parser.py:42(parse_identifier)
       66    0.002    0.000    0.003    0.000 parser.py:64(parse_string)
        1    0.002    0.002   28.132   28.132 parser.py:71(load_parser_tables)
      654    0.024    0.000    0.694    0.001 parser.py:75(scan_no_whitespace)
      653    0.008    0.000    0.038    0.000 parser.py:83(scan_token)
     1368    0.014    0.000    0.684    0.001 parser.py:95(peek_token)
        2    0.000    0.000    0.000    0.000 pathlib.py:147(splitroot)
        2    0.000    0.000    0.001    0.000 pathlib.py:484(_parse_args)
        1    0.000    0.000    0.001    0.001 pathlib.py:504(_from_parts)
        2    0.000    0.000    0.000    0.000 pathlib.py:515(_from_parsed_parts)
        1    0.000    0.000    0.000    0.000 pathlib.py:523(_format_parsed_parts)
        1    0.000    0.000    0.000    0.000 pathlib.py:530(_make_child)
        1    0.000    0.000    0.000    0.000 pathlib.py:536(__str__)
        1    0.000    0.000    0.000    0.000 pathlib.py:546(__fspath__)
        2    0.000    0.000    0.000    0.000 pathlib.py:56(parse_parts)
        1    0.000    0.000    0.000    0.000 pathlib.py:765(__truediv__)
        1    0.000    0.000    0.000    0.000 pathlib.py:777(parent)
        1    0.000    0.000    0.001    0.001 pathlib.py:868(__new__)
        1    0.000    0.000    0.000    0.000 pathlib.py:94(join_parsed_parts)
        1    0.000    0.000    0.006    0.006 pstats.py:1(<module>)
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
     8417    0.042    0.000    0.053    0.000 scanner.py:127(is_eof)
    10411    0.066    0.000    0.076    0.000 scanner.py:130(char_at)
     6329    0.069    0.000    0.107    0.000 scanner.py:136(peek_char)
     4082    0.092    0.000    0.159    0.000 scanner.py:139(consume_char)
      958    0.132    0.000    0.346    0.000 scanner.py:147(consume_while)
       66    0.000    0.000    0.000    0.000 scanner.py:163(string_terminated)
      263    0.034    0.000    0.107    0.000 scanner.py:176(scan_indentation)
      146    0.004    0.000    0.143    0.001 scanner.py:235(identifier_or_string)
      203    0.007    0.000    0.019    0.000 scanner.py:339(newline)
      930    0.010    0.000    0.010    0.000 scanner.py:35(is_whitespace)
       66    0.005    0.000    0.032    0.000 scanner.py:351(string)
       60    0.013    0.000    0.202    0.003 scanner.py:388(comment)
      807    0.002    0.000    0.002    0.000 scanner.py:39(is_indent)
     1321    0.003    0.000    0.003    0.000 scanner.py:394(<lambda>)
      276    0.009    0.000    0.023    0.000 scanner.py:406(token)
      263    0.001    0.000    0.001    0.000 scanner.py:43(is_blank)
      716    0.058    0.000    0.670    0.001 scanner.py:438(scan)
      897    0.006    0.000    0.006    0.000 scanner.py:47(is_identifier_start)
     1297    0.024    0.000    0.024    0.000 scanner.py:51(is_identifier)
      605    0.002    0.000    0.002    0.000 scanner.py:61(is_digit)
        1    0.000    0.000    0.000    0.000 scanner.py:78(__init__)
        1    0.000    0.000    0.000    0.000 subprocess.py:1120(__del__)
        1    0.000    0.000    0.000    0.000 subprocess.py:1576(_internal_poll)
        6    0.000    0.000    0.000    0.000 subprocess.py:218(Close)
       22    0.000    0.000    0.000    0.000 symbols.py:52(__str__)
      215    0.001    0.000    0.001    0.000 symbols.py:65(add_symbol)
        9    0.000    0.000    0.000    0.000 symbols.py:71(insert_symbol)
      860    0.002    0.000    0.002    0.000 threading.py:1163(name)
      860    0.003    0.000    0.003    0.000 threading.py:1464(current_thread)
        9    0.000    0.000    0.000    0.000 types.py:168(__init__)
       25    0.004    0.000    0.033    0.001 typing.py:1266(_is_dunder)
        3    0.000    0.000    0.000    0.000 typing.py:1279(__init__)
       27    0.000    0.000    0.001    0.000 typing.py:1285(__call__)
        2    0.001    0.001    0.005    0.003 typing.py:1310(__getattr__)
       23    0.000    0.000    0.029    0.001 typing.py:1320(__setattr__)
        3    0.000    0.000    0.033    0.011 typing.py:1376(__init__)
        9    0.000    0.000    0.000    0.000 typing.py:1381(<genexpr>)
        1    0.000    0.000    0.000    0.000 typing.py:1586(__getitem__)
        6    0.000    0.000    0.000    0.000 typing.py:159(_type_convert)
        3    0.000    0.000    0.000    0.000 typing.py:1591(<genexpr>)
        1    0.000    0.000    0.000    0.000 typing.py:1595(copy_with)
        2    0.000    0.000    0.000    0.000 typing.py:168(_type_check)
        2    0.000    0.000    0.034    0.017 typing.py:1830(__class_getitem__)
        6    0.000    0.000    0.000    0.000 typing.py:1844(<genexpr>)
        3    0.004    0.001    0.004    0.001 typing.py:251(_collect_parameters)
        3    0.000    0.000    0.000    0.000 typing.py:284(_check_generic)
       29    0.002    0.000    0.050    0.002 typing.py:373(inner)
      860    0.005    0.000    0.008    0.000 utf_8.py:19(encode)
        5    0.000    0.000    0.000    0.000 {built-in function __build_class__}
        1    0.000    0.000    0.000    0.000 {built-in function _codecs.utf_8_decode}
      860    0.003    0.000    0.003    0.000 {built-in function _codecs.utf_8_encode}
        1    0.000    0.000    0.000    0.000 {built-in function _imp._fix_co_filename}
      216    0.000    0.000    0.000    0.000 {built-in function _imp.acquire_lock}
        1    0.000    0.000    0.000    0.000 {built-in function _imp.find_frozen}
        1    0.000    0.000    0.000    0.000 {built-in function _imp.is_builtin}
      216    0.000    0.000    0.000    0.000 {built-in function _imp.release_lock}
        1    0.000    0.000    0.000    0.000 {built-in function _io.open_code}
        1    0.002    0.002    0.002    0.002 {built-in function _io.open}
        2    0.000    0.000    0.000    0.000 {built-in function _thread.allocate_lock}
     1722    0.002    0.000    0.002    0.000 {built-in function _thread.get_ident}
       10    0.000    0.000    0.000    0.000 {built-in function callable}
        1    0.000    0.000    0.000    0.000 {built-in function cpyext.is_cpyext_function}
      9/1    0.001    0.000    0.006    0.006 {built-in function exec}
       90    0.000    0.000    0.000    0.000 {built-in function getattr}
     1759    0.008    0.000    0.008    0.000 {built-in function hasattr}
57162604/37320836    2.002    0.000    2.885    0.000 {built-in function hash}
        2    0.000    0.000    0.000    0.000 {built-in function id}
 14919746    0.298    0.000    0.340    0.000 {built-in function isinstance}
        2    0.000    0.000    0.000    0.000 {built-in function issubclass}
 38281780    0.624    0.000    0.624    0.000 {built-in function len}
        1    0.000    0.000    0.000    0.000 {built-in function locals}
        1    0.000    0.000    0.000    0.000 {built-in function marshal.loads}
      862    0.005    0.000    0.005    0.000 {built-in function max}
        1    0.000    0.000    0.000    0.000 {built-in function nt._path_splitroot}
     5165    0.003    0.000    0.003    0.000 {built-in function nt.fspath}
      860    0.006    0.000    0.006    0.000 {built-in function nt.getpid}
        4    0.001    0.000    0.001    0.000 {built-in function nt.stat}
        1    0.000    0.000    0.000    0.000 {built-in function repr}
       33    0.000    0.000    0.000    0.000 {built-in function setattr}
      860    0.067    0.000    0.067    0.000 {built-in function sys._getframe}
        2    0.000    0.000    0.000    0.000 {built-in function sys.getrecursionlimit}
        9    0.000    0.000    0.000    0.000 {built-in function sys.intern}
        2    0.000    0.000    0.000    0.000 {built-in function time.perf_counter}
      860    0.010    0.000    0.010    0.000 {built-in function time.time}
        8    0.000    0.000    0.000    0.000 {method '__contains__' of 'frozenset' objects}
        1    0.000    0.000    0.000    0.000 {method '__exit__' of '_io._IOBase' objects}
        2    0.000    0.000    0.000    0.000 {method '__exit__' of '_thread.lock' objects}
        1    0.000    0.000    0.000    0.000 {method '__get__' of 'function' objects}
       10    0.000    0.000    0.000    0.000 {method '__get__' of 'getset_descriptor' objects}
        9    0.000    0.000    0.000    0.000 {method '__new__' of 'EnumType' objects}
        1    0.000    0.000    0.000    0.000 {method '__new__' of 'type' objects}
       13    0.000    0.000    0.000    0.000 {method '__setattr__' of 'EnumType' objects}
       23    0.000    0.000    0.000    0.000 {method '__setattr__' of '_BaseGenericAlias' objects}
     1723    0.009    0.000    0.009    0.000 {method 'acquire' of '_thread.RLock' objects}
 11669924    4.402    0.000    5.401    0.000 {method 'add' of 'set' objects}
  3250084    0.166    0.000    0.166    0.000 {method 'append' of 'list' objects}
        1    0.000    0.000    0.000    0.000 {method 'cast' of '_cffi_backend.FFI' objects}
        1    0.000    0.000    0.000    0.000 {method 'disable' of '_lsprof.Profiler' objects}
       44    0.000    0.000    0.000    0.000 {method 'endswith' of 'str' objects}
      980    0.005    0.000    0.005    0.000 {method 'find' of 'str' objects}
      860    0.011    0.000    0.011    0.000 {method 'flush' of '_io.TextIOWrapper' objects}
       10    0.000    0.000    0.000    0.000 {method 'format' of 'str' objects}
        3    0.000    0.000    0.000    0.000 {method 'from_bytes' of 'type' objects}
  7046544    2.999    0.000    4.132    0.000 {method 'get' of 'dict' objects}
       19    0.000    0.000    0.000    0.000 {method 'get' of 'mappingproxy' objects}
   132829    0.065    0.000    0.065    0.000 {method 'index' of 'list' objects}
        9    0.000    0.000    0.000    0.000 {method 'insert' of 'list' objects}
        8    0.000    0.000    0.000    0.000 {method 'isidentifier' of 'str' objects}
      105    0.000    0.000    0.001    0.000 {method 'issuperset' of 'set' objects}
    22611    0.003    0.000    0.003    0.000 {method 'items' of 'dict' objects}
        3    0.000    0.000    0.000    0.000 {method 'items' of 'mappingproxy' objects}
       44    0.001    0.000    0.001    0.000 {method 'join' of 'str' objects}
        8    0.000    0.000    0.000    0.000 {method 'keys' of 'dict' objects}
     2580    0.003    0.000    0.003    0.000 {method 'lower' of 'str' objects}
        1    0.000    0.000    0.000    0.000 {method 'lstrip' of 'str' objects}
        1    0.000    0.000    0.000    0.000 {method 'partition' of 'str' objects}
        1    0.000    0.000    0.000    0.000 {method 'pop' of 'dict' objects}
      711    0.001    0.000    0.001    0.000 {method 'pop' of 'list' objects}
        1    0.000    0.000    0.000    0.000 {method 'read' of '_io.BufferedReader' objects}
        1    0.001    0.001    0.001    0.001 {method 'read' of '_io.TextIOWrapper' objects}
     1723    0.002    0.000    0.002    0.000 {method 'release' of '_thread.RLock' objects}
     3444    0.007    0.000    0.007    0.000 {method 'replace' of 'str' objects}
        2    0.000    0.000    0.000    0.000 {method 'reverse' of 'list' objects}
     2584    0.005    0.000    0.005    0.000 {method 'rfind' of 'str' objects}
        6    0.000    0.000    0.000    0.000 {method 'rpartition' of 'str' objects}
      886    0.003    0.000    0.003    0.000 {method 'rstrip' of 'str' objects}
        2    0.000    0.000    0.000    0.000 {method 'split' of 'str' objects}
       44    0.028    0.001    0.028    0.001 {method 'startswith' of 'str' objects}
       55    0.001    0.000    0.001    0.000 {method 'strip' of 'str' objects}
        4    0.000    0.000    0.000    0.000 {method 'update' of 'dict' objects}
     1667    0.008    0.000    0.008    0.000 {method 'update' of 'set' objects}
     1200    0.001    0.000    0.001    0.000 {method 'values' of 'dict' objects}
        2    0.000    0.000    0.000    0.000 {method 'values' of 'mappingproxy' objects}
      860    0.614    0.001    0.622    0.001 {method 'write' of '_io.TextIOWrapper' objects}


********************************************
```
