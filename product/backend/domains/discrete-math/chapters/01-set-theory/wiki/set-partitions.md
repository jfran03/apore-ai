# Set Partitions

## Definition
A partition of a set S is a collection of non-empty subsets of S, written as {A₁, A₂, …, Aₖ}, such that:
- Aᵢ ∩ Aⱼ = ∅ for all i ≠ j (the subsets are pairwise disjoint)
- A₁ ∪ A₂ ∪ ... ∪ Aₖ = S (together they cover the whole set)
  > Source: Set Partitions.html

In plain terms:
- Every element of S belongs to exactly one piece.
- No element belongs to more than one piece.
- The union of all pieces equals S.
  > Source: Set Partitions.html

Think of a partition like dividing a pie into slices — each slice is separate, but together they make up the whole pie.
> Source: Set Partitions.html

## Examples

**Example 1:** Let S = {1,2,3,4,5,6}.
- { {1,2}, {3,4}, {5,6} } — valid partition
- { {1,3,5}, {2,4,6} } — also valid
  > Source: Set Partitions.html

**Example 2:** Let S = {a,b,c}. All possible partitions:
- { {a}, {b}, {c} }
- { {a,b}, {c} }
- { {a,c}, {b} }
- { {b,c}, {a} }
- { {a,b,c} }
  > Source: Set Partitions.html

**Example 3:** U = {Alice, Xi, Carol, Dave}. Partition into roles: { {Alice, Xi}, {Carol}, {Dave} }
> Source: Set Partitions.html

## Common Misconceptions
{ {1,2}, {2,3} } is NOT a valid partition of {1,2,3} because element 2 appears in two subsets — the subsets are not disjoint.
> Source: Set Partitions.html

## Applications
- **Computer science:** Datasets partitioned into training and testing subsets; hashing algorithms split data into separate "buckets" where each item belongs to exactly one bucket.
- **Cybersecurity:** Users separated into roles (administrators, developers, auditors) where each user belongs to exactly one role; network segmentation partitions devices into non-overlapping subnets.
- **Everyday life:** Students partitioned into grade levels; a deck of cards into four suits; organizing a closet into shirts, pants, and jackets.
  > Source: Set Partitions.html

## Did You Know
Partitions of sets are related to Bell numbers in combinatorics, which count the number of ways to partition a set. A 3-element set has 5 different partitions; a 4-element set has 15.
> Source: Set Partitions.html

## Related Topics
- [Special Sets](special-sets.md)
- [Set Operations](set-operations.md)
