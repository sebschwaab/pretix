import base64
import re
from io import BytesIO

from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

_SIGNATURE_DATA_URL_RE = re.compile(
    r'^data:image/(png|jpeg|jpg);base64,[A-Za-z0-9+/=]+$'
)
MAX_SIGNATURE_BYTES = 10 * 1024 * 1024  # 10 MB decoded


class SignatureWidget(forms.Widget):
    """
    Renders an HTML5 canvas signature pad.

    On submit, the canvas content is serialised to a PNG data-URL and placed
    in a hidden <input>.  value_from_datadict decodes that data-URL to an
    InMemoryUploadedFile so that SignatureField (a FileField subclass) is
    handled by Pretix's native _save_to_answer path, which stores the file in
    QuestionAnswer.file exactly like TYPE_FILE questions.

    If value is an existing FieldFile (edit form), its URL is passed via
    data-signature-preview so the JS can pre-draw it in the canvas.
    """

    def value_from_datadict(self, data, files, name):
        raw = (data.get(name) or '').strip()
        if not raw or not raw.startswith('data:'):
            return None

        if not _SIGNATURE_DATA_URL_RE.match(raw):
            # Keep the raw string so to_python can raise a clean ValidationError.
            return raw

        try:
            _header, b64data = raw.split(',', 1)
            png_bytes = base64.b64decode(b64data)
            if len(png_bytes) > MAX_SIGNATURE_BYTES:
                return raw  # to_python will reject it with a readable error
            bio = BytesIO(png_bytes)
            return InMemoryUploadedFile(
                bio,
                field_name=name,
                name='signature.png',
                content_type='image/png',
                size=len(png_bytes),
                charset=None,
            )
        except Exception:
            return raw  # to_python will raise ValidationError

    def render(self, name, value, attrs=None, renderer=None):
        final_attrs = self.build_attrs(attrs or {})
        element_id = final_attrs.get('id', 'id_' + name)

        # If value is an existing FieldFile, expose its URL so the JS can
        # pre-draw the stored signature into the canvas.
        preview_url = ''
        if hasattr(value, 'url'):
            try:
                preview_url = value.url
            except Exception:
                pass

        hidden_html = forms.HiddenInput().render(name, None, {'id': element_id})

        wrapper = (
            '<div class="signature-pad-wrapper"'
            '     data-signature-input="{input_id}"'
            '     data-signature-preview="{preview_url}">'
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
            preview_url=escape(preview_url),
            clear_label=escape(str(_('Clear signature'))),
            hint_label=escape(str(_('Draw your signature in the box above'))),
            hidden=hidden_html,
        )
        return mark_safe(wrapper)


class SignatureField(forms.FileField):
    """
    Accepts a PNG data-URL from SignatureWidget, converts it to an
    InMemoryUploadedFile, and stores it via QuestionAnswer.file — identical
    to how Pretix handles TYPE_FILE questions.

    When re-editing an order, clean(data=None, initial=FieldFile) returns the
    existing FieldFile unchanged (standard FileField behaviour), so the user
    only needs to re-sign if they want to update the signature.
    """

    widget = SignatureWidget

    def to_python(self, data):
        if data is None:
            return None
        if hasattr(data, 'read'):
            # Already decoded by value_from_datadict — pass through.
            return data
        if isinstance(data, str):
            # Widget returned the raw string because decoding failed.
            if len(data) > MAX_SIGNATURE_BYTES * 1.4:
                raise ValidationError(
                    _('The signature image is too large. Please clear and re-sign.')
                )
            raise ValidationError(
                _('Invalid signature format. Please draw your signature in the box.')
            )
        return super().to_python(data)
