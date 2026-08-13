import os
import sys
import mimetypes
from flask import Flask, render_template_string, jsonify, request, send_file, abort

# Initialize Flask application
app = Flask(__name__)

# Configure the default target directory to scan
DEFAULT_DIRECTORY = os.path.abspath(os.environ.get("PDF_SCAN_DIR", os.getcwd()))

# Allowed extensions for the scanner
SUPPORTED_EXTENSIONS = {'.pdf'}

# Simple in-memory database to store custom user edits/metadata (notes and tags)
# Key: relative_path, Value: {"tags": "...", "notes": "..."}
DOCUMENT_METADATA_STORE = {}

def scan_pdf_directory(base_dir):
    """
    Scans a given target directory recursively for PDF files.
    Combines file system metadata with custom user annotations from DOCUMENT_METADATA_STORE.
    """
    pdf_files = []
    id_counter = 1
    
    if not os.path.exists(base_dir) or not os.path.isdir(base_dir):
        return pdf_files, "Target directory path does not exist or is invalid."

    try:
        for root, _, files in os.walk(base_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    full_path = os.path.join(root, file)
                    try:
                        file_stat = os.stat(full_path)
                        relative_path = os.path.relpath(full_path, base_dir)
                        
                        # Fetch custom user metadata if it exists
                        meta = DOCUMENT_METADATA_STORE.get(relative_path, {"tags": "", "notes": ""})
                        
                        pdf_files.append({
                            "id": id_counter,
                            "name": file,
                            "relative_path": relative_path,
                            "size_bytes": file_stat.st_size,
                            "size_mb": round(file_stat.st_size / (1024 * 1024), 2),
                            "modified_time": file_stat.st_mtime,
                            "folder": os.path.basename(root) if root != base_dir else "Root",
                            "tags": meta["tags"],
                            "notes": meta["notes"]
                        })
                        id_counter += 1
                    except (OSError, PermissionError):
                        continue
    except Exception as e:
        return pdf_files, str(e)
                    
    pdf_files.sort(key=lambda x: x["modified_time"], reverse=True)
    return pdf_files, None

# --- HTML/CSS/JS Frontend Interface (Tailwind CSS UI) ---
INDEX_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Web Scanner Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
    </style>
</head>
<body class="bg-gray-50 text-gray-900 flex flex-col min-h-screen">

    <!-- Header Navigation Bar -->
    <header class="bg-white border-b border-gray-200 sticky top-0 z-50 shadow-sm">
        <div class="max-w-[90rem] mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <svg class="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                </svg>
                <div>
                    <h1 class="text-lg font-bold text-gray-900 tracking-tight">PDF Web Scanner</h1>
                </div>
            </div>
            <div class="flex items-center space-x-4">
                <button onclick="fetchPDFs()" class="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition shadow-sm focus:outline-none">
                    <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.253 8H18"></path>
                    </svg>
                    Refresh Scan
                </button>
            </div>
        </div>
    </header>

    <!-- Main Grid Content Area -->
    <main class="flex-1 max-w-[90rem] w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col lg:flex-row gap-6">
        
        <!-- Left Column: Settings, Search controls, Filter and Sidebar Stats -->
        <div class="w-full lg:w-72 flex-shrink-0 space-y-6">
            
            <!-- Base Directory Configuration Card -->
            <div class="bg-white p-5 rounded-xl border border-gray-200 shadow-sm space-y-4">
                <h2 class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Scan Settings</h2>
                <div>
                    <label for="directory-input" class="block text-xs font-medium text-gray-500 mb-1">Base Directory Path</label>
                    <div class="flex gap-2">
                        <input type="text" id="directory-input" value="{{ default_dir }}" placeholder="Target path..." class="flex-1 px-3 py-1.5 border border-gray-300 rounded-lg text-xs font-mono focus:ring-2 focus:ring-blue-500 outline-none transition">
                        <button onclick="updateDirectory()" class="px-2.5 py-1.5 bg-gray-800 text-white text-xs font-medium rounded-lg hover:bg-gray-700 transition">Set</button>
                    </div>
                    <p id="directory-status" class="text-xs mt-1 text-gray-400 truncate">Using system target root</p>
                </div>
            </div>

            <!-- Search & Filters -->
            <div class="bg-white p-5 rounded-xl border border-gray-200 shadow-sm space-y-4">
                <h2 class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Search & Filters</h2>
                <div>
                    <label for="search-input" class="block text-xs font-medium text-gray-500 mb-1">Filename Search</label>
                    <input type="text" id="search-input" oninput="filterLibrary()" placeholder="Type to filter..." class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none transition">
                </div>
                <div>
                    <label for="folder-filter" class="block text-xs font-medium text-gray-500 mb-1">Subfolder Filter</label>
                    <select id="folder-filter" onchange="filterLibrary()" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none bg-white transition">
                        <option value="ALL">All Directories</option>
                    </select>
                </div>
            </div>

            <!-- Summary Operational Cards -->
            <div class="bg-white p-5 rounded-xl border border-gray-200 shadow-sm space-y-4">
                <h2 class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Library Summary</h2>
                <div class="grid grid-cols-2 gap-4">
                    <div class="bg-gray-50 p-3 rounded-lg text-center">
                        <span class="block text-xl font-bold text-gray-900" id="stat-count">0</span>
                        <span class="text-[10px] uppercase text-gray-400 font-medium">Total PDFs</span>
                    </div>
                    <div class="bg-gray-50 p-3 rounded-lg text-center">
                        <span class="block text-md font-bold text-gray-900 truncate mt-1" id="stat-size">0 MB</span>
                        <span class="text-[10px] uppercase text-gray-400 font-medium">Volume</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Center Column: Main Document Table List -->
        <div class="flex-1 bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden flex flex-col">
            <div class="px-6 py-4 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
                <h3 class="font-semibold text-gray-800">Scanned Documents</h3>
                <span class="text-xs font-medium px-2.5 py-0.5 bg-blue-100 text-blue-800 rounded-full" id="showing-count">Showing 0 documents</span>
            </div>

            <!-- Document List View Container -->
            <div class="flex-1 overflow-y-auto max-h-[calc(100vh-16rem)]">
                <table class="min-w-full divide-y divide-gray-200 text-left text-sm">
                    <thead class="bg-gray-50 text-gray-500 uppercase text-xs tracking-wider">
                        <tr>
                            <th class="px-6 py-3 font-medium">Document Name</th>
                            <th class="px-6 py-3 font-medium hidden sm:table-cell">Subfolder</th>
                            <th class="px-6 py-3 font-medium">Size</th>
                            <th class="px-6 py-3 font-medium text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody id="document-table-body" class="divide-y divide-gray-200 bg-white">
                        <!-- Items rendered via JavaScript -->
                    </tbody>
                </table>
                
                <div id="empty-state" class="hidden text-center py-12 px-4">
                    <svg class="w-12 h-12 text-gray-300 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0a2 2 0 01-2 2H6a2 2 0 01-2-2m16 0V9a2 2 0 00-2-2H6a2 2 0 00-2 2v4.586a1 1 0 01-.293.707l-2.828 2.828a1 1 0 01-.707.293H2"></path>
                    </svg>
                    <p id="empty-state-text" class="text-gray-500 text-sm">No PDF files found matching your active criteria.</p>
                </div>
            </div>
        </div>

        <!-- Right Column: Document Details & Metadata Edit Canvas -->
        <div id="edit-canvas-panel" class="w-full lg:w-80 flex-shrink-0 bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden flex flex-col">
            <div class="px-5 py-4 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
                <h3 class="font-semibold text-gray-800 text-sm tracking-wide">Edit Metadata Canvas</h3>
                <span id="canvas-active-badge" class="text-[10px] font-medium px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full">No Selection</span>
            </div>
            
            <!-- Context Window Body -->
            <div id="canvas-empty-view" class="flex-1 flex flex-col items-center justify-center p-6 text-center text-gray-400">
                <svg class="w-10 h-10 mb-2 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
                </svg>
                <p class="text-xs">Select any document file and click <span class="font-semibold text-gray-600">Edit</span> to manage tags and properties in this canvas workspace.</p>
            </div>

            <div id="canvas-form-view" class="hidden flex-1 flex flex-col p-5 space-y-4 overflow-y-auto">
                <div>
                    <span class="block text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">File Name</span>
                    <p id="canvas-doc-name" class="text-sm font-semibold text-gray-900 break-all"></p>
                </div>

                <div>
                    <span class="block text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">Relative Path</span>
                    <p id="canvas-doc-path" class="text-xs font-mono text-gray-500 bg-gray-50 p-2 rounded border border-gray-100 break-all select-all"></p>
                </div>

                <!-- Custom Interactive Tags Input Box -->
                <div>
                    <label for="canvas-input-tags" class="block text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">Document Tags</label>
                    <input type="text" id="canvas-input-tags" placeholder="e.g. Invoice, Q3, Manual" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none transition">
                </div>

                <!-- Custom Notes Context Workspace -->
                <div class="flex-1 flex flex-col min-h-[120px]">
                    <label for="canvas-input-notes" class="block text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">File Notes / Summaries</label>
                    <textarea id="canvas-input-notes" placeholder="Enter annotations or metadata notes here..." class="w-full flex-1 p-3 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none resize-none transition"></textarea>
                </div>

                <div class="pt-2 border-t border-gray-100 flex items-center justify-between gap-2">
                    <button onclick="saveCanvasChanges()" class="flex-1 px-4 py-2 bg-blue-600 text-white font-medium text-xs rounded-lg hover:bg-blue-700 transition shadow-sm">
                        Save Metadata
                    </button>
                    <button onclick="clearCanvasSelection()" class="px-3 py-2 border border-gray-300 text-gray-600 text-xs rounded-lg hover:bg-gray-50 transition">
                        Cancel
                    </button>
                </div>
            </div>
        </div>
    </main>

    <!-- Interactive PDF Presentation Modal Frame Viewer -->
    <div id="preview-modal" class="fixed inset-0 bg-gray-900 bg-opacity-60 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
        <div class="bg-white rounded-xl shadow-2xl w-full max-w-5xl h-[85vh] flex flex-col overflow-hidden">
            <div class="px-6 py-4 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
                <div class="flex items-center space-x-2">
                    <svg class="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path>
                    </svg>
                    <h3 id="modal-title" class="font-semibold text-gray-800 truncate max-w-xl">Document Viewer</h3>
                </div>
                <button onclick="closePreview()" class="text-gray-400 hover:text-gray-600 transition p-1.5 hover:bg-gray-100 rounded-lg">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
            </div>
            <div class="flex-1 bg-gray-100 relative">
                <iframe id="preview-iframe" class="w-full h-full border-none bg-gray-200" src=""></iframe>
            </div>
        </div>
    </div>

    <script>
        let cachedDocuments = [];
        let currentTargetDir = "{{ default_dir }}";
        let activeCanvasPath = null;

        async function fetchPDFs() {
            const statusLabel = document.getElementById('directory-status');
            const emptyStateText = document.getElementById('empty-state-text');
            const tableBody = document.getElementById('document-table-body');
            
            try {
                const response = await fetch(`/api/documents?dir=${encodeURIComponent(currentTargetDir)}`);
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || "Failed to scan target path directory.");
                }
                
                statusLabel.textContent = "Active path validated";
                statusLabel.className = "text-xs mt-1 text-green-600 font-medium";
                
                cachedDocuments = data.files || [];
                populateFilters();
                filterLibrary();
                updateSystemStats();
                
                // If editing an item that got refreshed, reload its properties
                if (activeCanvasPath) {
                    const activeItem = cachedDocuments.find(d => d.relative_path === activeCanvasPath);
                    if (activeItem) {
                        openEditCanvas(activeItem.relative_path);
                    } else {
                        clearCanvasSelection();
                    }
                }
            } catch (err) {
                console.error("Scanning synchronization failure:", err);
                statusLabel.textContent = "Directory error / not found";
                statusLabel.className = "text-xs mt-1 text-red-600 font-medium";
                
                cachedDocuments = [];
                tableBody.innerHTML = '';
                document.getElementById('showing-count').textContent = 'Showing 0 documents';
                emptyStateText.textContent = err.message;
                document.getElementById('empty-state').classList.remove('hidden');
                updateSystemStats();
                clearCanvasSelection();
            }
        }

        function updateDirectory() {
            const newDir = document.getElementById('directory-input').value.trim();
            if (newDir) {
                currentTargetDir = newDir;
                fetchPDFs();
            }
        }

        function populateFilters() {
            const folderFilterSelect = document.getElementById('folder-filter');
            const uniqueFolders = new Set();
            
            cachedDocuments.forEach(doc => {
                if (doc.folder) uniqueFolders.add(doc.folder);
            });

            folderFilterSelect.innerHTML = '<option value="ALL">All Directories</option>';
            Array.from(uniqueFolders).sort().forEach(folderName => {
                const opt = document.createElement('option');
                opt.value = folderName;
                opt.textContent = folderName;
                folderFilterSelect.appendChild(opt);
            });
        }

        function updateSystemStats() {
            document.getElementById('stat-count').textContent = cachedDocuments.length;
            const totalSize = cachedDocuments.reduce((sum, item) => sum + item.size_mb, 0);
            document.getElementById('stat-size').textContent = totalSize.toFixed(2) + " MB";
        }

        function filterLibrary() {
            const query = document.getElementById('search-input').value.toLowerCase().trim();
            const chosenFolder = document.getElementById('folder-filter').value;
            const tableBody = document.getElementById('document-table-body');
            const emptyState = document.getElementById('empty-state');
            const emptyStateText = document.getElementById('empty-state-text');

            const subset = cachedDocuments.filter(doc => {
                const textPool = `${doc.name} ${doc.relative_path} ${doc.tags} ${doc.notes}`.toLowerCase();
                const matchesQuery = textPool.includes(query);
                const matchesFolder = (chosenFolder === 'ALL' || doc.folder === chosenFolder);
                return matchesQuery && matchesFolder;
            });

            document.getElementById('showing-count').textContent = `Showing ${subset.length} documents`;
            tableBody.innerHTML = '';

            if (subset.length === 0) {
                emptyStateText.textContent = "No PDF files found matching your active criteria.";
                emptyState.classList.remove('hidden');
                return;
            }
            emptyState.classList.add('hidden');

            subset.forEach(doc => {
                const row = document.createElement('tr');
                row.className = `hover:bg-gray-50 transition ${activeCanvasPath === doc.relative_path ? 'bg-blue-50/70 hover:bg-blue-50' : ''}`;
                row.innerHTML = `
                    <td class="px-6 py-4 max-w-xs md:max-w-md truncate">
                        <div class="font-medium text-gray-900 truncate flex items-center gap-1.5" title="${doc.name}">
                            ${doc.name}
                            ${doc.tags ? `<span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-100 text-blue-700 max-w-[80px] truncate">${doc.tags}</span>` : ''}
                        </div>
                        <div class="text-xs text-gray-400 font-mono truncate" title="${doc.relative_path}">${doc.relative_path}</div>
                    </td>
                    <td class="px-6 py-4 hidden sm:table-cell text-gray-500 whitespace-nowrap">
                        <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                            ${doc.folder}
                        </span>
                    </td>
                    <td class="px-6 py-4 text-gray-500 whitespace-nowrap">${doc.size_mb} MB</td>
                    <td class="px-6 py-4 text-right space-x-1 whitespace-nowrap">
                        <button onclick="launchPreview('${encodeURIComponent(doc.relative_path)}')" class="text-blue-600 hover:text-blue-900 text-xs font-semibold px-2 py-1.5 rounded-md hover:bg-blue-50 transition">
                            View
                        </button>
                        <button onclick="openEditCanvas('${encodeURIComponent(doc.relative_path)}')" class="text-amber-600 hover:text-amber-900 text-xs font-semibold px-2 py-1.5 rounded-md hover:bg-amber-50 transition">
                            Edit
                        </button>
                        <a href="/api/view?dir=${encodeURIComponent(currentTargetDir)}&path=${encodeURIComponent(doc.relative_path)}" target="_blank" download class="text-gray-600 hover:text-gray-900 text-xs font-semibold px-2 py-1.5 rounded-md hover:bg-gray-100 transition">
                            Download
                        </a>
                    </td>
                `;
                tableBody.appendChild(row);
            });
        }

        // --- Side Canvas Operation Logic ---
        function openEditCanvas(encodedPath) {
            const decodedPath = decodeURIComponent(encodedPath);
            const doc = cachedDocuments.find(d => d.relative_path === decodedPath);
            if (!doc) return;

            activeCanvasPath = doc.relative_path;

            // UI Elements state adjustments
            document.getElementById('canvas-active-badge').textContent = "Active File";
            document.getElementById('canvas-active-badge').className = "text-[10px] font-medium px-2 py-0.5 bg-amber-100 text-amber-800 rounded-full";
            
            document.getElementById('canvas-doc-name').textContent = doc.name;
            document.getElementById('canvas-doc-path').textContent = doc.relative_path;
            document.getElementById('canvas-input-tags').value = doc.tags || "";
            document.getElementById('canvas-input-notes').value = doc.notes || "";

            document.getElementById('canvas-empty-view').classList.add('hidden');
            document.getElementById('canvas-form-view').classList.remove('hidden');
            
            // Re-render table lists to reflect active highlight selection
            filterLibrary();
        }

        function clearCanvasSelection() {
            activeCanvasPath = null;
            document.getElementById('canvas-active-badge').textContent = "No Selection";
            document.getElementById('canvas-active-badge').className = "text-[10px] font-medium px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full";
            
            document.getElementById('canvas-empty-view').classList.remove('hidden');
            document.getElementById('canvas-form-view').classList.add('hidden');
            filterLibrary();
        }

        async function saveCanvasChanges() {
            if (!activeCanvasPath) return;

            const tagsVal = document.getElementById('canvas-input-tags').value.trim();
            const notesVal = document.getElementById('canvas-input-notes').value.trim();

            try {
                const response = await fetch('/api/metadata/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        relative_path: activeCanvasPath,
                        tags: tagsVal,
                        notes: notesVal
                    })
                });

                if (!response.ok) throw new Error("Metadata save rejection.");
                
                // Trigger refresh scan sync across global frontend cached state matrix
                fetchPDFs();
            } catch (err) {
                console.error("Error committing annotation canvas state data:", err);
                alert("Failed to preserve structural metadata attributes.");
            }
        }

        // --- Standard View Modal Controls ---
        function launchPreview(encodedPath) {
            const decodedPath = decodeURIComponent(encodedPath);
            const fileName = decodedPath.split('/').pop();
            document.getElementById('modal-title').textContent = fileName;
            
            document.getElementById('preview-iframe').src = `/api/view?dir=${encodeURIComponent(currentTargetDir)}&path=${encodedPath}#toolbar=1`;
            document.getElementById('preview-modal').classList.remove('hidden');
        }

        function closePreview() {
            document.getElementById('preview-modal').classList.add('hidden');
            document.getElementById('preview-iframe').src = '';
        }

        window.addEventListener('DOMContentLoaded', fetchPDFs);
    </script>
</body>
</html>
"""

# --- API Endpoint Matrix Configurations ---

@app.route('/')
def route_dashboard_index():
    """Serves the central web application UI container."""
    return render_template_string(INDEX_TEMPLATE, default_dir=DEFAULT_DIRECTORY)

@app.route('/api/documents')
def route_api_get_documents():
    """Exposes structured metadata array of scanned records for a dynamic base directory."""
    target_dir = request.args.get('dir', DEFAULT_DIRECTORY)
    target_dir = os.path.abspath(target_dir)
    
    files, error = scan_pdf_directory(target_dir)
    if error:
        return jsonify({"files": [], "error": error}), 400
        
    return jsonify({"files": files, "error": None})

@app.route('/api/metadata/save', methods=['POST'])
def route_api_save_metadata():
    """Preserves user edit canvas tags and annotations into the database module."""
    data = request.get_json() or {}
    relative_path = data.get('relative_path')
    
    if not relative_path:
        return jsonify({"success": False, "error": "Missing target file validation path"}), 400
        
    DOCUMENT_METADATA_STORE[relative_path] = {
        "tags": data.get('tags', ''),
        "notes": data.get('notes', '')
    }
    return jsonify({"success": True, "error": None})

@app.route('/api/view')
def route_api_serve_pdf():
    """Safely serves isolated PDF binaries within directory bounds constraints."""
    base_dir = request.args.get('dir', DEFAULT_DIRECTORY)
    relative_target_path = request.args.get('path', '')
    
    base_dir = os.path.abspath(base_dir)
    safe_path = os.path.normpath(os.path.join(base_dir, relative_target_path))
    
    if not safe_path.startswith(base_dir):
        abort(403, "Access to requested path resource is restricted.")
        
    if not os.path.exists(safe_path) or os.path.isdir(safe_path):
        abort(404, "Target document resource could not be found.")

    mime_type, _ = mimetypes.guess_type(safe_path)
    if not mime_type or mime_type != 'application/pdf':
        mime_type = 'application/pdf'

    return send_file(safe_path, mimetype=mime_type)

if __name__ == '__main__':
    print(f"[*] Starting Local Web Document Server...")
    print(f"[*] Default Directory Context Path: {DEFAULT_DIRECTORY}")
    print(f"[*] Serving locally at: http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000, debug=True)
