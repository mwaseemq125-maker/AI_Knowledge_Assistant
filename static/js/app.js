const $ = (id) => document.getElementById(id);
const TEST_QUESTIONS = [
  "What is artificial intelligence?",
  "How does machine learning work?",
  "What is the purpose of embeddings?",
  "How does semantic search differ from keyword search?",
  "What are the limitations of the information in these documents?"
];
let evaluationRows = [];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[c]);
}
function setStatus(id, message, error=false) {
  const el = $(id); el.textContent = message;
  el.style.color = error ? "#ff969e" : "#a9b4c9";
}
function setBusy(button, busy, label) {
  button.disabled = busy;
  button.classList.toggle("loading", busy);
  if (busy) { button.dataset.oldText = button.innerHTML; button.textContent = label; }
  else if (button.dataset.oldText) { button.innerHTML = button.dataset.oldText; }
}

async function loadDocuments() {
  try {
    const res = await fetch("/api/documents");
    const data = await res.json();
    $("chunkCount").textContent = data.total_chunks;
    $("documentList").innerHTML = data.documents.length ? data.documents.map(doc => `
      <div class="document-row">
        <div class="doc-name"><span class="doc-icon">▤</span>${escapeHtml(doc.name)}</div>
        <span class="chunk-count">${doc.chunks}</span><span class="indexed-pill">● Indexed</span>
      </div>`).join("") : '<div class="library-empty">No documents indexed yet. Upload a file to begin.</div>';
  } catch (err) {
    $("documentList").innerHTML = '<div class="library-empty">Could not load the document list. Is the server running?</div>';
  }
}

$("fileInput").addEventListener("change", () => {
  const files = [...$("fileInput").files];
  $("selectedFiles").textContent = files.length ? files.map(f => `${f.name} (${(f.size/1024).toFixed(1)} KB)`).join(" · ") : "No files selected";
});
$("uploadBtn").addEventListener("click", async () => {
  const files = [...$("fileInput").files];
  if (!files.length) return setStatus("uploadStatus", "Choose at least one PDF, TXT, or Markdown file.", true);
  const form = new FormData(); files.forEach(file => form.append("files", file));
  setBusy($("uploadBtn"), true, "Uploading & indexing…");
  setStatus("uploadStatus", "Extracting text and generating embeddings. The first model run may take longer.");
  try {
    const res = await fetch("/api/upload", {method:"POST", body:form});
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");
    const summary = data.results.map(r => `${r.ok ? "✓" : "✕"} ${r.filename}: ${r.message}`).join("\n");
    setStatus("uploadStatus", summary);
    $("fileInput").value = ""; $("selectedFiles").textContent = "No files selected";
    await loadDocuments();
  } catch (err) { setStatus("uploadStatus", err.message, true); }
  finally { setBusy($("uploadBtn"), false); }
});

