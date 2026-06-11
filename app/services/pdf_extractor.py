import os
import re
import fitz  # PyMuPDF
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Fonts that render only bullet/symbol glyphs (not readable text).
# Detected by checking the font name in the PDF; CMSY10 (F43 in this PDF) is a symbol font.
_SYMBOL_FONT_NAMES = {'cmsy10', 'cmsy7', 'cmsy5'}

_TJ_ELEMENT = re.compile(r'\(([^)]*)\)|([-\d.]+)')
_OP_PATTERN = re.compile(
    r'/(\w+)\s+[\d.]+\s+Tf'       # group 1: font name (Tf)
    r'|([-\d.]+)\s+([-\d.]+)\s+Td'  # group 2,3: dx dy (Td)
    r'|\[([^\]]*)\]\s*TJ',         # group 4: TJ array content
    re.DOTALL
)
_KERNING_SPACE = -200  # kerning more negative than this = word space


# TeX OT1/T1 font encoding: ligature characters stored at low codepoints.
# str.maketrans requires ordinal keys when the replacement is a multi-char string.
_TEX_LIGATURES: dict[int, str] = {
    0x0b: 'ff',   # 11 = ff
    0x0c: 'fi',   # 12 = fi
    0x0d: 'fl',   # 13 = fl
    0x0e: 'ffi',  # 14 = ffi
    0x0f: 'ffl',  # 15 = ffl
    0x14: 'ss',   # 20 = ss ligature
}
_TEX_LIGATURE_TABLE = str.maketrans(_TEX_LIGATURES)


def _decode_pdf_string(s: str) -> str:
    """Decode PDF string escape sequences: \\nnn (octal), \\n, \\r, \\t, \\\\, \\(, \\)"""
    result = []
    i = 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            next_ch = s[i + 1]
            if next_ch.isdigit():
                # Octal escape: up to 3 digits
                octal = ''
                j = i + 1
                while j < len(s) and s[j].isdigit() and len(octal) < 3:
                    octal += s[j]
                    j += 1
                result.append(chr(int(octal, 8)))
                i = j
            elif next_ch == 'n':
                result.append('\n'); i += 2
            elif next_ch == 'r':
                result.append('\r'); i += 2
            elif next_ch == 't':
                result.append('\t'); i += 2
            else:
                result.append(next_ch); i += 2
        else:
            result.append(s[i]); i += 1
    return ''.join(result)


def _decode_tj(content: str, is_symbol: bool) -> str:
    result = ''
    for m in _TJ_ELEMENT.finditer(content):
        if m.group(1) is not None:
            if is_symbol:
                continue
            text = _decode_pdf_string(m.group(1))
            text = text.replace('{', '-').replace('}', '-')
            text = text.translate(_TEX_LIGATURE_TABLE)
            result += text
        else:
            try:
                if float(m.group(2)) < _KERNING_SPACE and not is_symbol:
                    result += ' '
            except ValueError:
                pass
    return result


