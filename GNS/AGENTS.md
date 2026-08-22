# PinskGNS Project Guide

## Project Overview

PinskGNS is an industrial system for gas cylinder processing, filling, tracking, and shipment.

### Technology Stack

- Python
- Django
- Django REST Framework
- PostgreSQL
- Redis
- Celery
- Daphne
- JWT
- drf-spectacular

### Main Applications

- `core`
- `filling_station`
- `carousel`
- `railway_service`
- `autogas`
- `transport`
- `ttn`
- `mobile`

## Purpose of This File

Use this file as a high-level guide to the project structure and development workflow.
More specific implementation rules are stored in `.cursor/rules/*.mdc` and should be applied according to their descriptions and file patterns.

## Context and Analysis Strategy

Use the minimum context required to complete the task correctly.

Prefer:

- symbol search;
- targeted file reading;
- focused analysis of the relevant application and integration points;
- existing project patterns and reusable components.

Avoid:

- scanning the entire repository without a clear need;
- reading unrelated files;
- exploring migrations, static assets, media, logs, or `__pycache__` unless the task specifically requires it.

Before making changes:

1. Identify the relevant domain and application.
2. Locate the related models, services, API endpoints, tasks, and integrations.
3. Read only the files needed to understand the affected workflow.
4. Check existing tests and similar implementations.
5. Assess backward compatibility and possible side effects.

## General Development Principles

- Make only the changes required for the task.
- Do not refactor unrelated code.
- Reuse existing code and follow established project patterns where practical.
- Keep solutions readable, maintainable, and appropriately scoped.
- Use type hints in new Python code where practical and consistent with the surrounding code.
- Preserve backward compatibility unless the task explicitly requires a breaking change.
- Do not remove production safeguards or validations without an explicit requirement and a clear understanding of the consequences.
- Do not introduce new dependencies unless they are necessary.
- Update or add tests when behavior changes.

## Architecture Navigation

Start with the files most relevant to the task, typically:

- `models.py`
- `services.py`
- `serializers.py`
- `views.py`
- `api/`
- `tasks.py`
- `urls.py`
- relevant tests

Follow the existing application structure when equivalent functionality is organized differently.

## Domain Routing

Use this map to select the initial analysis area:

- RFID processing: `filling_station`
- Filling process: `carousel`, `filling_station`
- Railway operations: `railway_service`
- Checkpoint and transport operations: `transport`
- Waybills and shipment documents: `ttn`
- Mobile API: `mobile`
- Autogas functionality: `autogas`
- Shared project functionality: `core`

This map defines the starting point, not the complete impact area. Check connected applications and integrations when the workflow crosses domain boundaries.

## External Integrations

The project integrates with:

- Miriada
- Intellect
- OPC Server
- RFID equipment
- Carousel equipment

When a task affects an integration boundary, identify all callers, data formats, error-handling paths, asynchronous processing, and operational dependencies before editing.

## Working Expectations

When analyzing or implementing a task:

1. Briefly state the affected area and intended approach.
2. Inspect the smallest relevant set of files.
3. Make minimal, focused changes.
4. Validate the result with the most relevant available checks or tests.
5. Summarize changed files, behavior, assumptions, and any remaining risks.

If requirements are ambiguous, do not guess about production behavior. State the ambiguity and ask a focused question, or clearly document the assumption when progress can safely continue.
