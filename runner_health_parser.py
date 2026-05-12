"""
Parse runner-health dashboard data (from https://therock-runner-health.com/)
and expose:

  - SUMMARY:       aggregated online/offline counts and refresh time
  - PER_LABEL:     queue-status metrics per runner label (bad / ok)
  - PER_MACHINE:   list of individual runners with busy state + labels + pool

Three load paths (use `load_runner_health_any` to try them all in order):

  1. Local MHTML file       — saved manually from the dashboard while logged
                              into GitHub on the AMD VPN. NOT committed to
                              git (it's a verbatim dump of an internal page).
  2. Live HTTPS fetch       — anonymous GET against the dashboard URL. Will
                              succeed only if the network can reach the host
                              AND the response isn't a GitHub login redirect.
                              Most users on a clean shell will silently fail
                              this step and fall through to the snapshot.
  3. JSON snapshot          — cached copy of the parsed data, committed to
                              git so the report can always be rendered.
                              Refreshed automatically after a successful
                              MHTML or live fetch.

Quick use:
    from runner_health_parser import load_runner_health_any, RunnerHealth
    rh, src = load_runner_health_any(
        mhtml_candidates=["TheRock Runner Health.mhtml"],
        live_url="https://therock-runner-health.com/",
        snapshot_path="runner_health_snapshot.json",
    )
    if rh:
        print(f"Loaded from {src!r}, refresh={rh.refresh_time}, machines={len(rh.per_machine)}")
"""
from __future__ import annotations

import datetime
import email
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class RunnerHealth:
    refresh_time: str = ""
    summary: dict = field(default_factory=dict)
    per_label: dict = field(default_factory=dict)
    per_machine: list = field(default_factory=list)
    raw_size: int = 0

    def label_status(self, label: str) -> str:
        """Return 'bad' / 'ok' / 'unknown' for a given runner label."""
        return self.per_label.get(label, {}).get("status", "unknown")

    @staticmethod
    def physical_id(name: str) -> str:
        """Map a runner-registration name to a stable physical-machine
        identifier so that **multiple GHA runner registrations on the
        same physical box** are not double-counted.

        Pattern stripped:
          * Per-GPU runner suffix:  '-gpu0-1778145612' / '-gpu1-...'
            (one physical GPU server registers N runners, one per GPU
             — same hardware, different GPU slot)

        Patterns kept (each represents a separate VM / container, NOT
        the same physical machine):
          * ARC ephemeral suffix:  '-<5char-pool-id>-runner-<rand>'
            Each such runner is a distinct ephemeral VM/pod in the
            elastic pool (e.g. 84× linux-gfx942-1gpu-ossci-rocm-vth9c-
            runner-XXX = 84 distinct VMs).
        """
        s = re.sub(r'-gpu\d+-\d+$', '', name)
        return s

    def machines_for_label(self, label: str) -> list:
        return [m for m in self.per_machine if label in m.get("labels", [])]

    def label_busy_idle(self, label: str) -> tuple:
        """Return (busy_count, idle_count) of *physical online* machines for
        label. Multiple runners on the same physical hardware (per-GPU or
        ARC ephemeral) are deduplicated by `physical_id`.
        A machine is considered busy if ANY runner on it is busy."""
        machines = self.machines_for_label(label)
        seen: dict = {}
        for m in machines:
            phys = self.physical_id(m["name"])
            prev = seen.get(phys)
            if prev is None:
                seen[phys] = m["busy"]
            else:
                seen[phys] = prev or m["busy"]   # OR-merge busy state
        busy = sum(1 for v in seen.values() if v)
        idle = len(seen) - busy
        return busy, idle

    def family_busy_idle(self, labels: list) -> tuple:
        """Cross-label dedup: for a list of runner labels in the same gfx
        family, return (busy_count, idle_count) counting each physical
        machine ONCE even if it carries multiple labels (e.g. a strix-halo
        node that registers under linux-gfx1151-gpu-rocm AND
        linux-strix-halo-gpu-rocm-oem AND linux-gfx115X-gpu-rocm)."""
        seen: dict = {}
        for lbl in labels:
            for m in self.machines_for_label(lbl):
                phys = self.physical_id(m["name"])
                prev = seen.get(phys)
                seen[phys] = (prev or m["busy"]) if prev is not None else m["busy"]
        busy = sum(1 for v in seen.values() if v)
        idle = len(seen) - busy
        return busy, idle

    # ── JSON-snapshot serialization (used as fallback when no MHTML is on
    #    disk and the live dashboard is unreachable) ────────────────────────
    def to_dict(self) -> dict:
        """Serializable representation; suitable for JSON snapshot."""
        return {
            "refresh_time": self.refresh_time,
            "summary":      self.summary,
            "per_label":    self.per_label,
            "per_machine":  self.per_machine,
            "raw_size":     self.raw_size,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RunnerHealth":
        return cls(
            refresh_time = d.get("refresh_time", ""),
            summary      = d.get("summary", {}) or {},
            per_label    = d.get("per_label", {}) or {},
            per_machine  = d.get("per_machine", []) or [],
            raw_size     = int(d.get("raw_size", 0) or 0),
        )

    def save_snapshot(self, path: str | Path) -> None:
        """Write a JSON snapshot of the parsed data, plus a capture timestamp."""
        try:
            import zoneinfo
            _pt = zoneinfo.ZoneInfo("America/Los_Angeles")
        except ImportError:
            _pt = datetime.timezone(datetime.timedelta(hours=-7))
        captured = datetime.datetime.now(_pt).strftime("%Y-%m-%d %I:%M %p %Z")
        payload = {
            "_schema_version":   1,
            "_captured":         captured,
            "_source_note":      "Snapshot of the parsed runner-health data. "
                                 "Used as a fallback when the .mhtml is absent "
                                 "and the live dashboard is unreachable.",
            **self.to_dict(),
        }
        Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                              encoding="utf-8")

    @classmethod
    def load_snapshot(cls, path: str | Path) -> Optional["RunnerHealth"]:
        p = Path(path)
        if not p.exists():
            return None
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            return cls.from_dict(d)
        except Exception as e:
            print(f"[runner_health_parser] WARN: bad snapshot {p}: {e}")
            return None


