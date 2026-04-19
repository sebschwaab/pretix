# Expose the AppConfig class here so that the entry_point value
# ``pretix_signature_field:SignatureFieldApp`` is importable and so that
# Django can discover the app when ``pretix_signature_field`` is added to
# INSTALLED_APPS (which pretix does automatically via the entry_point module).
from pretix_signature_field.apps import SignatureFieldApp  # noqa: F401

# Kept for Django < 3.2 compatibility
default_app_config = 'pretix_signature_field.apps.SignatureFieldApp'
