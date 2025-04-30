import json
import os
from typing import Dict, List, Any, Optional

from open_deep_research.enhanced_graph import Reference


def generate_enhanced_graph_html(
    nodes: Dict[str, Dict[str, Any]],
    edges: Dict[str, Any],
    references: Dict[str, Reference],
    title: str = "Enhanced Research Graph"
) -> str:
    """Generate an HTML visualization of the enhanced research graph.
    
    Args:
        nodes (Dict[str, Dict[str, Any]]): Dictionary of graph nodes
        edges (Dict[str, Any]): Dictionary of graph edges
        references (Dict[str, Reference]): Dictionary of references
        title (str, optional): Title for the visualization. Defaults to "Enhanced Research Graph".
        
    Returns:
        str: HTML content for visualizing the graph
    """
    # Convert nodes and edges to the format expected by D3.js
    nodes_list = []
    for node_id, node_data in nodes.items():
        node_type = node_data.get("type", "unknown")
        
        # Get reference titles for this node
        reference_titles = []
        for ref_id in node_data.get("reference_ids", []):
            if ref_id in references:
                reference_titles.append(references[ref_id].title)
        
        node_obj = {
            "id": node_id,
            "label": node_data.get("content", "")[:50] + ("..." if len(node_data.get("content", "")) > 50 else ""),
            "type": node_type,
            "data": node_data,
            "references": reference_titles
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
    
    # Convert references to a list for the visualization
    references_list = []
    for ref_id, ref in references.items():
        references_list.append({
            "id": ref_id,
            "title": ref.title,
            "source": ref.source,
            "authors": ref.authors,
            "date": ref.date,
            "snippet": ref.content_snippet[:100] + ("..." if len(ref.content_snippet) > 100 else ""),
            "relevance": ref.relevance_score
        })
    
    # Create the HTML content with embedded D3.js visualization
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>
        <script src="https://d3js.org/d3.v7.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/lodash@4.17.21/lodash.min.js"></script>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
                background-color: #f5f5f5;
                display: flex;
                flex-direction: column;
                height: 100vh;
            }}
            .header {{
                padding: 10px;
                background-color: #333;
                color: white;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 1.5em;
            }}
            .container {{
                display: flex;
                flex: 1;
                overflow: hidden;
            }}
            #graph-container {{
                flex: 3;
                background-color: white;
                border: 1px solid #ddd;
                overflow: hidden;
            }}
            .sidebar {{
                flex: 1;
                background-color: #f0f0f0;
                border-left: 1px solid #ddd;
                padding: 10px;
                overflow-y: auto;
                display: flex;
                flex-direction: column;
            }}
            .controls {{
                padding: 10px;
                background-color: #f0f0f0;
                border-bottom: 1px solid #ddd;
                display: flex;
                justify-content: space-between;
            }}
            .control-group {{
                display: flex;
                gap: 5px;
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
            .detail-panel {{
                margin-top: 10px;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
                background-color: white;
                flex: 1;
                overflow-y: auto;
            }}
            .detail-panel h3 {{
                margin-top: 0;
                border-bottom: 1px solid #eee;
                padding-bottom: 5px;
            }}
            .reference-item {{
                margin-bottom: 10px;
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 3px;
                background-color: #f9f9f9;
            }}
            .reference-item h4 {{
                margin: 0 0 5px 0;
            }}
            .reference-item p {{
                margin: 5px 0;
                font-size: 0.9em;
            }}
            .search-box {{
                margin: 10px 0;
                padding: 5px;
                width: 100%;
                box-sizing: border-box;
            }}
            .filter-group {{
                margin: 10px 0;
            }}
            .filter-group label {{
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
            }}
            .export-options {{
                margin-top: auto;
                padding-top: 10px;
                border-top: 1px solid #ddd;
            }}
            .tab-container {{
                display: flex;
                border-bottom: 1px solid #ddd;
                margin-bottom: 10px;
            }}
            .tab {{
                padding: 8px 15px;
                cursor: pointer;
                background-color: #f0f0f0;
                border: 1px solid #ddd;
                border-bottom: none;
                margin-right: 5px;
                border-radius: 5px 5px 0 0;
            }}
            .tab.active {{
                background-color: white;
                border-bottom: 1px solid white;
                margin-bottom: -1px;
            }}
            .tab-content {{
                display: none;
            }}
            .tab-content.active {{
                display: block;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{title}</h1>
            <div>
                <input type="text" id="search-input" placeholder="Search nodes..." class="search-box">
                <button id="search-button">Search</button>
            </div>
        </div>
        <div class="controls">
            <div class="control-group">
                <button id="zoom-in">Zoom In</button>
                <button id="zoom-out">Zoom Out</button>
                <button id="reset">Reset</button>
            </div>
            <div class="control-group">
                <button id="toggle-labels">Toggle Labels</button>
                <button id="toggle-sidebar">Toggle Sidebar</button>
            </div>
        </div>
        <div class="container">
            <div id="graph-container"></div>
            <div class="sidebar">
                <div class="tab-container">
                    <div class="tab active" data-tab="details">Node Details</div>
                    <div class="tab" data-tab="references">References</div>
                    <div class="tab" data-tab="filters">Filters</div>
                </div>
                
                <div id="details-tab" class="tab-content active">
                    <div class="detail-panel">
                        <h3>Node Details</h3>
                        <p>Click on a node to view details.</p>
                        <div id="node-details"></div>
                    </div>
                </div>
                
                <div id="references-tab" class="tab-content">
                    <input type="text" id="reference-search" placeholder="Search references..." class="search-box">
                    <div class="detail-panel">
                        <h3>References</h3>
                        <div id="references-list"></div>
                    </div>
                </div>
                
                <div id="filters-tab" class="tab-content">
                    <div class="filter-group">
                        <label>Node Type</label>
                        <div>
                            <input type="checkbox" id="filter-root" checked>
                            <label for="filter-root">Root</label>
                        </div>
                        <div>
                            <input type="checkbox" id="filter-search" checked>
                            <label for="filter-search">Search</label>
                        </div>
                        <div>
                            <input type="checkbox" id="filter-response" checked>
                            <label for="filter-response">Response</label>
                        </div>
                    </div>
                    
                    <div class="filter-group">
                        <label>Edge State</label>
                        <div>
                            <input type="checkbox" id="filter-pending" checked>
                            <label for="filter-pending">Pending</label>
                        </div>
                        <div>
                            <input type="checkbox" id="filter-processing" checked>
                            <label for="filter-processing">Processing</label>
                        </div>
                        <div>
                            <input type="checkbox" id="filter-completed" checked>
                            <label for="filter-completed">Completed</label>
                        </div>
                    </div>
                </div>
                
                <div class="export-options">
                    <button id="export-svg">Export as SVG</button>
                    <button id="export-json">Export as JSON</button>
                    <button id="share-link">Generate Share Link</button>
                </div>
            </div>
        </div>
        <div id="tooltip" class="tooltip" style="display: none;"></div>
        
        <script>
            // Graph data
            const graphData = {
                nodes: ${json.dumps(nodes_list)},
                links: ${json.dumps(links_list)},
                references: ${json.dumps(references_list)}
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
                .on('mouseout', hideTooltip)
                .on('click', showNodeDetails);
            
            // Add labels to the nodes
            const labels = node.append('text')
                .attr('dx', 15)
                .attr('dy', 4)
                .text(d => d.label);
            
            // Set up the tooltip
            const tooltip = d3.select('#tooltip');
            
            function showTooltip(event, d) {
                const content = d.data.content;
                const response = d.data.response || '';
                const references = d.references || [];
                
                let tooltipContent = `<strong>Type:</strong> \${d.type}<br>`;
                tooltipContent += `<strong>Content:</strong> \${content}<br>`;
                
                if (response) {
                    tooltipContent += `<strong>Response:</strong> \${response.substring(0, 150)}...<br>`;
                }
                
                if (references.length > 0) {
                    tooltipContent += `<strong>References:</strong> \${references.join(', ')}`;
                }
                
                tooltip.html(tooltipContent)
                    .style('left', (event.pageX + 10) + 'px')
                    .style('top', (event.pageY + 10) + 'px')
                    .style('display', 'block');
            }
            
            function hideTooltip() {
                tooltip.style('display', 'none');
            }
            
            function showNodeDetails(event, d) {
                // Clear previous details
                const detailsPanel = document.getElementById('node-details');
                detailsPanel.innerHTML = '';
                
                // Create details HTML
                let detailsHTML = `<h4>\${d.type.charAt(0).toUpperCase() + d.type.slice(1)} Node</h4>`;
                detailsHTML += `<p><strong>Content:</strong> \${d.data.content}</p>`;
                
                if (d.data.response) {
                    detailsHTML += `<p><strong>Response:</strong> \${d.data.response}</p>`;
                }
                
                if (d.references && d.references.length > 0) {
                    detailsHTML += `<p><strong>References:</strong></p><ul>`;
                    d.references.forEach(ref => {
                        detailsHTML += `<li>\${ref}</li>`;
                    });
                    detailsHTML += `</ul>`;
                }
                
                // Add details to panel
                detailsPanel.innerHTML = detailsHTML;
                
                // Switch to details tab
                activateTab('details');
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
            
            // Toggle labels
            let labelsVisible = true;
            document.getElementById('toggle-labels').addEventListener('click', () => {
                labelsVisible = !labelsVisible;
                labels.style('display', labelsVisible ? 'block' : 'none');
            });
            
            // Toggle sidebar
            document.getElementById('toggle-sidebar').addEventListener('click', () => {
                const sidebar = document.querySelector('.sidebar');
                const currentDisplay = window.getComputedStyle(sidebar).display;
                sidebar.style.display = currentDisplay === 'none' ? 'flex' : 'none';
            });
            
            // Tab functionality
            function activateTab(tabName) {
                // Deactivate all tabs
                document.querySelectorAll('.tab').forEach(tab => {
                    tab.classList.remove('active');
                });
                document.querySelectorAll('.tab-content').forEach(content => {
                    content.classList.remove('active');
                });
                
                // Activate selected tab
                document.querySelector(`.tab[data-tab="\${tabName}"]`).classList.add('active');
                document.getElementById(`\${tabName}-tab`).classList.add('active');
            }
            
            document.querySelectorAll('.tab').forEach(tab => {
                tab.addEventListener('click', () => {
                    activateTab(tab.getAttribute('data-tab'));
                });
            });
            
            // Populate references tab
            function populateReferences(filter = '') {
                const referencesList = document.getElementById('references-list');
                referencesList.innerHTML = '';
                
                const filteredReferences = graphData.references.filter(ref => 
                    filter === '' || 
                    ref.title.toLowerCase().includes(filter.toLowerCase()) ||
                    ref.source.toLowerCase().includes(filter.toLowerCase()) ||
                    ref.snippet.toLowerCase().includes(filter.toLowerCase())
                );
                
                if (filteredReferences.length === 0) {
                    referencesList.innerHTML = '<p>No references found.</p>';
                    return;
                }
                
                filteredReferences.forEach(ref => {
                    const refElement = document.createElement('div');
                    refElement.className = 'reference-item';
                    
                    let refHTML = `<h4>\${ref.title}</h4>`;
                    refHTML += `<p><strong>Source:</strong> <a href="\${ref.source}" target="_blank">\${ref.source}</a></p>`;
                    
                    if (ref.authors && ref.authors.length > 0) {
                        refHTML += `<p><strong>Authors:</strong> \${ref.authors.join(', ')}</p>`;
                    }
                    
                    if (ref.date) {
                        refHTML += `<p><strong>Date:</strong> \${ref.date}</p>`;
                    }
                    
                    refHTML += `<p><strong>Snippet:</strong> \${ref.snippet}</p>`;
                    refHTML += `<p><strong>Relevance:</strong> \${ref.relevance.toFixed(2)}</p>`;
                    
                    refElement.innerHTML = refHTML;
                    referencesList.appendChild(refElement);
                });
            }
            
            // Initialize references
            populateReferences();
            
            // Reference search
            document.getElementById('reference-search').addEventListener('input', (event) => {
                populateReferences(event.target.value);
            });
            
            // Node search
            document.getElementById('search-button').addEventListener('click', () => {
                const searchTerm = document.getElementById('search-input').value.toLowerCase();
                if (!searchTerm) return;
                
                // Find matching nodes
                const matchingNodes = graphData.nodes.filter(n => 
                    n.label.toLowerCase().includes(searchTerm) || 
                    (n.data.content && n.data.content.toLowerCase().includes(searchTerm)) ||
                    (n.data.response && n.data.response.toLowerCase().includes(searchTerm))
                );
                
                if (matchingNodes.length > 0) {
                    // Highlight the first matching node
                    const matchNode = matchingNodes[0];
                    
                    // Center the view on the node
                    const transform = d3.zoomIdentity
                        .translate(width/2, height/2)
                        .scale(1.5)
                        .translate(-matchNode.x, -matchNode.y);
                    
                    svg.transition().duration(750).call(zoom.transform, transform);
                    
                    // Show node details
                    showNodeDetails(null, matchNode);
                }
            });
            
            // Node type filtering
            function updateNodeVisibility() {
                const showRoot = document.getElementById('filter-root').checked;
                const showSearch = document.getElementById('filter-search').checked;
                const showResponse = document.getElementById('filter-response').checked;
                
                node.style('display', d => {
                    if (d.type === 'root' && !showRoot) return 'none';
                    if (d.type === 'search' && !showSearch) return 'none';
                    if (d.type === 'response' && !showResponse) return 'none';
                    return null;
                });
                
                // Update links based on connected nodes visibility
                link.style('display', d => {
                    const sourceNode = graphData.nodes.find(n => n.id === d.source.id);
                    const targetNode = graphData.nodes.find(n => n.id === d.target.id);
                    
                    if (sourceNode.type === 'root' && !showRoot) return 'none';
                    if (sourceNode.type === 'search' && !showSearch) return 'none';
                    if (sourceNode.type === 'response' && !showResponse) return 'none';
                    
                    if (targetNode.type === 'root' && !showRoot) return 'none';
                    if (targetNode.type === 'search' && !showSearch) return 'none';
                    if (targetNode.type === 'response' && !showResponse) return 'none';
                    
                    return null;
                });
            }
            
            // Edge state filtering
            function updateEdgeVisibility() {
                const showPending = document.getElementById('filter-pending').checked;
                const showProcessing = document.getElementById('filter-processing').checked;
                const showCompleted = document.getElementById('filter-completed').checked;
                
                link.style('display', d => {
                    if (d.state === 1 && !showPending) return 'none';
                    if (d.state === 2 && !showProcessing) return 'none';
                    if (d.state === 3 && !showCompleted) return 'none';
                    return null;
                });
            }
            
            // Set up filter event listeners
            document.getElementById('filter-root').addEventListener('change', updateNodeVisibility);
            document.getElementById('filter-search').addEventListener('change', updateNodeVisibility);
            document.getElementById('filter-response').addEventListener('change', updateNodeVisibility);
            
            document.getElementById('filter-pending').addEventListener('change', updateEdgeVisibility);
            document.getElementById('filter-processing').addEventListener('change', updateEdgeVisibility);
            document.getElementById('filter-completed').addEventListener('change', updateEdgeVisibility);
            
            // Export as SVG
            document.getElementById('export-svg').addEventListener('click', () => {
                const svgData = new XMLSerializer().serializeToString(svg.node());
                const svgBlob = new Blob([svgData], {type: 'image/svg+xml;charset=utf-8'});
                const svgUrl = URL.createObjectURL(svgBlob);
                
                const downloadLink = document.createElement('a');
                downloadLink.href = svgUrl;
                downloadLink.download = 'research_graph.svg';
                document.body.appendChild(downloadLink);
                downloadLink.click();
                document.body.removeChild(downloadLink);
            });
            
            // Export as JSON
            document.getElementById('export-json').addEventListener('click', () => {
                const jsonData = JSON.stringify(graphData, null, 2);
                const jsonBlob = new Blob([jsonData], {type: 'application/json'});
                const jsonUrl = URL.createObjectURL(jsonBlob);
                
                const downloadLink = document.createElement('a');
                downloadLink.href = jsonUrl;
                downloadLink.download = 'research_graph.json';
                document.body.appendChild(downloadLink);
                downloadLink.click();
                document.body.removeChild(downloadLink);
            });
            
            // Generate share link
            document.getElementById('share-link').addEventListener('click', () => {
                // In a real implementation, this would generate a shareable link
                alert('In a production environment, this would generate a shareable link to this visualization.');
            });
        </script>
    </body>
    </html>
    """
    
    return html_content


def save_enhanced_graph_visualization(
    nodes: Dict[str, Dict[str, Any]],
    edges: Dict[str, Any],
    references: Dict[str, Reference],
    output_path: str,
    title: str = "Enhanced Research Graph"
):
    """Save the enhanced graph visualization to an HTML file.
    
    Args:
        nodes (Dict[str, Dict[str, Any]]): Dictionary of graph nodes
        edges (Dict[str, Any]): Dictionary of graph edges
        references (Dict[str, Reference]): Dictionary of references
        output_path (str): Path to save the HTML file
        title (str, optional): Title for the visualization. Defaults to "Enhanced Research Graph".
    """
    html_content = generate_enhanced_graph_html(nodes, edges, references, title)
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    # Write the HTML file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

