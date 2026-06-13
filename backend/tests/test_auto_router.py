from unittest.mock import patch, MagicMock
from app.graph.auto_router import route_query

@patch("app.graph.auto_router.fast_llm")
def test_auto_router_chat_keyword_bypass(mock_fast_llm):
    """Test that general conversational greetings are classified as 'chat' by the LLM."""
    state = {"query": "hello"}
    
    mock_chain = MagicMock()
    class MockOutput:
        intent = "chat"
    mock_chain.invoke.return_value = MockOutput()
    
    mock_fast_llm.with_structured_output.return_value = mock_chain
    result = route_query(state)
        
    assert result == "chat"
    mock_chain.invoke.assert_called_once()

@patch("app.graph.auto_router.fast_llm")
def test_auto_router_document_keyword_bypass(mock_fast_llm):
    """Test that explicit UI references (e.g. 'this tab') instantly route to 'fast'."""
    state = {"query": "summarize this tab for me"}
    
    mock_fast_llm.with_structured_output.side_effect = Exception("LLM should not be called!")
    result = route_query(state)
        
    assert result == "fast"

@patch("app.graph.auto_router.fast_llm")
def test_auto_router_llm_classification(mock_fast_llm):
    """Test that the LLM correctly handles generic ambiguous queries."""
    state = {"query": "What is the capital of France?"}
    
    mock_chain = MagicMock()
    class MockOutput:
        intent = "fast"
    mock_chain.invoke.return_value = MockOutput()
    
    mock_fast_llm.with_structured_output.return_value = mock_chain
    result = route_query(state)
        
    assert result == "fast"
    mock_chain.invoke.assert_called_once()
