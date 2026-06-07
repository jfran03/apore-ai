# Question Bank

> Generated from `wiki/` during the compile step. Extended on wrong-answer targeting and graduation.
> Do not edit manually — all changes are made by Claude during compile and session flows.

---

<!-- Question format (do not delete this comment):

## Q{NNN}
**Status:** active | retired
**Type:** mcq | short-answer | conceptual | true-false
**Difficulty:** introductory | intermediate | advanced
**Topic:** {topic-slug}
**Focus Area:** {specific concept or sub-topic}
**Question:** {question text}
**Answer:** {model answer — sourced from wiki only}

-->

## Q001
**Status:** active
**Type:** true-false
**Difficulty:** introductory
**Topic:** what-is-a-set
**Focus Area:** unordered property
**Question:** True or False: The set {1, 2, 3} and the set {3, 2, 1} are different sets because their elements appear in a different order.
**Answer:** False. A set is unordered — the order of elements doesn't matter. {1,2,3} and {3,2,1} are the same set. (Based on what-is-a-set.md)

## Q002
**Status:** active
**Type:** short-answer
**Difficulty:** introductory
**Topic:** what-is-a-set
**Focus Area:** distinct property
**Question:** How many elements does the set {a, b, a, c, b} contain?
**Answer:** 3. Sets only contain distinct elements, so duplicates are removed. The set is {a, b, c}, which has cardinality 3. (Based on what-is-a-set.md)

## Q003
**Status:** active
**Type:** mcq
**Difficulty:** introductory
**Topic:** what-is-a-set
**Focus Area:** well-defined sets
**Question:** Which of the following is a valid set? (A) The set of tall people (B) The set of prime numbers less than 10 (C) The set of hard problems (D) The set of interesting movies
**Answer:** (B) The set of prime numbers less than 10 = {2, 3, 5, 7}. It is well-defined because you can clearly determine whether any number belongs. Options A, C, and D rely on subjective judgments and cannot be clearly defined. (Based on what-is-a-set.md)

## Q004
**Status:** active
**Type:** mcq
**Difficulty:** introductory
**Topic:** what-is-a-set
**Focus Area:** common number sets
**Question:** Which symbol represents the set of all integers (including negative numbers and zero)?
**Answer:** ℤ, which represents {…, −2, −1, 0, 1, 2, …}. ℕ is natural numbers, ℚ is rationals, ℝ is reals, ℂ is complex numbers. (Based on what-is-a-set.md)

## Q005
**Status:** active
**Type:** mcq
**Difficulty:** introductory
**Topic:** ways-to-describe-sets
**Focus Area:** roster vs set-builder notation
**Question:** Which of the following is an example of set-builder notation? (A) {2, 4, 6, 8} (B) {red, blue, yellow} (C) { x ∈ ℕ | x < 5 } (D) "All students enrolled in the course"
**Answer:** (C) { x ∈ ℕ | x < 5 }. Set-builder notation describes a set by a property or rule rather than listing elements explicitly. (A) and (B) are roster notation. (D) is a plain-language description. (Based on ways-to-describe-sets.md)

## Q006
**Status:** active
**Type:** short-answer
**Difficulty:** intermediate
**Topic:** ways-to-describe-sets
**Focus Area:** converting set-builder to roster
**Question:** Write { x ∈ ℕ | x < 5 } using roster notation.
**Answer:** {0, 1, 2, 3, 4}. The set contains all natural numbers less than 5. (ℕ includes 0 per the source.) (Based on ways-to-describe-sets.md)

## Q007
**Status:** active
**Type:** short-answer
**Difficulty:** intermediate
**Topic:** ways-to-describe-sets
**Focus Area:** constructing set-builder notation
**Question:** Write the set of even integers using set-builder notation.
**Answer:** { x ∈ ℤ | x is even }. This describes all integers satisfying the property of being even. (Based on ways-to-describe-sets.md)

