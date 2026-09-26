"""
convert_to_docx.py
Converts FinSight_Experimental_Paper.txt to a properly formatted IEEE-style .docx
matching the layout of FinSight_IEEE_Paper_v10.docx:
  - Times New Roman body (10.5 pt), two-column layout
  - Centered bold title (24 pt), author/affiliation lines
  - Section headings (all-caps Roman numerals), sub-section headings
  - Tables rendered as Word tables
  - Code/equation blocks in Courier New
  - References section
"""

import re
from pathlib import Path
from docx import Document
from docx.shared import Pt, Inches, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# ── Paths ────────────────────────────────────────────────────────────────────
SRC_TXT  = Path(r"C:\Users\soham\Desktop\final1 asep2\FinSight_Experimental_Paper.txt")
OUT_DOCX = Path(r"C:\Users\soham\Desktop\final1 asep2\FinSight_Experimental_Paper.docx")

BODY_FONT   = "Times New Roman"
CODE_FONT   = "Courier New"
BODY_SIZE   = Pt(10.5)
TITLE_SIZE  = Pt(24)
H1_SIZE     = Pt(11)
H2_SIZE     = Pt(10.5)
H3_SIZE     = Pt(10.5)
TABLE_SIZE  = Pt(9)

# ── Helpers ──────────────────────────────────────────────────────────────────

def set_two_columns(section):
    """Apply two-column layout with 0.25-inch gap to a section."""
    sectPr = section._sectPr
    # Remove existing cols element if present
    for c in sectPr.findall(qn("w:cols")):
        sectPr.remove(c)
    cols_el = OxmlElement("w:cols")
    cols_el.set(qn("w:num"), "2")
    cols_el.set(qn("w:space"), "360")   # 0.25 inch in twentieths of a point
    sectPr.append(cols_el)


def set_single_column(section):
    sectPr = section._sectPr
    for c in sectPr.findall(qn("w:cols")):
        sectPr.remove(c)
    cols_el = OxmlElement("w:cols")
    cols_el.set(qn("w:num"), "1")
    sectPr.append(cols_el)


def add_column_break(doc):
    """Insert a column break (used to force content to next column)."""
    p = doc.add_paragraph()
    run = p.add_run()
    br = OxmlElement("w:br")
    br.set(qn("w:type"), "column")
    run._r.append(br)
    return p


def para_font(para, size=BODY_SIZE, bold=False, italic=False,
              font_name=BODY_FONT, color=None, alignment=None):
    pf = para.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after  = Pt(2)
    if alignment is not None:
        para.alignment = alignment
    for run in para.runs:
        run.font.name  = font_name
        run.font.size  = size
        run.font.bold  = bold
        run.font.italic = italic
        if color:
            run.font.color.rgb = color


def add_para(doc, text, size=BODY_SIZE, bold=False, italic=False,
             font_name=BODY_FONT, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY,
             space_after=Pt(2), first_line_indent=None):
    p = doc.add_paragraph()
    p.alignment = alignment
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after  = space_after
    if first_line_indent is not None:
        p.paragraph_format.first_line_indent = first_line_indent

    # Handle inline bold (**text**) and italic (*text*) markers
    parts = re.split(r'(\*\*[^*]+\*\*|\*[^*]+\*)', text)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            run = p.add_run(part[2:-2])
            run.bold = True
        elif part.startswith("*") and part.endswith("*"):
            run = p.add_run(part[1:-1])
            run.italic = True
        else:
            run = p.add_run(part)
        run.font.name  = font_name
        run.font.size  = size
        run.font.bold  = bold if not run.bold else True
        run.font.italic = italic if not run.italic else True
    return p


def add_heading(doc, text, level=1):
    if level == 1:
        # Roman-numeral section heading: centered, small-caps style
        p = add_para(doc, text, size=H1_SIZE, bold=True,
                     alignment=WD_ALIGN_PARAGRAPH.CENTER, space_after=Pt(4))
    elif level == 2:
        p = add_para(doc, text, size=H2_SIZE, bold=True,
                     alignment=WD_ALIGN_PARAGRAPH.LEFT, space_after=Pt(2))
    else:
        p = add_para(doc, text, size=H3_SIZE, bold=True, italic=True,
                     alignment=WD_ALIGN_PARAGRAPH.LEFT, space_after=Pt(2))
    p.paragraph_format.space_before = Pt(6)
    return p


