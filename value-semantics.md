## Theoretical Value Semantics

References are second class citizens and the compiler can freely represent code using
copies, references, etc. The compiler must track whether any data in the program is
owned, in addition to its origin if it's a projection.

Mutability is an attribute of bindings, not types.

#### Immutably owned bindings
* `digit = 9`
* `numbers = [100, 200, 300]`
* `structure = { x = 10, y = 20 }`

Reassignment and internal mutability is prohibited:
* `digit = 5`  ERROR: Cannot change immutable binding `digit`, consider explicit shadow or declaring it as `mut`
* `numbers.append(50)`  ERROR: Cannot project `numbers` mutably in function append, consider declaring it as `mut`
* `structure.x = 10`  ERROR: Cannot alter `structure` field as it is declared immutable, consider declaring it as `mut`

#### Mutably owned bindings
* `mut mutable_digit = 0`
* `mut mutable_numbers = [400, 500, 600]`
* `mut mutable_structure = { x = 5, y = 5 }`

Reassignment and internal mutability is acceptable:
* `mutable_digit = 1` -> `1`
* `mutable_numbers.append(700)` -> `[400, 500, 600, 700]`
* `mutable_structure.x = 10` -> `{ x = 10, y = 5 }`

#### Function passing conventions
Function parameters can define whether passed arguments must be mutable or possibly moved. Arguments follow the following
subtyping relationship: immutable <: mutable <: owned/move, meaning that owned staisfies mutable, and mutable satisfies immutable.

##### Immutably passed values
```py
def show_number(number: int):
    print(number)
```

Any one the following would work:
* `show_number(digit)`
* `show_number(mutable_digit)`
* `show_number(mutable_numbers[0])`

##### Mutably passed values
```py
bad_list = [1, 2, 3, 4, 5]
mut inc_list = [1, 2, 3, 4, 5]

def increment_number(mut numbers: [int]):
    numbers[0] += 1
```

Any one the following would work:
* `increment_number(inc_list)` -> `[2, 2, 3, 4, 5]` 

The following would not work:
* `increment_number(bad_list)` ERROR: Cannot peoject `bad_list` mutably in function `increment_number`

##### Moved values
```py
mut mut_struct = { x = 100, y = 100 }
imm_struct = { x = 100, y = 100 }

def move_structure(move structure: { x: int, y: int }):
    print(structure.x)
    print(structure.y)
```

The following would work:
* `move_structure(imm_struct)` Same as below
* `move_structure(mut_struct)` Attempting to access `mut_struct` after: ERROR: Cannot access `mut_struct` without reinitialization
because it was moved to function `move_structure`

#### Projected values
Projected values are non-owned values that have an origin attached. Origins may point to other projections
but should eventually lead to an owned value. Origin tracking is used by the compiler to enforce mutability XOR aliasing,
the same rule underpinning Rust's borrow checker.

##### Projection through assignment
The simplest form of projection uses the assignment operator. Recall that by the previous rules, the following are owned:
```rs
mut mut_nums = [100, 200, 300, 400]
immut_nums = []
```
Thus, assigning another name to these values creates a projection:
```rs
mut mut_proj = mut_nums
immut_proj = immut_nums
``` 
The following would be erroneous to the borrow checker:
* `immut_proj[0] = 10` Erroneous by basic mutability rules, not borrow checker rules
* `mut_nums[0] = 10` ERROR: Cannot access `mut_nums` until end of mutable projection `mut_proj`
* `mut mut_proj2 = mut_proj; mut_proj[0] = 10`  ERROR: Cannot access `mut_proj` until end of mutable projection `mut_proj2`

A very important thing to note is that mutability can be threaded through projections, preventing the need for any
code that varies only by mutability:
```rs
to_immut = mut_nums
mut back_to_mut = to_immut
```
Origin tracking allows us to guarantee that mutable projections are exclusive, and mutation cannot be observed until
it is complete. 

#### Mut ref and mut seal bindings
Mutable bindings can also be qualified with `ref` or `seal` to describe whether the binding should use
pass through semantics or mutability indirection.

