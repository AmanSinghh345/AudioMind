from streamlit.testing.v1 import AppTest


def test_main_workspaces_render():
    app = AppTest.from_file("streamlit_app.py", default_timeout=30).run()
    assert not app.exception
    labels = [tab.label for tab in app.tabs]
    assert labels == [
        "Document Library", "RAG Tutor", "Audiobook Studio", "Transparency"
    ]
    assert app.title or app.markdown
