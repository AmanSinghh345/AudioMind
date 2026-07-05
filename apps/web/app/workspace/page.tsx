"use client";

import { ChangeEvent, DragEvent, useEffect, useMemo, useState } from "react";
import { ApiClient, DEFAULT_API_BASE } from "../../lib/api";

type Collection = {
  id: string;
  name: string;
  description: string;
  document_count: number;
};

type DocumentItem = {
  id: string;
  filename: string;
  status: string;
  page_count: number;
  chunk_count: number;
};

type Source = {
  label: string;
  filename: string;
  page_number: number;
  chunk_index: number;
  chapter: string;
  text: string;
  vector_score: number;
  rerank_score: number;
};

type Answer = {
  answer: string;
  grounded: boolean;
  method: string;
  sources: Source[];
};

type Job = {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  result?: Record<string, unknown>;
  error?: string;
};

type Panel = "ask" | "audio" | "evidence" | null;

type AudioChapter = {
  id: string;
  chapter_number: number;
  title: string;
  script: string;
  audio_path?: string | null;
  duration?: number | null;
  status: string;
  audio_url?: string;
};

type Audiobook = {
  id: string;
  document_id: string;
  title: string;
  mode: string;
  voice: string;
  status: string;
  chapters: AudioChapter[];
};

const suggestedQuestions = [
  "Summarize this document",
  "Explain key concepts",
  "Create exam notes",
  "Generate Q&A"
];

