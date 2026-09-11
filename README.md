
# Keycloak Auto-Init (Realm, Client, User)

Dit pakket configureert Keycloak automatisch met:
- Realm: `promati`
- Client: `api` (public, direct access grants aan,
  standard flow aan, web origins/redirects *)
- User: `john` (emailVerified=true, geen required actions)

## Gebruik
1) Plaats `docker-compose.override.yml` naast je bestaande `docker-compose.yml` in `C:i-platform`.
2) Controleer je `.env` en voeg (of wijzig) toe:

```
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=admin123
KC_BASE=http://keycloak:8080
REALM_NAME=promati
INIT_USERNAME=john
INIT_PASSWORD=Prom#t!1234
INIT_EMAIL=john@example.com
```

3) Start of herstart je stack:
```
docker compose up -d keycloak
# wacht 10-20s totdat keycloak live is
docker compose up --build init-keycloak
```
> De init-service stopt vanzelf als alles klaar is.

4) Test token:
```
curl -X POST "http://localhost:8080/realms/promati/protocol/openid-connect/token"   -H "Content-Type: application/x-www-form-urlencoded"   --data "client_id=api&grant_type=password&username=john&password=Prom#t!1234"
```

## Wat het script doet
- Wacht tot Keycloak live is (`/.well-known/openid-configuration`)
- Vraagt admin token op
- Maakt realm als die niet bestaat
- Configureert client `api` (public, standard+direct access grants ON)
- Zet web origins en redirect URIs op `*` (alleen voor lokaal testen)
- Maakt of update user `john`, zet wachtwoord en emailVerified=true
- Verwijdert alle per-user Required Actions

## Veiligheid
- Gebruik sterke wachtwoorden in `.env`
- In productie **geen** `*` origins/redirects – specificeer je eigen URLs
- Overweeg HTTPS/TLS voor Keycloak
