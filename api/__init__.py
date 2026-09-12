from api.chain import ChainApi
from api.downloader import DownloaderApi
from api.history_api import HistoryApi
from api.playlist_builder import PlaylistBuilderApi
from api.setup import SetupApi
from api.synchronizer import SynchronizerApi


class UmupyApi(DownloaderApi, SynchronizerApi, PlaylistBuilderApi, ChainApi, HistoryApi, SetupApi):
    def __init__(self):
        DownloaderApi.__init__(self)
        SynchronizerApi.__init__(self)
        PlaylistBuilderApi.__init__(self)
        ChainApi.__init__(self)
