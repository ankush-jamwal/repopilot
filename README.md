# RepoPilot: AI GitHub Repository Analyzer

Paste a public GitHub repo and ask questions about its source code. RepoPilot parses the code, indexes it, and answers with **file and line references**. It runs **100% locally and free**: no paid API keys, and your code never leaves your machine (apart from the repo download from GitHub).

<!-- Add a screenshot: ![RepoPilot screenshot](docs/screenshot.png) -->

## Features
- Connect any public GitHub repository by URL
- Understands folders and files automatically
- Splits code at function and class boundaries with **Tree-sitter**
- Generates code embeddings locally with **fastembed** and stores them in **Qdrant**
- Three modes: **Explain code**, **Find bugs**, **Write docs**
- Every answer cites `path:line` sources
- Colorful React interface with a repo sidebar and chat

## How it works
```
GitHub URL -> download zip -> Tree-sitter chunks -> embeddings -> Qdrant
Question -> LangGraph: [retrieve top chunks] -> [local LLM via Ollama] -> answer + sources
```

## Tech stack
Python, FastAPI, LangGraph, Tree-sitter, Qdrant, fastembed, Ollama, GitHub API, React (Vite), Docker.

## Requirements
- Python 3.10+, Node.js 18+
- [Ollama](https://ollama.com/download)
- About 8 GB RAM for the 3B model (use `qwen2.5-coder:7b` if you have 16 GB)
- Docker is optional

## Quick start (no Docker)

**1. Download a local model**
```bash
ollama pull qwen2.5-coder:3b
```

**2. Start the backend**
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env
uvicorn main:app --port 8000
```
Vectors are stored in `backend/qdrant_data`. Run without `--reload`, because local Qdrant allows only one process.

**3. Start the frontend** (new terminal)
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173.

## Run with Docker
```bash
cp backend/.env.example backend/.env
docker compose up --build
```
Open http://localhost:3000. Ollama must be running on your host machine.

## Configuration (`backend/.env`)
| Variable | Purpose | Default |
|---|---|---|
| `OLLAMA_MODEL` | Local model name | `qwen2.5-coder:3b` |
| `OLLAMA_URL` | Ollama server | `http://localhost:11434` |
| `QDRANT_URL` | Qdrant server. Leave unset for local-folder mode | unset |
| `GITHUB_TOKEN` | Optional, raises GitHub rate limits | empty |

## Try it
Small repos work best: `pallets/itsdangerous`, `pallets/click`, `tj/commander.js`.
Example question: "How does the Signer class sign a value?"

## Limitations
- Indexing runs in one request, with no progress bar yet
- Answers return all at once, not streamed
- Small local models are less accurate than large hosted ones
- Repos are capped at 1,500 files

## Roadmap
- [ ] Streaming answers
- [ ] Live indexing progress
- [ ] Hybrid search (keyword plus vector)
- [ ] Call-graph and dependency view

## License
MIT
