import pathlib
import cv2


class StaticResourceIO:
    """
    StaticResourceIO は、staticディレクトリ配下の静的リソースの入出力を管理するクラスです。
    画像の保存と読み込みを行います。
    """

    def __init__(self, root_dir_path: pathlib.Path):
        if not root_dir_path:
            raise ValueError("root_dir_path must be specified.")
        if not isinstance(root_dir_path, pathlib.Path):
            raise TypeError("root_dir_path must be a pathlib.Path object.")
        if not root_dir_path.exists():
            raise FileNotFoundError(f"Directory {root_dir_path} does not exist.")
        if not root_dir_path.is_dir():
            raise NotADirectoryError(f"{root_dir_path} is not a directory.")

        # Bypass the static check.
        static_root = pathlib.Path.cwd() / "static"
        if not root_dir_path.resolve().is_relative_to(static_root):
            raise ValueError(f"root_dir_path must be a subdirectory of {static_root}.")

        self.root_dir_path = root_dir_path

    def save_image(
        self, filename: str | pathlib.Path, image: cv2.typing.MatLike
    ) -> None:
        """
        画像を指定されたパスに保存します。
        ディレクトリが存在しない場合は作成します。

        :param filename: 保存先のファイル名 （例: "image.png"）
        :param image: 保存する画像データ
        :raises ValueError: filename が空の場合
        """

        file_path = pathlib.Path(self.root_dir_path) / filename
        if not filename:
            raise ValueError("filename must be specified.")
        if not isinstance(filename, (str, pathlib.Path)):
            raise TypeError("filename must be a string or pathlib.Path object.")
        if not file_path.parent.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(file_path), image)

    def load_image(
        self, filename: pathlib.Path | str, grayscale: bool = False
    ) -> cv2.typing.MatLike:
        """
        指定されたパスから画像を読み込みます。
        画像が存在しない場合は例外をスローします。

        :param filename: 読み込む画像のファイル名 （例: "image.png"）
        :raises FileNotFoundError: 画像ファイルが見つからない場合
        :raises ValueError: filename が空の場合
        """

        # 画像ファイルのパスを生成
        if not filename:
            raise ValueError("filename must be specified.")
        if not isinstance(filename, (str, pathlib.Path)):
            raise TypeError("filename must be a string or pathlib.Path object.")
        file_path = pathlib.Path(self.root_dir_path) / filename

        # 画像ファイルの存在を確認
        if not file_path.exists():
            raise FileNotFoundError(f"Image file {file_path} not found.")

        # 画像がグレースケールかどうかを判定
        img_flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR

        # 画像を読み込む
        image = cv2.imread(str(file_path), img_flag)
        if image is None:
            raise FileNotFoundError(f"Image file {filename} not found.")
        return image
