$ErrorActionPreference = "Stop"

$AppRoot = "C:\ai-platform\api\app"

$ExpectedHashes = [ordered]@{
    "orchestrator\executor.py" =
        "64240F4D0C0A63D698DDFE44764DF14E2D2A9CC65EFB53589AED77B479019A5A"

    "orchestrator\planner.py" =
        "26DB88A34A29792C82A1F6685E43D397316EE2C5E8E000D5E1A9C4FB77E9CF68"

    "orchestrator\service.py" =
        "6BDA7AD0D4EB73DE6BB56170CC97B56319EA7AAFBCDA7E9EAFA4F524A4643761"

    "orchestrator\research_agent.py" =
        "672F029DDF1AA655CC11EB42ACAB23933918B2835B8D81B724FB9AF18A98BC0D"

    "routers\hybrid_api.py" =
        "2A5253EFCFC1EAA53DAD874F14D4AA71549E201A98D8BE8A384E7016FB0E657F"

    "routers\analysis_api_v10.py" =
        "6FAD131A4EE06375DCDBECE7018F426D08A2C761FE22C4BD8624A24B9085A6A1"

    "orchestrator\models.py" =
        "14C2E9DC4342D4554DF077925D9DAF3FB50B1D36A9B6D093D50379522E190C9E"

    "orchestrator\understanding.py" =
        "CF35835C9BD03D1267CED10EE47DCB67795A4DEA38336E4A1E8126049769BF78"
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " PROMATI PHASE-B2E TYPED EXECUTION CONTRACT V1" -ForegroundColor Cyan
Write-Host " DESIGN ONLY / READ ONLY / NO SOURCE WRITES" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan


# ============================================================
# Source guards
# ============================================================

$BeforeHashes = [ordered]@{}

Write-Host ""
Write-Host "=== SOURCE GUARDS ==="

foreach ($RelativePath in $ExpectedHashes.Keys) {

    $Path = Join-Path $AppRoot $RelativePath

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required source ontbreekt: $RelativePath"
    }

    $Hash = (
        Get-FileHash `
            -LiteralPath $Path `
            -Algorithm SHA256
    ).Hash

    $BeforeHashes[$Path] = $Hash

    Write-Host "$RelativePath=$Hash"

    if ($Hash -ne $ExpectedHashes[$RelativePath]) {
        throw "Source hash mismatch: $RelativePath"
    }
}

Write-Host "B2E_SOURCE_GUARDS_OK=TRUE"


# ============================================================
# Contract-level enums
# ============================================================

$TransportStates = @(
    "NOT_ATTEMPTED"
    "COMPLETED"
    "FAILED"
)

$SemanticOutcomes = @(
    "SUCCESS"
    "CLARIFICATION_REQUIRED"
    "AMBIGUOUS"
    "CONTEXT_CONFLICT"
    "NOT_FOUND"
    "UNAVAILABLE"
    "REDIRECT"
    "ERROR"
    "UNKNOWN"
)

$FallbackPolicies = @(
    "DISABLED"
    "EXPLICIT"
    "UNRESOLVED"
)

Write-Host ""
Write-Host "=== PROPOSED CONTRACT ENUMS ==="

foreach ($Value in $TransportStates) {
    Write-Host "TRANSPORT_STATE=$Value"
}

foreach ($Value in $SemanticOutcomes) {
    Write-Host "SEMANTIC_OUTCOME=$Value"
}

foreach ($Value in $FallbackPolicies) {
    Write-Host "FALLBACK_POLICY=$Value"
}


# ============================================================
# ExecutionRequest design
# ============================================================

$ExecutionRequestFields = @(
    "contract_version:str"
    "step_id:str"
    "domain:str"
    "action:str"
    "endpoint:str"
    "params:dict[str,Any]"
    "required:bool"
    "timeout_seconds:float"
    "retry_count:int"
    "fallback_policy:FallbackPolicy"
    "legacy_fallback_allowed:bool|None"
)

Write-Host ""
Write-Host "=== EXECUTION REQUEST V1 ==="

