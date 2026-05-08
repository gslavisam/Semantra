# Semantra Project Docs Map

Ovaj folder drži projektno-upravljačke dokumente za Semantru.

Koristi ih ovim redom:

- `plan.md`: strateški roadmap, tehničke faze, preporučeni redosled rada i operativna pravila.
- `epics.md`: backlog epika i njihov scope.
- `implementation_checklists.md`: aktivne MVP checkliste, release gate-ovi i izvršni koraci.
- `completed_slices.md`: isporučeni slice-ovi i završene tehničke faze.

## Kada koristiti koji dokument

Ako pitaš:

- "Kuda projekat ide?" -> `plan.md`
- "Koje velike teme postoje?" -> `epics.md`
- "Šta tačno radimo sledeće?" -> `implementation_checklists.md`
- "Šta je već završeno?" -> `completed_slices.md`

## Procena ostalih važnih dokumenata

Ovi dokumenti su i dalje korisni, ali nisu isti tip dokumentacije kao projektni backlog i plan, pa ih zato ne bih mešao u ovaj folder bez jasnog razloga.

### `docs/pilot/REAL_LIFE_PILOT_TEST_PLAN.md`

Status: zadržati.

Zašto:

- to je operativni pilot-validation dokument, ne backlog i ne roadmap
- koristan je za real-data proveru i release/pilot stabilizaciju
- ima dovoljno specifičnu namenu da ne treba da se utopi u `implementation_checklists.md`

Preporuka:

- ostaviti ga kao zaseban dokument
- držati ga u `docs/pilot/` kao tematski pilot-validation dokument

### `docs/vision/INTEGRATION_CATALOG_VISION.md`

Status: zadržati.

Zašto:

- to je dubinski vision dokument za jednu važnu temu, ne opšti epic katalog
- i dalje ima vrednost kao širi product/architecture memo iza `Epic 13`
- dobar je kao objašnjenje "zašto" i "u kom smeru", dok `epics.md` ostaje kraći backlog dokument

Preporuka:

- ostaviti ga kao zaseban vision dokument
- držati ga u `docs/vision/` kao vision/product memo

### `docs/presentation/presentation.md`

Status: verovatno zadržati, ali kao supporting artifact.

Zašto:

- nije planski dokument i nije backlog dokument
- koristan je za stakeholder prezentacije, demo narativ i positioning
- ne pomaže direktno dnevnom upravljanju backlog-om, ali jeste koristan poslovni artefakt

Preporuka:

- zadržati ga ako i dalje postoji potreba za prezentovanjem Semantre
- ako prestane da se koristi, može kasnije da se arhivira
- ako ostaje aktivan, prirodnije mu je mesto u `docs/presentation/` nego u `project_docs/`

## Trenutna preporučena granica

U `project_docs/` držati samo ove dokumente:

- plan
- epics
- implementation checklists
- completed slices

Van `project_docs/` za sada ostaviti:

- `docs/pilot/` dokumente
- `docs/vision/` dokumente
- `docs/presentation/` i demo artefakte

To drži granicu čistom: `project_docs/` ostaje mesto za upravljanje projektom, a ostali dokumenti ostaju tematski ili izlazni artefakti.