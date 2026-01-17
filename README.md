## Typethon
This is where I experiment with my statically typed 'Python' compiler.
So far, I've implemented most of the syntax and am currently working
on type analysis. I intend to use a similar approach to compilation
that is seen in Golang.

So, the compiler will look something like this:

#### Compiler frontend
1. Syntax (Scan and Parse into AST)
2. Analysis (Check AST types and memory safety)
3. Intermediate (Convert AST into IR AST and optimize)

#### Compiler middle-end
5. SSA (Convert IR AST into SSA and optimize)

#### Compiler backend
6. Compile (Convert to machine code and optimize)

This language is not intended to be identical to Python and it
will encourage alternative approaches in many areas. For example,
it might not permit inheritance, exceptions will be handled differently,
and there will probably be Rust-style traits.

#### Progress
* The pasrser has been completely implemented for regular Python code
with special syntax for annotations and type parameters
* Type checking has been implemented for most statements and expressions

##### To-Do
* Rewrite the parser to be more efficient and remove unused Python syntax
* Create tests for the parser and type analyzer
* Implement constraints for type parameters and the rest of type analysis
* Decide on mutable/constant and reference semantics
* Implement the compiler backend

Here is what I've decided on so far:
```py
# Gotchas:
# 1) Single quote strings can only contain one character, 't represents a type parameter
# 2) Classes do not represent functionality tied to a state. Instead, they classify
# types with the same functions (i.e. Haskell class, Java interface, Rust trait)
# 3) Scoping is stricter and bindings must be created using the let keyword

# Data types can be tuples or structures, they can be defined with type
# assignment statements.

type Structure = { field1: int, field2: str }

type Tuple = (int, str)

# Data types can also be unions

type Expr = 
    | Number(int)
    | Attribute(Expr, str)
    | Add(Expr, Expr)
    | Sub(Expr, Expr)

# "Variables" can be created using the let keyword.

def f():
    let i
    if some_condition:
        i = 10
    else:
        i = 20

# They can only be assigned to once on all code paths and must be assigned
# to on all code paths before they can be used.

# I do not want to add a special syntax for creating mutable bindings and I am wondering
# if I can get by without them. As far as I know, the only thing that would become impossible
# are loops with states, so they would need to look more like recursive functions with
# parameters if we go down this road. I also dont know to what extent the memory model
# would rely on the existance of mutable bindings.
# If shadowing is forbidden, there would quickly become a deficit of variable names.
# if not, we have to consider whether
let x = f(x)
let x = g(x)

# is too limiting or less expressive than
var x = f(x)
x = g(x)

# And we also need to consider the fact that shadowing is on a scope basis,
# so setting x to g(x) conditionally wouldn't actually be possible without another
# variable
let real_x
let x = f(10)
if some_condition:
    real_x = g(x)
else:
    real_x = x

# for reference
var x = f(10)
if some_condtion:
    x = f(x)

# Yes, I know this is terrible. If I find a solution to loops that can be applied
# to this situation as well, I will refrain from adding mutable bindings. But the way
# it looks now, the solution that doesn't become FP is really just mutable bindings...

# Parametric polymorphism is achieved through the use of 't

# Types and functions can be parametrically polymorphic. A data type can only be
# polymorphic over a field, and functions can be polymorphic over an argument or
# the return value. A class could be polymorphic over any arbitrary type t.

def identity(x: 't) -> 't:
    return x

type Box = { value: 't }

# You can pass type parameters to polymorphic functions and calsses by simply
# calling it with a value. In places where you need a polymorphic class as a type,
# it can be written as Class(T).

box = Box(5) # type: Box(int)
x = identity(5) # type: int

def unbox(box: Box('t)) -> 't:
    return box.value

def unbox_int(box: Box(int)) -> int:
    return box.value

x = unbox(box) # type: int
x = unbox_int(box) # type: int

# Not sure how to pass explicitly pass type parameters to functions 

# Ad-hoc polymorphism is achieved by constraining a polymorphic type t
# to what will eventually become classes. The with class for 't constrains
# the type 't to the class.

def get_str_item(items: 't, index: int) -> str with 't: Index(int, str):
    return items[index]

def get_item(items: 't, index: 'u) -> 'v with 't: Index('u, 'v):
    return items[index]

# If a function is polymorphic over it's return type, and it is not
# used in any constraints, the caller must explicitly state the type.

def new() -> 'u:
    return u()

let items = new()  # Impossible to resolve U
let items: [int] = new()  # Works fine

# Use blocked can be used to define a function on a type.

type Identity = ()

use Identity:
    def f(self: Self) -> Self:
        return self

x = Identity()
x = x.f()

# The use/for syntax can be used to denote
# a function serves as the implementation function for a type class function.

type Map = { mapping: dict('k, 'v) }

use Index('k, 'v) for Map('k, 'v):
    def get_item(self: Self, key: 'k) -> 'v:
        return self.mapping[key]

# I added a proof of concept lambda syntax that simply uses two colons
# and allows multiline blocks with a delimeter. Here is how it looks:

(arg1, arg2, ..., argn) :: expression

# This is the block form

(arg1, arg2, ..., argn) ::
    stmt1
    stmt2
    ...
    stmtn
::

# The expression form is equivalent to

(arg1, arg2, ..., argn) ::
    return expression
::

# I want to allow type annotation but due to ambiguity issues
# it will either need to a) allow either all annotations or no annotations,
# i.e. no annotating one but not the other, b) add a weird a: b expression only valid in tuples:

# I'm unsure how traits would be handled as of right now because:
# 1. Other languages use def f(x: Trait) for dynamic dispatch and def f(x: 't) with Trait for 't
#       for static dispatch. This is kind of confusing which is probably why rust forces
#       you to use the dyn keyword.

# I don't currently know much about memory management, but I want the
# language to enforce memory safety preferrably without a GC.
# However, I also don't like the restrictions that come from implementing
# a borrow checker. It seems they would make the language significantly
# less expressive, which is one thing I would like to retain from Python.

# Other notes:
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

# *There might be a mechanism for specifying the loop for break/continue

while true:
    for letter in input():
        if letter == 'c':
            break while

# This would be a nice feature, but it still has ambiguity when nesting in
# the same type of loop. This could be solved with labels, but I am not willing
# to add labels.

# *Theoretical match expression

result = match operator:
| Operators.ADD: self.add(left, right)
| Operator.SUB: self.sub(left, right)
| else:  UnknownOperatorError()

# I think match and if should work similarly. They should have a statement and
# an expression form, and which it is dependens upon whether the colon has a newline
# after it. So it would be similar to lambda, but without the extraordinary nesting behaviour.

if x = y: 10
else: 20

# This would clearly be an expression because there is no newline, indent, etc.
# And someting like this would then be invalid because return is not an expression:

if x = y: return 10

# The idea that every block can be an expression is interesting, but it's
# fundementally incompatible with Python's syntax, and one could argue that
# that a more explicit approach is preferrable anyways. If and match expressions with
# corresponding statements seems like a reasonable middleground.

# *I have been considering  allowing multiple iterators in for loops
# to avoid the long winded zip() function. For example:

for (
    name in username if len(name) < 10,
    user in users if len(user.name) < 10
):
    ...

# *I think maybe there should be some monad-like builtin type and special syntax
# for it. This could be used for things like handling. For this to work,
# I think higher kinded types will be necessary which I barely understand.

def some_function() -> Result(int, Error)

# So someting like this: 
result = some_function()
if not result.is_error():
    other_function(result.value)

# Might be written as:
result = some_function() in
value -> other_function(value)

# It definitely won't look like this
```