## Q008
**Status:** active
**Type:** short-answer
**Difficulty:** introductory
**Topic:** special-sets
**Focus Area:** cardinality
**Question:** What is the cardinality of the set {a, b, c, a, d}?
**Answer:** 4. The distinct elements are a, b, c, d. Cardinality counts only distinct elements, so the duplicate 'a' is not counted twice. |{a, b, c, d}| = 4. (Based on special-sets.md)

## Q009
**Status:** active
**Type:** true-false
**Difficulty:** introductory
**Topic:** special-sets
**Focus Area:** empty set — subset of every set
**Question:** True or False: The empty set ∅ is a subset of every set.
**Answer:** True. ∅ ⊆ A for any set A. This is one of the key properties of the empty set. (Based on special-sets.md)

## Q010
**Status:** active
**Type:** mcq
**Difficulty:** introductory
**Topic:** special-sets
**Focus Area:** empty set properties
**Question:** Which of the following is true about the empty set ∅? (A) It has cardinality 1 (B) It is a subset of every set (C) It is not a subset of itself (D) It contains exactly one element: nothing
**Answer:** (B) The empty set is a subset of every set. Its cardinality is 0 (not 1), it is a subset of itself (∅ ⊆ ∅), and it contains no elements — not even "nothing." (Based on special-sets.md)

## Q011
**Status:** active
**Type:** true-false
**Difficulty:** intermediate
**Topic:** special-sets
**Focus Area:** proper subset vs subset
**Question:** True or False: {1, 2, 3} ⊂ {1, 2, 3} (i.e., {1,2,3} is a proper subset of itself).
**Answer:** False. A proper subset requires A ≠ B. Since {1,2,3} = {1,2,3}, it is a subset (⊆) but NOT a proper subset (⊂). (Based on special-sets.md)

## Q012
**Status:** active
**Type:** short-answer
**Difficulty:** intermediate
**Topic:** special-sets
**Focus Area:** power set
**Question:** If A = {p, q}, list all elements of P(A) (the power set of A).
**Answer:** P(A) = { ∅, {p}, {q}, {p,q} }. The power set contains all possible subsets of A, including the empty set and A itself. (Based on special-sets.md)

## Q013
**Status:** active
**Type:** short-answer
**Difficulty:** intermediate
**Topic:** special-sets
**Focus Area:** power set cardinality formula
**Question:** A set A has 4 elements. How many elements does its power set P(A) have?
**Answer:** 2⁴ = 16. If a set has n elements, its power set always has 2ⁿ elements. (Based on special-sets.md)

## Q014
**Status:** active
**Type:** short-answer
**Difficulty:** introductory
**Topic:** special-sets
**Focus Area:** disjoint sets
**Question:** Are the sets {2, 4, 6} and {1, 3, 5} disjoint? Explain.
**Answer:** Yes, they are disjoint. They share no elements in common, so their intersection is the empty set: {2,4,6} ∩ {1,3,5} = ∅. (Based on special-sets.md)

## Q015
**Status:** active
**Type:** true-false
**Difficulty:** introductory
**Topic:** special-sets
**Focus Area:** equal sets
**Question:** True or False: {red, blue, red, yellow} = {yellow, red, blue}.
**Answer:** True. Sets ignore duplicates and order. Both sets contain exactly {red, blue, yellow}. (Based on special-sets.md)

## Q016
**Status:** active
**Type:** short-answer
**Difficulty:** introductory
**Topic:** venn-diagrams
**Focus Area:** intersection
**Question:** If A = {2, 4, 6} and B = {4, 5, 6}, what is A ∩ B?
**Answer:** {4, 6}. The intersection contains the elements common to both sets. (Based on venn-diagrams.md)

