import os
import json
import urllib.parse
from flask import Flask, render_template_string, jsonify, request, send_from_directory, abort

app = Flask(__name__)

# Global application state tracking local directory and the generated file dictionary
APPLICATION_STATE = {
    "target_directory": "",
    "pdf_library_dict": {}
}

# Integrated frontend user interface template with responsive grid cards and client-side PDF.js worker rendering
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Web PDF Library Viewer with Thumbnails</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
</head>
<body class="bg-gray-100 text-gray-800 font-sans min-h-screen">

    <!-- Header Navigation Section -->
    <header class="bg-slate-900 text-white shadow-md p-4">
        <div class="container mx-auto flex justify-between items-center">
            <h1 class="text-xl font-bold tracking-tight">📁 Local PDF Library Visual Scanner</h1>
            <span class="text-xs bg-blue-600 px-3 py-1 rounded text-white font-medium">PDF.js Thumbnail Mode</span>
        </div>
    </header>

    <main class="container mx-auto p-4 max-w-7xl">
        
        <!-- Target Folder Path Input and Actions Control Panel -->
        <section class="bg-white rounded-lg shadow p-6 mb-6">
            <h2 class="text-lg font-semibold mb-3 text-slate-700">Configure Local Storage Target</h2>
            <div class="flex flex-col sm:flex-row gap-3">
                <input type="text" id="dirPathInput" 
                       class="flex-1 border border-gray-300 rounded px-3 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" 
                       placeholder="Provide an absolute file directory string (e.g., E:\\MyPDFs or C:\\Users\\Name\\Documents)"
                       value="{{ current_path }}">
                
                <div class="flex gap-2">
                    <button onclick="initializeLibrary()" class="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded font-medium transition shadow-sm">
                        Set & Scan
                    </button>
                    <button onclick="triggerRescan()" id="rescanBtn" 
                            class="bg-emerald-600 hover:bg-emerald-700 text-white px-5 py-2 rounded font-medium transition shadow-sm {% if not current_path %}opacity-50 cursor-not-allowed{% endif %}"
                            {% if not current_path %}disabled{% endif %}>
                        🔄 Re-Scan
                    </button>
                </div>
            </div>
            <p id="statusMsg" class="mt-3 text-sm text-slate-500 italic">
                {% if current_path %}Monitoring active path structures: {{ current_path }}{% else %}Ready for indexing configurations.{% endif %}
            </p>
        </section>

        <!-- Dynamic Grid Content Split Layout -->
        <div class="grid grid-cols-1 lg:grid-cols-5 gap-6">
            
            <!-- Left Grid Panel: Interactive Library Grid Folders -->
            <section class="lg:col-span-3 bg-white rounded-lg shadow p-6">
                <div class="mb-4 border-b pb-2 flex justify-between items-center">
                    <h2 class="text-lg font-semibold text-slate-700">Library Folders</h2>
                    <span class="text-xs text-slate-400">💡 Click any preview card to open the file</span>
                </div>
                <div id="treeContainer" class="space-y-4 overflow-y-auto max-h-[650px] pr-2">
                    <p class="text-gray-400 italic text-sm">Provide valid targeting addresses above to build visual workspace indexes.</p>
                </div>
            </section>
            
            <!-- Right Grid Panel: Raw Metadata Live Dictionary Output -->
            <section class="lg:col-span-2 bg-white rounded-lg shadow p-6">
                <h2 class="text-lg font-semibold mb-4 text-slate-700 border-b pb-2">Structured Dictionary Representation</h2>
                <div class="relative">
                    <pre id="jsonViewer" class="bg-slate-900 text-emerald-400 p-4 rounded text-xs font-mono overflow-auto max-h-[650px] min-h-[200px]">{}</pre>
                </div>
            </section>
            
        </div>
    </main>

    <!-- Browser Runtime Scripts Layer -->
    <script>
        // Attach secure background worker thread link for the PDF library
        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

        document.addEventListener("DOMContentLoaded", () => {
            fetchLibraryData();
        });

        async function fetchLibraryData() {
            try {
                const response = await fetch('/api/library');
                const data = await response.json();
                
                if (data.target_directory) {
                    updateTreeDOM(data.pdf_library_dict);
                    document.getElementById('jsonViewer').textContent = JSON.stringify(data.pdf_library_dict, null, 4);
                    document.getElementById('rescanBtn').disabled = false;
                    document.getElementById('rescanBtn').classList.remove('opacity-50', 'cursor-not-allowed');
                }
            } catch (err) {
                console.error("Internal service request failure:", err);
            }
        }

        async function initializeLibrary() {
            const pathValue = document.getElementById('dirPathInput').value.trim();
            if (!pathValue) {
                alert("Please enter a valid directory target path layout.");
                return;
            }
            updateStatus("Mapping specified directories and validating dependencies...", "text-blue-600");
            try {
                const response = await fetch('/api/set-directory', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ directory: pathValue })
                });
                const result = await response.json();
                if (result.success) {
                    updateStatus(`Scan complete. Synced ${result.total_pdfs} PDF files securely. Generating cover previews...`, "text-emerald-600");
                    await fetchLibraryData();
                } else {
                    updateStatus(`Error mapping tracks: ${result.error}`, "text-red-600");
                }
            } catch (err) {
                updateStatus("System synchronization failure timeout.", "text-red-600");
            }
        }

        async function triggerRescan() {
            updateStatus("Analyzing directory paths to reconcile modifications...", "text-blue-600");
            try {
                const response = await fetch('/api/rescan', { method: 'POST' });
                const result = await response.json();
                if (result.success) {
                    updateStatus(`Reconciliation complete. Total files online: ${result.total_pdfs}. Regenerating previews...`, "text-emerald-600");
                    await fetchLibraryData();
                } else {
                    updateStatus(`Re-indexing workflow suspended: ${result.error}`, "text-red-600");
                }
            } catch (err) {
                updateStatus("Communication error while processing hardware scan arrays.", "text-red-600");
            }
        }

        function updateTreeDOM(libraryData) {
            const container = document.getElementById('treeContainer');
            container.innerHTML = '';
            const folders = Object.keys(libraryData);
            if (folders.length === 0) {
                container.innerHTML = '<p class="text-gray-400 italic text-sm">No documents found matching scanning requirements.</p>';
                return;
            }
            folders.forEach(folder => {
                const folderBox = document.createElement('div');
                folderBox.className = "border border-gray-200 rounded-lg overflow-hidden shadow-sm bg-white";

                const header = document.createElement('div');
                header.className = "bg-slate-100 px-4 py-3 flex justify-between items-center font-semibold text-slate-700 text-sm border-b border-gray-200 cursor-pointer hover:bg-slate-200 transition select-none";
                header.innerHTML = `<span>📁 ${folder}</span><span class="text-xs bg-slate-200 text-slate-600 px-2 py-1 rounded-full font-bold">${libraryData[folder].length} PDFs</span>`;
                
                const gridContainer = document.createElement('div');
                gridContainer.className = "p-4 bg-gray-50 grid grid-cols-2 sm:grid-cols-3 gap-4 transition-all duration-300";
                
                libraryData[folder].forEach((pdfFile, idx) => {
                    const encodedFolder = encodeURIComponent(folder);
                    const encodedFile = encodeURIComponent(pdfFile);
                    const targetUrl = `/view-pdf?folder=${encodedFolder}&file=${encodedFile}`;
                    
                    const card = document.createElement('div');
                    card.className = "bg-white rounded border border-gray-200 shadow-sm hover:shadow-md hover:border-blue-400 transition overflow-hidden flex flex-col justify-between group";
                    const canvasId = `canvas-${folder.replace(/[^a-zA-Z0-9]/g, '-')}-${idx}`;
                    
                    card.innerHTML = `
                        <a href="${targetUrl}" target="_blank" class="flex flex-col h-full">
                            <div class="bg-slate-200 aspect-[3/4] flex items-center justify-center relative overflow-hidden border-b border-gray-100">
                                <canvas id="${canvasId}" class="w-full h-full object-cover hidden"></canvas>
                                <div id="loader-${canvasId}" class="absolute inset-0 flex flex-col items-center justify-center text-slate-400 text-xs gap-2 p-2 text-center animate-pulse">
                                    <span class="text-xl">📄</span>
                                    <span class="text-[10px] truncate w-full">Loading preview...</span>
                                </div>
                            </div>
                            <div class="p-2 bg-white flex-1 flex flex-col justify-between">
                                <p class="text-[11px] font-mono text-slate-700 line-clamp-2 word-break leading-tight font-semibold" title="${pdfFile}">
                                    ${pdfFile}
                                </p>
                                <span class="text-[9px] text-blue-500 font-medium mt-1 self-start group-hover:underline">Open Document ↗</span>
                            </div>
                        </a>
                    `;
                    gridContainer.appendChild(card);
                    renderPDFThumbnail(targetUrl, canvasId);
                });

                header.onclick = () => gridContainer.classList.toggle('hidden');
                folderBox.appendChild(header);
                folderBox.appendChild(gridContainer);
                container.appendChild(folderBox);
            });
        }

        async function renderPDFThumbnail(pdfUrl, canvasId) {
            try {
                const loadingTask = pdfjsLib.getDocument(pdfUrl);
                const pdf = await loadingTask.promise;
                const page = await pdf.getPage(1);
                
                const canvas = document.getElementById(canvasId);
                const loader = document.getElementById(`loader-${canvasId}`);
                if (!canvas) return;
                
                const context = canvas.getContext('2d');
                const viewport = page.getViewport({ scale: 0.4 });
                canvas.height = viewport.height;
                canvas.width = viewport.width;
                
                const renderContext = { canvasContext: context, viewport: viewport };
                await page.render(renderContext).promise;
                
                canvas.classList.remove('hidden');
                if (loader) loader.classList.add('hidden');
            } catch (err) {
                console.error("Thumbnail capture error:", err);
                const loader = document.getElementById(`loader-${canvasId}`);
                if (loader) {
                    loader.innerHTML = '<span class="text-red-400 text-sm">⚠️</span><span class="text-[9px] text-red-400">Preview error</span>';
                    loader.classList.remove('animate-pulse');
                }
            }
        }

        function updateStatus(text, colorClass) {
            const el = document.getElementById('statusMsg');
            el.className = `mt-3 text-sm italic ${colorClass}`;
            el.textContent = text;
        }
    </script>
