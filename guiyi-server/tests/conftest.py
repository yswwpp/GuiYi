import os

# Force CPU and low content threshold for tests to avoid MPS OOM
os.environ.setdefault("GUIYI_EMBEDDING_DEVICE", "cpu")
os.environ.setdefault("GUIYI_MIN_CONTENT_LENGTH", "0")