def _stream_extract(doc: fitz.Document, page_num: int) -> str:
    """
    Reconstruct page text from the raw PDF content stream.
    Handles TeX-generated PDFs where symbol fonts cause PyMuPDF to drop text blocks.
    """
    page = doc.load_page(page_num)
    xrefs = page.get_contents()
    if not xrefs:
        return ''

    # Build a map from resource name (e.g. F43) -> font name (lowercase)
    font_map: dict[str, str] = {}
    for xref, name, ftype, basename, encoding, referencer in page.get_fonts():
        # basename is like 'XDJWFC+CMSY10' — strip the subset prefix
        clean = re.sub(r'^[A-Z]+\+', '', basename).lower()
        font_map[encoding] = clean  # encoding field holds the PDF resource name (F43 etc.)

    stream = doc.xref_stream(xrefs[0]).decode('latin-1')

    lines: list[str] = []
    current_line = ''
    current_font_name = ''

    for m in _OP_PATTERN.finditer(stream):
        if m.group(1):  # Tf — font change
            resource_name = m.group(1)
            new_font_name = font_map.get(resource_name, resource_name.lower())
            # Section headers use a distinct font (e.g. small-caps CMCSC10).
            # Flush current line when switching TO or FROM a section-header font.
            _HEADER_FONTS = {'cmcsc10', 'cmcsc7'}
            is_entering_header = any(hf in new_font_name for hf in _HEADER_FONTS)
            is_leaving_header = any(hf in current_font_name for hf in _HEADER_FONTS)
            if (is_entering_header or is_leaving_header) and current_line.strip():
                lines.append(current_line.strip())
                current_line = ''
            current_font_name = new_font_name

        elif m.group(2) is not None:  # Td — position move
            dx, dy = float(m.group(2)), float(m.group(3))
            if dy < -3:  # vertical descent = new line
                if current_line.strip():
                    lines.append(current_line.strip())
                current_line = ''
            elif dx > 50 and current_line.strip():  # large horizontal jump = field separator
                current_line += '  '

        elif m.group(4) is not None:  # TJ — text
            is_symbol = any(sym in current_font_name for sym in _SYMBOL_FONT_NAMES)
            text = _decode_tj(m.group(4), is_symbol)
            if text:
                current_line += text

    if current_line.strip():
        lines.append(current_line.strip())

    return '\n'.join(lines)


def _words_extract(page: fitz.Page) -> str:
    """
    Reconstruct text from word bounding boxes.
    Auto-detects two-column layouts: if both halves have substantial content,
    outputs left column then right column. Otherwise outputs a single reading-order stream.
    Unicode symbol/icon characters are dropped.
    """
    words = page.get_text('words')
    if not words:
        return ''

    page_mid = page.rect.width / 2

    from collections import defaultdict
    rows: dict[int, list[tuple[float, str]]] = defaultdict(list)
    for w in words:
        x0, y0, text = w[0], w[1], w[4]
        cleaned = ''.join(c if ord(c) < 0x2000 or c.isalpha() or c.isdigit() or c in '.-,@+:/()&%\'\"' else ' ' for c in text).strip()
        if not cleaned:
            continue
        row_key = round(y0 / 5) * 5
        rows[row_key].append((x0, cleaned))

    # Detect genuine two-column layout:
    # A real right column has a cluster of words starting well past the midpoint (>55% of width).
    # Simple word wrapping just past midpoint is NOT a second column.
    col2_start = page.rect.width * 0.55
    right_col_words = sum(1 for row in rows.values() for x, _ in row if x >= col2_start)
    left_count = sum(1 for row in rows.values() for x, _ in row if x < col2_start)
    is_two_column = right_col_words > 5 and (right_col_words / max(left_count, 1)) > 0.25

    if is_two_column:
        # Output left column lines first, then right column lines
        left_lines, right_lines = [], []
        for row_key in sorted(rows.keys()):
            row = rows[row_key]
            left = ' '.join(t for x, t in sorted(row) if x < col2_start)
            right = ' '.join(t for x, t in sorted(row) if x >= col2_start)
            if left.strip():
                left_lines.append(left.strip())
            if right.strip():
                right_lines.append(right.strip())
        all_lines = left_lines + right_lines
    else:
        # Single-column or wide layout: merge all words per row in reading order
        all_lines = []
        for row_key in sorted(rows.keys()):
            line = ' '.join(t for x, t in sorted(rows[row_key]))
            if line.strip():
                all_lines.append(line.strip())

    return '\n'.join(all_lines)


