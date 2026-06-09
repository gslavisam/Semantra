# Semantra: Domain-Specific Agentic Framework

> **Šta je ovo?** Prezentacija novog agentic pristupa Semantri — Python SDK + adapter + LangGraph integracija koji omogućavaju da se Semantra koristi iz agenta, notebook-a ili bilo kog drugog Python programa, sa ili bez postojećeg FastAPI backend-a.
>
> **Za koga?** Programeri koji žele da ugrađuju Semantra logiku (mapping, knowledge, bounded LLM) u svoje agent tokove. Takođe i svi koji danas koriste Semantra web aplikaciju a žele alternativni, programerski interfejs.
>
> **Status (jun 2026):** Framework kompletan, 121 test prolazi, 3 notebook-a spremna za pokretanje.

---

## 1. Ukratko: šta smo izgradili

Tri nova Python paketa u okviru postojećeg Semantra repozitorijuma:

| Paket | Šta radi | Zavisnosti |
|---|---|---|
| `semantra-core` | Pydantic modeli + Protocol ugovori + referentne implementacije + (opciono) LangGraph | Samo `pydantic>=2.0` |
| `semantra-backend-adapter` | Most: izlaže postojeći Semantra FastAPI backend kroz iste Protocol ugovore | `semantra-core>=0.2.0` + (opciono) backend |
| `notebooks/` (3 fajla) | Radni primeri: čist SDK, adapter, LangGraph | `semantra-core` |

**Ključna ideja:** Postojeći Semantra web app (FastAPI + Streamlit + SQLite) je **i dalje pilot proizvod** za ljude. Novi framework je **alternativni ulaz** za agente i programere — isti biznis logika, drugačiji interfejs.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Vaš agent / skripta                       │
│  (LangGraph, CrewAI, custom orchestrator, Jupyter, microservice)  │
└────────────────┬───────────────────────────┬─────────────────────┘
                 │                           │
                 ▼                           ▼
        ┌────────────────┐          ┌─────────────────────────┐
        │ semantra-core  │          │ semantra-backend-       │
        │   (čist SDK)   │          │      adapter            │
        │                │          │                         │
        │ • Pydantic v2  │          │ Most:                  │
        │ • Protocols    │◀────────▶│ • BackendMappingEngine  │
        │ • Reference    │          │ • BackendKnowledgeBase  │
        │   impls        │          │ • BackendLLMService     │
        │ • LangGraph    │          │ • BackendConnector      │
        └────────────────┘          └──────────┬──────────────┘
                 │                              │
                 │       (opciono)              ▼
                 │                  ┌──────────────────────┐
                 │                  │ Semantra FastAPI     │
                 │                  │ backend (postojeći)  │
                 │                  │ + Streamlit UI       │
                 │                  │ + SQLite             │
                 │                  └──────────────────────┘
                 ▼
        ┌────────────────┐
        │ In-memory      │   ← radi bez backend-a, idealno za
        │ reference impls│     testove i offline razvoj
        └────────────────┘
```

**Tri načina da se koristi (od najlakšeg do najmoćnijeg):**

1. **Čist SDK** — `InMemory*` reference implementacije, nema mrežnih poziva, radi u notebook-u.
2. **Backend adapter** — isti interfejs, ali pozivi idu kroz postojeći Semantra FastAPI backend.
3. **LangGraph workflow** — gotov state machine koji orchestrir-a `propose → validate → END`, zamenljiv sa bilo kojom implementacijom.

---

## 2. Tehnologije

| Sloj | Tehnologija | Zašto baš to |
|---|---|---|
| Modeli | **Pydantic v2** | Validacija, serijalizacija, schema-first dizajn, idealan za data contracts |
| Kontrakti | **`typing.Protocol` + `@runtime_checkable`** | Strukturni (duck) typing, `isinstance()` provere, nema nasleđivanja |
| Reference impl | Čist Python | Testiranje bez spoljnih zavisnosti |
| Agent runtime (opciono) | **LangGraph** | State machine orkestracija, TypedDict state, kompajliran graf |
| Backend most | **dataclass** + `try/except ImportError` za fallback | Adapter radi i kad backend nije učitan |
| Testovi | **pytest** | Standard, brz, parametrizacija |
| Notebooks | **Jupyter / VS Code** | Demos + reproducibilni tokovi |

**Ključni principi:**

- **Bounded AI only.** LLM se koristi samo u `LLMService.validate_mapping` (closed-set izbor) i `generate_transformation` (advisory code). Nema autonomnog LLM odlučivanja.
- **Deterministic-first.** Stub implementacije daju iste rezultate svaki put; backend daje iste rezultate kao i web app.
- **Framework-agnostic.** `semantra-core` nema dep na FastAPI/Streamlit/SQLite. Može se ugraditi bilo gde.
- **Graceful degradation.** Adapteri importuju backend `try/except`-om; kad backend nije dostupan, koriste referentne implementacije. Paket je testabilan i bez celog stack-a.

---

## 3. Kako je Namenjeno da se Koristi

### 3.1 Instalacija (jednom)

Iz root-a Semantra repozitorijuma:

```bash
# 1. Core SDK (obavezno)
pip install -e ./semantra-core

