import httpx


class OutboundWebhook:
    def __init__(self, url: str):
        self.url = url

    async def send(self, payload: dict):
        if not self.url:
            return
        async with httpx.AsyncClient() as client:
            try:
                await client.post(self.url, json=payload, timeout=15)
            except Exception:
                pass  # Webhook delivery is best-effort

    async def notify_run_complete(self, run_id: str, status: str, bugs_found: int, report_url: str):
        await self.send({
            "event": "run.completed",
            "run_id": run_id,
            "status": status,
            "bugs_found": bugs_found,
            "report_url": report_url,
        })
