"""
Skills registry — defines detectable skills and their code indicators.

Each skill has a list of indicators. An indicator matches if any of its
regex patterns are found in files matching any of its globs.

Scoring uses indicator diversity (how many different types matched),
file breadth (how many files), and project breadth (how many top-level
sub-directories) — NOT raw match counts.
"""

BUILTIN_SKILLS: list[dict] = [

    # =========================================================
    # DOMAIN 1 — AI & AGENTIC SYSTEMS
    # =========================================================
    {
        "domain": "AI & Agentic Systems",
        "name": "Prompt Engineering",
        "indicators": [
            {
                "name": "copilot/agent instructions file",
                "existence_globs": ["copilot-instructions.md", ".cursorrules", "AGENTS.md", "system_prompt.txt"],
            },
            {
                "name": "system role / system message in code",
                "patterns": [r'role["\s]*:?\s*["\']?system', r'SystemMessage\(', r'system_prompt'],
                "globs": ["*.py", "*.ts", "*.js"],
            },
            {
                "name": "structured prompt template",
                "patterns": [r'f["\'].*\{[a-z_]+\}', r'\.format\(', r'prompt\s*[+=]'],
                "globs": ["*.py"],
            },
            {
                "name": "AI SDK / API call",
                "patterns": [r'anthropic|openai|claude-|gpt-4|gemini', r'chat\.completions\.create', r'messages\.create'],
                "globs": ["*.py", "*.ts", "*.js", "*.env*", "*.toml", "requirements*.txt"],
            },
            {
                "name": "prompt documentation / teaching",
                "patterns": [r'## (Prompt|System|Instructions|Context)', r'prompt engineer', r'context window'],
                "globs": ["*.md"],
                "is_teaching": True,
            },
        ],
    },

    {
        "domain": "AI & Agentic Systems",
        "name": "Model Selection & Token Economics",
        "indicators": [
            {
                "name": "model name references",
                "patterns": [r'claude-[a-z0-9-]+', r'gpt-4[a-z0-9-]*', r'haiku|sonnet|opus', r'model\s*=\s*["\']'],
                "globs": ["*.py", "*.ts", "*.md", "*.json"],
            },
            {
                "name": "token counting / budgeting",
                "patterns": [r'max_tokens|token_count|input_tokens|output_tokens', r'context_window', r'token.*cost'],
                "globs": ["*.py", "*.ts", "*.md"],
            },
            {
                "name": "prompt caching",
                "patterns": [r'cache_control|prompt_caching|CacheControl'],
                "globs": ["*.py", "*.ts"],
            },
            {
                "name": "model routing logic",
                "patterns": [r'if.*haiku|elif.*sonnet|select.*model', r'model_router', r'choose_model'],
                "globs": ["*.py"],
            },
        ],
    },

    {
        "domain": "AI & Agentic Systems",
        "name": "RAG (Retrieval-Augmented Generation)",
        "indicators": [
            {
                "name": "RAG / retrieval code",
                "patterns": [r'retriev|rag[_ ]|vector.stor|embed(ding)?s?', r'chroma|pinecone|faiss|weaviate'],
                "globs": ["*.py"],
            },
            {
                "name": "grounding context from external source",
                "patterns": [r'grounding|context_doc|source_document|fetch.*context', r'sharepoint.*context|context.*sharepoint'],
                "globs": ["*.py", "*.md"],
            },
            {
                "name": "rag.py or retrieval module",
                "existence_globs": ["rag.py", "retrieval.py", "vector_store.py"],
            },
            {
                "name": "SharePoint as live data context",
                "patterns": [r'fetch_sharepoint|sharepoint.*list|graph.*sites', r'grounding.*list|list.*grounding'],
                "globs": ["*.py"],
            },
        ],
    },

    {
        "domain": "AI & Agentic Systems",
        "name": "Agent Architecture & MCP",
        "indicators": [
            {
                "name": "MCP server pattern",
                "patterns": [r'from mcp |import mcp|mcp\.server|@mcp\.|MCPServer', r'tool_name.*tool_description'],
                "globs": ["*.py", "*.ts"],
            },
            {
                "name": "tool definition / registration",
                "patterns": [r'@tool|tool_registry|register_tool|def.*tool.*\(', r'"type":\s*"function"'],
                "globs": ["*.py", "*.ts", "*.json"],
            },
            {
                "name": "agent loop / orchestration",
                "patterns": [r'while.*agent|agent_loop|run_agent|invoke_agent', r'ToolUseBlock|tool_use.*type'],
                "globs": ["*.py"],
            },
            {
                "name": "MCP or agent config file",
                "existence_globs": ["mcp_config.json", "mcp-config.json", ".mcp.json"],
            },
        ],
    },

    # =========================================================
    # DOMAIN 2 — PYTHON & SOFTWARE DEVELOPMENT
    # =========================================================
    {
        "domain": "Python & Development",
        "name": "Async Programming",
        "indicators": [
            {
                "name": "async function definitions",
                "patterns": [r'\basync def \w+'],
                "globs": ["*.py"],
            },
            {
                "name": "await expressions",
                "patterns": [r'\bawait\b'],
                "globs": ["*.py"],
            },
            {
                "name": "asyncio usage",
                "patterns": [r'asyncio\.(run|gather|create_task|sleep)', r'import asyncio'],
                "globs": ["*.py"],
            },
            {
                "name": "async HTTP / IO library",
                "patterns": [r'import (aiohttp|aiofiles|aiosqlite|httpx)', r'from (aiohttp|httpx|aiofiles|aiosqlite)'],
                "globs": ["*.py"],
            },
        ],
    },

    {
        "domain": "Python & Development",
        "name": "FastAPI / REST API Design",
        "indicators": [
            {
                "name": "FastAPI import and app",
                "patterns": [r'from fastapi import', r'app\s*=\s*FastAPI\('],
                "globs": ["*.py"],
            },
            {
                "name": "route decorators",
                "patterns": [r'@(app|router)\.(get|post|put|delete|patch)\('],
                "globs": ["*.py"],
            },
            {
                "name": "API Router / dependency injection",
                "patterns": [r'APIRouter\(', r'Depends\(', r'HTTPException'],
                "globs": ["*.py"],
            },
            {
                "name": "REST client (requests/httpx)",
                "patterns": [r'import (requests|httpx)', r'requests\.(get|post|put|delete)', r'httpx\.(get|post|AsyncClient)'],
                "globs": ["*.py"],
            },
        ],
    },

    {
        "domain": "Python & Development",
        "name": "Pydantic Data Modeling",
        "indicators": [
            {
                "name": "BaseModel definition",
                "patterns": [r'class \w+\(BaseModel\)', r'from pydantic import'],
                "globs": ["*.py"],
            },
            {
                "name": "Field with description/validation",
                "patterns": [r'Field\(', r'= Field\(description=', r'validator\(', r'field_validator'],
                "globs": ["*.py"],
            },
            {
                "name": "model_validator / computed_field",
                "patterns": [r'@model_validator', r'@computed_field', r'model_config'],
                "globs": ["*.py"],
            },
        ],
    },

    {
        "domain": "Python & Development",
        "name": "Testing with pytest",
        "indicators": [
            {
                "name": "test files exist",
                "existence_globs": ["test_*.py", "*_test.py"],
            },
            {
                "name": "pytest imports and fixtures",
                "patterns": [r'import pytest', r'@pytest\.(fixture|mark|parametrize)', r'conftest\.py'],
                "globs": ["*.py"],
            },
            {
                "name": "assertions and mocking",
                "patterns": [r'\bassert\b.*==', r'from unittest.mock import', r'mocker\.patch', r'MagicMock'],
                "globs": ["*.py"],
            },
            {
                "name": "test classes / parametrize",
                "patterns": [r'class Test\w+', r'@pytest\.mark\.parametrize', r'pytest\.raises'],
                "globs": ["*.py"],
            },
        ],
    },

    {
        "domain": "Python & Development",
        "name": "Code Quality (ruff / mypy)",
        "indicators": [
            {
                "name": "ruff config in pyproject.toml",
                "patterns": [r'\[tool\.ruff\]', r'ruff.*lint|lint.*ruff'],
                "globs": ["pyproject.toml", "*.toml"],
            },
            {
                "name": "mypy config",
                "patterns": [r'\[tool\.mypy\]', r'mypy.*strict|strict.*mypy'],
                "globs": ["pyproject.toml", "*.ini", "setup.cfg"],
            },
            {
                "name": "type annotations",
                "patterns": [r'def \w+\(.*\)\s*->', r': (str|int|float|bool|list|dict|Optional|Union|tuple)\b'],
                "globs": ["*.py"],
            },
            {
                "name": "linter or formatter in CI/requirements",
                "patterns": [r'ruff|mypy|flake8|pylint|black|isort'],
                "globs": ["requirements*.txt", "*.toml", "*.yml", "*.yaml"],
            },
        ],
    },

    {
        "domain": "Python & Development",
        "name": "Docker / Containerization",
        "indicators": [
            {
                "name": "Dockerfile exists",
                "existence_globs": ["Dockerfile", "Dockerfile.*"],
            },
            {
                "name": "docker-compose config",
                "existence_globs": ["docker-compose.yml", "docker-compose.yaml"],
            },
            {
                "name": "Docker instructions in Dockerfile",
                "patterns": [r'^FROM\s+', r'^RUN\s+', r'^COPY\s+', r'^ENTRYPOINT\s+'],
                "globs": ["Dockerfile", "Dockerfile.*"],
            },
            {
                "name": "container build/run commands",
                "patterns": [r'docker (build|run|push|pull|compose)', r'docker_image|container_name'],
                "globs": ["*.sh", "*.ps1", "*.yml", "*.yaml", "*.md"],
            },
        ],
    },

    {
        "domain": "Python & Development",
        "name": "GraphQL (Strawberry)",
        "indicators": [
            {
                "name": "Strawberry type definition",
                "patterns": [r'import strawberry', r'@strawberry\.(type|mutation|query|input)', r'strawberry\.Schema'],
                "globs": ["*.py"],
            },
            {
                "name": "GraphQL schema / field",
                "patterns": [r'graphql|gql|GraphQL', r'strawberry\.field', r'resolver'],
                "globs": ["*.py"],
            },
            {
                "name": "GraphQL query / mutation string",
                "patterns": [r'query\s+\w+\s*\{', r'mutation\s+\w+', r'graphql.*endpoint'],
                "globs": ["*.py", "*.ts", "*.graphql"],
            },
        ],
    },

    {
        "domain": "Python & Development",
        "name": "SQLite & Data Storage",
        "indicators": [
            {
                "name": "sqlite3 or aiosqlite usage",
                "patterns": [r'import sqlite3', r'import aiosqlite', r'aiosqlite\.connect', r'sqlite3\.connect'],
                "globs": ["*.py"],
            },
            {
                "name": "SQL statements",
                "patterns": [r'CREATE TABLE', r'INSERT INTO', r'SELECT .* FROM', r'UPDATE .* SET'],
                "globs": ["*.py", "*.sql"],
            },
            {
                "name": "caching strategy",
                "patterns": [r'cache|TTL|time_to_live|LRU', r'sqlite.*cache|cache.*sqlite'],
                "globs": ["*.py", "*.md"],
            },
        ],
    },

    {
        "domain": "Python & Development",
        "name": "OOP & Data Science",
        "indicators": [
            {
                "name": "class definition with constructor",
                "patterns": [r'class \w+.*:', r'def __init__\(self'],
                "globs": ["*.py"],
            },
            {
                "name": "inheritance and method override",
                "patterns": [r'class \w+\(\w+\)', r'super\(\)\.__init__', r'def \w+\(self.*\).*#.*override'],
                "globs": ["*.py"],
            },
            {
                "name": "pandas / data analysis",
                "patterns": [r'import pandas|from pandas', r'pd\.read_csv|\.DataFrame|\.iterrows\(\)', r'\.head\(\)'],
                "globs": ["*.py", "*.ipynb"],
            },
            {
                "name": "list comprehensions / functional patterns",
                "patterns": [r'\[.+ for .+ in .+\]', r'map\(|filter\(|reduce\('],
                "globs": ["*.py"],
            },
        ],
    },

    {
        "domain": "Python & Development",
        "name": "ML Environments (PyTorch / fast.ai)",
        "indicators": [
            {
                "name": "PyTorch import",
                "patterns": [r'import torch', r'from torch', r'torch\.nn|torch\.optim'],
                "globs": ["*.py", "*.ipynb"],
            },
            {
                "name": "fast.ai usage",
                "patterns": [r'from fastai|import fastai', r'DataBlock|learn\.fine_tune|cnn_learner'],
                "globs": ["*.py", "*.ipynb"],
            },
            {
                "name": "Jupyter / notebook",
                "existence_globs": ["*.ipynb"],
            },
            {
                "name": "ML debugging / environment setup",
                "patterns": [r'ipykernel|jupyter.*kernel|\.venv.*torch', r'CPU.*build|torch.*whl'],
                "globs": ["*.py", "*.md", "*.txt"],
            },
        ],
    },

    {
        "domain": "Python & Development",
        "name": "Security & Authentication",
        "indicators": [
            {
                "name": "MSAL / OAuth authentication",
                "patterns": [r'import msal|from msal', r'device_flow|device_code_flow|SerializableTokenCache', r'OAuth|oauth2'],
                "globs": ["*.py", "*.ps1"],
            },
            {
                "name": "DPAPI / encrypted token storage",
                "patterns": [r'DPAPI|CryptProtectData|CryptUnprotectData', r'Protect.*Data|Unprotect.*Data'],
                "globs": ["*.py", "*.ps1"],
            },
            {
                "name": "secrets management (.env / dotenv)",
                "patterns": [r'from dotenv|import dotenv|load_dotenv', r'os\.getenv\(|os\.environ\['],
                "globs": ["*.py"],
            },
            {
                "name": ".env.sample or .gitignore secrets pattern",
                "existence_globs": [".env.sample", ".env.template"],
            },
        ],
    },

    {
        "domain": "Python & Development",
        "name": "Encryption & FISMA Controls",
        "indicators": [
            {
                "name": "Fernet symmetric encryption",
                "patterns": [r'from cryptography.fernet import|Fernet\.generate_key', r'fernet\.encrypt|fernet\.decrypt'],
                "globs": ["*.py"],
            },
            {
                "name": "key rotation logic",
                "patterns": [r'key_rotat|rotate_key|re.encrypt', r'generate.*key.*encrypt'],
                "globs": ["*.py"],
            },
            {
                "name": "audit trail logging",
                "patterns": [r'audit\.db|audit_log|audit_trail', r'logging\..*AUDIT|logger.*audit'],
                "globs": ["*.py"],
            },
            {
                "name": "RBAC / role-based access",
                "patterns": [r'RBAC|role.*based|user_role', r'admin.*role|staff.*role', r'check_permission|has_permission'],
                "globs": ["*.py"],
            },
        ],
    },

    # =========================================================
    # DOMAIN 3 — MICROSOFT 365 & GRAPH API
    # =========================================================
    {
        "domain": "Microsoft 365 & Graph API",
        "name": "Microsoft Graph API",
        "indicators": [
            {
                "name": "Graph API endpoint in code",
                "patterns": [r'graph\.microsoft\.com', r'https://graph\.microsoft', r'/v1\.0/'],
                "globs": ["*.py", "*.ps1"],
            },
            {
                "name": "MSAL authentication for Graph",
                "patterns": [r'PublicClientApplication|ConfidentialClientApplication', r'acquire_token.*device_flow'],
                "globs": ["*.py"],
            },
            {
                "name": "Graph API module / client",
                "existence_globs": ["graph_auth.py", "graph_client.py", "*graph*.py"],
            },
            {
                "name": "token cache persistence",
                "patterns": [r'SerializableTokenCache|token_cache', r'cache.*load|load.*cache'],
                "globs": ["*.py"],
            },
        ],
    },

    {
        "domain": "Microsoft 365 & Graph API",
        "name": "SharePoint Integration",
        "indicators": [
            {
                "name": "SharePoint list operations",
                "patterns": [r'sharepoint|SharePoint', r'/lists/|/items/', r'siteId|listId'],
                "globs": ["*.py", "*.ps1"],
            },
            {
                "name": "paginated list retrieval",
                "patterns": [r'@odata\.nextLink|nextLink|odata\.skip', r'paginate|get_all_items'],
                "globs": ["*.py"],
            },
            {
                "name": "People field / user lookup",
                "patterns": [r'LookupId|User Information List|people.*field', r'resolve.*user|user.*lookup'],
                "globs": ["*.py"],
            },
            {
                "name": "SharePoint column provisioning",
                "patterns": [r'create.*column|idempotent.*pipeline|column.*provision', r'DiagramUrl|ensure.*column'],
                "globs": ["*.py"],
            },
        ],
    },

    {
        "domain": "Microsoft 365 & Graph API",
        "name": "PowerShell Scripting",
        "indicators": [
            {
                "name": "PowerShell script files",
                "existence_globs": ["*.ps1"],
            },
            {
                "name": "PowerShell advanced functions",
                "patterns": [r'\[CmdletBinding\]|\[Parameter\(', r'param\s*\(', r'Write-Host|Write-Output'],
                "globs": ["*.ps1"],
            },
            {
                "name": "Error handling in PS",
                "patterns": [r'try\s*\{', r'catch\s*\{', r'\$ErrorActionPreference'],
                "globs": ["*.ps1"],
            },
            {
                "name": "PowerShell VS Code tasks",
                "patterns": [r'"type":\s*"shell".*ps1|ps1.*"type":\s*"shell"', r'powershell.*-File'],
                "globs": ["tasks.json", "*.json"],
            },
        ],
    },

    {
        "domain": "Microsoft 365 & Graph API",
        "name": "GitHub Actions / CI Workflows",
        "indicators": [
            {
                "name": "GitHub Actions workflow file",
                "existence_globs": [".github/workflows/*.yml", ".github/workflows/*.yaml"],
            },
            {
                "name": "CI workflow steps",
                "patterns": [r'- name:', r'uses: actions/', r'run:', r'on:\s*(push|pull_request)'],
                "globs": ["*.yml", "*.yaml"],
            },
            {
                "name": "Python CI steps",
                "patterns": [r'pip install|pytest|ruff|mypy', r'Set up Python|setup-python'],
                "globs": ["*.yml", "*.yaml"],
            },
            {
                "name": "secrets / environment in CI",
                "patterns": [r'\$\{\{ secrets\.', r'env:\s*\n.*:\s*\$\{\{'],
                "globs": ["*.yml", "*.yaml"],
            },
        ],
    },

    # =========================================================
    # DOMAIN 4 — ENTERPRISE ARCHITECTURE & OBSERVABILITY
    # =========================================================
    {
        "domain": "Enterprise Architecture & Observability",
        "name": "ServiceNow & ITSM",
        "indicators": [
            {
                "name": "ServiceNow client / API",
                "patterns": [r'servicenow|ServiceNow|snow_client|sn_client'],
                "globs": ["*.py"],
            },
            {
                "name": "ITSM record queries",
                "patterns": [r'change_request|incident|cmdb_ci|sys_id', r'table_api|/api/now/'],
                "globs": ["*.py"],
            },
            {
                "name": "async ServiceNow with semaphore",
                "patterns": [r'asyncio\.Semaphore|semaphore.*ServiceNow|concurrent.*snow'],
                "globs": ["*.py"],
            },
            {
                "name": "ServiceNow client module",
                "existence_globs": ["sn_client.py", "snow_client.py", "*servicenow*.py"],
            },
        ],
    },

    {
        "domain": "Enterprise Architecture & Observability",
        "name": "KPI Design & Dashboards",
        "indicators": [
            {
                "name": "KPI definition in code",
                "patterns": [r'\bkpi\b|KPI|key.*performance|performance.*indicator'],
                "globs": ["*.py", "*.md", "*.json"],
            },
            {
                "name": "dashboard / HTML output",
                "patterns": [r'dashboard|HTML.*dashboard|serve.*static', r'<!DOCTYPE html|<html'],
                "globs": ["*.py", "*.html"],
            },
            {
                "name": "tier classification",
                "patterns": [r'tier\s*[12]|Tier.*classification|u_tier', r'tier_map|ci_tier'],
                "globs": ["*.py", "*.json"],
            },
            {
                "name": "signal emission / metric tracking",
                "patterns": [r'signal_emission|coverage.*tier|tier.*coverage', r'emit.*signal|metric.*emit'],
                "globs": ["*.py", "*.md"],
            },
        ],
    },

    {
        "domain": "Enterprise Architecture & Observability",
        "name": "SRE Observability (Four Golden Signals)",
        "indicators": [
            {
                "name": "latency tracking",
                "patterns": [r'latency|response_time|request_duration|HISTOGRAM|p95|p99|percentile'],
                "globs": ["*.py", "*.yml", "*.yaml"],
            },
            {
                "name": "traffic / throughput metric",
                "patterns": [r'requests_total|request_count|Counter\(|throughput|requests_per_second'],
                "globs": ["*.py"],
            },
            {
                "name": "error rate tracking",
                "patterns": [r'error_rate|errors_total|probe_up|failure_type|HTTP.*5[0-9]{2}|status.*error'],
                "globs": ["*.py"],
            },
            {
                "name": "saturation metric",
                "patterns": [r'Gauge\(|cpu_util|memory_usage|saturation|resource.*util|utilization'],
                "globs": ["*.py"],
            },
            {
                "name": "prometheus / metrics endpoint",
                "patterns": [r'prometheus_client|generate_latest|/metrics', r'start_http_server|REGISTRY'],
                "globs": ["*.py"],
            },
            {
                "name": "golden signals documentation",
                "patterns": [r'golden signal|latency.*traffic|four.*signal|SRE.*signal|saturation'],
                "globs": ["*.md"],
                "is_teaching": True,
            },
        ],
    },

    {
        "domain": "Enterprise Architecture & Observability",
        "name": "Enterprise GitHub CI/CD (CaaS + Conjur)",
        "indicators": [
            {
                "name": "reusable workflow (workflow_call)",
                "patterns": [r'workflow_call', r'uses:\s*\./.github/workflows/'],
                "globs": ["*.yml", "*.yaml"],
            },
            {
                "name": "Conjur PAM secrets fetch",
                "patterns": [r'conjur-fetch|conjur.*fetch|CONJUR_HOST|FMSPAMVLT'],
                "globs": ["*.yml", "*.yaml"],
            },
            {
                "name": "Kaniko container build",
                "patterns": [r'kaniko|gasp\.kaniko', r'no_cache.*true|amr-registry\.caas'],
                "globs": ["*.yml", "*.yaml"],
            },
            {
                "name": "kubectl CaaS deployment",
                "patterns": [r'kubectl.*apply|kubectl.*config.*use-context', r'caas.*cluster|CAAS_CLUSTER'],
                "globs": ["*.yml", "*.yaml"],
            },
            {
                "name": "matrix deployment environments",
                "patterns": [r'matrix:', r'fromJson.*DEPLOYMENT_ENVIRONMENTS', r'strategy:\s*\n.*matrix'],
                "globs": ["*.yml", "*.yaml"],
            },
            {
                "name": "Semgrep / SAST in CI",
                "patterns": [r'semgrep|SEMGREP_APP_TOKEN|semgrep-auto-tag|SAST'],
                "globs": ["*.yml", "*.yaml"],
            },
            {
                "name": "post-deploy notification (Squawker)",
                "patterns": [r'squawk|squawker|squawk_iap|squawk_team'],
                "globs": ["*.yml", "*.yaml"],
            },
        ],
    },

    # =========================================================
    # DOMAIN 5 — SECURITY & COMPLIANCE
    # =========================================================
    {
        "domain": "Security & Compliance",
        "name": "Secrets Management",
        "indicators": [
            {
                "name": ".env.sample pattern",
                "existence_globs": [".env.sample", ".env.template"],
            },
            {
                "name": ".gitignore with secrets patterns",
                "patterns": [r'\.env$|\.env\.\w+', r'token.*\.json|credentials|secrets'],
                "globs": [".gitignore"],
            },
            {
                "name": "load_dotenv in code",
                "patterns": [r'load_dotenv\(|from dotenv import', r'os\.getenv\(|os\.environ\.get\('],
                "globs": ["*.py"],
            },
            {
                "name": "no-hardcoded-secrets discipline",
                "patterns": [r'# (no|never) .*secret|# .*gitignore.*secret', r'secret.*env|env.*secret'],
                "globs": ["*.md", "copilot-instructions.md"],
                "is_teaching": True,
            },
        ],
    },

    {
        "domain": "Security & Compliance",
        "name": "AI-Assisted Code Security",
        "indicators": [
            {
                "name": "security review in copilot instructions",
                "patterns": [r'security|vuln|injection|sanitize|secret', r'review.*security|security.*review'],
                "globs": ["copilot-instructions.md", "*.md"],
            },
            {
                "name": "input validation / sanitization",
                "patterns": [r'validate|sanitize|escape\(', r'raise.*HTTPException.*4[0-9]{2}'],
                "globs": ["*.py"],
            },
            {
                "name": "dependency scanning or security tooling",
                "patterns": [r'bandit|safety|pip-audit|snyk', r'security.*scan|scan.*security'],
                "globs": ["requirements*.txt", "*.toml", "*.yml"],
            },
        ],
    },

    # =========================================================
    # DOMAIN 6 — LEADERSHIP, COMMUNICATION & OPERATIONS
    # =========================================================
    {
        "domain": "Leadership & Communication",
        "name": "Technical Documentation",
        "indicators": [
            {
                "name": "README or technical docs",
                "existence_globs": ["README.md", "README.rst", "docs/*.md"],
            },
            {
                "name": "copilot-instructions / architecture doc",
                "existence_globs": ["copilot-instructions.md"],
            },
            {
                "name": "inline prompt audit trail",
                "patterns": [r'# prompt:|# Prompt:', r'# AI generated|# generated by'],
                "globs": ["*.py", "*.ipynb"],
            },
            {
                "name": "project diagram or architecture doc",
                "existence_globs": ["*.drawio", "architecture*.md", "Graph-API*.md"],
            },
        ],
    },

    {
        "domain": "Leadership & Communication",
        "name": "Standards & Best Practices Enforcement",
        "indicators": [
            {
                "name": "linting/formatting enforced in CI",
                "patterns": [r'ruff check|mypy|flake8|pylint', r'lint.*on.*push|push.*lint'],
                "globs": ["*.yml", "*.yaml"],
            },
            {
                "name": "standards defined in copilot instructions",
                "patterns": [r'standard|convention|best.practice|must (use|have|include)', r'Domain \d\d|## Domain'],
                "globs": ["copilot-instructions.md", "*.md"],
                "is_teaching": True,
            },
            {
                "name": "coding standards document",
                "existence_globs": ["CONTRIBUTING.md", "STANDARDS.md", "coding-standards*.md"],
            },
            {
                "name": "audit/history logging pattern",
                "patterns": [r'history\.jsonl|audit_log|execution.*log', r'jsonl.*append|append.*jsonl'],
                "globs": ["*.py", "*.ps1"],
            },
        ],
    },
]