foreach ($Field in $ExecutionRequestFields) {
    Write-Host "EXECUTION_REQUEST_FIELD=$Field"
}

Write-Host "EXECUTION_REQUEST_TIMEOUT_DEFAULT_SECONDS=30"
Write-Host "EXECUTION_REQUEST_RETRY_COUNT_CURRENT=0"


# ============================================================
# ExecutionResult design
# ============================================================

$ExecutionResultFields = @(
    "contract_version:str"
    "step_id:str"
    "action:str"
    "domain:str"
    "endpoint:str"
    "transport_state:ExecutionTransportState"
    "semantic_outcome:ExecutionOutcome"
    "specialist_status:str|None"
    "legacy_accepted:bool"
    "result:dict[str,Any]"
    "error:str|None"
    "attempt_count:int"
    "duration_ms:int|None"
    "evidence_metadata:dict[str,Any]|None"
    "provenance_metadata:dict[str,Any]|None"
)

Write-Host ""
Write-Host "=== EXECUTION RESULT V1 ==="

foreach ($Field in $ExecutionResultFields) {
    Write-Host "EXECUTION_RESULT_FIELD=$Field"
}


# ============================================================
# Compatibility rules
# ============================================================

Write-Host ""
Write-Host "=== BACKWARD COMPATIBILITY RULES ==="

Write-Host "COMPAT_RULE=KEEP_CURRENT_EXECUTOR_WRAPPER_UNCHANGED_DURING_SHADOW"
Write-Host "COMPAT_RULE=PRESERVE_LEGACY_ACCEPTED_BOOLEAN"
Write-Host "COMPAT_RULE=PRESERVE_RAW_SPECIALIST_RESULT"
Write-Host "COMPAT_RULE=PRESERVE_RAW_SPECIALIST_STATUS"
Write-Host "COMPAT_RULE=DERIVE_SEMANTIC_OUTCOME_SEPARATELY"
Write-Host "COMPAT_RULE=DO_NOT_USE_SEMANTIC_OUTCOME_FOR_ROUTING_IN_PHASE_B"
Write-Host "COMPAT_RULE=DO_NOT_CHANGE_PHASE_A_QUERYPLAN"
Write-Host "COMPAT_RULE=DO_NOT_CHANGE_SPECIALIST_HTTP_ENDPOINTS"
Write-Host "COMPAT_RULE=DO_NOT_ENABLE_NEW_FALLBACK_BEHAVIOR"
Write-Host "COMPAT_RULE=DO_NOT_ENABLE_RETRIES"

Write-Host "LEGACY_ACCEPTED_MEANS=LEGACY_EXECUTOR_ACCEPTANCE_ONLY"
Write-Host "LEGACY_ACCEPTED_DOES_NOT_MEAN=SEMANTIC_SUCCESS"


# ============================================================
# Specialist registry design
# ============================================================