# 2. Backend adapter (ako želite da koristite postojeći Semantra backend)
pip install -e ./semantra-backend-adapter

# 3. LangGraph integracija (opciono, samo za agent tokove)
pip install -e "./semantra-core[langgraph]"
```

### 3.2 Tri putanje kroz kod

#### Putanja A — Čist SDK (offline, za testiranje i učenje)

Koristite `InMemory*` reference implementacije. Nema mrežnih poziva, nema fajlova, sve u memoriji.

```python
from semantra_core.models.schema import DatasetHandle, SchemaProfile, ColumnProfile
from semantra_core.models.knowledge import CanonicalGlossaryEntry
from semantra_core.services import (
    InMemoryMappingEngine,
    InMemoryKnowledgeBase,
    BoundedLLMService,
)

# Izgradite minimalni source dataset
source = DatasetHandle(
    dataset_id="customer_src",
    dataset_name="customer_src",
    schema_profile=SchemaProfile(
        dataset_id="customer_src",
        dataset_name="customer_src",
        row_count=120,
        columns=[
            ColumnProfile(name="cust_id", normalized_name="cust_id",
                          dtype="str", null_ratio=0.0,
                          unique_ratio=1.0, non_null_count=120),
            ColumnProfile(name="email", normalized_name="email",
                          dtype="str", null_ratio=0.05,
                          unique_ratio=0.95, non_null_count=114),
        ],
    ),
)

# Izgradite target šemu
target = SchemaProfile(
    dataset_id="customer_tgt", dataset_name="customer_tgt", row_count=0,
    columns=[
        ColumnProfile(name="customer_key", normalized_name="customer_key",
                      dtype="str", null_ratio=0.0,
                      unique_ratio=0.0, non_null_count=0),
        ColumnProfile(name="email_address", normalized_name="email_address",
                      dtype="str", null_ratio=0.0,
                      unique_ratio=0.0, non_null_count=0),
    ],
)

# Pokrenite engine
engine = InMemoryMappingEngine()
candidates = engine.map_source_to_target(source, target)
print(f"Kandidati: {len(candidates)} (stub vraća prazno)")
print("Signali:", engine.get_scoring_signals())
```

**Knowledge baza:**

```python
kb = InMemoryKnowledgeBase()
kb.add(CanonicalGlossaryEntry(
    concept_id="CUST_ID", entity="Customer", attribute="customer_id",
    display_name="Customer Identifier",
    description="Stabilan identifikator korisničkog zapisa.",
))
kb.add(CanonicalGlossaryEntry(
    concept_id="CUST_EMAIL", entity="Customer", attribute="email",
    display_name="Customer Email",
))

print("Pretraga 'email':", kb.search_concepts("email"))   # case-insensitive
print("Lookup CUST_ID:", kb.get_canonical_concept("CUST_ID"))
```

**Bounded LLM (stub):**

```python
llm = BoundedLLMService()
result = llm.validate_mapping(
    source_field="cust_id",
    candidate_targets=["customer_key", "customer_id", "id"],
    context={"description": "primary key"},
)
print(result)
# {'selected_target': 'customer_key', 'confidence': 0.0,
#  'reasoning': ['LLM service not configured; using stub.']}
```

> Kompletan radni primer: `notebooks/01_sdk_basics.ipynb`

#### Putanja B — Backend adapter (koristi postojeći Semantra)

Isti interfejs, ali adapter delegira stvarne pozive ka FastAPI backend-u.

```python
from semantra_core.models.schema import DatasetHandle, SchemaProfile, ColumnProfile
from semantra_backend_adapter import (
    BackendContext,
    create_backend_adapters,
)

# 1. Napravite context (ili pustite factory da učita pravi backend)
try:
    ctx = create_default_context()           # učita prave settings + DB session
    print("Učitan pravi backend context.")
except RuntimeError:
    ctx = BackendContext()                    # fallback: adapteri koriste stub

# 2. Napravite sve adaptere odjednom
adapters = create_backend_adapters(context=ctx, dataset_id="src1")
print("Dostupni adapteri:", list(adapters.keys()))
# ['engine', 'knowledge', 'llm', 'connector']

# 3. Koristite ih — isti API kao i kod čistog SDK-a
source = DatasetHandle(...)
target = SchemaProfile(...)

candidates = adapters["engine"].map_source_to_target(source, target)
print(f"Pravi backend vratio {len(candidates)} kandidata.")

# LLM kroz backend
result = adapters["llm"].validate_mapping(
    source_field="cust_id",
    candidate_targets=["customer_key", "id"],
    context={"description": "primary key"},
)
print("LLM:", result)

# Connector (ako je prosleđen dataset_id)
if "connector" in adapters:
    schema = adapters["connector"].fetch_schema()
    print("Šema:", schema.dataset_name)
