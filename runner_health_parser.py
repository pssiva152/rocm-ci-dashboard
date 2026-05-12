"""
Parse the runner health dashboard MHTML file (saved from
https://therock-runner-health.com/) and expose:

  - SUMMARY:       aggregated online/offline counts and refresh time
  - PER_LABEL:     queue-status metrics per runner label (bad / ok)
  - PER_MACHINE:   list of individual runners with busy state + labels + pool

Usage:
    from runner_health_parser import load_runner_health, RunnerHealth
    rh = load_runner_health("TheRock Runner Health.mhtml")
    if rh:
        print(rh.summary)              # {'online': 297, 'offline': 30, ...}
        print(rh.per_label["linux-gfx942-1gpu-ossci-rocm"])
        for m in rh.per_machine:
            print(m["name"], m["busy"], m["labels"])

If the MHTML is missing or malformed, load_runner_health() returns None
and the calling code should gracefully skip the enrichment.
"""
from __future__ import annotations

import email
import re
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


def load_runner_health(path: str | Path) -> Optional[RunnerHealth]:
    p = Path(path)
    if not p.exists():
        return None
    try:
        html = _extract_html_part(p)
        if not html:
            return None
        rh = RunnerHealth(raw_size=len(html))
        m = re.search(r'Last refresh[^<]*:\s*[^<]*<b>([^<]+)</b>', html, re.S)
        if m:
            rh.refresh_time = m.group(1).strip()
        rh.summary     = _parse_summary(html)
        rh.per_label   = _parse_per_label_metrics(html)
        rh.per_machine = _parse_per_machine(html)
        return rh
    except Exception as e:
        print(f"[runner_health_parser] WARN: failed to parse {p}: {e}")
        return None


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    rh = load_runner_health("TheRock Runner Health.mhtml")
    if not rh:
        print("No runner health data available.")
        raise SystemExit(0)
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
