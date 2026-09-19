# Biodiversiteit Verkenner 1.3

Een zelfstandige Streamlit-app om de verwachte biodiversiteit van nog niet
bezochte gebieden te verkennen met openbare iNaturalist-waarnemingen.

## Mogelijkheden

- Een bewaard GeoJSON-gebied openen of een nieuw gebied tekenen en downloaden.
- Standaard zoeken in de laatste tien kalenderjaren.
- Vóór de zoekactie filteren op kalendermaanden, waarnemingskwaliteit, grote
  soortgroep en een opgezochte orde of familie.
- Soorten rangschikken op het aantal waarnemingen in het gekozen gebied.
- Foto, Nederlandse naam, wetenschappelijke naam en iNaturalist-link tonen in
  een responsief raster.
- Snelle berekening met geaggregeerde soortaantallen en parallel opgehaalde
  taxonomie en persoonlijke soortenpagina's.
- Maanden kiezen met afzonderlijke ronde meerkeuzevakjes.
- Eén permanent uitgeklapt keuzemenu voor de vijf overzichten.
- Het actieve gebied automatisch herstellen via de eigen URL wanneer een
  Streamlit-sessie na inactiviteit opnieuw start.
- Persoonlijke vergelijking en volledige familietaxonomie pas laden wanneer
  het gekozen overzicht die gegevens daadwerkelijk nodig heeft.
- Vergelijken met een openbare persoonlijke iNaturalist-soortenlijst.
- Persoonlijke totale waarnemingsaantallen per soort tonen.
- Taartdiagrammen maken voor alle soorten en nog nooit geziene soorten.
- Soorten tonen uit families waarvan de gebruiker nog nooit een soort zag.
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
persoonlijke soortenlijst op. Daardoor verschijnt het eerste fotoraster veel
sneller. Persoonlijke overzichten kunnen daarna nog kort moeten laden.

## Belangrijk

Historische waarnemingsaantallen geven een kansbeeld. Ze garanderen niet dat een
soort tijdens een bezoek daadwerkelijk aanwezig of waarneembaar is.
