"""
Playwright-based live fetch for therock-runner-health.com.

The dashboard sits behind GitHub OAuth, so a plain `urllib` GET is bounced
to a GitHub sign-in page. This module drives Chromium with a *persistent*
user-data directory so the OAuth flow runs **once** interactively (visible
browser window, you sign in to GitHub) and is then reused **silently** on
every subsequent run (headless, no window).

  Setup (one-time, per user):

      pip install playwright
      python -m playwright install chromium

  First run (interactive):

      python generate_rocm_html.py
      # → "[runner_health_playwright] First run: opening Chromium..."
      # → a Chromium window appears at https://therock-runner-health.com/
      # → click "Sign in with GitHub", complete the OAuth flow
      # → the script captures the dashboard HTML and continues

  Subsequent runs (silent, headless):

      python generate_rocm_html.py
      # → "[runner_health_playwright] Reusing cached session ..."
      # → no window appears; dashboard is fetched headlessly

  When the cached session expires (typically every few days, controlled by
  GitHub's session lifetime), the script automatically retries with a
  visible browser so you can re-authenticate, then resumes silent runs.

  Disable entirely (e.g. on CI where you have no display and don't want the
  Chromium download):

      set RUNNER_HEALTH_NO_PLAYWRIGHT=1     # Windows cmd
      $env:RUNNER_HEALTH_NO_PLAYWRIGHT='1'  # Windows PowerShell
      export RUNNER_HEALTH_NO_PLAYWRIGHT=1  # macOS/Linux

  Override the profile directory (default: ~/.rocm-cicd-report/playwright-profile):

      set RUNNER_HEALTH_PLAYWRIGHT_PROFILE=D:/path/to/my-profile

  Give yourself more time to complete first-run sign-in (default: 300s = 5 min):

      set RUNNER_HEALTH_PLAYWRIGHT_TIMEOUT=600
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

DEFAULT_PROFILE_DIR = Path.home() / ".rocm-cicd-report" / "playwright-profile"
DASHBOARD_MARKER    = "Last refresh"   # text we expect in a successful page
LOGIN_MARKER        = "sign in"        # case-insensitive title check


def _profile_dir() -> Path:
    custom = os.environ.get("RUNNER_HEALTH_PLAYWRIGHT_PROFILE")
    return Path(custom).expanduser() if custom else DEFAULT_PROFILE_DIR


def _has_session(profile_dir: Path) -> bool:
    """Heuristic: does this profile already contain Chromium cookies?

    Chromium stores cookies under either `Default/Cookies` (older) or
    `Default/Network/Cookies` (current). Either with non-zero size means
    the user has logged into something on a previous run; we can try
    headless first and fall back to visible if the session is stale.
    """
    candidates = [
        profile_dir / "Default" / "Cookies",
        profile_dir / "Default" / "Network" / "Cookies",
    ]
    return any(p.exists() and p.stat().st_size > 0 for p in candidates)


def fetch_via_playwright(
    url: str = "https://therock-runner-health.com/",
    profile_dir: Optional[Path] = None,
    first_run_timeout: int = 300,    # 5 min — give the user time to sign in
    return_run_timeout: int = 30,    # 30 s — quick headless re-fetch
) -> Optional[str]:
    """Drive a persistent Chromium to fetch the dashboard.

    Returns the rendered HTML on success, or ``None`` if Playwright isn't
    installed, Chromium isn't downloaded, the dashboard isn't reachable,
    or sign-in didn't complete within the timeout.
    """
    if os.environ.get("RUNNER_HEALTH_NO_PLAYWRIGHT") == "1":
        print("[runner_health_playwright] disabled by RUNNER_HEALTH_NO_PLAYWRIGHT=1")
        return None

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
    except ImportError:
        print("[runner_health_playwright] playwright not installed; skipping live fetch.")
        print("  To enable: pip install playwright && python -m playwright install chromium")
        return None

    pdir = (profile_dir or _profile_dir()).expanduser()
    pdir.mkdir(parents=True, exist_ok=True)
    cached = _has_session(pdir)

    env_timeout = os.environ.get("RUNNER_HEALTH_PLAYWRIGHT_TIMEOUT")
    if env_timeout:
        try:
            first_run_timeout = max(int(env_timeout), 30)
        except ValueError:
            print(f"[runner_health_playwright] ignoring invalid "
                  f"RUNNER_HEALTH_PLAYWRIGHT_TIMEOUT={env_timeout!r}")

    def _attempt(headless: bool, timeout_sec: int,
                 short_circuit_on_login: bool) -> Optional[str]:
        """Run one Chromium session and return the page HTML (or None).

        ``short_circuit_on_login`` controls how impatient we are:
          * True  (return-run / headless): if the page settles on the GitHub
            sign-in screen, give up immediately so the caller can retry
            visibly. Don't sit at the login page for 5 minutes.
          * False (first-run / visible): only return when the dashboard's
            "Last refresh" marker appears. We need the user to complete the
            OAuth flow in the visible window, which can take 30-60s of
            clicking. Time out only on the full ``first_run_timeout``.
        """
        try:
            pw_ctx = sync_playwright().start()
        except Exception as e:
            print(f"[runner_health_playwright] playwright failed to start: {e}")
            return None
        ctx = None
        try:
            try:
                ctx = pw_ctx.chromium.launch_persistent_context(
                    user_data_dir=str(pdir),
                    headless=headless,
                    viewport={"width": 1280, "height": 1000},
                )
            except Exception as e:
                msg = str(e)
                if "Executable doesn't exist" in msg or "playwright install" in msg.lower():
                    print("[runner_health_playwright] Chromium binary missing. Run:")
                    print("    python -m playwright install chromium")
                    return None
                print(f"[runner_health_playwright] launch failed: {e}")
                return None

            page = ctx.new_page()
            try:
                page.goto(url, timeout=timeout_sec * 1000, wait_until="domcontentloaded")
            except PWTimeoutError:
                print("[runner_health_playwright] page.goto timed out — continuing anyway")
            except Exception as e:
                print(f"[runner_health_playwright] page.goto failed: {e}")
                return None

            # Two wait strategies depending on context:
            #   * First-run (visible): only success marker. The user is
            #     expected to drive the OAuth flow; we wait up to
            #     `first_run_timeout` seconds for the dashboard to render.
            #   * Return-run (headless): success OR login marker — if we
            #     land on the login page, return fast so caller can retry
            #     visibly.
            if short_circuit_on_login:
                wait_js = (
                    "() => document.body && ("
                    "  document.body.innerText.includes('" + DASHBOARD_MARKER + "')"
                    " || document.title.toLowerCase().includes('" + LOGIN_MARKER + "')"
                    ")"
                )
            else:
                wait_js = (
                    "() => document.body && "
                    "document.body.innerText.includes('" + DASHBOARD_MARKER + "')"
                )
                print(f"[runner_health_playwright] Waiting up to {timeout_sec}s for "
                      f"you to complete sign-in in the browser window...")
            try:
                page.wait_for_function(wait_js, timeout=timeout_sec * 1000)
            except PWTimeoutError:
                if not short_circuit_on_login:
                    print("[runner_health_playwright] Timed out waiting for sign-in. "
                          "If you need more time, set RUNNER_HEALTH_PLAYWRIGHT_TIMEOUT "
                          "to a higher number of seconds.")

            try:
                return page.content()
            except Exception as e:
                print(f"[runner_health_playwright] page.content() failed: {e}")
                return None
        finally:
            try:
                if ctx is not None:
                    ctx.close()
            finally:
                try:
                    pw_ctx.stop()
                except Exception:
                    pass

    if not cached:
        print("[runner_health_playwright] First run: opening Chromium for "
              "GitHub OAuth sign-in. Complete the sign-in in the browser "
              "window; the script will continue automatically.")
        print(f"[runner_health_playwright] Profile directory: {pdir}")
        html = _attempt(headless=False, timeout_sec=first_run_timeout,
                        short_circuit_on_login=False)
    else:
        print(f"[runner_health_playwright] Reusing cached session (profile: {pdir})")
        html = _attempt(headless=True, timeout_sec=return_run_timeout,
                        short_circuit_on_login=True)
        if html and DASHBOARD_MARKER not in html:
            print("[runner_health_playwright] Cached session expired — "
                  "re-running with visible browser for re-login.")
            html = _attempt(headless=False, timeout_sec=first_run_timeout,
                            short_circuit_on_login=False)

    if not html:
        return None
    if DASHBOARD_MARKER not in html:
        print("[runner_health_playwright] Did not see dashboard content — "
              "sign-in may be incomplete or the page layout changed.")
        return None
    print(f"[runner_health_playwright] dashboard fetched OK ({len(html)} bytes)")
    return html


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"Profile dir: {_profile_dir()}")
    print(f"Has session: {_has_session(_profile_dir())}")
    html = fetch_via_playwright()
    if html:
        print(f"OK — got {len(html)} bytes; '{DASHBOARD_MARKER}' present: "
              f"{DASHBOARD_MARKER in html}")
    else:
        print("Live fetch did not return usable HTML.")
