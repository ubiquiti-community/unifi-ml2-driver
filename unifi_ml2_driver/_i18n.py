import oslo_i18n

DOMAIN = "unifi_ml2_driver"

_translators = oslo_i18n.TranslatorFactory(domain=DOMAIN)

# The primary translation function using the well-known name "_"
_ = _translators.primary
