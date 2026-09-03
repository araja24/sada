# Sada

A web app that helps a Muslim match the *style* of their Quran recitation — melody, pacing, tone, elongation timing — to a specific professional reciter's. It is a style coach, never a correctness or tajweed checker.

## Language

**Sada**:
The product's name. Chosen because it means "echo" in Arabic/Urdu — fitting for an app about echoing a reciter's style.
_Avoid_: Recitation Coach (the working title used in the original PRD before this was named).

**Reciter**:
A professional Quran reciter whose recorded delivery serves as the style reference a user tries to match. v1 ships with exactly one preset reciter, Mishari Rashid al-`Afasy; more will be added later without changing this definition. (Originally planned as Maher Al Muaiqly -- switched because Maher isn't available on Quran Foundation's prelive tier, only production, which needs separate approval; see `docs/adr/0001-reference-data-source.md`. Revisit once/if production access is granted.)
