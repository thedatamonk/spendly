import json

from loguru import logger
from openai import OpenAI

from app.llm.prompts import SYSTEM_PROMPT
from app.models.schemas import LLMResponse, Obligation


class IntentParser:
    def __init__(self, api_key: str, model: str):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        self.model = model

    def parse(
        self,
        user_message: str,
        context: list[Obligation] | None = None,
        history: list[dict] | None = None,
    ) -> LLMResponse:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        if context:
            context_text = "Active obligations:\n"
            for ob in context:
                context_text += (
                    f"- {ob.person_name}: ₹{ob.remaining_amount} remaining "
                    f"({ob.type}, total ₹{ob.total_amount})"
                )
                if ob.note:
                    context_text += f" — {ob.note}"
                context_text += "\n"
            messages.append({"role": "system", "content": context_text})

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_message})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
            )

            raw = response.choices[0].message.content.strip()
            logger.debug("LLM raw response: {}", raw)

            # Strip markdown code fences if present
            if raw.startswith("```"):
                lines = raw.split("\n")
                lines = [l for l in lines if not l.startswith("```")]
                raw = "\n".join(lines)

            parsed_json = json.loads(raw)
            return LLMResponse.model_validate(parsed_json)

        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON: {}", e)
            return LLMResponse(
                parsed=None,
                confirmation_message="I couldn't understand that. Could you rephrase?",
                requires_confirmation=False,
            )
        except Exception as e:
            logger.error("LLM request failed: {}", e)
            return LLMResponse(
                parsed=None,
                confirmation_message="Something went wrong. Please try again.",
                requires_confirmation=False,
            )
