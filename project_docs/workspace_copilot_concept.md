 # Workspace Copilot Concept

Ovaj dokument spaja dva bliska product predloga u jedan pregledni artefakt:

1. konkretan `Workspace Copilot` UX i interaction model
2. tehničku mapu kako da se postojeće bounded guidance / refinement capability-je objedine bez većeg backend refaktora

Cilj nije da se Semantra pretvori u generički chat interfejs, nego da `LLM` bude stalno dostupan unutar istog analyst workflow-a tako da korisnik ne mora da copy/paste-uje mapping, warning, code ili pitanja u eksterni alat.

## 1. Product Goal

`Workspace Copilot` treba da bude stalno dostupan sloj unutar glavnog `Workspace` toka koji:

- uvek zna gde se korisnik nalazi (`Setup`, `Review`, `Decisions`, `Output`)
- uvek zna koji je trenutni radni kontekst (upload pair, target intent/profile, filteri, aktivne odluke, preview/codegen stanje)
- nudi kontekstualne `ask + act` akcije iz istog mesta
- ne radi auto-apply, auto-approval ni skriveno prepisivanje state-a
- koristi postojeće bounded capability-je umesto novog nedefinisanog agent layer-a

Najkraće: korisnik ne treba da zna koji panel da otvori da bi pitao `šta je problem`, `šta dalje`, `koji je sigurniji target`, `zašto je codegen blokiran`, ili `kako da popravim ovaj artifact`.

## 2. UX Proposal

### 2.1. Glavna forma

Predlog je jedan stalno vidljiv desni sidebar ili desni slide-over panel sa naslovom `Workspace Copilot`.

Panel bi imao tri stabilna bloka:

1. `Context`
2. `Ask`
3. `Actions`

To je namerno manje odvojeno od današnjih panela. Korisnik ne bira između pet LLM funkcija unapred; prvo vidi gde je, zatim pita ili bira sledeću akciju.

### 2.2. Context blok

`Context` treba da bude read-only i uvek vidljiv.

Treba da prikazuje:

- aktivni top-level area i `Workspace` section
- source/target dataset ili canonical target intent/profile
- broj aktivnih odluka, open review items i pending LLM proposals
- aktivni red ili fokusirani source kada postoji
- preview/codegen/refinement status kada postoji
- LLM runtime status (`reachable`, `unreachable`, `misconfigured`, `disabled`)

Poenta ovog bloka je da korisnik ne gubi osećaj `na čemu AI trenutno radi`.

### 2.3. Ask blok

`Ask` blok je jedan kompaktan prompt input sa nekoliko section-aware prečica ispod njega.

Ne treba da bude open-ended "pričaj sa modelom o bilo čemu". Treba da šalje bounded zahteve iz postojećeg produkta.

Predložene quick actions po section-u:

`Setup`

- `Should I enable LLM validation here?`
- `Explain upload/mode choice`
- `What metadata would improve this run?`

`Review`

- `Explain this row`
- `Suggest safer target`
- `Why is confidence low?`
- `What should I review first?`
- `Summarize current mapping state`

`Decisions`

- `Summarize pending risks`
- `Which proposals are safe to apply?`
- `What changed from the suggested mapping?`
- `Draft correction note`

`Output`

- `Why is codegen blocked?`
- `Explain preview warning`
- `Suggest safer transformation`
- `Refine this artifact`

Važno ograničenje:

- svaki quick action mora da mapira na postojeću bounded funkciju ili jasno definisan lokalni payload
- nema generičkog slobodnog odgovora bez aktivnog Workspace konteksta

### 2.4. Actions blok

`Actions` blok ne treba da bude samo tekstualni odgovor. Treba da prikazuje akcije koje odgovaraju trenutnom pitanju i section-u.

Primeri:

Ako je korisnik u `Review` i pita `What should I review first?`, panel treba da vrati:

- kratak odgovor
- `Run / Refresh Review Queue Plan`
- `Generate LLM Decision Proposals`
- `Open current low-confidence rows`

Ako je korisnik u `Output` i pita `Why is codegen blocked?`, panel treba da vrati:

- block reason
- listu redova/statusa koji ga drže blokiranim
- `Jump to Decisions`
- `Jump to row in Review`

Ako je korisnik u `Output` i pita `Refine this artifact`, panel treba da vrati:

