import asyncio
import os
from open_deep_research import get_research_graph
from open_deep_research.configuration import Configuration, ResearchMode

async def main():
    """Run a graph-based research example."""
    # Set up configuration
    config = Configuration(
        research_mode=ResearchMode.GRAPH,
        number_of_queries=3,
        max_search_depth=2,
        visualization_enabled=True,
        visualization_path="research_graph.html"
    )
    
    # Get the appropriate research graph
    graph = get_research_graph(config)
    
    # Run the graph with a topic
    topic = "The impact of artificial intelligence on healthcare"
    
    # Create config dict with API keys if needed
    config_dict = {
        "configurable": {
            "research_mode": "graph",
            "number_of_queries": 3,
            "max_search_depth": 2,
            "visualization_enabled": True,
            "visualization_path": "research_graph.html"
        }
    }
    
    # Add API keys from environment variables if available
    if "TAVILY_API_KEY" in os.environ:
        config_dict["tavily_api_key"] = os.environ["TAVILY_API_KEY"]
    
    # Run the graph
    result = await graph.ainvoke({"topic": topic}, config=config_dict)
    
    # Print the final report
    print("\n\n=== FINAL REPORT ===\n\n")
    print(result["final_report"])
    
    # Print path to visualization
    if config.visualization_enabled:
        print(f"\n\nVisualization saved to: {config.visualization_path}")

if __name__ == "__main__":
    asyncio.run(main())

