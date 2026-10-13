const state = {
  expedientes: [],
  selectedExpedienteId: null,
  selectedExpediente: null,
  agendaItems: [],
  proceduralTracks: [],
  draftSections: [],
};

// The host's OAuth session supplies a bearer in memory; actor/permissions remain server decisions.
let reviewerBearer = "";
let pendingRelease = null;
let releaseContextGeneration = 0;

function clearPendingRelease() {
  releaseContextGeneration += 1;
  pendingRelease = null;
  document.querySelector("#confirmReleaseButton").disabled = true;
  document.querySelector("#releaseGateResult").textContent = "";
}

window.addEventListener("legalize-auth-session", (event) => {
  reviewerBearer = typeof event.detail?.accessToken === "string" ? event.detail.accessToken : "";
  clearPendingRelease();
  document.querySelector("#evaluateReleaseButton").disabled = !reviewerBearer;
  document.querySelector("#releaseSessionStatus").textContent = reviewerBearer
    ? "Sesión de revisión conectada; el servidor verificará identidad y permisos."
    : "Sesión de revisión no conectada.";
});

const endpoints = {
  bootstrap: "/app-api/bootstrap",
  expedientes: "/app-api/expedientes",
  expediente: (id) => `/app-api/expedientes/${id}`,
  copilot: (id) => `/app-api/expedientes/${id}/copilot`,
  events: (id) => `/app-api/expedientes/${id}/events`,
  deadlines: (id) => `/app-api/expedientes/${id}/deadlines`,
  deadline: (id, deadlineId) => `/app-api/expedientes/${id}/deadlines/${deadlineId}`,
  drafts: (id) => `/app-api/expedientes/${id}/drafts`,
  revisions: (id) => `/app-api/expedientes/${id}/revisions`,
  defendability: (id) => `/app-api/expedientes/${id}/defendability-gate`,
  analysis: (id) => `/app-api/expedientes/${id}/analysis`,
  preflightChecklist: (id) => `/app-api/expedientes/${id}/preflight-checklist`,
  release: (id) => `/app-api/expedientes/${id}/release`,
};

const expedienteListEl = document.querySelector("#expedienteList");
const expedienteTitleEl = document.querySelector("#expedienteTitle");
const expedienteMetaEl = document.querySelector("#expedienteMeta");
const expedienteSummaryCardsEl = document.querySelector("#expedienteSummaryCards");
const partyListEl = document.querySelector("#partyList");
const deadlineListEl = document.querySelector("#deadlineList");
const deadlineUpdateSelectEl = document.querySelector("#deadlineUpdateSelect");
const documentListEl = document.querySelector("#documentList");
const timelineListEl = document.querySelector("#timelineList");
const releaseReceiptListEl = document.querySelector("#releaseReceiptList");
const releaseVersionSelectEl = document.querySelector("#releaseVersionSelect");
const copilotMessagesEl = document.querySelector("#copilotMessages");
const statusStripEl = document.querySelector("#statusStrip");
const agendaListEl = document.querySelector("#agendaList");
const procedureTrackSelectEl = document.querySelector("#procedureTrackSelect");
const preflightChecklistSummaryEl = document.querySelector("#preflightChecklistSummary");
const preflightChecklistListEl = document.querySelector("#preflightChecklistList");
const synthesisSummaryEl = document.querySelector("#synthesisSummary");
const synthesisContentEl = document.querySelector("#synthesisContent");
const draftSectionSelectEl = document.querySelector("#draftSectionSelect");
const draftSectionHelpEl = document.querySelector("#draftSectionHelp");
const revisionVersionSelectEl = document.querySelector("#revisionVersionSelect");
const revisionModeSelectEl = document.querySelector("#revisionModeSelect");
const revisionModeHintEl = document.querySelector("#revisionModeHint");
const revisionResultEl = document.querySelector("#revisionResult");
const defendabilityVersionSelectEl = document.querySelector("#defendabilityVersionSelect");
const defendabilityResultEl = document.querySelector("#defendabilityResult");

const refreshWorkspaceButtonEl = document.querySelector("#refreshWorkspaceButton");
const expedienteFormEl = document.querySelector("#expedienteForm");
const documentFormEl = document.querySelector("#documentForm");
const eventFormEl = document.querySelector("#eventForm");
const deadlineFormEl = document.querySelector("#deadlineForm");
const deadlineUpdateFormEl = document.querySelector("#deadlineUpdateForm");
const draftFormEl = document.querySelector("#draftForm");
const caseAnalysisFormEl = document.querySelector("#caseAnalysisForm");
const preflightChecklistFormEl = document.querySelector("#preflightChecklistForm");
const defendabilityFormEl = document.querySelector("#defendabilityForm");
const revisionFormEl = document.querySelector("#revisionForm");
const releaseFormEl = document.querySelector("#releaseForm");
const copilotFormEl = document.querySelector("#copilotForm");
const copilotPromptEl = document.querySelector("#copilotPrompt");
const toggleExpedienteFormButtonEl = document.querySelector("#toggleExpedienteFormButton");

const expedienteListItemTemplate = document.querySelector("#expedienteListItemTemplate");
const summaryCardTemplate = document.querySelector("#summaryCardTemplate");
const listRowTemplate = document.querySelector("#listRowTemplate");
const timelineItemTemplate = document.querySelector("#timelineItemTemplate");
const chatBubbleTemplate = document.querySelector("#chatBubbleTemplate");

function fmtDate(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("es-MX", {
    dateStyle: "medium",
    timeStyle: String(value).includes("T") ? "short" : undefined,
  });
}

function fmtInt(value) {
  if (value === null || value === undefined || value === "") return "—";
  return new Intl.NumberFormat("es-MX").format(Number(value));
}

