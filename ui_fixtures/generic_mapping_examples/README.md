# Generic Mapping Example Fixtures

Ovaj direktorijum sadrži dva uzorka za Semantra upload:

1. **Row-data primer** sa generičkim imenima kolona `col_1`..`col_5` i zasebnim opisima kolona.
2. **Schema-only primer** u kome nema redovnih podataka, pa se značenje mora zaključiti isključivo iz opisa.

Datoteke:

- `row_data_source.csv`
- `row_data_target.csv`
- `row_data_source_description.txt`
- `row_data_target_description.txt`
- `row_data_source_companion.csv`
- `row_data_target_companion.csv`
- `schema_source_spec.csv`
- `schema_target_spec.csv`
- `schema_source_description.txt`
- `schema_target_description.txt`
- `schema_source_companion.csv`
- `schema_target_companion.csv`

Korišćenje:

- Za prvi primer, koristite `row_data_source.csv` i `row_data_target.csv` kao primarne upload fajlove.
- Ako želite da obogatite upload opisima i deklarisanim tipovima, priložite `row_data_source_companion.csv` i/ili `row_data_target_companion.csv` kao companion metadata fajlove.
- Za schema-only primer, koristite `schema_source_spec.csv` i `schema_target_spec.csv` kao schema-spec ulaze.
- Companion schema fajlovi `schema_source_companion.csv` i `schema_target_companion.csv` služe kao dodatni opisni sloj za kolone kada u samom schema-spec uploadu želite jasnije deklarisane tipove i uzorke.

Napomena:

- Companion CSV fajlovi treba da imaju kolone `Column`, `Description`, `Type`, i opcionalno `Sample Values`.
- Ovaj format je kompatibilan sa Semantra `/upload/handle/metadata` companion metadata tokovima.
