"""Tests for project scanner."""

from pathlib import Path

from ctxforge.analysis.scanner import scan_project


class TestScanProject:
    def test_basic_python_project(self, tmp_path: Path):
        """Scan a minimal Python project."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "main.py").write_text("print('hello')")
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test-proj"\n')
        (tmp_path / "tests").mkdir()

        report = scan_project(tmp_path)

        assert report.project_name == tmp_path.name
        assert "python" in report.languages
        assert "pyproject.toml" in report.config_files

    def test_empty_directory(self, tmp_path: Path):
        """Scan an empty directory should not crash."""
        report = scan_project(tmp_path)
        assert report.project_name == tmp_path.name
        assert report.languages == []

    def test_dir_tree(self, tmp_path: Path):
        """Directory tree should list subdirectories up to max depth."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "api").mkdir()
        (tmp_path / "tests").mkdir()

        report = scan_project(tmp_path)

        assert "src" in report.dir_tree
        assert "tests" in report.dir_tree

    def test_excludes(self, tmp_path: Path):
        """Excluded directories should not appear in results."""
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg").mkdir()
        (tmp_path / "node_modules" / "pkg" / "index.js").write_text("")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("")

        report = scan_project(tmp_path)

        assert "node_modules" not in report.dir_tree
