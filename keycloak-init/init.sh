
#!/bin/sh
set -euo pipefail

KC_BASE=${KC_BASE:-http://keycloak:8080}
REALM_NAME=${REALM_NAME:-promati}
ADMIN=${KEYCLOAK_ADMIN:-admin}
ADMIN_PW=${KEYCLOAK_ADMIN_PASSWORD:-admin123}
INIT_USERNAME=${INIT_USERNAME:-john}
INIT_PASSWORD=${INIT_PASSWORD:-Prom#t!1234}
INIT_EMAIL=${INIT_EMAIL:-john@example.com}

log(){ echo "[init-keycloak] $1"; }

# helper om curl response + status te loggen
req() {
  # usage: req METHOD URL JSON_BODY(optional)
  METHOD="$1"; URL="$2"; BODY="${3-}"
  if [ -n "$BODY" ]; then
    RESP=$(curl -sS -o /tmp/resp.out -w "%{http_code}" -X "$METHOD" \
      -H "Authorization: Bearer $ADMIN_TOKEN" \
      -H "Content-Type: application/json" \
      "$URL" -d "$BODY")
  else
    RESP=$(curl -sS -o /tmp/resp.out -w "%{http_code}" -X "$METHOD" \
      -H "Authorization: Bearer $ADMIN_TOKEN" \
      "$URL")
  fi
  CODE="$RESP"
  echo "[init-keycloak] ${METHOD} ${URL} -> ${CODE}"
  if [ "$CODE" -ge 400 ]; then
    echo "[init-keycloak] Response body:"
    cat /tmp/resp.out || true
    exit 1
  fi
  cat /tmp/resp.out
}

# 1) Wachten tot Keycloak klaar is
until curl -sf "${KC_BASE}/realms/master/.well-known/openid-configuration" >/dev/null; do
  log "Wachten op Keycloak..."
  sleep 3
done
log "Keycloak bereikbaar: ${KC_BASE}"

# 2) Admin token ophalen
ADMIN_TOKEN=$(curl -sS -X POST "${KC_BASE}/realms/master/protocol/openid-connect/token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data "client_id=admin-cli&grant_type=password&username=${ADMIN}&password=${ADMIN_PW}" \
  | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')

if [ -z "$ADMIN_TOKEN" ]; then
  log "Kon geen admin token verkrijgen; check KEYCLOAK_ADMIN(_PASSWORD) en of je kunt inloggen op de Admin Console"
  exit 1
fi

# 3) Realm maken indien nodig
# GET realm
REALM_GET_CODE=$(curl -sS -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $ADMIN_TOKEN" "${KC_BASE}/admin/realms/${REALM_NAME}")
if [ "$REALM_GET_CODE" = "200" ]; then
  log "Realm ${REALM_NAME} bestaat al"
else
  log "Maak realm ${REALM_NAME}"
  req POST "${KC_BASE}/admin/realms" "$(cat <<JSON
{
  "realm": "${REALM_NAME}",
  "enabled": true
}
JSON
)"
fi

# 4) Client 'api' aanmaken of bijwerken
CLIENTS_JSON=$(req GET "${KC_BASE}/admin/realms/${REALM_NAME}/clients?clientId=api")
CID=$(echo "$CLIENTS_JSON" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p' | head -n1)
if [ -n "$CID" ]; then
  log "Client api bestaat (id=${CID}), bijwerken"
  req PUT "${KC_BASE}/admin/realms/${REALM_NAME}/clients/${CID}" "$(cat <<JSON
{
  "clientId": "api",
  "publicClient": true,
  "standardFlowEnabled": true,
  "directAccessGrantsEnabled": true,
  "redirectUris": ["*"],
  "webOrigins": ["*"]
}
JSON
)"
else
  log "Maak client api"
  req POST "${KC_BASE}/admin/realms/${REALM_NAME}/clients" "$(cat <<JSON
{
  "clientId": "api",
  "publicClient": true,
  "standardFlowEnabled": true,
  "directAccessGrantsEnabled": true,
  "redirectUris": ["*"],
  "webOrigins": ["*"]
}
JSON
)"
fi

# 5) User 'john' aanmaken of bijwerken
USERS_JSON=$(req GET "${KC_BASE}/admin/realms/${REALM_NAME}/users?username=${INIT_USERNAME}")
UID=$(echo "$USERS_JSON" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p' | head -n1)
if [ -n "$UID" ]; then
  log "User ${INIT_USERNAME} bestaat (id=${UID}), bijwerken"
  req PUT "${KC_BASE}/admin/realms/${REALM_NAME}/users/${UID}" "$(cat <<JSON
{
  "email": "${INIT_EMAIL}",
  "emailVerified": true,
  "enabled": true,
  "requiredActions": []
}
JSON
)"
else
  log "Maak user ${INIT_USERNAME}"
  req POST "${KC_BASE}/admin/realms/${REALM_NAME}/users" "$(cat <<JSON
{
  "username": "${INIT_USERNAME}",
  "email": "${INIT_EMAIL}",
  "emailVerified": true,
  "enabled": true,
  "requiredActions": []
}
JSON
)"
  # opnieuw lookup voor UID
  USERS_JSON=$(req GET "${KC_BASE}/admin/realms/${REALM_NAME}/users?username=${INIT_USERNAME}")
  UID=$(echo "$USERS_JSON" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p' | head -n1)
fi

# 6) Wachtwoord zetten (non-temporary)
log "Stel wachtwoord in voor ${INIT_USERNAME}"
req PUT "${KC_BASE}/admin/realms/${REALM_NAME}/users/${UID}/reset-password" "$(cat <<JSON
{
  "type": "password",
  "temporary": false,
  "value": "${INIT_PASSWORD}"
}
JSON
)"

log "Keycloak init voltooid"

