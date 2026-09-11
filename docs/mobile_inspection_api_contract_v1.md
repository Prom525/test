# PROMATI Mobile Inspection API Contract v1

Status: draft-v1  
Datum: 2026-07-07  
Doel: API-contract voor planner, mobiele inspectie-app, validatie en promotie naar de bestaande inspectiedatabase.

---

## 1. Hoofdregel

Mobiele inspecties schrijven nooit direct naar:

- `sb_inspections_v0`
- `sb_inspection_items_v0`

Mobiele inspecties gaan altijd via:

1. planner maakt inspectieplan
2. mobiele app downloadt inspectieplan
3. mobiele app uploadt submission naar mobile staging
4. planner valideert
5. backend promoveert naar canonieke inspectietabellen

---

## 2. Normale statusflow

### Inspectieplan

```text
DRAFT
→ PUBLISHED
→ DOWNLOADED
→ SUBMITTED
→ APPROVED
→ PROMOTED
```

### Planregel

```text
PLANNED
→ SUBMITTED
→ APPROVED
→ PROMOTED
```

### Mobiele submission

```text
WAITING_FOR_PLANNER_VALIDATION
→ APPROVED
→ PROMOTED_TO_CANONICAL_DB
```

---

## 3. Scope types

Geldige `scope_type` waarden:

- `BAND`
- `BAND_SIDE_COMPONENT`
- `SCRAPER_POSITION`
- `TRANSFER_POINT`
- `PERFORMANCE_MEASUREMENT`
- `ENVIRONMENT_MEASUREMENT`
- `LOCATION_OBSERVATION`

Voor v1 gebruiken we vooral:

```text
SCRAPER_POSITION
```

---

## 4. Planner API

Base prefix:

```text
/planner
```

### 4.1 Inspectieplan maken

```http
POST /planner/inspection-plans
```

Request voorbeeld:

```json
{
  "plan_date": "2026-07-08",
  "customer_id": "TATA_STEEL",
  "customer_name": "TATA Steel",
  "site_id": "IJMUIDEN",
  "site_name": "IJmuiden",
  "basisunit_code": "GSL",
  "sub_area_code": "MV2",
  "assigned_user_id": "monteur-test",
  "assigned_user_name": "Test Monteur",
  "created_by": "planner-test",
  "remarks": "Inspectieplan voorbeeld",
  "items": [
    {
      "sort_order": 1,
      "scope_type": "SCRAPER_POSITION",
      "customer_id": "TATA_STEEL",
      "site_id": "IJMUIDEN",
      "basisunit_code": "GSL",
      "sub_area_code": "MV2",
      "lijn_code": "MV2",
      "band_code": "E950",
      "scraper_position_id": "E950_SEC_01",
      "scraper_position": "Secundair",
      "scraper_role": "SECUNDAIR",
      "scraper_type": "R 1200-1050 SP/M3",
      "scraper_family": "R",
      "previous_meshoogte_mm": 5.0,
      "previous_condition_code": "OK",
      "required_measurements": [
        {
          "type": "MESHOOGTE",
          "unit": "mm",
          "required": true
        }
      ],
      "required_photos": false,
      "priority": 1,
      "planner_note": "Controleer meshoogte en staat van schraper"
    }
  ]
}
```

Response voorbeeld:

```json
{
  "status": "ok",
  "plan_id": "uuid",
  "plan_status": "DRAFT",
  "item_count": 1
}
```

Regels:

- `items` mag niet leeg zijn.
- Nieuw plan start als `DRAFT`.
- Planregels starten als `PLANNED`.

### 4.2 Inspectieplannen lijst

```http
GET /planner/inspection-plans
```

Optionele query:

```text
limit=50
```

Response voorbeeld:

```json
{
  "status": "ok",
  "count": 1,
  "results": []
}
```

### 4.3 Inspectieplan detail

```http
GET /planner/inspection-plans/{plan_id}
```

Response voorbeeld:

```json
{
  "plan": {},
  "items": []
}
```

### 4.4 Inspectieplan publiceren

```http
POST /planner/inspection-plans/{plan_id}/publish
```

Response voorbeeld:

```json
{
  "status": "ok",
  "plan_id": "uuid",
  "plan_status": "PUBLISHED",
  "published_at": "2026-07-07T15:01:11Z",
  "item_count": 1
}
```

Regels:

- Alleen plannen met status `DRAFT` of `READY_FOR_REVIEW` kunnen gepubliceerd worden.
- Plan moet minimaal 1 planregel hebben.

---

## 5. Mobile download API

Base prefix:

```text
/planner/mobile-download
```

