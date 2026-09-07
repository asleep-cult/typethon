## Typethon
The goal of this project is to create a Python-like programming language
that is built from the ground up with a strong emphasis on correctness.
This means removing Python's footguns such as inheritance-style classes,
exceptions-style errors, null values, loosely defined scopes, and dynamic
typing. I believe that the future of Python is limited by a poor foundation
that no amount of new type features can rectify. Python is still a popular
language because of the similicity it offers, but all too often it trades
simplicity for correctness. With a better foundation, many of Python's
benefits can be retained, and a language that is in many respects superior
can emerge. With that being said, the two most important factors for
developing this language are correctness, followed by simplicity. Naturally,
the two languages that should influence Typethon most are Python and Rust.

#### Notes on progress
* The parser is implemented as a custom LR(1) generator with a pushdown automaton
and most of the AST has been defined.
* I am currently working on the abstract semantic graph, which is a lowered representation of 
the AST split up into definitions and code. Code can exist on functions and modules with the 
intention of allowing code to be written at the top level of a file. The operating principle of 
ASG lowering is as follows:
    * Index all definitions (types, functions, etc.) recording a parent, AST node, and id for every definition
    * Resolve all names to a definition or local name and resolve attriute lookups from the index wherever possible
    * Lower nodes on demand and cache the result

* The following is undecided/not yet implemented for asg:
    * Paths are entirely ambiguous in code, so ASG code has no notion of paths, while ASG types do.
    I considered a path promotion phase after type initialization, but this would rely on unification in some capacity.
    It seems more reasonable for ASG code to remain pathless and do the work during unification.
    * Due to automatic local insertion (implicit binding creation on assignment or ascription), the name resolver
    has to do a bit more work to resolve local definitions.
    * I have to define the rules for automatic return insertion in lambdas and add it to the lowering phase.
