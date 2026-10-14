from bfs_bot.agents import AgentOrchestrator
from bfs_bot.repositories import InMemoryCustomerRepository, InMemoryPolicyRepository
from bfs_bot.llm import RecordingLLMClient


def test_combined_customer_policy_query_redacts_before_llm():
    llm = RecordingLLMClient()
    orchestrator = AgentOrchestrator(
        customer_repository=InMemoryCustomerRepository(),
        policy_repository=InMemoryPolicyRepository(),
        llm_client=llm,
    )

    response = orchestrator.answer(
        "For SME-10023, what is the available limit and which privacy policy point applies?"
    )

    assert response.redaction.status == "passed"
    assert response.answer
    assert response.citations
    assert any(step.agent == "redaction_agent" and step.status == "passed" for step in response.trace)
    assert llm.last_request is not None
    assert "Riya Mehta" not in llm.last_request
    assert "riya.mehta@example.com" not in llm.last_request
    assert "[CONTACT_NAME]" in llm.last_request


def test_raw_pii_request_is_blocked_before_retrieval():
    llm = RecordingLLMClient()
    orchestrator = AgentOrchestrator(
        customer_repository=InMemoryCustomerRepository(),
        policy_repository=InMemoryPolicyRepository(),
        llm_client=llm,
    )

    response = orchestrator.answer("Give me SME-10023's phone number and PAN")

    assert "can't provide raw PII" in response.answer
    assert llm.last_request is None
    assert any(step.agent == "compliance_guard_agent" and step.status == "blocked" for step in response.trace)