def _extract_html_part(mhtml_path: Path) -> str:
    """Decode the MHTML envelope; return the runner-health HTML part."""
    raw = mhtml_path.read_bytes()
    msg = email.message_from_bytes(raw)
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            cloc = part.get("Content-Location", "")
            if "runner-health" in cloc:
                payload = part.get_payload(decode=True)
                return payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else payload
    return ""


def _parse_summary(html: str) -> dict:
    """Find the top-level Online / Offline / Busy / Idle counts."""
    out = {}
    for label_text, key in [
        ("Online", "online"), ("Offline", "offline"),
        ("Busy (online)", "busy"), ("Idle (online)", "idle"),
    ]:
        m = re.search(rf'<td[^>]*>{re.escape(label_text)}</td><td[^>]*>(\d+)</td>', html)
        if m:
            out[key] = int(m.group(1))
    # Aggregated by Resource (CPU vs GPU)
    out["resource"] = {}
    for row in re.finditer(
        r'<tr class="(\w*)">\s*<td><b>(CPU|GPU)</b></td>'
        r'\s*<td>(\d+)</td>\s*<td>(\d+)</td>\s*<td>(\d+)</td>'
        r'\s*<td>(\d+)</td>\s*<td>(\d+)</td>',
        html,
    ):
        cls, kind, total, online, offline, busy, idle = row.groups()
        out["resource"][kind] = {
            "total": int(total), "online": int(online), "offline": int(offline),
            "busy": int(busy), "idle": int(idle),
            "status_class": cls or "ok",
        }
    return out


