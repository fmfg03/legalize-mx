const dashboardUrl = "/ops/api/dashboard";

const generatedAtEl = document.querySelector("#generatedAt");
const repoRootEl = document.querySelector("#repoRoot");
const topSignalsEl = document.querySelector("#topSignals");
const metricStripEl = document.querySelector("#metricStrip");
const legislationStatusEl = document.querySelector("#legislationStatus");
const legislationKpisEl = document.querySelector("#legislationKpis");
const legislationRunsEl = document.querySelector("#legislationRuns");
const legislationRunWindowEl = document.querySelector("#legislationRunWindow");
const queueCountEl = document.querySelector("#queueCount");
const queueItemsEl = document.querySelector("#queueItems");
const jurisprudenceStatusEl = document.querySelector("#jurisprudenceStatus");
const jurisprudenceKpisEl = document.querySelector("#jurisprudenceKpis");
const jurisprudenceStatesEl = document.querySelector("#jurisprudenceStates");
const jurisprudenceKindsEl = document.querySelector("#jurisprudenceKinds");
const releaseKpisEl = document.querySelector("#releaseKpis");
const releaseRowsEl = document.querySelector("#releaseRows");
const corpusKpisEl = document.querySelector("#corpusKpis");
const recentDocsEl = document.querySelector("#recentDocs");
const recentLegislationEl = document.querySelector("#recentLegislation");
const refreshButtonEl = document.querySelector("#refreshButton");

const metricCardTemplate = document.querySelector("#metricCardTemplate");
const listRowTemplate = document.querySelector("#listRowTemplate");

function fmtInt(value) {
  if (value === null || value === undefined || value === "") return "—";
  return new Intl.NumberFormat("en-US").format(Number(value));
}

function fmtDate(value) {
  if (!value) return "Unknown";
  return new Date(value).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Europe/Berlin",
  });
}

function fmtDuration(ms) {
  if (!ms && ms !== 0) return "—";
  const totalSeconds = Math.round(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes === 0) return `${seconds}s`;
  return `${minutes}m ${seconds}s`;
}

function setStatusPill(element, text, kind) {
  element.textContent = text;
  element.className = `status-pill ${kind}`;
}