- formu za instruction / edge cases / reference excerpt
- dugme `Run refinement`
- rezultat u side-by-side modu
- `Accept refined version` / `Discard refinement`

### 2.5. Odgovor modela

Odgovor treba standardizovati u tri dela:

1. `Answer`
2. `Why`
3. `Next actions`

Primer:

- `Answer`: `Code generation is blocked because one active mapping decision is still needs_review.`
- `Why`: `The accepted-only governance gate checks active review statuses before Pandas, PySpark, and dbt generation.`
- `Next actions`: `Change phone -> phone_number to accepted` / `Open Decisions` / `Open Review row`

Ovo je namerno više operator assistant nego open chat.

## 3. Interaction Model by Workflow Step

### 3.1. Setup

Cilj u `Setup` nije duboko reasoning-as-a-service, nego ubrzanje pravilnog starta.

Copilot ovde treba da pomaže sa:

- izborom `Standard` vs `Canonical`
- objašnjenjem kada vredi uključiti `Use LLM validation`
- preporukom za metadata enrichment (`source companion`, `target companion`)
- objašnjenjem target intent/profile u canonical toku

Ograničenje:

- dok mapping još ne postoji, copilot ne treba da glumi da zna red-level stanje
- fokus je guidance pre prvog generate koraka

### 3.2. Review

Ovo je glavni centar vrednosti.

Copilot u `Review` treba da objedini:

- `Mapping Analysis Overview`
- `Review Queue Plan`
- `Gap Queue Summary`
- batch `LLM Mapping Refine`
- per-row `Preview LLM refine`
- `LLM Decision Proposals` generation

To je već implementirano, ali danas u više odvojenih panela.

Copilot shell bi ovde trebalo da radi kao jedan orkestrator nad tim capability-jima.

### 3.3. Decisions

Copilot u `Decisions` ne treba da menja odluke direktno bez korisnika. Njegov posao je da skrati put do bounded apply tokova.

Treba da nudi:

- pregled `pending LLM proposals`
- objašnjenje `safe_to_apply` logike
- `Apply safe proposals`
- `Apply selected proposal`
- `Dismiss selected proposal`
- sažetak ručnih override-a i posledica po output governance
- draft correction note kada postoje pending corrections

### 3.4. Output

Copilot u `Output` treba da objedini tri stvari koje su danas odvojene:

- preview / codegen gating explanation
- transformation/codegen warning explanation
- artifact refinement

Najvažniji UX dobitak ovde je da korisnik ne mora da prelazi između preview warnings, generated code i refinement forme kao odvojene mentalne celine.

## 4. Technical Proposal Without Major Backend Refactor

Prvi slice treba da bude UI orchestration layer, ne novi backend AI subsystem.

To znači:

- zadržati postojeće endpoint-e i bounded contracts
- dodati jedan UI dispatcher koji na osnovu aktivnog section-a i pitanja bira postojeću capability funkciju
- koristiti postojeći `st.session_state` kao glavni source konteksta
- dodati samo tanki adapter sloj za unified sidebar rendering

## 5. Existing Capability Map

### 5.1. Setup and initial mapping

Postojeće capability-je koje copilot može odmah da koristi:

- `Use LLM validation` toggle u `streamlit_ui/workspace_views.py`
- LLM runtime reachability u `streamlit_ui/shared_views.py`
- target intent/profile state iz `upload_response` i session state-a

Ovo nije pun LLM assistant sloj, ali jeste dovoljan ulaz za section-aware setup guidance.

### 5.2. Review guidance and refinement

Postojeći capability-ji:

- `request_llm_mapping_refinement()` u `streamlit_ui/api.py`
- batch `LLM Mapping Refine` u `streamlit_ui/workspace_review_views.py`
- per-row `Preview LLM refine` u `streamlit_ui/workspace_review_views.py`
- `request_mapping_analysis_summary()` u `streamlit_ui/api.py`
- `request_review_plan_summary()` u `streamlit_ui/api.py`
- `request_mapping_analysis_narration()` i `request_mapping_analysis_audio()` u `streamlit_ui/api.py`
- `LLM Decision Proposals` generation u `streamlit_ui/workspace_review_views.py`

To znači da najveći deo `Review copilot` vrednosti već postoji i može da se izvuče u zajednički shell bez novog backend endpoint-a.

### 5.3. Decisions and proposal apply

Postojeći capability-ji:

