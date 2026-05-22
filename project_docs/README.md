# Semantra Project Docs

Ovaj folder drži mali skup projektnih dokumenata sa jasnim ulogama. Cilj je da stanje proizvoda, istorija isporuke, sledeći prioriteti i izvršne checkliste budu pregledni bez međusobnog preklapanja.

Ovaj set je usklađen sa trenutnim stanjem proizvoda zaključno sa 2026-05-22.

## Preporučeni red čitanja

1. `current_state.md`
	 - šta je danas stvarno implementirano i šta proizvod podržava
2. `completed_slices.md`
	 - hronologija isporučenih slice-ova i završenih faza
3. `plan.md`
	 - forward-looking prioriteti, redosled rada i tehničke teme
4. `epics.md`
	 - backlog mapa po epicima i njihov trenutni status
5. `implementation_checklists.md`
	 - aktivni izvršni checklist-i i release/hardening stavke

## Uloga svakog dokumenta

- `current_state.md`
	- primarni kontrolni dokument za današnje stanje proizvoda
	- uključuje i trenutnu granicu session continuity ponašanja i otvoreni resume-by-design fokus
- `completed_slices.md`
	- istorijski ledger; ovde ide ono što je završeno
- `plan.md`
	- ne opisuje istoriju i ne služi kao changelog; koristi se za sledeći redosled rada
- `epics.md`
	- backlog mapa; ne služi kao detaljna hronologija isporuke
- `implementation_checklists.md`
	- samo aktivne ili neposredno relevantne radne liste

## Pravila za održavanje foldera

- Novi "snapshot" ili "strategy review" dokument ne otvarati ako isti sadržaj može da stane u `current_state.md`, `plan.md` ili `completed_slices.md`.
- Kada se feature završi, detaljna checklist stavka izlazi iz `implementation_checklists.md` i prelazi u `completed_slices.md`.
- `epics.md` treba da ostane backlog mapa, ne mešavina retrospektive i aktivnih zadataka.
- `current_state.md` je mesto gde prvo proveravamo šta proizvod danas podržava.
- Kada se završi veći execution wave, `plan.md` mora da se prepiše tako da sledeći koraci budu jasni, a ne da zadržava jučerašnje prioritete.

## Granica ovog foldera

U `project_docs/` držimo samo projektno-upravljačke dokumente.

Van ovog foldera ostaju:

- `docs/vision/` za vision i product memo dokumente
- `docs/reference/` za dublje tehničke reference kao što su scoring, warning/runtime behavior, benchmark metrike, correction-impact i canonical/catalog reference
- `docs/pilot/` za pilot/test planove
- `docs/presentation/` i slični stakeholder/demo artefakti