# Biodiversiteit Verkenner 1.16

Een zelfstandige Streamlit-app om de verwachte biodiversiteit van nog niet
bezochte gebieden te verkennen met openbare iNaturalist-waarnemingen.

## Mogelijkheden

- Een bewaard GeoJSON-gebied openen of een nieuw gebied tekenen en downloaden.
- Standaard zoeken in de laatste tien kalenderjaren.
- Vóór de zoekactie filteren op kalendermaanden, waarnemingskwaliteit, grote
  soortgroep en een opgezochte orde of familie.
- Vlinders en bloemdieren als rechtstreekse hoofdgroepen selecteren.
- Hoofdgroepen kiezen in hetzelfde raster met ronde keuzes als de maanden;
  daarbij blijft steeds precies één hoofdgroep actief.
- Ordes en families zoeken met een formulier dat zowel op de zoekknop als via
  Enter werkt en Nederlandse, Engelse en wetenschappelijke zoektermen herkent.
- Alleen na een geslaagde zoekactie een concreet zoekresultaat kiezen. De
  gekozen orde of familie vervangt daarbij zichtbaar de hoofdgroep.
- Soorten naar keuze rangschikken op het aantal waarnemingen in het gekozen
  gebied of op taxonomie: rijk, stam, klasse, orde, familie, geslacht en soort.
  Binnen elk niveau staan de wetenschappelijke namen alfabetisch. Zo blijven
  bijvoorbeeld alle vogels bij elkaar, ook wanneer meerdere ordes voorkomen.
- Een minimumaantal waarnemingen per soort instellen. Dit gaat over de
  gebiedswaarnemingen binnen de gekozen zoekperiode en filters, niet over
  persoonlijke waarnemingen. Kaarten, overzichtstellers en CSV gebruiken
  hetzelfde minimum; standaard is dat 1, zodat alle gevonden soorten zichtbaar zijn.
- Taxonomie per taxon op schijf bewaren en hergebruiken bij andere gebieden,
  zoekperiodes en volgende sessies. Alleen ontbrekende taxa worden opgehaald.
  Bij taxonomisch sorteren worden alleen soorten boven het ingestelde minimum
  aangevuld; een lager minimum haalt vervolgens alleen de extra soorten op.
- Foto, Engelse naam, wetenschappelijke naam en iNaturalist-link tonen in
  een responsief raster.
- De schuifregelaar voor het soortenraster tot het volledige aantal gevonden
  soorten laten lopen; de eerdere bovengrens van 250 is verwijderd.
- Engelse iNaturalist-soortnamen gebruiken zonder Nederlandse plaatsvoorkeur.
- Snelle berekening met geaggregeerde soortaantallen en parallel opgehaalde
  taxonomie en persoonlijke soortenpagina's.
- Grote en soortenrijke gebieden automatisch in kleinere kaartvakken verdelen,
  zodat de 10.000-resultatenlimiet geen soorten meer afkapt. De aantallen uit
  alle vakken worden daarna per soort samengevoegd.
- Maanden kiezen met afzonderlijke ronde meerkeuzevakjes.
- De maanden beginnen leeg, zodat bewust minimaal één maand wordt gekozen.
- De cursor staat bij een nieuwe sessie direct in het gebruikersnaamveld.
- Het soortenoverzicht direct tonen, standaard gerangschikt op waarnemingen
  in het gebied, met daarnaast het persoonlijke totale aantal waarnemingen
  per soort. De CSV-download volgt de gekozen sortering.
- Soorten die de gebruiker nog nooit zag krijgen in het persoonlijke
  soortenoverzicht een rode kaartrand.
- De volledige soortkaart blauw omlijnen als alle eigen waarnemingen van de
  soort binnen de getekende gebiedsgrens vallen, en groen als de soort ook
  daarbuiten is waargenomen. De telling omvat alle jaren, gebruikt de exacte
  grens en wordt voor herhaalde weergaven bewaard.
- Geen lege taxonomieregels onderaan de fotokaarten.
- Het actieve gebied automatisch herstellen via de eigen URL wanneer een
  Streamlit-sessie na inactiviteit opnieuw start.
