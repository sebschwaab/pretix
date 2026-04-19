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

        # ── 3. Patch QuestionAnswer.to_string to display SIG answers nicely ─
        _orig_to_string = QuestionAnswer.to_string

        def _patched_to_string(self_ans, use_cached=True):
            if self_ans.question.type == Question.TYPE_SIGNATURE:
                return str(_('(signature on file)'))
            return _orig_to_string(self_ans, use_cached=use_cached)

        QuestionAnswer.to_string = _patched_to_string
        QuestionAnswer.to_string_i18n = property(
            lambda self_ans: _patched_to_string(self_ans, use_cached=False)
        )
