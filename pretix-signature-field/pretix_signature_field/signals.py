import base64
import hashlib
from functools import partial
from io import BytesIO

from django.dispatch import receiver
from django.template.loader import get_template
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from pretix.base.signals import layout_image_variables, layout_text_variables
from pretix.control.signals import html_head as control_html_head
from pretix.presale.signals import html_head as presale_html_head


@receiver(layout_image_variables, dispatch_uid="pretix_signature_field_layout_image_variables")
def images_from_sig_questions(sender, *args, **kwargs):
    from pretix.base.models import Question

    def get_sig_image(op, order, event, question_id, etag):
        a = None
        if op.addon_to:
            if 'answers' in getattr(op.addon_to, '_prefetched_objects_cache', {}):
                try:
                    a = [ans for ans in op.addon_to.answers.all() if ans.question_id == question_id][0]
                except IndexError:
                    pass
            else:
                a = op.addon_to.answers.filter(question_id=question_id).first()

        if 'answers' in getattr(op, '_prefetched_objects_cache', {}):
            try:
                a = [ans for ans in op.answers.all() if ans.question_id == question_id][0]
            except IndexError:
                pass
        else:
            a = op.answers.filter(question_id=question_id).first() or a

        if not a:
            return None

        # New format: PNG saved as a real file in answer.file (like TYPE_FILE).
        if a.file:
            if etag:
                return hashlib.sha1(a.file.name.encode()).hexdigest()
            return a.file

        # Backward compat: old answers that stored base64 in answer.answer.
        if a.answer and a.answer.startswith('data:'):
            if etag:
                return hashlib.sha1(a.answer.encode()).hexdigest()
            try:
                _header, b64data = a.answer.split(',', 1)
                return BytesIO(base64.b64decode(b64data))
            except Exception:
                pass

        return None

    d = {}
    for q in sender.questions.all():
        if q.type != Question.TYPE_SIGNATURE:
            continue
        d['question_{}'.format(q.identifier)] = {
            'label': _('Question: {question}').format(question=q.question),
            'evaluate': partial(get_sig_image, question_id=q.pk, etag=False),
            'etag': partial(get_sig_image, question_id=q.pk, etag=True),
        }
    return d


@receiver(layout_text_variables, dispatch_uid="pretix_signature_field_layout_text_variables")
def text_vars_from_sig_questions(sender, *args, **kwargs):
    """
    Override the text-variable entries for SIG questions so that the PDF text
    path (variables_from_questions → Paragraph → ReportLab paraparser) never
    receives an HTML <img> tag.  Returns plain text; the actual image is drawn
    by _patched_draw_imagearea via layout_image_variables.

    This receiver is registered in ready(), which runs after the core
    variables_from_questions receiver, so our dict entries win via dict.update().
    """
    from pretix.base.models import Question

    def get_sig_text(op, order, event, question_id):
        a = None
        if op.addon_to:
            if 'answers' in getattr(op.addon_to, '_prefetched_objects_cache', {}):
                try:
                    a = [ans for ans in op.addon_to.answers.all() if ans.question_id == question_id][0]
                except IndexError:
                    pass
            else:
                a = op.addon_to.answers.filter(question_id=question_id).first()

        if 'answers' in getattr(op, '_prefetched_objects_cache', {}):
            try:
                a = [ans for ans in op.answers.all() if ans.question_id == question_id][0]
            except IndexError:
                pass
        else:
            a = op.answers.filter(question_id=question_id).first() or a

        if not a:
            return ''
        return str(_('(signature enregistrée)')) if a.answer else str(_('(no signature)'))

    d = {}
    for q in sender.questions.all():
        if q.type != Question.TYPE_SIGNATURE:
            continue
        entry = {
            'label': _('Question: {question}').format(question=q.question),
            'editor_sample': _('<Answer: {question}>').format(question=q.question),
            'evaluate': partial(get_sig_text, question_id=q.pk),
        }
        d['question_{}'.format(q.identifier)] = dict(entry, migrate_from='question_{}'.format(q.pk))
        d['question_{}'.format(q.pk)] = dict(entry, hidden=True)
    return d


@receiver(presale_html_head, dispatch_uid="pretix_signature_field_presale_head")
def html_head_presale(sender, request=None, **kwargs):
    """
    Inject the signature pad CSS and JS into the <head> of every presale page
    for events where this plugin is active.

    Using the html_head signal (rather than class Media on the widget) is
    required because Pretix runs django-compressor in offline mode: only files
    referenced inside {% compress %} blocks that are processed at build time are
    served correctly.  Django's class Media mechanism bypasses that pipeline and
    the files are never found.
    """
    template = get_template('pretix_signature_field/presale_head.html')
    return template.render({'request': request})


@receiver(control_html_head, dispatch_uid="pretix_signature_field_control_head")
def html_head_control(sender, request=None, **kwargs):
    """
    Inject a small stylesheet into the control (back-office) <head> so that
    signature answer images displayed in the order detail page are rendered at
    a readable size.
    """
    return mark_safe(
        '<style>'
        '.answers dd img {'
        '  display: block;'
        '  max-width: 300px;'
        '  max-height: 120px;'
        '  border: 1px solid #ddd;'
        '  border-radius: 3px;'
        '  background: #fff;'
        '}'
        '</style>'
    )
