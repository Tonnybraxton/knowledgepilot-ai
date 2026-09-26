import io
from dataclasses import dataclass

from docx import Document as DocxDocument
from docx.text.paragraph import Paragraph
from pypdf import PdfReader


@dataclass(frozen=True)
class Passage:
    text: str
    page: int | None = None
    section: str | None = None


def extract(content: bytes, mime: str) -> list[Passage]:
    if mime == "application/pdf":
        pdf = PdfReader(io.BytesIO(content))
        if pdf.is_encrypted:
            raise ValueError("Password-protected PDFs are not supported. Upload an unlocked copy.")
        if len(pdf.pages) > 1000:
            raise ValueError("This PDF exceeds the 1,000-page processing limit.")
        passages = [
            Passage(page.extract_text() or "", index + 1) for index, page in enumerate(pdf.pages)
        ]
    elif "wordprocessingml" in mime:
        doc = DocxDocument(io.BytesIO(content))
        passages = []
        section = None
        for item in doc.iter_inner_content():
            if isinstance(item, Paragraph):
                if item.style and item.style.name and item.style.name.startswith("Heading"):
                    section = item.text[:500]
                passages.append(Passage(item.text, section=section))
            else:
                passages.append(
                    Passage(
                        "\n".join(" | ".join(cell.text for cell in row.cells) for row in item.rows),
                        section=section,
                    )
                )
    else:
        section = None
        passages = []
        for paragraph in content.decode("utf-8-sig").split("\n\n"):
            if mime == "text/markdown" and paragraph.startswith("#"):
                section = paragraph.splitlines()[0].lstrip("# ")[:500]
            passages.append(Passage(paragraph, section=section))
    if not any(p.text.strip() for p in passages):
        raise ValueError("No readable text found. Scanned documents need OCR before upload.")
    if sum(len(p.text) for p in passages) > 5_000_000:
        raise ValueError("Extracted text exceeds the processing limit.")
    return passages