## Q017
**Status:** active
**Type:** short-answer
**Difficulty:** introductory
**Topic:** venn-diagrams
**Focus Area:** union
**Question:** If A = {1, 2, 3} and B = {3, 4, 5}, what is A ∪ B?
**Answer:** {1, 2, 3, 4, 5}. The union contains all elements from both sets, with no duplicates. (Based on venn-diagrams.md)

## Q018
**Status:** active
**Type:** true-false
**Difficulty:** introductory
**Topic:** venn-diagrams
**Focus Area:** union calculation
**Question:** True or False: The union of {1, 2, 3} and {3, 4, 5} is {1, 2, 3, 4, 5}.
**Answer:** True. The union includes all elements from both sets; the shared element 3 appears only once. (Based on venn-diagrams.md)

## Q019
**Status:** active
**Type:** short-answer
**Difficulty:** intermediate
**Topic:** set-operations
**Focus Area:** set difference
**Question:** If A = {1,2,3,4} and B = {3,4,5}, what is A − B?
**Answer:** {1, 2}. A − B contains elements in A that are NOT in B. Elements 3 and 4 are removed because they appear in B. (Based on set-operations.md)

## Q020
**Status:** active
**Type:** short-answer
**Difficulty:** intermediate
**Topic:** set-operations
**Focus Area:** complement
**Question:** If U = {a,b,c,d} and A = {a,c}, what is Aᶜ (the complement of A)?
**Answer:** {b, d}. The complement contains all elements of the universal set U that are not in A. (Based on set-operations.md)

## Q021
**Status:** active
**Type:** true-false
**Difficulty:** advanced
**Topic:** set-operations
**Focus Area:** De Morgan's Laws
**Question:** True or False: (A ∪ B)′ = A′ ∩ B′.
**Answer:** True. This is De Morgan's Law: the complement of a union equals the intersection of the complements. (Based on set-operations.md)

## Q022
**Status:** active
**Type:** short-answer
**Difficulty:** advanced
**Topic:** set-operations
**Focus Area:** De Morgan's Laws — verification
**Question:** Let U = {1,2,3,4}, A = {1}, B = {2}. Verify De Morgan's Law by computing both sides of (A ∪ B)′ = A′ ∩ B′.
**Answer:** Left side: A ∪ B = {1,2}, so (A∪B)′ = {3,4}. Right side: A′ = {2,3,4}, B′ = {1,3,4}, so A′∩B′ = {3,4}. Both sides equal {3,4}. ✓ (Based on set-operations.md)

## Q023
**Status:** active
**Type:** short-answer
**Difficulty:** advanced
**Topic:** set-operations
**Focus Area:** Distributive Law
**Question:** Let A = {1,2}, B = {2,3}, C = {1,4}. Compute A ∩ (B ∪ C) and (A ∩ B) ∪ (A ∩ C). Are they equal?
**Answer:** B ∪ C = {1,2,3,4}. A ∩ (B∪C) = {1,2}. A ∩ B = {2}. A ∩ C = {1}. (A∩B) ∪ (A∩C) = {1,2}. Both sides equal {1,2}. ✓ This demonstrates the distributive law. (Based on set-operations.md)

## Q024
**Status:** active
**Type:** short-answer
**Difficulty:** intermediate
**Topic:** set-operations
**Focus Area:** complement laws
**Question:** If U = {1,2,3,4} and A = {1,2}, what is A ∪ A′?
**Answer:** {1,2,3,4} = U. By the Complement Law, A ∪ A′ = U. A′ = {3,4}, so {1,2} ∪ {3,4} = {1,2,3,4}. (Based on set-operations.md)

## Q025
**Status:** active
**Type:** true-false
**Difficulty:** intermediate
**Topic:** set-operations
**Focus Area:** identity laws
**Question:** True or False: For any set A and universal set U, A ∩ U = A.
**Answer:** True. This is the Identity Law: intersecting a set with the universal set gives back the original set unchanged. (Based on set-operations.md)

