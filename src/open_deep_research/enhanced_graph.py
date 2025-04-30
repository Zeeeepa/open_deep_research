import asyncio
import json
import queue
import random
import uuid
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from typing import Dict, List, Any, Optional, Tuple, Set

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from open_deep_research.configuration import Configuration
from open_deep_research.utils import get_config_value, get_search_params, select_and_execute_search


class Reference:
    """A class to represent a reference to a source.
    
    Attributes:
        id (str): Unique identifier for the reference
        title (str): Title of the reference
        source (str): Source of the reference (URL, book, etc.)
        authors (List[str]): List of authors
        date (str): Publication date
        content_snippet (str): A snippet of the content
        relevance_score (float): Score indicating relevance to the research
    """
    
    def __init__(
        self,
        title: str,
        source: str,
        authors: Optional[List[str]] = None,
        date: Optional[str] = None,
        content_snippet: Optional[str] = None,
        relevance_score: float = 0.0
    ):
        """Initialize a new Reference.
        
        Args:
            title (str): Title of the reference
            source (str): Source of the reference (URL, book, etc.)
            authors (List[str], optional): List of authors. Defaults to None.
            date (str, optional): Publication date. Defaults to None.
            content_snippet (str, optional): A snippet of the content. Defaults to None.
            relevance_score (float, optional): Score indicating relevance. Defaults to 0.0.
        """
        self.id = str(uuid.uuid4())
        self.title = title
        self.source = source
        self.authors = authors or []
        self.date = date or ""
        self.content_snippet = content_snippet or ""
        self.relevance_score = relevance_score
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the reference to a dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the reference
        """
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "authors": self.authors,
            "date": self.date,
            "content_snippet": self.content_snippet,
            "relevance_score": self.relevance_score
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Reference':
        """Create a Reference from a dictionary.
        
        Args:
            data (Dict[str, Any]): Dictionary representation of the reference
            
        Returns:
            Reference: A new Reference instance
        """
        reference = cls(
            title=data.get("title", ""),
            source=data.get("source", ""),
            authors=data.get("authors", []),
            date=data.get("date", ""),
            content_snippet=data.get("content_snippet", ""),
            relevance_score=data.get("relevance_score", 0.0)
        )
        reference.id = data.get("id", reference.id)
        return reference


class EnhancedResearchGraph:
    """An enhanced graph-based structure for managing research nodes and their relationships.
    
    This class extends the basic ResearchGraph with additional features:
    - Reference tracking for proper citation
    - Improved node and edge representation
    - JSON serialization for persistence
    - Parallel search execution
    
    Attributes:
        nodes (Dict[str, Dict[str, Any]]): Dictionary of nodes in the graph
        adjacency_list (Dict[str, List[dict]]): Adjacency list representing edges
        references (Dict[str, Reference]): Dictionary of references
        future_to_query (Dict): Mapping of futures to queries for async execution
        executor (ThreadPoolExecutor): Executor for parallel processing
        n_active_tasks (int): Number of active search tasks
        search_results_queue (queue.Queue): Queue for search results
    """
    
    def __init__(self, config: Optional[Configuration] = None):
        """Initialize a new EnhancedResearchGraph.
        
        Args:
            config (Configuration, optional): Configuration for the graph. Defaults to None.
        """
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.adjacency_list: Dict[str, List[dict]] = defaultdict(list)
        self.references: Dict[str, Reference] = {}
        self.future_to_query = dict()
        
        self.config = config or Configuration(research_mode="enhanced")
        max_workers = self.config.max_parallel_searches if self.config.parallel_search_enabled else 1
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.n_active_tasks = 0
        self.search_results_queue = queue.Queue()
    
    def add_root_node(
        self,
        node_content: str,
        node_name: str = "root",
    ):
        """Add the root node representing the main research question.
        
        Args:
            node_content (str): The main research question
            node_name (str, optional): Name for the root node. Defaults to "root".
        """
        node_id = node_name
        self.nodes[node_id] = {
            "id": node_id,
            "content": node_content,
            "type": "root",
            "created_at": time.time(),
            "reference_ids": []
        }
    
    def add_search_node(
        self,
        parent_id: str,
        node_content: str,
        node_name: Optional[str] = None,
    ) -> str:
        """Add a search node to the graph.
        
        Args:
            parent_id (str): ID of the parent node
            node_content (str): Content of the search node (query)
            node_name (str, optional): Name for the node. Defaults to None.
            
        Returns:
            str: ID of the created node
        """
        node_id = node_name or f"search_{str(uuid.uuid4())[:8]}"
        self.nodes[node_id] = {
            "id": node_id,
            "content": node_content,
            "type": "search",
            "created_at": time.time(),
            "reference_ids": []
        }
        
        # Add edge from parent to this node
        edge_id = f"{parent_id}_{node_id}"
        self.adjacency_list[parent_id].append({
            "id": edge_id,
            "name": node_id,
            "state": 1  # 1 = pending, 2 = processing, 3 = completed
        })
        
        return node_id
    
    def add_response_node(
        self,
        parent_id: str,
        node_content: str,
        response_content: str,
        reference_ids: Optional[List[str]] = None,
        node_name: Optional[str] = None,
    ) -> str:
        """Add a response node to the graph.
        
        Args:
            parent_id (str): ID of the parent node
            node_content (str): Original content that prompted the response
            response_content (str): The response content
            reference_ids (List[str], optional): List of reference IDs. Defaults to None.
            node_name (str, optional): Name for the node. Defaults to None.
            
        Returns:
            str: ID of the created node
        """
        node_id = node_name or f"response_{str(uuid.uuid4())[:8]}"
        self.nodes[node_id] = {
            "id": node_id,
            "content": node_content,
            "response": response_content,
            "type": "response",
            "created_at": time.time(),
            "reference_ids": reference_ids or []
        }
        
        # Add edge from parent to this node
        edge_id = f"{parent_id}_{node_id}"
        self.adjacency_list[parent_id].append({
            "id": edge_id,
            "name": node_id,
            "state": 3  # 1 = pending, 2 = processing, 3 = completed
        })
        
        return node_id
    
    def add_reference(self, reference: Reference) -> str:
        """Add a reference to the graph.
        
        Args:
            reference (Reference): The reference to add
            
        Returns:
            str: ID of the added reference
        """
        self.references[reference.id] = reference
        return reference.id
    
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get a node by its ID.
        
        Args:
            node_id (str): ID of the node to get
            
        Returns:
            Optional[Dict[str, Any]]: The node data or None if not found
        """
        return self.nodes.get(node_id)
    
    def get_reference(self, reference_id: str) -> Optional[Reference]:
        """Get a reference by its ID.
        
        Args:
            reference_id (str): ID of the reference to get
            
        Returns:
            Optional[Reference]: The reference or None if not found
        """
        return self.references.get(reference_id)
    
    def get_node_references(self, node_id: str) -> List[Reference]:
        """Get all references for a node.
        
        Args:
            node_id (str): ID of the node
            
        Returns:
            List[Reference]: List of references for the node
        """
        node = self.get_node(node_id)
        if not node:
            return []
        
        return [self.get_reference(ref_id) for ref_id in node.get("reference_ids", []) 
                if self.get_reference(ref_id)]
    
    def get_all_references(self) -> List[Reference]:
        """Get all references in the graph.
        
        Returns:
            List[Reference]: List of all references
        """
        return list(self.references.values())
    
    def get_all_search_results(self) -> Dict[str, Any]:
        """Get all search results from the graph.
        
        Returns:
            Dict[str, Any]: Dictionary mapping search queries to results
        """
        results = {}
        for node_id, node in self.nodes.items():
            if node["type"] == "search" and "response" in node:
                results[node["content"]] = node["response"]
        return results
    
    async def execute_search(
        self,
        node_id: str,
        query: str,
        config: Optional[Dict[str, Any]] = None
    ):
        """Execute a search for a given node.
        
        Args:
            node_id (str): ID of the node to search for
            query (str): Search query
            config (Dict[str, Any], optional): Configuration for the search. Defaults to None.
        """
        # Update edge state to processing
        for parent_id, edges in self.adjacency_list.items():
            for edge in edges:
                if edge["name"] == node_id:
                    edge["state"] = 2  # processing
        
        # Execute search
        search_params = get_search_params(config)
        search_results = await select_and_execute_search(query, search_params)
        
        # Extract references from search results
        reference_ids = []
        if self.config.reference_tracking_enabled and search_results:
            for result in search_results.get("results", []):
                # Create a reference from the search result
                reference = Reference(
                    title=result.get("title", ""),
                    source=result.get("url", ""),
                    content_snippet=result.get("content", ""),
                    relevance_score=float(result.get("score", 0.0))
                )
                reference_id = self.add_reference(reference)
                reference_ids.append(reference_id)
        
        # Update node with search results and references
        self.nodes[node_id]["response"] = search_results
        self.nodes[node_id]["reference_ids"] = reference_ids
        
        # Update edge state to completed
        for parent_id, edges in self.adjacency_list.items():
            for edge in edges:
                if edge["name"] == node_id:
                    edge["state"] = 3  # completed
        
        # Add to results queue
        self.search_results_queue.put((node_id, search_results))
    
    async def execute_searches_parallel(
        self,
        queries: List[Tuple[str, str]],
        config: Optional[Dict[str, Any]] = None
    ):
        """Execute multiple searches in parallel.
        
        Args:
            queries (List[Tuple[str, str]]): List of (node_id, query) tuples
            config (Dict[str, Any], optional): Configuration for the searches. Defaults to None.
        """
        if not self.config.parallel_search_enabled:
            # Execute searches sequentially if parallel is disabled
            for node_id, query in queries:
                await self.execute_search(node_id, query, config)
            return
        
        # Execute searches in parallel
        tasks = []
        for node_id, query in queries:
            task = asyncio.create_task(self.execute_search(node_id, query, config))
            tasks.append(task)
        
        # Wait for all searches to complete
        await asyncio.gather(*tasks)
    
    async def generate_response_with_references(
        self,
        prompt: str,
        context: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, List[str]]:
        """Generate a response with references.
        
        Args:
            prompt (str): The prompt for the response
            context (str): Context information for the response
            config (Dict[str, Any], optional): Configuration for the response. Defaults to None.
            
        Returns:
            Tuple[str, List[str]]: The response and list of reference IDs
        """
        config_dict = config or {}
        
        # Initialize the model
        writer_provider = get_config_value("writer_provider", config_dict, self.config)
        writer_model = get_config_value("writer_model", config_dict, self.config)
        writer_model_kwargs = get_config_value("writer_model_kwargs", config_dict, self.config) or {}
        
        llm = init_chat_model(
            model=writer_model,
            provider=writer_provider,
            **writer_model_kwargs
        )
        
        # Create system message with instructions for citing references
        system_message = SystemMessage(
            content=f"""You are a research assistant that generates responses based on provided context.
            Your task is to answer the prompt using the provided context.
            
            When using information from the context, cite the sources using [n] notation,
            where n is the number of the source in your response.
            
            At the end of your response, include a numbered list of all sources you cited.
            """
        )
        
        # Create human message with prompt and context
        human_message = HumanMessage(
            content=f"""Prompt: {prompt}
            
            Context:
            {context}
            """
        )
        
        # Generate response
        response = await llm.ainvoke([system_message, human_message])
        response_text = response.content
        
        # Extract reference IDs from the response
        # This is a simplified approach - in a real implementation, you would parse the
        # response to extract the actual references and match them to your reference database
        reference_ids = []
        if self.config.reference_tracking_enabled:
            # For this example, we'll just return all references in the context
            # In a real implementation, you would parse the response to extract the actual references
            for ref_id, ref in self.references.items():
                if ref.content_snippet and ref.content_snippet in context:
                    reference_ids.append(ref_id)
        
        return response_text, reference_ids
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the graph to a dictionary for serialization.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the graph
        """
        return {
            "nodes": self.nodes,
            "edges": {k: [edge for edge in v] for k, v in self.adjacency_list.items()},
            "references": {k: ref.to_dict() for k, ref in self.references.items()}
        }
    
    def to_json(self) -> str:
        """Convert the graph to a JSON string.
        
        Returns:
            str: JSON representation of the graph
        """
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], config: Optional[Configuration] = None) -> 'EnhancedResearchGraph':
        """Create an EnhancedResearchGraph from a dictionary.
        
        Args:
            data (Dict[str, Any]): Dictionary representation of the graph
            config (Configuration, optional): Configuration for the graph. Defaults to None.
            
        Returns:
            EnhancedResearchGraph: A new EnhancedResearchGraph instance
        """
        graph = cls(config)
        graph.nodes = data.get("nodes", {})
        
        # Reconstruct adjacency list
        graph.adjacency_list = defaultdict(list)
        for parent_id, edges in data.get("edges", {}).items():
            graph.adjacency_list[parent_id] = edges
        
        # Reconstruct references
        graph.references = {}
        for ref_id, ref_data in data.get("references", {}).items():
            graph.references[ref_id] = Reference.from_dict(ref_data)
        
        return graph
    
    @classmethod
    def from_json(cls, json_str: str, config: Optional[Configuration] = None) -> 'EnhancedResearchGraph':
        """Create an EnhancedResearchGraph from a JSON string.
        
        Args:
            json_str (str): JSON representation of the graph
            config (Configuration, optional): Configuration for the graph. Defaults to None.
            
        Returns:
            EnhancedResearchGraph: A new EnhancedResearchGraph instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data, config)
    
    def save_to_file(self, filepath: str):
        """Save the graph to a JSON file.
        
        Args:
            filepath (str): Path to save the file
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
    
    @classmethod
    def load_from_file(cls, filepath: str, config: Optional[Configuration] = None) -> 'EnhancedResearchGraph':
        """Load a graph from a JSON file.
        
        Args:
            filepath (str): Path to the file
            config (Configuration, optional): Configuration for the graph. Defaults to None.
            
        Returns:
            EnhancedResearchGraph: A new EnhancedResearchGraph instance
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            json_str = f.read()
        return cls.from_json(json_str, config)


