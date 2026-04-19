import re

from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

# Maximum size for a base64-encoded PNG (10 MB uncompressed → ≈14 MB base64)
MAX_SIGNATURE_SIZE = 14 * 1024 * 1024  # characters

# Accepted MIME types
_SIGNATURE_DATA_URL_RE = re.compile(
    r'^data:image/(png|jpeg|jpg);base64,[A-Za-z0-9+/=]+$'
)


class SignatureWidget(forms.HiddenInput):
    """
    Renders a hidden <input> alongside an HTML5 <canvas> signature pad.
    When the user draws, the canvas content is serialised to a PNG data-URL
    and stored in the hidden input.

    CSS and JS are injected via the html_head signal (signals.py) so that they
    go through Pretix's django-compressor offline pipeline.  Do NOT declare a
    class Media here: Pretix does not honour widget Media in its compressed
    templates, and the files would never be served.
    """

    def render(self, name, value, attrs=None, renderer=None):
        final_attrs = self.build_attrs(attrs or {})
        element_id = final_attrs.get('id', 'id_' + name)

        # Render the standard hidden input
        hidden_html = super().render(name, value, attrs, renderer)

        # Build the canvas container; all dynamic values are escaped.
        # No inline styles — all visual rules live in signature.css.
        wrapper = (
            '<div class="signature-pad-wrapper"'
            '     data-signature-input="{input_id}">'
            '  <div class="signature-pad-canvas-area">'
            '    <canvas class="signature-pad-canvas"></canvas>'
            '  </div>'
            '  <div class="signature-pad-toolbar">'
            '    <button type="button"'
            '            class="btn btn-sm btn-default signature-pad-clear">'
            '      {clear_label}'
            '    </button>'
            '    <span class="text-muted signature-pad-hint">'
            '      {hint_label}'
            '    </span>'
            '  </div>'
            '  {hidden}'
            '</div>'
        ).format(
            input_id=escape(element_id),
            clear_label=escape(str(_('Clear signature'))),
            hint_label=escape(str(_('Draw your signature in the box above'))),
            hidden=hidden_html,  # already marked safe by Django
        )
        return mark_safe(wrapper)


class SignatureField(forms.CharField):
    """
    A form field that accepts a base64-encoded PNG data URL produced by the
    :class:`SignatureWidget`.

    The value is stored as-is in ``QuestionAnswer.answer``.
    """

    widget = SignatureWidget

    def __init__(self, *args, **kwargs):
        # Signatures can be large; do not impose a max_length here.
        kwargs.setdefault('max_length', None)
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        value = super().to_python(value)
        if not value:
            return value
        return value.strip()

    def validate(self, value):
        super().validate(value)
        if not value:
            return
        if len(value) > MAX_SIGNATURE_SIZE:
            raise ValidationError(
                _('The signature image is too large. Please clear and re-sign.')
            )
        if not _SIGNATURE_DATA_URL_RE.match(value):
            raise ValidationError(
                _('Invalid signature format. Please draw your signature in the box.')
            )