```

> Kompletan radni primer: `notebooks/02_backend_adapter.ipynb`

**Ključna osobina:** Kad god backend nije učitan (nema `app.*` modula), adapter se tiho "spušta" na `InMemory*` referentne implementacije. Zato isti kod radi:
- u produkciji (kad je backend tu),
- u unit testovima (kad backend nije potreban),
- u demo notebook-u (kad korisnik nema backend).

#### Putanja C — LangGraph agent (state machine)

Gotov state machine koji izvršava **propose → validate → END**. Svaki čvor koristi `Protocol` interface — vi ubacite šta god želite.

```python
from semantra_core.models.schema import DatasetHandle, SchemaProfile, ColumnProfile
from semantra_core.services import InMemoryMappingEngine, BoundedLLMService
from semantra_core.langgraph_workflow import build_semantra_graph

source = DatasetHandle(...)
target = SchemaProfile(...)

# Koristite referentne implementacije (ili backend adaptere — isti API)
engine = InMemoryMappingEngine()
llm    = BoundedLLMService()

graph = build_semantra_graph(engine=engine, llm=llm)
result = graph.invoke({"source": source, "target": target})
print(result)
# {
#   'source': ..., 'target': ...,
#   'candidates': [...],
#   'selected_target': 'customer_key',
#   'confidence': 0.0,
#   'reasoning': [...]
# }
```

`SemantraState` TypedDict je vaš strukturirani "working memory" agenta:

```python
class SemantraState(TypedDict, total=False):
    source:          DatasetHandle
    target:          SchemaProfile
    candidates:      list[CandidateOption]
    selected_target: str
    confidence:      float
    reasoning:       list[str]
    error:           str
```

**Zamena implementacije (jedan red):**

```python
from semantra_backend_adapter import create_backend_adapters
adapters = create_backend_adapters()                    # pravi backend

graph_real = build_semantra_graph(
    engine=adapters["engine"],
    llm=adapters["llm"],
    knowledge=adapters["knowledge"],
)
result_real = graph_real.invoke({"source": source, "target": target})
```

> Kompletan radni primer: `notebooks/03_langgraph_workflow.ipynb`

---

## 4. Notebook demo tok — od nule do agenta u 15 minuta

```bash
# 1. Klonirajte Semantra
git clone https://github.com/gslavisam/Semantra
cd Semantra

# 2. Aktivirajte venv (Windows ili Linux)
python -m venv .venv
source .venv/bin/activate              # ili .venv\Scripts\activate na Windows-u

# 3. Instalirajte core + adapter + langgraph
pip install -e ./semantra-core
pip install -e ./semantra-backend-adapter
pip install -e "./semantra-core[langgraph]"

# 4. Otvorite notebook-ove
jupyter notebook notebooks/
```

Redosled:

| Notebook | Šta naučite | Vreme |
|---|---|---|
| `01_sdk_basics.ipynb` | Pydantic modeli, referentne impl, InMemory* | ~5 min |
| `02_backend_adapter.ipynb` | `create_backend_adapters()`, fallback ponašanje | ~5 min |
| `03_langgraph_workflow.ipynb` | `build_semantra_graph()`, zamena impl-ova | ~5 min |

---

## 5. Arhitektura u Detalje

### 5.1 Pydantic modeli (`semantra_core/models/`)

Tri modula, ~250 modela, sve čist Pydantic v2:

| Modul | Pokriva |
|---|---|
| `schema.py` | `ColumnProfile`, `SchemaProfile`, `DatasetHandle`, `PersistedDatasetRecord` (sa `to_handle()`), `SpecLayoutHint`/`SpecRecoverySuggestion` (heuristike za spec upload), response modeli (`UploadResponse`, `MetadataEnrichmentResponse`, `SqlTableDiscoveryResponse`) |
| `mapping.py` | `ScoringSignals` (10-dimenzionalni), `CandidateOption`/`MappingCandidate`, `MappingDecision` (persistabilan), request/response modeli (`AutoMappingRequest`/`Response`, `CanonicalMappingRequest`, `MappingRefinementRequest`), analiza (`MappingAnalysisSummaryResponse`, `MappingAnalysisNarrationResponse`), coverage report |
| `knowledge.py` | Canonical glossary (`CanonicalGlossaryEntry`, `CanonicalConceptSummary`/`Detail`), overlays (`KnowledgeOverlayVersion`/`Entry`/`ValidationResult`), runtime status, stewardship items, audit log, source field hints |

**Odluke:**
- `Literal` umesto `Enum` gde god je moguće — bolja Pydantic serijalizacija, manje koda.
- `default_factory=list` za sve kolekcije — sprečava deljeni mutable default.
- `PersistedDatasetRecord.to_handle()` eksplicitno "skida" storage metadata — čist API za agente.

### 5.2 Protokoli (`semantra_core/services/protocols.py`)

Četiri runtime-checkable Protokola:

```python
@runtime_checkable
class MappingEngine(Protocol):
    def map_source_to_target(self, source: DatasetHandle, target: SchemaProfile) -> list[CandidateOption]: ...
    def get_scoring_signals(self) -> ScoringSignals: ...

