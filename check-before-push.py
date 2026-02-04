#!/usr/bin/env python3
"""
Pre-push safety check: ensures no sensitive files are staged or untracked
in the repo root. Run before 'git push' (e.g. manually or via a git hook).
"""
import os
import subprocess
import sys

# Files/folders that must NEVER be committed (repo root only)
SENSITIVE_PATTERNS = [
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "credentials.json",
    "token.json",
    "client_secrets.json",
]

# Partial names that indicate a sensitive file
SENSITIVE_SUBSTRINGS = [
    "client_secret",
    ".credentials",
]

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def run_git(args):
    """Run git command, return (success, output)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0, (result.stdout or "") + (result.stderr or "")
    except FileNotFoundError:
        return False, "git not found"
    except subprocess.TimeoutExpired:
        return False, "git timed out"


def get_staged_and_untracked():
    """Return (staged_files, untracked_files)."""
    staged = []
    untracked = []

    # Staged files
    ok, out = run_git(["diff", "--cached", "--name-only"])
    if ok:
        for line in out.strip().splitlines():
            p = line.strip()
            if p:
                staged.append(p)

    # Untracked files: "?? path" in git status --porcelain
    ok, out = run_git(["status", "--porcelain", "-u"])
    if ok:
        for line in out.strip().splitlines():
            if len(line) >= 4 and line[:2] == "??":
                p = line[3:].strip()
                if p:
                    untracked.append(p)

    return staged, untracked


def is_sensitive(path):
    """Return True if path looks like a sensitive file."""
    base = os.path.basename(path)
    # Only care about root-level or clearly sensitive paths
    if path.startswith(".git"):
        return False
    if os.path.sep in path and path.count(os.path.sep) > 1:
        # Deep path; still check name
        pass
    if base in SENSITIVE_PATTERNS:
        return True
    for sub in SENSITIVE_SUBSTRINGS:
        if sub in base:
            return True
    return False


def get_tracked_files():
    """Return list of tracked files in the repo."""
    ok, out = run_git(["ls-files"])
    if not ok:
        return []
    return [p.strip() for p in out.strip().splitlines() if p.strip()]


def main():
    # Check we're in a git repo
    ok, _ = run_git(["rev-parse", "--git-dir"])
    if not ok:
        print("Not a git repository. Skipping check.")
        sys.exit(0)

    staged, untracked = get_staged_and_untracked()
    to_commit = staged + untracked

    # Block: sensitive files that would be committed (staged or new untracked)
    problems = [f for f in to_commit if is_sensitive(f)]

    if problems:
        print("ERROR: The following sensitive files are staged or untracked and must NOT be committed:")
        for p in sorted(set(problems)):
            print("  -", p)
        print()
        print("If already staged:  git rm --cached <file>")
        print("Ensure .env (etc.) is in .gitignore and never run 'git add .env'.")
        sys.exit(1)

    # Warn: sensitive-looking files already tracked (in repo history)
    tracked = get_tracked_files()
    already_tracked = [f for f in tracked if is_sensitive(f)]
    if already_tracked:
        print("WARNING: These sensitive-looking files are already tracked (they may be in history):")
        for p in sorted(set(already_tracked)):
            print("  -", p)
        print("To stop tracking (keep file on disk):  git rm --cached <file>  then commit.")
        print()

    print("Pre-push check passed: no sensitive files will be committed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