def _parse_per_label_metrics(html: str) -> dict:
    """Parse the per-label queue-time table.

    Each row looks like:
      <tr class="bad"><td><code>LABEL</code></td>
        <td>...</td>     # avg jobs/hr queued > 10m
        <td>JOBS_6H</td> # jobs over 6h
        <td>MEDIAN_Q</td>
        <td><b>WORST_Q</b></td>
        <td>MEDIAN_DUR</td>
        <td><b>WORST_DUR</b></td>
      </tr>
    """
    out = {}
    pat = re.compile(
        r'<tr class="(\w*)">\s*<td><code>([^<]+)</code></td>'
        r'\s*<td[^>]*>([^<]+)</td>'
        r'\s*<td[^>]*>([^<]+)</td>'
        r'\s*<td[^>]*>([^<]+)</td>'
        r'\s*<td[^>]*><b>([^<]+)</b></td>'
        r'\s*<td[^>]*>([^<]+)</td>'
        r'\s*<td[^>]*><b>([^<]+)</b></td>',
        re.S,
    )
    for m in pat.finditer(html):
        cls, label, avg_q, jobs_6h, med_q, worst_q, med_dur, worst_dur = m.groups()
        out[label.strip()] = {
            "status": "bad" if cls == "bad" else "ok",
            "avg_queued_per_hr": avg_q.strip(),
            "jobs_6h": jobs_6h.strip(),
            "median_queue": med_q.strip(),
            "worst_queue": worst_q.strip(),
            "median_duration": med_dur.strip(),
            "worst_duration": worst_dur.strip(),
        }
    return out


def _parse_per_machine(html: str) -> list:
    """Walk the per-machine <details> blocks and extract runner instances.

    Each <details> has a <summary><b>POOL_NAME</b> (N)</summary> followed by
    a <table> of <tr><td><b>RUNNER_NAME</b></td><td>BUSY</td><td>LABELS</td></tr>.
    The detail tables only enumerate ONLINE runners (offline machines are
    summarized in the aggregate counts but not listed individually).
    """
    machines = []
    # Find all <details> with a numeric "(N)" suffix in their summary
    detail_pat = re.compile(
        r'<details>\s*<summary><b>([^<]+?)</b>\s*\((\d+)\)</summary>'
        r'\s*<div class="content indent">\s*<table>(.*?)</table>',
        re.S,
    )
    row_pat = re.compile(
        r'<tr><td><b>([^<]+)</b></td><td>(yes|no)</td><td>([^<]*)</td></tr>'
    )
    # ARC ephemeral runner naming: "<label>-<5-char-pool-id>-runner-<rand>"
    # The labels column is often empty for these because labels are inherited
    # from the underlying runner pool, so derive from the name prefix.
    arc_pat = re.compile(r'^(.+?)-[a-z0-9]{5}-runner-[a-z0-9]+$')
    for d in detail_pat.finditer(html):
        pool = d.group(1).strip()
        for r in row_pat.finditer(d.group(3)):
            name = r.group(1).strip()
            busy = r.group(2) == "yes"
            labels_raw = r.group(3).strip()
            labels = [l.strip() for l in labels_raw.split(",") if l.strip()]
            # Fallback: derive label from ARC-style name prefix
            if not labels:
                m = arc_pat.match(name)
                if m:
                    labels = [m.group(1)]
            machines.append({
                "name": name,
                "busy": busy,
                "labels": labels,
                "pool": pool,
            })
    return machines


def _parse_html(html: str) -> Optional[RunnerHealth]:
    """Parse an already-decoded runner-health HTML body into a RunnerHealth."""
    if not html or "Last refresh" not in html:
        return None
    rh = RunnerHealth(raw_size=len(html))
    m = re.search(r'Last refresh[^<]*:\s*[^<]*<b>([^<]+)</b>', html, re.S)
    if m:
        rh.refresh_time = m.group(1).strip()
    rh.summary     = _parse_summary(html)
    rh.per_label   = _parse_per_label_metrics(html)
    rh.per_machine = _parse_per_machine(html)
    if not rh.summary and not rh.per_label and not rh.per_machine:
        return None
    return rh