## Q026
**Status:** active
**Type:** conceptual
**Difficulty:** introductory
**Topic:** set-partitions
**Focus Area:** partition definition — three conditions
**Question:** What three conditions must a collection of subsets satisfy to be a valid partition of a set S?
**Answer:** (1) Every subset must be non-empty. (2) The subsets must be pairwise disjoint — no element appears in more than one subset (Aᵢ ∩ Aⱼ = ∅ for i ≠ j). (3) The union of all subsets equals S — every element of S appears in exactly one subset. (Based on set-partitions.md)

## Q027
**Status:** active
**Type:** mcq
**Difficulty:** intermediate
**Topic:** set-partitions
**Focus Area:** identifying valid partitions
**Question:** Which of the following is a valid partition of S = {1,2,3,4}? (A) { {1,2}, {2,3,4} } (B) { {1,2}, {3}, {4} } (C) { {1,2,3,4}, ∅ } (D) { {1,3}, {2,4}, {1} }
**Answer:** (B) { {1,2}, {3}, {4} }. These subsets are non-empty, pairwise disjoint, and their union = {1,2,3,4}. (A) fails because 2 appears in two subsets. (C) fails because ∅ is not allowed (subsets must be non-empty). (D) fails because 1 appears in two subsets. (Based on set-partitions.md)

## Q028
**Status:** active
**Type:** mcq
**Difficulty:** introductory
**Topic:** what-is-a-set
**Focus Area:** well-defined sets — wrong-answer follow-up for Q003
**Question:** Which of the following describes a valid set? (A) The group of all enrolled students in MATH 3000 (B) The set of difficult concepts (C) The set of beautiful paintings (D) The set of important people
**Answer:** (A) The group of all enrolled students in MATH 3000. Membership is objectively determinable. Options B, C, and D rely on subjective judgment and therefore cannot be clearly defined as sets. (Based on what-is-a-set.md)

## Q029
**Status:** active
**Type:** true-false
**Difficulty:** intermediate
**Topic:** ways-to-describe-sets
**Focus Area:** ℕ includes 0 — wrong-answer follow-up for Q006
**Question:** True or False: The set { x ∈ ℕ | x < 3 } written in roster notation is {1, 2}.
**Answer:** False. ℕ includes 0, so the correct roster is {0, 1, 2}. (Based on ways-to-describe-sets.md)

## Q030
**Status:** active
**Type:** true-false
**Difficulty:** intermediate
**Topic:** special-sets
**Focus Area:** empty set as subset — wrong-answer follow-up for Q009
**Question:** True or False: ∅ ⊆ {5, 10, 15}.
**Answer:** True. The empty set is a subset of every set, including {5, 10, 15}. (Based on special-sets.md)

## Q031
**Status:** active
**Type:** short-answer
**Difficulty:** intermediate
**Topic:** ways-to-describe-sets
**Focus Area:** converting roster to set-builder notation
**Question:** Write the set {0, 3, 6, 9, 12} using set-builder notation.
**Answer:** { x ∈ ℕ | x is a multiple of 3 and x ≤ 12 }. The elements are multiples of 3 from 0 to 12. (Based on ways-to-describe-sets.md, 1.PNG)

## Q032
**Status:** active
**Type:** short-answer
**Difficulty:** intermediate
**Topic:** ways-to-describe-sets
**Focus Area:** converting roster to set-builder notation
**Question:** Write the set {−3, −2, −1, 0, 1, 2, 3} using set-builder notation.
**Answer:** { x ∈ ℤ | −3 ≤ x ≤ 3 }. The set contains all integers from −3 to 3 inclusive. (Based on ways-to-describe-sets.md, 1.PNG)

