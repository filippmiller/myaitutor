# Railway build.builder error fix (2025-12-01)

## Summary
- **Problem:** Deployment failed with `Failed to parse your service config. Error: build.builder: Invalid input`.
- **Fix:** Removed the invalid `railway.toml` file and configured the project to rely on the `Dockerfile` and the Railway Start Command.

## Root Cause
- The repository contained a `railway.toml` file with a `[build]` section and a `builder` key that contained an invalid value.
- Railway attempts to parse this file to determine the build strategy. When the value is invalid, the build fails before it even starts.
- We want Railway to automatically detect the `Dockerfile` or use the settings configured in the Railway UI, rather than being overridden by a broken local config file.

## Changes Made
1.  **Removed `railway.toml`:** The file has been deleted from the repository.
2.  **Verified `Dockerfile`:** Confirmed that the `Dockerfile` is present and correctly configured to build the application (including the frontend) and start the backend.
3.  **Start Command:** The `Dockerfile` now uses an explicit shell command to ensure the `$PORT` variable is correctly expanded:
    ```dockerfile
    CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
    ```
    This aligns with the Railway Start Command requirement: `poetry run uvicorn app.main:app --host 0.0.0.0 --port $PORT --log-level info --no-access-log` (Note: The Dockerfile uses `uvicorn` directly as `poetry` might not be in the container path or needed if dependencies are installed globally/in venv).

## Deployment & Verification
- **Trigger:** Changes were pushed to the `main` branch.
- **Verification:**
    - Waited for the deployment to complete.
    - Checked Railway logs to confirm successful build and startup.
    - Confirmed that the application is listening on the correct port (0.0.0.0:$PORT).

## Next Steps
- If specific Railway configurations are needed in the future, ensure the `railway.toml` syntax is validated against the latest Railway documentation.
- For now, the `Dockerfile` is the source of truth for the build process.
