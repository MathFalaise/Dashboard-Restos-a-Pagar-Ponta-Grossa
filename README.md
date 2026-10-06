# Restos a Pagar — Ponta Grossa/PR

Collects, preserves and analyzes the *Restos a Pagar* (prior-year unpaid commitments) published by the
Municipality of Ponta Grossa on its Transparency Portal, and reconciles them with the official RREO Annex VII
reports. The public interface and all reports are in Portuguese.

## Layout

```
app/                     code: the `rp` package, tests and config.toml (see app/README.md)
data/
  snapshots/             immutable raw store (manifests + objects) the database is rebuilt from
  backups/               SQLite copies made before structural changes
  stage01-samples/       raw API samples from stage 01 (+ stage01-samples.SHA256.txt)
  stage02-raw/           raw data from stage 02, used by the tests (+ stage02-raw.SHA256.txt)
docs/
  stages/01-source-discovery/      stage 01: the source (API, portal)
  stages/02-accounting-validation/ stage 02: accounting validation and reconciliation
  stages/03-data-model/            stage 03: data model and the independent validation suite
  stages/04-pipeline/              stage 04: collector, processing, interface, homologation
  stages/05-analysis/              stage 05: analysis screens, post-05 consolidation, D1 load
  audits/                          technical audit, critical review, source check
  foi-requests/                    access-to-information (e-SIC) requests
  FOLDER_MAP.md                    old folder names → new ones
rp.py                    shortcut: `python rp.py <command>` = `python -m rp <command>`
```

## Quick start

Inside `app/`:

```bash
python -m pip install -r requirements-lock.txt
```

```bash
python -m pytest tests
```

```bash
python -m rp interface
```

The interface opens at `http://127.0.0.1:8050/`. Everything else (rebuilding the database, collecting, processing,
quality gates) is in [app/README.md](app/README.md).

## Language conventions

- Comments, docstrings and configuration notes are in English (ASCII).
- Identifiers (modules, functions, variables, database tables and columns), CLI commands and options, and every
  text the program shows or stores (interface labels, messages, rule sources, evidence) stay in Portuguese: they
  are part of the homologated data and of the public interface.
- Two stage 02 investigation scripts, `docs/stages/02-accounting-validation/investigation/coletar.py` and
  `casos.py`, are frozen in their original Portuguese: their SHA-256 is recorded in the snapshot manifests they
  produced.
