import json
import os
import uuid
from pathlib import Path


class SessionStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.buffers = self.directory / "buffers"
        self.index_file = self.directory / "session.json"

    def save(self, entries, active_index):
        self.buffers.mkdir(parents=True, exist_ok=True)
        stored = []
        keep = set()
        for entry in entries:
            record = {key: value for key, value in entry.items() if key != "text"}
            text = entry.get("text")
            if text is not None:
                buffer_name = entry.get("buffer") or f"{uuid.uuid4().hex}.txt"
                self.write_atomic(self.buffers / buffer_name, text.encode("utf-8", errors="surrogatepass"))
                record["buffer"] = buffer_name
                keep.add(buffer_name)
            else:
                record.pop("buffer", None)
            stored.append(record)
        self.write_atomic(
            self.index_file,
            json.dumps({"version": 1, "active": active_index, "documents": stored}, ensure_ascii=False, indent=1).encode("utf-8"),
        )
        for leftover in self.buffers.iterdir():
            if leftover.name not in keep:
                leftover.unlink(missing_ok=True)

    def load(self):
        try:
            data = json.loads(self.index_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return [], 0
        documents = []
        for record in data.get("documents", []):
            if not isinstance(record, dict):
                continue
            buffer_name = record.get("buffer")
            if buffer_name:
                try:
                    record["text"] = (self.buffers / buffer_name).read_bytes().decode("utf-8", errors="replace")
                except OSError:
                    record["text"] = None
                    record["buffer"] = None
            documents.append(record)
        return documents, int(data.get("active", 0))

    def clear(self):
        self.index_file.unlink(missing_ok=True)
        if self.buffers.is_dir():
            for leftover in self.buffers.iterdir():
                leftover.unlink(missing_ok=True)

    @staticmethod
    def write_atomic(path, payload):
        temporary = path.with_name(path.name + ".tmp")
        with open(temporary, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