function clearChildren(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function setStatus(text, kind = "neutral") {
  statusStripEl.textContent = text;
  statusStripEl.className = `status-strip ${kind}`;
}

async function fetchJson(url, options = {}) {
  const config = { ...options };
  config.headers = { ...(options.headers || {}) };
  if (!(config.body instanceof FormData)) {
    config.headers["Content-Type"] = "application/json";
  }
  const response = await fetch(url, config);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    let payload = null;
    try {
      payload = await response.json();
      detail = payload.detail || payload.error || detail;
    } catch (_error) {
      // ignore
    }
    const error = new Error(detail);
    error.payload = payload;
    throw error;
  }
  return response.json();
}

function appendChat(role, content) {
  const fragment = chatBubbleTemplate.content.cloneNode(true);
  const card = fragment.querySelector(".chat-bubble");
  card.classList.add(role);
  fragment.querySelector(".chat-role").textContent = role === "user" ? "Tú" : "Lexera";
  fragment.querySelector(".chat-content").textContent = content;
  copilotMessagesEl.appendChild(fragment);
  copilotMessagesEl.scrollTop = copilotMessagesEl.scrollHeight;
}

function summaryCard({ label, value, note }) {
  const fragment = summaryCardTemplate.content.cloneNode(true);
  fragment.querySelector(".summary-label").textContent = label;
  fragment.querySelector(".summary-value").textContent = value;
  fragment.querySelector(".summary-note").textContent = note;
  return fragment;
}

function listRow({ title, detail, tag, meta }) {
  const fragment = listRowTemplate.content.cloneNode(true);
  fragment.querySelector(".row-title").textContent = title;
  fragment.querySelector(".row-detail").textContent = detail || "";
  fragment.querySelector(".row-tag").textContent = tag || "";
  fragment.querySelector(".row-meta").textContent = meta || "";
  return fragment;
}

function timelineItem({ title, detail, dateLabel }) {
  const fragment = timelineItemTemplate.content.cloneNode(true);
  fragment.querySelector(".timeline-date").textContent = dateLabel;
  fragment.querySelector(".timeline-title").textContent = title;
  fragment.querySelector(".timeline-detail").textContent = detail || "";
  return fragment;
}

function expedienteDocuments(expediente) {
  return expediente?.documents || [];
}

function proceduralTrackLabel(expediente) {
  const trackId = expediente?.extra?.procedure_track;
  if (!trackId) return "Sin automatizacion";
  const track = state.proceduralTracks.find((item) => item.id === trackId);
  return track ? `${track.label} | ${track.status}` : trackId;
}

function synthesisState(expediente) {
  const status = expediente?.extra?.synthesis_status || "missing";
  const synthesis = expediente?.extra?.latest_synthesis || null;
  return { status, synthesis };
}

function latestDocumentVersions(expediente) {
  const versions = [];
  expedienteDocuments(expediente).forEach((document) => {
    (document.versions || []).forEach((version) => {
      versions.push({
        ...version,
        document_id: document.id,
        document_title: document.title,
        document_type: document.document_type,
      });
    });
  });
  return versions.sort((a, b) => {
    const aDate = new Date(a.created_at || 0).getTime();
    const bDate = new Date(b.created_at || 0).getTime();
    return bDate - aDate;
  });
}

function populateDocumentSelects(expediente) {
  const docs = expedienteDocuments(expediente);
  document.querySelectorAll(".document-select").forEach((selectEl) => {
    const previousValue = selectEl.value;
    selectEl.innerHTML = '<option value="">Sin vincular</option>';
    docs.forEach((documentItem) => {
      const option = document.createElement("option");
      option.value = documentItem.id;
      option.textContent = `${documentItem.title} (${documentItem.document_type})`;
      selectEl.appendChild(option);
    });
    if (previousValue) selectEl.value = previousValue;
  });
}

function populateDeadlineSelect(expediente) {
  const previousValue = deadlineUpdateSelectEl.value;
  deadlineUpdateSelectEl.innerHTML = '<option value="">Selecciona un plazo</option>';
  (expediente?.deadlines || []).forEach((deadline) => {
    const option = document.createElement("option");
    option.value = deadline.id;
    option.textContent = `${deadline.label} · ${deadline.status} · ${fmtDate(deadline.due_at)}`;
    deadlineUpdateSelectEl.appendChild(option);
  });
  if (previousValue) deadlineUpdateSelectEl.value = previousValue;
}

function populateReleaseSelect(expediente) {
  const previousValue = releaseVersionSelectEl.value;
  releaseVersionSelectEl.innerHTML = '<option value="">Selecciona una versión</option>';
  latestDocumentVersions(expediente).forEach((version) => {
    const option = document.createElement("option");
    option.value = version.id;
    option.textContent = `${version.document_title} · v${version.version_number} · ${version.file_name}`;
    releaseVersionSelectEl.appendChild(option);
  });
  if (previousValue) releaseVersionSelectEl.value = previousValue;
}

function populateRevisionSelect(expediente) {
  if (!revisionVersionSelectEl) return;
  const previousValue = revisionVersionSelectEl.value;
  revisionVersionSelectEl.innerHTML = '<option value="">Selecciona una version</option>';
  latestDocumentVersions(expediente).forEach((version) => {
    const option = document.createElement("option");
    option.value = version.id;
    option.textContent = `${version.document_title} · v${version.version_number} · ${version.file_name}`;
    option.dataset.documentTitle = version.document_title || "";
    revisionVersionSelectEl.appendChild(option);
  });
  if (previousValue) revisionVersionSelectEl.value = previousValue;
}

