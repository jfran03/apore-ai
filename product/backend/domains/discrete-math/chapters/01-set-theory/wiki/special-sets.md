# Special Sets

## Cardinality

### Definition
The cardinality of a set is the number of distinct elements it contains, written as |A|.
> Source: Special Sets.html

### Examples
- |{2, 4, 6}| = 3
- |{red, blue, green, blue}| = 3 (duplicates don't count)
- |∅| = 0
- The set of natural numbers ℕ has infinite cardinality.
  > Source: Special Sets.html

---

## Singleton Set

### Definition
A singleton set is a set with exactly one element.
> Source: Special Sets.html

### Examples
- {7}
- {AdminRole}
  > Source: Special Sets.html

---

## The Empty Set

### Definition
The empty set (also called the null set) is a set with no elements. Written as { } or ∅.
> Source: Special Sets.html

### Key Properties
- It is a subset of every set.
- It has cardinality 0.
- It is unique: there is only one empty set.
  > Source: Special Sets.html

### Examples
- The set of whole numbers less than 0 is ∅.
- The set of squares of numbers between 2 and 3 is ∅.
  > Source: Special Sets.html

---

## Subsets and Proper Subsets

### Subsets
Set A is a subset of set B if every element of A is also an element of B. Notation: A ⊆ B ("A is a subset of B").
> Source: Special Sets.html

Examples of subsets:
- {1,2} ⊆ {1,2,3}
- {red, blue} ⊆ {red, blue, yellow}
- {1,2,3} ⊆ {1,2,3} (every set is a subset of itself)
- ∅ ⊆ {1,2,3} (the empty set is always a subset)
  > Source: Special Sets.html

### Proper Subsets
Set A is a proper subset of B if every element of A is also in B, AND A ≠ B. Notation: A ⊂ B ("A is a proper subset of B").
> Source: Special Sets.html

Examples of proper subsets:
- {1,2} ⊂ {1,2,3}
- {red, blue} ⊂ {red, blue, yellow}
- ∅ ⊂ {1,2,3}

Not proper subsets:
- {1,2,3} ⊂ {1,2,3} — fails because they're equal
- {1,2,3,4} ⊂ {1,2,3} — fails because 4 is not in the second set
  > Source: Special Sets.html

**Key Takeaway:**
- ⊆ (subset): Can be "smaller" or equal
- ⊂ (proper subset): Must be strictly smaller (A ≠ B)
  > Source: Special Sets.html

---

## The Power Set

### Definition
The power set of a set A is the set of all possible subsets of A. Notation: P(A), pow(A) or 𝒫(A).
> Source: Special Sets.html

### Key Rule
If a set has n elements, its power set has 2ⁿ elements: |P(A)| = 2ⁿ.
> Source: Special Sets.html

### Examples
- A = {1,2} → P(A) = { ∅, {1}, {2}, {1,2} }
- A = {x,y,z} has 3 elements → |P(A)| = 2³ = 8
  > Source: Special Sets.html

---

## Equal Sets

### Definition
Two sets are equal if they contain exactly the same elements. Order doesn't matter; duplicates don't affect equality.
> Source: Special Sets.html

### Rule
If every element of A is in B, and every element of B is in A, then A = B.
> Source: Special Sets.html

### Examples
- {1,2,3} = {3,2,1}
- {red, blue, red, yellow} = {yellow, red, blue}
- ∅ = { }
  > Source: Special Sets.html

---

## Disjoint Sets

### Definition
Two sets are disjoint if they share no elements in common. Their intersection is the empty set: A ∩ B = ∅.
> Source: Special Sets.html

### Examples
- {1,2,3} and {4,5,6} are disjoint
- {Admin, User} and {Guest, Auditor} are disjoint
- {red, blue} and {blue, green} are NOT disjoint (they share "blue")
  > Source: Special Sets.html

## Related Topics
- [What is a Set](what-is-a-set.md)
- [Venn Diagrams](venn-diagrams.md)
- [Set Operations](set-operations.md)
- [Set Partitions](set-partitions.md)
