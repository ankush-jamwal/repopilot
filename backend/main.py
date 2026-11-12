import io, os, re, zipfile
from typing import TypedDict
from collections import Counter

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langgraph.graph import StateGraph, END
from pydantic import BaseModel
from qdrant_client import QdrantClient
from tree_sitter_language_pack import get_parser

load_dotenv()
MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
qdrant = QdrantClient(path="qdrant_data")

app = FastAPI(title="AI GitHub Repository Analyzer")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

LANGS = {"py": "python", "js": "javascript", "jsx": "javascript", "ts": "typescript",
         "tsx": "tsx", "java": "java", "go": "go", "rs": "rust", "c": "c", "cpp": "cpp",
         "rb": "ruby", "php": "php"}
TEXT_EXTS = set(LANGS) | {"md", "json", "yml", "yaml", "toml", "html", "css", "sh"}
SKIP = {"node_modules", ".git", "dist", "build", "venv", ".venv", "__pycache__", "vendor"}
MAX_LINES = 70


# ---------- Tree-sitter chunking ----------
def node_ranges(node):
    out = []
    for ch in node.children:
        size = ch.end_point[0] - ch.start_point[0] + 1
        if size > MAX_LINES and ch.children:
            out += node_ranges(ch)
        else:
            out.append((ch.start_point[0], ch.end_point[0]))
    return out


def chunk_file(text, ext):
    lines = text.splitlines()
    ranges = []
    if ext in LANGS:
        try:
            tree = get_parser(LANGS[ext]).parse(text.encode())
            cur = None
            for s, e in node_ranges(tree.root_node):
                if cur and e - cur[0] + 1 <= MAX_LINES:
                    cur = (cur[0], e)
                else:
                    cur and ranges.append(cur)
                    cur = (s, e)
            cur and ranges.append(cur)
        except Exception:
            ranges = []
    if not ranges:  # fallback: fixed windows
        ranges = [(i, min(i + 59, len(lines) - 1)) for i in range(0, len(lines), 60)]
    return [(s + 1, e + 1, "\n".join(lines[s:e + 1])[:4000]) for s, e in ranges]


# ---------- Indexing ----------
def parse_repo(url):
    m = re.search(r"github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", url.strip())
    if not m:
        raise HTTPException(400, "Enter a URL like https://github.com/owner/repo")
    return m.group(1), m.group(2)


def collection_for(repo):
    return "repo_" + re.sub(r"\W", "_", repo.lower())


class IndexReq(BaseModel):
    repo_url: str


@app.post("/api/index")
def index_repo(req: IndexReq):
    owner, name = parse_repo(req.repo_url)
    headers = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"} if os.getenv("GITHUB_TOKEN") else {}
    r = httpx.get(f"https://api.github.com/repos/{owner}/{name}/zipball",
                  headers=headers, follow_redirects=True, timeout=120)
    if r.status_code != 200:
        raise HTTPException(r.status_code, "Could not download that repo. Is it public?")

    docs, meta, files, langs = [], [], [], Counter()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        for info in z.infolist():
            path = info.filename.split("/", 1)[-1]
            ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
            if (info.is_dir() or ext not in TEXT_EXTS or info.file_size > 200_000
                    or any(p in SKIP for p in path.split("/")) or len(files) >= 1500):
                continue
            try:
                text = z.read(info).decode("utf-8")
            except UnicodeDecodeError:
                continue
            files.append(path)
            langs[ext] += 1
            for s, e, code in chunk_file(text, ext):
                docs.append(f"# {path}\n{code}")
                meta.append({"path": path, "start": s, "end": e, "code": code})

    if not docs:
        raise HTTPException(400, "No readable source files found.")
    col = collection_for(f"{owner}/{name}")
    if qdrant.collection_exists(col):
        qdrant.delete_collection(col)
    for i in range(0, len(docs), 64):  # embeds locally with fastembed
        qdrant.add(col, documents=docs[i:i + 64], metadata=meta[i:i + 64],
                   ids=list(range(i, min(i + 64, len(docs)))))
    return {"repo": f"{owner}/{name}", "files": len(files), "chunks": len(docs),
            "languages": dict(langs.most_common(6)), "tree": sorted(files)[:200]}


# ---------- LangGraph: retrieve -> answer ----------
class State(TypedDict):
    repo: str
    question: str
    mode: str
    hits: list
    answer: str

PROMPTS = {
    "explain": "Explain the code clearly: what functions, classes and dependencies do and how they connect.",
    "bugs": "Act as a code reviewer. Find likely bugs, risky code and edge cases, and point to related code.",
    "docs": "Write technical documentation in Markdown: overview, architecture, key modules, setup and usage.",
}

def retrieve(s: State):
    limit = 10 if s["mode"] == "docs" else 6
    res = qdrant.query(collection_name=collection_for(s["repo"]), query_text=s["question"], limit=limit)
    return {"hits": [r.metadata for r in res]}

def answer(s: State):
    ctx = "\n\n".join(
        f"[{h['path']}:{h['start']}-{h['end']}]\n" + "\n".join(
            f"{h['start'] + i}: {l}" for i, l in enumerate(h["code"].splitlines()))
        for h in s["hits"])
    system = ("You answer questions about a GitHub repository using ONLY the provided snippets. "
              "Always cite sources as `path:line` or `path:start-end`. If the snippets are not enough, say so. "
              + PROMPTS[s["mode"]])
    try:
        r = httpx.post(f"{OLLAMA_URL}/api/chat", timeout=600, json={
            "model": MODEL, "stream": False, "options": {"num_ctx": 12288},
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": f"Snippets:\n{ctx}\n\nRequest: {s['question']}"}]})
        r.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(503, f"Ollama is not reachable or model '{MODEL}' is missing. Run: ollama pull {MODEL}")
    return {"answer": r.json()["message"]["content"]}

g = StateGraph(State)
g.add_node("retrieve", retrieve)
g.add_node("answer", answer)
g.set_entry_point("retrieve")
g.add_edge("retrieve", "answer")
g.add_edge("answer", END)
graph = g.compile()


class AskReq(BaseModel):
    repo: str
    question: str = ""
    mode: str = "explain"


@app.post("/api/ask")
def ask(req: AskReq):
    if req.mode not in PROMPTS:
        raise HTTPException(400, "Unknown mode")
    q = req.question or "project overview, architecture, entry points and main modules"
    if not qdrant.collection_exists(collection_for(req.repo)):
        raise HTTPException(404, "Index this repo first.")
    out = graph.invoke({"repo": req.repo, "question": q, "mode": req.mode, "hits": [], "answer": ""})
    sources = [{"path": h["path"], "start": h["start"], "end": h["end"]} for h in out["hits"]]
    return {"answer": out["answer"], "sources": sources}