function populateDefendabilitySelect(expediente) {
  if (!defendabilityVersionSelectEl) return;
  const previousValue = defendabilityVersionSelectEl.value;
  defendabilityVersionSelectEl.innerHTML = '<option value="">Selecciona una version</option>';
  latestDocumentVersions(expediente).forEach((version) => {
    const option = document.createElement("option");
    option.value = version.id;
    option.textContent = `${version.document_title} · v${version.version_number} · ${version.file_name}`;
    defendabilityVersionSelectEl.appendChild(option);
  });
  if (previousValue) defendabilityVersionSelectEl.value = previousValue;
}

function populateProcedureTrackSelect() {
  const previousValue = procedureTrackSelectEl.value;
  procedureTrackSelectEl.innerHTML = '<option value="">Sin automatizacion</option>';
  state.proceduralTracks.forEach((track) => {
    const option = document.createElement("option");
    option.value = track.id;
    option.textContent = `${track.label} | ${track.status}`;
    procedureTrackSelectEl.appendChild(option);
  });
  if (previousValue) procedureTrackSelectEl.value = previousValue;
}

function draftSectionSpec(sectionKey) {
  return state.draftSections.find((item) => item.key === sectionKey) || null;
}

function populateDraftSectionSelect() {
  if (!draftSectionSelectEl) return;
  const previousValue = draftSectionSelectEl.value;
  draftSectionSelectEl.innerHTML = '<option value="">Selecciona una seccion</option>';
  state.draftSections.forEach((section) => {
    const option = document.createElement("option");
    option.value = section.key;
    option.textContent = section.label;
    draftSectionSelectEl.appendChild(option);
  });
  if (previousValue) draftSectionSelectEl.value = previousValue;
  syncDraftSectionHelp();
}

function syncDraftSectionHelp() {
  if (!draftSectionHelpEl || !draftSectionSelectEl) return;
  const section = draftSectionSpec(draftSectionSelectEl.value);
  draftSectionHelpEl.textContent = section
    ? section.guidance
    : "Selecciona una seccion concreta. Lexera la redacta con base en la sintesis y los documentos cargados.";
}

function syncRevisionModeHint() {
  if (!revisionModeHintEl || !revisionModeSelectEl) return;
  revisionModeHintEl.value =
    revisionModeSelectEl.value === "broad"
      ? "La revision amplia puede bloquearse si la version ya fue aprobada."
      : "La revision puntual limita cambios y es el modo por defecto.";
}

function renderRevisionResult(result) {
  if (!revisionResultEl) return;
  if (!result) {
    revisionResultEl.className = "revision-result empty-state";
    revisionResultEl.textContent = "Todavia no hay resultado de revision en esta sesion.";
    return;
  }
  revisionResultEl.className = "revision-result";
  const justification = (result.justification || []).length
    ? `<ul>${result.justification.map((item) => `<li>${item}</li>`).join("")}</ul>`
    : "<p>Sin justificacion detallada.</p>";
  revisionResultEl.innerHTML = `
    <div class="revision-result-header">
      <strong>Revision ${result.revision_mode}</strong>
      <span>Confianza: ${result.confidence || "medio"} | Cambio: ${result.changed ? "si" : "no"}</span>
    </div>
    <div class="revision-result-block">
      <h4>Justificacion</h4>
      ${justification}
    </div>
    <div class="revision-result-block">
      <h4>Diff</h4>
      <pre>${result.diff_text || "Sin diff relevante."}</pre>
    </div>
  `;
}

function renderDefendabilityResult(response) {
  if (!defendabilityResultEl) return;
  if (!response || !response.gate) {
    defendabilityResultEl.className = "revision-result empty-state";
    defendabilityResultEl.textContent = "Todavia no hay evaluacion de defendibilidad en esta sesion.";
    return;
  }
  const gate = response.gate;
  const items = (gate.items || []).length
    ? `<ul>${gate.items
        .map(
          (item) =>
            `<li><strong>${item.support_status}</strong> | ${item.claim || "Punto sin descripcion"} | Evidencia: ${item.evidence_basis || "Sin evidencia"} | Expediente: ${item.expediente_support || "Sin soporte"} | Falta: ${item.missing_for_court || "No indicado"}</li>`,
        )
        .join("")}</ul>`
    : "<p>Sin items relevantes reportados.</p>";
  const blocking = (gate.blocking_reasons || []).length
    ? `<p><strong>Bloqueos procesales:</strong> ${(gate.blocking_reasons || []).join(" | ")}</p>`
    : "<p><strong>Bloqueos procesales:</strong> ninguno.</p>";
  defendabilityResultEl.className = "revision-result";
  defendabilityResultEl.innerHTML = `
    <div class="revision-result-header">
      <strong>Estado: ${gate.summary_status || "review_required"}</strong>
      <span>${gate.summary_note || "Sin nota general."}</span>
    </div>
    <div class="revision-result-block">
      <h4>Compuerta</h4>
      ${blocking}
    </div>
    <div class="revision-result-block">
      <h4>Trazabilidad de soporte</h4>
      ${items}
    </div>
  `;
}

function renderAgenda() {
  clearChildren(agendaListEl);
  if (!state.agendaItems.length) {
    agendaListEl.innerHTML = '<div class="empty-state">No hay terminos ni audiencias proximas.</div>';
    return;
  }
  state.agendaItems.forEach((item) => {
    agendaListEl.appendChild(
      listRow({
        title: item.title,
        detail: `${item.expediente_title}${item.notes ? ` | ${item.notes}` : ""}`,
        tag: item.kind === "deadline" ? item.status || "plazo" : "audiencia",
        meta: `${fmtDate(item.starts_at)} | ${item.expediente_number || "Sin numero"}`,
      }),
    );
  });
}