$Contracts = @(
    [pscustomobject]@{
        Action = "product_assistant"
        Endpoint = "/product/assistant/ask"
        Owner = "routers/hybrid_api.py:product_assistant_ask"
        Required = "vraag"
        AcceptedFields = "vraag,q,family_name,family_code,belt_width_mm,choice_type,component_group,mode,limit"
        PlannerFields = "vraag,mode"
        ResearchFields = "vraag,family_code,belt_width_mm,choice_type,component_group,mode,limit"
        DirectPlanner = "YES"
        LegacyFallbackAllowed = "TRUE"
        FallbackPolicy = "UNRESOLVED"
        StatusContract = "STATIC_OBSERVED"
        StatusMap = "ok=>SUCCESS"
    }

    [pscustomobject]@{
        Action = "analysis_assistant"
        Endpoint = "/analysis/assistant/ask"
        Owner = "routers/analysis_api_v10.py:analysis_assistant_ask"
        Required = "vraag"
        AcceptedFields = "vraag,lijn_code,date_from,date_to,band_code,scraper_type,zijde,scope_code,scope_type,area_code,installation_code,limit"
        PlannerFields = "vraag,mode"
        ResearchFields = "vraag,lijn_code,band_code,scraper_type,zijde,date_from,date_to,mode,limit,scope_code,scope_type,area_code,installation_code"
        DirectPlanner = "YES"
        LegacyFallbackAllowed = "TRUE"
        FallbackPolicy = "UNRESOLVED"
        StatusContract = "STATIC_OBSERVED"
        StatusMap = "resolved=>SUCCESS;clarification_required=>CLARIFICATION_REQUIRED;ambiguous=>AMBIGUOUS;context_conflict=>CONTEXT_CONFLICT;not_found=>NOT_FOUND;unavailable=>UNAVAILABLE"
    }

    [pscustomobject]@{
        Action = "technical_assistant"
        Endpoint = "/technical/assistant/ask"
        Owner = "routers/hybrid_api.py:technical_assistant_ask"
        Required = "vraag"
        AcceptedFields = "vraag,q,topic_group,source_code,item_type,use_rag,limit"
        PlannerFields = "vraag,use_rag"
        ResearchFields = "vraag,topic_group,source_code,item_type,use_rag,limit"
        DirectPlanner = "YES"
        LegacyFallbackAllowed = "TRUE"
        FallbackPolicy = "UNRESOLVED"
        StatusContract = "STATIC_OBSERVED"
        StatusMap = "ok=>SUCCESS;redirect=>REDIRECT"
    }

    [pscustomobject]@{
        Action = "rfq_assistant"
        Endpoint = "/rfq/assistant/ask"
        Owner = "routers/hybrid_api.py:rfq_assistant_ask"
        Required = "vraag"
        AcceptedFields = "vraag,q,rfq_id,position_id,product_type,bearing_type,rubber_material,language,mode,limit"
        PlannerFields = ""
        ResearchFields = "vraag,rfq_id,position_id,product_type,bearing_type,rubber_material,language,mode,limit"
        DirectPlanner = "NO_UNRESOLVED_INTENT"
        LegacyFallbackAllowed = "N/A"
        FallbackPolicy = "UNRESOLVED"
        StatusContract = "STATIC_PARTIAL_ERROR_ONLY"
        StatusMap = "error=>ERROR;other=>UNKNOWN"
    }

    [pscustomobject]@{
        Action = "org_assistant"
        Endpoint = "/org/assistant/ask"
        Owner = "routers/hybrid_api.py:org_assistant_ask"
        Required = "vraag"
        AcceptedFields = "vraag,firma,locatie,afdeling,mode"
        PlannerFields = "vraag,firma,mode"
        ResearchFields = "vraag,firma,locatie,afdeling,mode"
        DirectPlanner = "YES"
        LegacyFallbackAllowed = "TRUE"
        FallbackPolicy = "UNRESOLVED"
        StatusContract = "DELEGATED_NO_STATIC_STATUS"
        StatusMap = "unknown=>UNKNOWN"
    }

    [pscustomobject]@{
        Action = "diagnostics_assistant"
        Endpoint = "/diagnostics/assistant/ask"
        Owner = "routers/hybrid_api.py:diagnostics_assistant_ask"
        Required = "vraag"
        AcceptedFields = "vraag,domain,mode,objects,inspection_key,lijn_code,band_code,source_file_contains,sheet,diagnosis_code,filters,depth,limit"
        PlannerFields = "vraag,domain,mode,depth,limit"
        ResearchFields = "vraag,domain,mode,inspection_key,lijn_code,band_code,source_file_contains,sheet,diagnosis_code,depth,limit"
        DirectPlanner = "YES"
        LegacyFallbackAllowed = "TRUE"
        FallbackPolicy = "UNRESOLVED"
        StatusContract = "DELEGATED_DYNAMIC_STATUS"
        StatusMap = "unknown=>UNKNOWN"
    }
)

Write-Host ""
Write-Host "=== SPECIALIST CONTRACT REGISTRY V1 ==="

