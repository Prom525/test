$ErrorActionPreference = "Stop"

Set-Location C:\ai-platform

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " PROMATI PHASE-A FREEZE WRITER PREFLIGHT V1.1" -ForegroundColor Cyan
Write-Host " READ ONLY / NO FREEZE WRITE" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

$WriterPath = "C:\ai-platform\write_phase_a_freeze_artifact_v1.ps1"

$ExpectedWriterHash =
    "34F65D40365AD26971012BE750F0E8DFBBF343A7232F1259C66C632EFE5A6AE9"

$ProtectedFiles = [ordered]@{
    "runtime" = @{
        Path = "C:\ai-platform\artifacts\golden_testset_v1\a2e_entity_coverage_20260826_162549\a2e_runtime_200.json"
        Hash = "27D1C63B024D2EE26198F009AF95749DF92DE32A9E7E690E47D97FC1F0970016"
    }

    "summary" = @{
        Path = "C:\ai-platform\artifacts\golden_testset_v1\a2e_entity_coverage_20260826_162549\a2e_entity_summary.json"
        Hash = "37AF885A1A823A6826C54B1034117C5669E94CFBB2D459B7166ECA332640FE23"
    }

    "findings" = @{
        Path = "C:\ai-platform\artifacts\golden_testset_v1\a2e_entity_coverage_20260826_162549\a2e_entity_findings.json"
        Hash = "D09C9853A9C8A70FD3282285DB969D7CAF8538D9D055FCEA51FC03EC78D015A5"
    }

    "matrix" = @{
        Path = "C:\ai-platform\artifacts\golden_testset_v1\a2e_entity_coverage_20260826_162549\a2e_entity_key_matrix.csv"
        Hash = "F75CA56CF52EDFAD605F413FE814E3D3A018FFD91D63038FE672311B510E32A0"
    }

    "contract" = @{
        Path = "C:\ai-platform\artifacts\golden_testset_v1\phase_a_test_contract_v2.csv"
        Hash = "EE02DDC2FE72501F31DB80B97C4555B8D3E261A7C64A53079FAB5FB85F545529"
    }

    "evaluator" = @{
        Path = "C:\ai-platform\audit_phase_a2e_entity_coverage_cardinality_v1.ps1"
        Hash = "FDCE2E6E62685BF891216644B0ACC0530350267DCAFDE984F69E2CC899438A0B"
    }

    "a2c" = @{
        Path = "C:\ai-platform\artifacts\golden_testset_v1\a2c_dualrun_accept_20260826_114355\a2c_dualrun_full.json"
        Hash = "EEC621E1696BFA9E77CA627031EDECC4E01A9EEAF1C9F5D2A96B5954A09FD266"
    }

    "a2d" = @{
        Path = "C:\ai-platform\artifacts\golden_testset_v1\a2d_dualrun_accept_20260826_122437\a2d_dualrun_full.json"
        Hash = "96FA7AAD95D73C325FB30035CE9BB997666EF70CEA33ADF70D7C0B28E311088D"
    }

    "band192_cf" = @{
        Path = "C:\ai-platform\artifacts\golden_testset_v1\a2e_band_codes_192_counterfactual_20260826_151425\a2e_band_codes_192_counterfactual_200.json"
        Hash = "090EDE8CB10EEFB680C4B740BFC6D92211A3B503BF36D703D2435E8CD054D0DF"
    }

    "models.py" = @{
        Path = "C:\ai-platform\api\app\orchestrator\models.py"
        Hash = "14C2E9DC4342D4554DF077925D9DAF3FB50B1D36A9B6D093D50379522E190C9E"
    }

    "understanding.py" = @{
        Path = "C:\ai-platform\api\app\orchestrator\understanding.py"
        Hash = "CF35835C9BD03D1267CED10EE47DCB67795A4DEA38336E4A1E8126049769BF78"
    }

    "planner.py" = @{
        Path = "C:\ai-platform\api\app\orchestrator\planner.py"
        Hash = "26DB88A34A29792C82A1F6685E43D397316EE2C5E8E000D5E1A9C4FB77E9CF68"
    }

    "band_candidate_shadow.py" = @{
        Path = "C:\ai-platform\api\app\orchestrator\band_candidate_shadow.py"
        Hash = "D6FC239D81F1FFCB30D5E01EC6BD5B48F098AD21F8A0C9BCC92742C45057C484"
    }

    "query_classification.py" = @{
        Path = "C:\ai-platform\api\app\orchestrator\query_classification.py"
        Hash = "193C690E4D62798566B57D84BD590DB04655357FD6DE86AE4F56EB5E16E35576"
    }

    "normalizer.py" = @{
        Path = "C:\ai-platform\api\app\orchestrator\normalizer.py"
        Hash = "3AC3E4381FDB3501FF01E1D19BE317CBDCB03B214034409284E29A2D1303DDDB"
    }

    "complexity.py" = @{
        Path = "C:\ai-platform\api\app\orchestrator\complexity.py"
        Hash = "1A479E52DD552F92086D3A4D199FC54F9D0BAE77CC6B15924962570B9B425022"
    }

    "service.py" = @{
        Path = "C:\ai-platform\api\app\orchestrator\service.py"
        Hash = "6BDA7AD0D4EB73DE6BB56170CC97B56319EA7AAFBCDA7E9EAFA4F524A4643761"
    }

    "executor.py" = @{
        Path = "C:\ai-platform\api\app\orchestrator\executor.py"
        Hash = "64240F4D0C0A63D698DDFE44764DF14E2D2A9CC65EFB53589AED77B479019A5A"
    }
}


