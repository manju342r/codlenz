# CodLenz

** Understand any codebase in minutes, not hours.
CodeLens is an AI-powered codebase exploration assistant. It turns unfamiliar repositories into understandable, searchable, evidence-backed technical knowledge.

## Why CodLenz?

Joining a project with 150+ files, multiple modules and complex dependencies means hours of opening files one by one. CodeLens scans the repository and gives you a technical briefing instead.

1. **Understanding** – explains how the repository actually works.
2. **Evidence** – every answer is backed by verified source-code references.
3. **Conversational Analysis** – ask follow-up questions without any manually searching files.

## Features

| Feature | Purpose |
| --- | --- |
| Repository scanning | Analyze local and remote repositories |
| Project overview | Explain what the project does |
| Architecture analysis | Explain frontend, backend and integrations |
| Technology detection | Identify languages and frameworks |
| Component analysis | Explain important files and modules |
| Execution flow | Trace how parts interact |
| AI Q&A | Ask questions about the codebase |
| Source citations | Show where answers came from |
| Text briefing | Concise bullet-point reports |
| Audio briefing | Listen to the summary (TTS) |

## How It Works

1. **Repository input** – local directory or GitHub URL
2. **Code scanner** – scans files, folders and source code
3. **AI analysis** – Ollama + Gemma (primary model)
4. **Evidence verification** – checks answers against real source references
5. **Output** – text report, audio report, and Q&A

## Usage

```bash
codelens analyze https://github.com/example/project
```

Example output:

```
PROJECT OVERVIEW
- Full-stack web application
- React frontend, Python backend

ARCHITECTURE
- Frontend handles user interactions
- Backend processes requests

EXECUTION FLOW
- User submits request -> frontend calls API -> backend responds
```

Then ask things like:

- Where is user authentication implemented?
- How does the frontend communicate with backend services
- Where should I add a new feature?
- What is the execution path for user login 

## Technology Stack

| Technology | Role |
| --- | --- |
| Python | Core app and CLI |
| Click | Command-line interface |
| Ollama | Local AI model runtime |
| Gemma 3 4B | Primary model |
| Existing Ollama model | Fallback model |
| Git CLI | Clone remote repositories |
| Retrieval system | Find relevant source code | | Validate source references |
| HTML/CSS/JS | Demo interface |
| Text-to-speech | Read analysis aloud |

## Who Is It For?

Non technical people,New developers, open-source contributors, engineers on legacy code, teams onboarding members, students, and technical reviewers.