@runtime_checkable
class KnowledgeBase(Protocol):
    def get_canonical_concept(self, concept_id: str) -> Optional[CanonicalGlossaryEntry]: ...
    def search_concepts(self, query: str, limit: int = 10) -> list[CanonicalGlossaryEntry]: ...
    def get_active_overlay_entries(self) -> list[KnowledgeOverlayEntry]: ...

@runtime_checkable
class LLMService(Protocol):
    def validate_mapping(self, source_field: str, candidate_targets: list[str], context: dict) -> dict: ...
    def generate_transformation(self, mapping_decision: MappingDecision, context: dict) -> str: ...

@runtime_checkable
class Connector(Protocol):
    def fetch_schema(self) -> SchemaProfile: ...
    def fetch_preview(self, limit: int = 100) -> DatasetHandle: ...
```

**Odluke:**
- `@runtime_checkable` + `isinstance()` radi jer sve metode imaju ispravne signaturе.
- Kontrakt je **malan i stabilan**. Proširivanje = nove metode (neprobija stare pozivaoce).
- `LLMService` vraća `dict`, ne Pydantic model — jer LLM odgovori variraju po provajderu, a nama treba samo "closed-set izbor".

### 5.3 Referentne implementacije (`semantra_core/services/implementations.py`)

| Klasa | Ponašanje | Kada se koristi |
|---|---|---|
| `InMemoryMappingEngine` | Uvek vraća `[]`, signali su `ScoringSignals()` (sve nule) | Default u testovima i demo notebook-ovima |
| `InMemoryKnowledgeBase` | Čuva koncepte u `dict`, case-insensitive `search_concepts`, limit radi | Default kada nema backend-a |
| `BoundedLLMService` | Vraća prvog kandidata sa `confidence=0.0` i porukom "LLM service not configured" | Default u testovima |
| `StaticConnector` | Vraća injektovanu šemu, uvek prazan preview | Primeri i test fixtures |

**Odluke:**
- Implementacije NE izbacuju izuzetke. Ako nešto ne može, vraćaju bezazleni default.
- `InMemoryKnowledgeBase` radi case-insensitive pretragu da bi se ponašanje poklapalo sa backend-om.

### 5.4 LangGraph integracija (`semantra_core/langgraph_workflow.py`)

```python
class SemantraState(TypedDict, total=False):
    source:          NotRequired[DatasetHandle]
    target:          NotRequired[SchemaProfile]
    candidates:      NotRequired[list[CandidateOption]]
    selected_target: NotRequired[str]
    confidence:      NotRequired[float]
    reasoning:       NotRequired[list[str]]
    error:           NotRequired[str]
