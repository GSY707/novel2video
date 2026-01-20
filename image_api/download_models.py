import os
import json
import hashlib
import time
import requests
from pathlib import Path
from typing import Dict, Any, List

from huggingface_hub import snapshot_download

try:
    from . import config
except ImportError:
    import modules.config as config  # 允许直接运行


# =========================
# 基础路径
# =========================

BASE_DIR = Path(config.BASE_DIR)
MODEL_ROOT = Path(config.MODEL_ROOT)
STATE_ROOT = BASE_DIR / ".model_state"
STATE_HTTP = STATE_ROOT / "http"
STATE_HF = STATE_ROOT / "hf"

STATE_HTTP.mkdir(parents=True, exist_ok=True)
STATE_HF.mkdir(parents=True, exist_ok=True)

MAX_RETRY = 3
CHUNK_SIZE = 1024 * 1024  # 1MB


# =========================
# 工具函数
# =========================

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_state_name(path: Path) -> str:
    return str(path).replace(os.sep, "__")


def load_state(path: Path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_state(path: Path, data: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# =========================
# Registry 构建
# =========================

def build_download_registry(models: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """
    从 config.MODELS 派生下载用 registry
    """
    registry: Dict[str, List[Dict[str, Any]]] = {}

    for model_name, conf in models.items():
        artifacts = []

        if "hf_repo_id" in conf:
            artifacts.append({
                "kind": "hf_snapshot",
                "model_name": model_name,
                "repo_id": conf["hf_repo_id"],
                "local_dir": Path(conf["path"]),
                "key_files": ["*.safetensors"]
            })

        if "hf_file_url" in conf:
            artifacts.append({
                "kind": "http_file",
                "model_name": model_name,
                "url": conf["hf_file_url"],
                "local_path": Path(conf["path"]),
            })

        if artifacts:
            registry[model_name] = artifacts

    return registry


# =========================
# HTTP 大文件下载（断点续传）
# =========================

def download_http_file(artifact: Dict[str, Any]):
    target = artifact["local_path"]
    state_file = STATE_HTTP / f"{safe_state_name(target)}.json"
    part_file = target.with_suffix(target.suffix + ".part")

    retry = 0

    while retry < MAX_RETRY:
        # 已存在文件，尝试校验
        if target.exists():
            state = load_state(state_file)
            size = target.stat().st_size

            if state is None:
                print(f"[INFO] Register existing file: {target}")
                sha = sha256_file(target)
                save_state(state_file, {
                    "path": str(target),
                    "size": size,
                    "sha256": sha,
                    "verified_at": time.time()
                })
                return

            if size != state["size"]:
                print(f"[WARN] Size mismatch, re-downloading: {target}")
                target.unlink()
                retry += 1
                continue

            sha = sha256_file(target)
            if sha == state["sha256"]:
                print(f"[OK] Verified: {target}")
                return

            print(f"[WARN] Hash mismatch, force overwrite: {target}")
            target.unlink()
            retry += 1
            continue

        # 下载流程
        target.parent.mkdir(parents=True, exist_ok=True)

        headers = {}
        downloaded = 0
        if part_file.exists():
            downloaded = part_file.stat().st_size
            headers["Range"] = f"bytes={downloaded}-"

        print(f"[DOWNLOAD] {artifact['url']} → {target}")
        with requests.get(artifact["url"], stream=True, headers=headers) as r:
            r.raise_for_status()
            mode = "ab" if downloaded else "wb"
            with part_file.open(mode) as f:
                for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)

        part_file.rename(target)

        # 校验
        sha = sha256_file(target)
        size = target.stat().st_size
        save_state(state_file, {
            "path": str(target),
            "size": size,
            "sha256": sha,
            "verified_at": time.time()
        })
        print(f"[OK] Downloaded & verified: {target}")
        return

    raise RuntimeError(f"HTTP download failed after {MAX_RETRY} retries: {target}")


# =========================
# HuggingFace Snapshot 下载
# =========================

def find_key_file(folder: Path, patterns: List[str]) -> Path | None:
    for pat in patterns:
        files = list(folder.rglob(pat))
        if files:
            return max(files, key=lambda p: p.stat().st_size)
    return None


def download_hf_snapshot(artifact: Dict[str, Any]):
    local_dir = artifact["local_dir"]
    state_file = STATE_HF / f"{safe_state_name(local_dir)}.json"

    retry = 0

    while retry < MAX_RETRY:
        snapshot_download(
            repo_id=artifact["repo_id"],
            local_dir=str(local_dir),
            local_dir_use_symlinks=False
        )

        key_file = find_key_file(local_dir, artifact["key_files"])
        if not key_file:
            retry += 1
            print(f"[WARN] Key file not found in {local_dir}, retrying...")
            continue

        state = load_state(state_file)
        sha = sha256_file(key_file)

        if state is None:
            print(f"[INFO] Register HF model: {local_dir}")
            save_state(state_file, {
                "path": str(local_dir),
                "key_file": str(key_file),
                "sha256": sha,
                "verified_at": time.time()
            })
            return

        if sha == state["sha256"]:
            print(f"[OK] Verified HF model: {local_dir}")
            return

        print(f"[WARN] HF hash mismatch, re-downloading: {local_dir}")
        retry += 1
        for item in local_dir.iterdir():
            if item.is_file():
                item.unlink()

    raise RuntimeError(f"HF snapshot failed after {MAX_RETRY} retries: {local_dir}")


# =========================
# 主流程
# =========================

def main():
    print("=== Model preparation started ===")

    registry = build_download_registry(config.MODELS)

    for model_name, artifacts in registry.items():
        print(f"\n[MODEL] {model_name}")
        for art in artifacts:
            if art["kind"] == "http_file":
                download_http_file(art)
            elif art["kind"] == "hf_snapshot":
                download_hf_snapshot(art)

    print("\n=== All models ready ===")
    print("Offline environment prepared successfully.")


if __name__ == "__main__":
    main()
