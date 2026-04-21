from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ModernThemeApp(AppConfig):
    name = 'pretix_modern_theme'
    verbose_name = _('Modern Theme')

    class PretixPluginMeta:
        name = _('Modern Theme')
        author = 'Plombier Services'
        category = 'CUSTOMIZATION'
        version = '1.0.0'
        description = _(
            'Replaces the default Pretix presale interface with a modern, '
            'responsive design using cards, smooth animations, and clean typography.'
        )

    def ready(self):
        from . import signals  # noqa: F401
