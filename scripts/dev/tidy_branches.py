"""Tidy local branches after pull requests are merged on GitHub. Run it inside the repo (or a
worktree of it).

    python3 scripts/dev/tidy_branches.py            show what would happen   (on Windows, type py)
    python3 scripts/dev/tidy_branches.py --apply    do it

1. Fetches from GitHub; branches GitHub deleted after a merge are forgotten (--prune).
2. Deletes each local branch whose GitHub branch is gone, but only if nothing would be lost: the
   local branch was exactly what was pushed, or its changes are already in main (squash merge).
   Removes its worktree too.
3. Moves branches that were stacked on a merged branch onto the new main in one step
   (rebase --update-refs).
"""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # scripts/, for _common

from _common import say, stop  # noqa: E402


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    done = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and done.returncode:
        stop(f"git {' '.join(args)} failed:\n{done.stderr.strip()}")
    return done


def lines(*args: str) -> list[str]:
    return git(*args).stdout.splitlines()


def is_ancestor(a: str, b: str) -> bool:
    return git("merge-base", "--is-ancestor", a, b, check=False).returncode == 0


def is_squashed_into_main(branch: str) -> bool:
    """True if all of a branch's changes are already in origin/main as one squash-merged commit."""
    base = lines("merge-base", "origin/main", branch)[0]
    squashed = lines("commit-tree", f"{branch}^{{tree}}", "-p", base, "-m", "squash")[0]
    cherry = lines("cherry", "origin/main", squashed)
    return bool(cherry) and all(line.startswith("-") for line in cherry)


def refs(fields: str) -> list[list[str]]:
    return [line.split("|") for line in lines("for-each-ref", f"--format={fields}", "refs/heads")]


def main() -> int:
    parser = argparse.ArgumentParser(description="Tidy local branches after their PRs merge.")
    parser.add_argument("--apply", action="store_true", help="do it (otherwise only show)")
    apply = parser.parse_args().apply

    # Before fetching: which branches track a GitHub branch, and does each match what was pushed?
    in_sync = {}
    for name, tip, upstream in refs("%(refname:short)|%(objectname)|%(upstream:short)"):
        if upstream:
            pushed = git("rev-parse", "--verify", "--quiet", upstream, check=False).stdout.strip()
            in_sync[name] = pushed == tip

    git("fetch", "--prune", "origin")

    current = lines("branch", "--show-current")
    merged = []
    for name, track in refs("%(refname:short)|%(upstream:track)"):
        if track != "[gone]":
            continue
        if not (in_sync.get(name) or is_squashed_into_main(name)):
            say(f"Keeping {name}: it has commits that were never pushed.", "yellow")
            continue
        merged.append(name)

    if not merged:
        say("Nothing to tidy.")
        return 0

    # Branches built on a merged one: move them onto main, keeping the stack's labels in step.
    for name in merged:
        tip = lines("rev-parse", name)[0]
        children = [
            child
            for child in lines(
                "for-each-ref", "--contains", tip, "--format=%(refname:short)", "refs/heads"
            )
            if child != name and child not in merged
        ]
        # Only the top of each stack; --update-refs moves the branches below it along with it.
        tops = [c for c in children if not any(o != c and is_ancestor(c, o) for o in children)]
        for child in tops:
            say(f"Restack {child} onto origin/main (it was built on merged {name})")
            if apply:
                git("rebase", "--update-refs", "--onto", "origin/main", tip, child)

    worktrees, path = {}, None
    for line in lines("worktree", "list", "--porcelain"):
        if line.startswith("worktree "):
            path = line[len("worktree ") :]
        if line.startswith("branch refs/heads/"):
            worktrees[line[len("branch refs/heads/") :]] = path

    for name in merged:
        if current and name == current[0]:
            say(f"Skipping {name}: it's checked out here. Switch to main first.", "yellow")
            continue
        say(f"Delete merged branch {name}")
        if not apply:
            continue
        if name in worktrees and git("worktree", "remove", worktrees[name], check=False).returncode:
            # Usually something holding the folder open (a terminal or editor inside it).
            say(
                f"Couldn't remove the worktree folder for {name}; close anything using it, "
                "then run again.",
                "yellow",
            )
            continue
        git("branch", "-D", name)

    if not apply:
        say("\nNothing changed. Run again with --apply to do this.", "cyan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