document.querySelectorAll(".suggestion").forEach(btn => btn.addEventListener("click", () => {
  $("questionInput").value = btn.dataset.question; $("questionInput").focus();
}));
$("askBtn").addEventListener("click", async () => {
  const question = $("questionInput").value.trim();
  if (!question) { $("questionInput").focus(); return; }
  setBusy($("askBtn"), true, "Searching & generating…");
  $("answerArea").innerHTML = '<div class="empty-answer"><span>◌</span><strong>Searching your knowledge base…</strong><small>Embedding the question and retrieving relevant chunks.</small></div>';
  try {
    const res = await fetch("/api/ask", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({question, prompt_type:$("promptType").value, top_k:3})
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Could not generate answer");
    const sources = data.retrieved_chunks.length ? data.retrieved_chunks.map((chunk, i) => `
      <div class="source-item">
        <div class="source-meta"><span>${i+1}. ${escapeHtml(chunk.source)} · chunk ${escapeHtml(chunk.chunk)}</span><span>Similarity ${(chunk.similarity*100).toFixed(1)}%</span></div>
        <div class="source-text">${escapeHtml(chunk.text)}</div>
        <div class="score-track"><div class="score-fill" style="width:${chunk.similarity*100}%"></div></div>
      </div>`).join("") : '<div class="source-item source-text">No document chunks have been indexed yet.</div>';
    $("answerArea").innerHTML = `
      <div class="answer-card"><div class="answer-top"><span>✦ ${escapeHtml(data.prompt_type.toUpperCase())} RESPONSE</span><button class="copy-btn" id="copyAnswer">Copy answer ↗</button></div>
      <div class="answer-text">${escapeHtml(data.answer)}</div></div>
      <div class="source-list"><div class="field-label">RETRIEVED EVIDENCE · ${data.retrieved_chunks.length} CHUNKS</div>${sources}</div>`;
    $("copyAnswer").addEventListener("click", async () => {
      await navigator.clipboard.writeText(data.answer);
      $("copyAnswer").textContent = "Copied ✓";
    });
  } catch (err) {
    $("answerArea").innerHTML = `<div class="answer-card"><div class="answer-text">${escapeHtml(err.message)}</div></div>`;
  } finally { setBusy($("askBtn"), false); }
});

function renderQuestions() {
  $("testQuestions").innerHTML = TEST_QUESTIONS.map((q, i) => `
    <div class="question-item"><span class="question-num">Q${i+1}</span><span>${escapeHtml(q)}</span></div>`).join("");
}
$("refreshDocs").addEventListener("click", loadDocuments);

$("evaluateBtn").addEventListener("click", async () => {
  setBusy($("evaluateBtn"), true, "Running 15 tests…");
  setStatus("evaluationStatus", "Running the same five questions through all three prompts. This may take a little while.");
  $("evaluationResults").innerHTML = "";
  try {
    const res = await fetch("/api/evaluate", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({questions:TEST_QUESTIONS})
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Evaluation failed");
    evaluationRows = data.results;
    renderEvaluation();
    $("exportBtn").disabled = false;
    setStatus("evaluationStatus", `${data.results.length} answers generated. Rate accuracy, clarity, and relevance from 1–5, then export the CSV.`);
  } catch (err) { setStatus("evaluationStatus", err.message, true); }
  finally { setBusy($("evaluateBtn"), false); }
});

function renderEvaluation() {
  const groups = {};
  evaluationRows.forEach((row, idx) => {
    (groups[row.question_number] ||= []).push({...row, idx});
  });
  $("evaluationResults").innerHTML = Object.entries(groups).map(([num, rows]) => `
    <div class="result-group"><h5>Question ${num}: ${escapeHtml(rows[0].question)}</h5>
    ${rows.map(row => `<div class="result-entry">
      <div class="result-entry-top"><span class="technique-tag">${escapeHtml(row.technique)}</span><span class="source-text">Sources: ${escapeHtml((row.sources||[]).join(", ") || "None")}</span></div>
      <p>${escapeHtml(row.answer)}</p>
      <div class="rating-row">${["accuracy","clarity","relevance"].map(metric => `
        <label>${metric[0].toUpperCase()+metric.slice(1)}
          <select data-row="${row.idx}" data-metric="${metric}">
            <option value="">Rate / 5</option>${[1,2,3,4,5].map(n=>`<option value="${n}" ${row[metric]===n?"selected":""}>${n}</option>`).join("")}
          </select>
        </label>`).join("")}
      </div>
    </div>`).join("")}</div>`).join("");
  $("evaluationResults").querySelectorAll("select").forEach(select => select.addEventListener("change", () => {
    const row = evaluationRows[Number(select.dataset.row)];
    row[select.dataset.metric] = select.value ? Number(select.value) : null;
  }));
}

$("exportBtn").addEventListener("click", () => {
  if (!evaluationRows.length) return;
  const headers = ["Question Number","Question","Technique","Answer","Sources","Accuracy / 5","Clarity / 5","Relevance / 5","Average / 5"];
  const rows = evaluationRows.map(r => {
    const scores = [r.accuracy,r.clarity,r.relevance];
    const avg = scores.every(n=>Number.isFinite(n)) ? (scores.reduce((a,b)=>a+b,0)/3).toFixed(2) : "";
    return [r.question_number,r.question,r.technique,r.answer,(r.sources||[]).join("; "),r.accuracy??"",r.clarity??"",r.relevance??"",avg];
  });
  const csv = [headers,...rows].map(row=>row.map(v=>`"${String(v).replace(/"/g,'""')}"`).join(",")).join("\r\n");
  const blob = new Blob([csv],{type:"text/csv;charset=utf-8;"});
  const url = URL.createObjectURL(blob); const a = document.createElement("a");
  a.href=url; a.download="prompt_evaluation_results.csv"; a.click(); URL.revokeObjectURL(url);
});

renderQuestions();
loadDocuments();
