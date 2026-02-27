"""Tests for Project class."""

import pytest
from pathlib import Path

from ctxforge.core.project import Project, find_project_root
from ctxforge.exceptions import ProjectNotFoundError


class TestFindProjectRoot:
    def test_finds_in_current(self, ctxforge_project: Path):
        root = find_project_root(ctxforge_project)
        assert root == ctxforge_project

    def test_finds_in_parent(self, ctxforge_project: Path):
        subdir = ctxforge_project / "src" / "deep"
        subdir.mkdir(parents=True)
        root = find_project_root(subdir)
        assert root == ctxforge_project

    def test_not_found(self, tmp_path: Path):
        with pytest.raises(ProjectNotFoundError):
            find_project_root(tmp_path)


class TestProject:
    def test_load(self, ctxforge_project: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(ctxforge_project)
        project = Project.load()
        assert project.root == ctxforge_project
        assert project.config.project.name == "test-project"

    def test_ctxforge_dir(self, ctxforge_project: Path):
        project = Project.load(ctxforge_project)
        assert project.ctxforge_dir == ctxforge_project / ".ctxforge"

    def test_profiles_dir(self, ctxforge_project: Path):
        project = Project.load(ctxforge_project)
        assert project.profiles_dir == ctxforge_project / ".ctxforge" / "profiles"
