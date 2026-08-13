import os
import sys
import mimetypes
from flask import Flask, render_template_string, jsonify, request, send_file, abort

# Initialize Flask application
app = Flask(__name__)

# Configure the target directory to scan (Defaults to the current working directory)
TARGET_DIRECTORY = os.path.abspath(os.environ.get("PDF_SCAN_DIR", os.getcwd()))

# Allowed extensions for the scanner
SUPPORTED_EXTENSIONS = {'.pdf'}

def scan_pdf_directory(base_dir):
    """
    Scans the target directory recursively for PDF files and extracts basic file system metadata.
    Returns a list of structured dictionaries containing file details.
    """
    pdf_files = []
    id_counter = 1
    
    if not os.path.exists(base_dir):
        return pdf_files

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
                    # Skip files that cannot be accessed due to permission or system errors
                    continue
                    
    # Sort files by modification time descending by default
    pdf_files.sort(key=lambda x: x["modified_time"], reverse=True)
    return pdf_files

# --- HTML/CSS/JS Frontend Interface (Tailwind CSS UI) ---
INDEX_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Web Scanner Dashboard</title>
    <!-- Approved External Tailwind CSS Resource -->
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Inter', sans-serif;
        }
    </style>
</head>
<body class="bg-gray-50 text-gray-900 flex flex-col min-h-screen">

    <!-- Header Navigation Bar -->
    <header class="bg-white border-b border-gray-200 sticky top-0 z-50 shadow-sm">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <!-- Inline SVG Icon for Brand -->
                <svg class="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                </svg>
                <div>
                    <h1 class="text-lg font-bold text-gray-900 tracking-tight">PDF Web Scanner</h1>
                    <p class="text-xs text-gray-500 truncate max-w-md">Scanning: <span class="font-mono text-gray-700 bg-gray-100 px-1 py-0.5 rounded">{{ target_dir }}</span></p>
                </div>
            </div>
            <div class="flex items-center space-x-4">
                <button onclick="fetchPDFs()" class="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.253 8H18"></path>
                    </svg>
                    Refresh Scan
                </button>
            </div>
        </div>
    </header>

    <!-- Main Content Area -->
    <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col md:flex-row gap-6">
        
        <!-- Left Column: Search controls, Filter and Sidebar Stats -->
        <div class="w-full md:w-80 flex-shrink-0 space-y-6">
            <div class="bg-white p-6 rounded-xl border border-gray-200 shadow-sm space-y-4">
                <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wider">Search & Filters</h2>
                
                <!-- Search Input Field -->
                <div>
                    <label for="search-input" class="block text-xs font-medium text-gray-500 mb-1">Filename Search</label>
                    <div class="relative">
                        <input type="text" id="search-input" oninput="filterLibrary()" placeholder="Type to filter documents..." class="w-full pl-3 pr-10 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition">
                    </div>
                </div>

                <!-- Folder Filter Selection -->
                <div>
                    <label for="folder-filter" class="block text-xs font-medium text-gray-500 mb-1">Subfolder Filter</label>
                    <select id="folder-filter" onchange="filterLibrary()" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none bg-white transition">
                        <option value="ALL">All Directories</option>
                    </select>
                </div>
            </div>

            <!-- Summary Operational Cards -->
            <div class="bg-white p-6 rounded-xl border border-gray-200 shadow-sm space-y-4">
                <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wider">Library Summary</h2>
                <div class="grid grid-cols-2 gap-4">
                    <div class="bg-gray-50 p-4 rounded-lg text-center">
                        <span class="block text-2xl font-bold text-gray-900" id="stat-count">0</span>
                        <span class="text-xs text-gray-500">Total PDFs</span>
                    </div>
                    <div class="bg-gray-50 p-4 rounded-lg text-center">
                        <span class="block text-xl font-bold text-gray-900 truncate" id="stat-size">0 MB</span>
                        <span class="text-xs text-gray-500">Total Volume</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Right Column: Document Grid Table List -->
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
                
                <!-- State Message Box -->
                <div id="empty-state" class="hidden text-center py-12 px-4">
                    <svg class="w-12 h-12 text-gray-300 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0a2 2 0 01-2 2H6a2 2 0 01-2-2m16 0V9a2 2 0 00-2-2H6a2 2 0 00-2 2v4.586a1 1 0 01-.293.707l-2.828 2.828a1 1 0 01-.707.293H2"></path>
                    </svg>
                    <p class="text-gray-500 text-sm">No PDF files found matching your active criteria.</p>
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
                <button onclick="closePreview()" class="text-gray-400 hover:text-gray-600 transition focus:outline-none p-1.5 hover:bg-gray-100 rounded-lg">
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

    <!-- Application Initialization and Logic Client Script -->
    <script>
        let cachedDocuments = [];

        async function fetchPDFs() {
            try {
                const response = await fetch('/api/documents');
                if (!response.ok) throw new Error("Failed to scan directory records.");
                
                cachedDocuments = await response.json();
                populateFilters();
                filterLibrary();
                updateSystemStats();
            } catch (err) {
                console.error("Scanning synchronization failure:", err);
            }
        }

        function populateFilters() {
            const folderFilterSelect = document.getElementById('folder-filter');
            const uniqueFolders = new Set();
            
            cachedDocuments.forEach(doc => {
                if (doc.folder) uniqueFolders.add(doc.folder);
            });

            // Retain the structural "All" initialization option
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

            const subset = cachedDocuments.filter(doc => {
                const matchesQuery = doc.name.toLowerCase().includes(query) || doc.relative_path.toLowerCase().includes(query);
                const matchesFolder = (chosenFolder === 'ALL' || doc.folder === chosenFolder);
                return matchesQuery && matchesFolder;
            });

            document.getElementById('showing-count').textContent = `Showing ${subset.length} documents`;
            tableBody.innerHTML = '';

            if (subset.length === 0) {
                emptyState.classList.remove('hidden');
                return;
            }
            emptyState.classList.add('hidden');

            subset.forEach(doc => {
                const row = document.createElement('tr');
                row.className = "hover:bg-gray-50 transition";
                row.innerHTML = `
                    <td class="px-6 py-4 max-w-xs md:max-w-md truncate">
                        <div class="font-medium text-gray-900 truncate" title="${doc.name}">${doc.name}</div>
                        <div class="text-xs text-gray-400 font-mono truncate" title="${doc.relative_path}">${doc.relative_path}</div>
                    </td>
                    <td class="px-6 py-4 hidden sm:table-cell text-gray-500 whitespace-nowrap">
                        <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                            ${doc.folder}
                        </span>
                    </td>
                    <td class="px-6 py-4 text-gray-500 whitespace-nowrap">${doc.size_mb} MB</td>
                    <td class="px-6 py-4 text-right space-x-2 whitespace-nowrap">
                        <button onclick="launchPreview(${doc.id}, '${encodeURIComponent(doc.relative_path)}')" class="text-blue-600 hover:text-blue-900 text-xs font-semibold px-2.5 py-1.5 rounded-md hover:bg-blue-50 transition">
                            View
                        </button>
                        <a href="/api/view/${encodeURIComponent(doc.relative_path)}" target="_blank" download class="text-gray-600 hover:text-gray-900 text-xs font-semibold px-2.5 py-1.5 rounded-md hover:bg-gray-100 transition">
                            Download
                        </a>
                    </td>
                `;
                tableBody.appendChild(row);
            });
        }

        function launchPreview(id, encodedPath) {
            const decodedPath = decodeURIComponent(encodedPath);
            const fileName = decodedPath.split('/').pop();
            document.getElementById('modal-title').textContent = fileName;
            
            // Reference endpoint stream directly to browser iframe capability
            document.getElementById('preview-iframe').src = `/api/view/${encodedPath}#toolbar=1`;
            document.getElementById('preview-modal').classList.remove('hidden');
        }

        function closePreview() {
            document.getElementById('preview-modal').classList.add('hidden');
            document.getElementById('preview-iframe').src = '';
        }

        // Run direct fetch action mapping standard workspace sequence window loading execution
        window.addEventListener('DOMContentLoaded', fetchPDFs);
    </script>
