from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from audiomind.tts import AudioGenerator
from audiomind.services import get_services


st.set_page_config(page_title="AudioMind", page_icon="🎧", layout="wide")
st.markdown(
    """
    <style>
    .block-container{max-width:1220px;padding-top:2rem}.hero{padding:1.4rem 1.6rem;
    border:1px solid #263247;border-radius:16px;background:linear-gradient(135deg,#101827,#172036);
    margin-bottom:1.2rem}.hero h1{margin:0;font-size:2.6rem}.hero p{color:#aab6cb;margin:.45rem 0 0}
    [data-testid="stMetric"]{border:1px solid #263247;padding:.7rem;border-radius:10px}
    </style><div class="hero"><h1>AudioMind</h1><p>Source-grounded tutoring and chapter-wise
    audiobooks from your own study material.</p></div>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def load_services():
    return get_services()


@st.cache_resource
def load_audio():
    service = load_services()
    return AudioGenerator(service.settings.kokoro_env_name, service.settings.audio_path)


services = load_services()
repository = services.repository
repository.ensure_default_collection()


def choose_collection() -> str:
    st.sidebar.title("Workspace")
    collections = repository.list_collections()
    choices = {item["name"]: item["id"] for item in collections}
    name = st.sidebar.selectbox("Collection", list(choices))
    with st.sidebar.expander("Create collection"):
        new_name = st.text_input("Collection name")
        description = st.text_input("Description")
        if st.button("Create", use_container_width=True):
            try:
                if len(new_name.strip()) < 2:
                    raise ValueError("Name is too short")
                repository.create_collection(new_name, description)
                st.rerun()
            except Exception:
                st.error("Use a unique name with at least two characters.")
    st.sidebar.caption(f"Gemini: {'configured' if os.getenv('GEMINI_API_KEY') else 'offline fallback'}")
    st.sidebar.caption(f"Embeddings: {services.embeddings.method}")
    return choices[name]


collection_id = choose_collection()
library, tutor, studio, transparency = st.tabs(
    ["Document Library", "RAG Tutor", "Audiobook Studio", "Transparency"]
)


with library:
    st.subheader("Add study material")
    uploaded = st.file_uploader(
        "PDF, DOCX, TXT, Markdown, or scanned notes",
        type=["pdf", "docx", "txt", "md", "csv", "png", "jpg", "jpeg"],
    )
    use_ocr = st.checkbox("OCR scanned PDF pages", True)
    if uploaded and st.button("Index document", type="primary"):
        with st.spinner("Extracting pages, chunking, embedding, and indexing…"):
            try:
                indexed = services.ingestion.ingest_bytes(
                    collection_id, uploaded.name, uploaded.getvalue(), use_ocr
                )
                if indexed.get("deduplicated"):
                    st.info("This exact document is already indexed.")
                else:
                    st.success(
                        f"Indexed {indexed['page_count']} pages into {indexed['chunk_count']} chunks."
                    )
            except Exception as exc:
                st.error(f"Indexing failed: {exc}")

    with st.expander("Index a public web page"):
        page_url = st.text_input("URL", placeholder="https://example.com/study-notes")
        if st.button("Index URL", disabled=not page_url.strip()):
            with st.spinner("Downloading safely and indexing readable content…"):
                try:
                    indexed = services.web_ingestion.ingest_url(collection_id, page_url)
                    st.success(f"Indexed {indexed['chunk_count']} chunks from the page.")
                except Exception as exc:
                    st.error(f"URL indexing failed: {exc}")

    st.subheader("Indexed documents")
    documents = repository.list_documents(collection_id)
    if not documents:
        st.info("Upload a document to enable the tutor and audiobook studio.")
    for document in documents:
        with st.container(border=True):
            title, pages, chunks, action = st.columns([4, 1, 1, 1])
            title.markdown(f"**{document['filename']}**\n\n{document['status']}")
            pages.metric("Pages", document["page_count"])
            chunks.metric("Chunks", document["chunk_count"])
            if action.button("Remove", key=f"remove_{document['id']}"):
                services.ingestion.delete(document["id"])
                st.rerun()


with tutor:
    st.subheader("Ask from your collection")
    st.caption("AudioMind retrieves and reranks source chunks before answering. Unsupported questions are refused.")
    question = st.text_area(
        "Question", placeholder="Explain the main concept simply and cite its pages.", height=100
    )
    if st.button("Ask AudioMind", type="primary", disabled=not question.strip()):
        with st.spinner("Retrieving evidence and grounding the answer…"):
            try:
                st.session_state.rag_answer = services.rag.ask(collection_id, question)
            except Exception as exc:
                st.error(f"Question failed: {exc}")

    answer = st.session_state.get("rag_answer")
    if answer:
        st.markdown("### Answer")
        st.write(answer.answer)
        col1, col2, col3 = st.columns(3)
        col1.metric("Grounded", "Yes" if answer.grounded else "No")
        col2.metric("Method", answer.method)
        col3.metric("Sources", len(answer.sources))
        if st.button("Listen to answer"):
            with st.spinner("Generating answer audio…"):
                generated = load_audio().generate_audio(answer.answer)
            if generated["success"]:
                st.session_state.answer_audio = generated["file_path"]
            else:
                st.error(generated["error"])
        answer_audio = st.session_state.get("answer_audio")
        if answer_audio and Path(answer_audio).exists():
            st.audio(answer_audio)
        for index, source in enumerate(answer.sources, 1):
            with st.expander(f"[{index}] {source.label} · score {source.rerank_score:.3f}"):
                st.write(source.text)
                st.caption(
                    f"Vector {source.vector_score:.3f} · reranked {source.rerank_score:.3f} · {source.chapter}"
                )


with studio:
    st.subheader("Chapter-wise audiobook studio")
    ready_documents = [item for item in repository.list_documents(collection_id) if item["status"] == "ready"]
    if not ready_documents:
        st.info("Index a document first.")
    else:
        document_choices = {item["filename"]: item["id"] for item in ready_documents}
        selected_name = st.selectbox("Document", list(document_choices))
        document_id = document_choices[selected_name]
        mode_col, voice_col = st.columns(2)
        mode = mode_col.selectbox(
            "Mode",
            ["simple explanation", "exam revision", "podcast", "storytelling", "detailed lecture", "short summary"],
        )
        voice = voice_col.selectbox("Voice", ["af_heart", "af_bella", "am_adam", "am_michael"])
        if st.button("Create chapter scripts", type="primary"):
            with st.spinner("Writing chapter scripts with automatic offline fallback…"):
                try:
                    created = services.narration.create_scripts(document_id, mode, voice)
                    st.session_state.audiobook_id = created["id"]
                    st.success(f"Created {len(created['chapters'])} editable scripts.")
                except Exception as exc:
                    st.error(f"Script generation failed: {exc}")

        drafts = repository.list_audiobooks(document_id)
        if drafts:
            draft_choices = {f"{item['mode']} · {item['created_at'][:16]}": item["id"] for item in drafts}
            label = st.selectbox("Draft", list(draft_choices))
            book = repository.get_audiobook(draft_choices[label])
            for chapter in book["chapters"]:
                heading = f"Chapter {chapter['chapter_number']}: {chapter['title']}"
                with st.expander(heading, expanded=True):
                    script = st.text_area(
                        "Editable script", chapter["script"], height=220, key=f"script_{chapter['id']}"
                    )
                    save_col, generate_col = st.columns(2)
                    if save_col.button("Save script", key=f"save_{chapter['id']}"):
                        repository.update_chapter_script(chapter["id"], script)
                        st.success("Saved")
                    if generate_col.button("Generate audio", key=f"generate_{chapter['id']}"):
                        repository.update_chapter_script(chapter["id"], script)
                        output = services.settings.audio_path / f"chapter_{chapter['id']}.wav"
                        with st.spinner("Generating isolated Kokoro audio…"):
                            generated = load_audio().generate_audio(script, output)
                        if generated["success"]:
                            repository.update_chapter_audio(
                                chapter["id"], generated["file_path"], generated["duration"]
                            )
                            st.rerun()
                        else:
                            st.error(generated["error"])
                    if chapter.get("audio_path") and Path(chapter["audio_path"]).exists():
                        st.audio(chapter["audio_path"])
                        with open(chapter["audio_path"], "rb") as audio_file:
                            st.download_button(
                                "Download chapter", audio_file.read(),
                                file_name=f"{chapter['chapter_number']:02d}_{chapter['title']}.wav",
                                mime="audio/wav", key=f"download_{chapter['id']}",
                            )


with transparency:
    st.subheader("Retrieval history")
    history = repository.list_qa(collection_id)
    if not history:
        st.info("Questions and their evidence will appear here.")
    for item in history:
        with st.expander(item["question"]):
            st.write(item["answer"])
            st.caption(f"{len(item['sources'])} sources · {item['created_at']}")
            for source in item["sources"]:
                st.markdown(
                    f"- {source['filename']}, page {source['page_number']}, chunk {source['chunk_index'] + 1}"
                )
