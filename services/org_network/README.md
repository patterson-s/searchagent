# Organization Network Visualizer

Interactive network editor for organization ontology.

## Setup

1. Install dependencies:
```
pip install -r requirements.txt
```

2. Run aggregation (if needed):
```
python aggregate_orgs.py
```

3. Start the server:
```
python app.py
```

4. Open browser to: http://localhost:5000

## Features

- Interactive network visualization with Cytoscape.js
- Color-coded by sector (govt, io, ngo, private, academic)
- Node size = number of people who worked there
- Click nodes to edit name, sector, country
- Multiple layout options (force, hierarchy, circle)
- Search and filter by sector
- Save changes back to master_graph.json
- Automatic backups on save

## Controls

- **Layouts**: Switch between force-directed, hierarchical, and circular layouts
- **Search**: Find organizations by name
- **Filters**: Show/hide sectors
- **Edit**: Click node to edit properties
- **Save**: Save individual node or entire graph

## Node Types

- **Employers** (circles with thick border): Top-level organizations
- **Units** (rectangles): Sub-organizations
- **Orange edges**: Parent-child relationships within orgs
- **Gray edges**: Employer contains unit

## Files

- `aggregate_orgs.py`: Build master graph from enriched files
- `inspect_graph.py`: View graph statistics
- `app.py`: Flask server
- `index.html`: Interactive visualizer
- `master_graph.json`: Current graph data
- `master_graph_backup_*.json`: Auto-created on save