"""Snapshot and rollback management for DOOM."""

from datetime import datetime
from pathlib import Path
import shutil


class SnapshotManager:
    """Creates, lists, and restores file snapshots stored under .doom/snapshots/."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.snapshots_dir = workspace_root / ".doom" / "snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    def create_snapshot(self, relative_path_str: str) -> tuple[bool, str]:
        """Backs up the existing file before an overwrite or major edit."""
        try:
            source_file = (self.workspace_root / relative_path_str).resolve()
            if not source_file.exists() or not source_file.is_file():
                return False, f"Cannot snapshot '{relative_path_str}': file does not exist."

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Replace slashes and backslashes with underscores for the backup filename
            sanitized_name = relative_path_str.replace("/", "_").replace("\\", "_")
            backup_filename = f"{sanitized_name}.{timestamp}.bak"
            backup_path = self.snapshots_dir / backup_filename

            shutil.copy2(source_file, backup_path)
            return True, f"Snapshot created: {backup_filename}"

        except Exception as e:
            return False, f"Failed to create snapshot: {e}"

    def list_snapshots(self, relative_path_str: str = "") -> list[dict[str, str]]:
        """Lists available snapshots, optionally filtered by file path."""
        snapshots = []
        target_prefix = ""
        if relative_path_str:
            target_prefix = relative_path_str.replace("/", "_").replace("\\", "_")

        for backup_file in sorted(self.snapshots_dir.glob("*.bak"), reverse=True):
            if target_prefix and not backup_file.name.startswith(target_prefix):
                continue

            parts = backup_file.name.split(".")
            # Expected format: <filename>.<timestamp>.bak
            if len(parts) >= 3:
                original_file = ".".join(parts[:-2])
                raw_time = parts[-2]
                try:
                    dt = datetime.strptime(raw_time, "%Y%m%d_%H%M%S")
                    formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    formatted_time = raw_time

                snapshots.append({
                    "original": original_file,
                    "timestamp": formatted_time,
                    "backup_path": str(backup_file),
                })

        return snapshots

    def restore_latest_snapshot(self, relative_path_str: str) -> tuple[bool, str]:
        """Restores the most recent snapshot for the specified file."""
        try:
            matching = self.list_snapshots(relative_path_str)
            if not matching:
                return False, f"No snapshots found for '{relative_path_str}'."

            latest_backup = Path(matching[0]["backup_path"])
            target_file = (self.workspace_root / relative_path_str).resolve()

            if not target_file.is_relative_to(self.workspace_root):
                return False, f"Access denied: '{relative_path_str}' is outside workspace."

            shutil.copy2(latest_backup, target_file)
            return True, f"Restored '{relative_path_str}' from snapshot ({matching[0]['timestamp']})."

        except Exception as e:
            return False, f"Failed to restore snapshot: {e}"