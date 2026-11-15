# ReqMind AI

Upload a software requirements document and get back a clean list of requirements, the pairs that contradict each other, a knowledge graph, and a chat that answers questions with the source passages.

Team: Krrish Singh (backend, AI) and Muskaan Singhla (documents, export, frontend). B.Tech AI, Bennett University. 2026.

<!-- TODO: screenshot of the main screen once the frontend is in -->

## Contents
1. [What it does](#what-it-does)
2. [Results](#results)
3. [Quick start without Docker](#quick-start-without-docker)
4. [Quick start with Docker](#quick-start-with-docker)
5. [Models](#models)
6. [Using it](#using-it)
7. [Configuration](#configuration)
8. [Design document](#design-document)
9. [Tech stack](#tech-stack)
10. [Repository structure](#repository-structure)
11. [Code reference](#code-reference)
12. [Approaches compared](#approaches-compared)
13. [Hardware and run times](#hardware-and-run-times)
14. [Limitations](#limitations)
15. [Troubleshooting](#troubleshooting)
16. [Citations](#citations)
17. [License](#license)

## What it does

**Problem.** Requirement documents are long, written by many people, and often say two different things about the same feature. Reading them line by line to build a requirement list takes hours, and contradictions are easy to miss.

**For whom.** Students and small teams writing or reviewing an SRS, and anyone who receives a requirements document from a client.

**What they get.**

| Feature | What it does | Needs |
|---|---|---|
| Requirement extraction | Lists every requirement with type, category, priority, entities and the exact source sentence | LLM (falls back to text rules) |
| Vague wording check | Flags words like "fast" or "user-friendly" | Text rules |
| Conflict detection | Finds pairs that cannot both be true, with a one-line reason | Embeddings + LLM (falls back to number checks) |
| Knowledge graph | Documents, requirements and entities with their links | Neo4j (falls back to Postgres) |
| Chat | Answers questions using only the project's passages, and shows them | Qdrant + LLM (falls back to keyword search) |
| Teams | Every company sees only its own projects | Postgres |
| Upload, edit, export | PDF/DOCX/TXT upload, manual edits, MD/PDF/DOCX export | Muskaan's part, not built yet |

**Scope.** In: English text documents, one company per account, local models only. Out: scanned documents (no OCR), other languages, tracing requirements to code.

## Results

No measured numbers yet. They will come from a hand-labelled set of documents.

| Task | Metric | Text rules | qwen3:8b |
|---|---|---|---|
| Extraction | Recall / precision of requirements | TBD | TBD |
| Conflicts | Found / missed on planted conflicts | TBD | TBD |
| Chat | Answers fully supported by the shown passages | TBD | TBD |

On `samples/chunks.json` (4 chunks, 18 requirement sentences, 2 planted conflicts) the text rules find all 18 sentences and both conflicts. This file is used by the tests; it is too small to count as a result.

## Quick start without Docker

This is the main way to run the project. The commands are for Ubuntu 24.04.

### 1. Install the tools (one time)

| Tool | Install | Check |
|---|---|---|
| Python 3.12 | `sudo apt install python3.12 python3.12-venv` | `python3.12 --version` |
| Git | `sudo apt install git` | `git --version` |
| Docker + Compose | [docs.docker.com/engine/install/ubuntu](https://docs.docker.com/engine/install/ubuntu/) | `docker compose version` |
| Ollama (only for AI) | `curl -fsSL https://ollama.com/install.sh \| sh` | `ollama --version` |
| NVIDIA driver (only for AI on GPU) | `sudo ubuntu-drivers install` | `nvidia-smi` shows your GPU |

### 2. Get the code and install the packages

```bash
git clone https://github.com/Krrish768/reqmind-ai.git
cd reqmind-ai
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and set `JWT_SECRET_KEY` to a random string:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Set `APP_CONFIG=gpu_laptop` if you have Ollama, or `APP_CONFIG=cpu_laptop` if not.

### 3. Start the services

```bash
docker compose --profile ai up -d   # gpu_laptop: Postgres, MinIO, Redis, Qdrant, Neo4j
docker compose up -d                # cpu_laptop: only Postgres and MinIO
```

### 4. Download the models (gpu_laptop only)

```bash
python -m scripts.download_weights
ollama list                         # should show qwen3:8b and nomic-embed-text
```

### 5. Run

Check that everything is reachable:

```bash
python -m scripts.check_services
```

Then use two terminals, both in the repo root with `source .venv/bin/activate`:

```bash
uvicorn backend.app.main:app --reload --port 8000   # terminal 1: API
python -m scripts.run_worker                         # terminal 2: worker (gpu_laptop only)
```

API docs: http://localhost:8000/docs. The web page is served at http://localhost:8000 once `frontend/index.html` exists.

If Ollama is not running, the analysis still finishes with the text rules, and the job message says so. If Neo4j is down, the graph is built from Postgres. If Qdrant is down, chat uses keyword search.

### 6. Run the tests

```bash
python -m pytest -q
```

The tests use SQLite, an in-memory Qdrant and a fake LLM, so no service needs to be running.

## Quick start with Docker

Optional. Docker packs Python and all packages into one image. Ollama stays on the host.

1. Install Docker Engine and Compose (link above). No GPU toolkit is needed: the containers do not use the GPU, Ollama does.
2. Let the containers reach Ollama on the host. By default Ollama only listens on localhost:
   ```bash
   sudo systemctl edit ollama
   # add these two lines, save, then:
   # [Service]
   # Environment="OLLAMA_HOST=0.0.0.0"
   sudo systemctl restart ollama
   ```
3. Set `JWT_SECRET_KEY` in `.env` (compose reads it).
4. Build and start everything:
   ```bash
   docker compose --profile app up -d --build
   docker compose ps                                   # backend should become "healthy"
   curl http://localhost:8000/api/health
   ```

Useful commands:

```bash
docker compose logs -f backend worker               # logs
docker compose run --rm backend python -m scripts.check_services
docker compose --profile app down                   # stop (data stays)
docker compose --profile app down -v                # stop and delete all data
```

What stays on the host: the database, uploaded files, vectors and the graph live in Docker volumes (`postgres_data`, `minio_data`, `qdrant_data`, `neo4j_data`) and survive rebuilds. Models stay in Ollama's own folder on the host.

Without a GPU: start Ollama on CPU (slow) or not at all; the analysis falls back to the text rules.

Docker status: `docker compose config` was checked. The image build and run were not tested yet. <!-- TODO: test build + run on the laptop -->

## Models

Listed in `configs/weights.yaml`. Ollama stores them in `~/.ollama`, not in this repo.

| Name | What it is | Size | Source | Licence |
|---|---|---|---|---|
| `qwen3:8b` | LLM for extraction, conflict reasons and chat | 5.2 GB | [ollama.com/library/qwen3](https://ollama.com/library/qwen3), Qwen team | Apache-2.0 |
| `nomic-embed-text` | Embeddings for chat search and similarity | 274 MB | [ollama.com/library/nomic-embed-text](https://ollama.com/library/nomic-embed-text), Nomic AI | Apache-2.0 |

```bash
python -m scripts.download_weights                       # all
python -m scripts.download_weights --name qwen3:8b       # one
ollama pull qwen3:8b                                     # manual fallback
```

To copy models from another machine, copy `~/.ollama/models` (or `/usr/share/ollama/.ollama/models` for the system service) to the same place.

## Using it

### Web page
<!-- TODO: list the pages when Muskaan's frontend is in -->

### Command line

```bash
python -m scripts.analyze_document --chunks samples/chunks.json --limit 1   # agents on a sample, no database
python -m scripts.analyze_document --chunks samples/chunks.json --rules     # text rules only
python -m scripts.analyze_document --document-id 3                          # full pipeline on a saved document
python -m scripts.check_services                                            # are the services up?
```

### API

All routes start with `/api`. Every route except signup, login and health needs `Authorization: Bearer <token>`.

| Method | Path | What it does |
|---|---|---|
| GET | `/api/health` | API and database status |
| POST | `/api/auth/signup` | Create a user (and the company if new) |
| POST | `/api/auth/login` | Get a token |
| GET | `/api/auth/me` | Current user |
| POST / GET | `/api/projects` | Create / list projects |
| GET | `/api/projects/{id}` | One project |
| POST | `/api/projects/{id}/documents/{doc_id}/analyze` | Start an analysis job |
| GET | `/api/jobs/{job_id}` | Job status and progress (poll every 2 s) |
| GET | `/api/projects/{id}/jobs` | All jobs of a project |
| GET | `/api/projects/{id}/conflicts` | Conflicting pairs |
| GET | `/api/projects/{id}/graph?refresh=true` | Graph nodes and edges |
| POST | `/api/projects/{id}/chat` | Answer a question with sources |
| | `/api/projects/{id}/documents ...` | Upload and list documents (Muskaan, not built yet) |
| | `/api/projects/{id}/requirements ...` | List and edit requirements (Muskaan, not built yet) |
| | `/api/projects/{id}/export ...` | Export (Muskaan, not built yet) |

```bash
curl -X POST localhost:8000/api/auth/login -H "Content-Type: application/json" \
     -d '{"email": "you@example.com", "password": "secret123"}'
```

## Configuration

| File | Used on |
|---|---|
| `configs/gpu_laptop.yaml` | A laptop with Ollama: LLM, Redis queue, Qdrant, Neo4j |
| `configs/cpu_laptop.yaml` | A laptop without Ollama: text rules, jobs run inside the API |
| `configs/docker.yaml` | Inside the containers (service names instead of localhost) |
| `.env` | Secrets and `APP_CONFIG`, the config to use |

| Setting | Meaning |
|---|---|
| `ai_enabled` | Use Ollama. Off = text rules and keyword search |
| `ollama.num_ctx` | LLM context size. 4096 keeps both models inside 8 GB of VRAM |
| `redis.enabled` | Run jobs in a separate worker. Off = inside the API |
| `analysis.max_chunks` | Only the first N chunks of a document are analyzed |
| `analysis.conflict_similarity` | Pairs with cosine similarity at or above this are checked for conflicts |
| `analysis.max_conflict_pairs` | Upper limit of LLM conflict checks per document |
| `chat.top_k` | Passages given to the LLM per question |

## Design document

### 1. Problem and users
Analysts and students must turn a requirements document into a checked list. Success: every requirement in the document is listed once, with the sentence it came from, and real contradictions are shown. They must never get a requirement or a number that is not in the document.

### 2. Why generative AI, and which kind

| Criterion | Fit |
|---|---|
| Input is free text with no fixed format | Rules miss requirements that do not use "shall/must" |
| Output needs judgement (type, category, whether two sentences really clash) | Hard to write as rules |
| Every output can be checked against the source text | Errors can be caught in code |

Kind: prompting a local LLM with JSON-schema output (no fine-tuning), plus retrieval (RAG) for chat. Baseline: the text rules in `backend/app/agents/rules.py`, which are also the fallback.

What the LLM does not decide: priority (from the modal verb: must/shall = high, should/will = medium, may/could = low), the vague-word flag, which pairs are checked for conflicts (similarity and number checks), and whether a requirement is kept (its quote must be in the text).

### 3. Scope
See [What it does](#what-it-does). At the boundary: a document without chunks cannot be analyzed (409); only the first `max_chunks` chunks are used; a question with no matching passage gets "the documents do not say".

### 4. Requirements

| ID | Functional requirement | How it is tested |
|---|---|---|
| F1 | Each extracted requirement has a source quote found in the chunk | `test_agents.py` |
| F2 | Invented quotes and entities are retried once, then dropped | `test_agents.py` |
| F3 | Number clashes on the same topic are reported as conflicts | `test_agents.py` |
| F4 | Analysis still finishes when Ollama is down | `test_agents.py`, `test_analysis_api.py` |
| F5 | A company never sees another company's data | `test_auth_projects.py`, `test_analysis_api.py` |
| F6 | Re-analysis replaces old AI requirements and keeps manual ones | `test_analysis_api.py` |
| F7 | Chat answers list their sources; unchecked answers fall back to a template | `test_analysis_api.py` |

| Non-functional | Target | Measured |
|---|---|---|
| Analysis time, 10-page document, RTX 4060 | under 5 min | TBD |
| Chat answer time | under 10 s | TBD |
| VRAM | under 8 GB | TBD |
| Cost | 0 (local models, free tools) | 0 |
| Privacy | documents never leave the machine | yes, no cloud calls |

### 5. Architecture

```mermaid
flowchart LR
    UI[Web page] -->|REST /api| API[FastAPI]
    API --> PG[(Postgres)]
    API -->|enqueue| RQ[(Redis queue)]
    RQ --> W[Worker]
    W --> WF[LangGraph workflow<br/>extract, deduplicate, embed, conflicts]
    WF -->|JSON schema| OL[Ollama<br/>qwen3:8b + nomic-embed-text]
    W --> PG
    W --> QD[(Qdrant)]
    W --> NJ[(Neo4j)]
    API -->|chat search| QD
    API -->|graph| NJ
    API --> MI[(MinIO files)]
```
<!-- TODO: export this diagram to docs/images/architecture.png for slides -->

| Component | Why it exists |
|---|---|
| FastAPI | REST API for the web page (all F*) |
| Postgres | Source of truth for users, documents, requirements, conflicts, jobs (F5, F6) |
| Redis + RQ worker | Long LLM jobs run outside the web server, one at a time on the GPU |
| LangGraph | The analysis steps as nodes, with fallbacks between them (F4) |
| Ollama | Local LLM and embeddings, no cost, private |
| Qdrant | Vector search for chat (F7) |
| Neo4j | Graph queries over requirements and entities |
| MinIO | Stores uploaded files (Muskaan) |

How a request moves: the page asks the API to analyze a parsed document. The API saves a job and puts it on the Redis queue. The worker reads the chunks from Postgres and runs the LangGraph workflow. Each chunk goes to the LLM; every answer is checked against the chunk and retried once if needed. Requirements are embedded, similar pairs and number clashes are judged, and conflicts are kept only with a grounded reason. Results are saved to Postgres, chunk vectors go to Qdrant and the graph is copied to Neo4j. The page polls the job until it is done.

### 6. Failure modes and guardrails

| What can go wrong | What limits it | What can still get through |
|---|---|---|
| LLM invents a requirement | Quote must be in the chunk, one retry, then dropped | A real sentence given the wrong type or category |
| LLM invents a number in a reason or answer | Every number must appear in the sources | A wrong statement without numbers |
| Ollama down or out of memory | Text rules take over and the job message says so | Lower recall for sentences without modal verbs |
| Qdrant or Neo4j down | Keyword search; graph from Postgres | Weaker chat search |
| A worker dies mid-job | Job row keeps its last message | Job stays "running"; start a new analysis |
| A user joins another company by typing its name | Not handled yet | See Limitations |

### 7. Evaluation plan
Hand-label 5–10 public SRS documents (requirements and planted conflicts). Compare text rules against the LLM on recall and precision of requirements, and found/missed conflicts. Check chat answers by hand for support by the shown passages. Report per document, plus analysis time and VRAM. <!-- TODO: build scripts/evaluate_extraction.py and fill the Results table -->

### 8. Open questions and risks

| Question or risk | How to find out or handle it |
|---|---|
| Is qwen3:8b good enough on long, messy documents? | Evaluation above; try a smaller and a larger model |
| Is 0.80 the right similarity threshold for nomic-embed-text? | Tune on the labelled conflicts |
| Company signup is open to anyone who knows the name | Add invites before any real use |

## Tech stack

| Layer | Tools |
|---|---|
| Language | Python 3.12, HTML/CSS/JS |
| Backend | FastAPI, SQLAlchemy, Pydantic, python-jose, passlib |
| LLM | Ollama with qwen3:8b and nomic-embed-text |
| Agents | LangGraph (a 4-node workflow, no tool-calling agents) |
| Search | Qdrant |
| Graph | Neo4j 5 Community |
| Jobs | Redis + RQ |
| Database and files | Postgres 16, Silo (a MinIO fork, same S3 API) |
| Packaging | Docker, Docker Compose |
| Tests | pytest |

## Repository structure

```
reqmind-ai/
├── README.md
├── requirements.txt          pinned packages, one section per teammate
├── Dockerfile                image for the API and the worker
├── docker-compose.yml        Postgres, MinIO, Redis, Qdrant, Neo4j, API, worker
├── .env.example              secrets and APP_CONFIG
├── configs/                  settings per machine, models list
├── samples/chunks.json       small example document in the chunk format
├── backend/app/
│   ├── main.py               creates the app, mounts the web page
│   ├── config.py             loads configs/<APP_CONFIG>.yaml and .env
│   ├── database.py           engine and sessions
│   ├── models.py             tables
│   ├── schemas.py            every shared data format
│   ├── security.py           passwords and tokens
│   ├── pipeline.py           full analysis of one document
│   ├── jobs.py               job rows and the Redis queue
│   ├── api/                  routes (thin, call the parts below)
│   ├── agents/               LangGraph workflow, LLM extraction, conflicts, text rules
│   ├── llm/                  Ollama client, prompts, grounding checks
│   ├── rag/                  Qdrant store and chat answers
│   └── knowledge_graph/      graph from Postgres and Neo4j copy
├── scripts/                  worker, model download, service check, CLI analysis
├── tests/                    pytest tests
└── frontend/                 web page (being rebuilt in plain HTML/CSS/JS by Muskaan)
```

## Code reference

<details><summary><code>backend/app/agents/</code></summary>

| Function | What it does |
|---|---|
| `workflow.run_workflow` | Runs extract → deduplicate → embed → conflicts on a list of chunks |
| `extraction.extract_with_llm` | One chunk to the LLM, grounding check, one retry |
| `extraction.deduplicate` | Drops repeats from overlapping chunks |
| `conflicts.find_candidates` | Pairs by similarity, shared entities and number clashes |
| `conflicts.detect_conflicts` | LLM verdict per pair, reason checked |
| `rules.extract_with_rules` | Fallback and baseline extractor |
| `rules.priority_from_text` | Priority from the modal verb |
| `rules.vague_words_in` | Vague words in a sentence |
</details>

<details><summary><code>backend/app/llm/</code>, <code>rag/</code>, <code>knowledge_graph/</code></summary>

| Function | What it does |
|---|---|
| `client.chat_json` | LLM call with a JSON schema, temperature 0, no thinking |
| `client.embed_texts` | Embeddings with the nomic task prefixes |
| `grounding.quote_in_text` | Is the quote in the text |
| `grounding.unsupported_numbers` | Numbers not found in the facts |
| `vector_store.index_chunks` / `search` | Qdrant upsert and project-filtered search |
| `chat.answer_question` | Passages → LLM answer → check → template fallback |
| `builder.build_graph` | Graph from Postgres |
| `neo4j_store.sync_project` / `read_project` | Neo4j copy of the graph |
</details>

<details><summary><code>backend/app/</code> top level</summary>

| Function | What it does |
|---|---|
| `pipeline.analyze_document` | Chunks → workflow → save → Qdrant → Neo4j |
| `jobs.enqueue` | Redis queue, or `False` so the API runs the job itself |
| `jobs.run_analysis_job` | Runs one job and keeps its progress up to date |
| `api.deps.next_requirement_code` | Next free REQ-NNN in a project |
</details>

## Approaches compared

| Task | Tested | In use | Deciding metric | Result |
|---|---|---|---|---|
| Extraction | Text rules, qwen3:8b | qwen3:8b with rules as fallback | Recall at equal precision | TBD |
| Conflicts | Number rules, embeddings + qwen3:8b | Both together | Found / missed planted conflicts | TBD |

## Hardware and run times

| Machine | Used for |
|---|---|
| HP Victus, RTX 4060 8 GB, 16 GB RAM, Ubuntu 24.04 | Development and AI runs |

Analysis and chat times: TBD. Minimum: any machine with Docker for `cpu_laptop`; an 8 GB NVIDIA GPU for `gpu_laptop`.

## Limitations
- Only the first 40 chunks of a document are analyzed (`analysis.max_chunks`).
- The text rules only find sentences with modal verbs (shall, must, should, will, may, could, needs to).
- No OCR: scanned PDFs give no text.
- Anyone who types an existing company name at signup joins that company.
- Database tables are created on start; there are no migrations, so a changed column needs a reset (`docker compose down -v`).
- The old Next.js pages call the old API paths and will be replaced.

## Troubleshooting

| Problem | Fix |
|---|---|
| `DATABASE_URL is not set` | `cp .env.example .env` in the repo root |
| `connection refused` on port 5432 | `docker compose up -d` |
| Job stays at "Waiting for the worker" | Start `python -m scripts.run_worker`, or set `redis.enabled: false` |
| Job message says text rules were used | Ollama is not running: `sudo systemctl start ollama`, then `python -m scripts.check_services` |
| `missing models` from check_services | `python -m scripts.download_weights` |
| Ollama out of memory | Lower `ollama.num_ctx`, close other GPU programs |
| Container cannot reach Ollama | Set `OLLAMA_HOST=0.0.0.0` for the Ollama service (see Docker section) |
| `pull access denied for minio/minio` | The official image is gone; `docker-compose.yml` uses `pgsty/silo`. Run `git pull` |
| Port already in use | `docker compose down`, or stop the other program on that port |
| Graph `source` is `database` | Neo4j is off or down; `docker compose --profile ai up -d neo4j` |

## Citations
- Qwen Team. *Qwen3 Technical Report*, 2025. https://arxiv.org/abs/2505.09388
- Nussbaum et al. *Nomic Embed: Training a Reproducible Long Context Text Embedder*, 2024. https://arxiv.org/abs/2402.01613
- Lewis et al. *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*, 2020. https://arxiv.org/abs/2005.11401
- LangGraph, https://github.com/langchain-ai/langgraph. Qdrant, https://qdrant.tech. Neo4j, https://neo4j.com. Ollama, https://ollama.com.

## License
Code: MIT, see `LICENSE`. The models and tools keep their own licences (table in [Models](#models)).
