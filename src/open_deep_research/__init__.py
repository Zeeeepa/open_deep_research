"""Planning, research, and report generation."""

__version__ = "0.0.15"

# Import the graph from the graph.py file
from open_deep_research.graph import graph as linear_graph
from open_deep_research.multi_agent import graph as multi_agent_graph
from open_deep_research.graph_workflow import graph as graph_based_research

from open_deep_research.configuration import Configuration, ResearchMode

def get_research_graph(config: Configuration = None):
    """Get the appropriate research graph based on configuration.
    
    Args:
        config (Configuration, optional): Configuration for the research. Defaults to None.
        
    Returns:
        graph: The compiled research graph
    """
    if not config:
        config = Configuration()
    
    if config.research_mode == ResearchMode.GRAPH:
        return graph_based_research
    elif config.research_mode == ResearchMode.MULTI_AGENT:
        return multi_agent_graph
    else:  # Default to LINEAR mode
        return linear_graph