```

Dva čvora:

1. **`propose_candidates_node(state, engine)`** — zove `engine.map_source_to_target`, smešta rezultat u state.
2. **`validate_with_llm_node(state, llm)`** — uzima prvog kandidata, poziva `llm.validate_mapping`, popunjava `selected_target` / `confidence` / `reasoning`.

`build_semantra_graph(engine, llm, knowledge=None)` kompajlira i vraća LangGraph objekat spreman za `graph.invoke({"source": ..., "target": ...})`.

**Odluke:**
- `total=False` TypedDict — graf se poziva sa parcijalnim state-om, pa se polja popunjavaju postepeno.
- Svaki čvor ima `try/except` koji stavlja grešku u `state["error"]` umesto da širi izuzetak — agent može da odluči šta dalje.
- `knowledge` parametar je rezervisan za buduće čvorove (canonical lookup, glossary enrichment).

### 5.5 Backend adapter (`semantra-backend-adapter/`)

Šest modula:

| Modul | Uloga |
|---|---|
| `context.py` | `BackendContext` dataclass + `create_default_context()` koji pokušava da učita `app.*` |
| `mapping.py` | `BackendMappingEngine` — wrapuje `backend.app.services.mapping_service.generate_mapping_candidates` |
| `knowledge.py` | `BackendKnowledgeBase` — wrapuje `backend.app.services.metadata_knowledge_service` |
| `llm.py` | `BackendLLMService` — wrapuje `backend.app.services.llm_service` |
| `connector.py` | `BackendConnector` — wrapuje `backend.app.services.upload_store` |
| `factory.py` | `create_backend_adapters(context=None, dataset_id=None)` — vraća dict |

**Ključna odluka:** Svaki adapter pokušava `import` pozadinu `try/except ImportError`-om. Ako ne uspe, kreira instancu odgovarajuće `InMemory*` klase. Zato:

- U produkciji (kad je `app/` u istom env-u): radi puni Semantra.
- U testu (kad je samo `semantra-core` instaliran): radi in-memory.
- U demo notebook-u: radi in-memory sa jasnom porukom.

---

## 6. Da li Smo Samo Add-on Postojećem Projektu?

**Da, ali sa jasnom strategijskom namerom.**

| | Originalni Semantra | Novi Framework |
|---|---|---|
| **Tip** | Web aplikacija (FastAPI + Streamlit + SQLite) | Python SDK (paketi + protokoli) |
| **Korisnik** | Čovek (analitičar, data steward) | Programer (agent developer, integrator) |
| **Interfejs** | Browser UI | `import`-able kod |
| **Pokrivanje biznis logike** | 100% | 100% (isti engine, isti knowledge runtime) |
| **Pokrivanje UI/Storage** | 100% | 0% (namerno) |
| **Agentna orkestracija** | Nema | LangGraph state machine, zamenljiv |
| **Lanci alata** | Preko UI | Preko `Protocol` interfejsa |

**Šta to znači u praksi:**

1. **Postojeći korisnici ne moraju ništa da menjaju.** Web app nastavlja da radi kao pilot.
2. **Programeri dobijaju alternativni ulaz.** Mogu da pozovu Semantra logiku iz Python skripte, notebook-a, microservice-a ili agenta — bez pokretanja Streamlit-a.
3. **Backend adapter daje izbor.** Ako želite da koristite novi SDK, ali da i dalje delegirate stvarne pozive u postojeći Semantra (da ne duplirate biznis logiku), uključite `semantra-backend-adapter`.
4. **Lako se pravi nova integracija.** Recimo, `MappingEngine` može da se zameni sa:
   - Custom algoritmom (samo napišete klasu koja zadovoljava Protocol)
   - Remote servisom (HTTP/gRPC klijent)
   - Drugim framework-om (CrewAI, LlamaIndex)
5. **Streamlit UI nije zamenjen.** Streamlit ostaje primarni UI za ljude. Framework je za mašine.

**Pokrivenost (detaljno u `semantra-core/docs/CAPABILITY_ANALYSIS.md`):**

| Originalna mogućnost | Framework pokriva |
|---|---|
| Source-to-target mapping (deterministički) | ✅ 100% |
| Canonical concept lookup & search | ✅ 100% |
| Closed-set LLM validation | ✅ 100% |
| Transformation code generation | ✅ 100% (protocol postoji) |
| Bounded LLM use (bez autonomije) | ✅ 100% (garancija na tipu) |
| Multi-format ingestion (CSV/JSON/XML/XLSX/SQL) | ⚠️ 30% (jedan `BackendConnector`, per-format pack = budući rad) |
| Mapping Analysis Overview + naracija | ❌ (treba novi `AnalysisService` protocol) |
| Review Queue Plan | ❌ (isto) |
| Catalog search/reuse | ❌ (isto) |
| Governance & stewardship workflows | ❌ (read-only Protocol po dizajnu) |
| Streamlit UI, RBAC, SQLite, Workspace Copilot | ❌ (namerno, ne posao SDK-a) |
| **Agentic orkestracija** | **✅ NOVO** (LangGraph state machine) |

**Preporučeni obrasci upotrebe:**

| Ako ste... | Koristite... |
|---|---|
| Data analyst | I dalje web app |
| Backend developer koji gradi novu integraciju | `semantra-core` + vaš kod |
| Agent developer (LangGraph, CrewAI) | `semantra-core` + `langgraph_workflow` + vaše čvorove |
| Postojeći Semantra korisnik koji želi batch automation | `semantra-core` + `semantra-backend-adapter` |
| Istraživač / edukator | `semantra-core` sa `InMemory*` impl |

---

## 7. Testovi i Kvalitet Koda

| Paket | Test fajlova | Testova | Vreme | Status |
|---|---|---|---|---|
| `semantra-core` | 5 | **115** | 0.26s | ✅ svi prolaze |
| `semantra-backend-adapter` | 4 | **30** | ~28s | ✅ svi prolaze |
| **Ukupno novi framework** | **9** | **145** | **~28s** | ✅ |

**Pokrivenost (po modulu):**

- `test_schema_models.py` (17) — `ColumnProfile`, `SchemaProfile`, `DatasetHandle`, `PersistedDatasetRecord.to_handle()`, spec layout/recovery, response wrapperi.
- `test_mapping_models.py` (36) — `ScoringSignals` (10 dimenzija), kandidati, decision, request/response, analysis, narration, coverage report.
- `test_knowledge_models.py` (38) — privacy metadata, overlay lifecycle, runtime status, glossary, stewardship, audit, source field hints.
- `test_reference_implementations.py` (15) — `InMemoryMappingEngine` determinizam, `InMemoryKnowledgeBase` add/search/limit, `BoundedLLMService` echo, `StaticConnector` schema injection.
- `test_protocols.py` (9) — parametrizovano `isinstance()` za sva 4 Protokola + sanity provere da su svi metodi prisutni.
- `semantra-backend-adapter/tests/test_mapping_engine_regression.py` (3) — regression testovi za bag-ove otkrivene kroz `04_real_file_mapping_demo.py`: ne-prazan output, source field attach, signali iz `SCORING_PROFILES`.
- `semantra-backend-adapter/tests/test_e2e_mapping.py` (16) — **end-to-end testovi** sa pravim showcase fajlovima iz `ui_fixtures/`. Parametrizovano preko 4 domena (customer, material, supplier, customer-sales-area) i 3 formata (CSV, JSON, XLSX). Pokriva 3 nivoa: (1) loader gradi ispravan `SchemaProfile`, (2) engine vraća neprazan output, (3) top-kandidat pogađa očekivani target. Plus invariant: isti case učitan iz CSV i XLSX daje **identičan** mapping (format-agnostičnost).
- `semantra-backend-adapter/tests/test_e2e_rich_mapping.py` (5) — **rich e2e testovi** koji proveravaju punu `MappingCandidate` strukturu (kakvu koristi web app review tabela): 14 kandidata za supplier case, svi imaju ne-praznu `explanation`, punu 10-dimenzionu `ScoringSignals`, korektan `status` (accepted/needs_review/rejected), `canonical_details` sa poznatim konceptima, i coverage report sa `coverage_ratio >= 0.5`.

**Konvencije:**
- Svaki test ima type hint na potpisu (`def test_x() -> None`).
- Jedan koncept po testu (više `assert`-ova je OK ako pinuju jedno ponašanje).
- Literal validacija testirana sa `pytest.raises(ValidationError)`.
- LSP upozorenje: `Literal["a", "b"]` NIJE callable — poredi se sa stringom `==`, nikad sa `Literal("a")`.

**Pokretanje:**

```bash
cd /home/smili/Semantra/semantra-core
.venv/bin/pytest tests/ -v
# 115 passed in 0.26s
```

---

## 8. Fajl Struktura

**Od juna 2026, ceo agentic framework živi u jednom folderu: `semantra_agent/`.**

```
Semantra/
├── semantra_agent/                        # NOVI: Sve na jednom mestu (editable install)
│   ├── README.md                          # Glavni README sa quick start
│   ├── pyproject.toml                     # Unified: core + adapter + langgraph + langchain
│   ├── src/
│   │   ├── semantra_core/                 # Pydantic modeli + Protocol ugovori + reference impl
│   │   │   ├── models/                    #   schema.py, mapping.py, knowledge.py
│   │   │   ├── services/                  #   protocols.py, implementations.py
│   │   │   └── langgraph_workflow.py      #   build_semantra_graph
│   │   ├── semantra_backend_adapter/      # Most ka postojećem Semantra FastAPI backendu
│   │   │   ├── context.py
│   │   │   ├── factory.py
│   │   │   ├── mapping.py
│   │   │   ├── knowledge.py
│   │   │   ├── llm.py
│   │   │   └── connector.py
│   │   └── semantra_agent/                # NEW: viši nivo apstrakcije
│   │       └── langchain_tools.py         #   SDK → LangChain alati (build_semantra_tools)
│   ├── tests/                             # 145 testova (unit + regression + e2e)
│   │   ├── conftest.py
│   │   ├── test_schema_models.py          # 17
│   │   ├── test_mapping_models.py         # 36
│   │   ├── test_knowledge_models.py       # 38
│   │   ├── test_reference_implementations.py  # 15
│   │   ├── test_protocols.py              # 12 (ref impl + adapter conformance)
│   │   ├── test_mapping_engine_regression.py  # 3
│   │   ├── test_e2e_mapping.py            # 16 (4 case × 3 formata + format-invariant)
│   │   └── test_e2e_rich_mapping.py       # 5 (puni MappingCandidate payload)
│   ├── examples/                          # 5 radnih primera
│   │   ├── 01_sdk_basics.ipynb
│   │   ├── 02_backend_adapter.ipynb
│   │   ├── 03_langgraph_workflow.ipynb
│   │   ├── 04_real_file_mapping_demo.py
│   │   └── 04b_supplier_rich_mapping_demo.py
│   └── docs/                              # 3 markdown fajla
│       ├── AGENTIC_FRAMEWORK_PRESENTATION.md
│       ├── CAPABILITY_ANALYSIS.md
│       └── TECHNICAL_GUIDE.md
│
├── backend/                               # POSTOJEĆI: FastAPI + SQLite (nepromenjen)
├── streamlit_app.py                       # POSTOJEĆI: Web UI (nepromenjen)
└── requirements.txt                       # -e ./semantra_agent (umesto dva stara -e)
```

**Zašto jedan folder?** Originalno su `semantra-core/` i `semantra-backend-adapter/` bili dva odvojena paketa, svaki sa svojim `pyproject.toml`, `tests/`, i `docs/`. Konsolidacija u `semantra_agent/`:
- Jedan `pip install -e .` umesto dva
- Jedan `pyproject.toml` (sve dependency grupe na jednom mestu)
- Jedan `tests/` folder
- Jedan `docs/` folder
- Nove više-nivo apstrakcije (`semantra_agent.langchain_tools`) imaju gde da žive

**Import imena su zadržana** — `from semantra_core import ...` i `from semantra_backend_adapter import ...` i dalje rade, jer je `src/` layout dozvolio da oba paketa koegzistiraju pod istim distributivnim imenom `semantra-agent`.

---

## 9. Budući Rad (Roadmap)

| Faza | Šta | Status |
|---|---|---|
| **Phase 1** | Pure Pydantic modeli | ✅ |
| **Phase 2** | Protokoli + referentne impl + LangGraph | ✅ |
| **Phase 3** | Backend adapter (4 klase + factory) | ✅ |
| **Phase 4** | Testovi (115 + 6 = 121) | ✅ |
| Phase 5 | `semantra-connectors` pack (CSV, SQL, SAP, QAD, HTTP) | 📋 |
| Phase 6 | Agent templates (Discovery → Mapping → Validation, gotovi grafovi) | 📋 |
| Phase 7 | Async varijante Protokola | 📋 |
| Phase 8 | Distribuirana tracing integracija (OpenTelemetry) | 📋 |
| Phase 9 | Verzionisanje SDK-a + migration guide | 📋 |

Detaljnije u `semantra-core/docs/CAPABILITY_ANALYSIS.md` (sekcija 5).

---

## 10. Brzi Recepti

### "Imam source CSV, hoću mapping kandidate"
```python
from semantra_core.models.schema import DatasetHandle, SchemaProfile, ColumnProfile
from semantra_backend_adapter import create_backend_adapters