##### Pass-through semantics
In some cases, you might want to reassign something as a "dereferencing" assignment, rather than
rebinding. To achieve this, you can use `mut ref` bindings. It is important to understand that
`mut ref` is literally just a modifier that affects the assignment operator and arguably a misnomer.

```rs
def increment(mut ref i: int):
    i += 1

mut i = 0
increment(i)
```

##### Mutability indirection
Considering that in all cases item internal mutability assumes the mutability of the binding it resides on, it
becomes impossible to make a binding mutable over numerous immutable values without writing a wrapper around it.
To rectify this, bindings can be `mut seal`. This does not make immutable bindings mutable or operate as a
mutable cell, it simply allows the field to vary over a value without making any claims about the internal mutability
of that value.

```rs
type City = { name: str, time_size: str }

huston = { name = "Huston", time_size = "Central Daylight Time" }
new_york = { name = "New York City", time_zone = "Eastern Daylight Time" }

mut seal current_city = huston
if going_home():
    current_city = new_york
```

Without seal, it would be necessary for the cities to be mutable.

#### Mut compatibility
To define the rules governing `mut` binding  assignment, we must start by splitting
all types into two categories:
1) Those capable of internal mutation: any structure with a field marked `mut`
2) And the rest who are incapable of internal mutation

With that being defined, the following rules govern `mut` assignment:
* A plan, immutable binding can accept any value whether it be a projection or an owned value
* A binding marked as `mut` can accept an owned value or a mutable projection. If the binding's type is
incapable of internal mutation, it can also accept an immutable projection
* A binding marked as `mut ref` can only accept an owned value or a mutable projection regardless
of the type's internal mutability
* A binding marked as `mut seal` can accept any value regardless of mutability

##### Projection through functions
All non-moved data passed to a function is considered a projection. Functions can only return moved data, unless they
specify the origin of their result. By these rules, `moving_min` moves the result into the return value.
NOTE: 't is an OCaml-style type paraeter, completely unrelated to origins or lifetimes.
```rs
def moving_min(move a: 't, move b: 't) -> 't:
    if a < b: a else: b
```

Origins can be specified with from with respect to the functions argument. Rather than moving, `min` projects the result
into the return value. 
```rs
def min(a: 't, b: 't) -> 't from a | b:
    if a < b: a else: b
```

The from specifier can also be used to tie the origin of two arguments together, for example, when appending
the argument to a list:
```rs
def append(mut items: ['t], item: 't from items):
    items.append(item)
```

An important fact to understand about the from specifier is that it is not a conclusive representation of
the real origins of the data used by the compiler. The from clause serves the purpose of defining the
locking contract of the function to prevent changes to the body from silently breaking other code.
The compiler checks the function body to determine the real origins, checks it against the contract, and the
borrow checker locks according to the contract. As a result, the compiler understands that the following
is not an option from origin, but instead, an option containing the origin:
```rs
def wrap(x: 't) -> Option('t) from x:
    Some(x)
```

#### Structure and tuple fields
Structures and tuple's have no means of specifying whether their fields are owned or their possible origins.
They only describe the mutabilty of their fields, and two extra things to help express intent.
The following is an example of a struct definition:
```rs
type ListIter = { items: ['t], mut index: usize }
```

##### From/where clauses on individual fields
It may be confusing that structs cannot define their own field origins, but recall that the from clause
in conjunction with a function body can be automatically used to infer the origins of each field.
In addition to the from clause referencing individual parameters, it can also reference fields
within the parameter itself, meaning the following would be possible:
```rs
def current(iterator: ListIter('t)) -> 't from iterator.items:
    iterator.items[iterator.index]
```

The from clause can offer more exact specificity of field origins:
```rs
def iterator(items: ['t]) -> ListIter('t) from { items = items }:
    ListIter(items)

def err_min(a: 't, b: 't) -> Result('t, 't) from Ok(a | b), Err(a):
    if a == b: Err(a)
    elif a < b: Ok(a)
    else: Ok(b)
``` 

##### Field-level mutability
Structs can define the mutability of each of their individual fields. Field mutability defines the ceiling
for internal mutability.

The following exemplifies field-level mutability:
```rs
type First = { mut a: int, b: int }
type Second = { mut one: First, two: First }

mut second: Second = { one = { a = 10, b = 20 }, two = { a = 50, b = 60 } }
```

