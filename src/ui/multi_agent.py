import os
import re
import subprocess
import asyncio

from semantic_kernel.agents import AgentGroupChat, ChatCompletionAgent
from semantic_kernel.agents.strategies.termination.termination_strategy import TerminationStrategy
from semantic_kernel.agents.strategies.selection.kernel_function_selection_strategy import (
    KernelFunctionSelectionStrategy,
)
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.kernel import Kernel

# === Personas ===
BUSINESS_ANALYST_PROMPT = """
You are a Business Analyst which will take the requirements from the user (also known as a 'customer') and create a project plan for creating the requested app. The Business Analyst understands the user requirements and creates detailed documents with requirements and costing. The documents should be usable by the SoftwareEngineer as a reference for implementing the required features, and by the Product Owner for reference to determine if the application delivered by the Software Engineer meets all of the user's requirements.
"""

SOFTWARE_ENGINEER_PROMPT = """
You are a Software Engineer, and your goal is create a web app using HTML and JavaScript by taking into consideration all the requirements given by the Business Analyst. The application should implement all the requested features. Deliver the code to the Product Owner for review when completed. You can also ask questions of the BusinessAnalyst to clarify any requirements that are unclear.
"""

PRODUCT_OWNER_PROMPT = """
You are the Product Owner which will review the software engineer's code to ensure all user  requirements are completed. You are the guardian of quality, ensuring the final product meets all specifications. IMPORTANT: Verify that the Software Engineer has shared the HTML code using the format ```html [code] ```. This format is required for the code to be saved and pushed to GitHub. Once all client requirements are completed and the code is properly formatted, reply with 'READY FOR USER APPROVAL'. If there are missing features or formatting issues, you will need to send a request back to the SoftwareEngineer or BusinessAnalyst with details of the defect.
"""

# === Termination Strategy ===
class ApprovalTerminationStrategy(TerminationStrategy):
    async def should_agent_terminate(self, agent, history):
        for message in history:
            if message.author_role == AuthorRole.USER and "APPROVED" in message.content.upper():
                return True
        return False

# === HTML Extraction and Save ===
def extract_html_code_from_messages(messages, agent_name="SoftwareEngineerAgent"):
    html_codes = []
    pattern = re.compile(r"```html\\s*(.*?)```", re.DOTALL | re.IGNORECASE)

    for msg in messages:
        if msg.agent_name == agent_name:
            matches = pattern.findall(msg.content)
            html_codes.extend(matches)

    return "\n".join(html_codes)

def save_html_to_file(html_code, filename="index.html"):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_code)

# === Main Multi-Agent Logic ===
async def run_multi_agent(user_input: str):
    kernel = Kernel()
    kernel.add_service(
        AzureChatCompletion(
            deployment_name=os.environ["AZURE_DEPLOYMENT_NAME"],
            endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"]
        )
    )

    # Create agents
    business_analyst = ChatCompletionAgent(
        kernel=kernel,
        name="BusinessAnalystAgent",
        instructions=BUSINESS_ANALYST_PROMPT
    )

    software_engineer = ChatCompletionAgent(
        kernel=kernel,
        name="SoftwareEngineerAgent",
        instructions=SOFTWARE_ENGINEER_PROMPT
    )

    product_owner = ChatCompletionAgent(
        kernel=kernel,
        name="ProductOwnerAgent",
        instructions=PRODUCT_OWNER_PROMPT
    )

    # Group chat setup
    group = AgentGroupChat(
        agents=[business_analyst, software_engineer, product_owner],
        execution_settings={"termination": ApprovalTerminationStrategy()},
    )

    # Start chat
    messages = await group.chat(ChatMessageContent.from_user(user_input))

    # After termination condition
    html_code = extract_html_code_from_messages(messages)
    if html_code.strip():
        save_html_to_file(html_code)
        subprocess.run(["bash", "push_to_github.sh"], check=True)


    return messages
