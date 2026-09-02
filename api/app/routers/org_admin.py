from __future__ import annotations

import secrets
import html
from typing import Any
import json
import requests
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text

from app.db import engine
from app.config import settings

security = HTTPBasic()

def api_base_url() -> str:
    return settings.PROMATI_API_BASE_URL.rstrip("/")

def require_org_admin_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    expected_user = settings.ORG_ADMIN_USER
    expected_password = settings.ORG_ADMIN_PASSWORD

    if not expected_user or not expected_password:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ORG_ADMIN_USER en ORG_ADMIN_PASSWORD zijn niet ingesteld.",
        )

    username_ok = secrets.compare_digest(credentials.username, expected_user)
    password_ok = secrets.compare_digest(credentials.password, expected_password)

    if not username_ok or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ongeldige gebruikersnaam of wachtwoord.",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username

router = APIRouter(
    prefix="/org-admin",
    tags=["org-admin"],
    dependencies=[Depends(require_org_admin_auth)],
)


def fetch_all(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    with engine.begin() as conn:
        rows = conn.execute(text(sql), params or {}).mappings().all()
    return [dict(r) for r in rows]

def get_firmas() -> list[dict]:
    return fetch_all("""
        SELECT firma_naam
        FROM org_firmas
        WHERE actief = TRUE
        ORDER BY firma_naam
    """)


def get_locaties() -> list[dict]:
    return fetch_all("""
        SELECT firma_naam, locatie
        FROM org_locaties
        WHERE actief = TRUE
        ORDER BY firma_naam, locatie
    """)


def select_options_firmas(selected: str | None = None, include_empty: bool = False) -> str:
    firmas = get_firmas()
    html = ""

    if include_empty:
        html += '<option value="">-- geen / alle firma’s --</option>'

    for f in firmas:
        naam = f.get("firma_naam") or ""
        sel = "selected" if selected == naam else ""
        html += f'<option value="{naam}" {sel}>{naam}</option>'

    return html


def select_options_locaties(selected: str | None = None, include_empty: bool = False) -> str:
    locaties = get_locaties()
    html = ""

    if include_empty:
        html += '<option value="">-- geen / alle locaties --</option>'

    for l in locaties:
        firma = l.get("firma_naam") or ""
        locatie = l.get("locatie") or ""
        value = locatie
        label = f"{firma} - {locatie}"
        sel = "selected" if selected == locatie else ""
        html += f'<option value="{value}" {sel}>{label}</option>'

    return html


def execute(sql: str, params: dict[str, Any] | None = None):
    with engine.begin() as conn:
        conn.execute(text(sql), params or {})


def page(title: str, body: str) -> HTMLResponse:
    html = f"""
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 30px;
                background: #f7f8fa;
                color: #172033;
            }}
            nav a {{
                margin-right: 15px;
                color: #0b5cab;
                text-decoration: none;
                font-weight: bold;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                background: white;
                margin-top: 20px;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 8px;
                vertical-align: top;
            }}
            th {{
                background: #eef2f7;
                text-align: left;
            }}
            input, select, textarea {{
                width: 100%;
                padding: 7px;
                margin: 3px 0 10px 0;
                box-sizing: border-box;
            }}
            button {{
                padding: 8px 14px;
                background: #0b5cab;
                color: white;
                border: 0;
                cursor: pointer;
            }}
            .card {{
                background: white;
                padding: 18px;
                border: 1px solid #ddd;
                margin-top: 20px;
            }}
            .small {{
                color: #666;
                font-size: 13px;
            }}
        </style>
    </head>
    <body>
        <nav>
            <a href="/org-admin">Home</a>
            <a href="/org-admin/personen">Personen</a>
            <a href="/org-admin/taken">Taken</a>
            <a href="/org-admin/firmas-locaties">Firma's & locaties</a>
            <a href="/org-admin/externe-contacten">Externe contacten</a>
            <a href="/org-admin/routering">Routering</a>
            <a href="/org-admin/functies">Functies</a>
            <a href="/org-admin/rag-docs">RAG documenten</a>
            <a href="/org-admin/test">Test</a>
        </nav>
        <h1>{title}</h1>
        {body}
    </body>
    </html>
    """
    return HTMLResponse(html)


def get_taken() -> list[dict]:
    return fetch_all("""
        SELECT taak_code, taak_naam, categorie
        FROM org_taken
        WHERE actief = TRUE
        ORDER BY categorie, taak_naam
    """)


def get_personen() -> list[dict]:
    return fetch_all("""
        SELECT person_id, weergavenaam, locatie, afdeling
        FROM org_personen
        WHERE actief = TRUE
        ORDER BY weergavenaam
    """)


def get_externe_contacten() -> list[dict]:
    return fetch_all("""
        SELECT extern_contact_id, naam, type
        FROM org_externe_contacten
        WHERE actief = TRUE
        ORDER BY naam
    """)


@router.get("", response_class=HTMLResponse)
def org_admin_home():
    return page(
        "Interne hulp & vraagroutering",
        """
        <div class="card">
            <p>Beheer hier personen, taken, externe contacten en routeringen.</p>
            <p class="small">Gebruik de testpagina om te controleren welk antwoord PromatiGPT krijgt.</p>
        </div>
        """
    )


def select_options_taken(selected: str | None = None) -> str:
    rows = get_taken()
    html = ""

    for r in rows:
        code = r.get("taak_code") or ""
        naam = r.get("taak_naam") or code
        categorie = r.get("categorie") or ""
        label = f"{categorie} - {naam} ({code})" if categorie else f"{naam} ({code})"
        sel = "selected" if selected == code else ""
        html += f'<option value="{code}" {sel}>{label}</option>'

    return html


def select_options_personen(selected: int | str | None = None, include_empty: bool = True) -> str:
    rows = get_personen()
    selected_str = str(selected) if selected is not None else ""
    html = ""

    if include_empty:
        html += '<option value="">-- geen persoon --</option>'

    for r in rows:
        person_id = r.get("person_id")
        naam = r.get("weergavenaam") or f"Persoon {person_id}"
        locatie = r.get("locatie") or ""
        afdeling = r.get("afdeling") or ""
        extra = " / ".join([x for x in [locatie, afdeling] if x])
        label = f"{naam} ({extra})" if extra else naam
        sel = "selected" if str(person_id) == selected_str else ""
        html += f'<option value="{person_id}" {sel}>{label}</option>'

    return html

def select_options_functies(selected: str | None = None, include_empty: bool = True) -> str:
    rows = fetch_all("""
        SELECT functie_code, functie_naam, categorie
        FROM org_functies
        WHERE actief = TRUE
        ORDER BY categorie, functie_naam
    """)

    html_out = ""

    if include_empty:
        html_out += '<option value="">-- kies functie --</option>'

    for r in rows:
        code = r.get("functie_code") or ""
        naam = r.get("functie_naam") or code
        categorie = r.get("categorie") or ""
        label = f"{categorie} - {naam} ({code})" if categorie else f"{naam} ({code})"
        sel = "selected" if selected == code else ""
        html_out += f'<option value="{safe_html(code)}" {sel}>{safe_html(label)}</option>'

    return html_out

def select_options_externe_contacten(selected: int | str | None = None, include_empty: bool = True) -> str:
    rows = get_externe_contacten()
    selected_str = str(selected) if selected is not None else ""
    html = ""

    if include_empty:
        html += '<option value="">-- geen extern contact --</option>'

    for r in rows:
        contact_id = r.get("extern_contact_id")
        naam = r.get("naam") or f"Extern contact {contact_id}"
        type_ = r.get("type") or ""
        label = f"{naam} ({type_})" if type_ else naam
        sel = "selected" if str(contact_id) == selected_str else ""
        html += f'<option value="{contact_id}" {sel}>{label}</option>'

    return html

@router.get("/externe-contacten", response_class=HTMLResponse)
def externe_contacten_page():
    rows = fetch_all("""
        SELECT *
        FROM org_externe_contacten
        ORDER BY naam
    """)

    table_rows = ""
    for r in rows:
        actief = "ja" if r.get("actief") else "nee"
        table_rows += f"""
        <tr>
            <td>{r.get("extern_contact_id")}</td>
            <td>{r.get("naam") or ""}</td>
            <td>{r.get("type") or ""}</td>
            <td>{r.get("telefoon") or ""}</td>
            <td>{r.get("email") or ""}</td>
            <td>{r.get("beschikbaarheid") or ""}</td>
            <td>{actief}</td>
            <td><a href="/org-admin/externe-contacten/{r.get("extern_contact_id")}/edit">Bewerk</a></td>
        </tr>
        """

    body = f"""
    <div class="card">
        <h2>Nieuw extern contact</h2>
        <form method="post" action="/org-admin/externe-contacten/create">
            <label>Naam</label>
            <input name="naam" required>

            <label>Type</label>
            <input name="type" placeholder="helpdesk, nooddienst, leverancier">

            <label>Telefoon</label>
            <input name="telefoon">

            <label>Email</label>
            <input name="email">

            <label>Website</label>
            <input name="website">

            <label>Beschikbaarheid</label>
            <textarea name="beschikbaarheid"></textarea>

            <label>Opmerkingen</label>
            <textarea name="opmerkingen"></textarea>

            <button type="submit">Opslaan</button>
        </form>
    </div>

    <table>
        <tr>
            <th>ID</th>
            <th>Naam</th>
            <th>Type</th>
            <th>Telefoon</th>
            <th>Email</th>
            <th>Beschikbaarheid</th>
            <th>Actief</th>
            <th>Actie</th>
        </tr>
        {table_rows}
    </table>
    """
    return page("Externe contacten", body)


@router.post("/externe-contacten/create")
def create_extern_contact(
    naam: str = Form(...),
    type: str = Form(""),
    telefoon: str = Form(""),
    email: str = Form(""),
    website: str = Form(""),
    beschikbaarheid: str = Form(""),
    opmerkingen: str = Form(""),
):
    execute("""
        INSERT INTO org_externe_contacten (
            naam,
            type,
            telefoon,
            email,
            website,
            beschikbaarheid,
            opmerkingen,
            actief,
            created_at,
            updated_at
        )
        VALUES (
            :naam,
            :type,
            :telefoon,
            :email,
            :website,
            :beschikbaarheid,
            :opmerkingen,
            TRUE,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        )
    """, {
        "naam": naam,
        "type": type or None,
        "telefoon": telefoon or None,
        "email": email or None,
        "website": website or None,
        "beschikbaarheid": beschikbaarheid or None,
        "opmerkingen": opmerkingen or None,
    })

    return RedirectResponse("/org-admin/externe-contacten", status_code=303)

@router.get("/externe-contacten/{extern_contact_id}/edit", response_class=HTMLResponse)
def edit_extern_contact_page(extern_contact_id: int):
    rows = fetch_all("""
        SELECT *
        FROM org_externe_contacten
        WHERE extern_contact_id = :extern_contact_id
        LIMIT 1
    """, {"extern_contact_id": extern_contact_id})

    if not rows:
        return page("Niet gevonden", "<p>Extern contact niet gevonden.</p>")

    r = rows[0]
    checked = "checked" if r.get("actief") else ""

    body = f"""
    <div class="card">
        <h2>Extern contact bewerken</h2>
        <form method="post" action="/org-admin/externe-contacten/{extern_contact_id}/update">
            <label>Naam</label>
            <input name="naam" required value="{r.get("naam") or ""}">

            <label>Type</label>
            <input name="type" value="{r.get("type") or ""}">

            <label>Telefoon</label>
            <input name="telefoon" value="{r.get("telefoon") or ""}">

            <label>Email</label>
            <input name="email" value="{r.get("email") or ""}">

            <label>Website</label>
            <input name="website" value="{r.get("website") or ""}">

            <label>Beschikbaarheid</label>
            <textarea name="beschikbaarheid">{r.get("beschikbaarheid") or ""}</textarea>

            <label>Opmerkingen</label>
            <textarea name="opmerkingen">{r.get("opmerkingen") or ""}</textarea>

            <label>
                <input type="checkbox" name="actief" value="true" {checked} style="width:auto;">
                Actief
            </label>

            <br><br>
            <button type="submit">Opslaan</button>
        </form>
    </div>
    """
    return page("Extern contact bewerken", body)

@router.post("/externe-contacten/{extern_contact_id}/update")
def update_extern_contact(
    extern_contact_id: int,
    naam: str = Form(...),
    type: str = Form(""),
    telefoon: str = Form(""),
    email: str = Form(""),
    website: str = Form(""),
    beschikbaarheid: str = Form(""),
    opmerkingen: str = Form(""),
    actief: str | None = Form(None),
):
    execute("""
        UPDATE org_externe_contacten
        SET naam = :naam,
            type = :type,
            telefoon = :telefoon,
            email = :email,
            website = :website,
            beschikbaarheid = :beschikbaarheid,
            opmerkingen = :opmerkingen,
            actief = :actief,
            updated_at = CURRENT_TIMESTAMP
        WHERE extern_contact_id = :extern_contact_id
    """, {
        "extern_contact_id": extern_contact_id,
        "naam": naam,
        "type": type or None,
        "telefoon": telefoon or None,
        "email": email or None,
        "website": website or None,
        "beschikbaarheid": beschikbaarheid or None,
        "opmerkingen": opmerkingen or None,
        "actief": bool(actief),
    })

    return RedirectResponse("/org-admin/externe-contacten", status_code=303)

@router.get("/personen", response_class=HTMLResponse)
def personen_page():
    rows = fetch_all("""
        SELECT
            p.*,
            STRING_AGG(f.functie_naam, ', ' ORDER BY f.functie_naam) AS functies
        FROM org_personen p
        LEFT JOIN org_persoon_functies pf
            ON pf.person_id = p.person_id
           AND pf.geldig_tot IS NULL
        LEFT JOIN org_functies f
            ON f.functie_code = pf.functie_code
           AND f.actief = TRUE
        WHERE p.actief = TRUE
        GROUP BY p.person_id
        ORDER BY p.locatie, p.weergavenaam
    """)
    table_rows = ""
    for r in rows:
        actief = "ja" if r.get("actief") else "nee"
        table_rows += f"""
        <tr>
            <td>{r.get("person_id")}</td>
            <td>{r.get("weergavenaam") or ""}</td>
            <td>{r.get("firma_naam") or ""}</td>
            <td>{r.get("locatie") or ""}</td>
            <td>{r.get("afdeling") or ""}</td>
            <td>{r.get("officiele_functienaam") or ""}</td>
            <td>{r.get("functies") or ""}</td>
            <td>{r.get("email") or ""}</td>
            <td>{r.get("telefoon") or ""}</td>
            <td>{r.get("mobiel") or ""}</td>
            <td>{actief}</td>
            <td><a href="/org-admin/personen/{r.get("person_id")}/edit">Bewerk</a></td>
        </tr>
        """

    body = f"""
    <div class="card">
        <h2>Nieuwe persoon</h2>
        <form method="post" action="/org-admin/personen/create">
            <label>Voornaam</label>
            <input name="voornaam" required>

            <label>Achternaam</label>
            <input name="achternaam" required>

            <label>Weergavenaam</label>
            <input name="weergavenaam" placeholder="Bijvoorbeeld Andy" required>

            <label>Firma</label>
            <select name="firma_naam">
                {select_options_firmas(selected="Promati")}
            </select>

            <label>Locatie</label>
            <select name="locatie">
                {select_options_locaties(include_empty=True)}
            </select>

            <label>Afdeling</label>
            <input name="afdeling" placeholder="IT, TD, Kantoor, ...">

            <label>Email</label>
            <input name="email">

            <label>Telefoon</label>
            <input name="telefoon">

            <label>Mobiel</label>
            <input name="mobiel">

            <label>Officiële functiecode</label>
            <input name="officiele_functie_code" placeholder="IT_CONTACT, BHV_CONTACT, ...">

            <label>Officiële functienaam</label>
            <input name="officiele_functienaam" placeholder="IT-contactpersoon">

            <label>Datum in dienst</label>
            <input name="datum_in_dienst" type="date">

            <label>Datum uit dienst</label>
            <input name="datum_uit_dienst" type="date">

            <label>Opmerkingen</label>
            <textarea name="opmerkingen"></textarea>

            <button type="submit">Opslaan</button>
        </form>
    </div>

    <table>
        <tr>
            <th>ID</th>
            <th>Naam</th>
            <th>Firma</th>
            <th>Locatie</th>
            <th>Afdeling</th>
            <th>Officiële functie</th>
            <th>Gekoppelde functieomschrijving</th>
            <th>Email</th>
            <th>Telefoon</th>
            <th>Mobiel</th>
            <th>Actief</th>
            <th>Actie</th>
        </tr>
        {table_rows}
    </table>
    """
    return page("Personen", body)

@router.post("/personen/create")
def create_persoon(
    voornaam: str = Form(...),
    achternaam: str = Form(...),
    weergavenaam: str = Form(...),
    firma_naam: str = Form(""),
    locatie: str = Form(""),
    afdeling: str = Form(""),
    email: str = Form(""),
    telefoon: str = Form(""),
    mobiel: str = Form(""),
    officiele_functie_code: str = Form(""),
    officiele_functienaam: str = Form(""),
    datum_in_dienst: str = Form(""),
    datum_uit_dienst: str = Form(""),
    opmerkingen: str = Form(""),
):
    execute("""
        INSERT INTO org_personen (
            firma_naam,
            locatie,
            afdeling,
            voornaam,
            achternaam,
            weergavenaam,
            email,
            telefoon,
            mobiel,
            officiele_functie_code,
            officiele_functienaam,
            datum_in_dienst,
            datum_uit_dienst,
            actief,
            opmerkingen,
            created_at,
            updated_at
        )
        VALUES (
            :firma_naam,
            :locatie,
            :afdeling,
            :voornaam,
            :achternaam,
            :weergavenaam,
            :email,
            :telefoon,
            :mobiel,
            :officiele_functie_code,
            :officiele_functienaam,
            NULLIF(:datum_in_dienst, '')::date,
            NULLIF(:datum_uit_dienst, '')::date,
            TRUE,
            :opmerkingen,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        )
    """, {
        "firma_naam": firma_naam or None,
        "locatie": locatie or None,
        "afdeling": afdeling or None,
        "voornaam": voornaam,
        "achternaam": achternaam,
        "weergavenaam": weergavenaam,
        "email": email or None,
        "telefoon": telefoon or None,
        "mobiel": mobiel or None,
        "officiele_functie_code": officiele_functie_code or None,
        "officiele_functienaam": officiele_functienaam or None,
        "datum_in_dienst": datum_in_dienst or "",
        "datum_uit_dienst": datum_uit_dienst or "",
        "opmerkingen": opmerkingen or None,
    })

    return RedirectResponse("/org-admin/personen", status_code=303)

@router.get("/personen/{person_id}/edit", response_class=HTMLResponse)
def edit_persoon_page(person_id: int):
    rows = fetch_all("""
        SELECT *
        FROM org_personen
        WHERE person_id = :person_id
        LIMIT 1
    """, {"person_id": person_id})

    if not rows:
        return page("Niet gevonden", "<p>Persoon niet gevonden.</p>")

    r = rows[0]
    checked = "checked" if r.get("actief") else ""

    datum_in_dienst = r.get("datum_in_dienst") or ""
    datum_uit_dienst = r.get("datum_uit_dienst") or ""

    functies = fetch_all("""
        SELECT
            pf.persoon_functie_id,
            f.functie_code,
            f.functie_naam,
            f.categorie,
            f.entiteit,
            f.kernfocus,
            f.doel,
            f.kerntaken,
            f.veiligheid_vca,
            pf.primair,
            pf.geldig_vanaf,
            pf.geldig_tot,
            pf.opmerkingen
        FROM org_persoon_functies pf
        JOIN org_functies f
            ON f.functie_code = pf.functie_code
        WHERE pf.person_id = :person_id
          AND pf.geldig_tot IS NULL
        ORDER BY pf.primair DESC, f.functie_naam
    """, {"person_id": person_id})

    functie_rows = ""

    for f in functies:
        primair = "ja" if f.get("primair") else "nee"
        functie_rows += f"""
        <tr>
            <td>{safe_html(f.get("functie_naam"))}</td>
            <td>{safe_html(f.get("categorie"))}</td>
            <td>{safe_html(f.get("entiteit"))}</td>
            <td>{primair}</td>
            <td>
                <details>
                    <summary>{safe_html(f.get("kernfocus"))}</summary>

                    <p><strong>Doel</strong></p>
                    <pre style="white-space:pre-wrap;">{safe_html(f.get("doel"))}</pre>

                    <p><strong>Kerntaken</strong></p>
                    <pre style="white-space:pre-wrap;">{safe_html(f.get("kerntaken"))}</pre>

                    <p><strong>Veiligheid & VCA</strong></p>
                    <pre style="white-space:pre-wrap;">{safe_html(f.get("veiligheid_vca"))}</pre>
                </details>
            </td>
            <td>
                <form method="post" action="/org-admin/personen/{person_id}/functies/{f.get("persoon_functie_id")}/end" style="display:inline;">
                    <button type="submit">Beëindig</button>
                </form>
            </td>
        </tr>
        """

    if not functie_rows:
        functie_rows = """
        <tr>
            <td colspan="6">Nog geen functieomschrijving gekoppeld aan deze persoon.</td>
        </tr>
        """

    functies_html = f"""
    <div class="card">
        <h2>Gekoppelde functieomschrijvingen</h2>

        <table>
            <tr>
                <th>Functie</th>
                <th>Categorie</th>
                <th>Entiteit</th>
                <th>Primair</th>
                <th>Omschrijving</th>
                <th>Actie</th>
            </tr>
            {functie_rows}
        </table>
    </div>

    <div class="card">
        <h2>Functie koppelen</h2>

        <form method="post" action="/org-admin/personen/{person_id}/functies/add">
            <label>Functie</label>
            <select name="functie_code" required>
                {select_options_functies()}
            </select>

            <label>
                <input type="checkbox" name="primair" value="1" checked style="width:auto;">
                Primair
            </label>

            <label>Geldig vanaf</label>
            <input name="geldig_vanaf" type="date">

            <label>Opmerkingen</label>
            <textarea name="opmerkingen"></textarea>

            <button type="submit">Functie koppelen</button>
        </form>
    </div>
    """

    body = f"""
    <div class="card">
        <h2>Persoon bewerken</h2>
        <form method="post" action="/org-admin/personen/{person_id}/update">
            <label>Voornaam</label>
            <input name="voornaam" required value="{r.get("voornaam") or ""}">

            <label>Achternaam</label>
            <input name="achternaam" required value="{r.get("achternaam") or ""}">

            <label>Weergavenaam</label>
            <input name="weergavenaam" required value="{r.get("weergavenaam") or ""}">

            <label>Firma</label>
            <select name="firma_naam">
                {select_options_firmas(selected=r.get("firma_naam") or "Promati")}
            </select>

            <label>Locatie</label>
            <select name="locatie">
                {select_options_locaties(selected=r.get("locatie"), include_empty=True)}
            </select>

            <label>Afdeling</label>
            <input name="afdeling" value="{r.get("afdeling") or ""}">

            <label>Email</label>
            <input name="email" value="{r.get("email") or ""}">

            <label>Telefoon</label>
            <input name="telefoon" value="{r.get("telefoon") or ""}">

            <label>Mobiel</label>
            <input name="mobiel" value="{r.get("mobiel") or ""}">

            <label>Officiële functiecode</label>
            <input name="officiele_functie_code" value="{r.get("officiele_functie_code") or ""}">

            <label>Officiële functienaam</label>
            <input name="officiele_functienaam" value="{r.get("officiele_functienaam") or ""}">

            <label>Datum in dienst</label>
            <input name="datum_in_dienst" type="date" value="{datum_in_dienst}">

            <label>Datum uit dienst</label>
            <input name="datum_uit_dienst" type="date" value="{datum_uit_dienst}">

            <label>Opmerkingen</label>
            <textarea name="opmerkingen">{r.get("opmerkingen") or ""}</textarea>

            <label>
                <input type="checkbox" name="actief" value="true" {checked} style="width:auto;">
                Actief
            </label>

            <br><br>
            <button type="submit">Opslaan</button>
        </form>
    </div>

    {functies_html}
    """
    return page("Persoon bewerken", body)

@router.post("/personen/{person_id}/update")
def update_persoon(
    person_id: int,
    voornaam: str = Form(...),
    achternaam: str = Form(...),
    weergavenaam: str = Form(...),
    firma_naam: str = Form(""),
    locatie: str = Form(""),
    afdeling: str = Form(""),
    email: str = Form(""),
    telefoon: str = Form(""),
    mobiel: str = Form(""),
    officiele_functie_code: str = Form(""),
    officiele_functienaam: str = Form(""),
    datum_in_dienst: str = Form(""),
    datum_uit_dienst: str = Form(""),
    opmerkingen: str = Form(""),
    actief: str | None = Form(None),
):
    execute("""
        UPDATE org_personen
        SET firma_naam = :firma_naam,
            locatie = :locatie,
            afdeling = :afdeling,
            voornaam = :voornaam,
            achternaam = :achternaam,
            weergavenaam = :weergavenaam,
            email = :email,
            telefoon = :telefoon,
            mobiel = :mobiel,
            officiele_functie_code = :officiele_functie_code,
            officiele_functienaam = :officiele_functienaam,
            datum_in_dienst = NULLIF(:datum_in_dienst, '')::date,
            datum_uit_dienst = NULLIF(:datum_uit_dienst, '')::date,
            actief = :actief,
            opmerkingen = :opmerkingen,
            updated_at = CURRENT_TIMESTAMP
        WHERE person_id = :person_id
    """, {
        "person_id": person_id,
        "firma_naam": firma_naam or None,
        "locatie": locatie or None,
        "afdeling": afdeling or None,
        "voornaam": voornaam,
        "achternaam": achternaam,
        "weergavenaam": weergavenaam,
        "email": email or None,
        "telefoon": telefoon or None,
        "mobiel": mobiel or None,
        "officiele_functie_code": officiele_functie_code or None,
        "officiele_functienaam": officiele_functienaam or None,
        "datum_in_dienst": datum_in_dienst or "",
        "datum_uit_dienst": datum_uit_dienst or "",
        "actief": bool(actief),
        "opmerkingen": opmerkingen or None,
    })

    return RedirectResponse("/org-admin/personen", status_code=303)


@router.post("/personen/{person_id}/functies/add")
def add_functie_to_persoon(
    person_id: int,
    functie_code: str = Form(...),
    primair: str | None = Form(None),
    geldig_vanaf: str = Form(""),
    opmerkingen: str = Form(""),
):
    functie_code_clean = functie_code.strip()

    if not functie_code_clean:
        return RedirectResponse(f"/org-admin/personen/{person_id}/edit", status_code=303)

    execute("""
        INSERT INTO org_persoon_functies (
            person_id,
            functie_code,
            primair,
            geldig_vanaf,
            geldig_tot,
            opmerkingen,
            aangemaakt_op,
            bijgewerkt_op
        )
        VALUES (
            :person_id,
            :functie_code,
            :primair,
            NULLIF(:geldig_vanaf, '')::date,
            NULL,
            :opmerkingen,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        )
    """, {
        "person_id": person_id,
        "functie_code": functie_code_clean,
        "primair": bool(primair),
        "geldig_vanaf": geldig_vanaf or "",
        "opmerkingen": opmerkingen.strip() or None,
    })

    return RedirectResponse(f"/org-admin/personen/{person_id}/edit", status_code=303)


@router.post("/personen/{person_id}/functies/{persoon_functie_id}/end")
def end_functie_for_persoon(
    person_id: int,
    persoon_functie_id: int,
):
    execute("""
        UPDATE org_persoon_functies
        SET geldig_tot = CURRENT_DATE,
            bijgewerkt_op = CURRENT_TIMESTAMP
        WHERE persoon_functie_id = :persoon_functie_id
          AND person_id = :person_id
    """, {
        "persoon_functie_id": persoon_functie_id,
        "person_id": person_id,
    })

    return RedirectResponse(f"/org-admin/personen/{person_id}/edit", status_code=303)


@router.get("/taken", response_class=HTMLResponse)
def taken_page():
    rows = fetch_all("""
        SELECT *
        FROM org_taken
        ORDER BY actief DESC, categorie, taak_naam
    """)

    table_rows = ""
    for r in rows:
        actief = "ja" if r.get("actief") else "nee"
        info_eerst = "ja" if r.get("informatie_eerst") else "nee"
        selfservice = "ja" if r.get("selfservice_mogelijk") else "nee"
        escalatie = "ja" if r.get("escalatie_verplicht") else "nee"

        table_rows += f"""
        <tr>
            <td>{r.get("taak_code")}</td>
            <td>{r.get("taak_naam") or ""}</td>
            <td>{r.get("categorie") or ""}</td>
            <td>{r.get("zoekwoorden") or ""}</td>
            <td>{r.get("rag_document_code") or ""}</td>
            <td>{info_eerst}</td>
            <td>{selfservice}</td>
            <td>{escalatie}</td>
            <td>{actief}</td>
            <td><a href="/org-admin/taken/{r.get("taak_code")}/edit">Bewerk</a></td>
        </tr>
        """

    body = f"""
    <div class="card">
        <h2>Nieuwe taak</h2>
        <form method="post" action="/org-admin/taken/create">
            <label>Taakcode</label>
            <input name="taak_code" required placeholder="Bijvoorbeeld WIFI_SUPPORT">

            <label>Taaknaam</label>
            <input name="taak_naam" required placeholder="Bijvoorbeeld Wifi-problemen">

            <label>Categorie</label>
            <input name="categorie" placeholder="IT, Veiligheid, HR, Facilitair">

            <label>Zoekwoorden</label>
            <textarea name="zoekwoorden" placeholder="wifi, internet, netwerk, verbinding"></textarea>

            <label>RAG-documentcode</label>
            <input name="rag_document_code" placeholder="taak_WIFI_SUPPORT">

            <label>Standaard antwoord kort</label>
            <textarea name="standaard_antwoord_kort"></textarea>

            <label>
                <input type="checkbox" name="informatie_eerst" value="true" checked style="width:auto;">
                Eerst informatie geven
            </label><br>

            <label>
                <input type="checkbox" name="selfservice_mogelijk" value="true" checked style="width:auto;">
                Selfservice mogelijk
            </label><br>

            <label>
                <input type="checkbox" name="escalatie_verplicht" value="true" style="width:auto;">
                Escalatie verplicht
            </label>

            <br><br>
            <button type="submit">Opslaan</button>
        </form>
    </div>

    <table>
        <tr>
            <th>Taakcode</th>
            <th>Taaknaam</th>
            <th>Categorie</th>
            <th>Zoekwoorden</th>
            <th>RAG-code</th>
            <th>Info eerst</th>
            <th>Selfservice</th>
            <th>Escalatie</th>
            <th>Actief</th>
            <th>Actie</th>
        </tr>
        {table_rows}
    </table>
    """
    return page("Taken", body)

@router.post("/taken/create")
def create_taak(
    taak_code: str = Form(...),
    taak_naam: str = Form(...),
    categorie: str = Form(""),
    zoekwoorden: str = Form(""),
    rag_document_code: str = Form(""),
    standaard_antwoord_kort: str = Form(""),
    informatie_eerst: str | None = Form(None),
    selfservice_mogelijk: str | None = Form(None),
    escalatie_verplicht: str | None = Form(None),
):
    execute("""
        INSERT INTO org_taken (
            taak_code,
            taak_naam,
            categorie,
            zoekwoorden,
            rag_document_code,
            standaard_antwoord_kort,
            informatie_eerst,
            selfservice_mogelijk,
            escalatie_verplicht,
            actief,
            created_at,
            updated_at
        )
        VALUES (
            UPPER(:taak_code),
            :taak_naam,
            :categorie,
            :zoekwoorden,
            :rag_document_code,
            :standaard_antwoord_kort,
            :informatie_eerst,
            :selfservice_mogelijk,
            :escalatie_verplicht,
            TRUE,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        )
    """, {
        "taak_code": taak_code.strip(),
        "taak_naam": taak_naam,
        "categorie": categorie or None,
        "zoekwoorden": zoekwoorden or None,
        "rag_document_code": rag_document_code or None,
        "standaard_antwoord_kort": standaard_antwoord_kort or None,
        "informatie_eerst": bool(informatie_eerst),
        "selfservice_mogelijk": bool(selfservice_mogelijk),
        "escalatie_verplicht": bool(escalatie_verplicht),
    })

    return RedirectResponse("/org-admin/taken", status_code=303)

@router.get("/taken/{taak_code}/edit", response_class=HTMLResponse)
def edit_taak_page(taak_code: str):
    rows = fetch_all("""
        SELECT *
        FROM org_taken
        WHERE taak_code = :taak_code
        LIMIT 1
    """, {"taak_code": taak_code})

    if not rows:
        return page("Niet gevonden", "<p>Taak niet gevonden.</p>")

    r = rows[0]

    checked_info = "checked" if r.get("informatie_eerst") else ""
    checked_selfservice = "checked" if r.get("selfservice_mogelijk") else ""
    checked_escalatie = "checked" if r.get("escalatie_verplicht") else ""
    checked_actief = "checked" if r.get("actief") else ""

    body = f"""
    <div class="card">
        <h2>Taak bewerken</h2>
        <form method="post" action="/org-admin/taken/{taak_code}/update">
            <label>Taakcode</label>
            <input name="taak_code_display" value="{r.get("taak_code")}" disabled>

            <label>Taaknaam</label>
            <input name="taak_naam" required value="{r.get("taak_naam") or ""}">

            <label>Categorie</label>
            <input name="categorie" value="{r.get("categorie") or ""}">

            <label>Zoekwoorden</label>
            <textarea name="zoekwoorden">{r.get("zoekwoorden") or ""}</textarea>

            <label>RAG-documentcode</label>
            <input name="rag_document_code" value="{r.get("rag_document_code") or ""}">

            <label>Standaard antwoord kort</label>
            <textarea name="standaard_antwoord_kort">{r.get("standaard_antwoord_kort") or ""}</textarea>

            <label>
                <input type="checkbox" name="informatie_eerst" value="true" {checked_info} style="width:auto;">
                Eerst informatie geven
            </label><br>

            <label>
                <input type="checkbox" name="selfservice_mogelijk" value="true" {checked_selfservice} style="width:auto;">
                Selfservice mogelijk
            </label><br>

            <label>
                <input type="checkbox" name="escalatie_verplicht" value="true" {checked_escalatie} style="width:auto;">
                Escalatie verplicht
            </label><br>

            <label>
                <input type="checkbox" name="actief" value="true" {checked_actief} style="width:auto;">
                Actief
            </label>

            <br><br>
            <button type="submit">Opslaan</button>
        </form>
    </div>
    """
    return page("Taak bewerken", body)

@router.post("/taken/{taak_code}/update")
def update_taak(
    taak_code: str,
    taak_naam: str = Form(...),
    categorie: str = Form(""),
    zoekwoorden: str = Form(""),
    rag_document_code: str = Form(""),
    standaard_antwoord_kort: str = Form(""),
    informatie_eerst: str | None = Form(None),
    selfservice_mogelijk: str | None = Form(None),
    escalatie_verplicht: str | None = Form(None),
    actief: str | None = Form(None),
):
    execute("""
        UPDATE org_taken
        SET taak_naam = :taak_naam,
            categorie = :categorie,
            zoekwoorden = :zoekwoorden,
            rag_document_code = :rag_document_code,
            standaard_antwoord_kort = :standaard_antwoord_kort,
            informatie_eerst = :informatie_eerst,
            selfservice_mogelijk = :selfservice_mogelijk,
            escalatie_verplicht = :escalatie_verplicht,
            actief = :actief,
            updated_at = CURRENT_TIMESTAMP
        WHERE taak_code = :taak_code
    """, {
        "taak_code": taak_code,
        "taak_naam": taak_naam,
        "categorie": categorie or None,
        "zoekwoorden": zoekwoorden or None,
        "rag_document_code": rag_document_code or None,
        "standaard_antwoord_kort": standaard_antwoord_kort or None,
        "informatie_eerst": bool(informatie_eerst),
        "selfservice_mogelijk": bool(selfservice_mogelijk),
        "escalatie_verplicht": bool(escalatie_verplicht),
        "actief": bool(actief),
    })

    return RedirectResponse("/org-admin/taken", status_code=303)

@router.get("/routering", response_class=HTMLResponse)
def routering_page():
    routes = fetch_all("""
        SELECT
            r.route_id,
            r.taak_code,
            t.taak_naam,
            r.scope_type,
            r.firma_naam,
            r.locatie,
            r.afdeling,
            p.weergavenaam AS primair_naam,
            b.weergavenaam AS backup_naam,
            ec.naam AS extern_naam,
            r.prioriteit,
            r.actief
        FROM org_taak_routering r
        LEFT JOIN org_taken t
            ON t.taak_code = r.taak_code
        LEFT JOIN org_personen p
            ON p.person_id = r.primair_person_id
        LEFT JOIN org_personen b
            ON b.person_id = r.backup_person_id
        LEFT JOIN org_externe_contacten ec
            ON ec.extern_contact_id = r.extern_contact_id
        ORDER BY r.actief DESC, r.taak_code, r.prioriteit
    """)

    taak_options = select_options_taken()
    persoon_options = select_options_personen()
    extern_options = select_options_externe_contacten()
    firma_options = select_options_firmas(selected="Promati", include_empty=True)
    locatie_options = select_options_locaties(include_empty=True)

    table_rows = ""
    for r in routes:
        actief = "ja" if r.get("actief") else "nee"
        scope = r.get("scope_type") or ""
        table_rows += f"""
        <tr>
            <td>{r.get("route_id")}</td>
            <td>{r.get("taak_naam") or r.get("taak_code")}</td>
            <td>{scope}</td>
            <td>{r.get("firma_naam") or ""}</td>
            <td>{r.get("locatie") or ""}</td>
            <td>{r.get("afdeling") or ""}</td>
            <td>{r.get("primair_naam") or ""}</td>
            <td>{r.get("backup_naam") or ""}</td>
            <td>{r.get("extern_naam") or ""}</td>
            <td>{r.get("prioriteit")}</td>
            <td>{actief}</td>
            <td><a href="/org-admin/routering/{r.get("route_id")}/edit">Bewerk</a></td>
        </tr>
        """

    body = f"""
    <div class="card">
        <h2>Nieuwe routering</h2>
        <form method="post" action="/org-admin/routering/create">
            <label>Taak</label>
            <select name="taak_code" required>
                {taak_options}
            </select>

            <label>Scope</label>
            <select name="scope_type" required>
                <option value="GLOBAL">GLOBAL - alle firma's en locaties</option>
                <option value="FIRMA">FIRMA - alleen firma</option>
                <option value="LOCATIE">LOCATIE - firma + locatie</option>
                <option value="AFDELING">AFDELING - firma + locatie + afdeling</option>
            </select>

            <label>Firma</label>
            <select name="firma_naam">
                {firma_options}
            </select>

            <label>Locatie</label>
            <select name="locatie">
                {locatie_options}
            </select>

            <label>Afdeling</label>
            <input name="afdeling" placeholder="IT, TD, Kantoor">

            <label>Primair contact</label>
            <select name="primair_person_id">
                {persoon_options}
            </select>

            <label>Backup contact</label>
            <select name="backup_person_id">
                {persoon_options}
            </select>

            <label>Extern contact</label>
            <select name="extern_contact_id">
                {extern_options}
            </select>

            <label>Contactinstructie</label>
            <textarea name="contactinstructie"></textarea>

            <label>Escalatie-instructie</label>
            <textarea name="escalatie_instructie"></textarea>

            <label>Prioriteit</label>
            <input name="prioriteit" type="number" value="100">

            <button type="submit">Opslaan</button>
        </form>
    </div>

    <table>
        <tr>
            <th>ID</th>
            <th>Taak</th>
            <th>Scope</th>
            <th>Firma</th>
            <th>Locatie</th>
            <th>Afdeling</th>
            <th>Primair</th>
            <th>Backup</th>
            <th>Extern</th>
            <th>Prioriteit</th>
            <th>Actief</th>
            <th>Actie</th>
        </tr>
        {table_rows}
    </table>
    """
    return page("Routering", body)

@router.post("/routering/create")
def create_routering(
    taak_code: str = Form(...),
    scope_type: str = Form(...),
    firma_naam: str = Form(""),
    locatie: str = Form(""),
    afdeling: str = Form(""),
    primair_person_id: str = Form(""),
    backup_person_id: str = Form(""),
    extern_contact_id: str = Form(""),
    contactinstructie: str = Form(""),
    escalatie_instructie: str = Form(""),
    prioriteit: int = Form(100),
):
    execute("""
        INSERT INTO org_taak_routering (
            taak_code,
            scope_type,
            firma_naam,
            locatie,
            afdeling,
            primair_person_id,
            backup_person_id,
            extern_contact_id,
            contactinstructie,
            escalatie_instructie,
            prioriteit,
            actief,
            created_at,
            updated_at
        )
        VALUES (
            :taak_code,
            :scope_type,
            :firma_naam,
            :locatie,
            :afdeling,
            NULLIF(:primair_person_id, '')::int,
            NULLIF(:backup_person_id, '')::int,
            NULLIF(:extern_contact_id, '')::int,
            :contactinstructie,
            :escalatie_instructie,
            :prioriteit,
            TRUE,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        )
    """, {
        "taak_code": taak_code,
        "scope_type": scope_type,
        "firma_naam": firma_naam or None,
        "locatie": locatie or None,
        "afdeling": afdeling or None,
        "primair_person_id": primair_person_id or "",
        "backup_person_id": backup_person_id or "",
        "extern_contact_id": extern_contact_id or "",
        "contactinstructie": contactinstructie or None,
        "escalatie_instructie": escalatie_instructie or None,
        "prioriteit": prioriteit,
    })

    return RedirectResponse("/org-admin/routering", status_code=303)

@router.get("/routering/{route_id}/edit", response_class=HTMLResponse)
def edit_routering_page(route_id: int):
    rows = fetch_all("""
        SELECT *
        FROM org_taak_routering
        WHERE route_id = :route_id
        LIMIT 1
    """, {"route_id": route_id})

    if not rows:
        return page("Niet gevonden", "<p>Routering niet gevonden.</p>")

    r = rows[0]

    def selected(value, current):
        return "selected" if str(value or "") == str(current or "") else ""

    taak_options = select_options_taken(selected=r.get("taak_code"))
    persoon_options_primair = select_options_personen(selected=r.get("primair_person_id"))
    persoon_options_backup = select_options_personen(selected=r.get("backup_person_id"))
    extern_options = select_options_externe_contacten(selected=r.get("extern_contact_id"))
    firma_options = select_options_firmas(selected=r.get("firma_naam"), include_empty=True)
    locatie_options = select_options_locaties(selected=r.get("locatie"), include_empty=True)

    checked_actief = "checked" if r.get("actief") else ""

    body = f"""
    <div class="card">
        <h2>Routering bewerken</h2>
        <form method="post" action="/org-admin/routering/{route_id}/update">
            <label>Taak</label>
            <select name="taak_code" required>
                {taak_options}
            </select>

            <label>Scope</label>
            <select name="scope_type" required>
                <option value="GLOBAL" {selected("GLOBAL", r.get("scope_type"))}>GLOBAL - alle firma's en locaties</option>
                <option value="FIRMA" {selected("FIRMA", r.get("scope_type"))}>FIRMA - alleen firma</option>
                <option value="LOCATIE" {selected("LOCATIE", r.get("scope_type"))}>LOCATIE - firma + locatie</option>
                <option value="AFDELING" {selected("AFDELING", r.get("scope_type"))}>AFDELING - firma + locatie + afdeling</option>
            </select>

            <label>Firma</label>
            <select name="firma_naam">
                {firma_options}
            </select>

            <label>Locatie</label>
            <select name="locatie">
                {locatie_options}
            </select>

            <label>Afdeling</label>
            <input name="afdeling" value="{r.get("afdeling") or ""}">

            <label>Primair contact</label>
            <select name="primair_person_id">
                {persoon_options_primair}
            </select>

            <label>Backup contact</label>
            <select name="backup_person_id">
                {persoon_options_backup}
            </select>

            <label>Extern contact</label>
            <select name="extern_contact_id">
                {extern_options}
            </select>

            <label>Contactinstructie</label>
            <textarea name="contactinstructie">{r.get("contactinstructie") or ""}</textarea>

            <label>Escalatie-instructie</label>
            <textarea name="escalatie_instructie">{r.get("escalatie_instructie") or ""}</textarea>

            <label>Prioriteit</label>
            <input name="prioriteit" type="number" value="{r.get("prioriteit") or 100}">

            <label>
                <input type="checkbox" name="actief" value="true" {checked_actief} style="width:auto;">
                Actief
            </label>

            <br><br>
            <button type="submit">Opslaan</button>
        </form>
    </div>
    """
    return page("Routering bewerken", body)

@router.post("/routering/{route_id}/update")
def update_routering(
    route_id: int,
    taak_code: str = Form(...),
    scope_type: str = Form(...),
    firma_naam: str = Form(""),
    locatie: str = Form(""),
    afdeling: str = Form(""),
    primair_person_id: str = Form(""),
    backup_person_id: str = Form(""),
    extern_contact_id: str = Form(""),
    contactinstructie: str = Form(""),
    escalatie_instructie: str = Form(""),
    prioriteit: int = Form(100),
    actief: str | None = Form(None),
):
    execute("""
        UPDATE org_taak_routering
        SET taak_code = :taak_code,
            scope_type = :scope_type,
            firma_naam = :firma_naam,
            locatie = :locatie,
            afdeling = :afdeling,
            primair_person_id = NULLIF(:primair_person_id, '')::int,
            backup_person_id = NULLIF(:backup_person_id, '')::int,
            extern_contact_id = NULLIF(:extern_contact_id, '')::int,
            contactinstructie = :contactinstructie,
            escalatie_instructie = :escalatie_instructie,
            prioriteit = :prioriteit,
            actief = :actief,
            updated_at = CURRENT_TIMESTAMP
        WHERE route_id = :route_id
    """, {
        "route_id": route_id,
        "taak_code": taak_code,
        "scope_type": scope_type,
        "firma_naam": firma_naam or None,
        "locatie": locatie or None,
        "afdeling": afdeling or None,
        "primair_person_id": primair_person_id or "",
        "backup_person_id": backup_person_id or "",
        "extern_contact_id": extern_contact_id or "",
        "contactinstructie": contactinstructie or None,
        "escalatie_instructie": escalatie_instructie or None,
        "prioriteit": prioriteit,
        "actief": bool(actief),
    })

    return RedirectResponse("/org-admin/routering", status_code=303)


def safe_html(value) -> str:
    return html.escape(str(value or ""))


@router.get("/functies", response_class=HTMLResponse)
def functies_page():
    rows = fetch_all("""
        SELECT
            f.*,
            COUNT(pf.persoon_functie_id) AS aantal_personen
        FROM org_functies f
        LEFT JOIN org_persoon_functies pf
            ON pf.functie_code = f.functie_code
           AND pf.geldig_tot IS NULL
        GROUP BY f.functie_code
        ORDER BY f.actief DESC, f.categorie, f.functie_naam
    """)

    table_rows = ""

    for r in rows:
        actief = "ja" if r.get("actief") else "nee"

        table_rows += f"""
        <tr>
            <td>{safe_html(r.get("functie_code"))}</td>
            <td>{safe_html(r.get("functie_naam"))}</td>
            <td>{safe_html(r.get("categorie"))}</td>
            <td>{safe_html(r.get("entiteit"))}</td>
            <td>{safe_html(r.get("kernfocus"))}</td>
            <td>{safe_html(r.get("aantal_personen"))}</td>
            <td>{actief}</td>
            <td><a href="/org-admin/functies/{safe_html(r.get("functie_code"))}/edit">Bewerk</a></td>
        </tr>
        """

    body = f"""
    <div class="card">
        <h2>Nieuwe functieomschrijving</h2>

        <form method="post" action="/org-admin/functies/create">
            <label>Functiecode</label>
            <input name="functie_code" required placeholder="Bijvoorbeeld TECHNICUS_VCA_COORDINATOR">

            <label>Functienaam</label>
            <input name="functie_naam" required placeholder="Bijvoorbeeld Technicus / VCA Coördinator">

            <label>Categorie</label>
            <input name="categorie" placeholder="Directie, Stafdiensten, Techniek, Sales, Logistiek">

            <label>Entiteit</label>
            <input name="entiteit" placeholder="Promati BV (NL), Promati NV (BE), Group">

            <label>Rapporteert aan</label>
            <input name="rapporteert_aan">

            <label>Reikwijdte</label>
            <input name="reikwijdte">

            <label>Kernfocus</label>
            <input name="kernfocus">

            <label>Doel</label>
            <textarea name="doel" rows="4"></textarea>

            <label>Resultaatgebieden</label>
            <textarea name="resultaatgebieden" rows="5"></textarea>

            <label>Kerntaken</label>
            <textarea name="kerntaken" rows="8"></textarea>

            <label>Bevoegdheden</label>
            <textarea name="bevoegdheden" rows="5"></textarea>

            <label>KPI's / indicatoren</label>
            <textarea name="kpis" rows="5"></textarea>

            <label>Veiligheid & VCA</label>
            <textarea name="veiligheid_vca" rows="6"></textarea>

            <label>Documentverantwoordelijkheden</label>
            <textarea name="documentverantwoordelijkheden" rows="6"></textarea>

            <label>Bron doc id</label>
            <input name="bron_doc_id" placeholder="Bijvoorbeeld functieomschrijvingen_promati_vca_2026">

            <button type="submit">Functie opslaan</button>
        </form>
    </div>

    <table>
        <tr>
            <th>Functiecode</th>
            <th>Functie</th>
            <th>Categorie</th>
            <th>Entiteit</th>
            <th>Kernfocus</th>
            <th>Personen</th>
            <th>Actief</th>
            <th>Actie</th>
        </tr>
        {table_rows}
    </table>
    """

    return page("Functies", body)


@router.post("/functies/create")
def create_functie(
    functie_code: str = Form(...),
    functie_naam: str = Form(...),
    categorie: str = Form(""),
    entiteit: str = Form(""),
    rapporteert_aan: str = Form(""),
    reikwijdte: str = Form(""),
    kernfocus: str = Form(""),
    doel: str = Form(""),
    resultaatgebieden: str = Form(""),
    kerntaken: str = Form(""),
    bevoegdheden: str = Form(""),
    kpis: str = Form(""),
    veiligheid_vca: str = Form(""),
    documentverantwoordelijkheden: str = Form(""),
    bron_doc_id: str = Form(""),
):
    code = functie_code.strip().upper().replace(" ", "_")

    execute("""
        INSERT INTO org_functies (
            functie_code,
            functie_naam,
            categorie,
            entiteit,
            rapporteert_aan,
            reikwijdte,
            kernfocus,
            doel,
            resultaatgebieden,
            kerntaken,
            bevoegdheden,
            kpis,
            veiligheid_vca,
            documentverantwoordelijkheden,
            bron_doc_id,
            actief,
            aangemaakt_op,
            bijgewerkt_op
        )
        VALUES (
            :functie_code,
            :functie_naam,
            :categorie,
            :entiteit,
            :rapporteert_aan,
            :reikwijdte,
            :kernfocus,
            :doel,
            :resultaatgebieden,
            :kerntaken,
            :bevoegdheden,
            :kpis,
            :veiligheid_vca,
            :documentverantwoordelijkheden,
            :bron_doc_id,
            TRUE,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (functie_code) DO UPDATE
        SET functie_naam = EXCLUDED.functie_naam,
            categorie = EXCLUDED.categorie,
            entiteit = EXCLUDED.entiteit,
            rapporteert_aan = EXCLUDED.rapporteert_aan,
            reikwijdte = EXCLUDED.reikwijdte,
            kernfocus = EXCLUDED.kernfocus,
            doel = EXCLUDED.doel,
            resultaatgebieden = EXCLUDED.resultaatgebieden,
            kerntaken = EXCLUDED.kerntaken,
            bevoegdheden = EXCLUDED.bevoegdheden,
            kpis = EXCLUDED.kpis,
            veiligheid_vca = EXCLUDED.veiligheid_vca,
            documentverantwoordelijkheden = EXCLUDED.documentverantwoordelijkheden,
            bron_doc_id = EXCLUDED.bron_doc_id,
            actief = TRUE,
            bijgewerkt_op = CURRENT_TIMESTAMP
    """, {
        "functie_code": code,
        "functie_naam": functie_naam.strip(),
        "categorie": categorie.strip() or None,
        "entiteit": entiteit.strip() or None,
        "rapporteert_aan": rapporteert_aan.strip() or None,
        "reikwijdte": reikwijdte.strip() or None,
        "kernfocus": kernfocus.strip() or None,
        "doel": doel.strip() or None,
        "resultaatgebieden": resultaatgebieden.strip() or None,
        "kerntaken": kerntaken.strip() or None,
        "bevoegdheden": bevoegdheden.strip() or None,
        "kpis": kpis.strip() or None,
        "veiligheid_vca": veiligheid_vca.strip() or None,
        "documentverantwoordelijkheden": documentverantwoordelijkheden.strip() or None,
        "bron_doc_id": bron_doc_id.strip() or None,
    })

    return RedirectResponse("/org-admin/functies", status_code=303)


@router.get("/functies/{functie_code}/edit", response_class=HTMLResponse)
def edit_functie_page(functie_code: str):
    rows = fetch_all("""
        SELECT *
        FROM org_functies
        WHERE functie_code = :functie_code
        LIMIT 1
    """, {"functie_code": functie_code})

    if not rows:
        return page("Niet gevonden", "<p>Functie niet gevonden.</p>")

    r = rows[0]
    checked = "checked" if r.get("actief") else ""

    gekoppelde_personen = fetch_all("""
        SELECT
            pf.persoon_functie_id,
            pf.primair,
            pf.geldig_vanaf,
            pf.geldig_tot,
            pf.opmerkingen,
            p.weergavenaam,
            p.email,
            p.locatie
        FROM org_persoon_functies pf
        JOIN org_personen p
            ON p.person_id = pf.person_id
        WHERE pf.functie_code = :functie_code
        ORDER BY pf.primair DESC, p.weergavenaam
    """, {"functie_code": functie_code})

    personen_rows = ""

    for p in gekoppelde_personen:
        primair = "ja" if p.get("primair") else "nee"
        personen_rows += f"""
        <tr>
            <td>{safe_html(p.get("weergavenaam"))}</td>
            <td>{safe_html(p.get("email"))}</td>
            <td>{safe_html(p.get("locatie"))}</td>
            <td>{primair}</td>
            <td>{safe_html(p.get("geldig_vanaf"))}</td>
            <td>{safe_html(p.get("geldig_tot"))}</td>
            <td>{safe_html(p.get("opmerkingen"))}</td>
        </tr>
        """

    if not personen_rows:
        personen_rows = """
        <tr>
            <td colspan="7">Nog geen personen gekoppeld aan deze functie.</td>
        </tr>
        """

    body = f"""
    <div class="card">
        <h2>Functieomschrijving bewerken</h2>

        <form method="post" action="/org-admin/functies/{safe_html(r.get("functie_code"))}/update">
            <label>Functiecode</label>
            <input value="{safe_html(r.get("functie_code"))}" disabled>

            <label>Functienaam</label>
            <input name="functie_naam" value="{safe_html(r.get("functie_naam"))}" required>

            <label>Categorie</label>
            <input name="categorie" value="{safe_html(r.get("categorie"))}">

            <label>Entiteit</label>
            <input name="entiteit" value="{safe_html(r.get("entiteit"))}">

            <label>Rapporteert aan</label>
            <input name="rapporteert_aan" value="{safe_html(r.get("rapporteert_aan"))}">

            <label>Reikwijdte</label>
            <input name="reikwijdte" value="{safe_html(r.get("reikwijdte"))}">

            <label>Kernfocus</label>
            <input name="kernfocus" value="{safe_html(r.get("kernfocus"))}">

            <label>Doel</label>
            <textarea name="doel" rows="5">{safe_html(r.get("doel"))}</textarea>

            <label>Resultaatgebieden</label>
            <textarea name="resultaatgebieden" rows="6">{safe_html(r.get("resultaatgebieden"))}</textarea>

            <label>Kerntaken</label>
            <textarea name="kerntaken" rows="10">{safe_html(r.get("kerntaken"))}</textarea>

            <label>Bevoegdheden</label>
            <textarea name="bevoegdheden" rows="6">{safe_html(r.get("bevoegdheden"))}</textarea>

            <label>KPI's / indicatoren</label>
            <textarea name="kpis" rows="6">{safe_html(r.get("kpis"))}</textarea>

            <label>Veiligheid & VCA</label>
            <textarea name="veiligheid_vca" rows="8">{safe_html(r.get("veiligheid_vca"))}</textarea>

            <label>Documentverantwoordelijkheden</label>
            <textarea name="documentverantwoordelijkheden" rows="8">{safe_html(r.get("documentverantwoordelijkheden"))}</textarea>

            <label>Bron doc id</label>
            <input name="bron_doc_id" value="{safe_html(r.get("bron_doc_id"))}">

            <label>
                <input type="checkbox" name="actief" value="1" {checked} style="width:auto;">
                Actief
            </label>

            <br><br>
            <button type="submit">Wijzigingen opslaan</button>
        </form>
    </div>

    <div class="card">
        <h2>Gekoppelde personen</h2>
        <table>
            <tr>
                <th>Naam</th>
                <th>Email</th>
                <th>Locatie</th>
                <th>Primair</th>
                <th>Vanaf</th>
                <th>Tot</th>
                <th>Opmerkingen</th>
            </tr>
            {personen_rows}
        </table>
    </div>
    """

    return page(f"Functie: {safe_html(r.get('functie_naam'))}", body)


@router.post("/functies/{functie_code}/update")
def update_functie(
    functie_code: str,
    functie_naam: str = Form(...),
    categorie: str = Form(""),
    entiteit: str = Form(""),
    rapporteert_aan: str = Form(""),
    reikwijdte: str = Form(""),
    kernfocus: str = Form(""),
    doel: str = Form(""),
    resultaatgebieden: str = Form(""),
    kerntaken: str = Form(""),
    bevoegdheden: str = Form(""),
    kpis: str = Form(""),
    veiligheid_vca: str = Form(""),
    documentverantwoordelijkheden: str = Form(""),
    bron_doc_id: str = Form(""),
    actief: str | None = Form(None),
):
    execute("""
        UPDATE org_functies
        SET functie_naam = :functie_naam,
            categorie = :categorie,
            entiteit = :entiteit,
            rapporteert_aan = :rapporteert_aan,
            reikwijdte = :reikwijdte,
            kernfocus = :kernfocus,
            doel = :doel,
            resultaatgebieden = :resultaatgebieden,
            kerntaken = :kerntaken,
            bevoegdheden = :bevoegdheden,
            kpis = :kpis,
            veiligheid_vca = :veiligheid_vca,
            documentverantwoordelijkheden = :documentverantwoordelijkheden,
            bron_doc_id = :bron_doc_id,
            actief = :actief,
            bijgewerkt_op = CURRENT_TIMESTAMP
        WHERE functie_code = :functie_code
    """, {
        "functie_code": functie_code,
        "functie_naam": functie_naam.strip(),
        "categorie": categorie.strip() or None,
        "entiteit": entiteit.strip() or None,
        "rapporteert_aan": rapporteert_aan.strip() or None,
        "reikwijdte": reikwijdte.strip() or None,
        "kernfocus": kernfocus.strip() or None,
        "doel": doel.strip() or None,
        "resultaatgebieden": resultaatgebieden.strip() or None,
        "kerntaken": kerntaken.strip() or None,
        "bevoegdheden": bevoegdheden.strip() or None,
        "kpis": kpis.strip() or None,
        "veiligheid_vca": veiligheid_vca.strip() or None,
        "documentverantwoordelijkheden": documentverantwoordelijkheden.strip() or None,
        "bron_doc_id": bron_doc_id.strip() or None,
        "actief": bool(actief),
    })

    return RedirectResponse(f"/org-admin/functies/{functie_code}/edit", status_code=303)


@router.get("/firmas-locaties", response_class=HTMLResponse)
def firmas_locaties_page():
    firmas = fetch_all("""
        SELECT *
        FROM org_firmas
        ORDER BY actief DESC, firma_naam
    """)

    locaties = fetch_all("""
        SELECT *
        FROM org_locaties
        ORDER BY actief DESC, firma_naam, locatie
    """)

    firma_options = "".join([
        f'<option value="{f.get("firma_id")}">{f.get("firma_naam")}</option>'
        for f in firmas
        if f.get("actief")
    ])

    firma_rows = ""
    for f in firmas:
        actief = "ja" if f.get("actief") else "nee"
        firma_rows += f"""
        <tr>
            <td>{f.get("firma_id")}</td>
            <td>{f.get("firma_naam") or ""}</td>
            <td>{actief}</td>
            <td>{f.get("opmerkingen") or ""}</td>
            <td><a href="/org-admin/firmas/{f.get("firma_id")}/edit">Bewerk</a></td>
        </tr>
        """

    locatie_rows = ""
    for l in locaties:
        actief = "ja" if l.get("actief") else "nee"
        locatie_rows += f"""
        <tr>
            <td>{l.get("locatie_id")}</td>
            <td>{l.get("firma_naam") or ""}</td>
            <td>{l.get("locatie") or ""}</td>
            <td>{l.get("telefoon") or ""}</td>
            <td>{l.get("email") or ""}</td>
            <td>{l.get("kvk_nummer") or ""}</td>
            <td>{l.get("btw_nummer") or ""}</td>
            <td>{l.get("plaats") or ""}</td>
            <td>{l.get("noodnummer") or ""}</td>
            <td>{actief}</td>
            <td><a href="/org-admin/locaties/{l.get("locatie_id")}/edit">Bewerk</a></td>
        </tr>
        """

    body = f"""
    <div class="card">
        <h2>Nieuwe firma</h2>
        <form method="post" action="/org-admin/firmas/create">
            <label>Firma naam</label>
            <input name="firma_naam" required placeholder="Promati">

            <label>Opmerkingen</label>
            <textarea name="opmerkingen"></textarea>

            <button type="submit">Firma opslaan</button>
        </form>
    </div>

    <table>
        <tr>
            <th>ID</th>
            <th>Firma</th>
            <th>Actief</th>
            <th>Opmerkingen</th>
            <th>Actie</th>
        </tr>
        {firma_rows}
    </table>

    <div class="card">
        <h2>Nieuwe locatie</h2>
        <form method="post" action="/org-admin/locaties/create">
            <label>Firma</label>
            <select name="firma_id" required>
                {firma_options}
            </select>

            <label>Locatie</label>
            <input name="locatie" required placeholder="Maldegem">

            <label>Telefoon</label>
            <input name="telefoon">

            <label>Email</label>
            <input name="email">

            <label>KVK nummer</label>
            <input name="kvk_nummer">

            <label>BTW nummer</label>
            <input name="btw_nummer">

            <label>Ondernemingsnummer</label>
            <input name="ondernemingsnummer">

            <label>Straat</label>
            <input name="straat">

            <label>Huisnummer</label>
            <input name="huisnummer">

            <label>Postcode</label>
            <input name="postcode">

            <label>Plaats</label>
            <input name="plaats">

            <label>Land</label>
            <input name="land" value="België">

            <label>Volledig adres / extra adresinfo</label>
            <textarea name="adres"></textarea>

            <label>Openingstijden</label>
            <textarea name="openingstijden"></textarea>

            <label>Noodnummer / alarmnummer</label>
            <input name="noodnummer">

            <label>Alarm-instructie</label>
            <textarea name="alarm_instructie"></textarea>

            <label>Opmerkingen</label>
            <textarea name="opmerkingen"></textarea>

            <button type="submit">Locatie opslaan</button>
        </form>
    </div>

    <table>
        <tr>
            <th>ID</th>
            <th>Firma</th>
            <th>Locatie</th>
            <th>Telefoon</th>
            <th>Email</th>
            <th>KVK</th>
            <th>BTW</th>
            <th>Plaats</th>
            <th>Noodnummer</th>
            <th>Actief</th>
            <th>Actie</th>
        </tr>
        {locatie_rows}
    </table>
    """
    return page("Firma's & locaties", body)

@router.post("/firmas/create")
def create_firma(
    firma_naam: str = Form(...),
    opmerkingen: str = Form(""),
):
    execute("""
        INSERT INTO org_firmas (
            firma_naam,
            actief,
            opmerkingen,
            created_at,
            updated_at
        )
        VALUES (
            :firma_naam,
            TRUE,
            :opmerkingen,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (firma_naam) DO UPDATE
        SET actief = TRUE,
            opmerkingen = EXCLUDED.opmerkingen,
            updated_at = CURRENT_TIMESTAMP
    """, {
        "firma_naam": firma_naam.strip(),
        "opmerkingen": opmerkingen or None,
    })

    return RedirectResponse("/org-admin/firmas-locaties", status_code=303)

@router.post("/locaties/create")
def create_locatie(
    firma_id: int = Form(...),
    locatie: str = Form(...),
    telefoon: str = Form(""),
    email: str = Form(""),
    kvk_nummer: str = Form(""),
    btw_nummer: str = Form(""),
    ondernemingsnummer: str = Form(""),
    straat: str = Form(""),
    huisnummer: str = Form(""),
    postcode: str = Form(""),
    plaats: str = Form(""),
    land: str = Form(""),
    adres: str = Form(""),
    openingstijden: str = Form(""),
    noodnummer: str = Form(""),
    alarm_instructie: str = Form(""),
    opmerkingen: str = Form(""),
):
    rows = fetch_all("""
        SELECT firma_naam
        FROM org_firmas
        WHERE firma_id = :firma_id
        LIMIT 1
    """, {"firma_id": firma_id})

    if not rows:
        return page("Fout", "<p>Firma niet gevonden.</p>")

    firma_naam = rows[0]["firma_naam"]

    execute("""
        INSERT INTO org_locaties (
            firma_id,
            firma_naam,
            locatie,
            telefoon,
            email,
            kvk_nummer,
            btw_nummer,
            ondernemingsnummer,
            straat,
            huisnummer,
            postcode,
            plaats,
            land,
            adres,
            openingstijden,
            noodnummer,
            alarm_instructie,
            actief,
            opmerkingen,
            created_at,
            updated_at
        )
        VALUES (
            :firma_id,
            :firma_naam,
            :locatie,
            :telefoon,
            :email,
            :kvk_nummer,
            :btw_nummer,
            :ondernemingsnummer,
            :straat,
            :huisnummer,
            :postcode,
            :plaats,
            :land,
            :adres,
            :openingstijden,
            :noodnummer,
            :alarm_instructie,
            TRUE,
            :opmerkingen,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (firma_naam, locatie) DO UPDATE
        SET firma_id = EXCLUDED.firma_id,
            telefoon = EXCLUDED.telefoon,
            email = EXCLUDED.email,
            kvk_nummer = EXCLUDED.kvk_nummer,
            btw_nummer = EXCLUDED.btw_nummer,
            ondernemingsnummer = EXCLUDED.ondernemingsnummer,
            straat = EXCLUDED.straat,
            huisnummer = EXCLUDED.huisnummer,
            postcode = EXCLUDED.postcode,
            plaats = EXCLUDED.plaats,
            land = EXCLUDED.land,
            adres = EXCLUDED.adres,
            openingstijden = EXCLUDED.openingstijden,
            noodnummer = EXCLUDED.noodnummer,
            alarm_instructie = EXCLUDED.alarm_instructie,
            actief = TRUE,
            opmerkingen = EXCLUDED.opmerkingen,
            updated_at = CURRENT_TIMESTAMP
    """, {
        "firma_id": firma_id,
        "firma_naam": firma_naam,
        "locatie": locatie.strip(),
        "telefoon": telefoon or None,
        "email": email or None,
        "kvk_nummer": kvk_nummer or None,
        "btw_nummer": btw_nummer or None,
        "ondernemingsnummer": ondernemingsnummer or None,
        "straat": straat or None,
        "huisnummer": huisnummer or None,
        "postcode": postcode or None,
        "plaats": plaats or None,
        "land": land or None,
        "adres": adres or None,
        "openingstijden": openingstijden or None,
        "noodnummer": noodnummer or None,
        "alarm_instructie": alarm_instructie or None,
        "opmerkingen": opmerkingen or None,
    })

    return RedirectResponse("/org-admin/firmas-locaties", status_code=303)

@router.get("/firmas/{firma_id}/edit", response_class=HTMLResponse)
def edit_firma_page(firma_id: int):
    rows = fetch_all("""
        SELECT *
        FROM org_firmas
        WHERE firma_id = :firma_id
        LIMIT 1
    """, {"firma_id": firma_id})

    if not rows:
        return page("Niet gevonden", "<p>Firma niet gevonden.</p>")

    f = rows[0]
    checked = "checked" if f.get("actief") else ""

    body = f"""
    <div class="card">
        <h2>Firma bewerken</h2>
        <form method="post" action="/org-admin/firmas/{firma_id}/update">
            <label>Firma naam</label>
            <input name="firma_naam" required value="{f.get("firma_naam") or ""}">

            <label>Opmerkingen</label>
            <textarea name="opmerkingen">{f.get("opmerkingen") or ""}</textarea>

            <label>
                <input type="checkbox" name="actief" value="true" {checked} style="width:auto;">
                Actief
            </label>

            <br><br>
            <button type="submit">Opslaan</button>
        </form>
    </div>
    """
    return page("Firma bewerken", body)

@router.post("/firmas/{firma_id}/update")
def update_firma(
    firma_id: int,
    firma_naam: str = Form(...),
    opmerkingen: str = Form(""),
    actief: str | None = Form(None),
):
    execute("""
        UPDATE org_firmas
        SET firma_naam = :firma_naam,
            opmerkingen = :opmerkingen,
            actief = :actief,
            updated_at = CURRENT_TIMESTAMP
        WHERE firma_id = :firma_id
    """, {
        "firma_id": firma_id,
        "firma_naam": firma_naam.strip(),
        "opmerkingen": opmerkingen or None,
        "actief": bool(actief),
    })

    execute("""
        UPDATE org_locaties
        SET firma_naam = :firma_naam,
            updated_at = CURRENT_TIMESTAMP
        WHERE firma_id = :firma_id
    """, {
        "firma_id": firma_id,
        "firma_naam": firma_naam.strip(),
    })

    return RedirectResponse("/org-admin/firmas-locaties", status_code=303)

@router.get("/locaties/{locatie_id}/edit", response_class=HTMLResponse)
def edit_locatie_page(locatie_id: int):
    rows = fetch_all("""
        SELECT *
        FROM org_locaties
        WHERE locatie_id = :locatie_id
        LIMIT 1
    """, {"locatie_id": locatie_id})

    if not rows:
        return page("Niet gevonden", "<p>Locatie niet gevonden.</p>")

    l = rows[0]
    checked = "checked" if l.get("actief") else ""

    firmas = fetch_all("""
        SELECT *
        FROM org_firmas
        ORDER BY actief DESC, firma_naam
    """)

    firma_options = ""
    for f in firmas:
        selected = "selected" if str(f.get("firma_id")) == str(l.get("firma_id")) else ""
        firma_options += f'<option value="{f.get("firma_id")}" {selected}>{f.get("firma_naam")}</option>'

    body = f"""
    <div class="card">
        <h2>Locatie bewerken</h2>
        <form method="post" action="/org-admin/locaties/{locatie_id}/update">
            <label>Firma</label>
            <select name="firma_id" required>
                {firma_options}
            </select>

            <label>Locatie</label>
            <input name="locatie" required value="{l.get("locatie") or ""}">

            <label>Telefoon</label>
            <input name="telefoon" value="{l.get("telefoon") or ""}">

            <label>Email</label>
            <input name="email" value="{l.get("email") or ""}">

            <label>KVK nummer</label>
            <input name="kvk_nummer" value="{l.get("kvk_nummer") or ""}">

            <label>BTW nummer</label>
            <input name="btw_nummer" value="{l.get("btw_nummer") or ""}">

            <label>Ondernemingsnummer</label>
            <input name="ondernemingsnummer" value="{l.get("ondernemingsnummer") or ""}">

            <label>Straat</label>
            <input name="straat" value="{l.get("straat") or ""}">

            <label>Huisnummer</label>
            <input name="huisnummer" value="{l.get("huisnummer") or ""}">

            <label>Postcode</label>
            <input name="postcode" value="{l.get("postcode") or ""}">

            <label>Plaats</label>
            <input name="plaats" value="{l.get("plaats") or ""}">

            <label>Land</label>
            <input name="land" value="{l.get("land") or ""}">

            <label>Volledig adres / extra adresinfo</label>
            <textarea name="adres">{l.get("adres") or ""}</textarea>

            <label>Openingstijden</label>
            <textarea name="openingstijden">{l.get("openingstijden") or ""}</textarea>

            <label>Noodnummer / alarmnummer</label>
            <input name="noodnummer" value="{l.get("noodnummer") or ""}">

            <label>Alarm-instructie</label>
            <textarea name="alarm_instructie">{l.get("alarm_instructie") or ""}</textarea>

            <label>Opmerkingen</label>
            <textarea name="opmerkingen">{l.get("opmerkingen") or ""}</textarea>

            <label>
                <input type="checkbox" name="actief" value="true" {checked} style="width:auto;">
                Actief
            </label>

            <br><br>
            <button type="submit">Opslaan</button>
        </form>
    </div>
    """
    return page("Locatie bewerken", body)

@router.post("/locaties/{locatie_id}/update")
def update_locatie(
    locatie_id: int,
    firma_id: int = Form(...),
    locatie: str = Form(...),
    telefoon: str = Form(""),
    email: str = Form(""),
    kvk_nummer: str = Form(""),
    btw_nummer: str = Form(""),
    ondernemingsnummer: str = Form(""),
    straat: str = Form(""),
    huisnummer: str = Form(""),
    postcode: str = Form(""),
    plaats: str = Form(""),
    land: str = Form(""),
    adres: str = Form(""),
    openingstijden: str = Form(""),
    noodnummer: str = Form(""),
    alarm_instructie: str = Form(""),
    opmerkingen: str = Form(""),
    actief: str | None = Form(None),
):
    rows = fetch_all("""
        SELECT firma_naam
        FROM org_firmas
        WHERE firma_id = :firma_id
        LIMIT 1
    """, {"firma_id": firma_id})

    if not rows:
        return page("Fout", "<p>Firma niet gevonden.</p>")

    firma_naam = rows[0]["firma_naam"]

    execute("""
        UPDATE org_locaties
        SET firma_id = :firma_id,
            firma_naam = :firma_naam,
            locatie = :locatie,
            telefoon = :telefoon,
            email = :email,
            kvk_nummer = :kvk_nummer,
            btw_nummer = :btw_nummer,
            ondernemingsnummer = :ondernemingsnummer,
            straat = :straat,
            huisnummer = :huisnummer,
            postcode = :postcode,
            plaats = :plaats,
            land = :land,
            adres = :adres,
            openingstijden = :openingstijden,
            noodnummer = :noodnummer,
            alarm_instructie = :alarm_instructie,
            opmerkingen = :opmerkingen,
            actief = :actief,
            updated_at = CURRENT_TIMESTAMP
        WHERE locatie_id = :locatie_id
    """, {
        "locatie_id": locatie_id,
        "firma_id": firma_id,
        "firma_naam": firma_naam,
        "locatie": locatie.strip(),
        "telefoon": telefoon or None,
        "email": email or None,
        "kvk_nummer": kvk_nummer or None,
        "btw_nummer": btw_nummer or None,
        "ondernemingsnummer": ondernemingsnummer or None,
        "straat": straat or None,
        "huisnummer": huisnummer or None,
        "postcode": postcode or None,
        "plaats": plaats or None,
        "land": land or None,
        "adres": adres or None,
        "openingstijden": openingstijden or None,
        "noodnummer": noodnummer or None,
        "alarm_instructie": alarm_instructie or None,
        "opmerkingen": opmerkingen or None,
        "actief": bool(actief),
    })

    return RedirectResponse("/org-admin/firmas-locaties", status_code=303)

@router.get("/location-info")
def location_info(
    firma: str | None = None,
    locatie: str | None = None,
    q: str | None = None,
):
    q_norm = (q or "").lower()
    firma_norm = (firma or "").strip() or "Promati"
    locatie_norm = (locatie or "").strip()

    if not locatie_norm:
        if "breda" in q_norm:
            locatie_norm = "Breda"
        elif "maldegem" in q_norm:
            locatie_norm = "Maldegem"
        elif "algemeen" in q_norm or "promati" in q_norm:
            locatie_norm = "Algemeen"

    sql = """
        SELECT
            firma_naam,
            locatie,
            telefoon,
            email,
            kvk_nummer,
            btw_nummer,
            ondernemingsnummer,
            straat,
            huisnummer,
            postcode,
            plaats,
            land,
            adres,
            openingstijden,
            noodnummer,
            alarm_instructie,
            opmerkingen
        FROM org_locaties
        WHERE actief = TRUE
          AND LOWER(firma_naam) = LOWER(:firma_naam)
    """

    params = {
        "firma_naam": firma_norm,
    }

    if locatie_norm:
        sql += " AND LOWER(locatie) = LOWER(:locatie)"
        params["locatie"] = locatie_norm

    sql += " ORDER BY locatie LIMIT 10"

    rows = fetch_all(sql, params)

    if not rows:
        return {
            "status": "not_found",
            "query": q,
            "firma": firma_norm,
            "locatie": locatie_norm,
            "message": "Geen actieve locatiegegevens gevonden."
        }

    return {
        "status": "ok",
        "query": q,
        "firma": firma_norm,
        "locatie": locatie_norm,
        "results": rows,
        "write_actions_available": False,
    }

@router.get("/test", response_class=HTMLResponse)
def test_page(
    q: str = "",
    test_type: str = "auto",
):
    result_html = ""

    if q:
        q_lower = q.lower()

        if test_type == "location" or any(word in q_lower for word in [
            "adres",
            "telefoon",
            "btw",
            "kvk",
            "ondernemingsnummer",
            "openingstijden",
            "alarm",
            "alarmmelding",
            "noodnummer",
        ]):
            endpoint = "/analysis/context/org/location-info"
        else:
            endpoint = "/analysis/context/org/internal-help"

        q_encoded = quote_plus(q)

        result_html = f"""
        <div class="card">
            <h2>Testresultaat</h2>
            <p><strong>Gekozen endpoint:</strong> {endpoint}</p>
            <p>
                <a target="_blank" href="{endpoint}?q={q_encoded}">
                    Open JSON-resultaat
                </a>
            </p>
            <iframe
                src="{endpoint}?q={q_encoded}"
                style="width:100%; height:400px; border:1px solid #ccc; background:white;">
            </iframe>
        </div>
        """

    body = f"""
    <div class="card">
        <h2>PromatiGPT testpagina</h2>
        <form method="get" action="/org-admin/test">
            <label>Vraag</label>
            <input name="q" value="{q}" placeholder="Bijvoorbeeld: ik kan niet printen">

            <label>Type test</label>
            <select name="test_type">
                <option value="auto" {"selected" if test_type == "auto" else ""}>Automatisch kiezen</option>
                <option value="internal" {"selected" if test_type == "internal" else ""}>Interne hulp / routering</option>
                <option value="location" {"selected" if test_type == "location" else ""}>Firma / locatiegegevens</option>
            </select>

            <button type="submit">Testen</button>
        </form>
    </div>

    <div class="card">
        <h2>Voorbeelden</h2>
        <p><a href="/org-admin/test?q=ik kan niet printen">ik kan niet printen</a></p>
        <p><a href="/org-admin/test?q=wifi werkt niet">wifi werkt niet</a></p>
        <p><a href="/org-admin/test?q=alarmmelding maldegem">alarmmelding maldegem</a></p>
        <p><a href="/org-admin/test?q=wat is het adres van breda">wat is het adres van breda</a></p>
    </div>

    {result_html}
    """
    return page("Test", body)


def select_options_rag_taken(selected: str | None = None) -> str:
    rows = fetch_all("""
        SELECT taak_code, taak_naam, categorie
        FROM org_taken
        WHERE actief = TRUE
        ORDER BY categorie, taak_naam
    """)

    html = '<option value="">-- geen taak gekoppeld --</option>'

    for r in rows:
        code = r.get("taak_code") or ""
        naam = r.get("taak_naam") or code
        categorie = r.get("categorie") or ""
        label = f"{categorie} - {naam} ({code})" if categorie else f"{naam} ({code})"
        sel = "selected" if selected == code else ""
        html += f'<option value="{code}" {sel}>{label}</option>'

    return html


@router.get("/rag-docs", response_class=HTMLResponse)
def rag_docs_page():
    rows = fetch_all("""
        SELECT
            d.*,
            t.taak_naam
        FROM org_rag_documenten d
        LEFT JOIN org_taken t
            ON t.taak_code = d.taak_code
        ORDER BY d.actief DESC, d.categorie, d.titel
    """)

    table_rows = ""

    for r in rows:
        actief = "ja" if r.get("actief") else "nee"
        gepubliceerd = r.get("laatst_gepubliceerd_op") or ""
        status = r.get("laatste_publicatie_status") or ""

        table_rows += f"""
        <tr>
            <td>{r.get("doc_id")}</td>
            <td>{r.get("titel") or ""}</td>
            <td>{r.get("categorie") or ""}</td>
            <td>{r.get("taak_code") or ""}</td>
            <td>{r.get("taak_naam") or ""}</td>
            <td>{actief}</td>
            <td>{gepubliceerd}</td>
            <td>{status}</td>
            <td>
                <a href="/org-admin/rag-docs/{r.get("doc_id")}/edit">Bewerk</a>
                |
                <form method="post" action="/org-admin/rag-docs/{r.get("doc_id")}/publish" style="display:inline;">
                    <button type="submit">Publiceer</button>
                </form>
            </td>
        </tr>
        """

    body = f"""
    <div class="card">
        <h2>Nieuw RAG-document</h2>

        <form method="post" action="/org-admin/rag-docs/create">
            <label>doc_id</label>
            <input name="doc_id" placeholder="bijv. rag_org_info_mailbox" required>

            <label>Titel</label>
            <input name="titel" placeholder="bijv. Procedure info mailbox" required>

            <label>Categorie</label>
            <input name="categorie" placeholder="bijv. Administratie">

            <label>Gekoppelde taak</label>
            <select name="taak_code">
                {select_options_rag_taken()}
            </select>

            <label>Markdown inhoud</label>
            <textarea name="inhoud_md" rows="18" placeholder="# Procedure ..." required></textarea>

            <button type="submit">Opslaan</button>
        </form>
    </div>

    <table>
        <tr>
            <th>doc_id</th>
            <th>Titel</th>
            <th>Categorie</th>
            <th>Taak code</th>
            <th>Taak</th>
            <th>Actief</th>
            <th>Laatst gepubliceerd</th>
            <th>Status</th>
            <th>Actie</th>
        </tr>
        {table_rows}
    </table>
    """

    return page("RAG documenten", body)


@router.post("/rag-docs/create")
def create_rag_doc(
    doc_id: str = Form(...),
    titel: str = Form(...),
    categorie: str = Form(""),
    taak_code: str = Form(""),
    inhoud_md: str = Form(...),
):
    doc_id_clean = doc_id.strip()

    execute("""
        INSERT INTO org_rag_documenten (
            doc_id,
            titel,
            categorie,
            taak_code,
            inhoud_md,
            actief,
            aangemaakt_op,
            bijgewerkt_op
        )
        VALUES (
            :doc_id,
            :titel,
            :categorie,
            :taak_code,
            :inhoud_md,
            TRUE,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (doc_id) DO UPDATE
        SET titel = EXCLUDED.titel,
            categorie = EXCLUDED.categorie,
            taak_code = EXCLUDED.taak_code,
            inhoud_md = EXCLUDED.inhoud_md,
            actief = TRUE,
            bijgewerkt_op = CURRENT_TIMESTAMP
    """, {
        "doc_id": doc_id_clean,
        "titel": titel.strip(),
        "categorie": categorie.strip() or None,
        "taak_code": taak_code.strip() or None,
        "inhoud_md": inhoud_md,
    })

    return RedirectResponse("/org-admin/rag-docs", status_code=303)

def get_rag_chunks_for_doc(doc_id: str) -> dict:
    try:
        response = requests.post(
            f"{api_base_url()}/rag/chunks",
            json={
                "doc_id": doc_id,
                "limit": 200,
            },
            timeout=30,
        )

        try:
            payload = response.json()
        except Exception:
            payload = {
                "status": "error",
                "raw_response": response.text,
            }

        if response.status_code >= 400:
            return {
                "status": "error",
                "message": f"HTTP {response.status_code}",
                "payload": payload,
                "chunks": [],
                "total_count": 0,
            }

        return payload

    except Exception as e:
        return {
            "status": "exception",
            "message": str(e),
            "chunks": [],
            "total_count": 0,
        }


@router.get("/rag-docs/{doc_id}/edit", response_class=HTMLResponse)
def edit_rag_doc_page(doc_id: str):
    rows = fetch_all("""
        SELECT *
        FROM org_rag_documenten
        WHERE doc_id = :doc_id
        LIMIT 1
    """, {"doc_id": doc_id})

    if not rows:
        return page("Niet gevonden", "<p>RAG-document niet gevonden.</p>")

    r = rows[0]
    checked = "checked" if r.get("actief") else ""

    chunks_payload = get_rag_chunks_for_doc(doc_id)
    chunks = chunks_payload.get("chunks") or []
    total_chunks = chunks_payload.get("total_count") or 0
    chunks_status = chunks_payload.get("status") or "onbekend"

    chunk_rows = ""

    for c in chunks:
        chunk_index = c.get("chunk_index")
        point_id = html.escape(str(c.get("point_id") or ""))
        text_length = c.get("text_length") or 0
        preview = html.escape(c.get("preview") or "")
        full_text = html.escape(c.get("text") or "")

        chunk_rows += f"""
        <tr>
            <td>{chunk_index}</td>
            <td>{text_length}</td>
            <td><code>{point_id}</code></td>
            <td>
                <details>
                    <summary>{preview}</summary>
                    <pre style="white-space:pre-wrap; max-height:400px; overflow:auto;">{full_text}</pre>
                </details>
            </td>
        </tr>
        """

    if not chunk_rows:
        chunk_rows = """
        <tr>
            <td colspan="4">Geen actieve chunks gevonden voor dit doc_id.</td>
        </tr>
        """

    chunks_html = f"""
    <div class="card">
        <h2>Actieve RAG chunks</h2>
        <p>
            Status: <strong>{html.escape(str(chunks_status))}</strong><br>
            Totaal aantal chunks in Qdrant voor dit doc_id: <strong>{total_chunks}</strong>
        </p>

        <table>
            <tr>
                <th>Chunk index</th>
                <th>Tekens</th>
                <th>Point ID</th>
                <th>Tekst</th>
            </tr>
            {chunk_rows}
        </table>
    </div>
    """

    body = f"""
    <div class="card">
        <h2>RAG-document bewerken</h2>

        <form method="post" action="/org-admin/rag-docs/{r.get("doc_id")}/update">
            <label>doc_id</label>
            <input value="{r.get("doc_id")}" disabled>

            <label>Titel</label>
            <input name="titel" value="{r.get("titel") or ""}" required>

            <label>Categorie</label>
            <input name="categorie" value="{r.get("categorie") or ""}">

            <label>Gekoppelde taak</label>
            <select name="taak_code">
                {select_options_rag_taken(r.get("taak_code"))}
            </select>

            <label>Markdown inhoud</label>
            <textarea name="inhoud_md" rows="26" required>{r.get("inhoud_md") or ""}</textarea>

            <label>
                <input type="checkbox" name="actief" value="1" {checked} style="width:auto;">
                Actief
            </label>

            <button type="submit">Wijzigingen opslaan</button>
        </form>

        <form method="post" action="/org-admin/rag-docs/{r.get("doc_id")}/publish" style="margin-top:15px;">
            <button type="submit">Publiceer naar RAG</button>
        </form>

        <p class="small">
            Laatst gepubliceerd: {r.get("laatst_gepubliceerd_op") or "nog niet"}<br>
            Status: {r.get("laatste_publicatie_status") or ""}
        </p>
    </div>

    {chunks_html}
    """

    return page(f"RAG-document: {r.get('titel')}", body)


@router.post("/rag-docs/{doc_id}/update")
def update_rag_doc(
    doc_id: str,
    titel: str = Form(...),
    categorie: str = Form(""),
    taak_code: str = Form(""),
    inhoud_md: str = Form(...),
    actief: str | None = Form(None),
):
    execute("""
        UPDATE org_rag_documenten
        SET titel = :titel,
            categorie = :categorie,
            taak_code = :taak_code,
            inhoud_md = :inhoud_md,
            actief = :actief,
            bijgewerkt_op = CURRENT_TIMESTAMP
        WHERE doc_id = :doc_id
    """, {
        "doc_id": doc_id,
        "titel": titel.strip(),
        "categorie": categorie.strip() or None,
        "taak_code": taak_code.strip() or None,
        "inhoud_md": inhoud_md,
        "actief": bool(actief),
    })

    return RedirectResponse(f"/org-admin/rag-docs/{doc_id}/edit", status_code=303)


@router.post("/rag-docs/{doc_id}/publish")
def publish_rag_doc(doc_id: str):
    rows = fetch_all("""
        SELECT *
        FROM org_rag_documenten
        WHERE doc_id = :doc_id
        LIMIT 1
    """, {"doc_id": doc_id})

    if not rows:
        return page("Niet gevonden", "<p>RAG-document niet gevonden.</p>")

    r = rows[0]

    if not r.get("actief"):
        return page("Niet actief", "<p>Dit RAG-document is niet actief en wordt daarom niet gepubliceerd.</p>")

    payload = {
        "doc_id": r.get("doc_id"),
        "text": r.get("inhoud_md") or "",
        "chunk_size": 1200,
        "chunk_overlap": 200,
    }

    try:
        response = requests.post(
            f"{api_base_url()}/rag/replace",
            json=payload,
            timeout=120,
        )

        try:
            response_json = response.json()
        except Exception:
            response_json = {"raw_response": response.text}

        status_text = "replace_ok" if response.status_code < 400 else f"replace_fout_http_{response.status_code}"

        execute("""
            UPDATE org_rag_documenten
            SET laatst_gepubliceerd_op = CURRENT_TIMESTAMP,
                laatste_publicatie_status = :status,
                laatste_publicatie_response = CAST(:response AS jsonb),
                bijgewerkt_op = CURRENT_TIMESTAMP
            WHERE doc_id = :doc_id
        """, {
            "doc_id": doc_id,
            "status": status_text,
            "response": json.dumps(response_json, ensure_ascii=False),
        })

        if response.status_code >= 400:
            return page(
                "Publicatie fout",
                f"""
                <div class="card">
                    <p>Publicatie naar RAG faalde.</p>
                    <pre>{json.dumps(response_json, ensure_ascii=False, indent=2)}</pre>
                    <p><a href="/org-admin/rag-docs/{doc_id}/edit">Terug</a></p>
                </div>
                """
            )

        return RedirectResponse(f"/org-admin/rag-docs/{doc_id}/edit", status_code=303)

    except Exception as e:
        execute("""
            UPDATE org_rag_documenten
            SET laatst_gepubliceerd_op = CURRENT_TIMESTAMP,
                laatste_publicatie_status = :status,
                laatste_publicatie_response = CAST(:response AS jsonb),
                bijgewerkt_op = CURRENT_TIMESTAMP
            WHERE doc_id = :doc_id
        """, {
            "doc_id": doc_id,
            "status": "exception",
            "response": json.dumps({"error": str(e)}, ensure_ascii=False),
        })

        return page(
            "Publicatie fout",
            f"""
            <div class="card">
                <p>Publicatie naar RAG gaf een fout.</p>
                <pre>{str(e)}</pre>
                <p><a href="/org-admin/rag-docs/{doc_id}/edit">Terug</a></p>
            </div>
            """
        )