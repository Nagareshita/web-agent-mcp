"""Tests for SSRF safety module."""
import pytest
from web_agent_mcp.fetch.safety import validate_url


def test_valid_https():
    validate_url("https://example.com/page")


def test_blocks_localhost():
    with pytest.raises(ValueError, match="private"):
        validate_url("http://localhost/secret")


def test_blocks_127():
    with pytest.raises(ValueError, match="private"):
        validate_url("http://127.0.0.1/secret")


def test_blocks_file_scheme():
    with pytest.raises(ValueError, match="not allowed"):
        validate_url("file:///etc/passwd")


def test_blocks_metadata_endpoint():
    with pytest.raises(ValueError, match="metadata"):
        validate_url("http://169.254.169.254/latest/meta-data/")
