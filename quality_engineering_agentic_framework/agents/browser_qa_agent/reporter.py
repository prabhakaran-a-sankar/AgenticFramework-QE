import json
from datetime import datetime
from jinja2 import Template
from .planner import PlannerResult
from .storage import ArtifactStorage

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>QA Report - {{ run_id }}</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 960px; margin: 40px auto; padding: 0 20px; }
    h1 { color: #1a1a1a; }
    .badge { display: inline-block; padding: 4px 12px; border-radius: 4px; font-weight: bold; color: white; }
    .passed { background: #22c55e; }
    .failed { background: #ef4444; }
    .error { background: #f97316; }
    .finding { border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin: 12px 0; }
    .critical { border-left: 4px solid #7f1d1d; }
    .high { border-left: 4px solid #ef4444; }
    .medium { border-left: 4px solid #f97316; }
    .low { border-left: 4px solid #eab308; }
    .info { border-left: 4px solid #3b82f6; }
    .screenshot { max-width: 100%; border: 1px solid #e5e7eb; border-radius: 4px; margin-top: 8px; }
    .step-img { max-width: 280px; border-radius: 4px; border: 1px solid #ddd; }
    .steps { display: flex; flex-wrap: wrap; gap: 12px; }
    .step { text-align: center; font-size: 12px; }
  </style>
</head>
<body>
  <h1>QA Test Report</h1>
  <p><strong>Run ID:</strong> {{ run_id }}</p>
  <p><strong>Generated:</strong> {{ generated_at }}</p>
  <p><strong>Status:</strong> <span class="badge {{ status }}">{{ status.upper() }}</span></p>
  <p><strong>Summary:</strong> {{ summary }}</p>
  <p><strong>Bugs found:</strong> {{ findings|length }}</p>

  {% if findings %}
  <h2>Findings</h2>
  {% for f in findings %}
  <div class="finding {{ f.severity }}">
    <strong>[{{ f.severity|upper }}] {{ f.title }}</strong>
    <p>{{ f.description }}</p>
    <p><em>Expected:</em> {{ f.expected }}</p>
    <p><em>Actual:</em> {{ f.actual }}</p>
    {% if f.screenshot_url %}
    <img class="screenshot" src="{{ f.screenshot_url }}" alt="Evidence screenshot">
    {% endif %}
  </div>
  {% endfor %}
  {% endif %}

  <h2>Steps ({{ traces|length }})</h2>
  <div class="steps">
  {% for t in traces %}
  <div class="step">
    <div>{{ t.step }}. {{ t.action }}</div>
    {% if t.screenshot_url %}
    <img class="step-img" src="{{ t.screenshot_url }}" alt="Step {{ t.step }}">
    {% endif %}
  </div>
  {% endfor %}
  </div>

  {% if video_url %}
  <h2>Recording</h2>
  <p><a href="{{ video_url }}">Download video</a></p>
  {% endif %}
</body>
</html>
"""


class Reporter:
    def __init__(self, storage: ArtifactStorage):
        self.storage = storage

    async def generate(self, run_id: str, result: PlannerResult) -> dict:
        now = datetime.utcnow().isoformat()

        # Upload video
        video_url = ""
        if result.video_path:
            try:
                video_url = await self.storage.upload_file(
                    f"runs/{run_id}/video.webm",
                    result.video_path,
                    "video/webm",
                )
            except Exception:
                pass

        traces_data = [
            {
                "step": t.step,
                "action": t.action,
                "action_input": t.action_input,
                "screenshot_url": t.screenshot_url,
                "url": t.url,
            }
            for t in result.traces
        ]

        # JSON report
        json_report = {
            "run_id": run_id,
            "generated_at": now,
            "status": result.status,
            "summary": result.summary,
            "bugs_found": len(result.findings),
            "findings": result.findings,
            "steps": traces_data,
            "video_url": video_url,
        }
        json_bytes = json.dumps(json_report, indent=2).encode()
        json_url = await self.storage.upload(
            f"runs/{run_id}/report.json", json_bytes, "application/json"
        )

        # HTML report
        template = Template(HTML_TEMPLATE)
        html = template.render(
            run_id=run_id,
            generated_at=now,
            status=result.status,
            summary=result.summary,
            findings=result.findings,
            traces=result.traces,
            video_url=video_url,
        )
        html_url = await self.storage.upload(
            f"runs/{run_id}/report.html", html.encode(), "text/html"
        )

        return {
            "findings": result.findings,
            "artifact_urls": {"json": json_url, "html": html_url},
            "html_report_url": html_url,
            "video_url": video_url,
            "summary": result.summary,
            "bugs_found": len(result.findings),
        }
