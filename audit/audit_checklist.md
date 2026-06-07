# Audit Checklist

## Functional

- [x] App has index.html.
- [x] Demo data exists.
- [x] Airport board module exists.
- [x] Airport detail module exists.
- [x] Graphics queue module exists.
- [x] Exporters exist.
- [x] Source health module exists.

## Security

- [x] No service-role key in frontend code.
- [x] No real commercial API keys.
- [x] `.env` is ignored.
- [x] `.env.example` uses placeholders.

## Doctrine

- [x] FAA/NAS operational status separated from NWS forecast proxy.
- [x] Commercial/enrichment sources labeled non-official.
- [x] Forecast impact is not labeled official FAA delay forecast.

## Remaining manual checks

- [ ] Run locally in a browser.
- [ ] Test downloads from UI.
- [ ] Configure Supabase and validate live views.
