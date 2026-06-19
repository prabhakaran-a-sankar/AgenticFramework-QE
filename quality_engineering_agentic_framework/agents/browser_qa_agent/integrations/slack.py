import httpx
from ..config import get_settings


class SlackNotifier:
    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url or get_settings().slack_webhook_url

    async def notify_run_complete(
        self,
        run_id: str,
        test_name: str,
        status: str,
        bugs_found: int,
        report_url: str,
    ):
        if not self.webhook_url:
            return

        emoji = ":white_check_mark:" if status == "passed" else ":x:"
        color = "#22c55e" if status == "passed" else "#ef4444"

        payload = {
            "attachments": [
                {
                    "color": color,
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": (
                                    f"{emoji} *QA Run Complete*\n"
                                    f"*Test:* {test_name}\n"
                                    f"*Status:* {status.upper()}\n"
                                    f"*Bugs found:* {bugs_found}\n"
                                    f"<{report_url}|View Report>"
                                ),
                            },
                        }
                    ],
                }
            ]
        }

        async with httpx.AsyncClient() as client:
            await client.post(self.webhook_url, json=payload, timeout=10)
