# Full Menu Presentation Speaker Notes

Ovaj dokument je kratka speaker-notes verzija za [docs/pilot/FULL_MENU_PRESENTATION_SCENARIO.md](D:/py_radno/Semantra/docs/pilot/FULL_MENU_PRESENTATION_SCENARIO.md).

Namenjen je za slucaj kada hoces da pricas uz slajdove bez duzeg citanja glavnog scenario dokumenta. Svaki slajd ima kratak govorni blok koji mozes da izgovoris za 20 do 40 sekundi.

## 1. Naslov i problem

Semantra nije samo alat za mapiranje kolona. To je kompletan radni i governance sistem za data integration, od pripreme i review-a do benchmark merenja, runtime kontrole i stewardship odluka. Poenta prve poruke je da publika odmah vidi da je proizvod siri od jednog mapping ekrana.

## 2. Navigaciona mapa

Na vrhu aplikacije postoji pet glavnih zona: `Workspace`, `Catalog`, `Benchmarks`, `System` i `Governance`. `Workspace` je analyst radni tok, `Catalog` reuse i discovery sloj, `Benchmarks` quality evidence, `System` runtime observability, a `Governance` steward konzola. Time publika odmah dobija mentalni model cele aplikacije.

## 3. Workspace -> Setup

`Setup` je mesto gde pocinje rad sa podacima. Ovde korisnik bira da li radi standardni two-file mapping ili canonical-only tok, i ovde sistem tumaci da li je fajl row data ili schema spec. Poruka za publiku je da Semantra pokriva i ingestion i pravilno citanje inputa, a ne samo kasniji review.

## 4. Workspace -> Review

`Review` je analyst-centered trust layer. Tu se vide kandidati, coverage, knowledge i LLM signali, kao i review prioritizacija kroz queue plan. Bitno je naglasiti da LLM ovde nije autopilot, nego bounded pomocni sloj koji podrzava review odluke.

## 5. Workspace -> Decisions

`Decisions` je prelaz iz review-a u trajne ili polutrajne odluke. Tu se cuvaju manual overrides, import/export stanja, mapping set verzije, draft sessions i correction tokovi. Glavna poruka je continuity rada: tim ne gubi odluke ni kontekst kada prekine sesiju.

## 6. Workspace -> Output

`Output` pretvara aktivni mapping state u razvojne artefakte. Iz istog radnog stanja mogu da nastanu preview, Pandas, PySpark ili dbt izlazi, plus refinement kada je potreban. Ovim pokazujes da Semantra zatvara puni krug od inputa do tehnickog handoff-a.

## 7. Catalog -> Search and Discovery

`Catalog` je reuse i discovery biblioteka integracionog znanja. Pretraga radi po sistemima, domenu, statusu, owner-u i canonical signalima, pa korisnik ne mora da krece od nule. Publika treba da razume da je ovo akcioni katalog, ne pasivna arhiva.

## 8. Catalog -> Detail, Diff, Reuse i Handoff

Kada otvorimo konkretan asset, `Catalog` postaje ulaz u sledeci korak rada. Iz njega mozemo da uradimo reuse u `Workspace`, diff handoff u `Workspace Review` ili governance handoff u `Stewardship`. Najvaznija poruka je da catalog vodi korisnika dalje, umesto da ga zaustavi na read-only pregledu.

## 9. Benchmarks -> Dataset and Run Management

`Benchmarks` pocinju od cuvanja mapping stanja kao benchmark dataset-a i od ucitavanja prethodnih run-ova. To znaci da evaluacija nije jednokratna demonstracija, vec trajni kvalitetni signal koji tim moze da prati kroz vreme. Time publika vidi da postoji quality baseline, a ne samo subjektivni review.

## 10. Benchmarks -> Profile Comparison and Explanation

Kada benchmark dataset postoji, mozemo da uporedimo vise scoring profila i da dobijemo preporuceni default. Posle toga explanation prevodi metrike u razumljiv poslovni razlog, rizike i sledece korake. Poruka ovde je: sistem ne daje samo broj, vec i objasnjenje preporuke.

## 11. System -> Admin

`System -> Admin` je runtime administracija. Tu se ucitava runtime config, vide saved corrections i benchmark runs, i menja aktivni scoring profil za nove mapping prolaze. Naglasi da ovo nije analyst ekran, nego operativna kontrolna tabla za sistemsko ponasanje.

## 12. System -> Debug

`System -> Debug` je observability povrsina. Tu se vide decision logs, aktivni knowledge runtime, audit log i canonical coverage/debug insighte nad trenutnim mapping stanjem. Poenta je transparentnost i troubleshooting, ne svakodnevni poslovni rad.

## 13. Governance overview

`Governance` je steward konzola sa cetiri sekcije: `Canonical`, `Knowledge`, `Overlays & Runtime` i `Stewardship`. Ovaj slajd sluzi da publika shvati da governance nije jedan ekran, vec vise specijalizovanih odgovornosti nad istim znanjem.

## 14. Governance -> Canonical

`Canonical` je stabilni glossary sloj. Tu se upravlja canonical konceptima, aliasima, coverage kontekstom i promotion-ready signalima. Naglasi da promene ovde imaju dugorocan efekat i zato su stroze upravljane nego u operational sloju.

## 15. Governance -> Knowledge

`Knowledge` cuva radni registry pojmova blizih stvarnim integracionim izrazima. On povezuje operativno znanje sa canonical slojem i omogucava postepen prelaz iz fleksibilnog znanja ka stabilnijoj strukturi. Publika treba da vidi da knowledge i canonical nisu ista stvar.

## 16. Governance -> Overlays & Runtime

`Overlays & Runtime` sluzi za kontrolisane i reverzibilne promene znanja koje uticu na runtime bez direktnog menjanja stabilnog glossarya. Ovo je brz i bezbedan eksperimentalni sloj koji ipak ostaje auditabilan. Time objasnjavas kako sistem balansira stabilnost i agilnost.

## 17. Governance -> Stewardship

`Stewardship` je radna lista governance follow-up stavki. Tu steward vidi gapove, review note, queue statuse i odluke za promotion, reject ili ignore. Ovo je mesto gde signal iz operativnog rada postaje trajna, auditabilna governance odluka.

## Zavrsni slajd

Zakljucak prezentacije je da Semantra pokriva ceo zivotni ciklus: ingestion, review, decisions, output, reuse, benchmark evidence, runtime kontrolu i governance upravljanje znanjem. Ako hoces jednu zavrsnu recenicu, koristi: `Semantra povezuje analyst rad, quality evidence i steward odluke u jedinstven operativni tok.`