import logging
from io import BytesIO

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

_pdf_logger = logging.getLogger(__name__)


class SignatureFieldApp(AppConfig):
    name = 'pretix_signature_field'
    verbose_name = _("Signature Field")

    class PretixPluginMeta:
        name = _("Signature Field")
        author = "Plombier Services"
        category = 'FEATURE'
        version = '1.0.0'
        description = _(
            "Adds a handwritten signature question type to the checkout process. "
            "Buyers can sign directly in their browser using a touch or mouse gesture."
        )

    def ready(self):
        from . import signals  # noqa – registers all @receiver decorators
        from django.utils.html import escape as _escape
        from django.utils.safestring import mark_safe as _mark_safe
        from django.utils.translation import gettext_lazy as _
        from pretix.base.forms.questions import BaseQuestionsForm
        from pretix.base.models import Question
        from pretix.base.models.orders import QuestionAnswer
        from pretix.base.pdf import Renderer
        from PIL import Image as _PILImage
        from reportlab.lib.units import mm as _mm
        from reportlab.lib.utils import ImageReader as _RLImageReader

        # ── 1. Register the new question type ────────────────────────────────
        Question.TYPE_SIGNATURE = 'SIG'
        new_choice = (Question.TYPE_SIGNATURE, _('Handwritten signature'))

        already_registered = any(
            t[0] == Question.TYPE_SIGNATURE for t in Question.TYPE_CHOICES
        )
        if not already_registered:
            Question.TYPE_CHOICES = Question.TYPE_CHOICES + (new_choice,)

        try:
            Question._meta.get_field('type').choices = Question.TYPE_CHOICES
        except Exception:
            pass

        # ── 2. Patch BaseQuestionsForm.__init__ ───────────────────────────────
        _orig_init = BaseQuestionsForm.__init__

        def _patched_init(self_form, *args, **kwargs):
            cartpos = kwargs.get('cartpos')
            orderpos = kwargs.get('orderpos')
            pos = cartpos or orderpos

            sig_questions = []
            original_questions = None

            if pos and hasattr(pos.item, 'questions_to_ask'):
                original_questions = list(pos.item.questions_to_ask)
                sig_questions = [
                    q for q in original_questions
                    if q.type == Question.TYPE_SIGNATURE
                ]
                if sig_questions:
                    pos.item.questions_to_ask = [
                        q for q in original_questions
                        if q.type != Question.TYPE_SIGNATURE
                    ]

            try:
                _orig_init(self_form, *args, **kwargs)
            finally:
                if original_questions is not None and pos:
                    pos.item.questions_to_ask = original_questions

            if not sig_questions or pos is None:
                return

            import json
            from pretix.helpers.escapejson import escapejson_attr
            from pretix_signature_field.forms import SignatureField

            for q in sig_questions:
                answers = [a for a in pos.answerlist if a.question_id == q.id]
                # Use the stored file as initial (like TYPE_FILE) so that
                # FileField.clean(None, initial=FieldFile) preserves it on
                # re-submit without re-signing.
                existing = answers[0] if answers else None
                initial = existing.file if existing and existing.file else None

                field = SignatureField(
                    label=str(q.question),
                    required=q.required and not self_form.all_optional,
                    help_text=str(q.help_text) if q.help_text else '',
                    initial=initial,
                )
                field.question = q
                if existing:
                    field.answer = existing

                if q.dependency_question_id:
                    field.widget.attrs['data-question-dependency'] = q.dependency_question_id
                    field.widget.attrs['data-question-dependency-values'] = escapejson_attr(
                        json.dumps(q.dependency_values)
                    )
                    field._required = q.required and not self_form.all_optional
                    field.required = False

                self_form.fields['question_%s' % q.id] = field

        BaseQuestionsForm.__init__ = _patched_init

        # ── 3. Patch QuestionAnswer.to_string for back-office display ─────────
        # The admin order-detail template uses {{ q.answer.to_string_i18n|linebreaksbr }}
        # for non-FILE types.  We return an <img> pointing to the stored file
        # (or backward-compat data URL for old answers that pre-date file storage).
        _orig_to_string = QuestionAnswer.to_string

        def _patched_to_string(self_ans, use_cached=True):
            if self_ans.question.type == Question.TYPE_SIGNATURE:
                if self_ans.file:
                    url = self_ans.backend_file_url or ''
                    if not url:
                        try:
                            url = self_ans.file.url
                        except Exception:
                            pass
                    if url:
                        return _mark_safe(
                            '<img src="{url}" style="max-width:300px; max-height:150px;">'.format(
                                url=_escape(url),
                            )
                        )
                # Backward compat: old answers stored base64 in .answer
                if self_ans.answer and self_ans.answer.startswith('data:'):
                    return _mark_safe(
                        '<img src="{url}" style="max-width:300px; max-height:150px;">'.format(
                            url=_escape(self_ans.answer),
                        )
                    )
                return str(_('(no signature)'))
            return _orig_to_string(self_ans, use_cached=use_cached)

        def _patched_to_string_i18n(self_ans):
            return _patched_to_string(self_ans, use_cached=False)

        QuestionAnswer.to_string = _patched_to_string
        QuestionAnswer.to_string_i18n = _patched_to_string_i18n

        # ── 4. Patch Renderer._draw_imagearea (backward compat for old data: answers)
        # New answers have answer.file set; the core ThumbnailingImageReader handles
        # FieldFile natively.  This patch only activates for the old base64 format
        # (where the signal returns a BytesIO) so existing tickets keep working.
        _orig_draw_imagearea = Renderer._draw_imagearea

        def _patched_draw_imagearea(self_renderer, canvas, op, order, o):
            content = o.get('content', '')
            if content and content in self_renderer.images:
                ev = self_renderer._get_ev(op, order)
                try:
                    image_data = self_renderer.images[content]['evaluate'](op, order, ev)
                except Exception:
                    image_data = None

                if isinstance(image_data, BytesIO):
                    try:
                        image_data.seek(0)
                        pil_img = _PILImage.open(image_data)
                        pil_img.load()

                        area_w = float(o['width']) * _mm
                        area_h = float(o['height']) * _mm
                        img_w, img_h = pil_img.size

                        scale = min(area_w / img_w, area_h / img_h)
                        draw_w = img_w * scale
                        draw_h = img_h * scale
                        draw_x = float(o['left']) * _mm + (area_w - draw_w) / 2
                        draw_y = float(o['bottom']) * _mm + (area_h - draw_h) / 2

                        image_data.seek(0)
                        canvas.drawImage(
                            image=_RLImageReader(image_data),
                            x=draw_x,
                            y=draw_y,
                            width=draw_w,
                            height=draw_h,
                            mask='auto',
                        )
                        return
                    except Exception:
                        _pdf_logger.exception("Cannot draw SIG image in PDF")

            _orig_draw_imagearea(self_renderer, canvas, op, order, o)

        Renderer._draw_imagearea = _patched_draw_imagearea

        # ── 5. Patch Renderer.draw_page: redirect SIG text elements to image rendering
        # If the PDF designer placed a SIG question in a textarea/textcontainer,
        # ReportLab's Paragraph cannot render images.  Silently redirect those
        # elements to _draw_imagearea before drawing each page.
        _orig_draw_page = Renderer.draw_page

        def _patched_draw_page(self_renderer, canvas, order, op, show_page=True, only_page=None):
            sig_keys = set()
            for q in self_renderer.event.questions.all():
                if q.type == Question.TYPE_SIGNATURE:
                    sig_keys.add('question_{}'.format(q.identifier))
                    sig_keys.add('question_{}'.format(q.pk))

            if not sig_keys:
                return _orig_draw_page(self_renderer, canvas, order, op,
                                       show_page=show_page, only_page=only_page)

            patched_layout = []
            for o in self_renderer.layout:
                if o.get('type') in ('textarea', 'textcontainer') and o.get('content', '') in sig_keys:
                    o = dict(o, type='imagearea')
                patched_layout.append(o)

            orig_layout = self_renderer.layout
            self_renderer.layout = patched_layout
            try:
                _orig_draw_page(self_renderer, canvas, order, op,
                                show_page=show_page, only_page=only_page)
            finally:
                self_renderer.layout = orig_layout

        Renderer.draw_page = _patched_draw_page