def add_code_block(doc, lines):
    """Add a code/equation block in Courier New with a light-grey shading."""
    for line in lines:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after  = Pt(0)
        p.paragraph_format.left_indent  = Inches(0.15)
        run = p.add_run(line)
        run.font.name = CODE_FONT
        run.font.size = Pt(8)

        # Light grey paragraph shading
        pPr = p._p.get_or_add_pPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), "F2F2F2")
        pPr.append(shd)
    # small gap after block
    g = doc.add_paragraph()
    g.paragraph_format.space_after = Pt(2)


def add_table_from_md(doc, md_lines):
    """Parse a markdown table and render it as a Word table."""
    rows = []
    for line in md_lines:
        line = line.strip()
        if re.match(r'^[\|\s:\-]+$', line):
            continue  # separator row
        cells = [c.strip() for c in line.strip('|').split('|')]
        if cells:
            rows.append(cells)

    if not rows:
        return

    n_cols = len(rows[0])
    tbl = doc.add_table(rows=len(rows), cols=n_cols)
    tbl.style = 'Table Grid'

    for r_idx, row in enumerate(rows):
        for c_idx, cell_text in enumerate(row):
            cell = tbl.rows[r_idx].cells[c_idx]
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            # Strip markdown bold markers
            plain = re.sub(r'\*\*([^*]+)\*\*', r'\1', cell_text)
            run = p.add_run(plain)
            run.font.name = BODY_FONT
            run.font.size = TABLE_SIZE
            if r_idx == 0:
                run.font.bold = True

    doc.add_paragraph().paragraph_format.space_after = Pt(4)


# ── Main conversion ───────────────────────────────────────────────────────────