```py
# Gotchas:
# 1) Single quote strings can only contain one character, 't represents a type parameter
# 2) Classes do not represent functionality tied to a state. Instead, they classify
# types with the same functions (i.e. Haskell class, Java interface, Rust traits)
# 3) Scoping is stricter

# Data types can be tuples or structures, they can be defined with type
# assignment statements.

type Point = { x: int, y: int }

type UnnamedPoint = (int, int)

# Data can also be a sum type

type Expr = Number of int
    | Attribute of (Expr, str)
    | Add of (Expr, Expr)
    | Sub of (Expr, Expr)
# Tuples and structures can be instantiated in code like this:

(10, 20)
{ x = 10, y = 20 }

# Data defined in code without an explicit type is automatically deduced
# to a structural type.

point = { x = 10, y = 20 } # This can only be used where { x: int, y: int } is expected, not Point
point = (1, 2)  # This can only be used where (int, int) is expected, not UnnamedPoint

# The opposite is also true. Point cannot be coerced to the structural type { x: int, y: int }

# Structural struct types exist to match structural tuple types. The boundary between structural
# and nominal types cannot be crossed implicity in either case. Whether some variation
# of a { ..point }/(..point,) should allow you to convert between structural and nominal
# types of the same form is another question. 

# For example, this would be valid

def add(point: Point) -> int:
    return point.x + point.y

f({ x = 10, y = 20 })

f({ x = 30, y = -5 }: Point)

# All data fields are private by default
# The pub keyword can be used to make an individual fields public
# pub(...) can change visibility to specific parts of a code base

type Counter = { n: int }

use Counter:
    def new() -> Self:
        return Self { n = 0 }

    def current(self) -> int:
        return self.n

    # The mut self means the callee must have mutable access to the Counter
    def next(mut self) -> ():
        if self.n < 100:
            self.n += 1

def fn() -> ():
    mut counter = Counter.new()
    counter.next()

# Bindings are created by using the local keyword

def f():
    local i
    i = 20
    if some_condition:
        local i  # Explicit shadowing of i
        i = 30
        print(i) # Here i is 30

    print(i)  # Here i is 20

    i = 10  # This is invalid because i is an immutable binding

    local i  # Explicit shadowing of i
    i = 5
    print(i)  # Here i is 5

# Bindings are implicitly created when assigning to a new name or annotating a name

def f():
    i: int  # Implicit local i
    if some_condition:
        i = 10
    else:
        i = 20

# Bindings can be made mutable using mut

def f():
    mut x = 10  # Implicit local mut i
    if some_condition:
        x += 20

# Parametric polymorphism is achieved through the use of 't

# Types and functions can be parametrically polymorphic. A data type can only be
# polymorphic over a field, and functions can be polymorphic over an argument or
# the return type. A class could be polymorphic over any arbitrary type t.

def identity(x: 't) -> 't:
    return x

type Box = { value: 't }

# Type constructors and functions can be called with f(...)
identity(10) == 10
Box(int)

# Type parameters are inferred when used with values.

x = identity(5) # inferred 't: int

def unbox(box: Box('t)) -> 't:
    return box.value

def unbox_int(box: Box(int)) -> int:
    return box.value

box: Box = { value = 10 }
# What if you want to make sure box: Box, but infer type parameters?
# This potentially means all means that all annotations in asg code
# can refer to types and pass no parameters.

x = unbox(box) # type: int
x = unbox_int(box) # type: int

# Ad-hoc polymorphism is achieved by constraining a polymorphic type t
# to what will eventually become classes. Not the actual syntax.

def get_str_item('t: Index(int, str))(items: 't, index: int) -> str:
    return items[index]

def get_item('t: Index('u, 'v))(items: 't, index: 'u) -> 'v:
    return items[index]

# Expressions can be annotated when type inference isn't possible

def new() -> 'u:
    return u()

x = new(): int

# Or the type constructor can be accessed somehow
new.constructor(int)()

# Use blocks can be used to define a function on a type.

type Identity = ()

use Identity:
    def f(self) -> Self:
        return self

x: Identity = ()
x = x.f()

# The use/for syntax can be used to denote
# a function serves as the implementation function for a type class function.

type Map = { mapping: dict('k, 'v) }

use Map('k, 'v) as Index('k, 'v):
    def new(mapping: dict('k, 'v)) -> Self:
        return { mapping }

    def update(self, other: Self) -> Self:
        return { mapping = self.mapping | other.mapping }

    def get_item(self, key: 'k) -> 'v:
        return self.mapping[key]

# Maybe there will be a Type.new() convention

# I added a proof of concept lambda syntax that allows multiline blocks.
# Here is how it looks:

# Simple lambda

|arg1, arg2, ..., argn|: simple stmt

# Complex lambda

|arg1, arg2, ..., argn|:
    stmt1
    stmt2
    ...
    stmtn

# Complex lambdas can only exist in parenthesis or as part of an assignment
# I tried to make it work as the final value in an expression list
# but it apparently is a conflict, I don't feel like going through the logs
# to understand why, the amount of trickery needed to make it work is bad enough
# as it is.

spawn((|context, timeout|:
    while true:
        sleep(timeout)
        print(f"{context.thread_id} is working")), 50)

items.filer(|item| -> bool: item.len() >= 50)

items.filter(
    |item|:
        item.len >= 50
)

# Closures should have automatic return insertion for trailing expressions

items.map(|item: str|:
    if item == "Sword":
        150
    else:
        120
)

# This makes sense because it is the only block that is an expression, but the
# lack of a similar mechanism throughout the language makes me question
# whether this could serve a more powerful purpose in the language.

account = (||:
    if price >= 150:
        Account.Savings
    else:
        Account.Checkings)()

# For example, something like this would be possible but in this form its undesirable.
# The simplicity and automatic return insertion would significantly encourage more
# functional practices within the language.

# Closures can appear as a single expression, the final expression in a list of expressions,
# or the only expression in a list of expressions.

# I'm unsure how traits would be handled as of right now because:
# 1. Other languages use def f(x: Trait) for dynamic dispatch and def f(x: 't) with Trait for 't
#       for static dispatch. This is kind of confusing which is probably why rust forces
#       you to use the dyn keyword.

# *If statements, for statements, and while statements should become expressions:
x = if a > 10:
    b = 0
    while b < a:
        b += a / 1.5

    b ** 2
else:
    0

f(if a == 10: y else: z)

# *The assignment operator should work with patterns

# Structural and nonminal types should be unpacked like this
(x, y) = point
{ x, y } = named_point

# The assignment operator should have an else guard
(10, y) = point else: return Err(())

Symbol { kind = SymbolKind.Noterminal { productions }, .. } = symbol else: continue

# The assignment operator should work in if conditions
if Symbol { kind = SymbolKind.Nonterminal { .. }, .. } = symbol:
    ()

# Sum types should be unpacked in the same manner as their construction.

type Sum = Var1 of int
    | Var2 of (int,)
    | Var2 of { name: str }

Sum.Var1 10
Sum.Var2 (10,)
Sum.Var3 {name: "John"}

def f(the_sum: Sum) -> bool:
    the_sum is
    of Sum.Var1 n: n >= 50
    of Sum.Var2 (n,): n < 50
    of Sum.Var3 { name }: name.len() < 10

# *Theoretical match expression

result = expression is
of Expression.Binary { left, op = Operator.Add, right }:
    if not left.is_number() or not right.is_number():
        Value.Undefined
    else:
        Value.Number { value = left.value + right.value }
of Expression.Unary { op = Operator.Sub, operand }:
    if not operand.is_number():
        Value.Undefined
    else:
        Value.Number { value = -operand.value }

# *Function bodies are optional for prototyping

def proto(foo: int) -> str

# *Classes look like this

class Foo('t):
    def proto(self: Self, foo: int) -> 't

# *Labeled blocks (Dont know)

def f(x):
    `label:
        print(10)
        break label

    `loop while True:
        for i in range(30):
            if is_special_enough_to_break(i):
                break loop

# *Data types might automatically derive field names from the variable it is
# assigned to, for example:

x = 10
y = 20

{ x, y }
# Would be equivalent to
{ x = x, y = y }

# *Newline indent should be an escape sequence that starts elliding whitespace
# unless entering a block

type Number = int
    | float
    | complex

return numbers.filter(|n|: n >= 50)
    .map(str)
    .join(", ")

let result = x * y + 200 - z
    / y**2 - 4 * a + b
```
