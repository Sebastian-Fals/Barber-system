# encryption-validation Specification

## Purpose

Validación de integridad de `ENCRYPTION_KEY` al iniciar el sistema. Previene fallos silenciosos de desencriptación en runtime.

## Requirements

### Requirement: Startup Encryption Key Validation

Al iniciar, el sistema DEBE encriptar un valor conocido con `ENCRYPTION_KEY` y verificar que la desencriptación devuelve el valor original. Si la validación falla, el sistema DEBE hacer crash temprano con un mensaje claro.

#### Scenario: Valid encryption key

- GIVEN `ENCRYPTION_KEY` is correctly set
- WHEN the application starts
- THEN the encrypt/decrypt round-trip succeeds
- AND the application starts normally

#### Scenario: Invalid or corrupted encryption key

- GIVEN `ENCRYPTION_KEY` is invalid or does not match the key used to encrypt stored data
- WHEN the application starts
- THEN the validation fails
- AND the application MUST crash immediately with a clear error message
- AND the message explicitly states the encryption key is invalid

#### Scenario: Missing encryption key

- GIVEN `ENCRYPTION_KEY` is not set in the environment
- WHEN the application starts
- THEN the application MUST crash with a message indicating the key is missing

### Requirement: Key Immutability Documentation

La documentación DEBE advertir explícitamente que `ENCRYPTION_KEY` no debe cambiarse después del deploy inicial. Cambiarla requiere re-encriptar todos los datos almacenados.

#### Scenario: Developer reads docs before changing key

- GIVEN a developer considers changing `ENCRYPTION_KEY` post-deploy
- WHEN they read the project documentation
- THEN they find a clear warning: "Do NOT change ENCRYPTION_KEY after initial deployment. Changing it will make all encrypted data unreadable."
