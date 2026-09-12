from providers import soundcloud, spotify, youtube

PROVIDERS = {module.NAME: module for module in (youtube, spotify, soundcloud)}
TAGS = {module.NAME: module.TAG for module in PROVIDERS.values()}
DOWNLOAD_ORDER = (youtube.NAME, soundcloud.NAME)


def get(name):
    return PROVIDERS[name]


def detect(url):
    for provider in PROVIDERS.values():
        if provider.matches(url or ""):
            return provider.NAME

    return None


def fallbacks_for(source):
    return [name for name in DOWNLOAD_ORDER if name != source]
