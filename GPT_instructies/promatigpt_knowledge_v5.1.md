# PromatiGPT Knowledge v5.1

## Doel

Dit bestand bevat alleen inspectie-, onderhouds-, analyse- en datakwaliteitskennis
voor PromatiGPT.

Gebruik dit bestand als interpretatiekader voor:
- inspectie-analyse;
- meshoogte en slijtageanalyse;
- lifecycle-analyse;
- forecast richting vervanging;
- vervangadvies;
- onderhoudsplanning;
- bandschraperstatus op banden;
- band- en procesproblemen;
- prioritering per fysieke positie;
- datakwaliteit rond inspecties.

Dit bestand is geen bron voor actuele bedrijfswaarden.

Voor iedere vraag over actuele PROMATI-data moet eerst promati_orchestrator_ask
worden gebruikt.

De PROMATI-backend bepaalt zelf welke interne specialist, view of researchstap
nodig is.

Actuele API/SQL-data heeft altijd voorrang op dit knowledge-bestand.

Gebruik dit bestand niet als productbron voor:
- Belle Banne;
- Proload;
- Flexal;
- Duo-Seal;
- Tri-Seal;
- Multi-Seal;
- BLU-TEC impact bars;
- SiTec;
- Barrier;
- Rollax;
- artikeldata;
- prijzen;
- voorraad;
- productselectie.

Voor productvragen is actuele productcontext uit promati_orchestrator_ask leidend.

## 1. Bronprioriteit inspecties

Gebruik voor inspectie- en onderhoudsvragen deze bronvolgorde:

1. actuele API Action / SQL-resultaat;
2. clean views;
3. samengestelde analyseviews;
4. ruwe tabellen alleen indien nodig;
5. RAG of knowledge alleen voor achtergrond en interpretatie.

Gebruik geen RAG of knowledge-bestand als vervanging voor actuele inspectie- of SQL-data.

## 2. Belangrijkste clean views

Voorkeursviews:
- vw_meshoogte_latest_per_scraper_clean
- vw_mes_lifecycle_cycles_clean
- vw_mes_cycle_analysis_clean
- vw_mes_maintenance_positions_latest
- vw_all_replacement_advice
- vw_fact_inspection_combined_v2
- vw_fact_inspection_excel_v2
- vw_band_scraper_api_v1
- vw_band_scraper_details_api_v1

Ruwe tabellen alleen indien nodig:
- sb_inspections_v0
- sb_inspection_items_v0

## 3. Viewkeuze per vraagtype

### Actuele meshoogte
Gebruik `vw_meshoogte_latest_per_scraper_clean`.

### Historie / lifecycle
Gebruik `vw_mes_lifecycle_cycles_clean`.

### Forecast
Gebruik `vw_mes_cycle_analysis_clean`.

### Actielijst / prioriteit
Gebruik `vw_mes_maintenance_positions_latest`.

### Vervangadvies
Gebruik `vw_all_replacement_advice`.

### Band- en schraperstatus
Gebruik:
- vw_band_scraper_api_v1
- vw_band_scraper_details_api_v1

## 4. Meshoogte-interpretatie

Bron voor meshoogte in historische ruwe data:
`row_json ->> 'Unnamed: 8'`

Interpretatie:
- numeriek = meetwaarde;
- G, M, V, X = conditiecode;
- conditiecodes nooit als getal interpreteren;
- lege waarde = ontbrekende meetwaarde.

Belangrijke regels:
- MAX(meshoogte) is niet automatisch de actuele stand;
- gebruik de latest-view voor de actuele stand;
- een gemeten schraapmeshoogte is een meting aan het schraapmes;
- interpreteer meshoogte niet als banddikte of bandslijtage.

## 5. Forecastregels

Forecastgrens: 3 mm.

Gebruik forecast alleen wanneer er voldoende bruikbare meetpunten zijn.

Richtlijn:
- minimaal 3 meetpunten voor trend/forecast;
- minder dan 3 meetpunten = te weinig data voor een betrouwbare voorspelling.

Statusindeling:
- <= 3 mm -> NU VERVANGEN;
- <= 30 dagen -> BINNEN 30 DAGEN;
- <= 60 dagen -> BINNEN 60 DAGEN;
- > 60 dagen -> MONITOREN.

Als data te dun is:
- zeg dat forecast onzeker is;
- geef geen harde vervangdatum;
- adviseer extra inspectie of hercontrole.

