"""
Web search and fetch tool
"""
import requests
import json
from typing import ClassVar, Literal, Optional
from urllib.parse import quote
from anthropic.types.beta import BetaToolUnionParam

from .base import BaseAnthropicTool, ToolResult


class WebTool(BaseAnthropicTool):
    """
    A tool for web searches and fetching web content.
    """
    name: ClassVar[Literal["web"]] = "web"
    api_type: ClassVar[Literal["web_20241022"]] = "web_20241022"

    async def __call__(
        self,
        *,
        action: Literal[
            "search",
            "fetch",
            "get_headers",
            "download_file"
        ],
        query: Optional[str] = None,
        url: Optional[str] = None,
        file_path: Optional[str] = None,
        max_results: int = 10,
        timeout: int = 30,
        **kwargs
    ) -> ToolResult:
        """Execute web operations"""
        
        try:
            if action == "search":
                if not query:
                    return ToolResult(error="Query is required for search")
                
                # Use DuckDuckGo Instant Answer API (free, no API key required)
                search_url = f"https://api.duckduckgo.com/?q={quote(query)}&format=json&no_html=1&skip_disambig=1"
                
                try:
                    response = requests.get(search_url, timeout=timeout)
                    response.raise_for_status()
                    data = response.json()
                    
                    results = []
                    
                    # Add abstract if available
                    if data.get('Abstract'):
                        results.append({
                            "type": "abstract",
                            "title": data.get('AbstractText', ''),
                            "url": data.get('AbstractURL', ''),
                            "source": data.get('AbstractSource', '')
                        })
                    
                    # Add related topics
                    for topic in data.get('RelatedTopics', [])[:max_results]:
                        if isinstance(topic, dict) and 'Text' in topic:
                            results.append({
                                "type": "related_topic",
                                "title": topic.get('Text', ''),
                                "url": topic.get('FirstURL', '')
                            })
                    
                    # Add answer if available
                    if data.get('Answer'):
                        results.append({
                            "type": "answer",
                            "title": data.get('Answer', ''),
                            "url": data.get('AnswerURL', ''),
                            "answer_type": data.get('AnswerType', '')
                        })
                    
                    if not results:
                        return ToolResult(output="No search results found")
                    
                    return ToolResult(output=json.dumps(results, indent=2))
                    
                except requests.RequestException as e:
                    return ToolResult(error=f"Search request failed: {str(e)}")
            
            elif action == "fetch":
                if not url:
                    return ToolResult(error="URL is required for fetch")
                
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                    response = requests.get(url, headers=headers, timeout=timeout)
                    response.raise_for_status()
                    
                    content_type = response.headers.get('content-type', '').lower()
                    
                    if 'application/json' in content_type:
                        try:
                            data = response.json()
                            return ToolResult(output=json.dumps(data, indent=2))
                        except json.JSONDecodeError:
                            return ToolResult(output=response.text[:10000])  # Limit to 10KB
                    elif 'text/' in content_type:
                        return ToolResult(output=response.text[:10000])  # Limit to 10KB
                    else:
                        return ToolResult(output=f"Content type: {content_type}, Size: {len(response.content)} bytes")
                    
                except requests.RequestException as e:
                    return ToolResult(error=f"Fetch request failed: {str(e)}")
            
            elif action == "get_headers":
                if not url:
                    return ToolResult(error="URL is required for get_headers")
                
                try:
                    response = requests.head(url, timeout=timeout)
                    response.raise_for_status()
                    
                    headers_info = {
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "url": response.url
                    }
                    
                    return ToolResult(output=json.dumps(headers_info, indent=2))
                    
                except requests.RequestException as e:
                    return ToolResult(error=f"Headers request failed: {str(e)}")
            
            elif action == "download_file":
                if not url or not file_path:
                    return ToolResult(error="Both URL and file_path are required for download_file")
                
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                    response = requests.get(url, headers=headers, timeout=timeout, stream=True)
                    response.raise_for_status()
                    
                    with open(file_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    file_size = len(response.content)
                    return ToolResult(output=f"Downloaded {file_size} bytes to {file_path}")
                    
                except requests.RequestException as e:
                    return ToolResult(error=f"Download failed: {str(e)}")
                except IOError as e:
                    return ToolResult(error=f"File write failed: {str(e)}")
            
            else:
                return ToolResult(error=f"Unknown action: {action}")
                
        except Exception as e:
            return ToolResult(error=f"Web operation failed: {str(e)}")

    def to_params(self) -> BetaToolUnionParam:
        return {
            "type": self.api_type,
            "name": self.name,
        }