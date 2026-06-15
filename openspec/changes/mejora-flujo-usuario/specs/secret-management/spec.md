# secret-management Specification

## Purpose

Credenciales de Google Calendar desde variable de entorno `GOOGLE_APPLICATION_CREDENTIALS_JSON`, eliminando la dependencia de un archivo `credentials.json` en disco.

## Requirements

### Requirement: Google Credentials From Environment Variable

El sistema DEBE leer las credenciales de Google desde la variable de entorno `GOOGLE_APPLICATION_CREDENTIALS_JSON`, que contiene el JSON completo de la service account. NO DEBE requerir un archivo `credentials.json` en el filesystem.

#### Scenario: Valid JSON in environment variable

- GIVEN `GOOGLE_APPLICATION_CREDENTIALS_JSON` contains valid service account JSON
- WHEN the calendar service initializes
- THEN credentials are parsed successfully from the environment variable
- AND Google Calendar API calls work without a credentials file on disk

#### Scenario: Missing environment variable

- GIVEN `GOOGLE_APPLICATION_CREDENTIALS_JSON` is not set
- WHEN the calendar service initializes
- THEN the service MUST fail with a clear error: "GOOGLE_APPLICATION_CREDENTIALS_JSON not set"

#### Scenario: Invalid JSON in environment variable

- GIVEN `GOOGLE_APPLICATION_CREDENTIALS_JSON` contains malformed JSON
- WHEN the calendar service initializes
- THEN the service MUST fail with a clear parse error message

### Requirement: Remove credentials.json From Disk

Después de migrar a la variable de entorno, el archivo `credentials.json` DEBE ser eliminado del filesystem del proyecto.

#### Scenario: No credentials file on disk

- GIVEN the migration to `GOOGLE_APPLICATION_CREDENTIALS_JSON` is complete
- WHEN checking the project filesystem
- THEN `credentials.json` does NOT exist

### Requirement: Updated .env.example

El archivo `.env.example` DEBE documentar la variable `GOOGLE_APPLICATION_CREDENTIALS_JSON` con un placeholder claro.

#### Scenario: Developer reads .env.example

- GIVEN a new developer clones the repo
- WHEN they read `.env.example`
- THEN they see `GOOGLE_APPLICATION_CREDENTIALS_JSON="{...}"` with instructions
