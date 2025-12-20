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

Here is what I've decided on so far:
```py
# Parametric polymorphism is achieved through the use of |T|
# This might change to some prefix before T in the future (e.g. !T)

# Classes, Functions, (and in the future, Traits) can be parametrically polymorphic
# However, a class can only be polymorphic over an attribute, and functions
# can only be polymorphic over an argument. A trait could be polymorphic over any
# arbitrary type T.

def identity(x: |T|) -> T:
    return x

class Box:
    value: |T|

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

def get_item(items: |T: Indexable(int, |U|)|, index: int) -> U:
    return items[index]

# Alternatively, the for syntax can be used to for more complex constraints.
# ^ (maybe?)

def get_item(self, items: |T|, index: int) -> U
(
    Indexable(|U|) for T,
):
    return items[index]

# The for syntax cannot constrain parameters that aren't already defined
# in the function definition. (i.e. Indexable(|U|) for |T| would be invalid)
# However, it can be used to extract the parameters from a polymorphic constraint.

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

    def get_item(self: Self, key: K) -> V
    (
        Indexable(K, V) for Self
    ):
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
    def proto(self, foo: int) -> T

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
# target group syntax.

# For simple assignments, it would look like this:
{x, y, z} = 10
# x = 10; y = 10, z = 10
# (We would also remove the x = y = z = 10 syntax)

# With an annotation:
{x, y, z}: str = 'Target Group'

# For class attributes:
class Rectangle:
    {height, width}: int

# For function parameters:
def add({lhs, rhs}: int) -> int:
    return lhs + rhs

# Finally, the concatenate example would look like this:
def concatenate({map1, map2}: HashMap|K, V|) -> HashMap(K, V)

# This would probably involve removing the set syntax as well
# (oh well...) I am also certainly removing lists as targets.
# The biggest problem with this syntax is it could easily
# be confused with unpacking. It also adds plenty of unnecessary
# complication, but at the same time, it's much cleaner syntactically.

# For the sake of consistency, something like this would also
# be valid (although I cant imagine why anyone would ever do this):
for {x, y} in numbers: ...

# 12. While on the topic of for loops, I have been considering 
# allowing multiple iterators in for loops to avoid the long winded
# zip() function. For example:

for (
    name in username if len(name) < 10,
    user in users if len(user.name) < 10
):
    ...
```
