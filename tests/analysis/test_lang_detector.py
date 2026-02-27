"""Tests for language detection."""

from pathlib import Path

from ctxforge.analysis.lang_detector import detect_languages


class TestDetectLanguages:
    def test_python_files(self):
        files = [Path(f"src/mod{i}.py") for i in range(5)]
        assert detect_languages(files) == ["python"]

    def test_multiple_languages(self):
        files = [
            Path("src/app.py"),
            Path("src/utils.py"),
            Path("src/main.py"),
            Path("frontend/index.ts"),
            Path("frontend/app.ts"),
            Path("frontend/utils.ts"),
        ]
        result = detect_languages(files)
        assert "python" in result
        assert "typescript" in result

    def test_below_threshold(self):
        """Single file of a language should not be detected."""
        files = [Path("src/app.py"), Path("script.rb")]
        result = detect_languages(files, min_files=2)
        assert "ruby" not in result

    def test_empty(self):
        assert detect_languages([]) == []
