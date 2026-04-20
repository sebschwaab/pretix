from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


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
        from django.utils.translation import gettext_lazy as _
        from pretix.base.models import Question
        from pretix.base.models.orders import QuestionAnswer
        from pretix.base.forms.questions import BaseQuestionsForm

        # ── 1. Register the new question type on the Question model ──────────
        Question.TYPE_SIGNATURE = 'SIG'
        new_choice = (Question.TYPE_SIGNATURE, _('Handwritten signature'))

        already_registered = any(
            t[0] == Question.TYPE_SIGNATURE for t in Question.TYPE_CHOICES
        )
        if not already_registered:
            Question.TYPE_CHOICES = Question.TYPE_CHOICES + (new_choice,)

        # Also update the field-level choices so that admin forms and
        # model-level validation (full_clean) accept 'SIG'.
        try:
            Question._meta.get_field('type').choices = Question.TYPE_CHOICES
        except Exception:
            pass  # non-critical; admin fallback is the tuple on the class

        # ── 2. Monkey-patch BaseQuestionsForm to handle SIG questions ────────
        _orig_init = BaseQuestionsForm.__init__

        def _patched_init(self_form, *args, **kwargs):
            """
            Intercepts the form initialisation to:
            1. Temporarily remove SIG questions from the pre-fetched list so
               that the original __init__ (which has no SIG branch) does not
               crash with a NameError.
            2. Call the original __init__.
            3. Add a SignatureField for each SIG question.
            """
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
                    # Hide SIG questions from the original code path
                    pos.item.questions_to_ask = [
                        q for q in original_questions
                        if q.type != Question.TYPE_SIGNATURE
                    ]

            try:
                _orig_init(self_form, *args, **kwargs)
            finally:
                # Always restore the original list, even if __init__ raised
                if original_questions is not None and pos:
                    pos.item.questions_to_ask = original_questions

            # ── Add a SignatureField for each SIG question ───────────────────
            if not sig_questions or pos is None:
                return

            import json
            from pretix.helpers.escapejson import escapejson_attr
            from pretix_signature_field.forms import SignatureField

            for q in sig_questions:
                answers = [a for a in pos.answerlist if a.question_id == q.id]
                initial = answers[0].answer if answers else None

                field = SignatureField(
                    label=str(q.question),
                    required=q.required and not self_form.all_optional,
                    help_text=str(q.help_text) if q.help_text else '',
                    initial=initial,
                )
                field.question = q
                if answers:
                    field.answer = answers[0]

                if q.dependency_question_id:
                    field.widget.attrs['data-question-dependency'] = q.dependency_question_id
                    field.widget.attrs['data-question-dependency-values'] = escapejson_attr(
                        json.dumps(q.dependency_values)
                    )
                    field._required = q.required and not self_form.all_optional
                    field.required = False

                self_form.fields['question_%s' % q.id] = field

        BaseQuestionsForm.__init__ = _patched_init

        # ── 3. Patch QuestionAnswer.to_string to show the signature image ───
        #
        # The admin order detail template renders answers as:
        #   {{ q.answer.to_string_i18n|linebreaksbr }}
        #
        # Django's linebreaksbr filter calls conditional_escape(), which
        # respects SafeData: if the value is already mark_safe(), it is NOT
        # HTML-escaped.  Returning mark_safe('<img ...>') therefore lets the
        # image tag pass through unchanged and displays the signature inline.
        from django.utils.safestring import mark_safe as _mark_safe

        _orig_to_string = QuestionAnswer.to_string

        def _patched_to_string(self_ans, use_cached=True):
            if self_ans.question.type == Question.TYPE_SIGNATURE:
                if self_ans.answer:
                    return _mark_safe(
                        '<img src="{src}" style="max-width:300px; max-height:150px;">'.format(
                            src=self_ans.answer,
                        )
                    )
                return str(_('(no signature)'))
            return _orig_to_string(self_ans, use_cached=use_cached)

        def _patched_to_string_i18n(self_ans):
            return _patched_to_string(self_ans, use_cached=False)

        QuestionAnswer.to_string = _patched_to_string
        QuestionAnswer.to_string_i18n = _patched_to_string_i18n

        # ── 4. Patch Renderer._draw_imagearea to render SIG images in PDFs ──
        #
        # The default _draw_imagearea feeds the file object to ThumbnailingImageReader,
        # which is designed for Django FieldFile objects.  Our SIG answer is a
        # data:image/png;base64,... URL that signals.py decodes into a BytesIO.
        # We intercept that case and draw the image directly via PIL + ImageReader
        # so that it is reliably rendered in PDF tickets.
        import logging as _logging
        from io import BytesIO as _BytesIO

        from PIL import Image as _PILImage
        from pretix.base.pdf import Renderer
        from reportlab.lib.units import mm as _mm
        from reportlab.lib.utils import ImageReader as _RLImageReader

        _pdf_logger = _logging.getLogger(__name__)
        _orig_draw_imagearea = Renderer._draw_imagearea

        def _patched_draw_imagearea(self_renderer, canvas, op, order, o):
            content = o.get('content', '')
            if content and content in self_renderer.images:
                ev = self_renderer._get_ev(op, order)
                try:
                    image_data = self_renderer.images[content]['evaluate'](op, order, ev)
                except Exception:
                    image_data = None

                if isinstance(image_data, _BytesIO):
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
