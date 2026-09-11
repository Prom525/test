\# PromatiGPT Knowledge v4



\## Doel



Dit bestand bevat alleen inspectie-, onderhouds- en analysekennis voor PromatiGPT.



Gebruik dit bestand voor:

\- inspectie-analyse

\- meshoogte / slijtageanalyse

\- lifecycle-analyse

\- forecast richting vervanging

\- vervangadvies

\- onderhoudsplanning

\- bandschraperstatus op banden

\- band- en procesproblemen

\- prioritering per fysieke positie

\- datakwaliteit rond inspecties



Gebruik dit bestand niet als productbron voor:

\- Belle Banne

\- Proload

\- Flexal

\- Duo-Seal

\- Tri-Seal

\- Multi-Seal

\- BLU-TEC impact bars

\- SiTec

\- Barrier

\- Rollax

\- artikeldata

\- prijzen

\- voorraad

\- productselectie



Voor productvragen is product\_assistant\_ask leidend.



\---



\## 1. Bronprioriteit inspecties



Gebruik voor inspectie- en onderhoudsvragen deze bronvolgorde:



1\. API Action / SQL-resultaat

2\. Clean views

3\. Samengestelde analyseviews

4\. Ruwe tabellen alleen indien nodig

5\. RAG alleen voor achtergrond of procedurekennis



Gebruik geen RAG wanneer actuele inspectie- of SQL-data beschikbaar is.



\---



\## 2. Belangrijkste clean views



Voorkeursviews:



\- vw\_meshoogte\_latest\_per\_scraper\_clean

\- vw\_mes\_lifecycle\_cycles\_clean

\- vw\_mes\_cycle\_analysis\_clean

\- vw\_mes\_maintenance\_positions\_latest

\- vw\_all\_replacement\_advice

\- vw\_fact\_inspection\_combined\_v2

\- vw\_fact\_inspection\_excel\_v2

\- vw\_band\_scraper\_api\_v1

\- vw\_band\_scraper\_details\_api\_v1



Ruwe tabellen alleen indien nodig:



\- sb\_inspections\_v0

\- sb\_inspection\_items\_v0



\---



\## 3. Viewkeuze per vraagtype



\### Actuele meshoogte



Gebruik:



vw\_meshoogte\_latest\_per\_scraper\_clean



Voor vragen zoals:

\- Wat is de laatste meshoogte?

\- Welke schrapers staan laag?

\- Wat is de actuele stand?



\### Historie / lifecycle



Gebruik:



vw\_mes\_lifecycle\_cycles\_clean



Voor vragen zoals:

\- Hoe verloopt de slijtage?

\- Is er een normale slijtagecurve?

\- Hoe vaak is er vervangen?

\- Wat is de lifecycle van dit mes?



\### Forecast



Gebruik:



vw\_mes\_cycle\_analysis\_clean



Voor vragen zoals:

\- Wanneer moet dit mes vervangen worden?

\- Welke posities halen binnenkort 3 mm?

\- Wat is de forecast?



\### Actielijst / prioriteit



Gebruik:



vw\_mes\_maintenance\_positions\_latest



Voor vragen zoals:

\- Welke acties moeten we plannen?

\- Welke posities hebben prioriteit?

\- Wat moet eerst gebeuren?



\### Vervangadvies



Gebruik:



vw\_all\_replacement\_advice



Voor vragen zoals:

\- Welke messen moeten vervangen worden?

\- Wat is het vervangadvies?

\- Welke posities zijn kritiek?



\### Band- en schraperstatus



Gebruik:



vw\_band\_scraper\_api\_v1

vw\_band\_scraper\_details\_api\_v1



Voor vragen zoals:

\- Heeft deze band schrapers?

\- Hoeveel schrapers zijn actief?

\- Welke banden zijn zonder schrapers?

\- Wat is de status van de schraperconfiguratie?



\---



\## 4. Meshoogte interpretatie



Bron voor meshoogte:



row\_json ->> 'Unnamed: 8'



Interpretatie:

\- numeriek = meetwaarde

\- G, M, V, X = conditiecode

\- conditiecodes nooit als getal interpreteren

\- lege waarde = ontbrekende meetwaarde



Belangrijke regel:



MAX(meshoogte) is niet automatisch de actuele stand.

