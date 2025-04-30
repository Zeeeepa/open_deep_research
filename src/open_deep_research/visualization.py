import json
import os
from typing import Dict, Any, Optional

def generate_graph_html(nodes: Dict[str, Dict[str, Any]], edges: Dict[str, Any], title: str = "Research Graph") -> str:
    """Generate an HTML visualization of the research graph.
    
    Args:
        nodes (Dict[str, Dict[str, Any]]): Dictionary of graph nodes
        edges (Dict[str, Any]): Dictionary of graph edges
        title (str, optional): Title for the visualization. Defaults to "Research Graph".
        
    Returns:
        str: HTML content for visualizing the graph
    """
    # Convert nodes and edges to the format expected by D3.js
    nodes_list = []
    for node_id, node_data in nodes.items():
        node_type = node_data.get("type", "unknown")
        node_obj = {
            "id": node_id,
            "label": node_data.get("content", "")[:50] + ("..." if len(node_data.get("content", "")) > 50 else ""),
            "type": node_type,
            "data": node_data
        }
        nodes_list.append(node_obj)
    
    links_list = []
    for source, targets in edges.items():
        for target in targets:
            links_list.append({
                "source": source,
                "target": target["name"],
                "id": target["id"],
                "state": target["state"]
            })
    
    # Create the HTML content with embedded D3.js visualization
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>
        <script src="https://d3js.org/d3.v7.min.js"></script>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
                background-color: #f5f5f5;
            }}
            #graph-container {{
                width: 100%;
                height: 800px;
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 5px;
                overflow: hidden;
            }}
            .node {{
                cursor: pointer;
            }}
            .node circle {{
                stroke-width: 2px;
            }}
            .node text {{
                font-size: 12px;
                fill: #333;
            }}
            .link {{
                stroke-width: 2px;
                stroke-opacity: 0.6;
            }}
            .node-root circle {{
                fill: #ff7f0e;
                stroke: #e67300;
            }}
            .node-search circle {{
                fill: #1f77b4;
                stroke: #0e5a8a;
            }}
            .node-response circle {{
                fill: #2ca02c;
                stroke: #1a7a1a;
            }}
            .tooltip {{
                position: absolute;
                background-color: rgba(255, 255, 255, 0.9);
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
                max-width: 300px;
                font-size: 12px;
                pointer-events: none;
                z-index: 10;
            }}
            .controls {{
                padding: 10px;
                background-color: #f0f0f0;
                border-bottom: 1px solid #ddd;
            }}
            button {{
                margin-right: 5px;
                padding: 5px 10px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 3px;
                cursor: pointer;
            }}
            button:hover {{
                background-color: #45a049;
            }}
            .state-1 {{
                stroke: #ff7f0e;
                stroke-dasharray: 5;
            }}
            .state-2 {{
                stroke: #aaa;
            }}
            .state-3 {{
                stroke: #2ca02c;
            }}
        </style>
    </head>
    <body>
        <div class="controls">
            <button id="zoom-in">Zoom In</button>
            <button id="zoom-out">Zoom Out</button>
            <button id="reset">Reset</button>
        </div>
        <div id="graph-container"></div>
        <div id="tooltip" class="tooltip" style="display: none;"></div>
        
        <script>
            // Graph data
            const graphData = {
                nodes: ${json.dumps(nodes_list)},
                links: ${json.dumps(links_list)}
            };
            
            // Set up the SVG container
            const width = document.getElementById('graph-container').clientWidth;
            const height = document.getElementById('graph-container').clientHeight;
            
            const svg = d3.select('#graph-container')
                .append('svg')
                .attr('width', width)
                .attr('height', height);
            
            // Create a group for the graph
            const g = svg.append('g');
            
            // Set up zoom behavior
            const zoom = d3.zoom()
                .scaleExtent([0.1, 4])
                .on('zoom', (event) => {
                    g.attr('transform', event.transform);
                });
            
            svg.call(zoom);
            
            // Set up the simulation
            const simulation = d3.forceSimulation(graphData.nodes)
                .force('link', d3.forceLink(graphData.links).id(d => d.id).distance(150))
                .force('charge', d3.forceManyBody().strength(-500))
                .force('center', d3.forceCenter(width / 2, height / 2))
                .force('collision', d3.forceCollide().radius(80));
            
            // Create the links
            const link = g.append('g')
                .selectAll('line')
                .data(graphData.links)
                .enter()
                .append('line')
                .attr('class', d => `link state-\${d.state}`)
                .attr('stroke-width', 2);
            
            // Create the nodes
            const node = g.append('g')
                .selectAll('.node')
                .data(graphData.nodes)
                .enter()
                .append('g')
                .attr('class', d => `node node-\${d.type}`)
                .call(d3.drag()
                    .on('start', dragstarted)
                    .on('drag', dragged)
                    .on('end', dragended));
            
            // Add circles to the nodes
            node.append('circle')
                .attr('r', d => d.type === 'root' ? 20 : (d.type === 'response' ? 15 : 12))
                .on('mouseover', showTooltip)
                .on('mouseout', hideTooltip);
            
            // Add labels to the nodes
            node.append('text')
                .attr('dx', 15)
                .attr('dy', 4)
                .text(d => d.label);
            
            // Set up the tooltip
            const tooltip = d3.select('#tooltip');
            
            function showTooltip(event, d) {
                const content = d.data.content;
                const response = d.data.response || '';
                
                let tooltipContent = `<strong>Type:</strong> \${d.type}<br>`;
                tooltipContent += `<strong>Content:</strong> \${content}<br>`;
                
                if (response) {
                    tooltipContent += `<strong>Response:</strong> \${response.substring(0, 150)}...`;
                }
                
                tooltip.html(tooltipContent)
                    .style('left', (event.pageX + 10) + 'px')
                    .style('top', (event.pageY + 10) + 'px')
                    .style('display', 'block');
            }
            
            function hideTooltip() {
                tooltip.style('display', 'none');
            }
            
            // Update positions on each tick of the simulation
            simulation.on('tick', () => {
                link
                    .attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);
                
                node.attr('transform', d => `translate(\${d.x}, \${d.y})`);
            });
            
            // Drag functions
            function dragstarted(event, d) {
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            }
            
            function dragged(event, d) {
                d.fx = event.x;
                d.fy = event.y;
            }
            
            function dragended(event, d) {
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            }
            
            // Set up control buttons
            document.getElementById('zoom-in').addEventListener('click', () => {
                svg.transition().call(zoom.scaleBy, 1.5);
            });
            
            document.getElementById('zoom-out').addEventListener('click', () => {
                svg.transition().call(zoom.scaleBy, 0.75);
            });
            
            document.getElementById('reset').addEventListener('click', () => {
                svg.transition().call(zoom.transform, d3.zoomIdentity);
            });
        </script>
    </body>
    </html>
    """
    
    return html_content

def save_graph_visualization(nodes: Dict[str, Dict[str, Any]], edges: Dict[str, Any], 
                            output_path: str, title: str = "Research Graph"):
    """Save the graph visualization to an HTML file.
    
    Args:
        nodes (Dict[str, Dict[str, Any]]): Dictionary of graph nodes
        edges (Dict[str, Any]): Dictionary of graph edges
        output_path (str): Path to save the HTML file
        title (str, optional): Title for the visualization. Defaults to "Research Graph".
    """
    html_content = generate_graph_html(nodes, edges, title)
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    # Write the HTML file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