- Persoonlijke vergelijking en gebiedscontrole pas laden na de verkenning.
- De persoonlijke soortenlijst met hetzelfde vooraf gekozen soortgroep-,
  orde- of familiefilter ophalen als de gebiedsverkenning.
- Grote soortgroepen met hun vaste iNaturalist-taxonnummer opvragen. Daardoor
  gebruikt bijvoorbeeld de vissenkeuze zowel voor het gebied als voor de
  persoonlijke vergelijking exact taxon 47178 en kan een tekstfilter niet
  onbedoeld een lege uitkomst veroorzaken.
- Door verschuiven over een wereldkaart kunnen Leaflet-gebieden lengtegraden
  buiten -180 tot 180 graden bevatten (bijvoorbeeld -229 graden voor Raja
  Ampat). De app normaliseert die nu automatisch bij openen, tekenen,
  herstellen, bewaren en zoeken, zodat zulke gebieden niet langer nul
  resultaten opleveren.
- Vergelijken met een openbare persoonlijke iNaturalist-soortenlijst.
- Persoonlijke totale waarnemingsaantallen per soort tonen.
- Tabellen downloaden als CSV.

## Installatie

Pak de zip uit en plaats de volledige inhoud in een nieuwe GitHub-repository.
`app.py`, `taxonomy.py`, `requirements.txt` en `README.md` horen op het hoogste
niveau. Maak daarna een nieuwe
Streamlit Community Cloud-app met `app.py` als startbestand.

Lokaal starten kan vanuit de projectmap met:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Er zijn geen wachtwoorden, API-sleutels of Streamlit Secrets nodig.
De app begrenst API-verzoeken tot ongeveer zestig per minuut, overeenkomstig
de richtlijn van iNaturalist. De eerste berekening gebruikt de kleinste
rechthoek om het gekozen gebied en vraagt geen volledige taxonomie of
persoonlijke soortenlijst op. Daarna haalt het soortenoverzicht je openbare
persoonlijke aantallen en de eigen waarnemingen binnen de getekende grens op;
de eerste weergave kan daardoor langer duren. Herhaald bekijken met dezelfde
instellingen gebruikt bewaarde resultaten.
Zeer soortenrijke gebieden vragen door de automatische kaartvakverdeling meer
API-verzoeken dan kleine gebieden, maar worden niet meer stilzwijgend bij
3.000 of 10.000 soorten afgekapt.

## Taxonomie bewaren

De app maakt automatisch `.cache/taxonomy.sqlite3` aan naast `app.py`.
Deze opslag is per taxon en taal, zonder automatische vervaldatum. De eerste
keer kost het aanvullen van de taxonomie nog tijd; later worden alleen nog
onbekende taxa opgehaald. Ook na het herstarten van Python blijft de cache
bruikbaar zolang hetzelfde bestand op schijf aanwezig is. De cache bevat
alleen openbare taxonomie, geen gebruikersnamen of persoonlijke waarnemingen.

Bij hosting met een tijdelijke schijf kan de cache bij een nieuwe deployment
of vervanging van de server verdwijnen. Voor behoud over zulke herstarts heen
kun je `BIODIVERSITEIT_CACHE_DIR` instellen op een blijvend opslagvolume. Neem
het bestand anders mee in een back-up en herstel het op dezelfde plek.

Taxonomie kan incidenteel worden herzien. Om bewust alles opnieuw op te halen:
stop de app, verwijder `.cache/taxonomy.sqlite3` (of hetzelfde bestand in de
ingestelde cachemap) en start de app opnieuw.

## Controles

De regressiecontroles voor gemengde soortgroepen, hergebruik van de cache en
het minimumfilter draaien zonder iNaturalist-aanroepen:

```bash
python -m unittest discover -s tests -v
```

## Belangrijk

Historische waarnemingsaantallen geven een kansbeeld. Ze garanderen niet dat een
soort tijdens een bezoek daadwerkelijk aanwezig of waarneembaar is.