The following would be valid:
* `second.one = { a = 0, b = 0 }` -> `{ one = { a = 0, b = 0 }, two = { a = 50, b = 60 } }`
* `second.one.a = 500` -> `{ one = { a = 0, b = 500 }, two = { a = 50, b = 60 } }`

The following would be invalid:
* `second.one.b = 10`  ERROR: Cannot alter field `b` of `one` as it is declared immutable
* `second.two.a = 10`  ERROR: Cannot alter field `two` of `second` as it is declared immutable

##### Field mutability pass-through semantics
Struct fields allow for pass-through semantics with `mut ref`:
```rs
type Point = { mut ref x: int, mut ref y: int }

use Point:
    def add(mut self, other: Point):
        self.x += other.x
        self.y += other.y

mut x = 0
mut y = 0
point: Point = { x, y }
point.add({ x = 10, y = 20 })
```
At the end of this code, the local variable x would be 10, and y would be 20.

##### Field mutability indirection
Struct fields allow `mut seal` for mutability indirection:
```rs
type Peekable = { iterator: ListIter('t), mut seal current: 't }

use Peekable('t):
    def next(mut self) -> 't:
        tmp = self.current
        self.current = self.iterator.items[self.iterator.index]
        self.iterator.index += 1
        tmp

    def peek(self) -> 't:
        self.current
``` 

Without seal, this would fail because assiging `current` to `iterator.items` would
require it to be mutable. 

#### List internal mutability
The internal mutability of a list's elements is defined by the mutability of its binding.
List elements can also be sealed or use the same `ref` semantics struct fields can.

The following example are lists using non-sealed, non-ref semantics:
```rs
type Counter = { mut n: int }

static_counters: [Counter] = [{ n = 0 }, { n = 20 }]

another_counter = { n = 10 }
mut dynamic_counters: [Counter] = [{ n = 30 }, { n = 40 }]
```

Regarding owned values: Given that owned values are meant to work in mutable struct fields,
we should probably require variables that get moved into struct fields to be mutable.
The reason being that whether a value gets moved into a struct is an optimization decision and the
value cannot be moved if it is used again after struct creation. Allowing immutable owned
values to be moved would mean interpreting the immutability as killing the binding, while implying
a projection in the mutable case, which is too inconsistent and confusing.

Each of the following would be valid:
* `dynamic_counters[0].n += 1`
* `dynamic_counters.append({ n = 0 })`

The following would be invalid:
* `dynamic_counters.append(another_counter)`  ERROR: Cannot mutably project `another_counter` in function `append`
* `static_counters[0].n += 1`  ERROR: Cannot alter element of list as it is declared immutable

##### List mutability pass through semantics
Using a ref list to observe reassignment:
```rs
mut ref_counters: [ref Counter] = []

mut first_counter = { n = 10 }
ref_counters.append(first_counter)

ref_counters[0] = { n = 20 }
```
At the end, `first_counter.n` is now 20.

##### List mutability indirection
Using a sealed list to avoid internal mutability:
```rs
mut sealed_counters: [seal Counter] = []

mut mut_counter = { n = 0 }
mut immut_counter = { n = 10 }
```

The following would be valid:
* `sealed_counters.append(mut_counter)`
* `sealed_counters.append(immut_counter)`

The following would be invalid:
* `sealed_counters[0].n += 1`  ERROR: Cannot alter element of list as it is sealed
* `sealed: [seal Counter] = []`  ERROR: Remove meaningless seal, `sealed` is not mutable

#### Associated class origins
Similar to associated types, classes can define associated origins that implementations
must define.
```rs
class Iterator:
    from items
    type Item

    def next(mut self) -> Option(Self.Item) from Some(self.items)
```

Implementing Iterator for the previously defined list iterator type would look like this:
```rs
use ListIter('t) as Iterator
    where 't is Iterator.Item,
    (self as Iterator).items from self.items:

    def next(mut self) -> Option('t) from self.items:
        index = self.index
        if index < self.items.len():
            self.index += 1
            Some(self.items[index])
        else:
            None
```