foreach ($Contract in $Contracts) {

    Write-Host ""
    Write-Host "SPECIALIST=$($Contract.Action)"
    Write-Host "  ENDPOINT=$($Contract.Endpoint)"
    Write-Host "  OWNER=$($Contract.Owner)"
    Write-Host "  REQUIRED_FIELDS=$($Contract.Required)"
    Write-Host "  ACCEPTED_INPUT_FIELDS=$($Contract.AcceptedFields)"
    Write-Host "  PLANNER_FIELDS=$($Contract.PlannerFields)"
    Write-Host "  RESEARCH_FIELDS=$($Contract.ResearchFields)"
    Write-Host "  DIRECT_PLANNER=$($Contract.DirectPlanner)"
    Write-Host "  LEGACY_FALLBACK_ALLOWED=$($Contract.LegacyFallbackAllowed)"
    Write-Host "  PROPOSED_FALLBACK_POLICY=$($Contract.FallbackPolicy)"
    Write-Host "  STATUS_CONTRACT_STATE=$($Contract.StatusContract)"
    Write-Host "  STATUS_MAP=$($Contract.StatusMap)"
}


# ============================================================
# Outcome derivation policy
# ============================================================

Write-Host ""
Write-Host "=== SEMANTIC OUTCOME DERIVATION POLICY ==="

Write-Host "OUTCOME_RULE=ok=>SUCCESS"
Write-Host "OUTCOME_RULE=resolved=>SUCCESS"
Write-Host "OUTCOME_RULE=clarification_required=>CLARIFICATION_REQUIRED"
Write-Host "OUTCOME_RULE=ambiguous=>AMBIGUOUS"
Write-Host "OUTCOME_RULE=context_conflict=>CONTEXT_CONFLICT"
Write-Host "OUTCOME_RULE=not_found=>NOT_FOUND"
Write-Host "OUTCOME_RULE=unavailable=>UNAVAILABLE"
Write-Host "OUTCOME_RULE=redirect=>REDIRECT"
Write-Host "OUTCOME_RULE=error=>ERROR"
Write-Host "OUTCOME_RULE=failed=>ERROR"
Write-Host "OUTCOME_RULE=failure=>ERROR"

# Deliberately different from current legacy acceptance default.
Write-Host "OUTCOME_RULE=missing_or_unrecognized_status=>UNKNOWN"

Write-Host "OUTCOME_POLICY=MISSING_STATUS_MUST_NOT_BE_ASSUMED_SEMANTIC_SUCCESS"
Write-Host "OUTCOME_POLICY=LEGACY_ACCEPTED_REMAINS_UNCHANGED_IN_SHADOW_MODE"


# ============================================================
# Evidence / provenance boundary
# ============================================================

Write-Host ""
Write-Host "=== EVIDENCE / PROVENANCE BOUNDARY ==="

Write-Host "EVIDENCE_POLICY=METADATA_PLACEHOLDERS_ONLY_IN_PHASE_B"
Write-Host "EVIDENCE_POLICY=NO_EVIDENCE_QUALITY_SCORING_IN_PHASE_B"
Write-Host "EVIDENCE_POLICY=NO_CONFIDENCE_REDESIGN_IN_PHASE_B"
Write-Host "EVIDENCE_POLICY=NO_BOUNDED_RESEARCH_POLICY_CHANGE_IN_PHASE_B"
Write-Host "EVIDENCE_POLICY=PHASE_C_OWNS_EVIDENCE_ASSESSMENT"

Write-Host "PROPOSED_FIELD=evidence_metadata"
Write-Host "PROPOSED_FIELD=provenance_metadata"


# ============================================================
# Proven / unresolved design gates
# ============================================================

