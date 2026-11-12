import { useRef, useEffect, useState } from "react";
import Markdown from "react-markdown";

const MODES = [
  { id: "explain", label: "Explain code", hint: "What does the auth middleware do?" },
  { id: "bugs", label: "Find bugs", hint: "Any risky error handling in the API layer?" },
  { id: "docs", label: "Write docs", hint: "" },
];
const EXAMPLES = ["https://github.com/pallets/flask", "https://github.com/expressjs/express", "https://github.com/tiangolo/fastapi"];

async function post(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || "Something went wrong"));
  return data;
}

export default function App() {
  const [url, setUrl] = useState("");
  const [repo, setRepo] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [mode, setMode] = useState("explain");
  const [q, setQ] = useState("");
  const [chat, setChat] = useState([]);
  const end = useRef(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [chat, busy]);

  const index = async (u = url) => {
    setBusy(true); setError(""); setChat([]);
    try { setRepo(await post("/api/index", { repo_url: u })); }
    catch (e) { setError(e.message); }
    setBusy(false);
  };

  const ask = async (e) => {
    e?.preventDefault();
    if (mode !== "docs" && !q.trim()) return;
    const text = mode === "docs" ? "Generate technical documentation" : q;
    setChat((c) => [...c, { role: "user", text }]); setQ(""); setBusy(true); setError("");
    try {
      const r = await post("/api/ask", { repo: repo.repo, question: mode === "docs" ? "" : text, mode });
      setChat((c) => [...c, { role: "ai", text: String(r.answer ?? ""), sources: Array.isArray(r.sources) ? r.sources : [] }]);
    } catch (e) { setError(e.message); }
    setBusy(false);
  };

  if (!repo) return (
    <main className="hero">
      <div className="blob b1" /><div className="blob b2" />
      <div className="logo">QA</div>
      <h1>Drop a repo.<br />Interrogate every line.</h1>
      <p className="sub">Paste a public GitHub link. RepoPilot reads the whole codebase, then answers with file and line references.</p>
      <form className="bar" onSubmit={(e) => { e.preventDefault(); index(); }}>
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://github.com/owner/repo" aria-label="GitHub repository URL" />
        <button disabled={busy || !url}>{busy ? "Reading the code..." : "Analyze repo"}</button>
      </form>
      {busy && <div className="loader"><i /><i /><i /><span>Downloading, parsing with Tree-sitter, embedding. Big repos take a minute.</span></div>}
      {error && <p className="err">{error}</p>}
      <div className="chips">{EXAMPLES.map((x) => <button key={x} className="chip" onClick={() => { setUrl(x); index(x); }}>{x.replace("https://github.com/", "")}</button>)}</div>
    </main>
  );

  return (
    <div className="app">
      <aside>
        <div className="logo sm">QA</div>
        <h2>{repo.repo}</h2>
        <div className="stats"><div><b>{repo.files}</b>files</div><div><b>{repo.chunks}</b>chunks</div></div>
        <div className="chips">{Object.entries(repo.languages).map(([k, v]) => <span key={k} className="chip static">.{k} ({v})</span>)}</div>
        <ul className="tree">{repo.tree.map((f) => <li key={f}>{f}</li>)}</ul>
        <button className="ghost" onClick={() => setRepo(null)}>Switch repo</button>
      </aside>
      <section className="chat">
        <div className="msgs">
          {chat.length === 0 && <div className="empty"><h3>Pick a mode, then ask.</h3><p>Try: "{MODES[0].hint}"</p></div>}
          {chat.map((m, i) => (
            <div key={i} className={"msg " + m.role}>
              {m.role === "user" ? <p>{m.text}</p> : <>
                <Markdown>{String(m.text)}</Markdown>
                <div className="chips">{(m.sources || []).map((s, j) => <span key={j} className="chip src">{s.path}:{s.start}-{s.end}</span>)}</div>
              </>}
            </div>
          ))}
          {busy && <div className="loader"><i /><i /><i /></div>}
          {error && <p className="err">{error}</p>}
          <div ref={end} />
        </div>
        <div className="modes">{MODES.map((x) => <button key={x.id} className={mode === x.id ? "on" : ""} onClick={() => setMode(x.id)}>{x.label}</button>)}</div>
        <form className="bar" onSubmit={ask}>
          <input value={q} onChange={(e) => setQ(e.target.value)} disabled={mode === "docs"}
            placeholder={mode === "docs" ? "Docs come from the whole repo. Press the button." : MODES.find((x) => x.id === mode).hint} />
          <button disabled={busy}>{mode === "docs" ? "Generate docs" : "Ask"}</button>
        </form>
      </section>
    </div>
  );
}
