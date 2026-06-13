from unittest.mock import patch, MagicMock
from langchain_core.documents import Document
from app.graph.nodes.crag_evaluator import eval_docs
from app.graph.nodes.hallucination_grader import check_hallucination
from app.graph.nodes.answer_grader import check_usefulness

class MockCRAGOutput:
    def __init__(self, scores):
        self.scores = scores

class MockBinaryOutput:
    def __init__(self, score, reason="Mock reason"):
        self.score = score
        self.reason = reason

@patch("app.graph.nodes.crag_evaluator.fast_llm")
def test_crag_evaluator_all_correct(mock_fast_llm):
    """Test CRAG evaluator when LLM gives high scores."""
    state = {
        "query": "What is the capital of France?",
        "docs": [
            Document(page_content="Paris is the capital of France.", metadata={"source": "doc1"}),
            Document(page_content="France is a country.", metadata={"source": "doc1"})
        ]
    }
    
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = MockCRAGOutput(scores=[1.0, 1.0])
    mock_fast_llm.with_structured_output.return_value = mock_chain
    
    result = eval_docs(state)
        
    assert result["crag_verdict"] == "CORRECT"
    assert len(result["good_docs"]) == 2

@patch("app.graph.nodes.crag_evaluator.fast_llm")
def test_crag_evaluator_incorrect(mock_fast_llm):
    """Test CRAG evaluator when LLM gives very low scores."""
    state = {
        "query": "What is the capital of France?",
        "docs": [
            Document(page_content="The sky is blue.", metadata={"source": "doc1"})
        ]
    }
    
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = MockCRAGOutput(scores=[0.0])
    mock_fast_llm.with_structured_output.return_value = mock_chain
    
    result = eval_docs(state)
        
    assert result["crag_verdict"] == "INCORRECT"
    assert len(result["good_docs"]) == 0

@patch("app.graph.nodes.hallucination_grader.hallucination_checker")
def test_hallucination_grader_success(mock_checker):
    """Test hallucination grader allows grounded answers to pass."""
    state = {
        "refined_context": "The capital is Paris.",
        "draft_answer": "Paris is the capital."
    }
    
    mock_checker.invoke.return_value = MockBinaryOutput(score="yes")
    
    result = check_hallucination(state)
        
    assert result["is_supported"] is True

@patch("app.graph.nodes.answer_grader.usefulness_checker")
def test_answer_grader_success(mock_checker):
    """Test answer grader stops the pipeline when the answer is useful."""
    state = {
        "query": "What is the capital?",
        "draft_answer": "Paris is the capital."
    }
    
    mock_checker.invoke.return_value = MockBinaryOutput(score="yes")
    
    result = check_usefulness(state)
        
    assert result["is_useful"] is True
    assert result["final_answer"] == "Paris is the capital."
