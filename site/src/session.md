---
title: Session
---

# A modelling session

The other pages are what specsolve produces unattended: a job solves, archives, and this site reads the archive. This page is the other half of the story, a [marimo](https://marimo.io) notebook in which the model is a document you edit by hand. Change the YAML and the typeset math, the validation and the solve follow. Change a number in the data table, or move a slider under the pathway, and the charts re-solve.

**It runs in your browser.** Python, the HiGHS solver, polars and specsolve itself load as WebAssembly, so nothing runs on a server and there is nothing to install. The first load fetches about 40 MB and takes a moment; after that every edit to the model, the data or the sliders re-solves on your machine. The code stays out of sight; edit mode, linked below, shows it and lets you change it.

**It needs memory.** After a solve the tab holds about 1 GB, measured in Chromium. A desktop browser takes that in its stride; a phone browser does not, and will reload the page rather than run it. The [What if](./whatif) page answers the pathway's two sliders without any of that, from archives the job solved ahead of time.

```js
const app = "./session-app/index.html";
const phone = matchMedia("(max-width: 700px)").matches;
const launch = phone ? 0 : view(Inputs.button("Run the notebook here, in this page", {value: 0, reduce: (n) => n + 1}));
```

${phone ? html`<p><strong>On a phone, this is the still picture.</strong> The live notebook needs more memory than a phone browser gives one tab, which shows as the page reloading. The notebook below is the same session as it ran at the last build, outputs included; open this page on a desktop to run it.</p>` : html`<p><a href="${app}" target="_blank">Open it in its own tab ↗</a> · <a href="./session-edit/index.html" target="_blank">open it in edit mode ↗</a></p>`}

${launch ? html`<iframe src="${app}" title="The modelling session, running in your browser" style="width: 100%; height: 2400px; border: 1px solid var(--theme-foreground-faintest); border-radius: 8px; background: white;"></iframe>` : ""}

## Run it on your machine

The notebook is [`notebooks/session.py`](https://github.com/fluxopt/specsolve-showcase/blob/main/notebooks/session.py), a plain Python file. With a local kernel you can also edit the code, not only the model and the data:

```bash
git clone https://github.com/fluxopt/specsolve-showcase && cd specsolve-showcase
uv sync --all-extras
uv run marimo edit notebooks/session.py
```

## As it ran at the last build

The same notebook, executed on the build machine and kept as a static page: outputs included, controls inert. This is the fallback, and what search engines see.

```js
const session = FileAttachment("session.html").href;
```

<p>${html`<a href="${session}" target="_blank">Open the executed notebook in its own tab ↗</a>`}</p>

${phone ? html`<iframe src="${session}" title="The modelling session, as it ran at the last build" style="width: 100%; height: 2400px; border: 1px solid var(--theme-foreground-faintest); border-radius: 8px; background: white;"></iframe>` : ""}
