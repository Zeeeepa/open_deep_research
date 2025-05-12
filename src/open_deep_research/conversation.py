import json
import time
import uuid
from typing import Dict, List, Any, Optional, Tuple

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig

from open_deep_research.configuration import Configuration
from open_deep_research.enhanced_graph import Reference
from open_deep_research.utils import get_config_value


class ConversationMessage:
    """A class to represent a message in a conversation.
    
    Attributes:
        id (str): Unique identifier for the message
        role (str): Role of the message sender (user or assistant)
        content (str): Content of the message
        reference_ids (List[str]): List of reference IDs used in the message
        timestamp (float): Timestamp of the message
    """
    
    def __init__(
        self,
        role: str,
        content: str,
        reference_ids: Optional[List[str]] = None,
        timestamp: Optional[float] = None
    ):
        """Initialize a new ConversationMessage.
        
        Args:
            role (str): Role of the message sender (user or assistant)
            content (str): Content of the message
            reference_ids (List[str], optional): List of reference IDs. Defaults to None.
            timestamp (float, optional): Timestamp of the message. Defaults to None.
        """
        self.id = str(uuid.uuid4())
        self.role = role
        self.content = content
        self.reference_ids = reference_ids or []
        self.timestamp = timestamp or time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the message to a dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the message
        """
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "reference_ids": self.reference_ids,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationMessage':
        """Create a ConversationMessage from a dictionary.
        
        Args:
            data (Dict[str, Any]): Dictionary representation of the message
            
        Returns:
            ConversationMessage: A new ConversationMessage instance
        """
        message = cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            reference_ids=data.get("reference_ids", []),
            timestamp=data.get("timestamp", time.time())
        )
        message.id = data.get("id", message.id)
        return message


class Conversation:
    """A class to represent a conversation about research.
    
    This class manages a conversation between a user and an assistant about
    research findings, allowing the user to ask questions and get answers
    with proper citations.
    
    Attributes:
        messages (List[ConversationMessage]): List of messages in the conversation
        references (Dict[str, Reference]): Dictionary of references
        research_context (Dict[str, Any]): Context from the research
        config (Configuration): Configuration for the conversation
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        references: Optional[Dict[str, Reference]] = None,
        research_context: Optional[Dict[str, Any]] = None
    ):
        """Initialize a new Conversation.
        
        Args:
            config (Dict[str, Any], optional): Configuration for the conversation. Defaults to None.
            references (Dict[str, Reference], optional): Dictionary of references. Defaults to None.
            research_context (Dict[str, Any], optional): Context from the research. Defaults to None.
        """
        self.config_dict = config or {}
        self.config = Configuration.from_runnable_config({"configurable": self.config_dict})
        self.messages: List[ConversationMessage] = []
        self.references = references or {}
        self.research_context = research_context or {}
    
    def add_message(self, message: ConversationMessage):
        """Add a message to the conversation.
        
        Args:
            message (ConversationMessage): The message to add
        """
        self.messages.append(message)
    
    def get_messages(self) -> List[ConversationMessage]:
        """Get all messages in the conversation.
        
        Returns:
            List[ConversationMessage]: List of all messages
        """
        return self.messages
    
    def get_message_history(self) -> List[Dict[str, Any]]:
        """Get the message history in a format suitable for LLM context.
        
        Returns:
            List[Dict[str, Any]]: List of message dictionaries
        """
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.messages
        ]
    
    def set_research_context(self, context: Dict[str, Any]):
        """Set the research context.
        
        Args:
            context (Dict[str, Any]): The research context
        """
        self.research_context = context
    
    def set_references(self, references: Dict[str, Reference]):
        """Set the references.
        
        Args:
            references (Dict[str, Reference]): Dictionary of references
        """
        self.references = references
    
    async def ask(self, question: str) -> str:
        """Ask a question and get an answer with citations.
        
        Args:
            question (str): The question to ask
            
        Returns:
            str: The answer with citations
        """
        # Add user message
        user_message = ConversationMessage("user", question)
        self.add_message(user_message)
        
        # Prepare context for the assistant
        final_report = self.research_context.get("final_report", "")
        search_results = self.research_context.get("search_results", {})
        
        context_text = final_report + "\n\n"
        if search_results:
            context_text += "Additional search results:\n"
            for query, results in search_results.items():
                context_text += f"Query: {query}\n"
                if isinstance(results, dict) and "results" in results:
                    for i, result in enumerate(results.get("results", [])):
                        context_text += f"Result {i+1}: {result.get('content', '')}\n"
                context_text += "\n"
        
        # Prepare references
        references_text = ""
        if self.references:
            references_text = "References:\n"
            for i, (ref_id, ref) in enumerate(self.references.items()):
                references_text += f"{i+1}. {ref.title} - {ref.source}\n"
        
        # Initialize the model
        writer_provider = get_config_value("writer_provider", self.config_dict, self.config)
        writer_model = get_config_value("writer_model", self.config_dict, self.config)
        writer_model_kwargs = get_config_value("writer_model_kwargs", self.config_dict, self.config) or {}
        
        llm = init_chat_model(
            model=writer_model,
            provider=writer_provider,
            **writer_model_kwargs
        )
        
        # Create system message
        system_message = SystemMessage(
            content="""You are a research assistant that answers questions based on research findings.
            
            When answering questions:
            1. Use the provided research context to inform your answers
            2. Cite sources using [n] notation, where n is the number of the source
            3. If the research context doesn't contain relevant information, acknowledge this
            4. Be concise but thorough in your responses
            5. At the end of your response, include a list of the sources you cited
            """
        )
        
        # Convert conversation history to langchain messages
        history = []
        for msg in self.messages[:-1]:  # Exclude the latest user message
            if msg.role == "user":
                history.append(HumanMessage(content=msg.content))
            else:
                history.append(AIMessage(content=msg.content))
        
        # Create human message with the question and context
        human_message = HumanMessage(
            content=f"""Question: {question}
            
            Research Context:
            {context_text}
            
            {references_text}
            """
        )
        
        # Generate answer
        messages = [system_message] + history + [human_message]
        response = await llm.ainvoke(messages)
        answer = response.content
        
        # Extract reference IDs from the answer
        reference_ids = []
        if self.config.reference_tracking_enabled:
            # For this example, we'll use a simple approach
            # In a real implementation, you would parse the answer to extract the actual references
            for ref_id, ref in self.references.items():
                if ref.title and ref.title in answer:
                    reference_ids.append(ref_id)
        
        # Add assistant message
        assistant_message = ConversationMessage("assistant", answer, reference_ids)
        self.add_message(assistant_message)
        
        return answer
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the conversation to a dictionary for serialization.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the conversation
        """
        return {
            "messages": [msg.to_dict() for msg in self.messages],
            "references": {k: ref.to_dict() for k, ref in self.references.items()},
            "research_context": self.research_context
        }
    
    def to_json(self) -> str:
        """Convert the conversation to a JSON string.
        
        Returns:
            str: JSON representation of the conversation
        """
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> 'Conversation':
        """Create a Conversation from a dictionary.
        
        Args:
            data (Dict[str, Any]): Dictionary representation of the conversation
            config (Dict[str, Any], optional): Configuration for the conversation. Defaults to None.
            
        Returns:
            Conversation: A new Conversation instance
        """
        # Create conversation
        conversation = cls(config)
        
        # Reconstruct messages
        for msg_data in data.get("messages", []):
            conversation.add_message(ConversationMessage.from_dict(msg_data))
        
        # Reconstruct references
        references = {}
        for ref_id, ref_data in data.get("references", {}).items():
            references[ref_id] = Reference.from_dict(ref_data)
        conversation.references = references
        
        # Set research context
        conversation.research_context = data.get("research_context", {})
        
        return conversation
    
    @classmethod
    def from_json(cls, json_str: str, config: Optional[Dict[str, Any]] = None) -> 'Conversation':
        """Create a Conversation from a JSON string.
        
        Args:
            json_str (str): JSON representation of the conversation
            config (Dict[str, Any], optional): Configuration for the conversation. Defaults to None.
            
        Returns:
            Conversation: A new Conversation instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data, config)
    
    def save_to_file(self, filepath: str):
        """Save the conversation to a JSON file.
        
        Args:
            filepath (str): Path to save the file
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
    
    @classmethod
    def load_from_file(cls, filepath: str, config: Optional[Dict[str, Any]] = None) -> 'Conversation':
        """Load a conversation from a JSON file.
        
        Args:
            filepath (str): Path to the file
            config (Dict[str, Any], optional): Configuration for the conversation. Defaults to None.
            
        Returns:
            Conversation: A new Conversation instance
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            json_str = f.read()
        return cls.from_json(json_str, config)


# Factory function to create a conversation agent
def create_conversation_agent(
    config: Optional[Dict[str, Any]] = None,
    references: Optional[Dict[str, Reference]] = None,
    research_context: Optional[Dict[str, Any]] = None
) -> Conversation:
    """Create a conversation agent.
    
    Args:
        config (Dict[str, Any], optional): Configuration for the agent. Defaults to None.
        references (Dict[str, Reference], optional): Dictionary of references. Defaults to None.
        research_context (Dict[str, Any], optional): Context from the research. Defaults to None.
        
    Returns:
        Conversation: A new Conversation instance
    """
    return Conversation(config, references, research_context)