Write-Host ""
Write-Host "=== WRITER IDENTITY ==="

if (-not (Test-Path -LiteralPath $WriterPath -PathType Leaf)) {
    throw "Freeze writer ontbreekt."
}

$WriterHash = (Get-FileHash $WriterPath -Algorithm SHA256).Hash

Write-Host "WRITER_SHA256=$WriterHash"

if ($WriterHash -ne $ExpectedWriterHash) {
    throw "Freeze writer hash mismatch."
}


Write-Host ""
Write-Host "=== WRITER PARSER ==="

$Tokens = $null
$Errors = $null

[System.Management.Automation.Language.Parser]::ParseFile(
    $WriterPath,
    [ref]$Tokens,
    [ref]$Errors
) | Out-Null

Write-Host "WRITER_PARSE_ERROR_COUNT=$($Errors.Count)"

if ($Errors.Count -ne 0) {
    $Errors | Format-Table -AutoSize
    throw "Freeze writer is niet parser-green."
}

Write-Host "WRITER_PARSER_GREEN=TRUE"


Write-Host ""
Write-Host "=== FREEZE INPUT / APP HASHES ==="

foreach ($Name in $ProtectedFiles.Keys) {

    $Entry = $ProtectedFiles[$Name]
    $Path = $Entry.Path
    $ExpectedHash = $Entry.Hash

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Protected freeze input ontbreekt: $Name"
    }

    $ActualHash = (Get-FileHash $Path -Algorithm SHA256).Hash

    Write-Host "$Name=$ActualHash"

    if ($ActualHash -ne $ExpectedHash) {
        throw "Freeze preflight hash mismatch: $Name"
    }
}

Write-Host "ALL_FREEZE_INPUT_HASHES_OK=TRUE"


Write-Host ""
Write-Host "=== WRITER INTENT MARKERS ==="

$WriterText = Get-Content -LiteralPath $WriterPath -Raw

$RequiredMarkerCounts = [ordered]@{
    "PHASE_A_FREEZE_ARTIFACT_WRITTEN=TRUE" = 1
    "PHASE_A_FORMAL_FREEZE_READY=TRUE" = 1
    "NEXT_PHASE=PHASE_B_EXECUTION_CONTRACTS" = 2
    "PHASE_A_FORMAL_FREEZE_ARTIFACT_COMPLETE" = 1
}

foreach ($Marker in $RequiredMarkerCounts.Keys) {

    $ExpectedCount = [int]$RequiredMarkerCounts[$Marker]

    $Count = (
        [regex]::Matches(
            $WriterText,
            [regex]::Escape($Marker)
        )
    ).Count

    Write-Host "MARKER_COUNT[$Marker]=$Count"
    Write-Host "MARKER_EXPECTED_COUNT[$Marker]=$ExpectedCount"

    if ($Count -ne $ExpectedCount) {
        throw (
            "Freeze writer marker count mismatch: " +
            "$Marker actual=$Count expected=$ExpectedCount"
        )
    }
}

Write-Host "WRITER_FINAL_MARKERS_PRESENT=TRUE"


Write-Host ""
Write-Host "=== PREFLIGHT DECISION ==="

Write-Host "FREEZE_WRITER_EXECUTED=FALSE"
Write-Host "PHASE_A_FREEZE_ARTIFACT_WRITTEN=FALSE"

Write-Host "PROMATI_APP_CODE_CHANGED=FALSE"
Write-Host "EVALUATOR_CHANGED=FALSE"
Write-Host "GOLDEN_CONTRACT_CHANGED=FALSE"
Write-Host "FREEZE_EVIDENCE_CHANGED=FALSE"

Write-Host "NO_REBUILD_PERFORMED=TRUE"
Write-Host "NO_API_ENDPOINT_CALLS=TRUE"
Write-Host "NO_EXECUTOR_CALLS=TRUE"
Write-Host "NO_SPECIALIST_CALLS=TRUE"
Write-Host "NO_RESEARCH_PROVIDER_CALLS=TRUE"
Write-Host "NO_DB_WRITES=TRUE"

Write-Host ""
Write-Host "PHASE_A_FREEZE_WRITER_PREFLIGHT_OK=TRUE" -ForegroundColor Green
Write-Host "NEXT_STEP_CANDIDATE=EXECUTE_FREEZE_WRITER" -ForegroundColor Green