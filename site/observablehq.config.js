// The site is a reader of the archive directory, like a DuckDB shell would be:
// its one data loader shapes ../runs into a zip, and the pages query that in
// the browser. The loader runs under the repository's own Python environment.
import {readFileSync, readdirSync} from "node:fs";

// The banner's numbers are counted here, at build time, so they cannot drift.
const lines = (...files) => files.reduce((n, f) => n + readFileSync(new URL(f, import.meta.url), "utf8").split("\n").length - 1, 0);
const site = readdirSync(new URL("./src", import.meta.url)).filter((f) => f.endsWith(".md") || f.endsWith(".py")).map((f) => `./src/${f}`);
const model = lines("../models/pathway.yaml");
const job = lines("../src/showcase/scenarios.py", "../src/showcase/solve.py", "../src/showcase/warehouse.py");
const pages = lines(...site, "./src/data/runs.zip.py", "./src/data/grid.zip.py", "./src/perspective.css.js", "./src/perspective.js.js", "./src/components/palette.js", "./src/components/format.js", "./src/components/pivot.js", "./src/components/steady.js");
const notebook = lines("../notebooks/session.py");

export default {
  title: "Pathway planner",
  root: "src",
  theme: "dashboard",
  toc: false,
  pages: [
    {name: "What if", path: "/whatif"},
    {name: "Model", path: "/model"},
    {name: "Annex", path: "/annex"},
    {name: "Dispatch", path: "/dispatch"},
    {name: "Explore", path: "/explore"},
    {name: "Clients", path: "/clients"},
    {name: "Provenance", path: "/provenance"},
    {name: "Session", path: "/session"},
  ],
  interpreters: {
    ".py": ["uv", "run", "--project", "..", "python"],
  },
  header: `<div style="border: 1px solid var(--theme-foreground-faintest); border-radius: 8px; padding: 0.6rem 1rem; margin-bottom: 1.5rem; font-size: 0.9rem; line-height: 1.5;">
    <strong>An example of what you build on <a href="https://github.com/fluxopt/specsolve">specsolve</a>.</strong>
    A capacity-expansion planner: the model is ${model} lines of YAML, the job that solves and archives it ${job} lines of Python,
    this site ${pages} lines of Markdown and SQL over the parquet the job wrote, and the notebook ${notebook} lines.
    All of it is in <a href="https://github.com/fluxopt/specsolve-showcase">the source</a>; nothing else is behind it.
  </div>`,
  footer: `An example application built on <a href="https://github.com/fluxopt/specsolve">specsolve</a> · <a href="https://github.com/fluxopt/specsolve-showcase">source</a>`,
};
