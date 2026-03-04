import json, os, re
from typing import Any, Dict, List
from quality_engineering_agentic_framework.agents.agent_interface import AgentInterface

PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "templates", "invest_assessor_prompt.txt"
)

class InvestAssessorAgent(AgentInterface):
    async def process(self, input_data: Any) -> List[Dict]:
        requirements = input_data if isinstance(input_data, str) else "\n".join(input_data)
        with open(PROMPT_PATH, "r") as f:
            prompt = f.read().replace("{requirements}", requirements)

        schema = {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "requirement": {"type": "string"},
                            "invest_scores": {
                                "type": "object",
                                "properties": {k: {"type": "boolean"} for k in
                                               ["Independent","Negotiable","Valuable","Estimable","Small","Testable"]}
                            },
                            "verdict": {"type": "string", "enum": ["pass", "fail"]},
                            "reasons": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["requirement", "invest_scores", "verdict", "reasons"]
                    }
                }
            },
            "required": ["results"]
        }

        try:
            response = await self.llm.generate_with_json_output(
                prompt=prompt,
                json_schema=schema,
                system_message="You are an expert Agile requirements assessor. Return only valid JSON."
            )
            if isinstance(response, dict) and "results" in response:
                return response["results"]
            if isinstance(response, list):
                return response
        except Exception:
            pass

        # fallback: raw text parse
        raw = await self.llm.generate(prompt)
        match = re.search(r'"results"\s*:\s*(\[.*?\])', raw, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        return json.loads(match.group()) if match else []
