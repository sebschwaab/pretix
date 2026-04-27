import logging
import os

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class ModernThemeApp(AppConfig):
    name = 'pretix_modern_theme'
    verbose_name = _('Modern Theme')

    class PretixPluginMeta:
        name = _('Modern Theme')
        author = 'Plombier Services'
        category = 'CUSTOMIZATION'
        version = '2.0.0'
        description = _(
            'Modern SaaS-style theme for the Pretix presale interface with '
            'dark mode, animated cards, responsive grid and full template override.'
        )

    def ready(self):
        self._inject_template_dir()
        self._inject_static_dir()

    def _inject_template_dir(self):
        """
        Insert our templates/ directory at the front of the Django filesystem
        loader search paths so our templates take priority over pretix.presale
        regardless of INSTALLED_APPS order (plugins are appended after core apps).

        The filesystem loader calls engine.dirs on every render — modifying the
        list after engine initialisation is safe and effective.
        """
        try:
            from django.template import engines as django_engines

            templates_dir = os.path.join(os.path.dirname(__file__), 'templates')

            for engine in django_engines.all():
                inner = getattr(engine, 'engine', None)
                if inner is None:
                    continue
                dirs = getattr(inner, 'dirs', None)
                if dirs is None:
                    continue
                if templates_dir not in dirs:
                    dirs.insert(0, templates_dir)
                    logger.debug('pretix-modern-theme: injected template dir %s', templates_dir)
        except Exception:
            logger.exception('pretix-modern-theme: failed to inject template directory')

    def _inject_static_dir(self):
        """
        Insert our static/ directory at the front of STATICFILES_DIRS so that
        FileSystemFinder (which runs before AppDirectoriesFinder) serves our
        overridden static assets with priority over any other plugin — including
        pretix.plugins.stripe whose pretix-stripe.js we customise.
        """
        try:
            from django.conf import settings

            static_dir = os.path.join(os.path.dirname(__file__), 'static')
            dirs = list(getattr(settings, 'STATICFILES_DIRS', []))
            if static_dir not in dirs:
                dirs.insert(0, static_dir)
                settings.STATICFILES_DIRS = dirs
                logger.debug('pretix-modern-theme: injected static dir %s', static_dir)
        except Exception:
            logger.exception('pretix-modern-theme: failed to inject static directory')
