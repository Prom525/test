
# ChatGPT Action/Plugin bundel – Promati SQL Assistant

Deze bundel bevat alles wat je nodig hebt om ChatGPT (Actions) jouw API te laten aanroepen **zonder** handmatig een Authorization header mee te geven. We bieden een **plugin-facade** (`/plugin/...`) die lokaal draait en alleen **READ‑ONLY** SQL toelaat.

## Inhoud
- `.well-known/ai-plugin.json` – ChatGPT plugin manifest
- `.well-known/promati-openapi.yaml` – OpenAPI definitie voor Actions
- `plugin_proxy.py` – FastAPI router met `/plugin/schema` en `/plugin/sql`

## Installatie
1. **Kopieer** bestanden naar je API project (host):
   - Plaats `.well-known` map in `C:i-platformpipp\static\.well-known` of serve deze directory via je API. (Makkelijkste: maak een StaticFiles mount.)
   - Plaats `plugin_proxy.py` in `C:i-platformpippouters\plugin_proxy.py`.

2. **Publiceer de .well-known bestanden** in FastAPI (voeg toe in `main.py`):
   ```python
   from fastapi.staticfiles import StaticFiles
   import os

   app.mount(
       "/.well-known",
       StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static", ".well-known")),
       name="wellknown",
   )
   ```
   Maak de map `C:i-platformpipp\static\.well-known` aan en zet daar de twee bestanden uit deze bundel:
   - `ai-plugin.json`
   - `promati-openapi.yaml`

3. **Registreer de plugin-router** in `main.py`:
   ```python
   from .routers import plugin_proxy
   app.include_router(plugin_proxy.router)
   ```

4. **Rebuild & start**:
   ```powershell
   cd C:i-platform
   docker compose build --no-cache api
   docker compose up -d api
   ```

5. **Controleer**:
   - OpenAPI (plugin): `http://localhost:8000/.well-known/promati-openapi.yaml`
   - Manifest: `http://localhost:8000/.well-known/ai-plugin.json`
   - Endpoint test: `curl http://localhost:8000/plugin/schema`

## ChatGPT Actions – toevoegen
- In ChatGPT → **Actions** → **Create new** → kies **Import from URL** en geef op:
  - Manifest URL: `http://localhost:8000/.well-known/ai-plugin.json`
- De Actions interface leest dan automatisch je OpenAPI en toont `/plugin/sql` en `/plugin/schema`.

## Veiligheid
- Deze facade **accepteert geen Authorization** en is bedoeld voor **lokaal gebruik**. Gebruik voor productie:
  - IP filtering of VPN/Cloudflare Tunnel
  - of vervang door een flow die eerst een **Keycloak Client Credentials token** haalt en alleen requests mét geldige token accepteert (kan ik voor je maken als je wilt).

## Optioneel: Keycloak integratie
- Wil je tóch Authorization in de Actions? Dan kan de plugin ook een **client credentials** flow gebruiken. Ik kan een variant leveren die bij elke call een token ophaalt en het doorstuurt naar `/chatdb/sql`. Laat weten als je deze variant wilt.