class EnhancedResearchAgent:
    """Agent for conducting research using the enhanced graph methodology.
    
    This agent uses the EnhancedResearchGraph to conduct research on a topic,
    generate sub-questions, and produce a final report with proper citations.
    
    Attributes:
        graph (EnhancedResearchGraph): The research graph
        config (Configuration): Configuration for the agent
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize a new EnhancedResearchAgent.
        
        Args:
            config (Dict[str, Any], optional): Configuration for the agent. Defaults to None.
        """
        self.config_dict = config or {}
        self.config = Configuration.from_runnable_config({"configurable": self.config_dict})
        self.graph = EnhancedResearchGraph(self.config)
        self.topic = ""
    
    async def initialize_with_topic(self, topic: str):
        """Initialize the research with a topic.
        
        Args:
            topic (str): The research topic
        """
        self.topic = topic
        self.graph.add_root_node(topic)
    
    async def generate_sub_questions(self, topic: str) -> List[str]:
        """Generate sub-questions for the research topic.
        
        Args:
            topic (str): The research topic
            
        Returns:
            List[str]: List of sub-questions
        """
        # Initialize the model
        planner_provider = get_config_value("planner_provider", self.config_dict, self.config)
        planner_model = get_config_value("planner_model", self.config_dict, self.config)
        planner_model_kwargs = get_config_value("planner_model_kwargs", self.config_dict, self.config) or {}
        
        llm = init_chat_model(
            model=planner_model,
            provider=planner_provider,
            **planner_model_kwargs
        )
        
        # Create system message
        system_message = SystemMessage(
            content="""You are a research planner. Your task is to generate specific, 
            focused sub-questions that will help explore a research topic thoroughly.
            
            Generate questions that:
            1. Cover different aspects of the topic
            2. Are specific enough to be answered with a focused search
            3. Together provide comprehensive coverage of the topic
            4. Are diverse in their approach to the topic
            
            Return ONLY the list of questions, one per line, with no additional text.
            """
        )
        
        # Create human message
        human_message = HumanMessage(
            content=f"Generate {self.config.number_of_queries} focused sub-questions for researching: {topic}"
        )
        
        # Generate sub-questions
        response = await llm.ainvoke([system_message, human_message])
        
        # Parse the response into a list of questions
        questions = [q.strip() for q in response.content.strip().split('\n') if q.strip()]
        
        return questions
    
    async def expand_graph_with_questions(self, questions: List[str]):
        """Expand the research graph with sub-questions.
        
        Args:
            questions (List[str]): List of sub-questions
        """
        # Add search nodes for each question
        search_queries = []
        for question in questions:
            node_id = self.graph.add_search_node("root", question)
            search_queries.append((node_id, question))
        
        # Execute searches in parallel
        await self.graph.execute_searches_parallel(search_queries, self.config_dict)
        
        # Process search results and generate responses
        for node_id, _ in search_queries:
            node = self.graph.get_node(node_id)
            if not node or "response" not in node:
                continue
            
            search_results = node["response"]
            context = "\n\n".join([
                f"Source {i+1}: {result.get('content', '')}"
                for i, result in enumerate(search_results.get("results", []))
            ])
            
            # Generate response with references
            response_text, reference_ids = await self.graph.generate_response_with_references(
                prompt=node["content"],
                context=context,
                config=self.config_dict
            )
            
            # Add response node
            self.graph.add_response_node(
                parent_id=node_id,
                node_content=node["content"],
                response_content=response_text,
                reference_ids=reference_ids
            )
    
    async def generate_final_response(self) -> str:
        """Generate a final response based on the research.
        
        Returns:
            str: The final research report
        """
        # Collect all response nodes
        responses = []
        for node_id, node in self.graph.nodes.items():
            if node["type"] == "response":
                responses.append(node["response"])
        
        # Collect all references
        references = self.graph.get_all_references()
        references_text = "\n".join([
            f"{i+1}. {ref.title} - {ref.source}"
            for i, ref in enumerate(references)
        ])
        
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
            content=f"""You are a research report writer. Your task is to synthesize research findings 
            into a comprehensive report on the topic: {self.topic}.
            
            Use the following structure for your report:
            {self.config.report_structure}
            
            When using information from the research, cite the sources using [n] notation,
            where n is the number of the source in your references list.
            """
        )
        
        # Create human message
        human_message = HumanMessage(
            content=f"""Write a comprehensive research report on: {self.topic}
            
            Research findings:
            {' '.join(responses)}
            
            References:
            {references_text}
            """
        )
        
        # Generate final report
        response = await llm.ainvoke([system_message, human_message])
        
        return response.content
    
    def save_research(self, filepath: str):
        """Save the research graph to a file.
        
        Args:
            filepath (str): Path to save the file
        """
        self.graph.save_to_file(filepath)
    
    @classmethod
    def load_research(cls, filepath: str, config: Optional[Dict[str, Any]] = None) -> 'EnhancedResearchAgent':
        """Load a research graph from a file.
        
        Args:
            filepath (str): Path to the file
            config (Dict[str, Any], optional): Configuration for the agent. Defaults to None.
            
        Returns:
            EnhancedResearchAgent: A new EnhancedResearchAgent instance
        """
        agent = cls(config)
        agent.graph = EnhancedResearchGraph.load_from_file(filepath, agent.config)
        return agent


# Factory function to create an enhanced research agent
def create_enhanced_research_agent(config: Optional[Dict[str, Any]] = None) -> EnhancedResearchAgent:
    """Create an enhanced research agent.
    
    Args:
        config (Dict[str, Any], optional): Configuration for the agent. Defaults to None.
        
    Returns:
        EnhancedResearchAgent: A new EnhancedResearchAgent instance
    """
    return EnhancedResearchAgent(config)

