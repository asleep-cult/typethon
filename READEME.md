## Typethon
This is where I experiment with my statically typed 'Python' compiler.
So far, I've implemented most of the syntax and am currently working
on type analysis. I intend to use a similar approach to compilation
that is seen in Golang.

So, the compiler will look something like this:

Compiler frontend
1. Syntax (Scan and Parse into AST)
2. Analysis (Check AST types and memory safety)
3. Intermediate (Convert AST into IR AST and optimizes)

Compiler middle-end
5. SSA (Converts IR AST into SSA and optimizes)

Compiler backend
6. Compile (Conversion to machine code and optimizes)

This language is not intended to be identical to Python and it
will encourage alternative approaches in many areas. For example,
it might not permit inheritance, exceptions will be handled differently,
and there will probably be Rust-style traits.

Here is what I've decided on so far:
```py
# Parametric polymorphism is achieved through the use of |T|
# This might change to some prefix before T in the future (e.g. !T)

# Classes, Functions, (and future Traits) can be parametrically polymorphic
# However, a class can only be polymorphic over an attribute, and functions
# can be polymorphic over an argument. A trait would be polymorphic over any
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
# to what will probably become traits.

def get_item(items: |T: Indexable(|U|)|, index: int) -> U:
    return items[index]

# I'm unsure how traits would be handled as of right now for these reasons:
# 1. Other languages use def f(x: Trait) for dynamic dispatch and def f(x: |T: Trait|)
#       for static dispatch. This is kind of confusing which is probably why rust forces
#       you to use the dyn keyword.
# 2. This notation gets ugly when you start nesting polymorphic constraints
#       There will likely be something simelar to get_item(items: |T: Indexable|) -> T.Output
#       But overall we will probably need a more robust constraint syntax for more complex code
# Maybe some variation of this syntax (which is very questionable):

def get_item(self, items: T, index: int) -> U
with |U, T| as (  # maybe change 'with' to 'for'/'and'
    T: Indexable(U) # (or abuse curly braces)?
):
    return items[index]

# I don't currently know much about memory management, but I want the
# language to enforce memory safety preferrably without a GC.
# However, I also don't like the restrictions that come from implementing
# a borrow checker. It seems they would make the language significantly
# less expressive, which is one thing I would like to retain from Python.

# Other notes:
# 1. Function bodies are optional for prototyping

def proto(foo: int) -> str

# 2. Traits will probably look something like this

trait Foo with |T|:
    def proto(self, foo: int) -> T

# 3. Lambdas might be implicitly parametrically polymorphic

f = (x) -> x # def f(x: |T|) -> T: return x
f = (Box(x)) -> x # def f(box: Box(|T|)) -> T: return x.vaule
```