- `Apply safe proposals`
- `Apply selected proposal`
- `Dismiss selected proposal`
- decision-origin surfacing (`manual_mapping`, `llm_proposal`)

To znači da `Decisions copilot` može da bude tanak komandni sloj nad postojećim apply/dismiss tokovima.

### 5.4. Output and artifact refinement

Postojeći capability-ji:

- preview/codegen block reason računanje u `streamlit_ui/workspace_views.py`
- generated artifact warnings surfacing u `streamlit_ui/workspace_views.py`
- `POST /mapping/codegen/refine` kroz postojeći Output UI
- `Accept refined version` / `Discard refinement`

To znači da `Output copilot` može odmah da radi kao objedinjeni explanation + refinement shell, bez backend promene.

## 6. Minimal UI Composition

Prvi slice može da se uradi sa četiri interna režima unutar istog sidebar-a:

1. `Overview`
2. `Row help`
3. `Decision help`
4. `Output help`

Režim može da se bira automatski po section-u, uz ručno prebacivanje kada je potrebno.

Predlog ponašanja:

- ako nema mapping state-a: prikaži `Setup guidance`
- ako postoji aktivni source focus: prikaži `Row help`
- ako postoje pending proposals ili override-i: prikaži `Decision help`
- ako postoji preview/codegen state: prikaži `Output help`

## 7. What Can Be Reused As-Is

Bez većeg backend refaktora odmah se mogu reuse-ovati:

- session context (`upload_response`, `mapping_response`, `mapping_editor_state`, `llm_decision_proposals`, `preview_response`, `codegen_response`, `codegen_refinement_response`)
- bounded request funkcije iz `streamlit_ui/api.py`
- postojeći apply/dismiss handlers u `streamlit_ui/workspace_decision_views.py`
- postojeći output refinement workflow u `streamlit_ui/workspace_views.py`
- runtime status i sidebar operations strip u `streamlit_ui/shared_views.py`

## 8. What Still Needs Thin Adapter Work

Za prvi pravi `Workspace Copilot` slice ipak treba nekoliko tankih adaptera:

- unified sidebar state model koji zna section, selected source, current filters i last generated guidance output
- jedan dispatcher koji mapira quick action -> postojeća funkcija -> standardizovan odgovor
- jump/focus helper koji otvara odgovarajući `Workspace` section i fokusira relevantan source row kada je odgovor vezan za konkretan field
- standardizovan response shape (`answer`, `why`, `next_actions`, optional `artifacts`)
- mala kompozicija oko postojećih forms/inputa da `Refine with LLM` i slične akcije mogu da žive i u sidebar-u, ne samo u glavnom panelu

Ovo je UI composition posao, ne novi AI runtime sloj.

## 9. What Should Not Be Done In The First Slice

Ne uvoditi odmah:

- generički free-form chat endpoint bez jasnog bounded contract-a
- auto-apply odluka ili refinement-a
- background multi-step agent koji sam šeta kroz `Review`, `Decisions` i `Output`
- paralelni memory/chat transcript sistem koji postaje drugi source of truth pored workspace state-a
- novu backend orkestraciju samo da bi se postojeći paneli preimenovali u chat

## 10. Recommended Execution Order

### Slice A: UX shell

- dodati stalni `Workspace Copilot` container
- prikazati `Context` + quick actions + runtime state
- bez generičkog prompt inputa u prvoj iteraciji

### Slice B: Review unification

- povezati `Mapping Analysis Overview`, `Review Queue Plan`, row refine i proposal generation u jedan copilot surface
- dodati row-aware `Explain this row` i `Suggest safer target`

### Slice C: Decisions and Output actions

- povezati proposal apply/dismiss i output gating explanation
- povezati artifact refinement u isti shell

### Slice D: optional freeform prompt

Tek posle toga ima smisla dodati jednu bounded freeform prompt površinu koja i dalje radi samo nad aktivnim Workspace kontekstom i samo nad dozvoljenim capability-jima.

## 11. Product Decision Summary

Ako je cilj da `LLM` bude stalno dostupan i da poveća efikasnost bez izbacivanja korisnika iz aplikacije, onda sledeći korak nije dodavanje još jednog novog LLM capability-ja.

Sledeći korak je da se već postojeće bounded capability-je objedine u jedan `Workspace Copilot` shell.

Drugim rečima:

