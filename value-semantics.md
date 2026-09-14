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
bad_num = 0
bad_list = [1, 2, 3, 4, 5]

mut inc_num = 0
mut inc_list = [1, 2, 3, 4, 5]

def increment_number(mut number: int):
    number += 1
```

Any one the following would work:
* `increment_number(inc_num)` -> `1`
* `increment_number(inc_list[0])` -> `[2, 2, 3, 4, 5]` 

The following would not work:
* `increment_number(bad_num)` ERROR: Cannot project `bad_num` mutably in funciton `increment_number`
* `increment_number(bad_list[0])` ERROR: Cannot peoject `bad_list[0]` mutably in function `increment_number`

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
Projected values are values that are not owned and have an origin attached. Origins may point to other projections
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
def min(a: 't, b: 't) -> 't from a, b:
    if a < b: a else: b
```

The from specifier can also be used to tie the origin of two arguments together, for example, when appending
the argument to a list:
```rs
def append(mut items: ['t], item: 't from items):
    items.append(item)
```

An important fact to understand about the from specifier is that it is not a conclusive representation of
the real origins of the data used by the compiler. The from clause serves the sole purpose of defining the
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

The `where` clause can be used to specify the origin of individual fields, `.field` refers to fields on the returned value:
```rs
def iterator(items: ['t]) -> ListIter('t) where .items from items:
    ListIter(items)
``` 

##### Field-level mutability
Fields can define the mutability of each of their individual fields. Field internal mutability defined the ceiling
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

Now consider the following example:
```rs
type Point = { mut x: int, mut y: int }

use Point:
    def add(mut self, other: Point):
        self.x += other.x
        self.y += other.y

mut x = 0
mut y = 0
point: Point = { x, y }
point.add({ x = 10, y = 20 })
```

Given the semantics of the increment function stated earlier, it is natural to question whether
the x and y provided will mutate after `point.add` is called. This may seem like reasonable semantics,
but consider the following example next:
```rs
def rewrap_iter(iterator: ListIterator('t)) -> ListIterator('t) from iterator:
    { items = iterator.items, index = iterator.index }
```

According the the same semantics, the rewrapped iterator would have to mutate the other iterator's
index while changing its own, which is unacceptable behavior. As a result, we make the following
guarantee about the assignment to mutable struct fields: it is genuinely changing the struct field
rather than rewriting to the mutable binding that it was assigned with.

##### Field mutability pass-through semantics
This leads us to the first thing structures have to help specify intent: the `mut ref` field
modifier. To achieve the mutating result, simply rewrite the point struct to use `mut ref` fields.
```rs
type Point = { mut ref x: int, mut ref y: int }

use Point:
    ...

mut x = 0
mut y = 0
point: Point = { x, y }
point.add({ x = 10, y = 20 })
```
At the end of this code, the local variable x would be 10, and y would be 20. It is important to understand
that mut ref is literally just a modifier that affects the assignment operator when it is applied to a field and nothing move.

##### Field mutability indirection
Considering that in all cases, item internal mutability assumes the mutability of the binding it resides on, it
becomes is impossible to make a field mutable over numerous immutable fields without writing a wrapper around it.
To rectify this, struct fields also have the ability to specify fields as `mut seal`. This can be thought of
as an invisible single item tuple around the same.
```rs
type Peekable = { iterator: ListIter('t), mut seal current: 't }

use Peekable('t):
    def next() -> 't:
        tmp = self.current
        self.current = self.iterator.items[self.iterator.index]
        self.iterator.index += 1
        tmp

    def peek() -> 't:
        self.current
``` 

Without seal, this would fail because assiging `current` to `iterator.items` would
require it to be mutable. 

#### Associated class origins
Similar to associated types, classes can define associated origins that implementations
must define.
```rs
class Iterator:
    from items
    type Item

    def next(mut self) -> Option(Self.Item) from self.items
```

Implemantating itaration for the previously defined list iterator type would look like this:
```rs
use ListIter('t) as Iterator
    where 't is Iterator.Item,
    (self as Iterator).items from self.items:

    def next(mut self) -> Option('t) from self.items:
        index = self.index
        if index < self.items.len():
            self.index += 1
            self.items[index]
        else:
            None
```
