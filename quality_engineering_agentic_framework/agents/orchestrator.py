import re
from typing import Any, Dict, List, Optional
import httpx
from httpx import BasicAuth
from quality_engineering_agentic_framework.agents.agent_interface import AgentInterface
from quality_engineering_agentic_framework.agents.invest_assessor import InvestAssessorAgent
from quality_engineering_agentic_framework.agents.requirement_interpreter import TestCaseGenerationAgent

JIRA_ID_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]+-\d+$', re.IGNORECASE)


class OrchestratorAgent(AgentInterface):
    def __init__(self, llm, config):
        super().__init__(llm, config)
        self.state = "IDLE"
        self.objective = ""
        self.requirements = ""
        self.assessment_results: List[Dict] = []
        self.passing: List[Dict] = []
        self.failing: List[Dict] = []
        self.jira_config: Optional[Dict[str, str]] = None

    async def process(self, input_data: Any) -> Any:
        return await self.step(input_data)

    async def step(self, user_message: str, jira_config: Optional[Dict[str, str]] = None) -> Dict:
        if jira_config:
            self.jira_config = jira_config
        msg = user_message.strip()

        if self.state == "IDLE":
            self.objective = msg
            self.state = "AWAITING_REQUIREMENTS"
            return {
                "state": self.state,
                "reply": (f"Great objective! To help you achieve **\"{self.objective}\"**, "
                          "please share your requirements — one per line or as a numbered list."),
                "test_cases": [], "assessment": []
            }

        if self.state == "AWAITING_REQUIREMENTS":
            # Check if input looks like one or more Jira story IDs
            tokens = [t.strip() for t in msg.replace(',', ' ').split() if t.strip()]
            if tokens and all(JIRA_ID_PATTERN.match(t) for t in tokens):
                if not self.jira_config:
                    return {
                        "state": self.state,
                        "reply": "⚠️ Jira story IDs detected but no Jira configuration provided. Please fill in the Jira Configuration panel.",
                        "test_cases": [], "assessment": []
                    }
                fetched = await self._fetch_jira_stories(tokens)
                if not fetched["stories"]:
                    errors = ", ".join(f"{k}: {v}" for k, v in fetched["errors"].items())
                    return {
                        "state": self.state,
                        "reply": f"⚠️ Could not fetch Jira stories: {errors}",
                        "test_cases": [], "assessment": []
                    }
                lines = []
                for s in fetched["stories"]:
                    lines.append(f"Title: {s['summary']}")
                    if s.get("description"):
                        lines.append(f"Description: {s['description']}")
                    if s.get("acceptance_criteria"):
                        lines.append(f"Acceptance Criteria: {s['acceptance_criteria']}")
                msg = "\n".join(lines)
                story_ids = ", ".join(s["id"] for s in fetched["stories"])
                jira_notice = f"📋 Fetched {len(fetched['stories'])} Jira story/stories ({story_ids}). Proceeding with INVEST assessment...\n\n"
            else:
                jira_notice = ""
            self.requirements = msg
            self.state = "ASSESSING"
            try:
                assessor = InvestAssessorAgent(self.llm, {})
                self.assessment_results = await assessor.process(self.requirements)
            except Exception as e:
                self.state = "AWAITING_REQUIREMENTS"
                return {
                    "state": self.state,
                    "reply": f"⚠️ INVEST assessment failed: {e}. Please try again.",
                    "test_cases": [], "assessment": []
                }
            self.passing = [r for r in self.assessment_results if r.get("verdict") == "pass"]
            self.failing = [r for r in self.assessment_results if r.get("verdict") == "fail"]

            if not self.failing:
                return await self._generate(self.requirements, "all")

            self.state = "ASSESSMENT_FAILED"
            fail_lines = "\n".join(
                f"❌ **{r['requirement'][:80]}**\n   " + " | ".join(r.get("reasons", []))
                for r in self.failing
            )
            pass_line = f"\n\n✅ {len(self.passing)} requirement(s) passed." if self.passing else ""
            return {
                "state": self.state,
                "reply": (
                    f"{jira_notice}**INVEST Assessment Results:**\n\n{fail_lines}{pass_line}\n\n"
                    f"{len(self.failing)} requirement(s) need attention. How would you like to proceed?\n\n"
                    f"**A)** Revise and re-submit the failing requirements\n"
                    f"**B)** Proceed with only the {len(self.passing)} passing requirement(s)\n"
                    f"**C)** Proceed with all requirements anyway"
                ),
                "assessment": self.assessment_results, "test_cases": []
            }

        if self.state == "ASSESSMENT_FAILED":
            choice = msg.upper()
            if choice == "A":
                self.state = "AWAITING_REQUIREMENTS"
                return {"state": self.state, "reply": "Please provide your revised requirements.",
                        "test_cases": [], "assessment": []}
            if choice == "B":
                reqs = "\n".join(r["requirement"] for r in self.passing)
                return await self._generate(reqs, "passing")
            if choice == "C":
                return await self._generate(self.requirements, "all")
            return {"state": self.state, "reply": "Please reply with **A**, **B**, or **C**.",
                    "test_cases": [], "assessment": self.assessment_results}

        if self.state == "DONE":
            # reset for new conversation
            self.__init__(self.llm, self.config)
            return await self.step(user_message)

        return {"state": self.state, "reply": "Unexpected state. Please reset and start again.",
                "test_cases": [], "assessment": []}

    async def _fetch_jira_stories(self, story_ids: List[str]) -> Dict:
        cfg = self.jira_config
        base = cfg["jira_url"].rstrip("/")
        auth = BasicAuth(cfg["email"], cfg["pat"])
        stories, errors = [], {}
        async with httpx.AsyncClient(verify=False, auth=auth) as client:
            for sid in story_ids:
                try:
                    r = await client.get(f"{base}/rest/api/3/issue/{sid}", timeout=15)
                    if r.status_code == 404:
                        r = await client.get(f"{base}/rest/api/2/issue/{sid}", timeout=15)
                    r.raise_for_status()
                    fields = r.json().get("fields", {})
                    desc = fields.get("description") or ""
                    if isinstance(desc, dict):
                        desc = " ".join(
                            c.get("text", "") for block in desc.get("content", [])
                            for c in block.get("content", []) if c.get("type") == "text"
                        )
                    ac = fields.get("customfield_10016") or fields.get("customfield_10014") or ""
                    stories.append({"id": sid, "summary": fields.get("summary", ""), "description": desc, "acceptance_criteria": str(ac) if ac else ""})
                except Exception as e:
                    errors[sid] = str(e)
        return {"stories": stories, "errors": errors}

    async def _generate(self, requirements: str, label: str) -> Dict:
        self.state = "GENERATING"
        try:
            agent = TestCaseGenerationAgent(self.llm, {})
            result = await agent.process(requirements)
            test_cases = result.get("test_cases", [])
            self.state = "DONE"
            return {
                "state": self.state,
                "reply": f"✅ Generated **{len(test_cases)} test cases** from the {label} requirements.",
                "assessment": self.assessment_results,
                "test_cases": test_cases
            }
        except Exception as e:
            self.state = "ASSESSMENT_FAILED" if self.assessment_results else "AWAITING_REQUIREMENTS"
            return {
                "state": self.state,
                "reply": (
                    f"⚠️ Test case generation failed: {e}\n\n"
                    "Would you like to try again?\n"
                    "**A)** Re-submit requirements\n"
                    "**C)** Retry generation with all requirements"
                ),
                "assessment": self.assessment_results,
                "test_cases": []
            }