function renderPreflightChecklist(expediente) {
  const checklist = expediente?.extra?.pre_merits_checklist;
  clearChildren(preflightChecklistSummaryEl);
  clearChildren(preflightChecklistListEl);
  if (!checklist || !Array.isArray(checklist.items) || !checklist.items.length) {
    preflightChecklistSummaryEl.innerHTML =
      '<div class="empty-state">Todavia no hay checklist estructurado. Ejecuta "Auditar control previo".</div>';
    return;
  }

  const summary = document.createElement("div");
  summary.className = `checklist-summary-card status-${checklist.summary_status || "dudoso"}`;
  summary.innerHTML = `
    <strong>Estado general: ${checklist.summary_status || "dudoso"}</strong>
    <p>${checklist.summary_note || "Sin nota general."}</p>
    <span>Actualizado: ${fmtDate(checklist.generated_at)}</span>
  `;
  preflightChecklistSummaryEl.appendChild(summary);

  checklist.items.forEach((item) => {
    const card = document.createElement("article");
    card.className = `checklist-item status-${item.status || "faltante"}`;
    card.innerHTML = `
      <div class="checklist-item-header">
        <strong>${item.label}</strong>
        <span class="checklist-badge">${item.status || "faltante"}</span>
      </div>
      <p><strong>Evidencia:</strong> ${item.evidence || "Sin evidencia clara."}</p>
      <p><strong>Riesgo:</strong> ${item.risk || "Sin riesgo descrito."}</p>
      <p><strong>Siguiente accion:</strong> ${item.next_action || "Sin accion definida."}</p>
    `;
    preflightChecklistListEl.appendChild(card);
  });
}

function renderSynthesis(expediente) {
  clearChildren(synthesisSummaryEl);
  clearChildren(synthesisContentEl);
  const { status, synthesis } = synthesisState(expediente);
  if (!synthesis) {
    synthesisSummaryEl.innerHTML =
      '<div class="empty-state">Todavia no existe sintesis vigente. Generala antes de redactar borradores.</div>';
    return;
  }
  const summary = document.createElement("div");
  summary.className = `checklist-summary-card status-${status === "current" ? "acreditado" : "dudoso"}`;
  summary.innerHTML = `
    <strong>Estado de sintesis: ${status}</strong>
    <p>${synthesis.title || "Sintesis vigente del expediente"}</p>
    <span>Actualizada: ${fmtDate(synthesis.generated_at)} | Modelo: ${synthesis.model || "local"}</span>
  `;
  synthesisSummaryEl.appendChild(summary);

  const pre = document.createElement("pre");
  pre.className = "synthesis-pre";
  pre.textContent = synthesis.content || "Sin contenido de sintesis.";
  synthesisContentEl.appendChild(pre);
}

function renderExpedienteList() {
  clearChildren(expedienteListEl);
  if (!state.expedientes.length) {
    expedienteListEl.innerHTML = '<div class="empty-state">Todavía no hay expedientes cargados.</div>';
    return;
  }
  state.expedientes.forEach((expediente) => {
    const fragment = expedienteListItemTemplate.content.cloneNode(true);
    const button = fragment.querySelector(".expediente-item");
    if (state.selectedExpedienteId === expediente.id) button.classList.add("active");
    fragment.querySelector(".expediente-item-title").textContent = expediente.title;
    fragment.querySelector(".expediente-item-meta").textContent =
      [expediente.expediente_number || "Sin número", expediente.matter_type, expediente.status].filter(Boolean).join(" · ");
    button.addEventListener("click", () => loadExpediente(expediente.id));
    expedienteListEl.appendChild(fragment);
  });
}

