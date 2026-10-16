
from capstone.agents.rag_agent import RAGAgent


def test_rag_agent_returns_electronics_policy_citation():
    agent = RAGAgent()

    result = agent.answer(
        "What is the return window for Electronics?"
    )

    assert result["status"] == "evidence_found"
    assert any(
        citation["source"] == "category-electronics.md"
        for citation in result["citations"]
    )


def test_rag_agent_abstains_on_empty_question():
    agent = RAGAgent()

    result = agent.answer("")

    assert result["status"] == "insufficient_evidence"
    assert result["citations"] == []
