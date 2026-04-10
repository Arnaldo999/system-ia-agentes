# AGENTS.md
Operational guide for coding agents in `INGENIERO N8N/`.
Default target is `system-ia-agentes/` unless task scope says otherwise.

## 1) Workspace map
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/`: main FastAPI backend (active, own git repo)
- `01_PROYECTOS/01_ARNALDO_AGENCIA/workflows/repo-demo/`: n8n workflow backup repo
- `electronica-web/`: Vite + React demo frontend (secondary)
- `01_PROYECTOS/01_ARNALDO_AGENCIA/workflows/ai-sandbox/pruebas_crewai/`: local CrewAI experimentation sandbox
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/legacy-cerebro-central/`: legacy FastAPI backend
- `memory/`: operational runbooks and process memory
- `.agents/skills/`: n8n-focused skill docs

Architecture rule:
- IG/FB social comment auto-replies are implemented in FastAPI (`01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/social/worker.py`), not by duplicating n8n workflows.

## 2) Mandatory reads before substantial edits
Read in this order:
1. `ai.context.json` — agente activo, proyectos, infraestructura
2. `memory/ESTADO_ACTUAL.md` — estado del ecosistema
3. `02_OPERACION_COMPARTIDA/handoff/ULTIMA_SESION.md` — qué quedó pendiente
4. `CLAUDE.md` — reglas del proyecto (obligatorio)
5. Si aplica: `01_PROYECTOS/<PROYECTO>/docs/ESTADO_ACTUAL.md`

If request mentions `nuevo cliente`, `agregar cliente`, `redes sociales`, `instagram`, `facebook`, or `comentarios`, read `memory/nuevo-cliente-redes-sociales.md` first.

## 3) Build / run / lint / test commands

### 3.1 system-ia-agentes (primary backend)
Setup and run:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
Quick validation (no formal linter config detected):
```bash
python -m py_compile main.py
python -m py_compile workers/social/worker.py
```
Docker:
```bash
docker build -t system-ia-agentes .
docker run --rm -p 8000:8000 --env-file .env system-ia-agentes
```
Test status:
- No first-class pytest suite currently committed.
- New backend logic should add tests under `tests/`.
Single test command (once pytest tests exist):
```bash
pytest tests/path/test_file.py::test_case_name -q
```

### 3.2 electronica-web (secondary frontend)
Install and run:
```bash
npm install
npm run dev
```
Build and preview:
```bash
npm run build
npm run preview
```
Test status:
- `npm test` is a placeholder script and exits with error.
- No test framework currently configured.
Single test command (future convention if Vitest is added):
```bash
npx vitest run src/path/file.test.jsx -t "test name"
```

### 3.3 pruebas_crewai (sandbox)
Setup:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
Run script-based checks:
```bash
python test_basico.py
python demo_basic_restaurante.py
python demo_pro_restaurante.py
python demo_premium_restaurante.py
```
Single-test equivalent here:
```bash
python test_basico.py
```

## 4) Code style guidelines

### 4.1 Python (FastAPI workers)
- 4-space indentation.
- Keep endpoint handlers focused and small.
- Use `snake_case` for functions/variables and `UPPER_SNAKE_CASE` for constants.
- Keep Spanish business naming consistent with existing payload fields.
- Use `pydantic.BaseModel` schemas for POST payloads.
- Return structured JSON with explicit `status` (`success`, `error`, `partial`).
- Read config from environment variables.
- Set request timeouts for all external API calls.
- Catch exceptions at API boundaries and return actionable errors.

### 4.2 Imports
- Order imports: stdlib, third-party, local.
- Prefer explicit imports; avoid wildcard imports.
- Remove unused imports in touched files.

### 4.3 Formatting
- Keep lines readable (target <= 100-120 chars).
- Use trailing commas in multiline calls/literals when it improves diffs.
- Keep large prompts in triple-quoted strings with clear sections.
- Preserve language style already used by each file.

### 4.4 Types and contracts
- Add type hints for helper args/returns where practical.
- Use `Optional[...]` only when `None` is semantically valid.
- Prefer concrete containers (`list[str]`, `dict[str, Any]`) over bare `list`/`dict`.
- Validate external payload shape before nested indexing.
- Keep n8n-facing key names stable unless migration is requested.

### 4.5 Naming conventions
- Endpoint handlers should be action-oriented (for example `crear_post`).
- Internal helpers should use leading underscore (for example `_call_gemini_text`).
- DTO classes commonly use `Datos...` naming; keep consistency per worker.
- Constants should be descriptive (for example `GEMINI_TEXT_URL`).

### 4.6 Error handling and reliability
- Wrap third-party interactions in `try/except`.
- Distinguish config/init errors from runtime API errors.
- Use explicit partial-success responses (`status: partial` + `errores`).
- Avoid returning raw stack traces to API clients.

### 4.7 Security and secrets
- Never hardcode API keys, tokens, IDs, phone numbers, or credentials.
- Use environment variables only; do not commit `.env` files.
- Treat root `test*.py` scripts as potentially sensitive.

### 4.8 Frontend style (electronica-web)
- Functional React components only.
- JS identifiers in `camelCase`; component names in `PascalCase`.
- Keep presentation in `src/index.css`; avoid large inline style blocks.
- Prefer small pure helpers for repeated logic.
- Keep production API keys out of frontend code paths.

## 5) n8n + FastAPI collaboration rules
- Do not assume every automation task is an n8n workflow change.
- For social-comment flows, inspect FastAPI worker logic first.
- In n8n Code nodes, JavaScript is default unless Python is explicitly needed.
- For n8n webhook handling, payload is expected under `$json.body`.
- Validate n8n configuration before deploy (`validate_node`, `validate_workflow`).

## 6) Cursor / Copilot rules scan result
Checked paths:
- `.cursor/rules/`
- `.cursorrules`
- `.github/copilot-instructions.md`
Result in this workspace root: no matching files found.

Note: `01_PROYECTOS/01_ARNALDO_AGENCIA/workflows/gh-aw/` is a separate embedded repo with its own AGENTS/conventions; do not import them unless task scope explicitly targets `gh-aw/`.

## 7) Practical agent workflow
1. Identify target subproject and read mandatory context docs.
2. Make the smallest safe change, then run relevant validation commands.
3. Report changes, commands run, and residual risks.
When unsure, prioritize production safety and documented flows in `memory/`.
