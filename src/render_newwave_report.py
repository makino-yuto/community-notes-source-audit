"""Render a new four-page main paper in the retained official template geometry.

Usage: python src/render_newwave_report.py --sourceMD report.md --outputPDF paper.pdf
Use <!-- PAGEBREAK --> (or [[PAGEBREAK]]) between planned main pages.
References and Appendix headings automatically start separate pages.
[[FIGURE1]] inserts --figure plus its generated caption, unless the next
paragraph supplies a Figure 1 caption. Standard Markdown image paths also work.
Supported subscripts: p~a~, <sub>a</sub>, and simple inline math such as $p_a$.
The output is replaced only after the expected main-page count passes.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
try:
    import mistune
except ImportError:
    sys.path.append(str(ROOT / 'tmp' / 'python-packages'))
    import mistune
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, HRFlowable, Image, KeepTogether,
                               PageBreak, Paragraph, Preformatted,
                               PageTemplate, Spacer, Table, TableStyle)

PAGE_WIDTH, PAGE_HEIGHT = letter
MARGIN = 72
FRAME_WIDTH = PAGE_WIDTH - 2 * MARGIN
FONT_DIR = ROOT / 'assets' / 'fonts' / 'old-standard-tt'
FALLBACK_PATH = None


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(text):
    return text.replace('\u2011', '-').replace('\u2013', '-').replace('\u2014', '-').replace('\u2212', '-')


def register_fonts(directory):
    global FALLBACK_PATH
    for name, filename in [('OST', 'OldStandard-Regular.ttf'), ('OST-Bold', 'OldStandard-Bold.ttf'),
                           ('OST-Italic', 'OldStandard-Italic.ttf')]:
        path = directory / filename
        if not path.is_file():
            raise FileNotFoundError(f'Official Google Fonts Old Standard TT asset required: {path}')
        pdfmetrics.registerFont(TTFont(name, str(path)))
    pdfmetrics.registerFontFamily('OST', normal='OST', bold='OST-Bold', italic='OST-Italic', boldItalic='OST-Bold')
    candidates = [ROOT / 'tmp' / 'python-packages' / 'matplotlib' / 'mpl-data' / 'fonts' / 'ttf' / 'DejaVuSerif.ttf']
    try:
        import matplotlib
        candidates.append(Path(matplotlib.get_data_path()) / 'fonts' / 'ttf' / 'DejaVuSerif.ttf')
    except ImportError:
        pass
    candidates.append(Path('C:/Windows/Fonts/times.ttf'))
    FALLBACK_PATH = next((path for path in candidates if path.is_file()), None)
    if FALLBACK_PATH:
        pdfmetrics.registerFont(TTFont('OST-Fallback', str(FALLBACK_PATH)))


def safe_text(value):
    """Keep template text in OST; explicitly cover absent scientific glyphs."""
    value = clean(value)
    main = pdfmetrics.getFont('OST').face.charToGlyph
    fallback = pdfmetrics.getFont('OST-Fallback').face.charToGlyph if FALLBACK_PATH else {}
    pieces = []
    for char in value:
        if ord(char) in main or char.isspace():
            pieces.append(html.escape(char))
        elif ord(char) in fallback:
            pieces.append('<font name="OST-Fallback">' + html.escape(char) + '</font>')
        else:
            raise ValueError(f'No registered font covers U+{ord(char):04X}; replace the character or add an explicit font.')
    return ''.join(pieces)


def make_styles():
    common = dict(fontName='OST', textColor=colors.black, splitLongWords=True)
    return {
        'title': ParagraphStyle('NewTitle', **{**common, 'fontName': 'OST-Bold'}, fontSize=20, leading=23, alignment=TA_CENTER, spaceAfter=10),
        'author': ParagraphStyle('NewAuthor', **{**common, 'fontName': 'OST-Bold'}, fontSize=11, leading=15, alignment=TA_CENTER, spaceAfter=2),
        'affiliation': ParagraphStyle('NewAffiliation', **common, fontSize=11, leading=15, alignment=TA_CENTER, spaceAfter=3),
        'with': ParagraphStyle('NewWith', **common, fontSize=11, leading=14, alignment=TA_CENTER, spaceBefore=3, spaceAfter=8),
        'abstract_head': ParagraphStyle('NewAbstractHead', **{**common, 'fontName': 'OST-Bold'}, fontSize=14, leading=17, alignment=TA_CENTER, spaceBefore=7, spaceAfter=7),
        'abstract': ParagraphStyle('NewAbstract', **common, fontSize=11, leading=15, leftIndent=18, rightIndent=18, alignment=TA_JUSTIFY, spaceAfter=11),
        'body': ParagraphStyle('NewBody', **common, fontSize=11, leading=15, alignment=TA_LEFT, spaceAfter=6),
        'h2': ParagraphStyle('NewHeading2', **{**common, 'fontName': 'OST-Bold'}, fontSize=14, leading=17, spaceBefore=11, spaceAfter=6, keepWithNext=True),
        'h3': ParagraphStyle('NewHeading3', **{**common, 'fontName': 'OST-Bold'}, fontSize=11, leading=15, spaceBefore=8, spaceAfter=4, keepWithNext=True),
        'caption': ParagraphStyle('NewCaption', **common, fontSize=9.5, leading=12, spaceBefore=5, spaceAfter=8),
        'table': ParagraphStyle('NewTable', **common, fontSize=9.5, leading=12, alignment=TA_LEFT),
        'table_head': ParagraphStyle('NewTableHead', **{**common, 'fontName': 'OST-Bold'}, fontSize=9.5, leading=12),
        'reference': ParagraphStyle('NewReference', **common, fontSize=10, leading=13, leftIndent=12, firstLineIndent=-12, spaceAfter=5),
        'code': ParagraphStyle('NewCode', fontName='Courier', fontSize=8.3, leading=11, spaceAfter=8),
    }


def simple_math(raw):
    """A small explicit inline notation surface; reject unsupported TeX."""
    value = clean(raw.strip()).replace('\\,', ' ').replace('\\ ', ' ')
    for command, symbol in {'\\Delta': 'Δ', '\\alpha': 'α', '\\beta': 'β', '\\kappa': 'κ',
                            '\\leq': '≤', '\\geq': '≥', '\\times': '×', '\\pm': '±'}.items():
        value = value.replace(command, symbol)
    if '\\' in value:
        raise ValueError(f'Unsupported inline TeX; use explicit Markdown subscript/superscript or a figure: {raw}')
    token = re.compile(r'([_^])(?:\{([^{}]+)\}|([A-Za-z0-9]))')
    pieces, end = [], 0
    for match in token.finditer(value):
        pieces.append(safe_text(value[end:match.start()]))
        tag = 'sub' if match.group(1) == '_' else 'super'
        pieces.append(f'<{tag}>{safe_text(match.group(2) or match.group(3))}</{tag}>')
        end = match.end()
    pieces.append(safe_text(value[end:]))
    return ''.join(pieces)


def inline(nodes):
    out = []
    for node in nodes:
        kind = node['type']
        if kind == 'text':
            out.append(safe_text(node.get('raw', '')))
        elif kind in {'strong', 'emphasis', 'subscript', 'superscript', 'strikethrough'}:
            tag = {'strong': 'b', 'emphasis': 'i', 'subscript': 'sub', 'superscript': 'super', 'strikethrough': 'strike'}[kind]
            out.append(f'<{tag}>' + inline(node.get('children', [])) + f'</{tag}>')
        elif kind == 'codespan':
            out.append('<font name="Courier" size="9">' + safe_text(node['raw']) + '</font>')
        elif kind == 'link':
            target = html.escape(node.get('attrs', {}).get('url', ''), quote=True)
            out.append(f'<link href="{target}" color="#16516D">' + inline(node.get('children', [])) + '</link>')
        elif kind in {'linebreak', 'softbreak'}:
            out.append('<br/>' if kind == 'linebreak' else ' ')
        elif kind == 'inline_math':
            out.append(simple_math(node['raw']))
        elif kind == 'inline_html':
            raw = node.get('raw', '').strip().lower()
            allowed = {'<sub>': '<sub>', '</sub>': '</sub>', '<sup>': '<super>', '</sup>': '</super>',
                       '<br>': '<br/>', '<br/>': '<br/>', '<i>': '<i>', '</i>': '</i>', '<b>': '<b>', '</b>': '</b>'}
            if raw not in allowed:
                raise ValueError(f'Unsupported inline HTML: {raw}')
            out.append(allowed[raw])
        elif kind != 'image':
            out.append(inline(node.get('children', [])))
    return ''.join(out)


def plain(node):
    if node.get('type') in {'text', 'codespan', 'inline_math'}:
        return clean(node.get('raw', ''))
    if node.get('type') in {'softbreak', 'linebreak'}:
        return ' '
    return ''.join(plain(child) for child in node.get('children', []))


class SectionMarker(Flowable):
    def __init__(self, section):
        super().__init__()
        self.section = section
        self.width = self.height = 0

    def draw(self):
        pass


class TemplateDoc(BaseDocTemplate):
    def __init__(self, *args, **kwargs):
        self.section_pages = {}
        self.heading_index = 0
        super().__init__(*args, **kwargs)
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height,
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id='main')
        self.addPageTemplates(PageTemplate(id='paper', frames=[frame], onPage=footer))

    def afterFlowable(self, flowable):
        if isinstance(flowable, SectionMarker):
            self.section_pages.setdefault(flowable.section, self.page)
        if isinstance(flowable, Paragraph) and hasattr(flowable, 'outline_level'):
            self.heading_index += 1
            key = f'heading-{self.heading_index}'
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(flowable.getPlainText(), key, level=flowable.outline_level, closed=False)


def footer(canvas, document):
    canvas.saveState()
    canvas.setFont('OST', 9)
    canvas.drawRightString(PAGE_WIDTH - MARGIN, 36, str(document.page))
    if document.page == 1:
        canvas.setLineWidth(.5)
        canvas.line(MARGIN, 49, MARGIN + 145, 49)
        canvas.setFont('OST', 9)
        canvas.drawString(MARGIN, 35, '1 Research conducted at the AI x Epistemics Research Sprint, November 2026')
    canvas.restoreState()


def table_flowable(node, styles):
    headers = node['children'][0]['children']
    body = node['children'][1]['children']
    cells = [headers] + [row['children'] for row in body]
    count = len(headers)
    if count == 0:
        raise ValueError('Empty table')
    numeric = []
    weights = []
    for column in range(count):
        values = [plain(row[column]) for row in cells[1:]]
        is_numeric = bool(values) and all(re.fullmatch(r'[\d\s.,%+()/:<>=-]+', v or '') for v in values)
        numeric.append(is_numeric)
        longest = max(len(plain(row[column])) for row in cells)
        weights.append(max(5, min(55, longest)) ** .6 * (.75 if is_numeric else 1))
    widths = [FRAME_WIDTH * w / sum(weights) for w in weights]
    data = [[Paragraph(inline(cell.get('children', [])), styles['table_head' if i == 0 else 'table'])
             for cell in row] for i, row in enumerate(cells)]
    table = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
    rules = [('GRID', (0, 0), (-1, -1), .4, colors.HexColor('#D9D9D9')),
             ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E9EDF0')),
             ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
             ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
             ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]
    for index, is_numeric in enumerate(numeric):
        if is_numeric:
            rules.append(('ALIGN', (index, 1), (index, -1), 'RIGHT'))
            for row in data[1:]:
                row[index].style = ParagraphStyle('NumericCell', parent=styles['table'], alignment=2)
    table.setStyle(TableStyle(rules))
    return table


def figure_flowables(path, caption, styles):
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    image = Image(str(path))
    scale = min(FRAME_WIDTH / image.imageWidth, 1)
    image.drawWidth = image.imageWidth * scale
    image.drawHeight = image.imageHeight * scale
    image.hAlign = 'CENTER'
    result = [image]
    if caption:
        result.append(Paragraph(safe_text(caption), styles['caption']))
    return KeepTogether(result)


def render(source, output, figure, font_dir, expected_main_pages=4):
    if output.resolve() == (ROOT / 'output' / 'pdf' / 'Makino_Community_Notes_Source_Audit.pdf').resolve():
        raise ValueError('The retained legacy PDF is protected; choose a new output filename.')
    register_fonts(font_dir)
    styles = make_styles()
    markdown = mistune.create_markdown(renderer='ast', plugins=['table', 'math', 'subscript', 'superscript', 'strikethrough'])
    nodes = [node for node in markdown(source.read_text(encoding='utf-8')) if node['type'] != 'blank_line']
    if not nodes or nodes[0]['type'] != 'heading' or nodes[0]['attrs']['level'] != 1:
        raise ValueError('The manuscript must start with one # title.')
    title = plain(nodes[0])
    abstract_index = next((i for i, n in enumerate(nodes) if n['type'] == 'heading' and plain(n).lower() == 'abstract'), None)
    if abstract_index is None:
        raise ValueError('A ## Abstract section is required.')
    front = nodes[1:abstract_index]
    if any(n['type'] != 'paragraph' for n in front):
        raise ValueError('Use plain author and affiliation paragraphs before Abstract.')
    front = [n for n in front if plain(n).strip().lower() != 'with apart research']
    if not front:
        raise ValueError('Supply the author and affiliation before Abstract.')
    author = plain(front[0])
    story = [Spacer(1, 8), HRFlowable(width=FRAME_WIDTH, thickness=1.3, color=colors.black), Spacer(1, 9),
             Paragraph(inline(nodes[0]['children']) + '<super size="9">1</super>', styles['title']),
             HRFlowable(width=FRAME_WIDTH, thickness=.6, color=colors.black), Spacer(1, 11)]
    for i, node in enumerate(front):
        story.append(Paragraph(inline(node['children']), styles['author' if i == 0 else 'affiliation']))
    story.append(Paragraph('<b>With</b><br/>Apart Research', styles['with']))
    abstract_words = 0
    in_abstract = False
    in_references = False
    last_was_pagebreak = False
    index = abstract_index
    while index < len(nodes):
        node = nodes[index]
        kind = node['type']
        text = plain(node).strip()
        if kind == 'block_html' and re.fullmatch(r'\s*<!--\s*PAGEBREAK\s*-->\s*', node['raw'], re.I):
            if not last_was_pagebreak:
                story.append(PageBreak())
            last_was_pagebreak = True
            index += 1
            continue
        if kind == 'paragraph' and text in {'[[PAGEBREAK]]', '\\newpage'}:
            if not last_was_pagebreak:
                story.append(PageBreak())
            last_was_pagebreak = True
            index += 1
            continue
        if kind == 'heading':
            level = node['attrs']['level']
            key = re.sub(r'^\d+(?:\.\d+)*[. ]*', '', text).lower()
            if key == 'abstract':
                in_abstract = True
                story.append(Paragraph('Abstract', styles['abstract_head']))
            else:
                in_abstract = False
                section = 'references' if key.startswith('references') else 'appendix' if key.startswith('appendix') else None
                if section:
                    if not last_was_pagebreak:
                        story.append(PageBreak())
                    story.append(SectionMarker(section))
                    in_references = section == 'references'
                elif key.startswith('llm usage'):
                    in_references = False
                paragraph = Paragraph(inline(node['children']), styles['h2' if level <= 2 else 'h3'])
                paragraph.outline_level = 0 if level <= 2 else 1
                story.append(paragraph)
        elif kind == 'paragraph':
            image_node = next((n for n in node.get('children', []) if n['type'] == 'image'), None)
            if text == '[[FIGURE1]]' or image_node:
                path = figure if text == '[[FIGURE1]]' else Path(image_node['attrs']['url'])
                if not path.is_absolute():
                    path = source.parent / path
                caption = ''
                if index + 1 < len(nodes) and nodes[index + 1]['type'] == 'paragraph' and re.match(r'^Figure\s+\d+[.:]', plain(nodes[index + 1])):
                    caption = plain(nodes[index + 1])
                    index += 1
                elif text == '[[FIGURE1]]':
                    caption_file = path.with_name(path.stem + '_caption.txt')
                    if not caption_file.is_file():
                        raise FileNotFoundError(f'Numbered Figure 1 caption required: {caption_file}')
                    caption = caption_file.read_text(encoding='utf-8').strip()
                else:
                    caption = plain(image_node)
                    if not re.match(r'^Figure\s+\d+[.:]', caption):
                        raise ValueError('Provide a numbered Figure caption after the image or in its alt text.')
                story.append(figure_flowables(path, caption, styles))
            else:
                if in_abstract:
                    abstract_words += len(text.split())
                    style = styles['abstract']
                elif re.match(r'^(?:Figure|Table)\s+\d+[.:]', text):
                    style = (ParagraphStyle('NewTableCaption', parent=styles['caption'], keepWithNext=True)
                             if text.startswith('Table ') else styles['caption'])
                else:
                    style = styles['reference' if in_references else 'body']
                story.append(Paragraph(inline(node['children']), style))
        elif kind == 'table':
            story.extend([table_flowable(node, styles), Spacer(1, 7)])
        elif kind == 'list':
            ordered = node.get('attrs', {}).get('ordered', False)
            for i, item in enumerate(node['children'], node.get('attrs', {}).get('start', 1)):
                content = ' '.join(inline(child.get('children', [])) for child in item.get('children', []))
                style = ParagraphStyle('NewListItem', parent=styles['reference' if in_references else 'body'], leftIndent=15, firstLineIndent=-11, spaceAfter=4)
                story.append(Paragraph((f'{i}. ' if ordered else '- ') + content, style))
        elif kind == 'block_code':
            story.append(Preformatted(clean(node['raw']), styles['code'], maxLineLength=91))
        elif kind == 'block_quote':
            for child in node.get('children', []):
                story.append(Paragraph(inline(child.get('children', [])), ParagraphStyle('NewQuote', parent=styles['body'], leftIndent=15, rightIndent=15)))
        elif kind == 'thematic_break':
            story.append(Spacer(1, 6))
        else:
            raise ValueError(f'Unsupported Markdown block: {kind}')
        last_was_pagebreak = False
        index += 1
    if not 150 <= abstract_words <= 250:
        raise ValueError(f'Abstract must contain 150-250 words; found {abstract_words}.')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.stem + '.rendering.pdf')
    document = TemplateDoc(str(temporary), pagesize=letter, leftMargin=MARGIN, rightMargin=MARGIN,
                           topMargin=MARGIN, bottomMargin=MARGIN, title=title, author=author,
                           subject='Current citation inspectability in deployed Community Notes')
    document.build(story)
    reader = PdfReader(temporary)
    first_backmatter = min(document.section_pages.values()) if document.section_pages else len(reader.pages) + 1
    main_pages = first_backmatter - 1
    if expected_main_pages and main_pages != expected_main_pages:
        failed = output.with_name(output.stem + '.failed-layout.pdf')
        temporary.replace(failed)
        raise ValueError(f'Main text occupies {main_pages} pages; expected {expected_main_pages}. Inspect {failed}; adjust content or explicit page breaks.')
    if not {'references', 'appendix'} <= set(document.section_pages):
        raise ValueError('Use separate References and Appendix headings so the submission structure is explicit.')
    temporary.replace(output)
    manifest = {'source_sha256': sha(source), 'renderer_sha256': sha(Path(__file__)),
                'output_sha256': sha(output), 'title': title, 'author': author,
                'total_pages': len(reader.pages), 'main_pages': main_pages,
                'section_start_pages': document.section_pages, 'abstract_words': abstract_words,
                'page_size_points': [PAGE_WIDTH, PAGE_HEIGHT], 'margins_points': MARGIN,
                'frame_width_points': FRAME_WIDTH, 'font_family': 'Old Standard TT',
                'body_point_size': 11, 'body_leading_points': 15, 'title_point_size': 20,
                'heading_point_size': 14, 'fonts_sha256': {p.name: sha(p) for p in font_dir.glob('*.ttf')},
                'scientific_glyph_fallback': str(FALLBACK_PATH) if FALLBACK_PATH else None,
                'visual_QA_required_after_every_final_edit': True}
    output.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(output), 'main_pages': main_pages, 'total_pages': len(reader.pages),
                      'abstract_words': abstract_words, 'section_start_pages': document.section_pages}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sourceMD', '--source', dest='source', required=True, type=Path)
    parser.add_argument('--outputPDF', '--output', dest='output', required=True, type=Path)
    parser.add_argument('--figure', type=Path, default=ROOT / 'output' / 'figures' / 'newwave_access_figure1.png')
    parser.add_argument('--font-dir', type=Path, default=FONT_DIR)
    parser.add_argument('--main-pages', type=int, default=4, help='Required main pages, excluding separate References/Appendix; 0 disables only this count check.')
    args = parser.parse_args()
    render(args.source.resolve(), args.output.resolve(), args.figure.resolve(), args.font_dir.resolve(), args.main_pages)


if __name__ == '__main__':
    main()