def load_runner_health(path: str | Path) -> Optional[RunnerHealth]:
    """Load runner-health data from a saved MHTML page on disk."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        html = _extract_html_part(p)
        return _parse_html(html)
    except Exception as e:
        print(f"[runner_health_parser] WARN: failed to parse MHTML {p}: {e}")
        return None


def _fetch_live_anonymous(url: str, timeout: float) -> Optional[str]:
    """Cheap anonymous urllib GET. Returns HTML body or None.

    Almost always returns None for therock-runner-health.com (the URL is
    GitHub-OAuth-gated and we get a sign-in page back), but it's a 1-second
    probe that's worth keeping in case the dashboard ever opens up or the
    user happens to be on a network that proxies in cookies.
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "rocm-cicd-report/1.0 (+runner-health fetcher)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final_url = resp.geturl()
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as e:
        print(f"[runner_health_parser] anonymous live fetch FAIL: {e}")
        return None

    if "github.com" in final_url.lower() or "<title>Sign in to GitHub" in body:
        print("[runner_health_parser] anonymous live fetch: redirected to GitHub login.")
        return None
    return body


def _fetch_live_playwright(url: str) -> Optional[str]:
    """Try the Playwright-based fetch (persistent Chromium profile). Returns
    HTML body or None. Disabled by RUNNER_HEALTH_NO_PLAYWRIGHT=1; silently
    no-ops when the playwright package isn't installed."""
    try:
        from runner_health_playwright import fetch_via_playwright
    except ImportError:
        return None
    try:
        return fetch_via_playwright(url)
    except Exception as e:
        print(f"[runner_health_parser] playwright fetch FAIL: {e}")
        return None


def fetch_live(url: str = "https://therock-runner-health.com/",
               timeout: float = 10.0) -> Optional[RunnerHealth]:
    """Attempt to fetch the live dashboard via two mechanisms in order:

      (a) Anonymous urllib GET — fast probe; almost always falls through
          because the dashboard is gated by GitHub OAuth.
      (b) Playwright with persistent Chromium profile — opt-in (requires
          `pip install playwright && python -m playwright install chromium`).
          First run is interactive (visible browser for one-time GitHub
          sign-in); subsequent runs are silent and headless using the
          cached session.

    Returns a parsed `RunnerHealth` on success, or None so the caller can
    fall through to the JSON snapshot.
    """
    html = _fetch_live_anonymous(url, timeout)
    if html is None:
        html = _fetch_live_playwright(url)
    if html is None:
        return None

    rh = _parse_html(html)
    if rh is None:
        print("[runner_health_parser] live fetch: response did not look like "
              "the runner-health dashboard — falling back.")
    return rh