</body>
</html>
"""

def scan_local_filesystem(target_path):
    """Deep searches the specified path for matching files and builds a structural index map configuration."""
    normalized_path = os.path.normpath(target_path)
    if not os.path.exists(normalized_path) or not os.path.isdir(normalized_path):
        raise ValueError("Target folder path is invalid or cannot be reached by server processes.")

    new_library_dict = {}
    total_pdfs = 0

    for root, dirs, files in os.walk(normalized_path):
        pdf_files = [f for f in files if f.lower().endswith('.pdf')]
        if pdf_files:
            relative_dir = os.path.relpath(root, normalized_path)
            dict_key = "Root Folder" if relative_dir == "." else relative_dir
            new_library_dict[dict_key] = sorted(pdf_files)
            total_pdfs += len(pdf_files)

    return new_library_dict, total_pdfs

@app.route('/')
def index_view():
    """Serves the central layout structure."""
    return render_template_string(HTML_TEMPLATE, current_path=APPLICATION_STATE["target_directory"])

@app.route('/api/library', methods=['GET'])
def get_library_api():
    """Exposes internal database parameters."""
    return jsonify(APPLICATION_STATE)

@app.route('/api/set-directory', methods=['POST'])
def set_directory_api():
    """Switches operational targets dynamically on demand."""
    data = request.get_json() or {}
    directory_input = data.get('directory', '').strip()

    if not directory_input:
        return jsonify({"success": False, "error": "Target configuration paths are missing."}), 400

    try:
        pdf_map, count = scan_local_filesystem(directory_input)
        APPLICATION_STATE["target_directory"] = os.path.normpath(directory_input)
        APPLICATION_STATE["pdf_library_dict"] = pdf_map
        return jsonify({"success": True, "total_pdfs": count})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/rescan', methods=['POST'])
def rescan_api():
    """Forces background reconciliation updates on current paths."""
    current_dir = APPLICATION_STATE["target_directory"]
    if not current_dir:
        return jsonify({"success": False, "error": "No monitored path tracks mapped yet."}), 400

    try:
        pdf_map, count = scan_local_filesystem(current_dir)
        APPLICATION_STATE["pdf_library_dict"] = pdf_map
        return jsonify({"success": True, "total_pdfs": count})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/view-pdf', methods=['GET'])
def view_pdf_handler():
    """Securely authenticates tracking boundaries and streams the requested PDF resource natively."""
    base_root = APPLICATION_STATE["target_directory"]
    if not base_root:
        return abort(400, description="Tracking paths are unconfigured.")

    req_folder = request.args.get('folder', '')
    req_file = request.args.get('file', '')

    if not req_folder or not req_file:
        return abort(400, description="Missing path lookup index elements.")

    if req_folder == "Root Folder":
        target_dir_path = base_root
    else:
        target_dir_path = os.path.normpath(os.path.join(base_root, req_folder))

    if not target_dir_path.startswith(base_root):
        return abort(403, description="Access denied: outside application workspace root context.")

    full_file_path = os.path.join(target_dir_path, req_file)
    if not os.path.exists(full_file_path):
        return abort(404, description="Target asset could not be located on disk array paths.")

    return send_from_directory(
        directory=target_dir_path,
        path=req_file,
        mimetype='application/pdf'
    )

if __name__ == '__main__':
    print("Application Server running. Navigate to http://127.0.0.1:5000 in your web browser.")
    app.run(host='127.0.0.1', port=5000, debug=True)