function renderExpedienteDetail() {
  const expediente = state.selectedExpediente;
  if (!expediente) {
    expedienteTitleEl.textContent = "Selecciona un expediente";
    expedienteMetaEl.textContent = "La vista mostrará partes, documentos, plazos y actividad.";
    clearChildren(expedienteSummaryCardsEl);
    clearChildren(partyListEl);
    clearChildren(deadlineListEl);
    clearChildren(documentListEl);
    clearChildren(timelineListEl);
    clearChildren(releaseReceiptListEl);
    clearChildren(preflightChecklistSummaryEl);
    clearChildren(preflightChecklistListEl);
    clearChildren(synthesisSummaryEl);
    clearChildren(synthesisContentEl);
    populateDocumentSelects(null);
    populateDeadlineSelect(null);
    populateReleaseSelect(null);
    populateRevisionSelect(null);
    populateDefendabilitySelect(null);
    renderRevisionResult(null);
    renderDefendabilityResult(null);
    return;
  }

  expedienteTitleEl.textContent = expediente.title;
  expedienteMetaEl.textContent = [
    expediente.expediente_number || "Sin número",
    expediente.matter_type,
    expediente.jurisdiction_level || "jurisdicción pendiente",
    expediente.court_or_authority || "autoridad pendiente",
  ]
    .filter(Boolean)
    .join(" · ");

  clearChildren(expedienteSummaryCardsEl);
  [
    {
      label: "Estado",
      value: expediente.status,
      note: expediente.procedural_stage || "Sin etapa procesal capturada",
    },
    {
      label: "Documentos",
      value: fmtInt(expediente.documents.length),
      note: `${fmtInt(expediente.events.length)} eventos y ${fmtInt(expediente.deadlines.length)} plazos`,
    },
    {
      label: "Partes",
      value: fmtInt(expediente.parties.length),
      note: expediente.requested_outcome || "Sin pretension capturada",
    },
    {
      label: "Sintesis",
      value: synthesisState(expediente).status,
      note: synthesisState(expediente).synthesis?.generated_at
        ? `Vigente desde ${fmtDate(synthesisState(expediente).synthesis.generated_at)}`
        : "Sintesis pendiente",
    },
    {
      label: "Receipts",
      value: fmtInt((expediente.release_receipts || []).length),
      note: proceduralTrackLabel(expediente),
    },
  ].forEach((item) => expedienteSummaryCardsEl.appendChild(summaryCard(item)));

  clearChildren(partyListEl);
  if (!expediente.parties.length) {
    partyListEl.innerHTML = '<div class="empty-state">Sin partes cargadas.</div>';
  } else {
    expediente.parties.forEach((party) =>
      partyListEl.appendChild(
        listRow({
          title: party.display_name,
          detail: party.identifier || party.entity_type || "",
          tag: party.role,
          meta: "",
        }),
      ),
    );
  }

  clearChildren(deadlineListEl);
  if (!expediente.deadlines.length) {
    deadlineListEl.innerHTML = '<div class="empty-state">Sin plazos registrados.</div>';
  } else {
    [...expediente.deadlines]
      .sort((a, b) => new Date(a.due_at) - new Date(b.due_at))
      .forEach((deadline) =>
        deadlineListEl.appendChild(
          listRow({
            title: deadline.label,
            detail: deadline.notes || deadline.extra?.warning || "",
            tag: deadline.extra?.procedural_rule_id ? `${deadline.status} | auto` : deadline.status,
            meta: fmtDate(deadline.due_at),
          }),
        ),
      );
  }

  clearChildren(documentListEl);
  if (!expediente.documents.length) {
    documentListEl.innerHTML = '<div class="empty-state">Aún no hay documentos cargados.</div>';
  } else {
    expediente.documents.forEach((documentItem) => {
      const currentVersion = (documentItem.versions || []).slice(-1)[0];
      const sectionLabel = documentItem.extra?.draft_section_label;
      const detailParts = [];
      if (sectionLabel) detailParts.push(`Seccion ${sectionLabel}`);
      if (documentItem.description) {
        detailParts.push(documentItem.description);
      } else if (currentVersion?.notes) {
        detailParts.push(currentVersion.notes);
      }
      documentListEl.appendChild(
        listRow({
          title: documentItem.title,
          detail: detailParts.join(" | ") || "Sin descripción",
          tag: documentItem.document_type,
          meta: currentVersion
            ? `v${currentVersion.version_number} | ${currentVersion.file_name || "archivo"}`
            : fmtDate(documentItem.updated_at),
        }),
      );
    });
  }

  clearChildren(releaseReceiptListEl);
  if (!(expediente.release_receipts || []).length) {
    releaseReceiptListEl.innerHTML = '<div class="empty-state">Todavía no hay release receipts.</div>';
  } else {
    expediente.release_receipts.forEach((receipt) => {
      releaseReceiptListEl.appendChild(
        listRow({
          title: receipt.verdict,
          detail: receipt.gate_summary?.notes || receipt.response_type || "Sin notas",
          tag: receipt.response_type || "manual_review",
          meta: fmtDate(receipt.created_at),
        }),
      );
    });
  }

  clearChildren(timelineListEl);
  const timelineRows = [];
  expediente.events.forEach((event) => {
    timelineRows.push({
      title: event.title,
      detail: event.description || event.event_type,
      dateLabel: fmtDate(event.event_date),
      sortDate: new Date(event.event_date),
    });
  });
  expediente.documents.forEach((documentItem) => {
    timelineRows.push({
      title: documentItem.title,
      detail: `Documento ${documentItem.document_type}`,
      dateLabel: documentItem.event_date ? fmtDate(documentItem.event_date) : fmtDate(documentItem.updated_at),
      sortDate: new Date(documentItem.event_date || documentItem.updated_at),
    });
  });
  timelineRows
    .sort((a, b) => b.sortDate - a.sortDate)
    .forEach((row) => timelineListEl.appendChild(timelineItem(row)));

  populateDocumentSelects(expediente);
  populateDeadlineSelect(expediente);
  populateReleaseSelect(expediente);
  populateRevisionSelect(expediente);
  populateDefendabilitySelect(expediente);
  renderPreflightChecklist(expediente);
  renderSynthesis(expediente);
}

async function loadBootstrap() {
  setStatus("Cargando expedientes...", "loading");
  const payload = await fetchJson(endpoints.bootstrap);
  state.expedientes = payload.items || [];
  state.agendaItems = payload.agenda || [];
  state.proceduralTracks = payload.procedural_tracks || [];
  state.draftSections = payload.draft_sections || [];
  populateProcedureTrackSelect();
  populateDraftSectionSelect();
  renderAgenda();
  if (!state.selectedExpedienteId && state.expedientes.length) {
    state.selectedExpedienteId = state.expedientes[0].id;
  }
  renderExpedienteList();
  if (state.selectedExpedienteId) {
    await loadExpediente(state.selectedExpedienteId, { preserveStatus: true });
  } else {
    state.selectedExpediente = null;
    renderExpedienteDetail();
    setStatus("Listo para crear el primer expediente.", "ok");
  }
}

async function loadExpediente(expedienteId, options = {}) {
  if (state.selectedExpedienteId !== expedienteId) clearPendingRelease();
  state.selectedExpedienteId = expedienteId;
  renderExpedienteList();
  if (!options.preserveStatus) setStatus("Cargando expediente...", "loading");
  const expediente = await fetchJson(endpoints.expediente(expedienteId));
  state.selectedExpediente = expediente;
  renderExpedienteDetail();
  setStatus(`Expediente cargado: ${expediente.title}`, "ok");
}

function normalizeDateTimeLocal(value) {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString();
}

