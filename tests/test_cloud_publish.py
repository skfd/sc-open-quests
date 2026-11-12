"""tools/cloud_publish.py: the guards that keep a broken checkout from emptying the site. No network."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import cloud_publish as cp  # noqa: E402

WHOLE = ["index.html", "app.js", "style.css", "data/cities.json", "data/history/toronto.json"]


def test_whole_site_passes():
    cp.check_source(WHOLE, remote_count=5)
    cp.check_source(WHOLE, remote_count=0)  # an empty bucket: the first upload


@pytest.mark.parametrize("missing", ["index.html", "app.js", "data/cities.json"])
def test_missing_core_file_refused(missing):
    with pytest.raises(RuntimeError, match=missing):
        cp.check_source([f for f in WHOLE if f != missing], remote_count=5)


def test_far_fewer_files_than_the_bucket_refused():
    with pytest.raises(RuntimeError, match="partial"):
        cp.check_source(WHOLE, remote_count=100)


def test_beacon_removed_from_html():
    page = b'<p>x</p>\n<script defer src="https://static.cloudflareinsights.com/beacon.min.js/v1" data-cf-beacon=\'{}\'></script>\n</body>'
    assert cp.BEACON.sub(b"", page) == b"<p>x</p>\n</body>"


def test_env_file(tmp_path):
    f = tmp_path / "cloudflare.env"
    f.write_text("# comment\nCLOUDFLARE_API_TOKEN=abc\nCLOUDFLARE_ACCOUNT_ID=123\n")
    assert cp.read_env(f) == {"CLOUDFLARE_API_TOKEN": "abc", "CLOUDFLARE_ACCOUNT_ID": "123"}
    f.write_text("CLOUDFLARE_API_TOKEN=abc\n")
    with pytest.raises(RuntimeError, match="CLOUDFLARE_ACCOUNT_ID"):
        cp.read_env(f)
    with pytest.raises(RuntimeError, match="no Cloudflare token file"):
        cp.read_env(tmp_path / "absent.env")
