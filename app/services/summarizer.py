import boto3
import json
from typing import List, Dict, Any

from app.core.config import settings


class SummarizerService:
    """Service for generating summaries using Amazon Bedrock with Claude."""

    def __init__(self):
        self.bedrock_client = boto3.client(
            'bedrock-runtime',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )

    def create_prompt(self, transcript: str, categories: List[str]) -> str:
        """Create a prompt for the Claude model."""
        categories_list = ", ".join(categories)

        prompt = f"""You are an AI assistant tasked with summarizing podcast episodes and categorizing them.

Given the following podcast transcript, please:
1. Create a concise summary (200-300 words) that captures the main topics, key insights, and important takeaways.
2. Select the most relevant categories from the provided list that best describe the content.

TRANSCRIPT:
{transcript[:10000]}  # Limit transcript length to avoid token limits

AVAILABLE CATEGORIES:
{categories_list}

Please respond with a JSON object in the following format:
{{
    "summary": "Your summary here",
    "categories": ["category1", "category2", "category3"]
}}

Ensure the categories you select are ONLY from the provided list above. Select between 1-5 most relevant categories."""

        return prompt

    async def generate_summary(
        self,
        transcript: str,
        available_categories: List[str]
    ) -> Dict[str, Any]:
        """Generate summary and categorization using Amazon Bedrock."""
        prompt = self.create_prompt(transcript, available_categories)

        # Prepare the request for Claude
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "temperature": 0.3,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        try:
            # Invoke the model
            response = self.bedrock_client.invoke_model(
                modelId=settings.BEDROCK_MODEL_ID,
                body=json.dumps(request_body),
                contentType='application/json'
            )

            # Parse the response
            response_body = json.loads(response['body'].read())

            # Extract the text from Claude's response
            assistant_response = response_body.get('content', [{}])[0].get('text', '{}')

            # Parse the JSON response
            try:
                result = json.loads(assistant_response)
            except json.JSONDecodeError:
                # If JSON parsing fails, extract content manually
                # This is a fallback for when the model doesn't return valid JSON
                result = {
                    "summary": assistant_response,
                    "categories": []
                }

            # Validate categories are from the available list
            valid_categories = [
                cat for cat in result.get("categories", [])
                if cat in available_categories
            ]

            return {
                "summary": result.get("summary", "Summary generation failed"),
                "categories": valid_categories
            }

        except Exception as e:
            print(f"Error generating summary with Bedrock: {str(e)}")
            # Return a default response in case of error
            return {
                "summary": "Failed to generate summary due to technical error.",
                "categories": []
            }

    async def summarize_episode(
        self,
        transcript: str,
        available_categories: List[str]
    ) -> Dict[str, Any]:
        """Main method to summarize an episode."""
        return await self.generate_summary(transcript, available_categories)