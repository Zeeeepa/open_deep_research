import asyncio
import queue
import random
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from typing import Dict, List, Any, Optional, Tuple

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from open_deep_research.configuration import Configuration
from open_deep_research.utils import get_config_value, get_search_params, select_and_execute_search


class ResearchGraph:
    """A graph-based structure for managing research nodes and their relationships.
    
    This class provides methods for creating and managing a graph of research nodes,
    where each node represents a research question or sub-question, and edges represent
    relationships between questions.
    
    Attributes:
        nodes (Dict[str, Dict[str, Any]]): Dictionary of nodes in the graph
        adjacency_list (Dict[str, List[dict]]): Adjacency list representing edges
        future_to_query (Dict): Mapping of futures to queries for async execution
        executor (ThreadPoolExecutor): Executor for parallel processing
        n_active_tasks (int): Number of active search tasks
    """
    
    def __init__(self):
        """Initialize a new ResearchGraph."""
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.adjacency_list: Dict[str, List[dict]] = defaultdict(list)
        self.future_to_query = dict()
        self.executor = ThreadPoolExecutor(max_workers=10)
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
            node_name (str, optional): Name for the node. Defaults to "root".
        """
        self.nodes[node_name] = dict(content=node_content, type="root")
        self.adjacency_list[node_name] = []
    
    async def add_search_node(
        self,
        node_name: str,
        node_content: str,
        config: RunnableConfig,
        parent_node: Optional[str] = "root",
    ):
        """Add a search node for a specific research question.
        
        Args:
            node_name (str): Name for the node
            node_content (str): The research question
            config (RunnableConfig): Configuration for search
            parent_node (str, optional): Parent node name. Defaults to "root".
            
        Returns:
            Dict: The search results
        """
        # Create the node
        self.nodes[node_name] = dict(content=node_content, type="search")
        self.adjacency_list[node_name] = []
        
        # Connect to parent if provided
        if parent_node and parent_node in self.nodes:
            self.add_edge(parent_node, node_name)
        
        # Get configuration
        configurable = Configuration.from_runnable_config(config)
        search_api = get_config_value(configurable.search_api)
        search_api_config = configurable.search_api_config or {}
        params_to_pass = get_search_params(search_api, search_api_config)
        
        # Execute search
        query_list = [node_content]
        source_str = await select_and_execute_search(search_api, query_list, params_to_pass)
        
        # Store results in the node
        self.nodes[node_name]["response"] = source_str
        
        # Put results in queue for streaming
        self.search_results_queue.put((node_name, self.nodes[node_name], []))
        
        return source_str
    
    def add_response_node(
        self,
        node_content: str,
        node_name: str = "response",
        parent_nodes: Optional[List[str]] = None,
    ):
        """Add a response node containing the final research output.
        
        Args:
            node_content (str): The final research output
            node_name (str, optional): Name for the node. Defaults to "response".
            parent_nodes (List[str], optional): List of parent node names. Defaults to None.
        """
        self.nodes[node_name] = dict(content=node_content, type="response")
        self.adjacency_list[node_name] = []
        
        # Connect to parent nodes if provided
        if parent_nodes:
            for parent in parent_nodes:
                if parent in self.nodes:
                    self.add_edge(parent, node_name)
        
        # Put in queue for streaming
        self.search_results_queue.put((node_name, self.nodes[node_name], []))
    
    def add_edge(self, start_node: str, end_node: str):
        """Add an edge between two nodes.
        
        Args:
            start_node (str): Starting node name
            end_node (str): Ending node name
        """
        edge_id = str(uuid.uuid4())
        self.adjacency_list[start_node].append(dict(id=edge_id, name=end_node, state=2))
        self.search_results_queue.put(
            (start_node, self.nodes[start_node], self.adjacency_list[start_node])
        )
    
    def reset(self):
        """Reset the graph, clearing all nodes and edges."""
        self.nodes = {}
        self.adjacency_list = defaultdict(list)
    
    def node(self, node_name: str) -> dict:
        """Get a copy of a node's data.
        
        Args:
            node_name (str): Name of the node to retrieve
            
        Returns:
            dict: Copy of the node data
        """
        return self.nodes[node_name].copy() if node_name in self.nodes else {}
    
    def get_all_search_results(self) -> str:
        """Get all search results from the graph.
        
        Returns:
            str: Combined search results from all search nodes
        """
        results = []
        for name, node in self.nodes.items():
            if node["type"] == "search" and "response" in node:
                results.append(f"## {node['content']}\n\n{node['response']}")
        
        return "\n\n".join(results)
    
    def to_visualization_data(self) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
        """Convert the graph to a format suitable for visualization.
        
        Returns:
            Tuple: (nodes, edges) in a format suitable for visualization libraries
        """
        # Create a deep copy to avoid modifying the original data
        nodes = deepcopy(self.nodes)
        edges = deepcopy(self.adjacency_list)
        
        # Update edge states based on node completion
        for neighbors in edges.values():
            for neighbor in neighbors:
                # state: 1=in progress, 2=not started, 3=completed
                if not (neighbor["name"] in nodes and "response" in nodes[neighbor["name"]]):
                    neighbor["state"] = 2
                else:
                    neighbor["state"] = 3
        
        return nodes, edges


class GraphResearchAgent:
    """Agent that uses a graph-based approach for research.
    
    This agent manages the research process by creating and expanding a graph
    of research questions and their results.
    
    Attributes:
        graph (ResearchGraph): The research graph
        config (RunnableConfig): Configuration for the agent
    """
    
    def __init__(self, config: RunnableConfig):
        """Initialize a new GraphResearchAgent.
        
        Args:
            config (RunnableConfig): Configuration for the agent
        """
        self.graph = ResearchGraph()
        self.config = config
        self.configurable = Configuration.from_runnable_config(config)
    
    async def initialize_with_topic(self, topic: str):
        """Initialize the research graph with a main topic.
        
        Args:
            topic (str): The main research topic
        """
        self.graph.add_root_node(node_content=topic)
    
    async def generate_sub_questions(self, topic: str, num_questions: int = 3) -> List[str]:
        """Generate sub-questions for a research topic.
        
        Args:
            topic (str): The research topic
            num_questions (int, optional): Number of questions to generate. Defaults to 3.
            
        Returns:
            List[str]: List of generated sub-questions
        """
        # Get configuration
        writer_provider = get_config_value(self.configurable.writer_provider)
        writer_model_name = get_config_value(self.configurable.writer_model)
        writer_model_kwargs = get_config_value(self.configurable.writer_model_kwargs or {})
        
        # Initialize the model
        writer_model = init_chat_model(
            model=writer_model_name, 
            model_provider=writer_provider, 
            model_kwargs=writer_model_kwargs
        )
        
        # Create prompt for generating sub-questions
        system_prompt = f"""
        You are a research assistant tasked with breaking down a complex topic into specific sub-questions.
        For the topic: "{topic}", generate {num_questions} specific sub-questions that would help explore different aspects of this topic.
        
        The sub-questions should:
        1. Be specific and focused on a single aspect
        2. Be answerable through web search
        3. Cover different aspects of the main topic
        4. Be phrased as direct questions
        
        Format your response as a numbered list of questions only.
        """
        
        # Generate sub-questions
        response = await writer_model.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Generate {num_questions} sub-questions for researching: {topic}")
        ])
        
        # Parse the response to extract questions
        content = response.content
        questions = []
        
        # Simple parsing - extract lines that end with question marks
        for line in content.split('\n'):
            line = line.strip()
            if line and '?' in line:
                # Remove any numbering or bullets
                cleaned_line = line.lstrip('0123456789.- ')
                questions.append(cleaned_line)
        
        # Ensure we have the requested number of questions
        return questions[:num_questions]
    
    async def expand_graph_with_questions(self, questions: List[str]):
        """Expand the research graph with new questions.
        
        Args:
            questions (List[str]): List of questions to add to the graph
        """
        for i, question in enumerate(questions):
            node_name = f"question_{i+1}"
            await self.graph.add_search_node(
                node_name=node_name,
                node_content=question,
                config=self.config
            )
    
    async def generate_final_response(self) -> str:
        """Generate a final response based on all search results.
        
        Returns:
            str: The final research response
        """
        # Get all search results
        all_results = self.graph.get_all_search_results()
        
        # Get configuration
        writer_provider = get_config_value(self.configurable.writer_provider)
        writer_model_name = get_config_value(self.configurable.writer_model)
        writer_model_kwargs = get_config_value(self.configurable.writer_model_kwargs or {})
        
        # Initialize the model
        writer_model = init_chat_model(
            model=writer_model_name, 
            model_provider=writer_provider, 
            model_kwargs=writer_model_kwargs
        )
        
        # Create prompt for generating the final response
        system_prompt = f"""
        You are a research assistant tasked with synthesizing search results into a comprehensive report.
        Based on the search results provided, create a well-structured report that addresses the main topic.
        
        Your report should:
        1. Have a clear introduction that presents the topic
        2. Organize information logically with appropriate headings
        3. Synthesize information from multiple sources
        4. Include a conclusion that summarizes key findings
        5. Use markdown formatting for better readability
        
        The search results are provided in the following format:
        
        {all_results}
        """
        
        # Generate the final response
        response = await writer_model.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content="Generate a comprehensive report based on the search results.")
        ])
        
        # Add the response to the graph
        self.graph.add_response_node(
            node_content=response.content,
            parent_nodes=[node for node in self.graph.nodes if self.graph.nodes[node]["type"] == "search"]
        )
        
        return response.content
    
    def get_visualization_data(self) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
        """Get data for visualizing the research graph.
        
        Returns:
            Tuple: (nodes, edges) in a format suitable for visualization libraries
        """
        return self.graph.to_visualization_data()

