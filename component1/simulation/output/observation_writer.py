"""
observation_writer.py
Serializes NormalizedObservation dicts to NDJSON (one JSON object per line).
Each line = one observation batch = Component 2 ingestion unit.
"""
import json
import os
from pathlib import Path
from typing import Dict, Any


class ObservationWriter:
    def __init__(self, output_path: str):
        self.path = Path(output_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.path, "w", encoding="utf-8")
        self._count = 0

    def write(self, observation: Dict[str, Any]) -> None:
        """Write one NormalizedObservation as a single NDJSON line."""
        self._file.write(json.dumps(observation, default=str) + "\n")
        self._file.flush()
        self._count += 1

    def close(self) -> None:
        self._file.close()

    @property
    def observations_written(self) -> int:
        return self._count

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