function normalizeError(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export default function WorkspacePage() {
  const [apiKey, setApiKey] = useState("");
  const [apiBase, setApiBase] = useState(DEFAULT_API_BASE);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [collectionId, setCollectionId] = useState("");
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [health, setHealth] = useState({ status: "checking", method: "unknown", vectors: 0 });
  const [ocr, setOcr] = useState(true);
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState("");
  const [toast, setToast] = useState("");
  const [dragging, setDragging] = useState(false);
  const [audioUrl, setAudioUrl] = useState("");
  const [audiobook, setAudiobook] = useState<Audiobook | null>(null);
  const [audioDocumentId, setAudioDocumentId] = useState("");
  const [activePanel, setActivePanel] = useState<Panel>(null);
  const [voice, setVoice] = useState("af_heart");
  const [narrationMode, setNarrationMode] = useState("simple explanation");

  const api = useMemo(() => new ApiClient({ baseUrl: apiBase, apiKey }), [apiBase, apiKey]);

  const selectedCollection = useMemo(
    () => collections.find((collection) => collection.id === collectionId),
    [collections, collectionId]
  );

  const selectedDocuments = useMemo(
    () => documents.filter((document) => selectedDocumentIds.includes(document.id)),
    [documents, selectedDocumentIds]
  );

  useEffect(() => {
    const storedKey = window.localStorage.getItem("audiomindApiKey") || "";
    setApiKey(storedKey);
    setApiBase(DEFAULT_API_BASE);
    window.localStorage.removeItem("audiomindApiBase");
    void refresh(DEFAULT_API_BASE, storedKey);
  }, []);

  useEffect(() => {
    if (collectionId) {
      void loadDocuments(collectionId);
    } else {
      setDocuments([]);
      setSelectedDocumentIds([]);
    }
  }, [collectionId]);

  useEffect(() => {
    if (!audioDocumentId || !documents.some((document) => document.id === audioDocumentId)) {
      setAudioDocumentId(documents[0]?.id || "");
    }
  }, [documents, audioDocumentId]);

  function notify(message: string) {
    setToast(message);
    window.setTimeout(() => setToast(""), 3600);
  }

  function request<T>(path: string, options: RequestInit = {}, base = apiBase, key = apiKey) {
    const client = new ApiClient({ baseUrl: base, apiKey: key });
    return client.request<T>(path, {
      ...options,
      retryWithApiKey: (message) => {
        const nextKey = window.prompt(message) || "";
        if (nextKey) {
          window.localStorage.setItem("audiomindApiKey", nextKey);
          setApiKey(nextKey);
        }
        return nextKey;
      }
    });
  }

  async function refresh(base = apiBase, key = apiKey) {
    try {
      const status = await request<{ status: string; vector_chunks: number; embedding_method: string }>("/api/health", {}, base, key);
      setHealth({ status: status.status, method: status.embedding_method, vectors: status.vector_chunks });

      let nextCollections = await request<Collection[]>("/api/collections", {}, base, key);
      if (nextCollections.length === 0) {
        await request<{ id: string }>("/api/collections", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: "My Library", description: "Default workspace" })
        }, base, key);
        nextCollections = await request<Collection[]>("/api/collections", {}, base, key);
      }

      setCollections(nextCollections);
      setCollectionId((current) => {
        if (current && nextCollections.some((collection) => collection.id === current)) return current;
        return nextCollections[0]?.id || "";
      });
    } catch (error) {
      setHealth({ status: "offline", method: "unknown", vectors: 0 });
      notify(normalizeError(error, "API unavailable"));
    }
  }

  async function createWorkspace() {
    const name = window.prompt("Workspace name", "Untitled workspace")?.trim();
    if (!name) return;
    try {
      setBusy("workspace");
      const created = await request<{ id: string; name: string; description: string }>("/api/collections", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description: "" })
      });
      await refresh();
      setCollectionId(created.id);
      setAnswer(null);
      setAudioUrl("");
      setAudiobook(null);
      setActivePanel(null);
      notify("Workspace created");
    } catch (error) {
      notify(normalizeError(error, "Workspace creation failed"));
    } finally {
      setBusy("");
    }
  }

  async function loadDocuments(id: string) {
    try {
      const items = await request<DocumentItem[]>(`/api/collections/${id}/documents`);
      setDocuments(items);
      setSelectedDocumentIds((current) => current.filter((documentId) => items.some((item) => item.id === documentId)));
    } catch (error) {
      setDocuments([]);
      setSelectedDocumentIds([]);
      notify(normalizeError(error, "Could not load workspace documents"));
    }
  }

  async function waitForJob(jobId: string) {
    for (;;) {
      const job = await request<Job>(`/api/jobs/${jobId}`);
      if (job.status === "completed") return job;
      if (job.status === "failed") throw new Error(job.error || "Job failed");
      await new Promise((resolve) => window.setTimeout(resolve, 900));
    }
  }

  async function uploadFile(file: File) {
    if (!collectionId) return notify("Create or select a workspace first.");
    const form = new FormData();
    form.append("collection_id", collectionId);
    form.append("use_ocr", String(ocr));
    form.append("file", file);
    try {
      setBusy("upload");
      notify(`Indexing ${file.name}`);
      const job = await request<{ job_id: string }>("/api/documents", { method: "POST", body: form });
      await waitForJob(job.job_id);
      await loadDocuments(collectionId);
      await refresh();
      notify("Document indexed");
    } catch (error) {
      notify(normalizeError(error, "Upload failed"));
    } finally {
      setBusy("");
    }
  }

  async function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) await uploadFile(file);
    event.target.value = "";
  }

  async function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) await uploadFile(file);
  }

  async function ingestUrl() {
    if (!url.trim()) return notify("Paste a public URL first.");
    if (!collectionId) return notify("Create or select a workspace first.");
    try {
      setBusy("url");
      const job = await request<{ job_id: string }>("/api/urls", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ collection_id: collectionId, url: url.trim() })
      });
      await waitForJob(job.job_id);
      setUrl("");
      await loadDocuments(collectionId);
      await refresh();
      notify("URL indexed");
    } catch (error) {
      notify(normalizeError(error, "URL indexing failed"));
    } finally {
      setBusy("");
    }
  }

  async function removeDocument(documentId: string) {
    try {
      setBusy(documentId);
      await request(`/api/documents/${documentId}`, { method: "DELETE" });
      await loadDocuments(collectionId);
      await refresh();
      notify("Document removed");
    } catch (error) {
      notify(normalizeError(error, "Delete failed"));
    } finally {
      setBusy("");
    }
  }

  async function ask() {
    if (!collectionId) return notify("Select a workspace first.");
    if (!question.trim()) return notify("Ask a question first.");
    try {
      setBusy("ask");
      setAudioUrl("");
      setAudiobook(null);
      const result = await request<Answer>("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ collection_id: collectionId, question: question.trim() })
      });
      setAnswer(result);
      if (result.sources.length) setActivePanel("ask");
    } catch (error) {
      notify(normalizeError(error, "Question failed"));
    } finally {
      setBusy("");
    }
  }

  async function listen() {
    if (!answer?.answer) return notify("Ask a question before generating audio.");
    try {
      setBusy("listen");
      const job = await request<{ job_id: string }>("/api/listen", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: answer.answer })
      });
      const done = await waitForJob(job.job_id);
      const rawPath = String(done.result?.file_path || "");
      const fileName = rawPath.replaceAll("\\", "/").split("/").pop();
      if (!fileName) throw new Error("Audio path missing");
      setAudioUrl(api.audioUrl(fileName));
      notify("Audio ready");
    } catch (error) {
      notify(normalizeError(error, "Audio failed"));
    } finally {
      setBusy("");
    }
  }

  function audioFileUrl(rawPath: string) {
    const fileName = rawPath.replaceAll("\\", "/").split("/").pop();
    return fileName ? api.audioUrl(fileName) : "";
  }

  async function createScripts(documentId: string) {
    try {
      setBusy(documentId);
      const job = await request<{ job_id: string }>("/api/audiobooks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_id: documentId, mode: "simple explanation", voice })
      });
      await waitForJob(job.job_id);
      notify("Chapter scripts created");
    } catch (error) {
      notify(normalizeError(error, "Script generation failed"));
    } finally {
      setBusy("");
    }
  }

  async function generateAudiobook() {
    const documentId = audioDocumentId || documents[0]?.id;
    if (!documentId) return notify("Upload a document before generating an audiobook.");
    try {
      setBusy("audiobook");
      setAudiobook(null);
      notify("Creating audiobook script");
      const scriptJob = await request<{ job_id: string }>("/api/audiobooks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_id: documentId, mode: narrationMode, voice })
      });
      const scriptDone = await waitForJob(scriptJob.job_id);
      const created = scriptDone.result as unknown as Audiobook;
      if (!created?.chapters?.length) throw new Error("No audiobook chapters were created");

      const readyChapters: AudioChapter[] = [];
      for (const chapter of created.chapters) {
        notify(`Generating audio: ${chapter.title}`);
        const chapterJob = await request<{ job_id: string }>(`/api/chapters/${chapter.id}/audio`, { method: "POST" });
        const chapterDone = await waitForJob(chapterJob.job_id);
        const result = chapterDone.result || {};
        const rawPath = String(result.file_path || "");
        readyChapters.push({
          ...chapter,
          audio_path: rawPath || chapter.audio_path,
          duration: typeof result.duration === "number" ? result.duration : chapter.duration,
          status: "ready",
          audio_url: rawPath ? audioFileUrl(rawPath) : undefined
        });
        setAudiobook({ ...created, chapters: [...readyChapters, ...created.chapters.slice(readyChapters.length)] });
      }

      setAudiobook({ ...created, status: "ready", chapters: readyChapters });
      notify("Audiobook ready");
    } catch (error) {
      notify(normalizeError(error, "Audiobook generation failed"));
    } finally {
      setBusy("");
    }
  }

  function toggleDocument(documentId: string) {
    setSelectedDocumentIds((current) =>
      current.includes(documentId)
        ? current.filter((id) => id !== documentId)
        : [...current, documentId]
    );
  }

  const canUseActions = documents.length > 0;
  const evidenceSources = answer?.sources || [];

  return (
    <main className="appShell">
      <aside className="sidebar">
        <div className="brandBlock">
          <div className="brandMark"><span /></div>
          <div>
            <h1>AI Audiobook</h1>
            <p>Studio</p>
          </div>
        </div>

        <div className="navGroup">
          <a className="navItem active" href="#library">Library</a>
          <button className="navItem" onClick={() => setActivePanel("ask")}>Tutor</button>
          <button className="navItem" onClick={() => setActivePanel("evidence")}>Evidence</button>
          <a className="navItem" href="/">Home</a>
        </div>

        <div className="sidebarFooter">
          <div className="apiStatusLine">
            <span className={`statusDot ${health.status === "ok" ? "online" : ""}`} />
            <span>{health.status === "ok" ? "API online" : "API offline"}</span>
          </div>

          <details className="developerSettings">
            <summary>Developer settings</summary>
            <div className="sideCard">
              <span className={`statusDot ${health.status === "ok" ? "online" : ""}`} />
              <div>
                <strong>{health.status === "ok" ? "API online" : "API offline"}</strong>
                <small>{health.method} / {health.vectors} vectors</small>
              </div>
            </div>
            <label className="apiField">
              <span>API URL</span>
              <input
                value={apiBase}
                onChange={(event) => setApiBase(event.target.value)}
                onBlur={() => window.localStorage.setItem("audiomindApiBase", apiBase)}
              />
            </label>
            <button className="secondaryButton" onClick={() => refresh()}>Refresh</button>
          </details>
        </div>
      </aside>

      <section className="workspace">
        <header className="workspaceHeader">
          <div>
            <h2>Studio</h2>
            <p>Upload sources, organize them into a workspace, then generate Q&A or audiobook narration.</p>
          </div>
          <div className="heroStats" aria-label="Workspace stats">
            <span><strong>{documents.length}</strong> Documents</span>
            <span><strong>{evidenceSources.length}</strong> Sources</span>
            <span><strong>{audiobook ? "Ready" : "Idle"}</strong> Audio</span>
          </div>
        </header>

        <section className="toolbar">
          <label>
            <span>Current workspace</span>
            <select value={collectionId} onChange={(event) => {
              setCollectionId(event.target.value);
              setAnswer(null);
              setAudioUrl("");
              setActivePanel(null);
            }}>
              {collections.length === 0 ? <option value="">No workspace</option> : null}
              {collections.map((collection) => (
                <option key={collection.id} value={collection.id}>{collection.name}</option>
              ))}
            </select>
          </label>
          <button className="secondaryButton" onClick={createWorkspace} disabled={busy === "workspace"}>
            {busy === "workspace" ? "Creating" : "New workspace"}
          </button>
          <div className="collectionMeta">
            <strong>{selectedCollection?.name || "No workspace"}</strong>
            <span>{selectedCollection?.document_count || 0} indexed documents</span>
          </div>
        </section>

        <article id="library" className="surface libraryPanel">
          <div className="sectionTitle">
            <div>
              <h3>Sources</h3>
              <p>Upload documents or index a public URL.</p>
            </div>
            <label className="switch">
              <input checked={ocr} onChange={(event) => setOcr(event.target.checked)} type="checkbox" />
              <span>OCR</span>
            </label>
          </div>

          {health.status === "offline" ? (
            <div className="notice error">Backend is offline. Start the API, then refresh from Developer settings.</div>
          ) : null}

          <label
            className={`dropZone ${dragging ? "dragging" : ""}`}
            onDragEnter={() => setDragging(true)}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
          >
            <input onChange={onFileChange} type="file" accept=".pdf,.docx,.txt,.md,.csv,.png,.jpg,.jpeg" />
            <span className="dropIcon" aria-hidden="true" />
            <strong>{busy === "upload" ? "Indexing document..." : "Drop a file or click to upload"}</strong>
            <span>PDF, DOCX, TXT, MD, CSV, PNG, JPG</span>
          </label>

          <div className="urlBox">
            <input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="Paste a public study URL" />
            <button onClick={ingestUrl} disabled={busy === "url"}>{busy === "url" ? "Indexing" : "Index"}</button>
          </div>

          <div className="documentList">
            {documents.length === 0 ? (
              <div className="emptyState">Upload a PDF, note, or link to start.</div>
            ) : documents.map((doc) => (
              <div className="documentRow" key={doc.id}>
                <label className="documentCheck">
                  <input
                    type="checkbox"
                    checked={selectedDocumentIds.includes(doc.id)}
                    onChange={() => toggleDocument(doc.id)}
                  />
                  <span>
                    <strong>{doc.filename}</strong>
                    <small>{doc.page_count} pages / {doc.chunk_count} chunks / {doc.status}</small>
                  </span>
                </label>
                <div className="rowActions">
                  <button onClick={() => {
                    setAudioDocumentId(doc.id);
                    setActivePanel("audio");
                  }}>Audiobook</button>
                  <button onClick={() => removeDocument(doc.id)} disabled={busy === doc.id}>Remove</button>
                </div>
              </div>
            ))}
          </div>
        </article>

        {canUseActions ? (
          <section className="actionGrid" aria-label="Workspace actions">
            <button className="actionCard" onClick={() => setActivePanel(activePanel === "ask" ? null : "ask")}>
              <strong>Ask Questions</strong>
              <span>Open a focused Q&A panel for this workspace.</span>
            </button>
            <button className="actionCard" onClick={() => setActivePanel(activePanel === "audio" ? null : "audio")}>
              <strong>Generate Audiobook</strong>
              <span>Turn a selected uploaded document into narrated chapters.</span>
            </button>
            <button className="actionCard" onClick={() => setActivePanel(activePanel === "evidence" ? null : "evidence")}>
              <strong>View Evidence</strong>
              <span>Inspect retrieved source chunks after asking.</span>
            </button>
          </section>
        ) : null}

        {activePanel === "ask" ? (
          <article id="tutor" className="surface tutorPanel">
            <div className="sectionTitle">
              <div>
                <h3>Ask Questions</h3>
                <p>Questions use the active workspace by default.</p>
              </div>
              <button className="iconButton" aria-label="Close ask panel" onClick={() => setActivePanel(null)}>x</button>
            </div>

            <div className="chipRow">
              {suggestedQuestions.map((suggestion) => (
                <button key={suggestion} onClick={() => setQuestion(suggestion)}>{suggestion}</button>
              ))}
            </div>

            <div className="sourceSelector">
              <strong>Sources</strong>
              <span>
                {selectedDocuments.length
                  ? `${selectedDocuments.length} selected document${selectedDocuments.length === 1 ? "" : "s"}`
                  : "All documents in this workspace"}
              </span>
            </div>

            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask a question about your sources..."
            />
            <button className="primaryButton" onClick={ask} disabled={busy === "ask" || !canUseActions}>
              {busy === "ask" ? "Retrieving" : "Ask"}
            </button>

            {answer ? (
              <div className="answerBox">
                <div className="answerMeta">
                  <span className={answer.grounded ? "pill good" : "pill"}>{answer.grounded ? "Grounded" : "Needs review"}</span>
                  <span className="pill">{answer.method}</span>
                  <span className="pill">{answer.sources.length} sources</span>
                </div>
                <p>{answer.answer}</p>
                {answer.sources.length ? (
                  <div className="citationRow">
                    {answer.sources.slice(0, 6).map((source, index) => (
                      <button key={`${source.filename}-${source.chunk_index}-${index}`} onClick={() => setActivePanel("evidence")}>
                        {source.label}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
          </article>
        ) : null}

        {activePanel === "audio" ? (
          <article className="surface audioPanel">
            <div className="sectionTitle">
              <div>
                <h3>Generate Audiobook</h3>
                <p>Create chapter scripts from a full uploaded document, then generate audio for each chapter.</p>
              </div>
              <button className="iconButton" aria-label="Close audio panel" onClick={() => setActivePanel(null)}>x</button>
            </div>

            <div className="audioControls">
              <label>
                <span>Document</span>
                <select value={audioDocumentId} onChange={(event) => setAudioDocumentId(event.target.value)}>
                  {documents.map((document) => (
                    <option key={document.id} value={document.id}>{document.filename}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Style</span>
                <select value={narrationMode} onChange={(event) => setNarrationMode(event.target.value)}>
                  <option value="simple explanation">Simple explanation</option>
                  <option value="exam revision">Exam revision</option>
                  <option value="podcast">Podcast</option>
                  <option value="storytelling">Storytelling</option>
                  <option value="detailed lecture">Detailed lecture</option>
                  <option value="short summary">Short summary</option>
                </select>
              </label>
              <label>
                <span>Voice</span>
                <select value={voice} onChange={(event) => setVoice(event.target.value)}>
                  <option value="af_heart">Warm narrator</option>
                </select>
              </label>
            </div>

            <button className="primaryButton" onClick={generateAudiobook} disabled={!audioDocumentId || busy === "audiobook"}>
              {busy === "audiobook" ? "Generating audiobook" : "Generate full audiobook"}
            </button>

            {audiobook ? (
              <div className="chapterList">
                <div className="audioBookHeader">
                  <strong>{audiobook.title}</strong>
                  <span>{audiobook.chapters.length} chapters</span>
                </div>
                {audiobook.chapters.map((chapter) => (
                  <div className="chapterCard" key={chapter.id}>
                    <div>
                      <strong>{chapter.chapter_number}. {chapter.title}</strong>
                      <span>{chapter.status}{chapter.duration ? ` / ${Math.round(chapter.duration)}s` : ""}</span>
                    </div>
                    {chapter.audio_url ? <audio controls src={chapter.audio_url} /> : <span className="audioEmpty">Waiting for audio...</span>}
                  </div>
                ))}
              </div>
            ) : (
              <div className="audioEmpty">Choose a document and generate an audiobook.</div>
            )}
          </article>
        ) : null}

        {activePanel === "evidence" ? (
          <section id="evidence" className="surface evidencePanel">
            <div className="sectionTitle">
              <div>
                <h3>Evidence</h3>
                <p>Retrieved source chunks used for the latest answer.</p>
              </div>
              <button className="iconButton" aria-label="Close evidence panel" onClick={() => setActivePanel(null)}>x</button>
            </div>

            <div className="sourceGrid">
              {!evidenceSources.length ? (
                <div className="emptyState">No evidence retrieved yet. Ask a question first.</div>
              ) : evidenceSources.map((source, index) => (
                <details className="sourceCard" key={`${source.filename}-${source.chunk_index}-${index}`} open={index === 0}>
                  <summary>{source.label}</summary>
                  <p>{source.text}</p>
                  <span>Rerank {source.rerank_score.toFixed(3)} / Vector {source.vector_score.toFixed(3)}</span>
                </details>
              ))}
            </div>
          </section>
        ) : null}
      </section>

      {toast ? <div className="toast">{toast}</div> : null}
    </main>
  );
}
