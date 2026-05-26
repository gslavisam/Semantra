# Catalog Window Use Case

## Svrha

Ovaj use case objašnjava kako se koristi Catalog prozor u realnom BA/Integration toku, šta je očekivani izlaz po koraku i koju poslovnu vrednost Catalog donosi.

Catalog u Semantra nije pasivna lista metapodataka. To je operativni discovery i handoff sloj izmedju istorijski odobrenih mapping artefakata i aktivnog Workspace review toka.

## Kada koristimo Catalog

Catalog koristiš kada želiš da odgovoriš na pitanja:

- Da li već postoji slična ili ista integracija koju možemo da reuse-ujemo?
- Koja approved verzija je najbolja polazna tačka?
- Koji canonical koncepti su već stabilni, a gde su razlike/rizici?
- Kako najbrže prebaciti fokus na "needs_review" redove iz relevantnog reuse konteksta?

## Primarni korisnici

- Business Analyst (BA)
- Integration Lead
- Governance reviewer

## Preduslovi

- Postoje sačuvani mapping set-ovi u sistemu.
- Barem deo artefakata je u statusu `approved` (za shortlist/reuse vrednost).
- Workspace može biti učitan, ali nije obavezno za osnovni discovery.

## Glavni scenario (end-to-end)

1. Otvori Catalog i učitaj rezultate (`Load all integrations` ili search/filter).
2. Pregledaj Integration Results tabelu da vidiš status, canonical footprint i `next_action` signal.
3. U panelu `Workspace Reuse Shortlist` klikni `Generate workspace shortlist`.
4. Sistem rangira approved kandidate deterministički (concept overlap, system/domain match, quality proxy).
5. Izaberi top kandidata i otvori:
- `Open shortlisted integration` za širi lineage kontekst.
- `Open shortlisted version` za verziju koju želiš da porediš/reuse-uješ.
- `Open review focus` za direktan handoff u Workspace Review sa prefilled filterima.
6. U panelu `Integration Pair Compare` uporedi base vs peer integraciju kada postoji dilema između dva kandidata.
7. U Workspace Review nastavi rad samo na najrelevantnijem slice-u (`needs_review` + canonical concept fokus).

## Šta dobijamo kao izlaz

- Kratku listu najboljih reuse kandidata umesto ručnog prolaska kroz sve verzije.
- Objašnjiv score breakdown po kandidatu.
- Brži prelaz iz discovery faze u review akciju (deep-link handoff).
- Manje rizika da se krene od pogrešne integracione linije.

## Poslovna vrednost

1. Brže donošenje odluke o reuse-u
- BA tim ne troši vreme na ručno pretraživanje celog istorijata.

2. Veća konzistentnost između projekata
- Reuse ide iz approved artefakata i canonical poklapanja, ne iz ad-hoc procene.

3. Niži operativni rizik
- Compare i governance signali smanjuju chance da se preskoče konceptualne razlike.

4. Fokus na stvarni review workload
- Deep-link handoff vodi direktno na redove koji traže odluku, umesto na generičan pregled.

## Kako merimo uspeh (predlog KPI)

- Time-to-first-reusable-candidate (min)
- Udeo mapping set-ova koji kreću iz approved reuse baseline-a
- Smanjenje broja ručnih korekcija nakon reuse starta
- Review throughput nad `needs_review` redovima po sesiji

## Scope i ograničenja

- Shortlist je action-based: rezultat postoji tek nakon klika na `Generate workspace shortlist`.
- Shortlist rangira approved integracije; draft/review redovi nisu reuse baseline.
- Catalog radi nad sačuvanim artefaktima (persisted), ne nad prolaznim live state-om.

## Kratki narativ za demo

"U Catalog-u ne tražimo samo podatke, već najbolju početnu tačku. Za jedan klik dobijamo rangiranu listu approved kandidata, odmah uporedimo dve najrelevantnije integracije, i iz istog ekrana pređemo u Workspace Review sa već podešenim fokusom na redove koji traže odluku. Time skraćujemo discovery fazu i povećavamo kvalitet reuse odluka." 