async function submitExpedienteForm(event) {
  event.preventDefault();
  const formData = new FormData(expedienteFormEl);
  const partyName = String(formData.get("party_display_name") || "").trim();
  const payload = {
    title: String(formData.get("title") || "").trim(),
    expediente_number: String(formData.get("expediente_number") || "").trim() || null,
    matter_type: String(formData.get("matter_type") || "").trim(),
    jurisdiction_level: String(formData.get("jurisdiction_level") || "").trim() || null,
    court_or_authority: String(formData.get("court_or_authority") || "").trim() || null,
    summary: String(formData.get("summary") || "").trim() || null,
    extra: formData.get("procedure_track")
      ? { procedure_track: String(formData.get("procedure_track") || "").trim() }
      : {},
    parties: partyName
      ? [
          {
            display_name: partyName,
            role: formData.get("party_role"),
          },
        ]
      : [],
  };

  setStatus("Creando expediente...", "loading");
  const created = await fetchJson(endpoints.expedientes, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  expedienteFormEl.reset();
  expedienteFormEl.classList.add("hidden");
  state.selectedExpedienteId = created.id;
  await loadBootstrap();
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      const [, base64] = result.split(",", 2);
      resolve(base64 || "");
    };
    reader.onerror = () => reject(reader.error || new Error("No fue posible leer el archivo."));
    reader.readAsDataURL(file);
  });
}

