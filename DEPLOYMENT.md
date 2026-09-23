# Deployment Runbook — Databricks Apps

**Status: not deployed anywhere yet.** This documents what's needed to
deploy this app to Databricks Apps (the platform named in Sean's Business
Requirements doc / the CODA meeting notes as the eventual target if this
Streamlit route is used instead of Excel — see the README's "direction
tension" note), and is explicit about what's confirmed vs. assumed, since
I have no network access from this environment and no sibling Databricks
Apps config from your org to test or compare against.

## Prerequisites — confirm with your Databricks workspace admin / IT

- [ ] Databricks Apps is enabled for the target workspace.
- [ ] You (or someone) has permission to create an App in that workspace.
- [ ] Decide whether this app will ever use the "Databricks Volume path"
      input mode (vs. upload-only). If yes, the app's service principal
      needs a READ grant on that specific Unity Catalog Volume/path —
      nothing has been provisioned for this yet.
- [ ] Ask whether your org has a house convention for `app.yaml` (env vars,
      secret scopes, service principal assignment) that this should follow
      instead of the generic one committed here. I don't have an existing
      app to match against — see the note in `app.yaml`.
- [ ] No secrets or credentials are needed for anything currently built —
      v1 is manual file upload/Volume-path only, no live system connections
      (per the CODA meeting notes' explicit decision). If that changes,
      this section needs to change with it.

## Steps (via Databricks CLI, once you have workspace access)

```bash
databricks apps create fast-reconciler
databricks sync . /Workspace/Users/<you>/fast-reconciler
databricks apps deploy fast-reconciler --source-code-path /Workspace/Users/<you>/fast-reconciler
```

Or via the workspace UI: **Compute → Apps → Create App**, then point it at
this source. **I have not run these commands myself** (no Databricks Apps
access from this environment) — treat the exact flags as a starting point
and check `databricks apps --help` / current Databricks docs for your CLI
version before relying on them.

## Before calling a deployment done

- [ ] Upload `sample_data/sample_cadency_export.csv`,
      `sample_sap_export.csv`, and `sample_bank_export.csv` through the
      *deployed* app's UI and confirm Phase 1 and Phase 2 render identically
      to local testing (see README's "Running locally" section for expected
      results).
- [ ] Confirm the account selector and the Active Rules expanders load.
- [ ] If Volume-path input is in use: confirm a real Volume path load works
      end-to-end with the granted service principal.
- [ ] Decide who gets access (workspace group vs. individual users) via the
      App's permissions tab.

## Open items that affect deployment readiness, not just the app.yaml guess

These carry over from `README.md`'s "open items" — resolving them matters
before this is trusted with real daily data, deployed or not:

- SAP export layout and Treasury/bank export layout are still unconfirmed
  assumptions (`core/schema.py`).
- Whether Phase 1's `"5801"` code should match a range (5801–5905) or the
  exact string.
- Account 187's trigger condition (conditional, not daily) is undocumented.
- Ownership of hosting/deployment/defect-fixes is still an open leadership
  question (Umar was named as the contact in the meeting notes).
