import hashlib
import ipaddress
import json
import os
import shutil
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlsplit
from zipfile import ZIP_DEFLATED, ZipFile

import requests
from bs4 import BeautifulSoup


_ASSET_FIELDS = (("img", "src"), ("link", "href"), ("script", "src"), ("source", "src"))
_ALLOWED_CONTENT_PREFIXES = (
    "image/", "text/css", "text/javascript", "application/javascript",
    "application/x-javascript", "font/", "application/font", "application/octet-stream",
)


def _setting(config, key, default):
    if config is None:
        return default
    value = config.get_default(key)
    return default if value is None else value


def _safe_remote_url(value):
    """Reject non-web, local, private and metadata-style asset targets."""
    try:
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return False
        port = parts.port or (443 if parts.scheme == "https" else 80)
        for info in socket.getaddrinfo(parts.hostname, port):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        return True
    except Exception:
        return False


def _asset_filename(url, content_type=""):
    suffix = os.path.splitext(urlsplit(url).path)[1].lower()[:10]
    if not suffix:
        suffix = {
            "text/css": ".css", "text/javascript": ".js", "application/javascript": ".js",
            "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
            "image/webp": ".webp", "image/svg+xml": ".svg",
        }.get((content_type or "").split(";", 1)[0].lower(), ".bin")
    return f"asset_{hashlib.sha256(url.encode('utf-8', errors='ignore')).hexdigest()[:20]}{suffix}"


def _download_asset(client, url, folder, per_resource_limit, shared_budget, deadline):
    result = {"url": url, "saved": False, "bytes": 0, "content_type": "", "reason": ""}
    if time.monotonic() >= deadline:
        result["reason"] = "archive_deadline"
        return result
    if not _safe_remote_url(url):
        result["reason"] = "unsafe_or_unresolvable_url"
        return result
    reserved = 0
    path = ""
    try:
        remaining = max(1.0, deadline - time.monotonic())
        with client.get(url, timeout=(3, min(8, remaining)), stream=True, allow_redirects=True) as response:
            if response.status_code != 200:
                result["reason"] = f"http_{response.status_code}"
                return result
            if not _safe_remote_url(response.url):
                result["reason"] = "unsafe_redirect"
                return result
            content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].lower()
            result["content_type"] = content_type
            if content_type and not any(content_type.startswith(prefix) for prefix in _ALLOWED_CONTENT_PREFIXES):
                result["reason"] = "unsupported_content_type"
                return result
            declared = int(response.headers.get("Content-Length") or 0)
            if declared > per_resource_limit:
                result["reason"] = "resource_too_large"
                return result
            filename = _asset_filename(response.url, content_type)
            path = os.path.join(folder, filename)
            with open(path, "wb") as handle:
                for chunk in response.iter_content(65536):
                    if not chunk:
                        continue
                    if time.monotonic() >= deadline:
                        raise TimeoutError("archive_deadline")
                    if reserved + len(chunk) > per_resource_limit:
                        raise ValueError("resource_too_large")
                    with shared_budget["lock"]:
                        if shared_budget["used"] + len(chunk) > shared_budget["limit"]:
                            raise ValueError("total_asset_budget_exhausted")
                        shared_budget["used"] += len(chunk)
                    reserved += len(chunk)
                    handle.write(chunk)
            if reserved <= 0:
                raise ValueError("empty_response")
            result.update(saved=True, bytes=reserved, filename=filename)
            return result
    except Exception as exc:
        result["reason"] = str(exc)[:120]
        with shared_budget["lock"]:
            shared_budget["used"] = max(0, shared_budget["used"] - reserved)
        if path and os.path.isfile(path):
            try:
                os.unlink(path)
            except Exception:
                pass
        return result


def _collect_assets(soup, base_url, maximum):
    references = {}
    for tag_name, attribute in _ASSET_FIELDS:
        for node in soup.find_all(tag_name):
            raw = node.get(attribute)
            if not raw or str(raw).startswith(("data:", "blob:", "javascript:")):
                continue
            canonical = urljoin(base_url, str(raw).strip())
            if canonical not in references and len(references) >= maximum:
                continue
            references.setdefault(canonical, []).append((node, attribute))
    return references


def _write_frames(folder, frame_documents):
    entries = []
    frames_folder = os.path.join(folder, "frames")
    for index, document in enumerate(list(frame_documents or []), start=1):
        entry = {
            "index": index,
            "url": str(document.get("url") or ""),
            "name": str(document.get("name") or ""),
            "saved": False,
            "truncated": bool(document.get("truncated")),
            "error": str(document.get("error") or "")[:200],
        }
        source = document.get("html") or ""
        if document.get("saved") and source:
            try:
                os.makedirs(frames_folder, exist_ok=True)
                relative = f"frames/frame_{index:03d}.html"
                with open(os.path.join(folder, *relative.split("/")), "w", encoding="utf-8", errors="replace") as handle:
                    handle.write(source)
                entry.update(saved=True, path=relative, bytes=len(source.encode("utf-8", errors="replace")))
            except Exception as exc:
                entry["error"] = str(exc)[:200]
        elif not entry["error"]:
            entry["error"] = "frame_content_unavailable"
        entries.append(entry)
    return entries


