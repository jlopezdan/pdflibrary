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

def scan_pdf_directory(base_dir):
    """
    Scans a given target directory recursively for PDF files.
    Returns a list of structured dictionaries containing file details.
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
                        
                        pdf_files.append({
                            "id": id_counter,
                            "name": file,
                            "relative_path": relative_path,
                            "size_bytes": file_stat.st_size,
                            "size_mb": round(file_stat.st_size / (1024 * 1024), 2),
                            "modified_time": file_stat.st_mtime,
                            "folder": os.path.basename(root) if root != base_dir else "Root"
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
    <!-- Whitelisted Cloudflare resource for secure client-side PDF canvas rendering -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.min.js"></script>
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

    <!-- Main Content Area Container -->
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
                        <span class="text-[10px] text-gray-400 uppercase font-medium">Total PDFs</span>
                    </div>
                    <div class="bg-gray-50 p-3 rounded-lg text-center">
                        <span class="block text-md font-bold text-gray-900 truncate mt-1" id="stat-size">0 MB</span>
                        <span class="text-[10px] text-gray-400 uppercase font-medium">Volume</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Center Column: Document Grid Table List -->
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
                        </tr>
                    </thead>
                    <tbody id="document-table-body" class="divide-y divide-gray-200 bg-white">
                        <!-- Items rendered via JavaScript -->
                    </tbody>
                </table>
                
                <div id="empty-state" class="hidden text-center py-12 px-4">
                    <svg class="w-12 h-12 text-gray-300 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0a2 2 0 01-2-2H6a2 2 0 01-2-2m16 0V9a2 2 0 00-2-2H6a2 2 0 00-2 2v4.586a1 1 0 01-.293.707l-2.828 2.828a1 1 0 01-.707.293H2"></path>
                    </svg>
                    <p id="empty-state-text" class="text-gray-500 text-sm">No PDF files found matching your active criteria.</p>
                </div>
            </div>
        </div>

        <!-- Right Column: First Page Canvas Preview Panel View -->
        <div id="preview-canvas-panel" class="w-full lg:w-80 flex-shrink-0 bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden flex flex-col">
            <div class="px-5 py-4 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
                <h3 class="font-semibold text-gray-800 text-sm tracking-wide">Page Preview</h3>
                <span id="preview-active-badge" class="text-[10px] font-medium px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full">No Selection</span>
            </div>
            
            <!-- Empty Panel Selection State View -->
            <div id="preview-empty-view" class="flex-1 flex flex-col items-center justify-center p-6 text-center text-gray-400">
                <svg class="w-10 h-10 mb-2 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                </svg>
                <p class="text-xs">Click any document entry in the list view to render its first page in this panel.</p>
            </div>

            <!-- Active Document Preview Content Wrapper -->
            <div id="preview-active-view" class="hidden flex-1 flex flex-col p-4 space-y-4 overflow-y-auto">
                <div class="border-b border-gray-100 pb-2">
                    <h4 id="preview-doc-name" class="text-xs font-semibold text-gray-900 truncate"></h4>
                    <p id="preview-doc-folder" class="text-[11px] text-gray-400 truncate mt-0.5"></p>
                </div>
                
                <!-- Target Presentation Canvas Wrapper Frame -->
                <div id="canvas-container" class="bg-gray-50 rounded-lg border border-gray-200 overflow-hidden flex items-center justify-center p-2 min-h-[350px] relative">
                    <div id="preview-loading" class="text-xs text-gray-500 hidden flex flex-col items-center">
                        <svg class="animate-spin h-5 w-5 text-blue-600 mb-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <span>Rendering page 1...</span>
                    </div>
                    <canvas id="preview-page-canvas" class="shadow-sm max-w-full bg-white hidden rounded border border-gray-100"></canvas>
                </div>

                <button id="full-view-btn" class="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium text-xs rounded-lg transition shadow-sm focus:outline-none">
                    Open Full Document Viewer
                </button>
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
        // Configure whitelisted library worker mapping globally
        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.worker.min.js';

        let cachedDocuments = [];
        let currentTargetDir = "{{ default_dir }}";
        let activeRowElement = null;

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
                resetCanvasPreviewPanel();
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
                resetCanvasPreviewPanel();
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
                const matchesQuery = doc.name.toLowerCase().includes(query) || doc.relative_path.toLowerCase().includes(query);
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
                row.className = "hover:bg-gray-50/80 transition cursor-pointer select-none";
                
                // Clicking anywhere on the list element item loads its side canvas preview
                row.onclick = (e) => {
                    if (e.target.closest('button')) return;
                    openDocumentPreview(doc.relative_path, row);
                };

                row.innerHTML = `
                    <td class="px-6 py-4 max-w-xs md:max-w-md flex items-center space-x-3">
                        <button onclick="launchPreview('${encodeURIComponent(doc.relative_path)}')" class="text-red-600 hover:text-red-800 transition focus:outline-none flex-shrink-0" title="Open full viewer modal">
                            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path>
                            </svg>
                        </button>
                        <div class="truncate">
                            <div class="font-medium text-gray-900 truncate" title="${doc.name}">${doc.name}</div>
                            <div class="text-xs text-gray-400 font-mono truncate" title="${doc.relative_path}">${doc.relative_path}</div>
                        </div>
                    </td>
                    <td class="px-6 py-4 hidden sm:table-cell text-gray-500 whitespace-nowrap">
                        <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                            ${doc.folder}
                        </span>
                    </td>
                    <td class="px-6 py-4 text-gray-500 whitespace-nowrap">${doc.size_mb} MB</td>
                `;
                tableBody.appendChild(row);
            });
        }

        // --- Side Panel Canvas Operations ---

        function openDocumentPreview(relative_path, rowEl) {
            const doc = cachedDocuments.find(d => d.relative_path === relative_path);
            if (!doc) return;

            // Update row item selection highlight
            if (activeRowElement) {
                activeRowElement.classList.remove('bg-blue-50/70', 'hover:bg-blue-50');
            }
            activeRowElement = rowEl;
            activeRowElement.classList.add('bg-blue-50/70', 'hover:bg-blue-50');

            // Shift states and assign summary values
            document.getElementById('preview-active-badge').textContent = "Rendering";
            document.getElementById('preview-active-badge').className = "text-[10px] font-medium px-2 py-0.5 bg-blue-100 text-blue-800 rounded-full";
            document.getElementById('preview-doc-name').textContent = doc.name;
            document.getElementById('preview-doc-folder').textContent = `Subfolder: ${doc.folder}`;
            
            document.getElementById('preview-empty-view').classList.add('hidden');
            document.getElementById('preview-active-view').classList.remove('hidden');

            document.getElementById('full-view-btn').onclick = () => {
                launchPreview(encodeURIComponent(doc.relative_path));
            };

            // Stream document link into client-side canvas render thread
            const targetStreamUrl = `/api/view?dir=${encodeURIComponent(currentTargetDir)}&path=${encodeURIComponent(doc.relative_path)}`;
            renderFirstPageCanvas(targetStreamUrl);
        }

        function renderFirstPageCanvas(url) {
            const canvas = document.getElementById('preview-page-canvas');
            const ctx = canvas.getContext('2d');
            const loadingEl = document.getElementById('preview-loading');
            
            loadingEl.classList.remove('hidden');
            canvas.classList.add('hidden');
            
            pdfjsLib.getDocument(url).promise.then(function(pdf) {
                return pdf.getPage(1);
            }).then(function(page) {
                const container = document.getElementById('canvas-container');
                const containerWidth = container.clientWidth - 16; // Account for inner container margins
                
                const viewport = page.getViewport({ scale: 1.0 });
                const scale = containerWidth / viewport.width;
                const scaledViewport = page.getViewport({ scale: scale });

                canvas.height = scaledViewport.height;
                canvas.width = scaledViewport.width;

                const renderContext = {
                    canvasContext: ctx,
                    viewport: scaledViewport
                };
                
                return page.render(renderContext).promise;
            }).then(function() {
                loadingEl.classList.add('hidden');
                canvas.classList.remove('hidden');
                document.getElementById('preview-active-badge').textContent = "Active Preview";
                document.getElementById('preview-active-badge').className = "text-[10px] font-medium px-2 py-0.5 bg-green-100 text-green-800 rounded-full";
            }).catch(function(error) {
                console.error('Error executing rendering pipeline thread:', error);
                loadingEl.innerHTML = '<span class="text-red-500 font-medium">Failed to load preview canvas</span>';
                document.getElementById('preview-active-badge').textContent = "Error";
                document.getElementById('preview-active-badge').className = "text-[10px] font-medium px-2 py-0.5 bg-red-100 text-red-800 rounded-full";
            });
        }

        function resetCanvasPreviewPanel() {
            document.getElementById('preview-empty-view').classList.remove('hidden');
            document.getElementById('preview-active-view').classList.add('hidden');
            document.getElementById('preview-active-badge').textContent = "No Selection";
            document.getElementById('preview-active-badge').className = "text-[10px] font-medium px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full";
            activeRowElement = null;
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

@app.route('/api/view')
def route_api_serve_pdf():
    """
    Safely resolves, maps, and serves individual PDF binary objects 
    relative to the dynamically passed base directory parameter.
    """
    base_dir = request.args.get('dir', DEFAULT_DIRECTORY)
    relative_target_path = request.args.get('path', '')
    
    base_dir = os.path.abspath(base_dir)
    safe_path = os.path.normpath(os.path.join(base_dir, relative_target_path))
    
    # Path security validation: block path traversal outside of the target base folder
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