- capability coverage je već dovoljno široka
- UX orchestration još nije
- najveći dobitak je u unifikaciji, ne u još jednom endpoint-u

## 12. First Slice Implementation Checklist

Ovo je konkretan prvi execution paket za `Workspace Copilot`. Namerno je uzak: ne pokušava da spoji sve `LLM` surface-e odjednom, nego da isporuči prvi stalno dostupan shell koji je odmah koristan i ne traži veći backend refaktor.

### 12.1. Scope

Prvi slice treba da isporuči:

- stalni `Workspace Copilot` shell unutar `Workspace`
- `Context` blok sa aktivnim workflow signalima
- section-aware quick actions bez generičkog freeform chata
- minimalni dispatcher koji poziva postojeće bounded capability-je
- prvi korisni podskup akcija za `Review`, `Decisions` i `Output`

Prvi slice ne treba da isporuči:

- novi backend orchestration servis
- auto-apply bilo čega
- punu cross-surface podršku za `Catalog`, `Benchmarks` i `Governance`
- novi transcript/memory sistem
- slobodan prompt koji izlazi van aktivnog Workspace konteksta

### 12.2. Suggested File Surface

Predloženi minimalni fajl-sloj:

- `streamlit_ui/workspace_copilot_views.py`
Za novi shell, rendering `Context` / `Ask` / `Actions`, i kompoziciju quick action rezultata.

- `streamlit_ui/workspace_copilot_state.py`
Za izračunavanje read-only copilot context-a iz `st.session_state`, active section-a, selected source-a, preview/codegen state-a i pending proposal-a.

- `streamlit_ui/workspace_copilot_actions.py`
Za tanki dispatcher: quick action -> postojeća capability funkcija -> standardizovan rezultat.

- `streamlit_ui/workspace_views.py`
Za mount-ovanje copilot shell-a u `Workspace` layout i prosleđivanje postojećih handler-a / request funkcija.

- `streamlit_ui/api.py`
Bez novih velikih endpoint-a; samo reuse postojećih request helper-a i eventualno tanki wrapper kada neka capability još nema pogodnu UI entry funkciju.

- `tests/test_streamlit_workspace_copilot_state.py`
Za context model i section-aware state rezoluciju.

- `tests/test_streamlit_workspace_copilot_actions.py`
Za dispatcher ponašanje i bounded action mapu.

- `tests/test_streamlit_workspace_views.py`
Za mount/regression proveru da novi shell ne lomi postojeći `Workspace` flow.

### 12.3. Execution Checklist

#### A. Scope freeze

- [ ] Potvrditi da prvi slice ostaje `Workspace-only` i ne uvodi novi top-level tab.
- [ ] Zaključati prvu listu supported quick action-a na najviše 6-8 akcija.
- [ ] Ostaviti `Catalog`, `Benchmarks` i `Governance` van prve iteracije, osim eventualnog read-only future stub copy-ja.

#### B. Context model

- [ ] Napraviti jedan `Workspace Copilot Context` shape koji sadrži:
	- aktivni `Workspace` section
	- source/target ili canonical target intent/profile
	- active decisions count
	- open review items count
	- pending LLM proposals count
	- selected/focused source ako postoji
	- preview/codegen/refinement status ako postoji
	- LLM runtime status
- [ ] Obavezno držati ovaj shape read-only; copilot context ne sme postati drugi source of truth.
- [ ] Context model mora da radi i kada postoji samo upload state, bez mapping response-a.

#### C. Shell rendering

- [ ] Dodati stalni `Workspace Copilot` container u `Workspace` layout.
- [ ] Prikazati `Context`, `Ask`, `Actions` blokove u stabilnom redosledu.
- [ ] `Ask` u prvoj iteraciji raditi kroz quick action dugmad i kratke instruction inpute samo tamo gde već postoje bounded forme.
- [ ] Jasno prikazati da je runtime `LLM` reachable / unavailable, bez skrivene degradacije.

#### D. First quick-action set

Prva iteracija treba da podrži samo ovaj skup:

- [ ] `Review`: `Summarize current mapping state`
- [ ] `Review`: `What should I review first?`
- [ ] `Review`: `Generate proposals for current review slice`
- [ ] `Decisions`: `Which proposals are safe to apply?`
- [ ] `Output`: `Why is codegen blocked?`
- [ ] `Output`: `Refine this artifact`

