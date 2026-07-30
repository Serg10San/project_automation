"""
sharepoint_upload.py — upload a file to a SharePoint document library via
Microsoft Graph.

Supports two auth modes, selected by GRAPH_AUTH_MODE (default "delegated"):

  "delegated" — uses the caller's own signed-in identity via the Azure CLI
      (`az login`). No app registration or client secret required, but the
      Azure CLI must be installed and `az login` run beforehand, and the
      signed-in user must already have write access to the target SharePoint
      site. Recommended default for interactive/manual use.

  "app" — app-only auth via an Azure AD app registration (client credentials
      flow). Requires admin-provisioned GRAPH_CLIENT_ID/GRAPH_CLIENT_SECRET.
      Use for unattended automation (scheduled tasks, CI) with no user
      available to run `az login`.

Requires the following variables in .env (comments in that file explain how
to obtain them):
    GRAPH_TENANT_ID     (both modes)
    GRAPH_CLIENT_ID     (app mode only)
    GRAPH_CLIENT_SECRET (app mode only)
    GRAPH_SP_HOSTNAME   (e.g. intel.sharepoint.com)
    GRAPH_SP_SITE_PATH  (e.g. /sites/ire)
    GRAPH_SP_FOLDER     (folder path relative to the site's default document
                         library root, e.g. "weeklies" — do NOT prefix with
                         "Shared Documents", the drive root already IS that
                         library)

Usage
-----
    python -m src.tools.sharepoint_upload path\\to\\weekly.docx

    from src.tools.sharepoint_upload import upload_file
    upload_file("path/to/weekly.docx")
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class SharePointUploadError(RuntimeError):
    """Raised when authentication, site resolution, or upload fails."""


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SharePointUploadError(
            f"Missing required environment variable: {name}. " "See .env for setup instructions."
        )
    return value


def _get_delegated_token() -> str:
    """
    Acquire a Graph access token for the current user via the Azure CLI.

    Requires `az login` to have been run already. Raises SharePointUploadError
    with guidance if the Azure CLI is missing or no one is logged in.
    """
    try:
        result = subprocess.run(
            [
                "az",
                "account",
                "get-access-token",
                "--resource",
                "https://graph.microsoft.com",
                "--output",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            shell=True,  # resolve az.cmd on Windows via PATH
        )
    except FileNotFoundError as exc:
        raise SharePointUploadError(
            "Azure CLI ('az') not found. Install it, or set GRAPH_AUTH_MODE=app "
            "to use client-credentials auth instead."
        ) from exc

    if result.returncode != 0:
        raise SharePointUploadError(
            "Azure CLI has no active login. Run 'az login' first, or set "
            f"GRAPH_AUTH_MODE=app to use client-credentials auth. Details: {result.stderr.strip()}"
        )
    return json.loads(result.stdout)["accessToken"]


def _get_app_token() -> str:
    """Acquire an app-only access token via the client credentials flow."""
    tenant_id = _require_env("GRAPH_TENANT_ID")
    client_id = _require_env("GRAPH_CLIENT_ID")
    client_secret = _require_env("GRAPH_CLIENT_SECRET")

    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    resp = requests.post(
        token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=30,
    )
    if not resp.ok:
        raise SharePointUploadError(f"Token request failed ({resp.status_code}): {resp.text}")
    return resp.json()["access_token"]


def get_access_token() -> str:
    """Acquire a Graph access token using the configured GRAPH_AUTH_MODE."""
    mode = os.environ.get("GRAPH_AUTH_MODE", "delegated").strip().lower()
    if mode == "delegated":
        return _get_delegated_token()
    if mode == "app":
        return _get_app_token()
    raise SharePointUploadError(f"Invalid GRAPH_AUTH_MODE={mode!r}. Use 'delegated' or 'app'.")


def get_site_id(token: str) -> str:
    """Resolve the numeric SharePoint site ID from hostname + site path."""
    hostname = _require_env("GRAPH_SP_HOSTNAME")
    site_path = _require_env("GRAPH_SP_SITE_PATH")

    url = f"{GRAPH_BASE}/sites/{hostname}:{site_path}"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if not resp.ok:
        raise SharePointUploadError(f"Site lookup failed ({resp.status_code}): {resp.text}")
    return resp.json()["id"]


def upload_file(local_path: str | Path, remote_name: str | None = None) -> dict:
    """
    Upload local_path to GRAPH_SP_FOLDER on the configured SharePoint site.

    Returns the Graph driveItem JSON for the uploaded file.
    """
    local_path = Path(local_path)
    if not local_path.is_file():
        raise SharePointUploadError(f"File not found: {local_path}")

    folder = _require_env("GRAPH_SP_FOLDER").strip("/")
    remote_name = remote_name or local_path.name

    token = get_access_token()
    site_id = get_site_id(token)

    # Small-file upload (<4MB) via PUT to the drive item content endpoint.
    # For files >4MB, switch to an upload session:
    # https://learn.microsoft.com/graph/api/driveitem-createuploadsession
    remote_path = quote(f"{folder}/{remote_name}")
    url = f"{GRAPH_BASE}/sites/{site_id}/drive/root:/{remote_path}:/content"

    with open(local_path, "rb") as fh:
        resp = requests.put(
            url,
            headers={"Authorization": f"Bearer {token}"},
            data=fh,
            timeout=60,
        )
    if not resp.ok:
        raise SharePointUploadError(f"Upload failed ({resp.status_code}): {resp.text}")

    return resp.json()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="Path to the file to upload")
    parser.add_argument(
        "--name",
        default=None,
        help="Optional remote filename override (defaults to the local filename)",
    )
    args = parser.parse_args()

    load_dotenv()

    try:
        result = upload_file(args.file, args.name)
    except SharePointUploadError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    web_url = result.get("webUrl", "(no webUrl returned)")
    print(f"Uploaded successfully: {web_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