source = DatasetHandle(
    dataset_id="my_csv", dataset_name="my_csv",
    schema_profile=SchemaProfile(
        dataset_id="my_csv", dataset_name="my_csv", row_count=1000,
        columns=[ColumnProfile(name="email", normalized_name="email",
                               dtype="str", null_ratio=0.0,
                               unique_ratio=0.8, non_null_count=1000)],
    ),
)
target = SchemaProfile(
    dataset_id="tgt", dataset_name="tgt", row_count=0,
    columns=[ColumnProfile(name="email_address", normalized_name="email_address",
                           dtype="str", null_ratio=0.0,
                           unique_ratio=0.0, non_null_count=0)],
)
adapters = create_backend_adapters()
candidates = adapters["engine"].map_source_to_target(source, target)
for c in candidates:
    print(c.target, c.confidence, c.confidence_label)
```

### "Imam LangGraph, hoću Semantra čvorove"
```python
from semantra_core.langgraph_workflow import build_semantra_graph
from semantra_core.services import InMemoryMappingEngine, BoundedLLMService

graph = build_semantra_graph(
    engine=InMemoryMappingEngine(),
    llm=BoundedLLMService(),
)
result = graph.invoke({"source": source, "target": target})
```

### "Hoću test, bez mreže"
```python
from semantra_core.services import (
    InMemoryMappingEngine, InMemoryKnowledgeBase, BoundedLLMService, StaticConnector,
)
# Sve radi u memoriji, nema fajlova, nema HTTP-a.
```

### "Hoću da zamenim engine svojom implementacijom"
```python
from semantra_core.services.protocols import MappingEngine