def savepage(url, page, session, instance_no="1", html_source=None, frame_documents=None, config=None, deadline=None):
    if html_source is None:
        try:
            html_source = page.content() if hasattr(page, "content") else page.page_source
        except Exception:
            html_source = "<html><body></body></html>"
    soup = BeautifulSoup(html_source or "<html><body></body></html>", "lxml")
    folder = os.path.join("zip", str(instance_no))
    os.makedirs(folder, exist_ok=True)
    maximum_count = int(_setting(config, "HTML_ASSET_MAX_COUNT", 120))
    per_resource = int(_setting(config, "HTML_ASSET_MAX_BYTES", 5 * 1024 * 1024))
    total_limit = int(_setting(config, "HTML_TOTAL_ASSET_MAX_BYTES", 12 * 1024 * 1024))
    workers = max(1, min(8, int(_setting(config, "HTML_ASSET_WORKERS", 4))))
    archive_seconds = float(_setting(config, "HTML_ARCHIVE_TIMEOUT_SECONDS", 25))
    if deadline is not None:
        deadline.check("html_archive")
        archive_seconds = min(archive_seconds, deadline.remaining())
    archive_deadline = time.monotonic() + max(0.1, archive_seconds)
    references = _collect_assets(soup, url, maximum_count)
    shared_budget = {"used": 0, "limit": total_limit, "lock": threading.Lock()}
    client = session if session is not None else requests.Session()
    results = {}
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="archive") as executor:
        futures = {
            executor.submit(_download_asset, client, asset_url, folder, per_resource, shared_budget, archive_deadline): asset_url
            for asset_url in references
        }
        for future in as_completed(futures):
            asset_url = futures[future]
            try:
                results[asset_url] = future.result()
            except Exception as exc:
                results[asset_url] = {"url": asset_url, "saved": False, "bytes": 0, "reason": str(exc)[:120]}
    for asset_url, nodes in references.items():
        result = results.get(asset_url, {})
        if result.get("saved"):
            for node, attribute in nodes:
                node[attribute] = result["filename"]
    with open(os.path.join(folder, "PowerAdSpy.html"), "w", encoding="utf-8", errors="replace") as handle:
        handle.write(soup.prettify())
    frame_entries = _write_frames(folder, frame_documents)
    manifest = {
        "version": 2,
        "source_url": url,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "limits": {"resource_bytes": per_resource, "total_asset_bytes": total_limit, "resource_count": maximum_count},
        "assets": [results.get(asset_url, {"url": asset_url, "saved": False, "reason": "not_attempted"}) for asset_url in references],
        "frames": frame_entries,
        "unsupported": ["css_url_dependencies", "font_dependencies", "video_bodies", "css_background_images", "dynamic_api_responses", "iframe_assets"],
    }
    with open(os.path.join(folder, "archive_manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    return folder


def get(page, r_session, current_url, instance_no, html_source=None, frame_documents=None, config=None, deadline=None):
    if not bool(_setting(config, "HTML_ARCHIVE_ENABLED", True)):
        return None
    folder = os.path.join("zip", str(instance_no))
    os.makedirs(folder, exist_ok=True)
    for filename in os.listdir(folder):
        path = os.path.join(folder, filename)
        try:
            if os.path.isfile(path) or os.path.islink(path):
                os.unlink(path)
            elif os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
        except Exception as exc:
            print(f"[HTML Cleanup Warning] {path}: {exc}")
    try:
        savepage(current_url, page, r_session, str(instance_no), html_source, frame_documents, config, deadline)
    except Exception as exc:
        print(f"[HTML Savepage Warning] {exc}")
        return None
    zip_path = os.path.join(folder, "html.zip")
    maximum_zip_bytes = int(_setting(config, "HTML_ARCHIVE_MAX_BYTES", 15 * 1024 * 1024))
    try:
        with ZipFile(zip_path, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
            for root, _dirs, files in os.walk(folder):
                for filename in files:
                    full_path = os.path.join(root, filename)
                    if os.path.abspath(full_path) == os.path.abspath(zip_path):
                        continue
                    archive.write(full_path, os.path.relpath(full_path, folder).replace(os.sep, "/"))
        if os.path.getsize(zip_path) > maximum_zip_bytes:
            os.unlink(zip_path)
            print(f"[HTML Zip Warning] Archive exceeded {maximum_zip_bytes} bytes and was omitted")
            return None
        with ZipFile(zip_path, "r") as archive:
            if archive.testzip() is not None:
                raise ValueError("ZIP integrity validation failed")
            required = {"PowerAdSpy.html", "archive_manifest.json"}
            if not required.issubset(set(archive.namelist())):
                raise ValueError("ZIP missing required archive entries")
        return zip_path
    except Exception as exc:
        print(f"[HTML Zip Error] Could not create valid zip: {exc}")
        try:
            if os.path.isfile(zip_path):
                os.unlink(zip_path)
        except Exception:
            pass
        return None
