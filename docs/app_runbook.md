# Run the complete local application

Open Docker Desktop and run this from the repository root:

```powershell
python scripts/start_app.py
```

The command checks the pinned raw files, starts PostgreSQL, runs Staging migrations/load/quality, executes the verified DW/Mart workflow with reconciliation and idempotency checks, prepares compatible ML artifacts, builds the backend/frontend images, starts both services and verifies live inference through the API and frontend proxy.

- App: http://localhost:5173/dss/demand-forecast
- API explorer: http://localhost:8000/docs

It prints these links only after readiness checks pass. First-time image builds and ML training can take several minutes. Later runs reuse Docker layers and verified models for the same published data version; the pipeline still reruns its quality gates.

## Prerequisites

- Python 3.12+ on the host; only its standard library is needed for the launcher.
- Running Docker Desktop/Engine with Compose v2 (including `up --wait`). Python ETL/ML dependencies are installed inside the tools image; no host pip/venv setup is required.
- The verified raw files and acquisition metadata selected by `docs/data_dictionary/operations_source_set.json`. This checkout already has them. They are ignored by Git, so transfer/restore them when using a fresh clone. The launcher deliberately stops on missing files or checksum differences rather than downloading a different Weather version or changing the source contract. See [the current source manifest](data_dictionary/source_manifest_20261110.md).

Existing `.env` settings are preserved. If `.env` is absent, the launcher creates local defaults with a generated password without printing it. With an existing PostgreSQL volume, use that volume's existing credentials; a newly generated password cannot change an existing database login. Connection failures stop preparation; the launcher does not reset the database, alter existing passwords or remove volumes.

## Optional full pipeline test suite

```powershell
python scripts/start_app.py --with-tests
```

This also runs the existing Staging/DW/Mart tests against fixture-owned databases. The configured PostgreSQL user needs CREATEDB. Quality/reconciliation checks run even without this option.

`--tree-jobs 6` is the default for offline training; use `--tree-jobs 1` if a smaller worker count is preferable.

## Models and reports

Models are reused only after checking their data version, source fingerprint, snapshot/metadata/state checksums, source notebooks and recorded dependency versions. Missing or incompatible models trigger a fresh immutable release under `artifacts/ml_serving/releases/`; previous artifacts are retained. Training still follows validation selection and stops if no supported selected model can be published.

Each startup writes a new directory under `artifacts/startup/`. Inspect `summary.json`, `preparation/failed.json` or the pipeline step reports if startup fails. The generated `compose.json` selects the verified model/snapshot paths for the backend image; it contains no credentials. The command returns a nonzero exit code when a required stage fails.

The backend image packages the selected release at its normal container paths. Keep using `python scripts/start_app.py` for future rebuilds so that the newest compatible release is selected. Plain `docker compose up --build` uses the Dockerfile's original default artifact paths and does not rerun the pipeline.

## Check logs or stop

```powershell
docker compose ps
docker compose logs --tail=100 backend frontend db
docker compose stop
```

Named PostgreSQL volumes and published snapshots are preserved. The launcher recreates backend/frontend containers and renews only the frontend's anonymous dependency volume to match the image; it does not renew or delete the PostgreSQL volume.

To continue frontend editing, sources remain mounted as before. After editing an artifact or changing data/config, rerun the one-command startup to rebuild and verify the serving images. The frontend API proxy is verified as part of startup.