def convert(src: Path, out: Path):
    doc = Document()

    # Page setup — IEEE letter size, narrow margins (matching v10)
    section = doc.sections[0]
    section.page_width   = Inches(8.5)
    section.page_height  = Inches(11)
    section.top_margin   = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    section.left_margin  = Inches(0.625)
    section.right_margin = Inches(0.625)

    # Start with single column for title block
    set_single_column(section)

    lines = src.read_text(encoding="utf-8").splitlines()

    in_code    = False
    code_buf   = []
    in_table   = False
    table_buf  = []
    title_done = False
    body_started = False  # True once we pass the title block into body

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # ── Code block ────────────────────────────────────────────────────
        if stripped.startswith("```"):
            if in_code:
                add_code_block(doc, code_buf)
                code_buf = []
                in_code  = False
            else:
                in_code = True
            i += 1
            continue

        if in_code:
            code_buf.append(line)
            i += 1
            continue

        # ── Table ─────────────────────────────────────────────────────────
        if stripped.startswith("|"):
            if not in_table:
                in_table = True
                table_buf = []
            table_buf.append(stripped)
            i += 1
            continue
        else:
            if in_table:
                add_table_from_md(doc, table_buf)
                table_buf = []
                in_table  = False

        # ── Empty line ────────────────────────────────────────────────────
        if not stripped:
            i += 1
            continue

        # ── Horizontal rule ───────────────────────────────────────────────
        if re.match(r'^-{3,}$', stripped) or re.match(r'^\*{3,}$', stripped):
            i += 1
            continue

        # ── Headings ──────────────────────────────────────────────────────
        if stripped.startswith("#### "):
            add_heading(doc, stripped[5:], level=3)
            i += 1; continue

        if stripped.startswith("### "):
            text = stripped[4:]
            add_heading(doc, text, level=2)
            i += 1; continue

        if stripped.startswith("## "):
            text = stripped[3:]
            # Switch to two-column when we hit the body
            if not body_started and text.upper().startswith("I."):
                body_started = True
                # Insert section break to start two-column layout
                new_sec = doc.add_section()
                new_sec.page_width   = section.page_width
                new_sec.page_height  = section.page_height
                new_sec.top_margin   = section.top_margin
                new_sec.bottom_margin = section.bottom_margin
                new_sec.left_margin  = section.left_margin
                new_sec.right_margin = section.right_margin
                set_two_columns(new_sec)

            add_heading(doc, text, level=1)
            i += 1; continue

        if stripped.startswith("# "):
            text = stripped[2:]
            # Paper title
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after  = Pt(6)
            run = p.add_run(text)
            run.font.name = BODY_FONT
            run.font.size = TITLE_SIZE
            run.font.bold = True
            title_done = True
            i += 1; continue
            
        # ── Images ![Caption](path) ───────────────────────────────────────
        img_match = re.match(r'^!\[(.*?)\]\((.*?)\)$', stripped)
        if img_match:
            caption = img_match.group(1)
            img_path = img_match.group(2)
            try:
                # Add picture, centered
                p_img = doc.add_paragraph()
                p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run_img = p_img.add_run()
                run_img.add_picture(img_path, width=Inches(3.0)) # Fits inside one column
                
                # Add caption
                p_cap = doc.add_paragraph()
                p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_cap.paragraph_format.space_before = Pt(2)
                p_cap.paragraph_format.space_after = Pt(6)
                run_cap = p_cap.add_run(caption)
                run_cap.font.name = BODY_FONT
                run_cap.font.size = Pt(9)
                run_cap.italic = True
            except Exception as e:
                print(f"Failed to add image {img_path}: {e}")
            i += 1; continue

        # ── Blockquote (>) ────────────────────────────────────────────────
        if stripped.startswith("> "):
            text = stripped[2:]
            # Remove [!NOTE] / [!TIP] etc.
            text = re.sub(r'\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]', '', text).strip()
            if text:
                p = add_para(doc, text, italic=True, size=Pt(9.5),
                             alignment=WD_ALIGN_PARAGRAPH.JUSTIFY)
                p.paragraph_format.left_indent  = Inches(0.2)
                p.paragraph_format.right_indent = Inches(0.2)
            i += 1; continue

        # ── Bullet / numbered list ────────────────────────────────────────
        list_m = re.match(r'^(\s*)([-*+]|\d+\.)\s+(.*)', stripped)
        if list_m:
            indent_level = len(line) - len(line.lstrip())
            content = list_m.group(3)
            p = add_para(doc, content, size=BODY_SIZE,
                         alignment=WD_ALIGN_PARAGRAPH.LEFT, space_after=Pt(1))
            p.paragraph_format.left_indent       = Inches(0.2 + indent_level * 0.15)
            p.paragraph_format.first_line_indent = Inches(-0.15)
            i += 1; continue

        # ── Title-block lines (authors, affiliation, abstract, index terms) ──
        if not body_started:
            lower = stripped.lower()
            if lower.startswith("abstract"):
                p = add_para(doc, stripped, bold=False,
                             alignment=WD_ALIGN_PARAGRAPH.JUSTIFY,
                             first_line_indent=Inches(0.2))
            elif lower.startswith("index terms"):
                p = add_para(doc, stripped, italic=True,
                             alignment=WD_ALIGN_PARAGRAPH.JUSTIFY,
                             first_line_indent=Inches(0.2))
            else:
                p = add_para(doc, stripped,
                             alignment=WD_ALIGN_PARAGRAPH.CENTER,
                             size=Pt(10.5))
            i += 1; continue

        # ── Reference entries [N] ─────────────────────────────────────────
        ref_m = re.match(r'^\[(\d+)\]\s+(.*)', stripped)
        if ref_m:
            ref_text = f"[{ref_m.group(1)}] {ref_m.group(2)}"
            p = add_para(doc, ref_text, size=Pt(9),
                         alignment=WD_ALIGN_PARAGRAPH.LEFT, space_after=Pt(2))
            p.paragraph_format.left_indent       = Inches(0.25)
            p.paragraph_format.first_line_indent = Inches(-0.25)
            i += 1; continue

        # ── Body paragraph ────────────────────────────────────────────────
        add_para(doc, stripped, size=BODY_SIZE,
                 alignment=WD_ALIGN_PARAGRAPH.JUSTIFY,
                 first_line_indent=Inches(0.2))
        i += 1

    # Flush any remaining table
    if in_table:
        add_table_from_md(doc, table_buf)

    doc.save(str(out))
    print(f"[OK] Saved: {out}")


if __name__ == "__main__":
    convert(SRC_TXT, OUT_DOCX)
