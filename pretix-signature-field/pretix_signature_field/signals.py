from django.dispatch import receiver
from django.template.loader import get_template
from django.utils.safestring import mark_safe

from pretix.control.signals import html_head as control_html_head
from pretix.presale.signals import html_head as presale_html_head


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
        '.signature-answer-preview {'
        '  display: block;'
        '  max-width: 300px;'
        '  max-height: 120px;'
        '  border: 1px solid #ddd;'
        '  border-radius: 3px;'
        '  background: #fff;'
        '}'
        '</style>'
    )
