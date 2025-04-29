import tomlkit
from pathlib import Path


class GlobalSettings:
    """
    Manage global settings stored in .nyxpy/global.toml under the working directory.
    """

    def __init__(self):
        self.config_dir = Path.cwd() / ".nyxpy"
        self.config_dir.mkdir(exist_ok=True)
        self.config_path = self.config_dir / "global.toml"
        self.data = {}
        self.load()

    def load(self):
        if self.config_path.exists():
            text = self.config_path.read_text(encoding="utf-8")
            self.data = tomlkit.loads(text)
        else:
            # default global settings and persist initial config during init
            self.data = {
                "capture_device": "",
                "serial_device": "",
                "serial_baud": 9600,
                "serial_protocol": "CH552",  # デフォルトで CH552 プロトコルを使用
            }
            # create initial config file
            self.save()

    def save(self):
        toml_str = tomlkit.dumps(self.data)
        self.config_path.write_text(toml_str, encoding="utf-8")

    def get(self, key, default=None):
        # ドット区切りキーでネストdictにも対応
        if '.' in key:
            parts = key.split('.')
            d = self.data
            for p in parts[:-1]:
                d = d.get(p, {})
            return d.get(parts[-1], default)
        return self.data.get(key, default)

    def set(self, key, value):
        # ドット区切りキーでネストdictにも対応
        if '.' in key:
            parts = key.split('.')
            d = self.data
            for p in parts[:-1]:
                if p not in d or not isinstance(d[p], dict):
                    d[p] = {}
                d = d[p]
            d[parts[-1]] = value
        else:
            self.data[key] = value
        self.save()
