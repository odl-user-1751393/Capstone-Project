import os
import re
import platform
import subprocess
import asyncio

from dotenv import load_dotenv

load_dotenv()

from semantic_kernel.agents import AgentGroupChat, ChatCompletionAgent
from semantic_kernel.agents.strategies.termination.termination_strategy import TerminationStrategy
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
            if (
                message.role == "assistant"
                and "READY FOR USER APPROVAL" in message.content.upper()
            ):
                return True
        return False

# === HTML Extraction and Save ===
def extract_html_code_from_messages(messages, agent_name="SoftwareEngineerAgent"):
    html_codes = []
    pattern = re.compile(r"```html\s*(.*?)```", re.DOTALL | re.IGNORECASE)

    for msg in messages:
        if msg.get("agent_name") == agent_name:
            matches = pattern.findall(msg.get("content", ""))
            html_codes.extend(matches)

    return "\n".join(html_codes)

def save_html_to_file(html_code, filename="index.html"):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_code)

# === Helper to check OS ===
def push_code():
    if platform.system() == "Windows":
        bash_path = r"C:\Program Files\Git\bin\bash.exe"  # Adjust if needed
        subprocess.run([bash_path, "push_to_github.sh"], check=True)
    else:
        subprocess.run(["bash", "push_to_github.sh"], check=True)

# === Pushing to repository after APPROVED ===
def finalize_approval_and_push(messages):
    html_code = extract_html_code_from_messages(messages)
    if html_code.strip():
        save_html_to_file(html_code)
        push_code()
    print("✅ Code saved and pushed to GitHub!")

# === Main Multi-Agent Logic ===
async def run_multi_agent(user_input: str):
    kernel = Kernel()
    kernel.add_service(
        AzureChatCompletion(
            deployment_name=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"],
            endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"]
        )
    )

    # Create agents with proper personas and names
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

    # Create AgentGroupChat with termination_strategy passed in constructor
    group = AgentGroupChat(
        agents=[business_analyst, software_engineer, product_owner],
        termination_strategy=ApprovalTerminationStrategy()
    )

    # DO NOT try to set group.execution_settings.termination (does not exist)

    # Add the initial user message
    await group.add_chat_message(
        ChatMessageContent(
            role="user",
            author_role=AuthorRole.USER,
            content=user_input
        )
    )

    # Run the multi-agent chat loop asynchronously
    messages = []
    ready_for_approval = False

    async for content in group.invoke():
        author_role = getattr(content, "author_role", None)
        author_role_name = author_role.name if author_role else None

        print(f"# {content.role} - {content.name or '*'}: '{content.content}'")

        messages.append({
            "content": content.content,
            "agent_name": content.name,
            "role": content.role,
            "author_role": author_role_name,
        })

        if (
            content.role == "assistant"
            and content.name == "ProductOwnerAgent"
            and "READY FOR USER APPROVAL" in content.content.upper()
        ):
            ready_for_approval = True
            break  # stop the loop here and wait for actual user input

            # After termination condition is met (ApprovalTerminationStrategy triggers)
    if ready_for_approval:
        # Instead of waiting for input here, just return that approval is required
        return {
            "messages": messages,
            "ready_for_approval": True
        }

    # If no approval needed, just return messages
    return {
        "messages": messages,
        "ready_for_approval": False
    }
