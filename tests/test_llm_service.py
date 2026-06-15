from unittest.mock import MagicMock, mock_open, patch

# Correctly patch the LLMService to avoid init issues (missing API KEY)
from app.features.communication.llm_service import LLMService


class TestLLMService:
    @patch("app.features.communication.llm_service.settings")
    @patch("app.features.communication.llm_service.genai")
    def test_prompt_rendering(self, mock_genai, mock_settings):
        # Setup
        mock_settings.GOOGLE_API_KEY = "fake"
        mock_settings.GOOGLE_APPLICATION_CREDENTIALS = "fake.json"

        service = LLMService()

        # Mock Context
        context = {
            "business_name": " Barbería <script>alert(1)</script> ",
            "today": "2023-10-27",
            "day_name": "Viernes",
            "barbers": ["Juan", "Pedro"],
            "current_state": "IDLE",
            "history": [],
        }
        message_body = "Hola {{ destructive_variable }}"

        # We need to test the INTERNAL rendering logic.
        # Since analyze_message loads from YAML, we should mock the YAML load to provide a controlled template.

        # Mock open to avoid IO error or file dependency
        with patch("builtins.open", mock_open(read_data="dummy")):
            # Mock yaml to return controlled template
            with patch("app.features.communication.llm_service.yaml.safe_load") as mock_yaml:
                test_template = "Biz: {business_name} | Msg: {message_body}"
                mock_yaml.return_value = {"system_prompt": test_template}

                # Mock Client Response
                mock_response = MagicMock()
                mock_response.text = '{"intent": "CHITCHAT"}'
                service.client.models.generate_content.return_value = mock_response

                # Run
                result = service.analyze_message(message_body, context)

                print(f"Result: {result}")

                # Verify Call
                assert service.client.models.generate_content.called, "generate_content was not called!"

                # Check Prompt Content
                call_args = service.client.models.generate_content.call_args
                # kwargs['contents'] should contain the rendered string
                rendered_prompt = call_args.kwargs["contents"]

                print(f"Rendered Prompt: {rendered_prompt}")

                # Check Jinja2 rendering
                assert "Biz:  Barbería <script>alert(1)</script> " in rendered_prompt  # Should contain value
                assert "Msg: Hola {{ destructive_variable }}" in rendered_prompt  # Should contain literal braces

            # Check that {{ destructive_variable }} was NOT interpreted as a tag (it's inside message_body variable)
            # Jinja2 auto-escapes? No, we are rendering a string.
            # In `t.render(message_body="...")`, the value is put in.
            # If the template was "Msg: {{ message_body }}", and content is "{{ val }}",
            # output is "{{ val }}". It is NOT recursive.
            # This confirms injection protection (user input is treated as data, not code).