### 5.1 Gepubliceerde plannen ophalen voor monteur

```http
GET /planner/mobile-download/inspection-plans?assigned_user_id={user_id}
```

Voorbeeld:

```http
GET /planner/mobile-download/inspection-plans?assigned_user_id=monteur-test
```

Response voorbeeld:

```json
{
  "status": "ok",
  "count": 1,
  "results": [
    {
      "plan_id": "uuid",
      "plan_date": "2026-07-08",
      "assigned_user_id": "monteur-test",
      "status": "PUBLISHED",
      "item_count": 1
    }
  ]
}
```

Zichtbare planstatussen voor mobiele app:

- `PUBLISHED`
- `DOWNLOADED`
- `IN_PROGRESS`
- `PARTLY_SUBMITTED`
- `SUBMITTED`

### 5.2 Volledig plan downloaden

```http
GET /planner/mobile-download/inspection-plans/{plan_id}
```

Response voorbeeld:

```json
{
  "status": "ok",
  "plan": {},
  "items": [],
  "item_count": 1,
  "download_mode": "offline_cache_ready"
}
```

Regels:

- App krijgt planheader en alle planregels.
- App bewaart dit lokaal voor offline gebruik.

### 5.3 Plan markeren als gedownload

```http
POST /planner/mobile-download/inspection-plans/{plan_id}/downloaded
```

Request voorbeeld:

```json
{
  "user_id": "monteur-test",
  "device_id": "test-device-001"
}
```

Response voorbeeld:

```json
{
  "status": "ok",
  "plan_id": "uuid",
  "plan_status": "DOWNLOADED",
  "user_id": "monteur-test",
  "device_id": "test-device-001"
}
```

Regels:

- Alleen toegewezen gebruiker mag download melden.
- `PUBLISHED` wordt `DOWNLOADED`.
- Als plan al verder is, blijft status gelijk.

---

## 6. Mobile upload API

Base prefix:

```text
/mobile
```

### 6.1 Mobiele submission uploaden

```http
POST /mobile/inspection-submissions
```

Request voorbeeld:

```json
{
  "client_submission_id": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
  "plan_id": "uuid",
  "user_id": "monteur-test",
  "user_name": "Test Monteur",
  "device_id": "test-device-001",
  "customer_id": "TATA_STEEL",
  "customer_name": "TATA Steel",
  "site_id": "IJMUIDEN",
  "site_name": "IJmuiden",
  "basisunit_code": "GSL",
  "sub_area_code": "MV2",
  "offline_started_at": "2026-07-08T08:00:00Z",
  "offline_completed_at": "2026-07-08T08:20:00Z",
  "raw_payload": {
    "source": "mobile_app"
  },
  "items": [
    {
      "client_item_id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
      "plan_item_id": "uuid",
      "scope_type": "SCRAPER_POSITION",
      "lijn_code": "MV2",
      "band_code": "E950",
      "scraper_position_id": "E950_SEC_01",
      "scraper_position": "Secundair",
      "scraper_role": "SECUNDAIR",
      "scraper_type": "R 1200-1050 SP/M3",
      "scraper_family": "R",
      "measurement_type": "MESHOOGTE",
      "meshoogte_mm": 4.2,
      "condition_code": "OK",
      "status": "OK",
      "severity": "LOW",
      "opmerking": "Mobiele inspectie ingevuld",
      "action_required": false,
      "replaced": false,
      "asset_match_status": "MATCHED",
      "offline_created_at": "2026-07-08T08:15:00Z"
    }
  ]
}
```

Response voorbeeld eerste upload:

```json
{
  "status": "ok",
  "submission_id": "uuid",
  "validation_status": "WAITING_FOR_PLANNER_VALIDATION",
  "item_count": 1,
  "validation_issue_count": 0,
  "ready_for_planner_approval": true,
  "write_target": "mobile_staging_only"
}
```

Response voorbeeld dubbele upload:

```json
{
  "status": "ok",
  "idempotent": true,
  "message": "Submission was al ontvangen. Bestaande submission teruggegeven.",
  "submission_id": "uuid",
  "validation_status": "WAITING_FOR_PLANNER_VALIDATION",
  "item_count": 1,
  "validation_issue_count": 0,
  "ready_for_planner_approval": true,
  "write_target": "mobile_staging_only"
}
```

Regels:

- `client_submission_id` is uniek.
- Dubbele upload is idempotent.
- Submission moet minimaal 1 item hebben.
- Bij gekoppeld `plan_id` + `plan_item_id` wordt planregel `SUBMITTED`.
- Als alle planregels submitted zijn, wordt plan `SUBMITTED`.
- Er wordt niet naar `sb_inspections_v0` geschreven.