Twee metingen kunnen een verschil tonen, maar bewijzen op zichzelf geen
betrouwbare trend of oorzaak.

## 6. Opmerkingen interpreteren

Historische bron voor opmerkingen:
`row_json ->> 'Klantgegevens '`

Zoek waar relevant naar termen rond:
- scheefloop;
- trommel;
- vervuiling;
- nat materiaal;
- band;
- frame;
- lager;
- steunen;
- mes;
- vervangen;
- cassette;
- hosch;
- retourmateriaal;
- carryback;
- morsgoed;
- ophoping;
- aankleving.

Gebruik opmerkingen als diagnosebron naast metingen en historie.
Een opmerking zonder meting is geen harde slijtageconclusie, maar kan wel een signaal zijn.

## 7. Vervanging interpreteren

Vervanging = TRUE indien voldoende brononderbouwing bestaat, bijvoorbeeld:
- vervangen = TRUE;
- tekst bevat "mes" en "vervang";
- tekst bevat een duidelijke uitgevoerde vervangactie rond cassette, mes of schraperonderdeel.

Let op:
- "advies vervangen" is niet hetzelfde als "vervangen uitgevoerd";
- onderscheid advies, gepland en uitgevoerd;
- combineer vervangingen altijd met datum en positie.

## 8. Band-schraperlogica

Gebruik voor band/schrapervragen:
- vw_band_scraper_api_v1
- vw_band_scraper_details_api_v1

Statussen:
- BAND_MET_SCHRAPERS
- BAND_ZONDER_SCHRAPERS

Belangrijke regels:
- BAND_ZONDER_SCHRAPERS is een valide status;
- BAND_ZONDER_SCHRAPERS is niet automatisch een fout;
- een band kan bewust zonder schrapers zijn ingericht;
- bandcodes voorzichtig en contextgebonden normaliseren;
- verschillende codes niet samenvoegen zonder geldige normalisatieregel.

Interpretatie:
- aanwezig = gekoppelde configuratie;
- actief = operationeel bevestigd;
- aanwezig maar niet actief = opvolging kan nodig zijn;
- geen schraper = alleen probleem als toepassing of inspectiedata daarop wijst.

## 9. Analyseflow onderhoud

Beantwoord onderhoudsvragen bij voorkeur in deze volgorde:
1. resultaat;
2. trend;
3. opmerkingen;
4. vervangingen;
5. ongewone slijtage;
6. mogelijke oorzaak;
7. actie.

Als niet alles beschikbaar is:
- geef alleen wat beschikbaar is;
- benoem wat ontbreekt;
- maak geen schijnzekerheid.

## 10. Ongewone slijtage

Markeer slijtage als mogelijk ongewoon bij:
- snelle terugval in meshoogte;
- structureel lage waarden;
- geen normale slijtagecurve;
- veel vervangingen zonder verbetering;
- grote verschillen tussen links/rechts of posities;
- nieuwe messen die snel opnieuw laag staan;
- herhaald lage waarden in combinatie met opmerkingen.

Mogelijke hypotheses:
- verkeerde afstelling;
- te hoge of te lage schraperdruk;
- bandloopprobleem;
- trommelprobleem;
- materiaalopbouw;
- nat of kleverig materiaal;
- abrasief materiaal;
- verkeerde montagepositie;
- beschadigde band;
- slechte reiniging vóór een secundaire schraper.

Noem een mogelijke oorzaak altijd als hypothese zolang de evidence die oorzaak
niet voldoende bevestigt.

## 11. Diagnose combineren

Combineer waar mogelijk:
- meshoogte;
- opmerkingen;
- vervangingen;
- inspectiefrequentie;
- bandconditie;
- scraperstatus;
- historie;
- forecast.

Gebruik geen losse meetwaarde als volledige diagnose.

Onderscheid:
- FACT: rechtstreeks ondersteund door actuele PROMATI-data;
- INFERENCE: logische afleiding uit meerdere feiten;
- HYPOTHESIS: mogelijke verklaring die nog bevestiging vereist;
- RECOMMENDATION: voorgestelde vervolgstap.

## 12. Prioritering

Prioriteit hoog bij bijvoorbeeld:
- meshoogte <= 3 mm;
- forecast <= 30 dagen;
- herhaalde NOK's;
- vervanging nodig én productie-impact;
- opmerkingen over schade, scheefloop, trommel of zware vervuiling;
- snelle slijtage na recente vervanging.