function clearChildren(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function metricCard({ label, value, note }) {
  const fragment = metricCardTemplate.content.cloneNode(true);
  fragment.querySelector(".metric-label").textContent = label;
  fragment.querySelector(".metric-value").textContent = value;
  fragment.querySelector(".metric-note").textContent = note || "";
  return fragment;
}

function listRow({ title, detail, tag, meta, tagClass }) {
  const fragment = listRowTemplate.content.cloneNode(true);
  fragment.querySelector(".row-title").textContent = title;
  fragment.querySelector(".row-detail").textContent = detail || "";
  const tagEl = fragment.querySelector(".row-tag");
  tagEl.textContent = tag || "";
  tagEl.className = `row-tag ${tagClass || ""}`.trim();
  fragment.querySelector(".row-meta").textContent = meta || "";
  return fragment;
}

function renderMetrics(node, items) {
  clearChildren(node);
  items.forEach((item) => node.appendChild(metricCard(item)));
}

function renderList(node, rows, emptyText) {
  clearChildren(node);
  if (!rows.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = emptyText;
    node.appendChild(empty);
    return;
  }
  rows.forEach((row) => node.appendChild(listRow(row)));
}

function healthyLabel(kind) {
  if (kind === "healthy") return "Healthy";
  if (kind === "degraded") return "Degraded";
  return "Unknown";
}

function renderTopSignals(data) {
  renderMetrics(topSignalsEl, [
    {
      label: "Legislation queue",
      value: fmtInt(data.legislation.pending_queue.count),
      note: "Pending Diputados jobs",
    },
    {
      label: "Release receipts",
      value: fmtInt(data.releases.release_receipts_total),
      note: "Logged release decisions",
    },
    {
      label: "Grounding receipts",
      value: fmtInt(data.releases.grounding_receipts_total),
      note: "Evidence gate executions",
    },
    {
      label: "Recent jurisprudence docs",
      value: fmtInt(data.corpus.recent_documents.length),
      note: "Newest canonical JSON files",
    },
  ]);
}

function renderMetricStrip(data) {
  const docs = data.corpus.documents;
  const indexes = data.corpus.indexes;
  renderMetrics(metricStripEl, [
    {
      label: "Legislation docs",
      value: fmtInt(docs.legislation_docs),
      note: `${fmtInt(indexes.legislation_manifest_rows)} manifest rows`,
    },
    {
      label: "Jurisprudence docs",
      value: fmtInt(docs.tesis_docs + docs.precedente_docs + docs.voto_docs + docs.acuerdo_docs),
      note: `${fmtInt(indexes.jurisprudence_manifest_rows)} manifest rows`,
    },
    {
      label: "Legislation chunks",
      value: fmtInt(indexes.legislation_chunk_rows),
      note: "Retrieval units ready",
    },
    {
      label: "Jurisprudence chunks",
      value: fmtInt(indexes.jurisprudence_chunk_rows),
      note: "Grounding index surface",
    },
  ]);
}

function renderLegislation(data) {
  const pipeline = data.legislation;
  setStatusPill(legislationStatusEl, healthyLabel(pipeline.status), pipeline.status);

  const latest = pipeline.latest_cycle || {};
  const counts = pipeline.latest_batch_counts || {};
  renderMetrics(legislationKpisEl, [
    {
      label: "Last cycle",
      value: fmtDuration(latest.duration_ms),
      note: latest.finished_at ? `Finished ${fmtDate(latest.finished_at)}` : "No snapshot",
    },
    {
      label: "Processed",
      value: fmtInt(counts.processed),
      note: `${fmtInt(counts.partial)} partial / ${fmtInt(counts.error)} error`,
    },
    {
      label: "Selected",
      value: fmtInt(counts.selected_count),
      note: `${fmtInt(pipeline.pending_queue.count)} still queued`,
    },
  ]);

  legislationRunWindowEl.textContent = `${fmtInt(pipeline.recent_runs.length)} latest run records`;
  renderList(
    legislationRunsEl,
    pipeline.recent_runs.map((row) => ({
      title: row.source_id || "Unknown source",
      detail: (row.errors || []).map((entry) => `${entry.stage}: ${entry.error}`).join(" | ") || "No error details",
      tag: row.status || "unknown",
      tagClass: row.status === "ok" ? "ok" : row.status === "partial" ? "partial" : "error",
      meta: row.finished_at ? fmtDate(row.finished_at) : "No finish time",
    })),
    "No legislation runs found.",
  );

  queueCountEl.textContent = `${fmtInt(pipeline.pending_queue.count)} queued`;
  renderList(
    queueItemsEl,
    pipeline.pending_queue.items.map((row) => ({
      title: row.source_id || row.job_type || "Queued job",
      detail: row.url || "No URL",
      tag: row.job_type || "pending",
      tagClass: "pending",
      meta: `${fmtInt(row.attempt_count)} attempts`,
    })),
    "Queue is empty.",
  );
}

function renderJurisprudence(data) {
  const pipeline = data.jurisprudence;
  setStatusPill(jurisprudenceStatusEl, healthyLabel(pipeline.status), pipeline.status);

  const latest = pipeline.latest_cycle || {};
  renderMetrics(jurisprudenceKpisEl, [
    {
      label: "Last cycle",
      value: fmtDuration(latest.duration_ms),
      note: latest.finished_at ? `Finished ${fmtDate(latest.finished_at)}` : "No snapshot",
    },
    {
      label: "State files",
      value: fmtInt(pipeline.states.length),
      note: "Incremental cursors tracked",
    },
    {
      label: "Kinds in batch",
      value: fmtInt((pipeline.latest_kinds || []).length),
      note: "Kinds touched in latest cycle",
    },
  ]);

  renderList(
    jurisprudenceStatesEl,
    pipeline.states.map((row) => ({
      title: row.document_kind || "Unknown kind",
      detail: `next page ${fmtInt(row.next_page)} | completed ${String(Boolean(row.completed))}`,
      tag: row.last_status || "unknown",
      tagClass: row.last_status === "ok" ? "ok" : row.last_status === "no_items" ? "warning" : "error",
      meta: row.last_run_at ? fmtDate(row.last_run_at) : "No last run",
    })),
    "No jurisprudence state files found.",
  );

  renderList(
    jurisprudenceKindsEl,
    (pipeline.latest_kinds || []).map((row) => ({
      title: row.document_kind || "Unknown kind",
      detail: `${fmtInt(row.items)} items | source index ${row.source_index || "unknown"}`,
      tag: row.status || "unknown",
      tagClass: row.status === "ok" ? "ok" : "error",
      meta: `next page ${fmtInt(row.next_page)}`,
    })),
    "No latest jurisprudence batch details found.",
  );
}

function renderReleases(data) {
  const releases = data.releases;
  renderMetrics(releaseKpisEl, [
    {
      label: "Approved",
      value: fmtInt(releases.verdict_counts.APPROVED),
      note: `${fmtInt(releases.artifacts.approved)} artifacts stored`,
    },
    {
      label: "Blocked",
      value: fmtInt(releases.verdict_counts.BLOCKED),
      note: `${fmtInt(releases.artifacts.blocked)} artifacts stored`,
    },
    {
      label: "Bypass",
      value: fmtInt(releases.verdict_counts.BYPASS),
      note: `${fmtInt(releases.artifacts.bypass)} artifacts stored`,
    },
  ]);

  renderList(
    releaseRowsEl,
    releases.recent_releases.map((row) => ({
      title: row.request_id || row.response_type || "Release",
      detail: row.release_reason || "No reason",
      tag: row.release_verdict || "unknown",
      tagClass:
        row.release_verdict === "APPROVED"
          ? "approved"
          : row.release_verdict === "BLOCKED"
            ? "blocked"
            : "bypass",
      meta: row.created_at ? fmtDate(row.created_at) : "Unknown time",
    })),
    "No release receipts found.",
  );
}

function renderCorpus(data) {
  const docs = data.corpus.documents;
  renderMetrics(corpusKpisEl, [
    {
      label: "Tesis",
      value: fmtInt(docs.tesis_docs),
      note: "Canonical JSON docs",
    },
    {
      label: "Precedentes",
      value: fmtInt(docs.precedente_docs),
      note: "Canonical JSON docs",
    },
    {
      label: "Votos + acuerdos",
      value: fmtInt(docs.voto_docs + docs.acuerdo_docs),
      note: "Canonical JSON docs",
    },
  ]);

  renderList(
    recentDocsEl,
    data.corpus.recent_documents.map((row) => ({
      title: row.path,
      detail: `${fmtInt(row.size_bytes)} bytes`,
      tag: "doc",
      tagClass: "pending",
      meta: fmtDate(row.modified_at),
    })),
    "No recent jurisprudence docs found.",
  );

  renderList(
    recentLegislationEl,
    data.corpus.recent_legislation.map((row) => ({
      title: row.path,
      detail: `${fmtInt(row.size_bytes)} bytes`,
      tag: "markdown",
      tagClass: "pending",
      meta: fmtDate(row.modified_at),
    })),
    "No recent legislation docs found.",
  );
}

async function loadDashboard() {
  refreshButtonEl.disabled = true;
  refreshButtonEl.textContent = "Refreshing";
  try {
    const response = await fetch(dashboardUrl, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Dashboard request failed with ${response.status}`);
    }
    const data = await response.json();
    generatedAtEl.textContent = fmtDate(data.generated_at);
    repoRootEl.textContent = data.repo_root;
    renderTopSignals(data);
    renderMetricStrip(data);
    renderLegislation(data);
    renderJurisprudence(data);
    renderReleases(data);
    renderCorpus(data);
  } catch (error) {
    generatedAtEl.textContent = "Failed";
    clearChildren(metricStripEl);
    metricStripEl.appendChild(
      metricCard({
        label: "Console error",
        value: "Fetch failed",
        note: error instanceof Error ? error.message : String(error),
      }),
    );
  } finally {
    refreshButtonEl.disabled = false;
    refreshButtonEl.textContent = "Refresh snapshot";
  }
}

refreshButtonEl.addEventListener("click", () => {
  void loadDashboard();
});

void loadDashboard();
