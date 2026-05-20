# Semantra Docs

Ovaj folder drži šire product, reference, pilot i wave dokumente koji nisu deo uskog `project_docs/` plan/current-state seta.

Koristi ga za:

- product vision memo dokumente
- detaljne tehničke reference
- pilot i benchmark planove
- veće wave dokumente koji ne treba da opterete kratke project-management dokumente

## Novi knowledge-expansion dokumenti

- `vision/KNOWLEDGE_EXPANSION_WAVE.md`
	- why-now, boundary, phase model i exit criteria za SAP-first vendor knowledge wave
- `reference/VENDOR_KNOWLEDGE_INGEST_AND_SOURCE_INVENTORY.md`
	- konkretan source inventory, staging schema i predloženi folder layout za raw/staged/generated vendor knowledge ingest
- `reference/KNOWLEDGE_CANONICAL_AUTHORITY_MATRIX.md`
	- authority matrix za knowledge/canonical sloj: sta je source-of-truth u fajlovima, sta je runtime snapshot u bazi, i kako radi DB-first reseed logika
- `pilot/SAP_BENCHMARK_MATRIX.md`
	- prvi benchmark matrix za SAP-first coverage i quality merenje nad postojećim fixture porodicama

## Folder roles

- `vision/`
	- veći product i wave memo dokumenti
- `reference/`
	- detaljne tehničke reference i operational model dokumenti
- `pilot/`
	- pilot test planovi, benchmark matrix-i i execution logovi
- `presentation/`
	- stakeholder i demo artefakti