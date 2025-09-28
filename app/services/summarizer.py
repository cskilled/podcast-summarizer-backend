import boto3
import json
from typing import List, Dict, Any

from app.core.config import settings


class SummarizerService:
    """Service for generating summaries using Amazon Bedrock with Gemini fallback."""

    def __init__(self):
        # Try to initialize Bedrock client
        self.bedrock_client = None
        self.gemini_model = None

        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            try:
                aws_config = {
                    'region_name': settings.AWS_REGION,
                    'aws_access_key_id': settings.AWS_ACCESS_KEY_ID,
                    'aws_secret_access_key': settings.AWS_SECRET_ACCESS_KEY
                }
                # Add session token if present (for temporary credentials)
                if settings.AWS_SESSION_TOKEN:
                    aws_config['aws_session_token'] = settings.AWS_SESSION_TOKEN

                self.bedrock_client = boto3.client('bedrock-runtime', **aws_config)
                print("✅ Bedrock client initialized")
            except Exception as e:
                print(f"⚠️  Failed to initialize Bedrock: {str(e)}")
                self.bedrock_client = None

        # Initialize Gemini as fallback
        if settings.GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self.gemini_model = genai.GenerativeModel(settings.GEMINI_MODEL_NAME)
                print("✅ Gemini fallback initialized")
            except Exception as e:
                print(f"⚠️  Failed to initialize Gemini: {str(e)}")
                self.gemini_model = None

    def create_prompt(self, transcript: str, categories: List[str]) -> str:
        """Create a prompt for the AI model."""
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

    async def generate_summary_with_bedrock(
        self,
        transcript: str,
        available_categories: List[str]
    ) -> Dict[str, Any]:
        """Generate summary using Amazon Bedrock."""
        if not self.bedrock_client:
            raise Exception("Bedrock client not available")

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
            result = {
                "summary": assistant_response,
                "categories": []
            }

        return result

    async def generate_summary_with_gemini(
        self,
        transcript: str,
        available_categories: List[str]
    ) -> Dict[str, Any]:
        """Generate summary using Google Gemini as fallback."""
        if not self.gemini_model:
            raise Exception("Gemini model not available")

        prompt = self.create_prompt(transcript, available_categories)

        # Generate with Gemini
        response = self.gemini_model.generate_content(prompt)

        # Extract the text response
        assistant_response = response.text

        # Parse the JSON response
        try:
            # Find JSON in the response (Gemini might add extra text)
            import re
            json_match = re.search(r'\{.*\}', assistant_response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(assistant_response)
        except (json.JSONDecodeError, AttributeError):
            # If JSON parsing fails, create a structured response
            result = {
                "summary": assistant_response[:500] if len(assistant_response) > 500 else assistant_response,
                "categories": []
            }

        return result

    async def generate_summary(
        self,
        transcript: str,
        available_categories: List[str]
    ) -> Dict[str, Any]:
        """Generate summary using Bedrock with Gemini fallback."""
        result = None

        # Try Bedrock first
        if self.bedrock_client:
            try:
                print("🔄 Attempting summary with Bedrock...")
                result = await self.generate_summary_with_bedrock(transcript, available_categories)
                print("✅ Summary generated with Bedrock")
            except Exception as e:
                print(f"❌ Bedrock failed: {str(e)}")
                result = None

        # Fallback to Gemini if Bedrock fails
        if result is None and self.gemini_model:
            try:
                print("🔄 Falling back to Gemini...")
                result = await self.generate_summary_with_gemini(transcript, available_categories)
                print("✅ Summary generated with Gemini")
            except Exception as e:
                print(f"❌ Gemini also failed: {str(e)}")
                result = None

        # If both fail, return a default response
        if result is None:
            print("⚠️  All AI services failed, returning default response")
            return {
                "summary": "Unable to generate summary. Please check your AI service configuration.",
                "categories": []
            }

        # Validate categories are from the available list
        valid_categories = [
            cat for cat in result.get("categories", [])
            if cat in available_categories
        ]

        return {
            "summary": result.get("summary", "Summary generation failed"),
            "categories": valid_categories[:5]  # Limit to 5 categories
        }

    async def summarize_episode(
        self,
        transcript: str,
        available_categories: List[str]
    ) -> Dict[str, Any]:
        """Main method to summarize an episode."""
        return await self.generate_summary(transcript, available_categories)