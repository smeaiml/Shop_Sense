
from capstone.rag.answer import answer_from_evidence
from capstone.rag.chunking import chunk_documents
from capstone.rag.ingestion import load_documents


def test_electronics_answer_has_relevant_citation():
    chunks = chunk_documents(load_documents())

    result = answer_from_evidence(
        "What is the return window and restocking fee for opened Electronics items?",
        chunks,
    )

    assert result["status"] == "evidence_found"
    assert any(
        citation["title"] == "Category Policy Addendum: Electronics"
        for citation in result["citations"]
    )


def test_citations_are_unique():
    chunks = chunk_documents(load_documents())

    result = answer_from_evidence(
        "What is the return window and restocking fee for opened Electronics items?",
        chunks,
    )

    source_keys = [
        (citation["title"], citation["source"])
        for citation in result["citations"]
    ]

    assert len(source_keys) == len(set(source_keys))


def test_empty_query_abstains():
    chunks = chunk_documents(load_documents())

    result = answer_from_evidence("", chunks)

    assert result["status"] == "insufficient_evidence"
    assert result["citations"] == []

def test_combined_electronics_question_answers_both_facts():
    chunks = chunk_documents(load_documents())

    result = answer_from_evidence(
        "What is the return window and restocking fee for opened Electronics items?",
        chunks,
    )

    assert result["status"] == "evidence_found"
    assert "15 days" in result["answer"]
    assert "15%" in result["answer"]
    assert any(
        citation["source"] == "category-electronics.md"
        for citation in result["citations"]
    )


def test_explicit_category_query_excludes_other_category_addenda():
    from capstone.rag.retrieval import retrieve

    chunks = chunk_documents(load_documents())
    results = retrieve(
        "What is the return policy for Home & Kitchen items?",
        chunks,
        top_k=8,
    )
    category_titles = {
        item["title"] for item in results
        if item["title"].startswith("Category Policy Addendum:")
    }
    assert "Category Policy Addendum: Home & Kitchen" in category_titles
    assert category_titles == {"Category Policy Addendum: Home & Kitchen"}
