# Biodiversiteit Verkenner 1.13

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
- Soorten rangschikken op het aantal waarnemingen in het gekozen gebied.
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
- Het soortenoverzicht direct tonen, gerangschikt op waarnemingen in het gebied,
  met daarnaast het persoonlijke totale aantal waarnemingen per soort.
- Soorten die de gebruiker nog nooit zag krijgen in het persoonlijke
  soortenoverzicht een rode kaartrand.
- Foto's groen omlijnen van soorten die de gebruiker zelf binnen de getekende
  gebiedsgrens heeft waargenomen, ook buiten de gekozen zoekperiode. Deze
  controle gebruikt de exacte grens en wordt voor herhaalde weergaven bewaard.
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
`app.py`, `requirements.txt` en `README.md` horen op het hoogste niveau; laat
`.streamlit/config.toml` in de map `.streamlit` staan. Maak daarna een nieuwe
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

## Belangrijk

Historische waarnemingsaantallen geven een kansbeeld. Ze garanderen niet dat een
soort tijdens een bezoek daadwerkelijk aanwezig of waarneembaar is.