### 6.2 Mobiele submission detail

```http
GET /mobile/inspection-submissions/{submission_id}
```

Response voorbeeld:

```json
{
  "submission": {},
  "items": [],
  "validation_issues": []
}
```

### 6.3 Mobiele validatiequeue

```http
GET /mobile/validation-queue
```

Response voorbeeld:

```json
{
  "status": "ok",
  "count": 1,
  "results": []
}
```

---

## 7. Planner validatie API

Base prefix:

```text
/validation
```

### 7.1 Validatiewachtrij

```http
GET /validation/queue
```

Response voorbeeld:

```json
{
  "status": "ok",
  "count": 1,
  "results": [
    {
      "submission_id": "uuid",
      "validation_status": "WAITING_FOR_PLANNER_VALIDATION",
      "item_count": 1,
      "validation_issue_count": 0,
      "ready_for_planner_approval": true
    }
  ]
}
```

### 7.2 Validatie detail

```http
GET /validation/submissions/{submission_id}
```

Response voorbeeld:

```json
{
  "submission": {},
  "items": [],
  "validation_issues": []
}
```

### 7.3 Validatie starten

```http
POST /validation/submissions/{submission_id}/start
```

Request voorbeeld:

```json
{
  "validated_by": "planner-test",
  "note": "Validatie gestart"
}
```

Response voorbeeld:

```json
{
  "status": "ok",
  "submission_id": "uuid",
  "validation_status": "VALIDATION_IN_PROGRESS"
}
```

### 7.4 Submission goedkeuren

```http
POST /validation/submissions/{submission_id}/approve
```

Request voorbeeld:

```json
{
  "validated_by": "planner-test",
  "note": "Goedgekeurd"
}
```

Response voorbeeld:

```json
{
  "status": "ok",
  "submission_id": "uuid",
  "validation_status": "APPROVED",
  "write_target": "mobile_staging_only",
  "next_step": "ready_for_promotion_later"
}
```

Response dubbele approve:

```json
{
  "status": "already_approved",
  "submission_id": "uuid",
  "validation_status": "APPROVED",
  "write_target": "mobile_staging_only",
  "next_step": "ready_for_promotion_later"
}
```

Geblokkeerd na promotie:

```http
400 Bad Request
```

```json
{
  "detail": "Submission is al gepromoveerd en kan niet opnieuw worden goedgekeurd."
}
```

Regels:

- Alleen submissions zonder validatieproblemen kunnen worden goedgekeurd.
- Gekoppelde planregels worden `APPROVED`.
- Als alle planregels approved/promoted zijn, wordt plan `APPROVED`.
- Goedkeuren schrijft niet naar canonieke inspectietabellen.

### 7.5 Submission afwijzen

```http
POST /validation/submissions/{submission_id}/reject
```

Request voorbeeld:

```json
{
  "validated_by": "planner-test",
  "note": "Afgekeurd wegens ontbrekende gegevens"
}
```

Response voorbeeld:

```json
{
  "status": "ok",
  "submission_id": "uuid",
  "validation_status": "REJECTED"
}
```

### 7.6 Correctie vragen

```http
POST /validation/submissions/{submission_id}/needs-correction
```

Request voorbeeld:

```json
{
  "validated_by": "planner-test",
  "note": "Foto ontbreekt"
}
```

Response voorbeeld:

```json
{
  "status": "ok",
  "submission_id": "uuid",
  "validation_status": "NEEDS_CORRECTION"
}
```

### 7.7 Promoveren naar canonieke inspectiedatabase

```http
POST /validation/submissions/{submission_id}/promote
```

Request voorbeeld:

```json
{
  "validated_by": "planner-test",
  "note": "Promotie naar canonieke inspectietabellen"
}
```

Response voorbeeld:

```json
{
  "status": "ok",
  "submission_id": "uuid",
  "canonical_inspection_key": "MOBILE|uuid",
  "header_inserted_count": 1,
  "item_inserted_count": 1,
  "canonical_item_count": 1,
  "validation_status": "PROMOTED_TO_CANONICAL_DB",
  "write_target": "canonical_db"
}
```

Response dubbele promotie:

```json
{
  "status": "already_promoted",
  "submission_id": "uuid",
  "canonical_inspection_key": "MOBILE|uuid",
  "write_target": "canonical_db"
}
```

Regels:

- Alleen `APPROVED` submissions kunnen gepromoveerd worden.
- Promotie schrijft naar `sb_inspections_v0` en `sb_inspection_items_v0`.
- `inspection_key` krijgt formaat `MOBILE|{submission_id}`.
- `source_file` krijgt formaat `MOBILE:{submission_id}`.
- `sheet` is `MOBILE_INSPECTION`.
- Planregel wordt `PROMOTED`.
- Plan wordt `PROMOTED` als alle regels promoted zijn.

