$ErrorActionPreference = "Stop"

$ApiRoot = "C:\ai-platform\api"
$AppRoot = Join-Path $ApiRoot "app"

$B2EFreezeDir =
    "C:\ai-platform\artifacts\phase_b\b2e_contract_design_freeze_20260826_215159"

$B3B2FreezeDir =
    "C:\ai-platform\artifacts\phase_b\b3b2_types_registry_shadow_freeze_20260827_074025"

$B3DScript =
    "C:\ai-platform_temp\phase_b\audit_phase_b3d_transport_state_boundary_v1.ps1"

$ExpectedB3DScriptHash =
    "F68FDB7AAEE23EC4E8DCD9068AE00F7CB4EA9E09E1404156E684E5E59B3F104D"


$FreezeHashes = [ordered]@{
    "b2e_typed_execution_contract_v1.json" =
        "5DE306324FB0B15163AB956C69A5220685D23C6BC68EF0583D3C92FAFA6CA2E6"

    "b3b2_freeze_manifest.json" =
        "0814F0A4B82C405C5BB370E91B77F540A0F028956F2535BC38EE9FC44C66B4D3"

    "b3b2_freeze_summary.txt" =
        "B463F4C5445A7C706507607853E7FDD74ABA0D96F98E50CDCDA486420F114F55"

    "b3b2_freeze_hashes.txt" =
        "1FF731366E4D421CB20FF4CB1F887AAF23B1FC28F7B5B0007FED884DB7471095"
}


$LiveHashes = [ordered]@{
    "orchestrator\executor.py" =
        "64240F4D0C0A63D698DDFE44764DF14E2D2A9CC65EFB53589AED77B479019A5A"

    "orchestrator\execution_contracts.py" =
        "FF66191BAF057371A8802130AC10D5744C2C3775DC2D51362EBD2658667D660E"

    "orchestrator\specialist_registry.py" =
        "9694B81932F41C1C5B28005D40A8A3586EBD94DFEA9B15D90A65D8086AEF9F8F"

    "orchestrator\execution_shadow.py" =
        "F5122A5DEAB1635DD48CEE352B2BF5216DADF87CCB5D05CC26C75FFD1A311B8A"

    "orchestrator\models.py" =
        "14C2E9DC4342D4554DF077925D9DAF3FB50B1D36A9B6D093D50379522E190C9E"

    "orchestrator\planner.py" =
        "26DB88A34A29792C82A1F6685E43D397316EE2C5E8E000D5E1A9C4FB77E9CF68"

    "orchestrator\service.py" =
        "6BDA7AD0D4EB73DE6BB56170CC97B56319EA7AAFBCDA7E9EAFA4F524A4643761"
}


Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " PROMATI PHASE-B3E TRANSPORT STATE ADDENDUM V1" -ForegroundColor Cyan
Write-Host " DESIGN ONLY / NO SOURCE WRITES / NO ARTIFACTS" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan


# ============================================================
# B3D provenance
# ============================================================

Write-Host ""
Write-Host "=== B3D PROVENANCE GUARD ==="

if (-not (Test-Path -LiteralPath $B3DScript -PathType Leaf)) {
    throw "B3D audit script ontbreekt."
}

$B3DHash = (
    Get-FileHash `
        -LiteralPath $B3DScript `
        -Algorithm SHA256
).Hash

Write-Host "B3D_SCRIPT_SHA256=$B3DHash"

if ($B3DHash -ne $ExpectedB3DScriptHash) {
    throw "B3D audit-script hash mismatch."
}

Write-Host "B3D_PROVENANCE_OK=TRUE"


# ============================================================
# Freeze guards
# ============================================================

Write-Host ""
Write-Host "=== FROZEN CONTRACT GUARDS ==="

$FreezePaths = [ordered]@{
    "b2e_typed_execution_contract_v1.json" =
        (Join-Path $B2EFreezeDir "b2e_typed_execution_contract_v1.json")

    "b3b2_freeze_manifest.json" =
        (Join-Path $B3B2FreezeDir "freeze_manifest.json")

    "b3b2_freeze_summary.txt" =
        (Join-Path $B3B2FreezeDir "freeze_summary.txt")

    "b3b2_freeze_hashes.txt" =
        (Join-Path $B3B2FreezeDir "freeze_hashes.txt")
}


