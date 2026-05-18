# Semantra Implementation Checklists

Ovaj dokument je primarno mesto za izvršni redosled aktivnog rada.

Drži samo aktivne ili neposredno relevantne izvršne checkliste.

Ne koristi se za:

- istoriju isporuke
- opšti backlog pregled
- snapshot opis trenutnog stanja

Za to služe `completed_slices.md`, `epics.md` i `current_state.md`.

## Aktivne checkliste

Poslednji završen execution wave:

- `Run0518` je prebačen u `completed_slices.md` da ovaj dokument ostane fokusiran na aktivne i neposredno sledeće checkliste.

## Post-pilot hardening checkliste

### Mapping progress jobs

Status: future hardening after completed local pilot slice.

- [x] Zadržati trenutni in-memory/thread job model za lokalni/pilot režim dok je opterećenje malo.
- [ ] Pre multi-user ili dužeg execution režima planirati persistent queue/status backend.
- [x] Dodati TTL cleanup i operativne limite za aktivne/završene jobove.
- [x] Definisati cancel/retry semantiku ako batch i duži run-ovi uđu u scope.

### SQLite read/write normalization

Status: future hardening.

- [ ] Normalizovati samo one SQLite read/write modele koji su već dokazano potrebni za governance i discovery.