---

## 8. Validatieproblemen

View:

```text
vw_mobile_submission_validation_issues
```

Issue codes v1:

- `CUSTOMER_MISSING`
- `SITE_MISSING`
- `INSPECTION_DATE_MISSING`
- `LIJN_CODE_MISSING`
- `BAND_CODE_MISSING`
- `SCRAPER_POSITION_MISSING`
- `MESHOOGTE_MISSING`
- `ASSET_PENDING_MAPPING`
- `EMPTY_ITEM`

Queue view:

```text
vw_mobile_validation_queue
```

Belangrijke velden:

- `item_count`
- `validation_issue_count`
- `ready_for_planner_approval`

Een submission mag alleen approved worden als:

```text
item_count > 0
validation_issue_count = 0
ready_for_planner_approval = true
```

---

## 9. Idempotency regels

### 9.1 Mobiele upload

Unieke sleutel:

```text
client_submission_id
```

Bij dubbele upload:

- geen extra submission
- geen extra items
- bestaande submission wordt teruggegeven

### 9.2 Mobiele items

Unieke sleutel:

```text
client_item_id
```

Bij dubbele item-upload:

- item wordt niet opnieuw toegevoegd

### 9.3 Canonieke promotie

Canonieke header uniek op:

```text
inspection_key
```

Canonieke items uniek op:

```text
inspection_key + section_idx + row_nr
```

Bij dubbele promote:

- geen extra header
- geen extra items
- response `already_promoted`

---

## 10. Mapping naar canonieke inspectietabellen

### 10.1 `sb_inspections_v0`

| Canonieke kolom | Waarde |
|---|---|
| `inspection_key` | `MOBILE\|{submission_id}` |
| `lijn_code` | eerste item `lijn_code`, anders `sub_area_code`, anders `basisunit_code` |
| `source_file` | `MOBILE:{submission_id}` |
| `sheet` | `MOBILE_INSPECTION` |
| `sheet_kind` | `MOBILE` |
| `inspected_on` | `offline_completed_at`, anders `offline_started_at`, anders `submitted_at` |
| `inspected_on_source` | `mobile_inspection_submissions` |
| `performed_by` | `user_name`, anders `user_id` |
| `title` | mobiele inspectie + site/sub_area |
| `row_count` | aantal mobiele items |
| `sheet_norm` | `MOBILE_INSPECTION` |
| `customer_code` | `customer_id` |
| `site_code` | `site_id` |

### 10.2 `sb_inspection_items_v0`

| Canonieke kolom | Waarde |
|---|---|
| `inspection_key` | `MOBILE\|{submission_id}` |
| `lijn_code` | item `lijn_code` |
| `source_file` | `MOBILE:{submission_id}` |
| `sheet` | `MOBILE_INSPECTION` |
| `section_idx` | `1` |
| `row_nr` | volgnummer per item |
| `locatie` | `band_code`, anders `scraper_position_id`, anders `scraper_position` |
| `merk_type` | `scraper_type` |
| `vervangen` | `replaced` |
| `row_json` | volledige mobiele itemcontext |
| `customer_code` | `customer_id` |
| `site_code` | `site_id` |

In `row_json` wordt voor bestaande meshoogte-views ook gezet:

```text
Unnamed: 8 = meshoogte_mm
Klantgegevens  = opmerking
```

---

## 11. Open punten na v1

Nog niet inbegrepen in v1:

- foto-upload naar MinIO
- PDF-generatie
- NFC-tags
- asset masterdata download
- volledige 5 jaar offline historie
- frontend planner-schermen
- Flutter app
- gebruikersauthenticatie/autorisatie per rol
- automatische rapportage na promotie

---

## 12. Minimale testflow

1. `POST /planner/inspection-plans`
2. `POST /planner/inspection-plans/{plan_id}/publish`
3. `POST /planner/mobile-download/inspection-plans/{plan_id}/downloaded`
4. `POST /mobile/inspection-submissions`
5. `POST /mobile/inspection-submissions` opnieuw met dezelfde `client_submission_id`
6. `POST /validation/submissions/{submission_id}/approve`
7. `POST /validation/submissions/{submission_id}/approve` opnieuw
8. `POST /validation/submissions/{submission_id}/promote`
9. `POST /validation/submissions/{submission_id}/promote` opnieuw
10. `POST /validation/submissions/{submission_id}/approve` na promotie moet `400` geven