## Q033
**Status:** active
**Type:** short-answer
**Difficulty:** intermediate
**Topic:** set-operations
**Focus Area:** listing elements from set-builder definitions
**Question:** Let U = { x ∈ ℤ | 0 < x ≤ 20 }, A = { x | x is a factor of 36 }, B = { x | x is a positive multiple of 3 less than 20 }. List all the elements of A and B (within U).
**Answer:** A = {1, 2, 3, 4, 6, 9, 12, 18} (factors of 36 that fall within U). B = {3, 6, 9, 12, 15, 18} (positive multiples of 3 less than 20). (Based on ways-to-describe-sets.md, set-operations.md, 2.PNG)

## Q034
**Status:** active
**Type:** short-answer
**Difficulty:** advanced
**Topic:** set-operations
**Focus Area:** complement and De Morgan's Laws
**Question:** Using U = {1,2,…,20}, A = {1,2,3,4,6,9,12,18}, B = {3,6,9,12,15,18}, compute A̅ ∪ B̅.
**Answer:** A̅ = {5,7,8,10,11,13,14,15,16,17,19,20}. B̅ = {1,2,4,5,7,8,10,11,13,14,16,17,19,20}. A̅ ∪ B̅ = {1,2,4,5,7,8,10,11,13,14,15,16,17,19,20}. By De Morgan's Law, this equals (A ∩ B)̅. (Based on set-operations.md, 2.PNG)

## Q035
**Status:** active
**Type:** conceptual
**Difficulty:** intermediate
**Topic:** set-operations
**Focus Area:** difference-complement identity
**Question:** Using the identity A − B = A ∩ B̅, rewrite the expression C − D without the difference operator.
**Answer:** C ∩ D̅. The set difference of C and D equals the intersection of C with the complement of D. (Based on set-operations.md, 5.PNG)

## Q036
**Status:** active
**Type:** short-answer
**Difficulty:** advanced
**Topic:** set-operations
**Focus Area:** complement partition identity
**Question:** Let U = {1,2,3,4,5}, A = {1,2,3,4}, B = {2,3}. Verify that (A ∩ B) ∪ (A ∩ B̅) = A.
**Answer:** B̅ = {1,4,5}. A ∩ B = {2,3}. A ∩ B̅ = {1,4}. (A ∩ B) ∪ (A ∩ B̅) = {2,3} ∪ {1,4} = {1,2,3,4} = A. ✓ (Based on set-operations.md, 5.PNG)

## Q037
**Status:** active
**Type:** conceptual
**Difficulty:** intermediate
**Topic:** set-operations
**Focus Area:** set relationship implications
**Question:** If A ∪ B = A, what can you conclude about the relationship between A and B? Justify your answer.
**Answer:** B ⊆ A. Since A ∪ B = { x | x ∈ A or x ∈ B } and the result equals A, every element of B must already be in A — the union adds nothing new. (Based on venn-diagrams.md, set-operations.md, 7.PNG)

## Q038
**Status:** active
**Type:** conceptual
**Difficulty:** intermediate
**Topic:** set-operations
**Focus Area:** set relationship implications
**Question:** If A − B = A, what does this tell you about A and B?
**Answer:** A and B are disjoint (A ∩ B = ∅). Since A − B = { x | x ∈ A and x ∉ B } and the result equals A, removing B's elements changes nothing — meaning A and B share no elements. (Based on set-operations.md, special-sets.md, 7.PNG)

## Q039
**Status:** active
**Type:** short-answer
**Difficulty:** intermediate
**Topic:** set-partitions
**Focus Area:** constructing partitions
**Question:** Give three valid partitions of the set A = {−5, −6, −7, 0, 6, 7, 8, 9, 10}.
**Answer:** Answers may vary. Examples: (1) { {−5,−6,−7}, {0}, {6,7,8,9,10} } (2) { {−5,−6,−7,0}, {6,7,8,9,10} } (3) { {−7,−6,−5}, {0,6}, {7,8,9,10} }. Each must be non-empty, pairwise disjoint, and union to A. (Based on set-partitions.md, 6.PNG)

