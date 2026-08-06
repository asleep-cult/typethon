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
Everything outlined below is both semantically and syntactically accurate
to my vision of the language with the possible exception of the type parameter
constriant syntax.

#### Notes on progress
* The parser is implemented as a custom LR(1) generator with a pushdown automaton
and most of the AST has been defined.
* I have began working on type-analysis, but I am not a fan of the direction it is
heading in. Because I believe this problem can only be solved by improving my
understanding of static analysis overall, I will begin doing more research on the
internals of the Rust compiler. In addition, my inability to fully understand certain
functional concepts that could serve our goal of correctness suggests that it might
be necessary to do more research in that area as well. This, and the fact that I have
more important real-world obligations, means that I will have to postpone development
of this project until further notice. Instead, my current goals are much less ambitious:
    1. Port the LR(1) parser generator into OCaml, allowing the parser table to be dumped
    and run in any language.
    2. Start a moderately complex project in Rust to learn the rules of the borrow checker
    and type system.
    3. Deeply research the Rust compiler development guide and resources that explain
    complex functional theories.
* Upon "further notice", I will make a decision about whether the entire project should
be ported to Rust, Ocaml, or maybe even Zig.

```py
# Gotchas:
# 1) Single quote strings can only contain one character, 't represents a type parameter
# 2) Classes do not represent functionality tied to a state. Instead, they classify
# types with the same functions (i.e. Haskell class, Java interface, Rust traits)
# 3) Scoping is stricter and bindings must be created using the let keyword

# Data types can be tuples or structures, they can be defined with type
# assignment statements.

type Point = { x: int, y: int }

type UnnamedPoint = (int, int)

# Data can also be a sum type

type Expr = (
    Number of int
    | Attribute of (Expr, str)
    | Add of (Expr, Expr)
    | Sub of (Expr, Expr)
)
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

# All data fields are private and immutable by default
# The pub and mut keywords can be used to make individual fields public and mutable
# pub(...) and mut(...) can change visibility and mutability to specific parts of a code base

type Counter = {
    pub mut(self) n: int
}
# If mut was bare, anyone with mutable access could mutate n
# mut(self) makes the field invariant

use Counter:
    def new() -> move Self:
        return { n = 0 }

    # The mut self means the callee must have mutable access to the Counter
    def next(mut self: Self) -> ():
        if self.n < 100:
            self.n += 1

def fn() -> ():
    mut counter = Counter.new()
    other_counter = counter
    counter.next()

# Bindings are created by annotating a name or simply using the assignment operator

def f():
    i: int
    if some_condition:
        i = 10
    else:
        i = 20

# They are immutable and can only be assigned to once on all code paths.
# They also must be assigned to on all code paths before they can be used.

# Bindings can be made mutable using mut

def f():
    mut x = 10
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
# to what will eventually become classes. The `with class for 't` constrains
# the type 't to the class.

def get_str_item(items: 't, index: int) -> str with 't: Index(int, str):
    return items[index]

def get_item(items: 't, index: 'u) -> 'v with 't: Index('u, 'v):
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
    def f(self: Self) -> Self:
        return self

x: Identity = ()
x = x.f()

# The use/for syntax can be used to denote
# a function serves as the implementation function for a type class function.

type Map = { mapping: dict('k, 'v) }

use Index('k, 'v) for Map('k, 'v):
    def new(mapping: dict('k, 'v)) -> Self:
        return { mapping = mapping }

    def update(self: Self, other: Self) -> Self:
        return { mapping = self.mapping | other.mapping }

    def get_item(self: Self, key: 'k) -> 'v:
        return self.mapping[key]

# Maybe there will be a Type.new() convention

# I added a proof of concept lambda syntax that simply uses two colons
# and allows multiline blocks with a delimeter. Here is how it looks:

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

spawn((|context, timeout| -> ():
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
    if item.name == "Sword":
        150
    else:
        120)

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

# I question whether the block form should be able to be assigned to a variable at all

# I'm unsure how traits would be handled as of right now because:
# 1. Other languages use def f(x: Trait) for dynamic dispatch and def f(x: 't) with Trait for 't
#       for static dispatch. This is kind of confusing which is probably why rust forces
#       you to use the dyn keyword.

# I don't currently know much about memory management, but I want the
# language to enforce memory safety preferably without a GC.
# However, I also don't like the restrictions that come from implementing
# a borrow checker. It seems they would make the language significantly
# less expressive, which is one thing I would like to retain from Python.

# Other notes:
# *Mutability and reference model

# All values, except primitives, are implicitly references.
# All bindings and struct fields can be made mutable. Types are not mutable, names are.
# All types can be qualified with move, suggesting that ownership is taken.

# Aliasing XOR Mutability
# There can exist either 1 mutable reference, or many immutable references to any data.
# If there is a mutable reference, the owner/move type is unreadable and unwritable.
# If there are any immutable references, the owner/move type is unwritable.

type Player = { mut score: int }

# Struct initialization is implicit move (i.e. mut player1 = move { ... })
mut player1: Player = { score = 10 }  # Mutable binding
player1.score = 20  # Valid

player2: Player = { score = 10 }  # Immutable binding
player2.score = 20  # Invalid

new_player2 = move player2  # Move ownership of player2 to new_player2
                            # player2 is dead and inaccessible

player1_immutable = player1  # Immutable reference to data owned by player1
                             # player1 is write-locked until this reference is dropped

mut player2_mutable = mut new_player2  # Mutable reference to data owned by player2
                                       # new_player2 is read/write-locked until this reference is dropped

def shared_borrow(player: Player) -> ()
def exclusive_borrow(mut player: Player) -> ()
def transfer_ownership(player: move Player) -> ()

shared_borrow(player1)
exclusive_borrow(mut player1)
transfer_ownership(move player1)

# Move is only explicitly necessary when it would kill a binding in the current scope

# *Function bodies are optional for prototyping

def proto(foo: int) -> str

# *Classes look like this

class Foo('t):
    def proto(self: Self, foo: int) -> 't

# *If expressions will be changed to the rejected form to add more flexibility

f(if x < 0: "negative" else: "positive")

# This is ambiguous

# *No comperhensions for now

# *For statements might have an optional guard

for name in usernames if name.len() < 10:
    ...

# The ideas above range from highly likely to certain, the ones
# below might not happen at all.

# *Theoretical match expression

result = match operator:
| Operators.ADD: self.add(left, right)
| Operator.SUB: self.sub(left, right)
| else:  UnknownOperatorError()

# I think match and if should work similarly. They should have a statement and
# an expression form, and which it is dependens upon whether the colon has a newline
# after it. So it would be similar to lambda, but without the extraordinary nesting behaviour.

if x == y: 10
else: 20

# This would clearly be an expression because there is no newline, indent, etc.
# And someting like this would then be invalid because return is not an expression:

if x == y: return 10

# The idea that every block can be an expression is interesting, but it's
# fundementally incompatible with Python's syntax, and one could argue that
# that a more explicit approach is preferrable anyways. If and match expressions with
# corresponding statements seems like a reasonable middleground.

# *Labeled blocks (Dont know)

def f(x):
    ~label:
        print(10)
        break label

    ~loop while True:
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

# *You might be able to chain binary operations across multiple lines with an indent
type Number = int
    | float
    | complex

return numbers.filter(|n| n >= 50)
    .map(str)
    .join(", ")

let result = x * y + 200 - z
    / y**2 - 4 * a + b

# This wouldn't work:

if x > 50
    and y < 100
    and z == 20:
    do_something()
```
