from django.dispatch import receiver
from django.templatetags.static import static
from pretix.presale.signals import html_head


@receiver(html_head, dispatch_uid='pretix_modern_theme_html_head')
def inject_modern_css(sender, request=None, **kwargs):
    url = static('pretix_modern_theme/modern.css')
    return '<link rel="stylesheet" href="{url}">'.format(url=url)
