from django.dispatch import receiver
from django.template.loader import get_template

from pretix.presale.signals import html_head


@receiver(html_head, dispatch_uid="pretix_signature_field_html_head")
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
