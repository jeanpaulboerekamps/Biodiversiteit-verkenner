# Biodiversiteit Verkenner 1.0

Een zelfstandige Streamlit-app om de verwachte biodiversiteit van nog niet
bezochte gebieden te verkennen met openbare iNaturalist-waarnemingen.

## Mogelijkheden

- Een bewaard GeoJSON-gebied openen of een nieuw gebied tekenen en downloaden.
- Standaard zoeken in de laatste tien kalenderjaren.
- Filteren op kalendermaanden, waarnemingskwaliteit, orde en familie.
- Soorten rangschikken op het aantal waarnemingen in het gekozen gebied.
- Foto, Nederlandse naam, wetenschappelijke naam en iNaturalist-link tonen.
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
de richtlijn van iNaturalist. Zeer grote of intensief onderzochte gebieden
kunnen daardoor enkele minuten nodig hebben.

## Belangrijk

Historische waarnemingsaantallen geven een kansbeeld. Ze garanderen niet dat een
soort tijdens een bezoek daadwerkelijk aanwezig of waarneembaar is.
