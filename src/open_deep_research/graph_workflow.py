from typing import Literal, Dict, Any, List, Optional

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from langgraph.constants import Send
from langgraph.graph import START, END, StateGraph
from langgraph.types import interrupt, Command

from open_deep_research.state import (
    ReportStateInput,
    ReportStateOutput,
    ReportState,
)
from open_deep_research.configuration import Configuration
from open_deep_research.utils import get_config_value
from open_deep_research.research_graph import GraphResearchAgent
from open_deep_research.visualization import save_graph_visualization

class GraphResearchState(ReportState):
    """State for the graph-based research workflow."""
    graph_agent: Optional[GraphResearchAgent] = None
    visualization_path: Optional[str] = None
    sub_questions: List[str] = []
    final_report: str = ""

async def initialize_research_graph(state: GraphResearchState, config: RunnableConfig):
    """Initialize the research graph with the main topic.
    
    Args:
        state: Current graph state containing the report topic
        config: Configuration for models, search APIs, etc.
        
    Returns:
        Dict containing the initialized graph agent
    """
    # Get the topic
    topic = state["topic"]
    
    # Initialize the graph agent
    graph_agent = GraphResearchAgent(config)
    await graph_agent.initialize_with_topic(topic)
    
    return {"graph_agent": graph_agent}

async def generate_sub_questions(state: GraphResearchState, config: RunnableConfig):
    """Generate sub-questions for the research topic.
    
    Args:
        state: Current graph state with the graph agent
        config: Configuration for models, search APIs, etc.
        
    Returns:
        Dict containing the generated sub-questions
    """
    # Get the topic and graph agent
    topic = state["topic"]
    graph_agent = state["graph_agent"]
    
    # Get configuration
    configurable = Configuration.from_runnable_config(config)
    num_questions = configurable.number_of_queries
    
    # Generate sub-questions
    sub_questions = await graph_agent.generate_sub_questions(topic, num_questions)
    
    return {"sub_questions": sub_questions}

def human_feedback_on_questions(state: GraphResearchState, config: RunnableConfig) -> Command[Literal["expand_graph_with_questions", "generate_sub_questions"]]:
    """Get human feedback on the generated sub-questions.
    
    Args:
        state: Current graph state with sub-questions
        config: Configuration for the workflow
        
    Returns:
        Command to either proceed with the questions or regenerate them
    """
    # Get the sub-questions
    sub_questions = state["sub_questions"]
    
    # Format the questions for display
    questions_str = "\n".join([f"{i+1}. {q}" for i, q in enumerate(sub_questions)])
    
    # Get feedback on the questions from interrupt
    interrupt_message = f"""Please review the following research sub-questions:
    
{questions_str}

Do these questions cover the important aspects of the topic?
Pass 'true' to approve the questions.
Or, provide feedback to regenerate the questions:"""
    
    feedback = interrupt(interrupt_message)
    
    # If the user approves the questions, proceed with expanding the graph
    if isinstance(feedback, bool) and feedback is True:
        return Command(goto="expand_graph_with_questions")
    
    # If the user provides feedback, regenerate the questions
    elif isinstance(feedback, str):
        return Command(goto="generate_sub_questions", 
                      update={"feedback_on_questions": feedback})
    else:
        raise TypeError(f"Interrupt value of type {type(feedback)} is not supported.")

async def expand_graph_with_questions(state: GraphResearchState, config: RunnableConfig):
    """Expand the research graph with the approved sub-questions.
    
    Args:
        state: Current graph state with sub-questions and graph agent
        config: Configuration for models, search APIs, etc.
        
    Returns:
        Dict containing the updated graph agent
    """
    # Get the graph agent and sub-questions
    graph_agent = state["graph_agent"]
    sub_questions = state["sub_questions"]
    
    # Expand the graph with the questions
    await graph_agent.expand_graph_with_questions(sub_questions)
    
    # Generate visualization
    nodes, edges = graph_agent.get_visualization_data()
    visualization_path = "research_graph.html"
    save_graph_visualization(nodes, edges, visualization_path, "Research Graph")
    
    return {"graph_agent": graph_agent, "visualization_path": visualization_path}

async def generate_final_response(state: GraphResearchState, config: RunnableConfig):
    """Generate the final research response based on all search results.
    
    Args:
        state: Current graph state with the expanded graph
        config: Configuration for models, search APIs, etc.
        
    Returns:
        Dict containing the final report
    """
    # Get the graph agent
    graph_agent = state["graph_agent"]
    
    # Generate the final response
    final_report = await graph_agent.generate_final_response()
    
    # Update visualization with the final response
    nodes, edges = graph_agent.get_visualization_data()
    visualization_path = state.get("visualization_path", "research_graph.html")
    save_graph_visualization(nodes, edges, visualization_path, "Research Graph")
    
    return {"final_report": final_report}

def human_feedback_on_report(state: GraphResearchState, config: RunnableConfig) -> Command[Literal["generate_final_response", END]]:
    """Get human feedback on the final report.
    
    Args:
        state: Current graph state with the final report
        config: Configuration for the workflow
        
    Returns:
        Command to either regenerate the report or end the workflow
    """
    # Get the final report
    final_report = state["final_report"]
    
    # Get feedback on the report from interrupt
    interrupt_message = f"""Please review the final research report:
    
{final_report[:500]}...

Is this report satisfactory?
Pass 'true' to approve the report.
Or, provide feedback to regenerate the report:"""
    
    feedback = interrupt(interrupt_message)
    
    # If the user approves the report, end the workflow
    if isinstance(feedback, bool) and feedback is True:
        return Command(goto=END)
    
    # If the user provides feedback, regenerate the report
    elif isinstance(feedback, str):
        return Command(goto="generate_final_response", 
                      update={"feedback_on_report": feedback})
    else:
        raise TypeError(f"Interrupt value of type {type(feedback)} is not supported.")

# Build the graph-based research workflow
graph_research_builder = StateGraph(GraphResearchState, input=ReportStateInput, output=ReportStateOutput, config_schema=Configuration)

# Add nodes
graph_research_builder.add_node("initialize_research_graph", initialize_research_graph)
graph_research_builder.add_node("generate_sub_questions", generate_sub_questions)
graph_research_builder.add_node("human_feedback_on_questions", human_feedback_on_questions)
graph_research_builder.add_node("expand_graph_with_questions", expand_graph_with_questions)
graph_research_builder.add_node("generate_final_response", generate_final_response)
graph_research_builder.add_node("human_feedback_on_report", human_feedback_on_report)

# Add edges
graph_research_builder.add_edge(START, "initialize_research_graph")
graph_research_builder.add_edge("initialize_research_graph", "generate_sub_questions")
graph_research_builder.add_edge("generate_sub_questions", "human_feedback_on_questions")
graph_research_builder.add_edge("expand_graph_with_questions", "generate_final_response")
graph_research_builder.add_edge("generate_final_response", "human_feedback_on_report")

# Compile the graph
graph = graph_research_builder.compile()

