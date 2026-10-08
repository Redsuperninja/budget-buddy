# Preview and import a bank CSV file into an account on the TEST Home Base.
#
#   scripts\import-csv.ps1                                       the sample file into the demo checking account
#   scripts\import-csv.ps1 -File my.csv -Account "Demo Credit Card" -FlipSign
#   add -SkipInvalid to import the good rows when a few rows can't be read

param(
    [string]$File = (Join-Path $PSScriptRoot "sample-bank-statement.csv"),
    [string]$Account = "Demo Everyday Checking",
    [switch]$FlipSign,
    [switch]$SkipInvalid
)

. "$PSScriptRoot\test-settings.ps1"
Assert-SetUp
$extra = @()
if ($FlipSign) { $extra += "--flip-sign" }
if ($SkipInvalid) { $extra += "--skip-invalid" }
& $Python (Join-Path $PSScriptRoot "import_csv.py") $File --account $Account --port $TestPort @extra
exit $LASTEXITCODE
