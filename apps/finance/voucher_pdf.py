"""Generation d'une piece comptable PDF (mouvement bancaire) + annexes fusionnees.

Pile 100 % Windows-friendly, sans dependance systeme :
  - reportlab   : construit la page de garde (la piece) en partie double ;
  - Pillow      : lecture des images annexes ;
  - pypdf       : concatene les annexes PDF derriere la piece.

Les annexes images (jpg/png/...) sont converties en pages PDF. Les annexes
PDF sont ajoutees telles quelles. Les autres formats (ex: .docx) ne sont pas
fusionnables et sont signales sur une page recapitulative finale.
"""

from decimal import Decimal
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from pypdf import PdfReader, PdfWriter

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff"}

_GREEN = colors.HexColor("#1c6b48")
_LINE = colors.HexColor("#d9d4c7")


def _fmt(amount):
    """Formate un montant XOF en 1 234 567 (separateur d'espace insecable)."""
    if amount is None:
        amount = Decimal("0")
    return f"{int(round(float(amount))):,}".replace(",", " ")


def _build_cover(context) -> BytesIO:
    """Construit la piece comptable (page de garde) et renvoie un BytesIO PDF."""
    movement = context["movement"]
    account = context["account"]
    entry = context["entry"]
    lines = context["journal_lines"]
    allocations = context["allocations"]
    documents = context["documents"]

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"Piece {context['piece_ref']}",
    )
    styles = getSampleStyleSheet()
    h_title = ParagraphStyle("title", parent=styles["Title"], textColor=_GREEN, fontSize=18, spaceAfter=2)
    h_sub = ParagraphStyle("sub", parent=styles["Normal"], fontSize=9, textColor=colors.grey)
    h_sec = ParagraphStyle("sec", parent=styles["Heading2"], textColor=_GREEN, fontSize=12, spaceBefore=10, spaceAfter=4)
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=9, leading=12)
    cell_b = ParagraphStyle("cellb", parent=cell, fontName="Helvetica-Bold")

    elems = []
    elems.append(Paragraph("PIECE COMPTABLE", h_title))
    elems.append(Paragraph(
        f"Reference&nbsp;: <b>{context['piece_ref']}</b> &middot; "
        f"Compte&nbsp;: {account.name} &middot; "
        f"Date d'operation&nbsp;: {movement.date_operation:%d/%m/%Y}",
        h_sub,
    ))
    elems.append(Spacer(1, 6))

    # --- Bloc en-tete mouvement ---
    sens = "Entree (credit bancaire)" if context["is_credit"] else "Sortie (debit bancaire)"
    head_rows = [
        [Paragraph("Sens", cell_b), Paragraph(sens, cell),
         Paragraph("Montant", cell_b), Paragraph(f"{_fmt(context['amount'])} {account.currency}", cell_b)],
        [Paragraph("Libelle", cell_b), Paragraph(movement.label or "&mdash;", cell),
         Paragraph("Reference releve", cell_b), Paragraph(movement.reference or "&mdash;", cell)],
        [Paragraph("Beneficiaire / source", cell_b), Paragraph(movement.recipient or "&mdash;", cell),
         Paragraph("Projet", cell_b),
         Paragraph(
             (f"<b>{movement.project.code}</b> &mdash; {movement.project.title}")
             if movement.project else "Budget General", cell)],
    ]
    t = Table(head_rows, colWidths=[34 * mm, 58 * mm, 34 * mm, 48 * mm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, _LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f4f2ea")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f4f2ea")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elems.append(t)

    if movement.commentary:
        elems.append(Spacer(1, 4))
        elems.append(Paragraph(f"<i>Commentaire&nbsp;:</i> {movement.commentary}", cell))

    # --- Ecriture en partie double ---
    elems.append(Paragraph("Imputation comptable (partie double SYCEBNL)", h_sec))
    je_rows = [[Paragraph("Compte", cell_b), Paragraph("Libelle", cell_b),
                Paragraph("Debit", cell_b), Paragraph("Credit", cell_b)]]
    if lines:
        for l in lines:
            je_rows.append([
                Paragraph(f"{l.account.code} - {l.account.name}", cell),
                Paragraph(l.label or "", cell),
                Paragraph(_fmt(l.debit) if l.debit else "", cell),
                Paragraph(_fmt(l.credit) if l.credit else "", cell),
            ])
        je_rows.append([
            Paragraph("", cell), Paragraph("TOTAL", cell_b),
            Paragraph(_fmt(context["total_debit"]), cell_b),
            Paragraph(_fmt(context["total_credit"]), cell_b),
        ])
    else:
        je_rows.append([Paragraph("Aucune ecriture comptable rattachee.", cell), "", "", ""])

    jt = Table(je_rows, colWidths=[64 * mm, 60 * mm, 25 * mm, 25 * mm])
    jt.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, _LINE),
        ("BACKGROUND", (0, 0), (-1, 0), _GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (2, 0), (3, -1), "RIGHT"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, _GREEN),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elems.append(jt)

    # --- Ventilations analytiques ---
    if allocations:
        elems.append(Paragraph("Ventilation analytique", h_sec))
        al_rows = [[Paragraph("Projet", cell_b), Paragraph("Ligne budgetaire", cell_b),
                    Paragraph("Compte", cell_b), Paragraph("Montant", cell_b)]]
        for a in allocations:
            al_rows.append([
                Paragraph(a.project.code if a.project else "&mdash;", cell),
                Paragraph(a.budget_line.code if a.budget_line else "&mdash;", cell),
                Paragraph(a.contra_account.code if a.contra_account else "&mdash;", cell),
                Paragraph(_fmt(a.amount), cell),
            ])
        at = Table(al_rows, colWidths=[28 * mm, 56 * mm, 40 * mm, 30 * mm])
        at.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, _LINE),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4f2ea")),
            ("ALIGN", (3, 0), (3, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elems.append(at)

    # --- Liste des annexes ---
    elems.append(Paragraph("Pieces justificatives (annexes)", h_sec))
    if documents:
        labels = {dt.value: dt.label for dt in type(documents[0]).DocumentType}
        an_rows = [[Paragraph("#", cell_b), Paragraph("Type", cell_b),
                    Paragraph("Libelle / fichier", cell_b), Paragraph("Annexe", cell_b)]]
        for i, d in enumerate(documents, start=1):
            name = Path(d.file.name).name if d.file else ""
            ext = Path(name).suffix.lower()
            joined = "PDF" if ext == ".pdf" else ("Image" if ext in IMAGE_EXTS else "Non fusionnee")
            an_rows.append([
                Paragraph(str(i), cell),
                Paragraph(labels.get(d.document_type, d.document_type), cell),
                Paragraph(d.label or name, cell),
                Paragraph(joined, cell),
            ])
        ant = Table(an_rows, colWidths=[10 * mm, 44 * mm, 80 * mm, 30 * mm])
        ant.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, _LINE),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4f2ea")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elems.append(ant)
        elems.append(Spacer(1, 4))
        elems.append(Paragraph(
            "Les annexes PDF et images suivent cette page. Les pieces marquees "
            "« Non fusionnee » (ex: Word, Excel) ne sont pas integrables "
            "au PDF : se referer a la piece electronique d'origine.", h_sub,
        ))
    else:
        elems.append(Paragraph("Aucune piece justificative attachee.", cell))

    doc.build(elems)
    buf.seek(0)
    return buf


def _image_to_pdf_page(path: Path, title: str) -> BytesIO:
    """Convertit une image en une page PDF A4 (image centree, titre en haut)."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 18 * mm
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(_GREEN)
    c.drawString(margin, height - margin, f"Annexe : {title}"[:110])
    c.setFillColor(colors.black)

    img = ImageReader(str(path))
    iw, ih = img.getSize()
    max_w = width - 2 * margin
    max_h = height - 2 * margin - 8 * mm
    scale = min(max_w / iw, max_h / ih)
    dw, dh = iw * scale, ih * scale
    x = (width - dw) / 2
    y = (height - margin - 8 * mm) - dh
    c.drawImage(img, x, y, dw, dh, preserveAspectRatio=True, anchor="n")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def _notice_page(message: str) -> BytesIO:
    """Page texte simple (ex: 'annexe introuvable')."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 18 * mm
    c.setFont("Helvetica", 11)
    c.drawString(margin, height - margin, message[:120])
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def build_voucher_pdf(context) -> bytes:
    """Assemble la piece comptable + ses annexes en un seul PDF (bytes)."""
    writer = PdfWriter()

    for page in PdfReader(_build_cover(context)).pages:
        writer.add_page(page)

    for d in context["documents"]:
        if not d.file:
            continue
        try:
            path = Path(d.file.path)
        except (NotImplementedError, ValueError):
            continue  # storage non-local : pas de chemin disque
        title = d.label or Path(d.file.name).name
        ext = path.suffix.lower()
        try:
            if ext == ".pdf":
                if path.exists():
                    for page in PdfReader(str(path)).pages:
                        writer.add_page(page)
                else:
                    for page in PdfReader(_notice_page(f"Annexe PDF introuvable : {title}")).pages:
                        writer.add_page(page)
            elif ext in IMAGE_EXTS and path.exists():
                for page in PdfReader(_image_to_pdf_page(path, title)).pages:
                    writer.add_page(page)
            # autres formats : deja signales sur la page recapitulative
        except Exception as exc:  # noqa: BLE001 - annexe corrompue : on continue
            for page in PdfReader(_notice_page(f"Annexe illisible ({title}) : {exc}")).pages:
                writer.add_page(page)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()
