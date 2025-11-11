import pytest
from unittest.mock import patch

from pydmconverter.__main__ import (
    copy_img_files,
    convert_files_in_folder,
    run,
)


class TestCopyImgFiles:
    """Tests for copy_img_files function."""

    def test_copy_img_files_basic(self, tmp_path):
        """Test basic image file copying with various formats."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        (input_dir / "test.png").write_bytes(b"PNG data")
        (input_dir / "photo.jpg").write_bytes(b"JPG data")
        (input_dir / "image.gif").write_bytes(b"GIF data")
        (input_dir / "document.txt").write_text("Not an image")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        copy_img_files(input_dir, output_dir)

        assert (output_dir / "test.png").exists()
        assert (output_dir / "photo.jpg").exists()
        assert (output_dir / "image.gif").exists()
        assert not (output_dir / "document.txt").exists()

        assert (output_dir / "test.png").read_bytes() == b"PNG data"

    def test_copy_img_files_empty_directory(self, tmp_path):
        """Test copying from directory with no images."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        (input_dir / "document.txt").write_text("Text file")
        (input_dir / "data.json").write_text('{"key": "value"}')

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        copy_img_files(input_dir, output_dir)

        assert len(list(output_dir.iterdir())) == 0

    def test_copy_img_files_creates_subdirectories(self, tmp_path):
        """Test that nested directory structure is preserved."""
        input_dir = tmp_path / "input"
        subdir = input_dir / "images" / "icons"
        subdir.mkdir(parents=True)

        (subdir / "icon.png").write_bytes(b"PNG icon data")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        copy_img_files(input_dir, output_dir)

        assert (output_dir / "images" / "icons" / "icon.png").exists()
        assert (output_dir / "images" / "icons" / "icon.png").read_bytes() == b"PNG icon data"

    def test_copy_img_files_case_insensitive(self, tmp_path):
        """Test that file extension matching is case-insensitive."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        (input_dir / "image.PNG").write_bytes(b"PNG data")
        (input_dir / "photo.JPG").write_bytes(b"JPG data")
        (input_dir / "mixed.JpEg").write_bytes(b"JPEG data")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        copy_img_files(input_dir, output_dir)

        assert (output_dir / "image.PNG").exists()
        assert (output_dir / "photo.JPG").exists()
        assert (output_dir / "mixed.JpEg").exists()


class TestConvertFilesInFolder:
    """Tests for convert_files_in_folder function."""

    @patch("pydmconverter.__main__.convert")
    @patch("pydmconverter.__main__.copy_img_files")
    def test_convert_files_in_folder_basic(self, mock_copy_img, mock_convert, tmp_path):
        """Test batch conversion of .edl files."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        (input_dir / "file1.edl").write_text("EDM content 1")
        (input_dir / "file2.edl").write_text("EDM content 2")
        (input_dir / "file3.edl").write_text("EDM content 3")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        files_found, files_failed = convert_files_in_folder(
            input_dir, output_dir, ".edl", override=True, scrollable=False
        )

        assert files_found == 3
        assert len(files_failed) == 0

        assert mock_convert.call_count == 3

        mock_copy_img.assert_called_once_with(input_dir, output_dir)

    @patch("pydmconverter.__main__.convert")
    @patch("pydmconverter.__main__.copy_img_files")
    def test_convert_files_in_folder_no_files(self, mock_copy_img, mock_convert, tmp_path):
        """Test directory with no matching files."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        (input_dir / "file.txt").write_text("Text file")
        (input_dir / "data.json").write_text("JSON data")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        files_found, files_failed = convert_files_in_folder(
            input_dir, output_dir, ".edl", override=True, scrollable=False
        )

        assert files_found == 0
        assert len(files_failed) == 0
        mock_convert.assert_not_called()

    @patch("pydmconverter.__main__.convert")
    @patch("pydmconverter.__main__.copy_img_files")
    def test_convert_files_in_folder_with_override(self, mock_copy_img, mock_convert, tmp_path):
        """Test override flag allows overwriting existing files."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        (input_dir / "file1.edl").write_text("EDM content")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create existing output file
        (output_dir / "file1.ui").write_text("Existing UI file")

        # Convert with override=True
        files_found, files_failed = convert_files_in_folder(
            input_dir, output_dir, ".edl", override=True, scrollable=False
        )

        assert files_found == 1
        assert len(files_failed) == 0
        mock_convert.assert_called_once()

    @patch("pydmconverter.__main__.convert")
    @patch("pydmconverter.__main__.copy_img_files")
    def test_convert_files_in_folder_without_override(self, mock_copy_img, mock_convert, tmp_path):
        """Test that existing files are skipped when override=False."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        (input_dir / "file1.edl").write_text("EDM content")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        (output_dir / "file1.ui").write_text("Existing UI file")

        files_found, files_failed = convert_files_in_folder(
            input_dir, output_dir, ".edl", override=False, scrollable=False
        )

        assert files_found == 1
        assert len(files_failed) == 1
        assert str(input_dir / "file1.edl") in files_failed
        mock_convert.assert_not_called()


class TestRun:
    """Tests for run function."""

    @patch("pydmconverter.__main__.convert")
    @patch("pydmconverter.__main__.copy_img_files")
    def test_run_basic_file_conversion(self, mock_copy_img, mock_convert, tmp_path):
        """Test single file conversion through run()."""
        input_file = tmp_path / "test.edl"
        input_file.write_text("EDM content")

        output_file = tmp_path / "test.ui"

        run(str(input_file), str(output_file), input_file_type=".edl", override=False, scrollable=False)

        mock_convert.assert_called_once()
        args = mock_convert.call_args[0]
        assert args[0] == str(input_file)
        assert args[1] == str(output_file)

        mock_copy_img.assert_called_once()

    @patch("pydmconverter.__main__.convert_files_in_folder")
    @patch("pydmconverter.__main__.copy_img_files")
    def test_run_directory_conversion(self, mock_copy_img, mock_convert_folder, tmp_path):
        """Test directory conversion through run()."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        output_dir = tmp_path / "output"

        mock_convert_folder.return_value = (3, [])

        run(str(input_dir), str(output_dir), input_file_type=".edl", override=True, scrollable=False)

        mock_convert_folder.assert_called_once()
        args = mock_convert_folder.call_args[0]
        assert args[0] == input_dir
        assert str(args[1]) == str(output_dir)
        assert args[2] == ".edl"

    @patch("pydmconverter.__main__.convert")
    @patch("pydmconverter.__main__.copy_img_files")
    def test_run_file_exists_without_override(self, mock_copy_img, mock_convert, tmp_path):
        """Test that FileExistsError is raised when output exists and override=False."""
        input_file = tmp_path / "test.edl"
        input_file.write_text("EDM content")

        output_file = tmp_path / "test.ui"
        output_file.write_text("Existing UI file")

        with pytest.raises(FileExistsError) as exc_info:
            run(str(input_file), str(output_file), input_file_type=".edl", override=False, scrollable=False)

        assert "already exists" in str(exc_info.value)
        assert "Use --override" in str(exc_info.value)

    @patch("pydmconverter.__main__.convert")
    @patch("pydmconverter.__main__.copy_img_files")
    def test_run_adds_ui_suffix(self, mock_copy_img, mock_convert, tmp_path):
        """Test that .ui suffix is automatically added to output file."""
        input_file = tmp_path / "test.edl"
        input_file.write_text("EDM content")

        output_file = tmp_path / "test.txt"

        run(str(input_file), str(output_file), input_file_type=".edl", override=False, scrollable=False)

        mock_convert.assert_called_once()
        args = mock_convert.call_args[0]
        assert args[1].endswith(".ui")

    @patch("pydmconverter.__main__.convert")
    @patch("pydmconverter.__main__.copy_img_files")
    def test_run_with_scrollable_option(self, mock_copy_img, mock_convert, tmp_path):
        """Test that scrollable option is passed through."""
        input_file = tmp_path / "test.edl"
        input_file.write_text("EDM content")

        output_file = tmp_path / "test.ui"

        run(str(input_file), str(output_file), input_file_type=".edl", override=False, scrollable=True)

        mock_convert.assert_called_once()
        args = mock_convert.call_args[0]
        assert len(args) == 3
        assert args[2] is True

    @patch("pydmconverter.__main__.convert_files_in_folder")
    def test_run_directory_prepends_dot_to_file_type(self, mock_convert_folder, tmp_path):
        """Test that file type gets . prepended if missing."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        output_dir = tmp_path / "output"

        mock_convert_folder.return_value = (0, [])

        run(str(input_dir), str(output_dir), input_file_type="edl", override=True, scrollable=False)

        args = mock_convert_folder.call_args[0]
        assert args[2] == ".edl"
