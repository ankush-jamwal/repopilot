import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

class Boundary extends React.Component {
  state = { err: null };
  static getDerivedStateFromError(err) { return { err }; }
  render() {
    if (!this.state.err) return this.props.children;
    return (
      <div style={{ padding: 32, color: "#fff", fontFamily: "monospace" }}>
        <h2>The page hit an error</h2>
        <pre style={{ whiteSpace: "pre-wrap", color: "#FFD23F" }}>{String(this.state.err.stack || this.state.err)}</pre>
        <button onClick={() => location.reload()}>Reload</button>
      </div>
    );
  }
}
createRoot(document.getElementById("root")).render(<Boundary><App /></Boundary>);
