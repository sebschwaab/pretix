import logging
import os
from io import BytesIO

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

# A4 in PDF points (1 pt = 1/72 inch)
_A4_W = 595
_A4_H = 842
_MARGIN = 40

_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tif', '.tiff', '.jfif'}


def _image_to_pdf_bytes(file_field):
    """
    Open an image from a FieldFile, fit it to an A4 page with margins,
    and return PDF bytes (single page).
    """
    from PIL import Image

    with file_field.open('rb') as f:
        img = Image.open(f)
        img.load()

    # Flatten transparency onto white background
    if img.mode in ('RGBA', 'LA'):
        bg = Image.new('RGB', img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    elif img.mode == 'P':
        img = img.convert('RGBA')
        bg = Image.new('RGB', img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    max_w = _A4_W - 2 * _MARGIN
    max_h = _A4_H - 2 * _MARGIN
    img_w, img_h = img.size
    scale = min(max_w / img_w, max_h / img_h, 1.0)
    if scale < 1.0:
        img = img.resize(
            (int(img_w * scale), int(img_h * scale)),
            Image.LANCZOS,
        )

    buf = BytesIO()
    img.save(buf, format='PDF', resolution=72)
    buf.seek(0)
    return buf


def _append_attachments(ticket_buf, op):
    """
    Given a BytesIO containing the ticket PDF and an OrderPosition, return a
    new BytesIO with every FILE-type question attachment appended as extra
    pages.  Images are converted to single-page PDFs; PDFs are merged
    page-by-page.  SIG questions and non-image/non-PDF files are skipped.
    Returns the original ticket_buf unchanged when there is nothing to append.
    """
    import pypdf
    from pretix.base.models import Question

    try:
        answers = list(
            op.answers
            .select_related('question')
            .filter(question__type=Question.TYPE_FILE)
            .order_by('question__position', 'pk')
        )
    except Exception:
        logger.exception('file-concatenator: could not query answers for op %s', op.pk)
        return ticket_buf

    appendable = [a for a in answers if a.file]
    if not appendable:
        return ticket_buf

    ticket_buf.seek(0)
    merger = pypdf.PdfWriter()
    merger.append(ticket_buf)

    appended = False
    for answer in appendable:
        ext = os.path.splitext(answer.file.name.lower())[1]
        try:
            if ext == '.pdf':
                with answer.file.open('rb') as f:
                    merger.append(BytesIO(f.read()))
                appended = True
            elif ext in _IMAGE_EXTENSIONS:
                pdf_buf = _image_to_pdf_bytes(answer.file)
                merger.append(pdf_buf)
                appended = True
            # Other file types (Word, Excel, …) are intentionally ignored.
        except Exception:
            logger.exception(
                'file-concatenator: failed to append answer %s (file: %s)',
                answer.pk,
                getattr(answer.file, 'name', '?'),
            )

    if not appended:
        merger.close()
        ticket_buf.seek(0)
        return ticket_buf

    out = BytesIO()
    merger.write(out)
    merger.close()
    out.seek(0)
    return out


class FileConcatenatorApp(AppConfig):
    name = 'pretix_file_concatenator'
    verbose_name = _('File Concatenator')

    class PretixPluginMeta:
        name = _('File Concatenator')
        author = 'Plombier Services'
        category = 'FEATURE'
        version = '1.0.0'
        description = _(
            'Appends FILE-type question attachments (PDF, JPG, PNG) as extra '
            'pages at the end of every generated ticket PDF.'
        )

    def ready(self):
        from pretix.plugins.ticketoutputpdf.ticketoutput import PdfTicketOutput

        _orig_draw_page = PdfTicketOutput._draw_page

        def _patched_draw_page(self_output, layout, op, order):
            ticket_buf = _orig_draw_page(self_output, layout, op, order)
            try:
                return _append_attachments(ticket_buf, op)
            except Exception:
                logger.exception('file-concatenator: unexpected error for op %s', op.pk)
                ticket_buf.seek(0)
                return ticket_buf

        PdfTicketOutput._draw_page = _patched_draw_page
