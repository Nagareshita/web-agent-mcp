"""Tests for PDF extraction."""
import pytest
from pathlib import Path


def test_pdf_extract(tmp_path):
    """Create a minimal PDF and extract text from it."""
    pytest.importorskip("fitz")

    import fitz

    # Create a simple one-page PDF
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello PDF extraction test content here.")
    pdf_path = tmp_path / "test.pdf"
    doc.save(str(pdf_path))
    doc.close()

    from web_agent_mcp.extract.pdf import extract_pdf

    title, pages = extract_pdf(pdf_path)
    assert len(pages) == 1
    page_num, text = pages[0]
    assert page_num == 1
    assert "Hello PDF" in text
