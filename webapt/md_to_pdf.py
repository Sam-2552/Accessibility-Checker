"""Markdown to PDF conversion using WeasyPrint."""

from pathlib import Path

import markdown
from weasyprint import HTML


# Professional CSS for report PDFs
PDF_CSS = """
@page {
    size: A4;
    margin: 2cm;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #333;
    max-width: 100%;
}

h1 {
    color: #1a1a2e;
    border-bottom: 2px solid #16213e;
    padding-bottom: 8px;
    font-size: 20pt;
    margin-top: 24pt;
}

h2 {
    color: #16213e;
    border-bottom: 1px solid #e0e0e0;
    padding-bottom: 4px;
    font-size: 16pt;
    margin-top: 18pt;
}

h3 {
    color: #0f3460;
    font-size: 13pt;
    margin-top: 14pt;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 12pt 0;
    font-size: 9pt;
}

th, td {
    border: 1px solid #ddd;
    padding: 6pt 8pt;
    text-align: left;
    word-wrap: break-word;
}

th {
    background-color: #16213e;
    color: white;
    font-weight: 600;
}

tr:nth-child(even) {
    background-color: #f8f9fa;
}

img {
    max-width: 100%;
    height: auto;
    border: 1px solid #ddd;
    border-radius: 4px;
    margin: 8pt 0;
    page-break-inside: avoid;
}

code {
    background-color: #f4f4f4;
    padding: 2pt 4pt;
    border-radius: 3px;
    font-size: 9pt;
    font-family: "Fira Code", "Courier New", monospace;
}

pre {
    background-color: #f4f4f4;
    padding: 10pt;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 9pt;
    border: 1px solid #e0e0e0;
    page-break-inside: avoid;
}

pre code {
    background: none;
    padding: 0;
}

blockquote {
    border-left: 4px solid #16213e;
    margin: 10pt 0;
    padding: 6pt 12pt;
    background-color: #f8f9fa;
}
"""


def convert_md_to_pdf(md_path: str | Path, pdf_path: str | Path | None = None) -> Path:
    """Convert a Markdown file to PDF.

    Args:
        md_path: Path to the input Markdown file.
        pdf_path: Path for the output PDF. If None, uses same name with .pdf extension
                  in a 'pdf' sibling directory.

    Returns:
        Path to the generated PDF file.
    """
    md_path = Path(md_path)
    if not md_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    if pdf_path is None:
        pdf_dir = md_path.parent.parent / "pdf"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = pdf_dir / md_path.with_suffix(".pdf").name
    else:
        pdf_path = Path(pdf_path)
        pdf_path.parent.mkdir(parents=True, exist_ok=True)

    md_content = md_path.read_text(encoding="utf-8")

    # Convert MD to HTML
    html_body = markdown.markdown(
        md_content,
        extensions=["tables", "fenced_code", "toc", "attr_list"],
    )

    html_doc = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>{PDF_CSS}</style>
</head>
<body>
{html_body}
</body>
</html>"""

    # Use the markdown file's directory as base_url so relative image paths resolve
    HTML(string=html_doc, base_url=str(md_path.parent)).write_pdf(str(pdf_path))

    return pdf_path


def convert_all_reports(project_dir: str | Path) -> list[Path]:
    """Convert all Markdown reports in a project directory to PDF.

    Searches accessibility_reports/ and analysis_reports/ for .md files
    and converts each to PDF in the pdf/ directory.

    Args:
        project_dir: Path to the project output directory.

    Returns:
        List of generated PDF paths.
    """
    project_dir = Path(project_dir)
    pdf_dir = project_dir / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    pdfs = []
    report_dirs = [
        project_dir / "accessibility_reports",
        project_dir / "analysis_reports",
    ]

    # Also check for qa_report.md in project root
    qa_report = project_dir / "qa_report.md"
    if qa_report.exists():
        pdf_path = pdf_dir / "qa_report.pdf"
        convert_md_to_pdf(qa_report, pdf_path)
        pdfs.append(pdf_path)

    for report_dir in report_dirs:
        if not report_dir.exists():
            continue
        for md_file in sorted(report_dir.glob("*.md")):
            pdf_path = pdf_dir / md_file.with_suffix(".pdf").name
            try:
                convert_md_to_pdf(md_file, pdf_path)
                pdfs.append(pdf_path)
            except Exception as e:
                print(f"Warning: Failed to convert {md_file.name}: {e}")

    return pdfs
