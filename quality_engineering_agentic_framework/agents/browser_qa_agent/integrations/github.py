import hashlib
import hmac
import time
import httpx
import jwt as pyjwt
from ..config import get_settings


class GitHubIntegration:
    """
    GitHub App integration for posting Check Runs on pull requests.
    Requires a GitHub App with `checks:write` permission installed on the repo.
    """

    API_BASE = "https://api.github.com"

    def __init__(self):
        settings = get_settings()
        self.app_id = settings.github_app_id
        self.private_key = settings.github_private_key
        self.webhook_secret = settings.github_webhook_secret

    def verify_webhook_signature(self, payload_bytes: bytes, signature_header: str) -> bool:
        if not self.webhook_secret:
            return True
        expected = "sha256=" + hmac.new(
            self.webhook_secret.encode(), payload_bytes, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header or "")

    def _make_jwt(self) -> str:
        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + 540, "iss": self.app_id}
        return pyjwt.encode(payload, self.private_key, algorithm="RS256")

    async def _get_installation_token(self, installation_id: int) -> str:
        jwt_token = self._make_jwt()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.API_BASE}/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            resp.raise_for_status()
            return resp.json()["token"]

    async def create_check_run(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        head_sha: str,
        name: str = "QA Agent",
    ) -> int:
        token = await self._get_installation_token(installation_id)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.API_BASE}/repos/{owner}/{repo}/check-runs",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                json={
                    "name": name,
                    "head_sha": head_sha,
                    "status": "in_progress",
                },
            )
            resp.raise_for_status()
            return resp.json()["id"]

    async def update_check_run(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        check_run_id: int,
        status: str,  # passed | failed
        bugs_found: int,
        report_url: str,
    ):
        token = await self._get_installation_token(installation_id)
        conclusion = "success" if status == "passed" else "failure"
        summary = f"QA Agent found **{bugs_found}** bug(s). [View report]({report_url})"

        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"{self.API_BASE}/repos/{owner}/{repo}/check-runs/{check_run_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                json={
                    "status": "completed",
                    "conclusion": conclusion,
                    "output": {
                        "title": f"QA: {bugs_found} bug(s) found",
                        "summary": summary,
                    },
                },
            )
            resp.raise_for_status()