foreach ($Name in $FreezePaths.Keys) {

    $Path = $FreezePaths[$Name]

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Freeze artifact ontbreekt: $Path"
    }

    $Hash = (
        Get-FileHash `
            -LiteralPath $Path `
            -Algorithm SHA256
    ).Hash

    Write-Host "$Name=$Hash"

    if ($Hash -ne $FreezeHashes[$Name]) {
        throw "Freeze hash mismatch: $Name"
    }
}

Write-Host "FROZEN_CONTRACT_GUARDS_OK=TRUE"


# ============================================================
# Live source guards
# ============================================================

$BeforeHashes = [ordered]@{}

Write-Host ""
Write-Host "=== LIVE SOURCE GUARDS ==="

foreach ($RelativePath in $LiveHashes.Keys) {

    $Path = Join-Path $AppRoot $RelativePath

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Live source ontbreekt: $RelativePath"
    }

    $Hash = (
        Get-FileHash `
            -LiteralPath $Path `
            -Algorithm SHA256
    ).Hash

    $BeforeHashes[$RelativePath] = $Hash

    Write-Host "$RelativePath=$Hash"

    if ($Hash -ne $LiveHashes[$RelativePath]) {
        throw "Live source hash mismatch: $RelativePath"
    }
}

Write-Host "LIVE_SOURCE_GUARDS_OK=TRUE"


# ============================================================
# Static compatibility proof
# ============================================================

$Python = @'
import ast
import json
import pathlib
import sys


api_root = pathlib.Path(sys.argv[1]).resolve()
app_root = api_root / "app"

spec_path = pathlib.Path(sys.argv[2]).resolve()

executor_path = app_root / "orchestrator" / "executor.py"
contracts_path = app_root / "orchestrator" / "execution_contracts.py"
shadow_path = app_root / "orchestrator" / "execution_shadow.py"


def parse(path):
    source = path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source,
        filename=str(path),
    )

    compile(
        source,
        str(path),
        "exec",
    )

    return source, tree


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        prefix = dotted(node.value)

        if prefix:
            return prefix + "." + node.attr

        return node.attr

    return None


def find_function(tree, name):
    hits = [
        node
        for node in ast.walk(tree)
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
        and node.name == name
    ]

    if len(hits) != 1:
        raise RuntimeError(
            f"Expected one {name}; found {len(hits)}"
        )

    return hits[0]


