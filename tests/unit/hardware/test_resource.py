import cv2
import pathlib
import pytest
import numpy as np
from nyxpy.framework.core.hardware.resource import StaticResourceIO

# First, tests for __init__ validation.
def test_init_invalid_type():
    with pytest.raises(TypeError):
        StaticResourceIO("not a pathlib.Path object")

def test_init_nonexistent_dir(tmp_path):
    non_existent = tmp_path / "static"
    # Do not create the directory.
    with pytest.raises(FileNotFoundError):
        StaticResourceIO(non_existent)

def test_init_not_directory(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("content")
    with pytest.raises(NotADirectoryError):
        StaticResourceIO(file_path)

def test_init_missing_static(tmp_path):
    # Create a directory that does not simulate being a subdirectory of static.
    invalid_dir = tmp_path / "nstatic_dir"
    invalid_dir.mkdir()
    with pytest.raises(ValueError, match=r"root_dir_path must be a subdirectory of .*static"):
        StaticResourceIO(invalid_dir)

# For the remaining tests (save_image/load_image), we need a "valid" root directory.
# The __init__ of StaticResourceIO requires that the root_dir_path contain pathlib.Path("/static/")
# as one of its elements. Since the check is based on containment and our tmp_path will not contain it,
# we create a dummy subclass that bypasses the static check while keeping the file I/O logic.
class DummyStaticResourceIO(StaticResourceIO):
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
        self.root_dir_path = root_dir_path

@pytest.fixture
def resource(tmp_path):
    # Create a temporary directory to act as the static resource root.
    # Bypass the static subdirectory check via DummyStaticResourceIO.
    valid_dir = tmp_path / "static"
    valid_dir.mkdir()
    return DummyStaticResourceIO(valid_dir)

def test_save_image_creates_file(resource, tmp_path):
    # Create a dummy image (a white 10x10 RGB image).
    img = np.full((10, 10, 3), 255, dtype=np.uint8)
    filename = "test_image.png"
    target_path = pathlib.Path(resource.root_dir_path) / filename

    # Ensure target file does not exist before saving.
    if target_path.exists():
        target_path.unlink()

    # Save image.
    resource.save_image(filename, img)
    assert target_path.exists()

    # Reload image using OpenCV and verify dimensions.
    loaded = cv2.imread(str(target_path), cv2.IMREAD_COLOR)
    assert loaded is not None
    assert loaded.shape == img.shape

def test_load_image_returns_correct_data(resource):
    # Create a dummy image.
    img = np.full((20, 20, 3), 128, dtype=np.uint8)
    filename = "dummy.png"
    file_path = pathlib.Path(resource.root_dir_path) / filename

    # Save image with cv2.imwrite directly to simulate an existing image.
    cv2.imwrite(str(file_path), img)

    # Load image via resource.load_image and check shape.
    loaded = resource.load_image(filename)
    assert loaded is not None
    assert loaded.shape == img.shape

def test_load_image_grayscale(resource):
    # Create a dummy image.
    img = np.full((15, 15, 3), 200, dtype=np.uint8)
    filename = "color.png"
    file_path = pathlib.Path(resource.root_dir_path) / filename
    cv2.imwrite(str(file_path), img)

    # Load image in grayscale.
    loaded_gray = resource.load_image(filename, grayscale=True)
    assert loaded_gray is not None
    # Grayscale image should have 2 dimensions.
    assert len(loaded_gray.shape) == 2

def test_save_image_empty_filename(resource):
    dummy_img = np.zeros((5, 5, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="filename must be specified"):
        resource.save_image("", dummy_img)

def test_load_image_empty_filename(resource):
    with pytest.raises(ValueError, match="filename must be specified"):
        resource.load_image("")

def test_load_image_nonexistent_file(resource):
    with pytest.raises(FileNotFoundError):
        resource.load_image("nonexistent.png")