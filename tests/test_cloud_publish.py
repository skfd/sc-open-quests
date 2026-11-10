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


def test_deploy_summary_reads_wranglers_output():
    out = "Uploaded 1000 of 4836 assets\nUploaded 176 of 176 assets\nCurrent Version ID: c08fc746-2bc4\n"
    assert cp.deploy_summary(out) == "176 of 176 files uploaded, version c08fc746-2bc4"
    out = "No updated asset files to upload. Proceeding with deployment...\nCurrent Version ID: abc\n"
    assert cp.deploy_summary(out) == "no file changed, version abc"
    assert cp.deploy_summary("something else") == "upload count not reported, version not reported"


def _site(tmp_path, extra=()):
    for rel in [*WHOLE, *extra]:
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(rel)
    return tmp_path


def test_deploy_refuses_more_files_than_one_version_takes(tmp_path, monkeypatch):
    monkeypatch.setattr(cp, "MAX_ASSETS", 3)
    with pytest.raises(RuntimeError, match="takes 3"):
        cp.deploy(docs=_site(tmp_path))


def test_deploy_says_how_to_install_wrangler(tmp_path, monkeypatch):
    monkeypatch.setattr(cp, "WRANGLER", tmp_path / "absent" / "wrangler.js")
    with pytest.raises(RuntimeError, match="npm install"):
        cp.deploy(docs=_site(tmp_path))


def test_check_skips_the_files_cloudflare_does_not_serve(tmp_path, monkeypatch):
    docs = _site(tmp_path, extra=["_headers"])
    asked = []

    def fetch(rel):
        asked.append(rel)
        return rel, cp.hashlib.md5((docs / rel).read_bytes()).hexdigest(), 200

    monkeypatch.setattr(cp, "_fetch_md5", fetch)
    assert cp.check(docs=docs, workers=2) == 0
    assert "_headers" not in asked and sorted(asked) == sorted(WHOLE)