$Gates = @(
    [pscustomobject]@{
        Name = "ANALYSIS_MODE_SCHEMA_DRIFT"
        Classification = "PROVEN"
        EnforcementBlocker = "YES"
        Note = "planner/research include mode; request schema does not"
    }

    [pscustomobject]@{
        Name = "ANALYSIS_MODE_RUNTIME_EFFECT"
        Classification = "UNKNOWN"
        EnforcementBlocker = "YES"
        Note = "extra policy not statically declared"
    }

    [pscustomobject]@{
        Name = "RFQ_DIRECT_PLANNER_CAPABILITY_ASYMMETRY"
        Classification = "PROVEN"
        EnforcementBlocker = "NO"
        Note = "active handler plus research capability, no direct planner step"
    }

    [pscustomobject]@{
        Name = "RFQ_DIRECT_PLANNER_ABSENCE_INTENTIONALITY"
        Classification = "UNKNOWN"
        EnforcementBlocker = "YES"
        Note = "do not add RFQ planner step without separate decision"
    }

    [pscustomobject]@{
        Name = "EXECUTOR_SEMANTIC_ACCEPTANCE_FLATTENING"
        Classification = "PROVEN"
        EnforcementBlocker = "NO"
        Note = "shadow outcome can be introduced without changing legacy accepted"
    }

    [pscustomobject]@{
        Name = "ORG_DELEGATED_OUTPUT_OWNERSHIP"
        Classification = "PROVEN"
        EnforcementBlocker = "NO"
        Note = "delegates uniquely to /rag/query"
    }

    [pscustomobject]@{
        Name = "DIAGNOSTICS_DELEGATED_OUTPUT_OWNERSHIP"
        Classification = "PROVEN"
        EnforcementBlocker = "NO"
        Note = "delegates uniquely to /diagnostics/analyze"
    }

    [pscustomobject]@{
        Name = "ORG_DIAGNOSTICS_STATUS_TAXONOMY"
        Classification = "PARTIAL"
        EnforcementBlocker = "YES"
        Note = "delegation owner known; final semantic status schema not fully static"
    }

    [pscustomobject]@{
        Name = "RFQ_SUCCESS_STATUS_TAXONOMY"
        Classification = "PARTIAL"
        EnforcementBlocker = "YES"
        Note = "static handler audit only exposed error"
    }

    [pscustomobject]@{
        Name = "FALLBACK_RUNTIME_CONTRACT"
        Classification = "UNKNOWN"
        EnforcementBlocker = "YES"
        Note = "legacy planner flag exists; executor fallback execution not proven"
    }
)

Write-Host ""
Write-Host "=== DESIGN GATES ==="

$BlockerCount = 0

foreach ($Gate in $Gates) {

    Write-Host (
        "DESIGN_GATE=" +
        $Gate.Name +
        "|classification=" +
        $Gate.Classification +
        "|enforcement_blocker=" +
        $Gate.EnforcementBlocker +
        "|note=" +
        $Gate.Note
    )

    if ($Gate.EnforcementBlocker -eq "YES") {
        $BlockerCount++
    }
}

Write-Host "PRODUCTION_ENFORCEMENT_BLOCKER_COUNT=$BlockerCount"


# ============================================================
# Proposed introduction sequence
# ============================================================

Write-Host ""
Write-Host "=== PROPOSED IMPLEMENTATION SEQUENCE ==="

Write-Host "IMPLEMENTATION_STAGE_1=ADD_TYPES_AND_REGISTRY_ONLY"
Write-Host "IMPLEMENTATION_STAGE_2=DERIVE_TYPED_RESULT_IN_SHADOW"
Write-Host "IMPLEMENTATION_STAGE_3=COMPARE_TYPED_SHADOW_WITH_LEGACY_WRAPPER"
Write-Host "IMPLEMENTATION_STAGE_4=ADD_CONTRACT_TESTS"
Write-Host "IMPLEMENTATION_STAGE_5=RESOLVE_UNKNOWN_GATES"
Write-Host "IMPLEMENTATION_STAGE_6=ONLY_THEN_CONSIDER_ENFORCEMENT"

Write-Host "IMPLEMENTATION_RULE=NO_PHASE_A_ROUTER_CHANGE"
Write-Host "IMPLEMENTATION_RULE=NO_ENDPOINT_CHANGE"
Write-Host "IMPLEMENTATION_RULE=NO_SPECIALIST_BEHAVIOR_CHANGE"
Write-Host "IMPLEMENTATION_RULE=NO_FALLBACK_BEHAVIOR_CHANGE"
Write-Host "IMPLEMENTATION_RULE=NO_RETRY_BEHAVIOR_CHANGE"
Write-Host "IMPLEMENTATION_RULE=SHADOW_FIRST"


