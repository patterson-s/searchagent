#!/usr/bin/env python3

import cohere
import json
import requests

def perform_web_search(query: str) -> str:
    """Simple web search using a basic search API or mock results"""
    try:
        # For testing, we'll use a simple mock search result
        # In production, you'd use a real search API like Google Custom Search, Bing, etc.
        mock_results = f"""
        Search results for "{query}":
        1. "OpenAI Releases New GPT Model" - TechCrunch - Latest developments in AI technology
        2. "Google's Gemini AI Update" - The Verge - New features and capabilities announced
        3. "Meta's AI Research Breakthrough" - Reuters - Significant progress in machine learning
        """
        return mock_results
    except Exception as e:
        return f"Search failed: {str(e)}"

def test_web_search():
    api_key = input("Enter your Cohere API key: ").strip()
    
    if not api_key:
        print("No API key provided. Exiting.")
        return
    
    co = cohere.ClientV2(api_key=api_key)
    
    web_search_tool = {
        "type": "function",
        "function": {
            "name": "web-search",
            "description": "Run a live internet search and return links.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string", 
                        "description": "Search query"
                    }
                },
                "required": ["query"]
            }
        }
    }
    
    test_prompt = "What are the latest AI news headlines today?"
    
    print(f"Testing web search with prompt: '{test_prompt}'")
    print("=" * 60)
    
    try:
        # Step 1: Initial request with tools
        response = co.chat(
            model="command-r7b-12-2024",
            messages=[{"role": "user", "content": test_prompt}],
            tools=[web_search_tool],
            tool_choice="required"
        )
        
        print("STEP 1: Tool call made")
        print("=" * 40)
        print("Tool call details:")
        for tool_call in response.message.tool_calls:
            print(f"Tool: {tool_call.function.name}")
            args = json.loads(tool_call.function.arguments)
            print(f"Query: {args['query']}")
        
        # Step 2: Execute the tool call and send results back
        tool_results = []
        for tool_call in response.message.tool_calls:
            if tool_call.function.name == "web-search":
                args = json.loads(tool_call.function.arguments)
                search_results = perform_web_search(args["query"])
                
                tool_results.append({
                    "call": tool_call,
                    "outputs": [{"result": search_results}]
                })
        
        # Step 3: Send tool results back to get final response
        messages = [
            {"role": "user", "content": test_prompt},
            {"role": "assistant", "tool_calls": response.message.tool_calls},
            {"role": "tool", "tool_call_id": tool_results[0]["call"].id, "content": tool_results[0]["outputs"][0]["result"]}
        ]
        
        final_response = co.chat(
            model="command-r7b-12-2024",
            messages=messages
        )
        
        print("\nSTEP 2: Final response with search results")
        print("=" * 40)
        print("FINAL RESPONSE:")
        print(final_response.message.content[0].text if final_response.message.content else "No content")
        
        print("\n" + "=" * 60)
        print("FULL RAW FINAL RESPONSE:")
        print("=" * 60)
        final_response_dict = final_response.model_dump() if hasattr(final_response, 'model_dump') else vars(final_response)
        print(json.dumps(final_response_dict, indent=2, default=str))
        
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {str(e)}")
        print("=" * 60)
        print("This could mean:")
        print("1. Your API key doesn't support tool use")
        print("2. The r7b model doesn't support web search tools")
        print("3. Web search is not enabled for your account")
        print("4. API connection issue")
        print("5. Tool response format issue")

if __name__ == "__main__":
    test_web_search()