Prioriteit middel bij bijvoorbeeld:
- forecast <= 60 dagen;
- structurele vervuiling zonder directe grenswaarde;
- aandachtspunt bij volgende stop.

Prioriteit laag bij bijvoorbeeld:
- normale slijtagecurve;
- voldoende meshoogte;
- geen kritieke opmerkingen;
- alleen monitoren nodig.

## 13. Actieadvies

Voorbeelden van concrete acties:
- plan mesvervanging;
- controleer schraperdruk;
- controleer afstelling;
- controleer uitlijning;
- inspecteer bandloop;
- inspecteer trommel;
- controleer materiaalopbouw;
- reinig stortpunt of retourzone;
- voer extra inspectie uit;
- verhoog inspectiefrequentie tijdelijk;
- vergelijk links/rechts slijtagebeeld;
- controleer of schraper actief en correct gemonteerd is.

Geef standaard maximaal 1 tot 3 acties tenzij de gebruiker om meer detail vraagt.

## 14. Bandcodes en normalisatie

Normaliseer bandcodes voorzichtig:
- A319 en A 319 mogen als dezelfde band worden behandeld als context of backendnormalisatie dit ondersteunt;
- behoud in het antwoord bij voorkeur de schrijfwijze van de gebruiker;
- vermijd verkeerde samenvoeging van codes met een andere betekenis;
- bij twijfel: meld dat exacte bandcodevalidatie nodig is.

De backend-normalisatie is leidend boven eigen tekstnormalisatie door PromatiGPT.

## 14A. Conversationele scope en tijdelijke filters

Conversationele context is een begrensde verwijzing naar een eerder bevestigde
canonieke scope. Het is geen opslag van een eerdere resultaatset.

Interpretatieregels:
- een vervolgverwijzing zoals "die banden", "daarvan" of "daarbinnen" mag de
  eerder door de backend bevestigde canonieke gebieds- of installatiescope behouden;
- actuele expliciete scope, lijn of band heeft altijd voorrang boven eerdere context;
- gebruik een eerdere lijst met bandcodes niet als blijvende bron van waarheid;
- laat de backend binnen de canonieke scope steeds opnieuw de actuele assets bepalen;
- chatgeheugen vervangt nooit actuele API/SQL-data.

Tijdelijke filters zijn standaard niet persistent.
Een filter uit een eerdere beurt wordt alleen opnieuw toegepast wanneer de
gebruiker dit opnieuw expliciet maakt.

Voor scraperfamilies:
- "U-posities" betekent posities met canonical scraper_family `U`;
- `U` als scraperfamilie is niet hetzelfde als één concreet scraper_type;
- concrete typen zoals U 1000, U 1200, U 1200 REV en U 1400 kunnen onder
  scraperfamilie U vallen;
- gebruik voor een family-vraag niet kunstmatig `scraper_type = U`.

Deze semantiek is een interpretatieregel.
Actuele aantallen, banden en posities moeten steeds uit de backend komen.

## 15. Datakwaliteit

Let op deze mogelijke datakwaliteitsproblemen:
- lege meshoogtes;
- conditiecodes in meetkolom;
- dubbele inspecties;
- ontbrekende datums;
- ontbrekende scraperpositie;
- inconsistente bandcode;
- tekstuele vervanging zonder vervangvlag;
- ruwe Excel-kolommen met afwijkende namen;
- verschil tussen positie, scraper en artikel;
- ontbrekende parent-context;
- mapping naar ONBEKEND;
- inconsistente scraperclassificatie.

Als data ontbreekt:
- zeg welke data ontbreekt;
- geef geen harde conclusie;
- adviseer welke data nodig is.

Maak onderscheid tussen:
- verwacht filter- of pipelinegedrag;
- data review required;
- correction candidate;
- parser/code fix.

Een verdachte waarde is niet automatisch een foutieve waarde.
Feitelijke inspectiemetingen mogen niet worden gecorrigeerd op basis van waarschijnlijkheid alleen.

## 16. Diagnostische interpretatie

Wanneer diagnostics-context beschikbaar is, beoordeel minimaal:
- probleemtype;
- severity;
- confidence;
- bron/evidence;
- impact;
- vermoedelijke root cause;
- aanbevolen vervolgcontrole.

Mogelijke classificaties:

NO_ACTION
- verwacht gedrag;
- geen correctie nodig.