Ovo je dovoljno da copilot odmah bude koristan, a i dalje ostaje bounded.

#### E. Dispatcher wiring

- [ ] Mapirati `Summarize current mapping state` na postojeći `Mapping Analysis Overview` flow.
- [ ] Mapirati `What should I review first?` na postojeći `Review Queue Plan` flow.
- [ ] Mapirati `Generate proposals for current review slice` na postojeći `LLM Decision Proposals` generation flow.
- [ ] Mapirati `Which proposals are safe to apply?` na postojeći proposal summary + apply surface bez auto-apply ponašanja.
- [ ] Mapirati `Why is codegen blocked?` na postojeći Output gating razlog i aktivne review statuse.
- [ ] Mapirati `Refine this artifact` na postojeći `Refine with LLM` workflow sa instruction/edge-case/reference inputima.

#### F. Response shape standardization

- [ ] Uvesti jedan mali rezultat shape za copilot odgovor:
	- `answer`
	- `why`
	- `next_actions`
	- `artifacts` opcionalno
- [ ] Ne uvoditi poseban novi rich backend response contract; standardizacija treba da bude UI-level adaptacija nad postojećim payload-ima.
- [ ] Ako capability vrati fallback ili locked stanje, copilot odgovor mora to eksplicitno da kaže umesto da glumi pun uspeh.

#### G. Action execution behavior

- [ ] Nijedna quick action u prvom slice-u ne sme da uradi auto-apply decision, auto-accept refinement ili auto-navigation bez jasnog korisničkog klika.
- [ ] `Refine this artifact` sme da generiše refinement candidate, ali `Accept refined version` i dalje mora da ostane eksplicitna odluka korisnika.
- [ ] `Which proposals are safe to apply?` sme da objasni i ponudi `Apply safe proposals`, ali ne sme da ga pokreće sam.

#### H. Navigation and focus helpers

- [ ] Dodati tanki helper za `Jump to Review`, `Jump to Decisions`, `Jump to Output` kada je odgovor vezan za drugi section.
- [ ] Ako postoji row-aware odgovor, pomoći fokus kroz `pending_workspace_section` i source focus state umesto ručnog skrolovanja gde je moguće.
- [ ] Ne uvoditi novi global navigation model; reuse postojećeg handoff mehanizma.

#### I. Validation and regression

- [ ] Unit-testovati context shape za najmanje ova stanja:
	- upload-only
	- mapping-ready review state
	- decisions state with pending proposals
	- output state with codegen response
- [ ] Unit-testovati dispatcher mapu za svaku prvu quick action rutu.
- [ ] Unit-testovati locked/unavailable behavior kada mapping, preview ili codegen state ne postoji.
- [ ] Browser-potvrditi da `Workspace Copilot` ne lomi postojeći `Setup -> Review -> Decisions -> Output` flow.
- [ ] Browser-potvrditi da `Why is codegen blocked?` u copilot shell-u daje isti razlog kao postojeći Output caption.
- [ ] Browser-potvrditi da `Refine this artifact` iz copilot shell-a prolazi isti `candidate -> accept/discard` contract kao postojeći Output panel.

### 12.4. Acceptance Criteria

Prvi slice je završen kada važi sledeće:

- korisnik ima stalno vidljiv `Workspace Copilot` shell unutar `Workspace`
- shell uvek prikazuje tačan aktivni context bez dodatnog ručnog unosa
- najmanje 6 definisanih quick action-a rade nad postojećim capability-jima
- nijedna akcija ne izlazi iz bounded product contract-a
- nijedna akcija ne uvodi auto-apply ili auto-approval
- shell ne lomi postojeće browser-potvrđene Workspace tokove
- fallback i runtime-unavailable stanja su jasna i ne zvuče kao tiha greška

### 12.5. Out of Scope for the Next Slice

Ako prvi slice prođe, tek sledeći execution paket ima smisla za:

- row-aware `Explain this row` sa boljim fokus handoff-om
- `Suggest safer target` kao direktan copilot ulaz u per-row `LLM refine`
- `Draft correction note` i srodne Decisions pomoćne forme
- canonical-gap copilot surfacing
- bounded freeform prompt nad aktivnim Workspace kontekstom

Drugim rečima, prvi slice treba da dokaže da objedinjeni shell zaista podiže efikasnost pre nego što se širi u puniji assistant surface.
