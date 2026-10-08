# Tidy local branches after pull requests are merged on GitHub.
#
#   powershell -ExecutionPolicy Bypass -File scripts\dev\tidy-branches.ps1           show what would happen
#   powershell -ExecutionPolicy Bypass -File scripts\dev\tidy-branches.ps1 -Apply    do it
#
# 1. Fetches from GitHub; branches GitHub deleted after a merge are forgotten (--prune).
# 2. Deletes each local branch whose GitHub branch is gone, but only if nothing would be lost: the local branch
#    was exactly what was pushed, or its changes are already in main (squash merge). Removes its worktree too.
# 3. Moves branches that were stacked on a merged branch onto the new main in one step (rebase --update-refs).

param([switch]$Apply)
$ErrorActionPreference = "Stop"

function RunGit { & git @args; if ($LASTEXITCODE) { throw "git $args failed" } }
function IsAncestor($a, $b) { & git merge-base --is-ancestor $a $b; return $LASTEXITCODE -eq 0 }

# True if all of a branch's changes are already in origin/main as one squash-merged commit.
function IsSquashedIntoMain($branch) {
    $base = RunGit merge-base origin/main $branch
    $squashed = RunGit commit-tree "$branch^{tree}" -p $base -m squash
    return (RunGit cherry origin/main $squashed) -like "-*"
}

# Before fetching: which branches track a GitHub branch, and does each match what was pushed?
$tracked = @{}
foreach ($line in (RunGit for-each-ref --format="%(refname:short)|%(objectname)|%(upstream:short)" refs/heads)) {
    $name, $tip, $upstream = $line -split "\|"
    if ($upstream) {
        $pushed = (& git rev-parse --verify --quiet $upstream)
        $tracked[$name] = @{ Tip = $tip; InSync = ($pushed -eq $tip) }
    }
}

RunGit fetch --prune origin

$current = RunGit branch --show-current
$merged = @()
foreach ($line in (RunGit for-each-ref --format="%(refname:short)|%(upstream:track)" refs/heads)) {
    $name, $track = $line -split "\|"
    if ($track -ne "[gone]") { continue }
    if (-not ($tracked[$name].InSync -or (IsSquashedIntoMain $name))) {
        Write-Host "Keeping $name`: it has commits that were never pushed." -ForegroundColor Yellow
        continue
    }
    $merged += $name
}

if (-not $merged) { Write-Host "Nothing to tidy."; exit 0 }

# Branches built on top of a merged one: move them onto main, keeping the stack's branch labels in step.
foreach ($name in $merged) {
    $tip = RunGit rev-parse $name
    $children = RunGit for-each-ref --contains $tip --format="%(refname:short)" refs/heads |
        Where-Object { $_ -ne $name -and $merged -notcontains $_ }
    # Only the top of each stack; --update-refs moves the branches below it along with it.
    $tops = $children | Where-Object {
        $c = $_
        -not ($children | Where-Object { $_ -ne $c -and (IsAncestor $c $_) })
    }
    foreach ($child in $tops) {
        Write-Host "Restack $child onto origin/main (it was built on merged $name)"
        if ($Apply) { RunGit rebase --update-refs --onto origin/main $tip $child }
    }
}

$worktrees = @{}
$path = $null
foreach ($line in (RunGit worktree list --porcelain)) {
    if ($line -like "worktree *") { $path = $line.Substring(9) }
    if ($line -like "branch refs/heads/*") { $worktrees[$line.Substring(18)] = $path }
}

foreach ($name in $merged) {
    if ($name -eq $current) {
        Write-Host "Skipping $name`: it's checked out here. Switch to main first." -ForegroundColor Yellow
        continue
    }
    Write-Host "Delete merged branch $name"
    if ($Apply) {
        if ($worktrees[$name]) {
            & git worktree remove $worktrees[$name]
            if ($LASTEXITCODE) {
                # Usually Windows holding the folder open (a terminal or editor inside it). Close it and run again.
                Write-Host "Couldn't remove the worktree folder for $name; close anything using it and run again." -ForegroundColor Yellow
                continue
            }
        }
        RunGit branch -D $name
    }
}

if (-not $Apply) { Write-Host "`nNothing changed. Run again with -Apply to do this." -ForegroundColor Cyan }
