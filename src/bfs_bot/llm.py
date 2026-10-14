from __future__ import annotations

from typing import Protocol

from bfs_bot.repositories import PolicyChunk


class LLMClient(Protocol):
    def generate(self, prompt: str) -> str:
        ...


class RecordingLLMClient:
    """Deterministic local client for tests and offline demos.

    Generates variable responses based on the prompt content, so that
    querying different customer IDs returns different information.
    """

    def __init__(self) -> None:
        self.last_request: str | None = None

    def _extract_customer_id_from_prompt(self, prompt: str) -> str | None:
        """Extract SME-XXXXX customer ID from a prompt string."""
        import re
        match = re.search(r"\bSME-\d{5}\b", prompt, re.I)
        return match.group(0).upper() if match else None

    def _build_response(
        self,
        customer_id: str | None,
        redacted_context: dict | None,
        has_policy: bool,
    ) -> str:
        """Build a variable response based on customer and policy context."""
        if customer_id:
            # Build response based on available customer data
            lines: list[str] = []
            if redacted_context:
                for key, value in sorted(redacted_context.items()):
                    lines.append(f"{key}: {value}")
            else:
                lines.append(f"Customer ID: {customer_id}")

            credit_info = ""
            if "credit_limit" in (redacted_context or {}):
                credit_info = f" has an available credit limit."
            elif "available_limit" in (redacted_context or {}):
                credit_info = f" has an available limit."

            base = f"{customer_id}{credit_info} "
            if lines:
                base += ". ".join(lines[0].split(". ", 1)[1:]) if "." in lines[0] else lines[0][:20]
            return base + " Based on the retrieved policy context, customer data should be used only for stated service, compliance, risk, communication, and support purposes."

        if has_policy:
            return (
                "Based on the retrieved policy context and the question asked, "
                "the answer can be derived from the policy excerpts provided. "
                "No specific customer record was needed for this query."
            )
        return (
            "I don't have enough information to answer this question. "
            "Please provide a query that includes a customer ID (e.g., SME-10023) "
            "or ask a policy-related question."
        )

    def generate(self, prompt: str) -> str:
        self.last_request = prompt

        customer_id = self._extract_customer_id_from_prompt(prompt)

        # Check if the prompt contains redacted customer context lines
        has_customer_context = (
            "customer_id:" in prompt.lower()
            or "business_name:" in prompt.lower()
            or "available limit" in prompt.lower()
            or "credit limit" in prompt.lower()
        )

        # Check if policy chunks are referenced
        has_policy = "policy" in prompt.lower() or "excerpt" in prompt.lower()

        # Try to extract redacted context info from prompt
        redacted_context: dict | None = None
        if has_customer_context:
            # Parse simple key:value lines from the prompt
            lines: list[tuple[str, str]] = []
            for line in prompt.split("\n"):
                line = line.strip()
                if ":" in line and not line.startswith("You are") and not line.startswith("Use only") and not line.startswith("Do not") and not line.startswith("Question:") and not line.startswith("Redacted customer facts:") and not line.startswith("Policy excerpts:"):
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        if key and value:
                            lines.append((key, value))
            if lines:
                redacted_context = dict(lines)

        return self._build_response(customer_id, redacted_context, has_policy)


def build_prompt(
    question: str,
    redacted_customer_context: dict | None,
    policy_chunks: list[PolicyChunk],
) -> str:
    customer_lines = ["No customer record was needed."]
    if redacted_customer_context:
        customer_lines = [
            f"{key}: {value}" for key, value in sorted(redacted_customer_context.items())
        ]

    policy_lines = [
        f"[{chunk.chunk_id}] {chunk.title} / {chunk.section}: {chunk.text}"
        for chunk in policy_chunks
    ]
    return "\n".join(
        [
            "You are an SME credit support assistant.",
            "Use only the redacted customer facts and policy excerpts below.",
            "Do not reveal or infer raw PII.",
            f"Question: {question}",
            "Redacted customer facts:",
            *customer_lines,
            "Policy excerpts:",
            *(policy_lines or ["No policy excerpts were retrieved."]),
        ]
    )

