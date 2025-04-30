import asyncio
import os
from open_deep_research import create_enhanced_research_agent, create_conversation_agent
from open_deep_research.configuration import Configuration, ResearchMode
from open_deep_research.enhanced_visualization import save_enhanced_graph_visualization

async def main():
    """Run an enhanced graph-based research example."""
    # Set up configuration
    config = Configuration(
        research_mode=ResearchMode.ENHANCED,
        number_of_queries=3,
        max_search_depth=2,
        reference_tracking_enabled=True,
        conversation_enabled=True,
        enhanced_visualization_path="enhanced_research_graph.html",
        parallel_search_enabled=True,
        max_parallel_searches=3
    )
    
    # Create config dict
    config_dict = {
        "research_mode": "enhanced",
        "number_of_queries": 3,
        "max_search_depth": 2,
        "reference_tracking_enabled": True,
        "conversation_enabled": True,
        "enhanced_visualization_path": "enhanced_research_graph.html",
        "parallel_search_enabled": True,
        "max_parallel_searches": 3
    }
    
    # Add API keys from environment variables if available
    if "TAVILY_API_KEY" in os.environ:
        config_dict["tavily_api_key"] = os.environ["TAVILY_API_KEY"]
    
    # Create enhanced research agent
    agent = create_enhanced_research_agent(config_dict)
    
    # Run the research
    topic = "The impact of artificial intelligence on healthcare"
    
    print(f"Initializing research on topic: {topic}")
    await agent.initialize_with_topic(topic)
    
    print("Generating sub-questions...")
    sub_questions = await agent.generate_sub_questions(topic)
    print(f"Generated {len(sub_questions)} sub-questions:")
    for i, question in enumerate(sub_questions, 1):
        print(f"{i}. {question}")
    
    print("\nExpanding graph with questions...")
    await agent.expand_graph_with_questions(sub_questions)
    
    print("\nGenerating final report...")
    final_report = await agent.generate_final_response()
    
    print("\n\n=== FINAL REPORT ===\n\n")
    print(final_report)
    
    # Save the research graph
    agent.save_research("research_data.json")
    print("\nResearch data saved to: research_data.json")
    
    # Generate visualization
    save_enhanced_graph_visualization(
        agent.graph.nodes,
        agent.graph.adjacency_list,
        agent.graph.references,
        config.enhanced_visualization_path,
        f"Research on: {topic}"
    )
    print(f"\nVisualization saved to: {config.enhanced_visualization_path}")
    
    # Create conversation agent
    print("\nInitializing conversation agent...")
    conversation_agent = create_conversation_agent(
        config_dict,
        agent.graph.references,
        {
            "final_report": final_report,
            "search_results": agent.graph.get_all_search_results()
        }
    )
    
    # Example conversation
    print("\n=== CONVERSATION EXAMPLE ===\n")
    
    questions = [
        "What are the main benefits of AI in healthcare?",
        "Are there any ethical concerns with AI in healthcare?",
        "How is AI being used for medical diagnosis?"
    ]
    
    for question in questions:
        print(f"Question: {question}")
        answer = await conversation_agent.ask(question)
        print(f"Answer: {answer}\n")
    
    # Save the conversation
    conversation_agent.save_to_file("conversation.json")
    print("Conversation saved to: conversation.json")

if __name__ == "__main__":
    asyncio.run(main())

