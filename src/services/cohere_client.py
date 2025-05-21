# src/services/cohere_client.py
import cohere

class CohereClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = cohere.ClientV2(api_key=api_key)
    
    def test_connection(self) -> bool:
        try:
            response = self.client.chat(
                model="command-r7b-12-2024",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            return True
        except Exception:
            return False
    
    def chat(self, message: str) -> str:
        try:
            response = self.client.chat(
                model="command-r7b-12-2024",
                messages=[{"role": "user", "content": message}]
            )
            
            # Extract text from response
            if hasattr(response, 'message') and hasattr(response.message, 'content'):
                for content in response.message.content:
                    if hasattr(content, 'text'):
                        return content.text
            
            return "No response received"
            
        except Exception as e:
            raise RuntimeError(f"Chat failed: {str(e)}")