## Q040
**Status:** active
**Type:** true-false
**Difficulty:** intermediate
**Topic:** set-operations
**Focus Area:** commutativity of set difference
**Question:** True or False: For any two sets A and B, A − B = B − A.
**Answer:** False. Set difference is not commutative. For example, if A = {1,2,3} and B = {3,4,5}, then A − B = {1,2} but B − A = {4,5}. A − B = B − A only when A = B. (Based on set-operations.md, 7.PNG)

## Q041
**Status:** active
**Type:** short-answer
**Difficulty:** intermediate
**Topic:** ways-to-describe-sets
**Focus Area:** constructing set-builder notation — wrong-answer follow-up for Q007
**Question:** Write the set of all integers strictly between −5 and 5 using set-builder notation.
**Answer:** { x ∈ ℤ | −5 < x < 5 }. The domain is ℤ (integers) and the condition bounds x strictly between −5 and 5. (Based on ways-to-describe-sets.md)

## Q042
**Status:** active
**Type:** short-answer
**Difficulty:** intermediate
**Topic:** ways-to-describe-sets
**Focus Area:** constructing set-builder notation — wrong-answer follow-up for Q007
**Question:** Write the set of all natural numbers greater than 10 using set-builder notation.
**Answer:** { x ∈ ℕ | x > 10 }. The domain is ℕ (natural numbers) and the condition is x > 10. (Based on ways-to-describe-sets.md)

## Q043
**Status:** active
**Type:** true-false
**Difficulty:** intermediate
**Topic:** special-sets
**Focus Area:** proper subset — a set is not a proper subset of itself — wrong-answer follow-up for Q011
**Question:** True or False: ∅ ⊂ ∅ (the empty set is a proper subset of itself).
**Answer:** False. A proper subset requires A ≠ B. Since ∅ = ∅, the empty set is a subset (⊆) of itself but never a proper subset (⊂). No set is ever a proper subset of itself. (Based on special-sets.md)

## Q044
**Status:** active
**Type:** mcq
**Difficulty:** intermediate
**Topic:** special-sets
**Focus Area:** proper subset vs subset — both can hold simultaneously — wrong-answer follow-up for Q011
**Question:** Given A = {1,2} and B = {1,2,3}, which statement is true? (A) A ⊆ B only (B) A ⊂ B only (C) Both A ⊆ B and A ⊂ B (D) Neither
**Answer:** (C) Both A ⊆ B and A ⊂ B. Every element of A is in B (so A ⊆ B), and A ≠ B (so A ⊂ B). Every proper subset is also a subset — ⊂ implies ⊆, but not vice versa. (Based on special-sets.md)

## Q045
**Status:** active
**Type:** short-answer
**Difficulty:** intermediate
**Topic:** special-sets
**Focus Area:** power set cardinality formula — reverse application — wrong-answer follow-up for Q013
**Question:** If |P(A)| = 8, how many elements does A have?
**Answer:** 3. Since |P(A)| = 2ⁿ and 2³ = 8, A must have 3 elements. (Based on special-sets.md)

## Q046
**Status:** active
**Type:** true-false
**Difficulty:** intermediate
**Topic:** special-sets
**Focus Area:** power set cardinality — edge case with empty set — wrong-answer follow-up for Q013
**Question:** True or False: The power set of the empty set is also the empty set.
**Answer:** False. |P(∅)| = 2⁰ = 1. The power set of the empty set contains exactly one element — the empty set itself: P(∅) = {∅}. (Based on special-sets.md)

## Q047
**Status:** active
**Type:** true-false
**Difficulty:** intermediate
**Topic:** set-operations
**Focus Area:** complement laws — distinguishing union vs intersection — wrong-answer follow-up for Q024
**Question:** True or False: For any set A and universal set U, A ∩ A′ = U.
**Answer:** False. A ∩ A′ = ∅. A set and its complement share no elements — their intersection is always empty. It is the union that covers everything: A ∪ A′ = U. (Based on set-operations.md)