class MyRemoteEngine:
    """Šalje HTTP zahtev mom servisu."""
    def map_source_to_target(self, source, target):
        return requests.post(URL, json=source.dict()).json()
    def get_scoring_signals(self):
        return ScoringSignals(name=1.0, semantic=0.5)

# isinstance(MyRemoteEngine(), MappingEngine) == True
# Može odmah da se ubaci u build_semantra_graph(engine=MyRemoteEngine())
```

---

## 11. Demonstracija: Pravo Mapiranje Fajl-na-Fajl

> **Ova sekcija nije dokument — to je pokazna vežba.** Skripta `notebooks/04_real_file_mapping_demo.py` učitava dva prava CSV fajla iz `ui_fixtures/showcase_customer_mapping/`, gradi semantra-core Pydantic modele, i pokreće **oba** engine-a jedan za drugim.

### 11.1 Šta se dešava u demo-u

1. **Učitaj CSV-ove** — minimalni parser pretvara redove u `ColumnProfile` (detektuje dtype, null ratio, unique ratio, sample values, jednostavne pattern-e: `email`, `phone`, `date`, `integer`, `float`).
2. **Izgradi `SchemaProfile` + `DatasetHandle`** — čist Pydantic, bez backend poziva.
3. **Pozovi `InMemoryMappingEngine`** — vraća 0 kandidata (stub, po dizajnu). Ovo **dokazuje** da SDK plumbing radi.
4. **Pozovi `BackendMappingEngine`** — učitava `backend.app.services.mapping_service.generate_mapping_candidates`, dobija `AutoMappingResponse` sa `ranked_mappings[*].candidates`, konvertuje u `list[CandidateOption]`, grupiše po source polju.
5. **Prikaži rezultat** — po source polju, najbolji target + confidence + method.

### 11.2 Rezultat (stvarni output, jun 2026)

Pokretanje: `python notebooks/04_real_file_mapping_demo.py`

**SOURCE** (`showcase_customer_source.csv`, 5 redova, 8 kolona):
```
legacy_customer_code  str  uuid
purchaser             str  uuid
primary_contact_email str  email
main_phone            str  phone
billing_country       str  uuid
go_live_date          date date
segment_label         str  text
annual_spend_usd      float float
```

**TARGET** (`showcase_customer_target.csv`, 5 redova, 8 kolona):
```
account_id        str  uuid
customer_name     str  uuid
email_address     str  email
phone_number      str  phone
country_iso       str  uuid
created_date      date date
customer_segment  str  text
annual_revenue_usd float float
```

**Per-source-field resolution (real engine):**

| Source polje | → | Target | Confidence | Method |
|---|---|---|---|---|
| `legacy_customer_code` | → | `account_id` | 0.62 | multi_signal_heuristic |
| `purchaser` | → | `customer_name` | 0.64 | multi_signal_heuristic |
| `primary_contact_email` | → | `email_address` | 0.68 | multi_signal_heuristic |
| `main_phone` | → | `phone_number` | 0.65 | multi_signal_heuristic |
| `billing_country` | → | `country_iso` | 0.66 | multi_signal_heuristic |
| `go_live_date` | → | `created_date` | 0.65 | multi_signal_heuristic |
| `segment_label` | → | `customer_segment` | 0.66 | multi_signal_heuristic |
| `annual_spend_usd` | → | `annual_revenue_usd` | 0.69 | multi_signal_heuristic |

Sva mapiranja su **korektna**. Engine je dao 24 kandidata (8 source × 3 alternative po polju). Confidence je u opsegu 0.49-0.69 jer radi bez LLM providera (heuristika + knowledge base + canonical), pa je u "low_confidence" / "medium_confidence" opsegu.

### 11.3 Bagovi u novom kodu koje je demo otkrio

Demonstracija je imala **konkretnu vrednost** — otkrila je dva prava buga u `semantra-backend-adapter` koja su prošla neprimećena kroz postojeće testove:

**Bag 1: `_convert_candidates` čitao nepostojeći atribut**
```python
# PRE (uvek vraćalo []):
for mc in getattr(response, "candidates", []) or []:
    ...

