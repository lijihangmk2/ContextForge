"""Tests for static documentation/config file detection."""

from pathlib import Path

from ctxforge.analysis.doc_detector import detect_doc_candidates


class TestDetectDocCandidates:
    def test_detect_readme(self, tmp_path: Path):
        (tmp_path / "README.md").write_text("# Hello")
        result = detect_doc_candidates(tmp_path)
        assert "README.md" in result

    def test_config_files_excluded(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("[project]")
        result = detect_doc_candidates(tmp_path)
        assert "pyproject.toml" not in result

    def test_doc_dirs_not_returned(self, tmp_path: Path):
        """Directories are never returned, only individual files."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text("guide")
        result = detect_doc_candidates(tmp_path)
        assert "docs/" not in result
        assert "docs/guide.md" in result

    def test_nothing_found(self, tmp_path: Path):
        result = detect_doc_candidates(tmp_path)
        assert result == []

    def test_case_insensitive(self, tmp_path: Path):
        (tmp_path / "readme.md").write_text("# hello")
        result = detect_doc_candidates(tmp_path)
        assert "readme.md" in result

    def test_detect_other_md_files(self, tmp_path: Path):
        """Root-level *.md files not matching known prefixes are detected."""
        (tmp_path / "CLAUDE.md").write_text("instructions")
        (tmp_path / "DEVELOPMENT.md").write_text("dev guide")
        result = detect_doc_candidates(tmp_path)
        assert "CLAUDE.md" in result
        assert "DEVELOPMENT.md" in result

    def test_md_no_duplicate_with_prefix(self, tmp_path: Path):
        """README.md matched by prefix should not appear twice via *.md."""
        (tmp_path / "README.md").write_text("# Hello")
        result = detect_doc_candidates(tmp_path)
        assert result.count("README.md") == 1

    def test_subdir_md_in_doc_dir(self, tmp_path: Path):
        """Markdown files inside known doc dirs are detected individually."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "api.md").write_text("api")
        (docs / "guide.md").write_text("guide")
        result = detect_doc_candidates(tmp_path)
        assert "docs/api.md" in result
        assert "docs/guide.md" in result

    def test_subdir_md_in_design_dir(self, tmp_path: Path):
        """Markdown files inside design/ are detected."""
        design = tmp_path / "design"
        design.mkdir()
        (design / "architecture.md").write_text("arch")
        result = detect_doc_candidates(tmp_path)
        assert "design/architecture.md" in result

    def test_subdir_md_outside_doc_dirs_ignored(self, tmp_path: Path):
        """Markdown files in arbitrary subdirectories are NOT detected."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "notes.md").write_text("notes")
        lib = tmp_path / "lib"
        lib.mkdir()
        (lib / "info.md").write_text("info")
        result = detect_doc_candidates(tmp_path)
        assert "src/notes.md" not in result
        assert "lib/info.md" not in result

    def test_max_results_cap(self, tmp_path: Path):
        """Results are capped at 30 entries."""
        docs = tmp_path / "docs"
        docs.mkdir()
        for i in range(40):
            (docs / f"file_{i:03d}.md").write_text(f"content {i}")
        result = detect_doc_candidates(tmp_path)
        assert len(result) <= 30

    def test_order(self, tmp_path: Path):
        """Known-prefix docs → other root *.md → doc-dir *.md."""
        (tmp_path / "README.md").write_text("# Hello")
        (tmp_path / "CLAUDE.md").write_text("instructions")
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "api.md").write_text("api")

        result = detect_doc_candidates(tmp_path)
        readme_idx = result.index("README.md")
        claude_idx = result.index("CLAUDE.md")
        docs_api_idx = result.index("docs/api.md")
        assert readme_idx < claude_idx < docs_api_idx