async function submitDocumentForm(event) {
  event.preventDefault();
  if (!state.selectedExpedienteId) {
    throw new Error("Primero selecciona o crea un expediente.");
  }
  const formData = new FormData(documentFormEl);
  const file = formData.get("file");
  if (!(file instanceof File) || !file.size) {
    throw new Error("Selecciona un archivo para cargar.");
  }
  setStatus("Subiendo documento...", "loading");
  const payload = {
    document: {
      title: String(formData.get("title") || "").trim(),
      document_type: formData.get("document_type"),
      description: String(formData.get("description") || "").trim() || null,
      event_date: formData.get("event_date") || null,
    },
    version: {
      source_kind: "uploaded",
      file_name: file.name,
      mime_type: file.type || "application/octet-stream",
      content_base64: await fileToBase64(file),
      notes: "Cargado desde workspace de Lexera",
    },
  };
  await fetchJson(`${endpoints.expediente(state.selectedExpedienteId)}/documents`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  documentFormEl.reset();
  await loadBootstrap();
  setStatus(`Documento cargado en ${state.selectedExpediente.title}.`, "ok");
}

async function submitEventForm(event) {
  event.preventDefault();
  if (!state.selectedExpedienteId) throw new Error("Primero selecciona o crea un expediente.");
  const formData = new FormData(eventFormEl);
  setStatus("Registrando actuación...", "loading");
  const response = await fetchJson(endpoints.events(state.selectedExpedienteId), {
    method: "POST",
    body: JSON.stringify({
      title: String(formData.get("title") || "").trim(),
      event_type: formData.get("event_type"),
      event_date: normalizeDateTimeLocal(formData.get("event_date")),
      description: String(formData.get("description") || "").trim() || null,
      document_id: formData.get("document_id") || null,
    }),
  });
  eventFormEl.reset();
  await loadBootstrap();
  const createdDeadlines = response.created_deadlines || [];
  setStatus(
    createdDeadlines.length
      ? `Actuacion registrada | ${createdDeadlines.length} plazo(s) preliminar(es) generado(s).`
      : "Actuacion registrada.",
    "ok",
  );
}

async function submitDeadlineForm(event) {
  event.preventDefault();
  if (!state.selectedExpedienteId) throw new Error("Primero selecciona o crea un expediente.");
  const formData = new FormData(deadlineFormEl);
  setStatus("Guardando plazo...", "loading");
  await fetchJson(endpoints.deadlines(state.selectedExpedienteId), {
    method: "POST",
    body: JSON.stringify({
      label: String(formData.get("label") || "").trim(),
      due_at: normalizeDateTimeLocal(formData.get("due_at")),
      status: formData.get("status"),
      notes: String(formData.get("notes") || "").trim() || null,
      document_id: formData.get("document_id") || null,
    }),
  });
  deadlineFormEl.reset();
  await loadBootstrap();
  setStatus("Plazo guardado.", "ok");
}

async function submitDeadlineUpdateForm(event) {
  event.preventDefault();
  if (!state.selectedExpedienteId) throw new Error("Primero selecciona o crea un expediente.");
  const formData = new FormData(deadlineUpdateFormEl);
  const deadlineId = String(formData.get("deadline_id") || "");
  if (!deadlineId) throw new Error("Selecciona un plazo para actualizar.");
  setStatus("Actualizando plazo...", "loading");
  await fetchJson(endpoints.deadline(state.selectedExpedienteId, deadlineId), {
    method: "PATCH",
    body: JSON.stringify({
      status: formData.get("status"),
      notes: String(formData.get("notes") || "").trim() || null,
    }),
  });
  deadlineUpdateFormEl.reset();
  await loadBootstrap();
  setStatus("Plazo actualizado.", "ok");
}

async function submitDraftForm(event) {
  event.preventDefault();
  if (!state.selectedExpedienteId) throw new Error("Primero selecciona o crea un expediente.");
  if (!synthesisState(state.selectedExpediente).synthesis) {
    throw new Error("Genera primero una sintesis vigente del expediente antes de redactar borradores.");
  }
  const formData = new FormData(draftFormEl);
  const bundleTitle = String(formData.get("bundle_title") || "").trim();
  const sectionKey = String(formData.get("section_key") || "").trim();
  const prompt = String(formData.get("prompt") || "").trim();
  const section = draftSectionSpec(sectionKey);
  if (!bundleTitle) throw new Error("Captura el nombre del escrito o bundle.");
  if (!sectionKey || !section) throw new Error("Selecciona la seccion que quieres redactar.");
  if (!prompt) throw new Error("Escribe una instrucción para generar el borrador.");
  setStatus(`Generando seccion ${section.label}...`, "loading");
  appendChat("user", `Genera seccion ${section.label} de ${bundleTitle}: ${prompt}`);
  const response = await fetchJson(endpoints.drafts(state.selectedExpedienteId), {
    method: "POST",
    body: JSON.stringify({
      bundle_title: bundleTitle,
      title: bundleTitle,
      document_type: formData.get("document_type"),
      event_date: formData.get("event_date") || null,
      description: String(formData.get("description") || "").trim() || null,
      section_key: sectionKey,
      prompt,
    }),
  });
  draftFormEl.reset();
  syncDraftSectionHelp();
  appendChat("assistant", response.answer);
  await loadBootstrap();
  setStatus(
    `Seccion ${response.section_label} guardada en el expediente (${response.document_action}) con modelo ${response.model}.`,
    "ok",
  );
}

async function submitCaseAnalysisForm(event) {
  event.preventDefault();
  if (!state.selectedExpedienteId) throw new Error("Primero selecciona o crea un expediente.");
  if (!state.selectedExpediente?.documents?.length) {
    throw new Error("Carga documentos del expediente antes de pedir el analisis.");
  }
  const formData = new FormData(caseAnalysisFormEl);
  setStatus("Generando sintesis vigente...", "loading");
  appendChat("user", "Genera una sintesis vigente del expediente.");
  const response = await fetchJson(endpoints.analysis(state.selectedExpedienteId), {
    method: "POST",
    body: JSON.stringify({
      title: String(formData.get("title") || "").trim(),
      objective: String(formData.get("objective") || "").trim(),
    }),
  });
  caseAnalysisFormEl.reset();
  caseAnalysisFormEl.querySelector('input[name="title"]').value = "Sintesis vigente del expediente";
  appendChat("assistant", response.analysis);
  await loadBootstrap();
  setStatus(`Sintesis guardada en el expediente con modelo ${response.model}.`, "ok");
}

async function submitPreflightChecklistForm(event) {
  event.preventDefault();
  if (!state.selectedExpedienteId) throw new Error("Primero selecciona o crea un expediente.");
  if (!state.selectedExpediente?.documents?.length) {
    throw new Error("Carga documentos del expediente antes de auditar el control previo.");
  }
  const formData = new FormData(preflightChecklistFormEl);
  setStatus("Auditando control previo...", "loading");
  const response = await fetchJson(endpoints.preflightChecklist(state.selectedExpedienteId), {
    method: "POST",
    body: JSON.stringify({
      objective: String(formData.get("objective") || "").trim(),
    }),
  });
  await loadBootstrap();
  renderPreflightChecklist({ extra: { pre_merits_checklist: response.checklist } });
  setStatus(`Checklist actualizado con modelo ${response.model}.`, "ok");
}

async function submitRevisionForm(event) {
  event.preventDefault();
  if (!state.selectedExpedienteId) throw new Error("Primero selecciona o crea un expediente.");
  if (!synthesisState(state.selectedExpediente).synthesis) {
    throw new Error("Genera primero una sintesis vigente del expediente antes de revisar textos.");
  }
  const formData = new FormData(revisionFormEl);
  const documentVersionId = String(formData.get("document_version_id") || "").trim();
  const revisionMode = String(formData.get("revision_mode") || "narrow").trim();
  const objective = String(formData.get("objective") || "").trim();
  if (!documentVersionId) throw new Error("Selecciona la version a revisar.");
  if (!objective) throw new Error("Describe el objetivo de la revision.");
  setStatus(`Ejecutando revision ${revisionMode}...`, "loading");
  const response = await fetchJson(endpoints.revisions(state.selectedExpedienteId), {
    method: "POST",
    body: JSON.stringify({
      document_version_id: documentVersionId,
      revision_mode: revisionMode,
      objective,
    }),
  });
  renderRevisionResult(response);
  appendChat(
    "assistant",
    `Revision ${response.revision_mode} sobre version ${response.base_version_id}: ${response.justification.join(" | ") || "sin justificacion detallada."}`,
  );
  await loadBootstrap();
  setStatus(`Revision ${response.revision_mode} guardada como nueva version.`, "ok");
}

async function submitDefendabilityForm(event) {
  event.preventDefault();
  if (!state.selectedExpedienteId) throw new Error("Primero selecciona o crea un expediente.");
  if (!synthesisState(state.selectedExpediente).synthesis) {
    throw new Error("Genera primero una sintesis vigente del expediente antes de evaluar liberabilidad.");
  }
  const formData = new FormData(defendabilityFormEl);
  const documentVersionId = String(formData.get("document_version_id") || "").trim();
  if (!documentVersionId) throw new Error("Selecciona la version a evaluar.");
  setStatus("Evaluando defendibilidad...", "loading");
  const response = await fetchJson(endpoints.defendability(state.selectedExpedienteId), {
    method: "POST",
    body: JSON.stringify({
      document_version_id: documentVersionId,
    }),
  });
  renderDefendabilityResult(response);
  setStatus(`Compuerta de defendibilidad: ${response.gate.summary_status}.`, "ok");
}

async function submitReleaseForm(event) {
  event.preventDefault();
  clearPendingRelease();
  if (!reviewerBearer) throw new Error("Necesitas una sesión autenticada de revisión.");
  if (!state.selectedExpedienteId) throw new Error("Selecciona un expediente.");
  const formData = new FormData(releaseFormEl);
  const documentVersionId = String(formData.get("document_version_id") || "");
  if (!documentVersionId) throw new Error("Selecciona una versión almacenada.");
  const bundle = JSON.parse(String(formData.get("bundle") || ""));
  const expedienteId = state.selectedExpedienteId;
  const sessionAtStart = reviewerBearer;
  const bundleAtStart = String(formData.get("bundle") || "");
  const contextAtStart = releaseContextGeneration;
  const result = await fetchJson(endpoints.release(expedienteId), {
    method: "POST", headers: { Authorization: `Bearer ${reviewerBearer}` },
    body: JSON.stringify({ action: "evaluate", document_version_id: documentVersionId, bundle }),
  });
  if (releaseContextGeneration !== contextAtStart || reviewerBearer !== sessionAtStart || state.selectedExpedienteId !== expedienteId
    || releaseVersionSelectEl.value !== documentVersionId
    || String(new FormData(releaseFormEl).get("bundle") || "") !== bundleAtStart) {
    clearPendingRelease();
    throw new Error("La sesión, selección o bundle cambió; evalúa nuevamente.");
  }
  document.querySelector("#releaseGateResult").textContent = JSON.stringify({ verdict: result.verdict, gates: result.evidence?.gates }, null, 2);
  if (result.verdict === "approved" && result.id && result.document_version_id === documentVersionId) {
    pendingRelease = { expedienteId, documentVersionId, bundle, executionId: result.id };
    document.querySelector("#confirmReleaseButton").disabled = false;
  }
  setStatus(result.verdict === "approved" ? "Validación aprobada; revisa los gates antes de registrar la liberación." : "Liberación bloqueada por los gates del servidor.", result.verdict === "approved" ? "ok" : "error");
}

async function confirmRelease() {
  if (!reviewerBearer || !pendingRelease) throw new Error("Evalúa primero el bundle con tu sesión autenticada.");
  if (pendingRelease.expedienteId !== state.selectedExpedienteId || pendingRelease.documentVersionId !== releaseVersionSelectEl.value) {
    clearPendingRelease();
    throw new Error("La selección cambió; evalúa nuevamente.");
  }
  const candidate = pendingRelease;
  const sessionAtStart = reviewerBearer;
  const bundleAtStart = String(new FormData(releaseFormEl).get("bundle") || "");
  clearPendingRelease();
  const contextAtStart = releaseContextGeneration;
  const receipt = await fetchJson(endpoints.release(candidate.expedienteId), {
    method: "POST", headers: { Authorization: `Bearer ${reviewerBearer}` },
    body: JSON.stringify({ action: "release", execution_id: candidate.executionId, bundle: candidate.bundle }),
  });
  if (receipt.verdict !== "approved" || receipt.execution_id !== candidate.executionId) throw new Error("El recibo no confirma esta ejecución aprobada.");
  if (releaseContextGeneration !== contextAtStart || reviewerBearer !== sessionAtStart
    || state.selectedExpedienteId !== candidate.expedienteId
    || releaseVersionSelectEl.value !== candidate.documentVersionId
    || String(new FormData(releaseFormEl).get("bundle") || "") !== bundleAtStart) {
    setStatus(`La operación anterior terminó para el expediente ${candidate.expedienteId}; recibo ${receipt.id}. Consulta su historial. La sesión o selección cambió.`, "error");
    return;
  }
  await loadBootstrap();
  if (releaseContextGeneration !== contextAtStart || reviewerBearer !== sessionAtStart
    || state.selectedExpedienteId !== candidate.expedienteId
    || releaseVersionSelectEl.value !== candidate.documentVersionId) {
    setStatus(`La operación anterior terminó para el expediente ${candidate.expedienteId}; recibo ${receipt.id}. Consulta su historial. La sesión o selección cambió.`, "error");
    return;
  }
  document.querySelector("#releaseGateResult").textContent = JSON.stringify(receipt, null, 2);
  setStatus("Liberación registrada con evidencia del servidor.", "ok");
}

async function submitCopilot(event) {
  event.preventDefault();
  if (!state.selectedExpedienteId) throw new Error("Selecciona un expediente antes de usar el copiloto.");
  const prompt = copilotPromptEl.value.trim();
  if (!prompt) return;
  appendChat("user", prompt);
  copilotPromptEl.value = "";
  setStatus("Consultando al copiloto...", "loading");
  const response = await fetchJson(endpoints.copilot(state.selectedExpedienteId), {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
  appendChat("assistant", response.answer);
  setStatus(`Copiloto listo | modelo ${response.model}`, "ok");
}

function installHandlers() {
  refreshWorkspaceButtonEl.addEventListener("click", () => loadBootstrap().catch(handleError));
  toggleExpedienteFormButtonEl.addEventListener("click", () => expedienteFormEl.classList.toggle("hidden"));
  expedienteFormEl.addEventListener("submit", (event) => submitExpedienteForm(event).catch(handleError));
  documentFormEl.addEventListener("submit", (event) => submitDocumentForm(event).catch(handleError));
  eventFormEl.addEventListener("submit", (event) => submitEventForm(event).catch(handleError));
  deadlineFormEl.addEventListener("submit", (event) => submitDeadlineForm(event).catch(handleError));
  deadlineUpdateFormEl.addEventListener("submit", (event) => submitDeadlineUpdateForm(event).catch(handleError));
  draftFormEl.addEventListener("submit", (event) => submitDraftForm(event).catch(handleError));
  draftSectionSelectEl?.addEventListener("change", syncDraftSectionHelp);
  defendabilityFormEl.addEventListener("submit", (event) => submitDefendabilityForm(event).catch(handleError));
  revisionFormEl.addEventListener("submit", (event) => submitRevisionForm(event).catch(handleError));
  revisionModeSelectEl?.addEventListener("change", syncRevisionModeHint);
  caseAnalysisFormEl.addEventListener("submit", (event) => submitCaseAnalysisForm(event).catch(handleError));
  preflightChecklistFormEl.addEventListener("submit", (event) => submitPreflightChecklistForm(event).catch(handleError));
  releaseFormEl.addEventListener("submit", (event) => submitReleaseForm(event).catch(handleError));
  releaseFormEl.addEventListener("input", clearPendingRelease);
  document.querySelector("#confirmReleaseButton").addEventListener("click", () => confirmRelease().catch(handleError));
  copilotFormEl.addEventListener("submit", (event) => submitCopilot(event).catch(handleError));
}

function handleError(error) {
  console.error(error);
  setStatus(error.message || "Ocurrió un error en el workspace.", "error");
}

installHandlers();
syncRevisionModeHint();
loadBootstrap().catch(handleError);