class PDFExtractorService:
    @staticmethod
    def extract_text_from_docx(filepath: str) -> str:
        """
        Extracts text from a .docx file, normalizing output to match PDF extractor format:
        - Tables reconstructed row-by-row (tab-separated cells)
        - Tab-separated designation lines preserved as-is
        - List Paragraph / bullet text prefixed with '- '
        - Section headers emitted as-is
        """
        if not os.path.exists(filepath):
            raise ValueError(f"File not found at: {filepath}")

        import docx
        from docx.oxml.ns import qn

        doc = docx.Document(filepath)
        body = doc.element.body
        lines = []
        in_bullet_block = False
        EMPLOYER_KEYWORDS = ['hospital', 'clinic', 'medical', 'centre', 'center',
                             'college', 'institute', 'foundation', 'healthcare']

        for child in body.iterchildren():
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag

            if tag == 'p':
                p_text = ''.join(run.text for run in child.iter(qn('w:t')))
                if not p_text.strip():
                    continue

                style_val = ''
                style_el = child.find('.//' + qn('w:pStyle'))
                if style_el is not None:
                    style_val = style_el.get(qn('w:val'), '').lower()

                is_heading = 'heading' in style_val
                is_list = 'listparagraph' in style_val or 'listbullet' in style_val
                text = p_text.replace('\t', '  ')

                if is_heading:
                    in_bullet_block = False
                    lines.append(text.strip())
                elif is_list:
                    in_bullet_block = True
                    lines.append('- ' + text.strip())
                else:
                    if '\t' in p_text:
                        in_bullet_block = False
                        tab_parts = p_text.split('\t', 1)
                        designation = tab_parts[0].strip()
                        date_and_rest = tab_parts[1].strip()
                        date_match = re.match(
                            r'((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{4})\S*\s*-\s*'
                            r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{4}|present|current))',
                            date_and_rest, re.IGNORECASE
                        )
                        date_part = date_match.group(1).strip() if date_match else date_and_rest.split(' - ')[0].strip()
                        lines.append(f'{designation}  {date_part}')
                        in_bullet_block = True
                    elif in_bullet_block:
                        is_employer = (
                            len(text.strip()) < 80
                            and text.strip()[0].isupper()
                            and any(kw in text.lower() for kw in EMPLOYER_KEYWORDS)
                            and not text.strip().startswith(('-', '•'))
                        )
                        if is_employer:
                            in_bullet_block = False
                            lines.append(text.strip())
                        else:
                            lines.append('- ' + text.strip())
                    else:
                        lines.append(text.strip())

            elif tag == 'tbl':
                in_bullet_block = False
                for row in child.iter(qn('w:tr')):
                    cells = []
                    for cell in row.iter(qn('w:tc')):
                        cell_text = ''.join(t.text for t in cell.iter(qn('w:t'))).strip()
                        if cell_text:
                            cells.append(cell_text)
                    if cells:
                        lines.append('  '.join(cells))

        if not lines:
            raise ValueError("The DOCX file contains no extractable text.")
        return '\n'.join(lines)

    @staticmethod
    def extract_text(filepath: str) -> str:
        """
        Extracts text from a PDF. Uses PyMuPDF get_text() first; falls back to
        raw stream parsing per-page if get_text() drops content (TeX bullet-font issue).
        """
        if not os.path.exists(filepath):
            raise ValueError(f"File not found at: {filepath}")

        logger.info(f"Extracting text from PDF: {filepath}")

        try:
            doc = fitz.open(filepath)
        except Exception as e:
            logger.error(f"Failed to open/parse PDF {filepath}: {str(e)}")
            raise ValueError("The uploaded PDF file is corrupted or invalid.")

        try:
            if len(doc) == 0:
                raise ValueError("The PDF file contains no pages.")

            pages_text: list[str] = []
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                get_text_result = page.get_text().strip()
                stream_result = _stream_extract(doc, page_num)

                # Prefer stream result (handles TeX symbol-font truncation).
                # Fall back to word-coordinate extraction (handles two-column / CIDFont PDFs).
                # Last resort: raw get_text.
                if stream_result.strip():
                    pages_text.append(stream_result)
                else:
                    words_result = _words_extract(page)
                    if words_result.strip():
                        logger.info(f"Page {page_num}: using word-coordinate extraction")
                        pages_text.append(words_result)
                    elif get_text_result:
                        logger.info(f"Page {page_num}: using get_text fallback")
                        pages_text.append(get_text_result)

            extracted_text = '\n'.join(pages_text).strip()

            if not extracted_text:
                raise ValueError("The PDF file contains no extractable text. It might be scanned or empty.")

            return extracted_text

        finally:
            doc.close()
