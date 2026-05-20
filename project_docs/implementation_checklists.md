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

### Knowledge expansion i canonical coverage wave

Status: active planning accepted; SAP-first execution wave is the next structured knowledge expansion focus.

- [ ] Napraviti inventory svih postojećih SAP source artefakata i označiti koje izvore tretiramo kao authoritative za field-level knowledge refresh.
- [ ] Definisati staging/provenance format za vendor knowledge ingest (`system`, `module`, `object`, `field`, `description`, `source`, `source_type`, `public_or_internal`, `last_verified_at`).
- [ ] Napraviti SAP-first generated refresh put za knowledge sloj umesto ručnog masovnog editovanja `metadata_dict.csv`.
- [ ] Izvući SAP canonical-gap candidate set i razdvojiti vendor-specific field knowledge od stvarnih cross-system business concepts.
- [ ] Definisati SAP benchmark/eval slice-ove po domenima (`master data`, `FI/AP/AR`, `MM/SD`, `HR`) i KPI-jeve za coverage i mapping quality.
- [ ] Posle SAP pilot rezultata proširiti isti ingest/eval/promocija model na Workday, QAD i QuickBooks.
- [ ] Dokumentovati pravila za javno dostupne web/vendor spec izvore pre širenja na dodatne sisteme.

## Post-pilot hardening checkliste

### Mapping progress jobs

Status: current pilot hardening slice delivered; next phase is only future multi-process execution work.

- [x] Zadržati trenutni in-memory/thread job model za lokalni/pilot režim dok je opterećenje malo.
- [x] Uvesti SQLite-backed status/progress backend uz isti `start / poll / cancel` API contract i lokalni thread-backed execution model.
- [x] Dodati TTL cleanup i operativne limite za aktivne/završene jobove.
- [x] Definisati cancel/retry semantiku ako batch i duži run-ovi uđu u scope.
- [ ] Uvoditi lease/dequeue ili spoljašnji broker tek kada cross-process execution stvarno postane potreban.

### SQLite read/write normalization

Status: ciljane governance/discovery i canonical-runtime normalizacije su isporučene za trenutni pilot scope.

- [x] Normalizovati samo one SQLite read/write modele koji su već dokazano potrebni za governance i discovery.
- [x] Razdvojiti canonical authoring sync od full metadata reseed puta za glossary import i overlay-promotion authoring tokove.
- [x] Uvesti uske repository slojeve za stewardship queue, catalog discovery, mapping-set governance i knowledge runtime snapshot pristup.
- [ ] Širiti normalizaciju dalje samo kada nove discovery/governance površine pokažu da je to stvarno potrebno.