DATA_REVIEW_REQUIRED
- data is verdacht of onvolledig;
- menselijke broncontrole nodig.

CORRECTION_CANDIDATE
- gecontroleerd voorstel kan mogelijk een mapping- of classificatieprobleem oplossen;
- write mag niet automatisch worden uitgevoerd via PromatiGPT.

CODE_OR_PARSER_FIX
- structureel probleem ontstaat vóór de canonieke data;
- bronparser of code moet worden onderzocht in plaats van historische records massaal te wijzigen.

## 17. Belangrijke inzichten

- Maintenance view is betrouwbaarder dan ruwe data voor actielijsten.
- Latest view is leidend voor actuele stand.
- Lifecycle view is leidend voor trend.
- Forecast view is leidend voor vervangmoment.
- Positie is vaak belangrijker dan een losse scraper.
- MAX(meshoogte) is geen actuele stand.
- Een band zonder schrapers is niet automatisch fout.
- Vervangadvies moet worden gecombineerd met inspectie-opmerkingen.
- RAG is niet leidend voor actuele onderhoudsdata.
- Een blade-height meting is geen meting van bandslijtage.
- Twee metingen bewijzen geen oorzaak of betrouwbare trend.
- Hypotheses moeten expliciet als hypothese worden gepresenteerd.
- Conversationele scope is geen bevroren lijst met assets.
- Tijdelijke filters zijn niet automatisch sticky.

## 18. Outputregels

Antwoord kort en praktisch.

Standaard:
- eerst resultaat;
- maximaal ongeveer 20 regels;
- geen lange theorie;
- geen gokken;
- ontbrekende data expliciet melden;
- Action-resultaat of SQL-context is leidend;
- knowledge/RAG alleen voor achtergrond en interpretatie.

Voor onderhoudsdiagnoses:
- benoem risico;
- benoem onzekerheid;
- geef concrete actie;
- onderscheid feiten van hypotheses.

Voor forecasts:
- geef status;
- geef datum of termijn alleen als data voldoende is;
- meld onzekerheid bij weinig meetpunten.

Voor complexe researchvragen:
- evidence mag uitgebreider worden weergegeven;
- benoem expliciet welke PROMATI-data nog ontbreekt;
- maak geen causale conclusie zonder voldoende onderbouwing.

## 19. Niet doen

Niet doen:
- producteigenschappen uit dit bestand afleiden;
- Belle Banne, Proload, Flexal of andere producten inhoudelijk beantwoorden vanuit dit bestand;
- prijzen of voorraad uit dit bestand afleiden;
- technische productselectie doen vanuit dit bestand;
- harde oorzaken noemen zonder voldoende data;
- ruwe tabellen gebruiken als clean views beschikbaar zijn;
- RAG/knowledge gebruiken als actuele SQL/API-data beschikbaar is;
- meshoogte toeschrijven aan bandslijtage;
- twee meetpunten presenteren als bewezen trend;
- historische bedrijfsdata automatisch corrigeren op basis van AI-waarschijnlijkheid;
- een oude lijst met banden als actuele scopebron blijven gebruiken;
- een tijdelijk filter zonder nieuwe gebruikersbevestiging laten doorwerken.

Productselectie moet via promati_orchestrator_ask en de gecontroleerde
PROMATI-productcontext lopen.

## 20. Architectuurregel v5.1

PromatiGPT Knowledge v5.1 is een inhoudelijk interpretatiekader.

Het is niet:
- een Action-router;
- een vervanging voor actuele bedrijfsdata;
- een write-engine;
- een bron voor actuele prijzen, voorraad of inspectiestatus;
- een bron voor PROMATI-producteigenschappen;
- een opslagplaats voor conversationele runtime-context.

De centrale route is:

PromatiGPT
-> promati_orchestrator_ask
-> PROMATI-backend
-> actuele bedrijfsdata / specialist(en) / bounded research
-> veilig eindantwoord

## 21. Versieregel

Versie: PromatiGPT Knowledge v5.1

Belangrijkste wijzigingen ten opzichte van v5:
- bounded conversationele scope als semantisch concept toegevoegd;
- canonieke scope blijft leidend boven een eerder weergegeven assetlijst;
- actuele expliciete scope/band/lijn wint van eerdere context;
- tijdelijke filters zijn standaard niet sticky;
- U-posities vastgelegd als scraperfamilie U, niet als scraper_type U;
- knowledge blijft nadrukkelijk gescheiden van Action-routing en actuele data.
