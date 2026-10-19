"""Offline tests: deterministic stub providers, no API keys, no paid calls."""
import os

os.environ["INSIGHT_FAKE"] = "1"  # must be set before pipeline.clients is imported