Gebruik latest-view voor actuele stand.



\---



\## 5. Forecastregels



Forecastgrens:



3 mm



Gebruik forecast alleen wanneer er voldoende meetpunten zijn.

Richtlijn:



\- minimaal 3 meetpunten voor trend/forecast

\- minder dan 3 meetpunten = te weinig data voor betrouwbare voorspelling



Statusindeling:



\- <= 3 mm → NU VERVANGEN

\- <= 30 dagen → BINNEN 30 DAGEN

\- <= 60 dagen → BINNEN 60 DAGEN

\- > 60 dagen → MONITOREN



Als data te dun is:

\- zeg dat forecast onzeker is

\- geef geen harde vervangdatum

\- adviseer extra inspectie of hercontrole



\---



\## 6. Opmerkingen interpretatie



Bron voor opmerkingen:



row\_json ->> 'Klantgegevens '



Zoek altijd naar termen rond:



\- scheefloop

\- trommel

\- vervuiling

\- nat materiaal

\- band

\- frame

\- lager

\- steunen

\- mes

\- vervangen

\- cassette

\- hosch

\- retourmateriaal

\- carryback

\- morsgoed

\- ophoping

\- aankleving



Gebruik opmerkingen als diagnosebron naast meshoogte.

Opmerking zonder meting is geen harde slijtageconclusie, maar wel een signaal.



\---



\## 7. Vervanging interpretatie



Vervanging = TRUE indien:



\- vervangen = TRUE

\- tekst bevat "mes" en "vervang"

\- tekst bevat duidelijke vervangactie rond cassette, mes of schraperonderdeel



Let op:



\- “advies vervangen” is niet hetzelfde als “vervangen uitgevoerd”

\- onderscheid advies, gepland en uitgevoerd

\- combineer vervangingen altijd met datum en positie



\---



\## 8. Band-schraper logica



Gebruik voor band/schrapervragen:



\- vw\_band\_scraper\_api\_v1

\- vw\_band\_scraper\_details\_api\_v1



Statussen:



\- BAND\_MET\_SCHRAPERS

\- BAND\_ZONDER\_SCHRAPERS



Belangrijke regels:



\- BAND\_ZONDER\_SCHRAPERS is een valide status

\- BAND\_ZONDER\_SCHRAPERS is niet automatisch een fout

\- een band kan bewust zonder schrapers zijn ingericht

\- voorbeeld: A 461 kan valide zonder schrapers zijn

\- bandcodes exact matchen

\- R 5 is niet automatisch hetzelfde als R5, tenzij normalisatie dit expliciet ondersteunt



Interpretatie:



\- aanwezig = gekoppelde configuratie

\- actief = operationeel bevestigd

\- aanwezig maar niet actief = opvolging nodig

\- geen schraper = alleen probleem als toepassing of inspectiedata daarop wijst



\---



\## 9. Analyseflow onderhoud



Beantwoord onderhoudsvragen standaard in deze volgorde:



1\. Resultaat

2\. Trend

3\. Opmerkingen

4\. Vervangingen

5\. Ongewone slijtage

6\. Mogelijke oorzaak

7\. Actie



Als niet alles beschikbaar is:

\- geef alleen wat beschikbaar is

\- benoem wat ontbreekt

\- maak geen schijnzekerheid



\---



\## 10. Ongewone slijtage



Markeer slijtage als ongewoon bij:



\- snelle terugval in meshoogte

\- structureel lage waarden

\- geen normale slijtagecurve

\- veel vervangingen zonder verbetering

\- grote verschillen tussen links/rechts of posities

\- nieuwe messen die snel opnieuw laag staan

\- herhaald lage waarden in combinatie met opmerkingen



Mogelijke hypotheses:



\- verkeerde afstelling

\- te hoge of te lage schraperdruk

\- bandloopprobleem

\- trommelprobleem

\- materiaalopbouw

\- nat of kleverig materiaal

\- abrasief materiaal

\- verkeerde montagepositie

\- beschadigde band

\- slechte reiniging vóór secundaire schraper



Noem hypothese altijd als hypothese, niet als bewezen oorzaak.



\---



\## 11. Diagnose combineren



Combineer waar mogelijk:



\- meshoogte

\- opmerkingen

