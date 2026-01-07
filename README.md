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
# Parametric polymorphism is achieved through the use of |T|
# This might change to some prefix before T in the future (e.g. !T)

# Classes, Functions, (and in the future, Traits) can be parametrically polymorphic
# However, a class can only be polymorphic over an attribute, and functions
# can be polymorphic over an argument or the return value. A trait could be polymorphic
# over any arbitrary type T.

def identity(x: |T|) -> T:
    return x

class Box:
    value: |T|

# Actually, I do not like this syntax. I think I will to steal OCaml's polymorphic
# type syntax.

def f(x: 't) -> 't

# We will just have to get rid of single quote strings. And restrict them
# to single characters depending on how strings end up working.

# Classes will automatically have initializers for the attributes defined
# in their body. I'm unsure whether there will be getters, setters,
# getattribute and other weird overrides.

# You can pass type parameters to polymorphic functions and calsses by simply
# calling it with a value. In places where you need a polymorphic class as a type,
# it can be written as Class(T).

box = Box(5) # type: Box(int)
x = identity(5) # type: int

def unbox(box: Box(|T|)) -> T:
    return box.value

def unbox_int(box: Box(int)) -> int:
    return box.value

x = unbox(box) # type: int
x = unbox_int(box) # type: int

# It is not immediately clear whether explicit passing of type parameters
# for functions will be necessary.

# Ad-hoc polymorphism is achieved by constraining a polymorphic type T
# to what will eventually become traits. The syntax |T: Trait| constrains
# the type T to a Trait.

def get_str_item(items: |T: Index(int, str)|, index: int) -> str:
    return items[index]

# Type parameters cannot be nested within the constraint of another type
# parameter. Instead, they must be defined and constrarined using the with/for
# syntax.

def get_item(items: |T|, index: |U|) -> |V| with Index(U, V) for T:
    return items[index]

# In addition, the with/for syntax can contain new type parameters but they
# cannot be used in the parameter-list for the sake of consistency.
# (It should be defined in the parameter list instead.)

def use_index(items: |T|) -> ValueTrait with (
    Index|U: DefaultTrait, V: ValueTrait| for T
):
    return items[U.default()].value()

# If a function is polymorphic over it's return type, and it is not
# used in any constraints, the caller must explicitly state the type.

def new() -> |U|:
    return U()

items = new()  # Impossible to resolve U
items: [int] = new()  # Works fine

# The Self type is a special type used to define a function on a type.

class Identity:
    def f(self: Self) -> Self:
        return self

# Alternatively, Self can be used to define a function on a type outside of
# the type by binding it with the Self(T) syntax.

def g(self: Self(Identity)) -> Self:
    return self

x = Identity()
x = x.f()
x = x.g()

# The Self type can be used in combination with the for syntax to denote
# a function serves as the implementation function for a trait function.

class Map:
    mapping: {|K|: |V|}

    def get_item(self: Self, key: K) -> V with Index(K, V) for Self:
        return self.mapping[key]

# I'm unsure how traits would be handled as of right now because:
# 1. Other languages use def f(x: Trait) for dynamic dispatch and def f(x: |T: Trait|)
#       for static dispatch. This is kind of confusing which is probably why rust forces
#       you to use the dyn keyword.

# I don't currently know much about memory management, but I want the
# language to enforce memory safety preferrably without a GC.
# However, I also don't like the restrictions that come from implementing
# a borrow checker. It seems they would make the language significantly
# less expressive, which is one thing I would like to retain from Python.

# Other notes:
# 1. Function bodies are optional for prototyping

def proto(foo: int) -> str

# 2. Traits will probably look something like this

trait Foo |T|:
    def proto(self: Self, foo: int) -> T

# 3. There will probably be syntactic sugar for initializing a polymorphic type
# with a polymorphic parameter to reduce clutter

Type|T, U| # Same as Type(|T|, |U|)

# 4. If expressions will be changed to the rejected form to add more flexibility

f(if x < 0: 'negative' else: 'positive')

# The expression might be a "complex expression" meaning it skips whitespace
# when not in parenthesis

status = if response == 200: 'ok'
elif response == 402: 'forbidden'
else: response.str()

# 5. Comprehensions will be similarly changed

names = for names in usernames: name.lower()

# Indentation should be reccomended but it cannot be enforced
# because the scanner skips whitespace in paranthesis and it would be
# weird to only enforce is in this context.

names = for name in usernames:
    if name.len() < 10: name
    else: f'name[:10]...'

# 6. For statements and expressions might have an optional guard

for name in usernames if name.len() < 10:
    ...

names = for name in usernames if name.len() < 10: name

# 7. Assignment expressions do not and probably will not exist.

# The ideas above range from highly likely to certain, the ones
# below might not happen at all.

# 8. There might be a mechanism for specifying the loop for break/continue

while True:
    for letter in input():
        if letter == 'c':
            break while

# This would be a nice feature, but it still has ambiguity when nesting in
# the same type of loop. This could be solved with labels, but I am not willing
# to add labels.

# 9. Lambdas might be defined with double colons. 
# They also might be implicitly parametrically polymorphic

f = (x) :: x # def f(x: |T|) -> T: return x
f = (Box(x)) :: x # def f(box: Box(|T|)) -> T: return x.vaule

# They can be made multiline by adding another double colon at the end

users = apply((name) ::
    if name not in usenames:
        usernames.append(name)

    return User(name)
::, ['Alice', 'Jimmy'])

# This is actually very nice syntactically, but I do not want to run amuck
# and completely destroy the pythonic syntax. Here are my arguments against
# the syntax:
# 1. The double colon looks very out of place and makes the language
# feel like Haskell or C++
# 2. Nothing else in the language requires explicitly defining the end of a
# block and theres no reason to do it here.
# 3. This can easily be achieved by using a function instead of introducing
# special syntax

# Counter-arguments:
# 1. The double colon is significantly more pythnonic than braces or alternative
# syntax choices and is semi-consistent with colons defining the beginning of
# blocks 
# 2. The purpose of a this lambda is to allow the use of a code block as a single
# expression, so it is inherently different from other statements
# 3. The existing lambda syntax is so restrictive that the majority of reasonable
# use cases are impossible without a function

# 10. Match statements might become a complex expression. (They  will almost certainly
# use else.)

result = match operator:
    case Operators.ADD: self.add(left, right)
    case operator.SUB: self.sub(left, right)
    else: UnknownOperatorError()

# Not sure how the statement form will work but I want to avoid the deep nesting
# that comes from indented case blocks.

# 11. While imagining some examples, I realized that the type parameter syntax
# is a burden when expressing that two things are of the same exact type.
# For example, imagine you have some polymorphic type called HashMap and you
# want to write a function that concatenates them:

def concatenate(map1: HashMap|K, V|, map2: HashMap(K, V)) -> HashMap(K, V)

# Here, map1 and map2 are of the same type, but they do not use the same
# syntax, which is both confusing and aesthetically displeasing.
# Before I continue, I would like to contrast this with something like:

def set_item(map: HashMap|K, V|, key: K, value: V) -> None

# In this instance, the type parameter syntax is actually very intuitive,
# and it is clear that the key must be the key type of HashMap and the
# value must be the value type.

# Now, to make our concatenate function more intuitive, I am
# considering a new syntax. I dont intend to use some generic form
# (not a pun) such as def f|K, V|(map1: HashMap(K, V), map2: HashMap(K, V))
# which in my opinion is too verbose an arguably a worse expression
# of the function's behavior. Instead, my proposal consists of a new
# multi-target annotation syntax.

x, y, z: int
# x: int, y: int, z: int

# For class attributes:
class Rectangle:
    height, width: int

# The previous examples were asssignment annotations, function parameters
# are similar. A parameter with no annotation uses the annotation of the
# next parameter.
def add(lhs, rhs: int) -> int:
    return lhs + rhs

# An example with type parameters
class Pair:
    x, y: |T|

def nest_pairs(pair1, pair2: Pair|T|) -> Pair(Pair(T)):
    return Pair(Pair(pair1.x, pair2.x), Pair(pair1.y, pair2.y))

# The concatenate example simply becomes:
def concatenate(map1, map2: HashMap|K, V|) -> HashMap(K, V)

# 12. There (wont) might be a way to state the value of an expression with
# an annotation (similar to casting).

# An empty list of integers
([]: [int])

# 13. I have been considering  allowing multiple iterators in for loops
# to avoid the long winded zip() function. For example:

for (
    name in username if len(name) < 10,
    user in users if len(user.name) < 10
):
    ...

# 14. Class attributes should just behave exactly like function parameters

class Box(
    value: |T|,
)

class Collection(
    items: |T|,
) with Index|U, V| for T

# If functions get defaults, kwonly args, etc., classes do as well.

# 15. I think maybe there should be some monad-like builtin type and special syntax
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

# Not sure...
```