</body>
</html>
"""

# --- API Endpoint Matrix Configurations ---

@app.route('/')
def route_dashboard_index():
    """Serves the central web application UI container."""
    return render_template_string(INDEX_TEMPLATE, target_dir=TARGET_DIRECTORY)

@app.route('/api/documents')
def route_api_get_documents():
    """Exposes structured metadata array of scanned records."""
    records = scan_pdf_directory(TARGET_DIRECTORY)
    return jsonify(records)

@app.route('/api/view/<path:relative_target_path>')
def route_api_serve_pdf(relative_target_path):
    """
    Safely resolves, maps, and serves individual PDF binary objects 
    ensuring directory traversal constraints remain strictly bounded.
    """
    safe_path = os.path.normpath(os.path.join(TARGET_DIRECTORY, relative_target_path))
    
    # Path security validation: block external relative directory access attempts
    if not safe_path.startswith(TARGET_DIRECTORY):
        abort(403, "Access to requested path resource is restricted.")
        
    if not os.path.exists(safe_path) or os.path.isdir(safe_path):
        abort(404, "Target document resource could not be found.")

    # Determine asset MIME type context dynamically
    mime_type, _ = mimetypes.guess_type(safe_path)
    if not mime_type or mime_type != 'application/pdf':
        mime_type = 'application/pdf'

    return send_file(safe_path, mimetype=mime_type)

if __name__ == '__main__':
    print(f"[*] Starting Local Web Document Server...")
    print(f"[*] Directory Context Path: {TARGET_DIRECTORY}")
    print(f"[*] Serving locally at: http://127.0.0.1:5000")
    
    # Execute application engine locally
    app.run(host='127.0.0.1', port=5000, debug=True)