# ============================================================
# B2E decision
# ============================================================

$SpecialistCount = $Contracts.Count

$AllSixPresent = (
    $SpecialistCount -eq 6
)

$UniqueActions = (
    $Contracts.Action |
        Sort-Object -Unique
).Count

$RegistryValid = (
    $AllSixPresent -and
    $UniqueActions -eq 6
)

Write-Host ""
Write-Host "=== B2E DECISION ==="

Write-Host "SPECIALIST_CONTRACT_COUNT=$SpecialistCount"
Write-Host "SPECIALIST_ACTION_COUNT_UNIQUE=$UniqueActions"

Write-Host (
    "TYPED_CONTRACT_REGISTRY_STRUCTURALLY_VALID=" +
    $RegistryValid.ToString().ToUpper()
)

Write-Host "TRANSPORT_SEMANTIC_SEPARATION_DESIGNED=TRUE"
Write-Host "LEGACY_ACCEPTED_COMPATIBILITY_PRESERVED=TRUE"
Write-Host "TIMEOUT_POLICY_CAPTURED=TRUE"
Write-Host "RETRY_POLICY_CAPTURED=TRUE"
Write-Host "FALLBACK_POLICY_EXPLICITLY_UNRESOLVED=TRUE"
Write-Host "EVIDENCE_PHASE_BOUNDARY_PRESERVED=TRUE"
Write-Host "PHASE_A_TYPES_UNCHANGED=TRUE"

Write-Host "SHADOW_CONTRACT_DESIGN_READY=TRUE"

Write-Host (
    "PRODUCTION_CONTRACT_ENFORCEMENT_READY=" +
    (
        ($BlockerCount -eq 0).
            ToString().
            ToUpper()
    )
)

Write-Host "NEXT_STEP_CANDIDATE=REVIEW_AND_FREEZE_B2E_CONTRACT_DESIGN_V1"

Write-Host ""
Write-Host "SOURCE_FILES_WRITTEN=FALSE"
Write-Host "ARTIFACT_FILES_WRITTEN=FALSE"
Write-Host "PYTHON_MODULES_IMPORTED=FALSE"
Write-Host "API_ENDPOINTS_CALLED=FALSE"
Write-Host "EXECUTOR_CALLED=FALSE"
Write-Host "SPECIALISTS_EXECUTED=FALSE"
Write-Host "DB_WRITES=FALSE"
Write-Host "PHASE_A_ROUTER_CHANGED=FALSE"
Write-Host "PHASE_B2E_DESIGN_ONLY_COMPLETE=TRUE"


# ============================================================
# Final immutability
# ============================================================

Write-Host ""
Write-Host "=== FINAL IMMUTABILITY ==="

foreach ($RelativePath in $ExpectedHashes.Keys) {

    $Path = Join-Path $AppRoot $RelativePath

    $After = (
        Get-FileHash `
            -LiteralPath $Path `
            -Algorithm SHA256
    ).Hash

    if ($After -ne $BeforeHashes[$Path]) {
        throw "Source veranderde tijdens B2E design: $RelativePath"
    }
}

Write-Host "WATCHED_SOURCE_FILES_CHANGED=FALSE"
Write-Host "PHASE_A_FROZEN_FILES_CHANGED=FALSE"
Write-Host "PROMATI_SOURCE_CHANGED=FALSE"
Write-Host "NO_ARTIFACT_FILES_WRITTEN=TRUE"
Write-Host "NO_REBUILD_PERFORMED=TRUE"
Write-Host "NO_API_ENDPOINT_CALLS=TRUE"
Write-Host "NO_EXECUTOR_CALLS=TRUE"
Write-Host "NO_SPECIALIST_CALLS=TRUE"
Write-Host "NO_DB_WRITES=TRUE"
Write-Host "PHASE_B2E_READ_ONLY_COMPLETE=TRUE" -ForegroundColor Green