def load_runner_health_any(
    mhtml_candidates: Optional[list] = None,
    live_url: Optional[str] = "https://therock-runner-health.com/",
    snapshot_path: Optional[str | Path] = "runner_health_snapshot.json",
    refresh_snapshot: bool = True,
    try_live: bool = True,
) -> tuple[Optional[RunnerHealth], Optional[str]]:
    """Three-tier loader: local MHTML → live HTTPS → JSON snapshot.

    Returns ``(RunnerHealth | None, source_label | None)`` where
    ``source_label`` is one of ``"mhtml"``, ``"live"``, ``"snapshot"``.

    When the load succeeds via mhtml or live, the snapshot at
    ``snapshot_path`` is refreshed (if ``refresh_snapshot`` is True) so the
    next snapshot-only run sees the latest numbers.
    """
    # 1) Local MHTML
    for cand in (mhtml_candidates or []):
        p = Path(cand)
        if not p.exists():
            continue
        rh = load_runner_health(p)
        if rh:
            print(f"[runner_health_parser] mhtml OK: {p.name} "
                  f"({len(rh.per_machine)} machines, "
                  f"{len(rh.per_label)} labels, refresh={rh.refresh_time!r})")
            if refresh_snapshot and snapshot_path:
                try:
                    rh.save_snapshot(snapshot_path)
                    print(f"[runner_health_parser] snapshot refreshed -> {snapshot_path}")
                except Exception as e:
                    print(f"[runner_health_parser] WARN: could not refresh snapshot: {e}")
            return rh, "mhtml"

    # 2) Live HTTPS
    if try_live and live_url:
        rh = fetch_live(live_url)
        if rh:
            print(f"[runner_health_parser] live OK: {live_url} "
                  f"({len(rh.per_machine)} machines, "
                  f"{len(rh.per_label)} labels, refresh={rh.refresh_time!r})")
            if refresh_snapshot and snapshot_path:
                try:
                    rh.save_snapshot(snapshot_path)
                    print(f"[runner_health_parser] snapshot refreshed -> {snapshot_path}")
                except Exception as e:
                    print(f"[runner_health_parser] WARN: could not refresh snapshot: {e}")
            return rh, "live"

    # 3) JSON snapshot fallback
    if snapshot_path:
        rh = RunnerHealth.load_snapshot(snapshot_path)
        if rh:
            print(f"[runner_health_parser] snapshot OK: {snapshot_path} "
                  f"({len(rh.per_machine)} machines, "
                  f"{len(rh.per_label)} labels, refresh={rh.refresh_time!r})")
            return rh, "snapshot"

    return None, None


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    rh, src = load_runner_health_any(
        mhtml_candidates=["TheRock Runner Health.mhtml", "runner_health.mhtml",
                          "runner-health.mhtml", "TheRockRunnerHealth.mhtml"],
        live_url="https://therock-runner-health.com/",
        snapshot_path="runner_health_snapshot.json",
    )
    if not rh:
        print("No runner health data available (no mhtml, live unreachable, no snapshot).")
        raise SystemExit(0)
    print(f"Source : {src}")
    print(f"Refresh: {rh.refresh_time}")
    print(f"Summary: {rh.summary}")
    print(f"Per-label entries: {len(rh.per_label)}")
    print(f"Per-machine entries: {len(rh.per_machine)}")
    print()
    print("Sample per-label rows:")
    for k in list(rh.per_label)[:5]:
        print(f"  {k}: {rh.per_label[k]}")
    print()
    print("Sample machines:")
    for m in rh.per_machine[:5]:
        print(f"  {m['name']:<70}  busy={m['busy']}  pool={m['pool']}  labels={m['labels'][:3]}")

    # Cross-reference with our snapshot's RUNNER_DATA labels
    print("\n=== Cross-reference: per-label coverage for our key runners ===")
    key_labels = [
        "linux-gfx942-1gpu-ossci-rocm", "linux-gfx942-1gpu-ccs-ossci-rocm",
        "linux-gfx942-1gpu-core42-ossci-rocm", "linux-gfx942-8gpu-ossci-rocm",
        "linux-gfx950-1gpu-ccs-ossci-rocm", "linux-gfx950-8gpu-ccs-ossci-rocm",
        "linux-gfx90a-gpu-rocm", "linux-gfx110X-gpu-rocm", "linux-gfx1151-gpu-rocm",
        "windows-gfx1151-gpu-rocm", "windows-gfx110X-gpu-rocm",
    ]
    for lbl in key_labels:
        busy, idle = rh.label_busy_idle(lbl)
        machines = rh.machines_for_label(lbl)
        status = rh.label_status(lbl)
        print(f"  {lbl:<45}  online={len(machines):>3}  busy={busy:>2}  idle={idle:>2}  status={status}")
