from pathlib import Path

from prompt_study_notifier.settings import resolve_project_root


def test_resolve_project_root_prefers_repo_cwd(monkeypatch: object) -> None:
    repo_root = Path("/Users/darkcreation/Documents/git_repos/prompt-study-notifier")
    monkeypatch.chdir(repo_root)
    assert resolve_project_root() == repo_root
