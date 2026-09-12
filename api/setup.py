import os

import spotify_converter


class SetupApi:
    def spotify_ready(self):
        path = spotify_converter.get_credentials_path()
        return {"ready": os.path.isfile(path), "path": path}
