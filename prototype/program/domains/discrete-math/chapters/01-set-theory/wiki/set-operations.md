# Set Operations

## Difference

### Definition
The difference of two sets A and B (written A − B or A\B) is the set of elements in A that are not in B.
- A − B = { x | x ∈ A and x ∉ B }
  > Source: Set Operations.html

### Example
If A = {1,2,3,4} and B = {3,4,5}:
- A − B = {1,2}
- B − A = {5}
  > Source: Set Operations.html

On a Venn diagram: shade the part of A that does not overlap with B.
> Source: Set Operations.html

---

## Complement

### Definition
The complement of a set A (written A', Aᶜ or Ā) includes all elements of the universal set U that are not in A.
- A' = { x ∈ U | x ∉ A }
  > Source: Set Operations.html

**Note:** Complements only make sense once the universal set is defined.
> Source: Set Operations.html

### Example
If U = {1,2,3,4,5,6} and A = {2,4,6}: A' = {1,3,5}
> Source: Set Operations.html

---

## Set Identities

Set identities always hold, no matter what sets you're working with.
> Source: Set Operations.html

### Identity Laws
A ∩ U = A  
A ∪ ∅ = A
> Source: Set Operations.html

### Domination Laws
A ∪ U = U  
A ∩ ∅ = ∅
> Source: Set Operations.html

### Idempotent Laws
Repeating the same operation on a set doesn't change the result.  
A ∪ A = A  
A ∩ A = A
> Source: Set Operations.html

### Complementation Law
Taking the complement twice returns the original set.  
(A′)′ = A
> Source: Set Operations.html

### Commutative Laws
The order of sets doesn't matter.  
A ∪ B = B ∪ A  
A ∩ B = B ∩ A
> Source: Set Operations.html

### Associative Laws
When combining three sets, the grouping doesn't matter.  
A ∪ (B ∪ C) = (A ∪ B) ∪ C  
A ∩ (B ∩ C) = (A ∩ B) ∩ C
> Source: Set Operations.html

### Distributive Laws
Union distributes over intersection, and intersection distributes over union.  
A ∪ (B ∩ C) = (A ∪ B) ∩ (A ∪ C)  
A ∩ (B ∪ C) = (A ∩ B) ∪ (A ∩ C)
> Source: Set Operations.html

### De Morgan's Laws
Complements of unions and intersections "flip" the operations.  
(A ∪ B)′ = A′ ∩ B′  
(A ∩ B)′ = A′ ∪ B′
> Source: Set Operations.html

**Example:** U = {1,2,3,4}, A = {1}, B = {2}:
- (A∪B)′ = {1,2}′ = {3,4}
- A′∩B′ = {2,3,4} ∩ {1,3,4} = {3,4} ✓
  > Source: Set Operations.html

### Absorption Laws
A set "absorbs" another when combined with its own union or intersection.  
A ∪ (A ∩ B) = A  
A ∩ (A ∪ B) = A
> Source: Set Operations.html

### Complement Laws
A set and its complement cover all of U; their intersection is empty.  
A ∪ A′ = U  
A ∩ A′ = ∅
> Source: Set Operations.html

### Difference-Complement Identity
The set difference can be expressed using intersection and complement.  
A − B = A ∩ B̅
> Source: 5.PNG

### Complement Partition Identity
A set can be reconstructed from its intersection with another set and the intersection with that set's complement.  
(A ∩ B) ∪ (A ∩ B̅) = A
> Source: 5.PNG

## Related Topics
- [Special Sets](special-sets.md)
- [Venn Diagrams](venn-diagrams.md)
- [Set Partitions](set-partitions.md)