\- vervangingen

\- inspectiefrequentie

\- bandconditie

\- scraperstatus

\- historie

\- forecast



Gebruik geen losse meetwaarde als volledige diagnose.

Een onderhoudsadvies is sterker wanneer meerdere signalen hetzelfde beeld geven.



\---



\## 12. Prioritering



Prioriteit hoog bij:



\- meshoogte <= 3 mm

\- forecast <= 30 dagen

\- herhaalde NOK’s

\- vervanging nodig én productie-impact

\- opmerkingen over schade, scheefloop, trommel of zware vervuiling

\- snelle slijtage na recente vervanging



Prioriteit middel bij:



\- forecast <= 60 dagen

\- structurele vervuiling zonder directe grenswaarde

\- aandachtspunt bij volgende stop



Prioriteit laag bij:



\- normale slijtagecurve

\- voldoende meshoogte

\- geen kritieke opmerkingen

\- alleen monitoren nodig



\---



\## 13. Actieadvies



Voorbeelden van concrete acties:



\- plan mesvervanging

\- controleer schraperdruk

\- controleer afstelling

\- controleer uitlijning

\- inspecteer bandloop

\- inspecteer trommel

\- controleer materiaalopbouw

\- reinig stortpunt of retourzone

\- voer extra inspectie uit

\- verhoog inspectiefrequentie tijdelijk

\- vergelijk links/rechts slijtagebeeld

\- controleer of schraper actief en correct gemonteerd is



Geef maximaal 1 tot 3 acties tenzij gebruiker om detail vraagt.



\---



\## 14. Bandcodes en normalisatie



Normaliseer bandcodes voorzichtig:



\- A319 en A 319 mogen als dezelfde band worden behandeld als context dit ondersteunt

\- behoud in antwoord bij voorkeur de schrijfwijze van gebruiker

\- vermijd verkeerde samenvoeging van codes met andere betekenis

\- bij twijfel: meld dat exacte bandcodevalidatie nodig is



\---



\## 15. Datakwaliteit



Let op deze datakwaliteitsproblemen:



\- lege meshoogtes

\- conditiecodes in meetkolom

\- dubbele inspecties

\- ontbrekende datums

\- ontbrekende scraperpositie

\- inconsistente bandcode

\- tekstuele vervanging zonder vervangvlag

\- ruwe Excel-kolommen met afwijkende namen

\- verschil tussen positie, scraper en artikel



Als data ontbreekt:

\- zeg welke data ontbreekt

\- geef geen harde conclusie

\- adviseer welke data nodig is



\---



\## 16. Belangrijke inzichten



\- Maintenance view is betrouwbaarder dan ruwe data voor actielijsten.

\- Latest view is leidend voor actuele stand.

\- Lifecycle view is leidend voor trend.

\- Forecast view is leidend voor vervangmoment.

\- Positie is vaak belangrijker dan losse scraper.

\- MAX(meshoogte) is geen actuele stand.

\- Een band zonder schrapers is niet automatisch fout.

\- Vervangadvies moet worden gecombineerd met inspectie-opmerkingen.

\- RAG is niet leidend voor actuele onderhoudsdata.



\---



\## 17. Outputregels



Antwoord kort en praktisch.



Standaard:

\- eerst resultaat

\- maximaal 20 regels

\- geen lange theorie

\- geen gokken

\- data ontbreekt → expliciet melden

\- Action-resultaat of SQL-context is leidend

\- RAG alleen voor achtergrond



Voor onderhoudsdiagnoses:

\- benoem risico

\- benoem onzekerheid

\- geef concrete actie



Voor forecasts:

\- geef status

\- geef datum of termijn alleen als data voldoende is

\- meld onzekerheid bij weinig meetpunten



\---



\## 18. Niet doen



Niet doen:



\- producteigenschappen uit dit bestand afleiden

\- Belle Banne, Proload, Flexal of andere producten inhoudelijk beantwoorden vanuit dit bestand

\- prijzen of voorraad uit dit bestand afleiden

\- technische productselectie doen zonder product\_assistant\_ask

\- harde oorzaken noemen zonder data

\- ruwe tabellen gebruiken als clean views beschikbaar zijn

\- RAG gebruiken als SQL/API-data beschikbaa

