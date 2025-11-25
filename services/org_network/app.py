from flask import Flask, jsonify, request, send_file
from pathlib import Path
import json
import time

app = Flask(__name__, static_folder='.')

GRAPH_FILE = Path("master_graph.json")


@app.route('/')
def index():
    return send_file('index.html')


@app.route('/api/graph', methods=['GET'])
def get_graph():
    """
    Return the full master_graph.json as-is.

    Expected structure:
    {
        "nodes": [...],
        "edges": [...],
        "stats": {
            "total_organizations": int,
            "total_units": int,
            "total_nodes": int,
            "total_edges": int,
            "sectors": [...]
        }
    }
    """
    try:
        if not GRAPH_FILE.exists():
            return jsonify({'error': 'master_graph.json not found'}), 404

        with open(GRAPH_FILE, encoding='utf-8') as f:
            data = json.load(f)

        # Be defensive about keys
        data.setdefault("nodes", [])
        data.setdefault("edges", [])
        data.setdefault("stats", {})

        return jsonify(data)

    except Exception as e:
        print(f"Error loading graph: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/graph', methods=['POST'])
def save_graph():
    """
    Save the entire graph sent from the frontend.

    This overwrites master_graph.json but first creates a timestamped backup.
    """
    data = request.json

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    backup_file = None
    if GRAPH_FILE.exists():
        backup_file = GRAPH_FILE.with_name(f"master_graph_backup_{time.time()}.json")
        GRAPH_FILE.rename(backup_file)

    with open(GRAPH_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return jsonify({
        'status': 'saved',
        'backup': str(backup_file) if backup_file else None
    })


@app.route('/api/node/<node_id>', methods=['PUT'])
def update_node(node_id: str):
    """
    Update a single node by id inside master_graph.json.
    """
    updates = request.json

    if not updates:
        return jsonify({'error': 'No update data provided'}), 400

    if not GRAPH_FILE.exists():
        return jsonify({'error': 'master_graph.json not found'}), 404

    with open(GRAPH_FILE, encoding='utf-8') as f:
        graph = json.load(f)

    nodes = graph.get('nodes', [])
    for node in nodes:
        if node.get('id') == node_id:
            node.update(updates)
            break

    graph['nodes'] = nodes

    with open(GRAPH_FILE, 'w', encoding='utf-8') as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)

    return jsonify({'status': 'updated'})


if __name__ == '__main__':
    # Keep it simple: always debug=True, port=5000 as before
    app.run(debug=True, port=5000)
