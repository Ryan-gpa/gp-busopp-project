"""Box JWT service account client.

One-time setup (requires Box admin):
1. developer.box.com → My Apps → Create New App
   App type: Custom App → Server Authentication (with JWT)
2. App Settings → Configuration → Generate RSA Keypair → Download JSON
3. App Settings → App Access Level: "App + Enterprise Access"
4. Submit for Admin Authorization (Box admin approves in Admin Console)
5. Share the folder containing financial reports with the service account
   (email shown in App Settings → General → Service Account Info)
6. Place the downloaded JSON at:
     disclosure-review-kit/config/box_config.json
   (add this file to .gitignore — it contains a private key)
7. pip install "boxsdk[jwt]>=3.9.0"
8. Restart the API server
"""
from pathlib import Path
import json
import os
import sys

_HERE = Path(__file__).parent
_CONFIG_PATH = (_HERE / "../../disclosure-review-kit/config/box_config.json").resolve()
_client = None


def _ensure_config() -> bool:
    """Write box_config.json from BOX_CONFIG_JSON env var if the file is absent."""
    if _CONFIG_PATH.exists():
        return True
    env_json = os.environ.get("BOX_CONFIG_JSON", "").strip()
    if not env_json:
        return False
    try:
        parsed = json.loads(env_json)
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CONFIG_PATH, "w") as f:
            json.dump(parsed, f)
        return True
    except Exception as e:
        print(f"[box] Failed to write config from BOX_CONFIG_JSON env var: {e}", file=sys.stderr)
        return False


def is_configured() -> bool:
    return _ensure_config()


def get_client():
    """Return a cached Box Client, or None if not configured / SDK not installed."""
    global _client
    if _client is not None:
        return _client
    if not _CONFIG_PATH.exists():
        return None
    try:
        from boxsdk import JWTAuth, Client  # type: ignore
        auth = JWTAuth.from_settings_file(str(_CONFIG_PATH))
        _client = Client(auth)
        return _client
    except ImportError:
        print("[box] boxsdk not installed — run: pip install 'boxsdk[jwt]>=3.9.0'", file=sys.stderr)
    except Exception as e:
        print(f"[box] Failed to initialise Box client: {e}", file=sys.stderr)
    return None


def list_folder(folder_id: str = "0") -> list:
    """List items in a Box folder. Returns dicts with id/name/type/size/modifiedAt."""
    client = get_client()
    if not client:
        return []
    items = []
    for item in client.folder(folder_id).get_items(limit=200):
        items.append({
            "id": item.id,
            "name": item.name,
            "type": item.type,
            "size": getattr(item, "size", None),
            "modifiedAt": str(getattr(item, "modified_at", "") or ""),
        })
    return items


def get_folder_info(folder_id: str) -> dict:
    """Return name + parent of a folder."""
    client = get_client()
    if not client:
        return {"id": folder_id, "name": folder_id}
    folder = client.folder(folder_id).get()
    parent = folder.parent
    return {
        "id": folder_id,
        "name": folder.name,
        "parentId": parent.id if parent else None,
        "parentName": parent.name if parent else None,
    }


def search_pdfs(query: str) -> list:
    """Search Box for PDF files matching query. Returns up to 20 results.

    Tries enterprise_content scope first (finds files across the org); falls back
    to user_content scope if the app doesn't have enterprise search permission.
    Either way, only files the service account can access are returned.
    """
    client = get_client()
    if not client:
        return []

    def _run(scope: str):
        items = []
        for item in client.search().query(
            query, file_extensions=["pdf"], type="file", limit=20, scope=scope
        ):
            items.append({
                "id": item.id,
                "name": item.name,
                "type": "file",
                "size": getattr(item, "size", None),
                "modifiedAt": str(getattr(item, "modified_at", "") or ""),
                "parentName": (item.parent.name if hasattr(item, "parent") and item.parent else None),
            })
        return items

    try:
        results = _run("enterprise_content")
        # enterprise_content may return 0 results if not authorised — fall back
        if not results:
            results = _run("user_content")
        return results
    except Exception:
        try:
            return _run("user_content")
        except Exception as e:
            print(f"[box] search error: {e}", file=sys.stderr)
            return []


def download_file(file_id: str) -> tuple:
    """Download a Box file. Returns (bytes, filename)."""
    client = get_client()
    if not client:
        raise RuntimeError("Box not configured or SDK not installed.")
    file_obj = client.file(file_id).get()
    name = file_obj.name
    content = file_obj.content()
    return content, name


def get_file_parent_folder(file_id: str) -> str | None:
    """Return the parent folder ID of a Box file, or None on error."""
    client = get_client()
    if not client:
        return None
    try:
        file_obj = client.file(file_id).get(fields=["parent"])
        parent = file_obj.parent
        return parent.id if parent else None
    except Exception as e:
        print(f"[box] get_file_parent_folder error: {e}", file=sys.stderr)
        return None


def upload_file(folder_id: str, filename: str, content: bytes) -> dict | None:
    """Upload bytes as filename into folder_id.

    If a file with the same name already exists in the folder, uploads a new
    version instead of creating a duplicate. Returns the Box file dict or None.
    """
    client = get_client()
    if not client:
        return None
    import io
    stream = io.BytesIO(content)
    try:
        # Check for existing file with same name
        existing_id = None
        for item in client.folder(folder_id).get_items(limit=200):
            if item.type == "file" and item.name == filename:
                existing_id = item.id
                break

        if existing_id:
            uploaded = client.file(existing_id).update_contents(stream)
        else:
            uploaded = client.folder(folder_id).upload_stream(stream, filename)

        return {"id": uploaded.id, "name": uploaded.name}
    except Exception as e:
        print(f"[box] upload error: {e}", file=sys.stderr)
        return None