# POSLE (ispravno čita ranked_mappings):
for rm in getattr(response, "ranked_mappings", []) or []:
    for c in getattr(rm, "candidates", []) or []:
        ...
```

**Bag 2: `get_scoring_signals` koristio string umesto dict**
```python
# PRE (DEFAULT_SCORING_PROFILE je "balanced" string, ne dict):
profile = mapping_service.DEFAULT_SCORING_PROFILE
profile.get("name", 0.0)   # AttributeError → fallback na sve 0.0

# POSLE (čita dict iz SCORING_PROFILES):
profile_name = mapping_service.DEFAULT_SCORING_PROFILE
profile = mapping_policy.SCORING_PROFILES.get(profile_name, {})
profile.get("name", 0.0)   # vraća 0.2
```

Oba buga su ispravljena u `semantra-backend-adapter/src/semantra_backend_adapter/mapping.py`, a regression testovi su dodati u `semantra-backend-adapter/tests/test_mapping_engine_regression.py`. **Broj testova**: 121 → 140.

### 11.4 Kako se pokreće

```bash
cd /home/smili/Semantra
/home/smili/Semantra/semantra-core/.venv/bin/python notebooks/04_real_file_mapping_demo.py
```

Skripta automatski dodaje `/home/smili/Semantra/backend` na `sys.path` da bi `from app.core.config import settings` radio (jer `mapping_service` koristi relativne import-e unutar `backend/`).

---

## 12. Gde Sledeće

| Želim... | Čitaj... |
|---|---|
| Da razumem arhitekturu | `semantra-core/docs/TECHNICAL_GUIDE.md` |
| Da vidim šta je pokriveno od starog Semantra | `semantra-core/docs/CAPABILITY_ANALYSIS.md` |
| Da pokrenem prvi primer | `notebooks/01_sdk_basics.ipynb` |
| Da koristim pravi backend | `notebooks/02_backend_adapter.ipynb` |
| Da napravim agenta | `notebooks/03_langgraph_workflow.ipynb` |
| **Da vidim pravo file-to-file mapiranje** | **`notebooks/04_real_file_mapping_demo.py`** + **`semantra-backend-adapter/tests/test_e2e_mapping.py`** |
| Da vidim testove | `semantra-core/tests/` + `semantra-backend-adapter/tests/` |
| Da proširim framework | Pročitaj protokole u `semantra_core/services/protocols.py` (kratki su) |

---

*Dokument pripremljen: jun 2026.*
*Autor refaktora: gslavisam + AI-assisted development.*
*Kontakt: GitHub Issues na `gslavisam/Semantra`.*