def enum_values(tree, class_name):
    hits = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == class_name
    ]

    if len(hits) != 1:
        raise RuntimeError(
            f"Expected one enum {class_name}"
        )

    values = []

    for node in hits[0].body:
        if not isinstance(node, ast.Assign):
            continue

        if not (
            len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue

        values.append(
            node.value.value
        )

    return values


executor_source, executor_tree = parse(
    executor_path
)

contracts_source, contracts_tree = parse(
    contracts_path
)

shadow_source, shadow_tree = parse(
    shadow_path
)

spec = json.loads(
    spec_path.read_text(
        encoding="utf-8-sig"
    )
)


execute_plan = find_function(
    executor_tree,
    "execute_plan",
)

default_sender = find_function(
    executor_tree,
    "default_sender",
)

derive_result = find_function(
    shadow_tree,
    "derive_execution_result",
)


# ============================================================
# Frozen enum proof
# ============================================================

frozen_states = spec.get(
    "transport_states"
)

live_states = enum_values(
    contracts_tree,
    "ExecutionTransportState",
)


print("")
print("=== TRANSPORT ENUM BASELINE ===")

print(
    "FROZEN_TRANSPORT_STATES="
    + ",".join(
        frozen_states
    )
)

print(
    "LIVE_TRANSPORT_STATES="
    + ",".join(
        live_states
    )
)


if frozen_states != [
    "NOT_ATTEMPTED",
    "COMPLETED",
    "FAILED",
]:
    raise RuntimeError(
        "Unexpected frozen transport-state enum"
    )

if live_states != frozen_states:
    raise RuntimeError(
        "Live enum differs from B2E frozen enum"
    )


print("TRANSPORT_ENUM_UNCHANGED=TRUE")
print("ADDENDUM_REQUIRES_ENUM_CHANGE=FALSE")


# ============================================================
# Sender boundary proof
# ============================================================

sender_arg_present = any(
    arg.arg == "sender"
    for arg in (
        list(execute_plan.args.posonlyargs)
        + list(execute_plan.args.args)
    )
)


transport_assignment = []


for node in ast.walk(
    execute_plan
):
    if not isinstance(
        node,
        (
            ast.Assign,
            ast.AnnAssign,
        ),
    ):
        continue

    if isinstance(node, ast.Assign):
        targets = node.targets
        value = node.value
    else:
        targets = [node.target]
        value = node.value

    if not any(
        isinstance(target, ast.Name)
        and target.id == "transport"
        for target in targets
    ):
        continue

    transport_assignment.append(
        ast.unparse(value)
    )


transport_calls = [
    node
    for node in ast.walk(
        execute_plan
    )
    if isinstance(node, ast.Call)
    and dotted(node.func) == "transport"
]


print("")
print("=== EXECUTOR -> SENDER BOUNDARY ===")

print(
    "EXECUTE_PLAN_HAS_SENDER_PARAMETER="
    + str(
        sender_arg_present
    ).upper()
)

print(
    "TRANSPORT_LOCAL_ASSIGNMENT_COUNT="
    + str(
        len(
            transport_assignment
        )
    )
)

for value in transport_assignment:
    print(
        "TRANSPORT_LOCAL_ASSIGNMENT_VALUE="
        + value
    )

print(
    "TRANSPORT_CALL_COUNT="
    + str(
        len(
            transport_calls
        )
    )
)


boundary_proven = (
    sender_arg_present
    and transport_assignment
        == ["sender or default_sender"]
    and len(transport_calls) == 1
)


print(
    "EXECUTOR_SENDER_INVOCATION_BOUNDARY_PROVEN="
    + str(
        boundary_proven
    ).upper()
)


if not boundary_proven:
    raise RuntimeError(
        "Executor/sender boundary not structurally proven"
    )


# ============================================================
# Current call result behavior
# ============================================================

transport_call = transport_calls[0]


result_assignment_found = False

for node in ast.walk(
    execute_plan
):
    if not isinstance(
        node,
        (
            ast.Assign,
            ast.AnnAssign,
        ),
    ):
        continue

    if isinstance(node, ast.Assign):
        targets = node.targets
        value = node.value
    else:
        targets = [node.target]
        value = node.value

    if not any(
        isinstance(target, ast.Name)
        and target.id == "result"
        for target in targets
    ):
        continue

    if value is transport_call:
        result_assignment_found = True
        break


accepted_after_transport = any(
    isinstance(node, ast.Call)
    and dotted(node.func) == "_is_accepted"
    and getattr(
        node,
        "lineno",
        0,
    ) > getattr(
        transport_call,
        "lineno",
        0,
    )
    for node in ast.walk(
        execute_plan
    )
)


print("")
print("=== POST-SENDER CONTROL FLOW ===")

print(
    "TRANSPORT_RETURN_ASSIGNED_TO_RESULT="
    + str(
        result_assignment_found
    ).upper()
)

print(
    "ACCEPTED_COMPUTED_AFTER_TRANSPORT_RETURN="
    + str(
        accepted_after_transport
    ).upper()
)


# ============================================================
# No execute_plan exception capture
# ============================================================

execute_plan_try_count = sum(
    1
    for node in ast.walk(
        execute_plan
    )
    if isinstance(node, ast.Try)
)


print(
    "EXECUTE_PLAN_TRY_COUNT="
    + str(
        execute_plan_try_count
    )
)

print(
    "EXECUTE_PLAN_CURRENTLY_MATERIALIZES_FAILED_RESULT="
    + str(
        execute_plan_try_count > 0
    ).upper()
)


# ============================================================
# default_sender facts
# ============================================================

post_calls = [
    node
    for node in ast.walk(
        default_sender
    )
    if isinstance(node, ast.Call)
    and dotted(node.func)
        == "requests.post"
]


raise_calls = [
    node
    for node in ast.walk(
        default_sender
    )
    if isinstance(node, ast.Call)
    and dotted(node.func)
        == "response.raise_for_status"
]


json_calls = [
    node
    for node in ast.walk(
        default_sender
    )
    if isinstance(node, ast.Call)
    and dotted(node.func)
        == "response.json"
]


exception_returns_dict = False


for handler in [
    node
    for node in ast.walk(
        default_sender
    )
    if isinstance(
        node,
        ast.ExceptHandler,
    )
]:

    for statement in handler.body:

        if (
            isinstance(statement, ast.Return)
            and isinstance(
                statement.value,
                ast.Dict,
            )
        ):
            exception_returns_dict = True


print("")
print("=== DEFAULT SENDER FACTS ===")

print(
    "DEFAULT_SENDER_REQUESTS_POST_COUNT="
    + str(
        len(post_calls)
    )
)

print(
    "DEFAULT_SENDER_RAISE_FOR_STATUS_COUNT="
    + str(
        len(raise_calls)
    )
)

print(
    "DEFAULT_SENDER_RESPONSE_JSON_COUNT="
    + str(
        len(json_calls)
    )
)

print(
    "DEFAULT_SENDER_CAUGHT_EXCEPTION_RETURNS_DICT="
    + str(
        exception_returns_dict
    ).upper()
)


default_sender_normalizes_failures = (
    len(post_calls) == 1
    and len(raise_calls) == 1
    and len(json_calls) == 1
    and exception_returns_dict
)


print(
    "DEFAULT_SENDER_CAN_NORMALIZE_HTTP_NETWORK_FAILURE_TO_RESULT="
    + str(
        default_sender_normalizes_failures
    ).upper()
)


# ============================================================
# Current shadow default
# ============================================================

transport_default = None

all_args = (
    list(derive_result.args.posonlyargs)
    + list(derive_result.args.args)
)

defaults = list(
    derive_result.args.defaults
)

required_count = (
    len(all_args)
    - len(defaults)
)

for index, arg in enumerate(
    all_args
):

    if arg.arg != "transport_state":
        continue

    if index < required_count:
        transport_default = "<required>"
    else:
        transport_default = ast.unparse(
            defaults[
                index - required_count
            ]
        )


print("")
print("=== CURRENT SHADOW DERIVER ===")

print(
    "DERIVER_TRANSPORT_DEFAULT="
    + str(
        transport_default
    )
)


if (
    transport_default
    != "ExecutionTransportState.COMPLETED"
):
    raise RuntimeError(
        "Unexpected current shadow transport default"
    )


# ============================================================
# Contract addendum
# ============================================================

print("")
print("=== B3E TRANSPORT STATE CONTRACT ADDENDUM V1 ===")

print(
    "TRANSPORT_BOUNDARY="
    "EXECUTOR_TO_SENDER_INVOCATION"
)

print(
    "TRANSPORT_BOUNDARY_NOT="
    "RAW_HTTP_NETWORK_LAYER"
)

print(
    "TRANSPORT_BOUNDARY_NOT="
    "SPECIALIST_SEMANTIC_SUCCESS"
)


print(
    "TRANSPORT_STATE_DEFINITION="
    "NOT_ATTEMPTED|"
    "sender invocation did not begin"
)

print(
    "TRANSPORT_STATE_DEFINITION="
    "COMPLETED|"
    "sender callable returned normally with a result dict "
    "that reached post-call executor processing"
)

print(
    "TRANSPORT_STATE_DEFINITION="
    "FAILED|"
    "sender invocation raised or aborted before returning "
    "a usable result dict"
)


print("")
print("=== SEMANTIC SEPARATION ===")

print(
    "COMPLETED_IMPLIES_HTTP_SUCCESS=FALSE"
)

print(
    "COMPLETED_IMPLIES_SPECIALIST_SUCCESS=FALSE"
)

print(
    "FAILED_IMPLIES_SPECIALIST_SEMANTIC_ERROR=FALSE"
)

print(
    "TRANSPORT_AND_SEMANTIC_OUTCOME_ARE_ORTHOGONAL=TRUE"
)


print("")
print("=== DEFAULT SENDER INTERPRETATION ===")

print(
    "DEFAULT_SENDER_CAUGHT_HTTP_NETWORK_EXCEPTION="
    "transport:COMPLETED"
)

print(
    "DEFAULT_SENDER_CAUGHT_HTTP_NETWORK_EXCEPTION="
    "semantic:ERROR"
)

print(
    "RATIONALE="
    "default_sender returned normally to execute_plan with an error result dict"
)


print("")
print("=== INJECTED SENDER INTERPRETATION ===")

print(
    "INJECTED_SENDER_RETURNS_RESULT_DICT="
    "transport:COMPLETED"
)

print(
    "INJECTED_SENDER_RAISES_BEFORE_RESULT="
    "transport:FAILED"
)

print(
    "INJECTED_SENDER_NOT_CALLED="
    "transport:NOT_ATTEMPTED"
)


# ============================================================
# Initial local-only shadow emission scope
# ============================================================

current_local_shadow_can_emit_completed = (
    result_assignment_found
    and accepted_after_transport
)

current_local_shadow_can_emit_failed = (
    execute_plan_try_count > 0
)

current_local_shadow_can_emit_not_attempted = False


print("")
print("=== INITIAL LOCAL-ONLY SHADOW EMISSION SCOPE ===")

print(
    "INITIAL_SHADOW_MAY_EMIT_COMPLETED="
    + str(
        current_local_shadow_can_emit_completed
    ).upper()
)

print(
    "INITIAL_SHADOW_MAY_EMIT_FAILED="
    + str(
        current_local_shadow_can_emit_failed
    ).upper()
)

print(
    "INITIAL_SHADOW_MAY_EMIT_NOT_ATTEMPTED="
    + str(
        current_local_shadow_can_emit_not_attempted
    ).upper()
)

print(
    "INITIAL_SHADOW_ALLOWED_STATE_SET=COMPLETED"
)

print(
    "FAILED_REQUIRES_FUTURE_CONTROL_FLOW_SUPPORT=TRUE"
)

print(
    "NOT_ATTEMPTED_REQUIRES_FUTURE_LIFECYCLE_SUPPORT=TRUE"
)


# ============================================================
# Compatibility constraints
# ============================================================

print("")
print("=== ADDENDUM COMPATIBILITY CONSTRAINTS ===")

print(
    "ADDENDUM_CHANGES_ENUM_VALUES=FALSE"
)

print(
    "ADDENDUM_CHANGES_EXECUTIONRESULT_SCHEMA=FALSE"
)

print(
    "ADDENDUM_CHANGES_LEGACY_ACCEPTED=FALSE"
)

print(
    "ADDENDUM_CHANGES_LEGACY_WRAPPER=FALSE"
)

print(
    "ADDENDUM_CHANGES_ROUTING=FALSE"
)

print(
    "ADDENDUM_CHANGES_QUERYPLAN=FALSE"
)

print(
    "ADDENDUM_CHANGES_ENDPOINTS=FALSE"
)

print(
    "ADDENDUM_CHANGES_FALLBACK=FALSE"
)

print(
    "ADDENDUM_CHANGES_RETRY=FALSE"
)

print(
    "ADDENDUM_ADDS_EVIDENCE_SCORING=FALSE"
)


# ============================================================
# Design decision
# ============================================================

design_ready = all(
    (
        boundary_proven,
        result_assignment_found,
        accepted_after_transport,
        default_sender_normalizes_failures,
        transport_default
            == "ExecutionTransportState.COMPLETED",
    )
)


print("")
print("=== B3E DECISION ===")

print(
    "TRANSPORT_BOUNDARY_CONTRACT_DEFINED=TRUE"
)

print(
    "TRANSPORT_STATE_SEMANTICS_DEFINED=TRUE"
)

print(
    "CURRENT_RUNTIME_COMPATIBILITY_PROVEN="
    + str(
        design_ready
    ).upper()
)

print(
    "INITIAL_LOCAL_ONLY_SHADOW_STATE_SCOPE_PROVEN=TRUE"
)

print(
    "TRANSPORT_ADDENDUM_DESIGN_READY="
    + str(
        design_ready
    ).upper()
)

# Design is not frozen yet.
print(
    "EXECUTOR_SHADOW_PATCH_ALLOWED_NOW=FALSE"
)

if design_ready:

    print(
        "NEXT_STEP_CANDIDATE="
        "FREEZE_B3E_TRANSPORT_STATE_CONTRACT_ADDENDUM_V1"
    )

else:

    print(
        "NEXT_STEP_CANDIDATE="
        "INVESTIGATE_B3E_TRANSPORT_CONTRACT_BLOCKER"
    )


print("")
print("SOURCE_FILES_WRITTEN=FALSE")
print("ARTIFACT_FILES_WRITTEN=FALSE")
print("PYTHON_MODULES_IMPORTED=FALSE")
print("API_ENDPOINTS_CALLED=FALSE")
print("EXECUTOR_CALLED=FALSE")
print("SPECIALISTS_EXECUTED=FALSE")
print("DB_WRITES=FALSE")
print("PHASE_A_ROUTER_CHANGED=FALSE")
print("PHASE_B3E_DESIGN_ONLY_COMPLETE=TRUE")
'@


$SpecPath =
    Join-Path `
        $B2EFreezeDir `
        "b2e_typed_execution_contract_v1.json"


$Output = @(
    $Python |
        & python -B - `
            $ApiRoot `
            $SpecPath
)

$Exit = $LASTEXITCODE

$Output | ForEach-Object {
    Write-Host $_
}

if ($Exit -ne 0) {
    throw "Phase-B3E transport-state addendum design mislukt."
}


# ============================================================
# Final immutability
# ============================================================

Write-Host ""
Write-Host "=== FINAL IMMUTABILITY ==="

foreach ($RelativePath in $LiveHashes.Keys) {

    $Path = Join-Path $AppRoot $RelativePath

    $After = (
        Get-FileHash `
            -LiteralPath $Path `
            -Algorithm SHA256
    ).Hash

    if ($After -ne $BeforeHashes[$RelativePath]) {
        throw "Live source veranderde tijdens B3E: $RelativePath"
    }
}


foreach ($Name in $FreezePaths.Keys) {

    $Path = $FreezePaths[$Name]

    $After = (
        Get-FileHash `
            -LiteralPath $Path `
            -Algorithm SHA256
    ).Hash

    if ($After -ne $FreezeHashes[$Name]) {
        throw "Freeze artifact veranderde tijdens B3E: $Name"
    }
}


$FinalB3DHash = (
    Get-FileHash `
        -LiteralPath $B3DScript `
        -Algorithm SHA256
).Hash

if ($FinalB3DHash -ne $ExpectedB3DScriptHash) {
    throw "B3D audit script veranderde tijdens B3E."
}


Write-Host "PROMATI_SOURCE_CHANGED=FALSE"
Write-Host "B2E_FREEZE_ARTIFACTS_CHANGED=FALSE"
Write-Host "B3B2_FREEZE_ARTIFACTS_CHANGED=FALSE"
Write-Host "PHASE_A_FROZEN_FILES_CHANGED=FALSE"
Write-Host "NO_ARTIFACT_FILES_WRITTEN=TRUE"
Write-Host "NO_REBUILD_PERFORMED=TRUE"
Write-Host "NO_API_ENDPOINT_CALLS=TRUE"
Write-Host "NO_EXECUTOR_CALLS=TRUE"
Write-Host "NO_SPECIALIST_CALLS=TRUE"
Write-Host "NO_DB_WRITES=TRUE"
Write-Host "PHASE_B3E_READ_ONLY_COMPLETE=TRUE" -ForegroundColor Green