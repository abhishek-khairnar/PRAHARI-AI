import sys
import os
import platform
import subprocess
import json

def test_environment():
    report = []
    report.append("=== PRAHARI-AI ENVIRONMENT AUDIT ===")
    report.append(f"OS: {platform.system()} {platform.release()} ({platform.version()}) - Architecture: {platform.machine()}")
    report.append(f"Python: {sys.version}")

    # Test Python package imports
    packages = [
        ("FastAPI", "fastapi"),
        ("Uvicorn", "uvicorn"),
        ("NumPy", "numpy"),
        ("OpenCV", "cv2"),
        ("PyTorch", "torch"),
        ("Torchvision", "torchvision"),
        ("Ultralytics", "ultralytics"),
        ("HuggingFace Hub", "huggingface_hub"),
        ("EasyOCR", "easyocr"),
        ("Psutil", "psutil"),
        ("Requests", "requests"),
        ("HTTPX", "httpx"),
        ("SQLite3", "sqlite3")
    ]

    import_results = {}
    for name, mod in packages:
        try:
            m = __import__(mod)
            ver = getattr(m, "__version__", "Built-in / Available")
            import_results[name] = {"status": "PASS", "version": str(ver)}
            report.append(f"{name} ({mod}): PASS - version {ver}")
        except Exception as e:
            import_results[name] = {"status": "FAIL", "error": str(e)}
            report.append(f"{name} ({mod}): FAIL - {e}")

    # Test CUDA & GPU
    try:
        import torch
        cuda_avail = torch.cuda.is_available()
        report.append(f"CUDA Available: {cuda_avail}")
        if cuda_avail:
            report.append(f"CUDA Device Count: {torch.cuda.device_count()}")
            report.append(f"CUDA Device Name: {torch.cuda.get_device_name(0)}")
            report.append(f"CUDA Version (PyTorch): {torch.version.cuda}")
            report.append("CUDA: PASS")
        else:
            report.append("CUDA: FAIL / NOT AVAILABLE")
    except Exception as e:
        report.append(f"CUDA check error: {e}")

    # Test Node & NPM
    try:
        node_ver = subprocess.check_output(["node", "-v"], text=True).strip()
        npm_ver = subprocess.check_output(["npm.cmd", "-v"], text=True).strip()
        report.append(f"Node.js: PASS - {node_ver}")
        report.append(f"NPM: PASS - {npm_ver}")
    except Exception as e:
        report.append(f"Node/NPM check error: {e}")

    # Check frontend package.json dependencies
    frontend_pkg_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "package.json")
    if os.path.exists(frontend_pkg_path):
        with open(frontend_pkg_path, "r") as f:
            pkg = json.load(f)
            report.append("Frontend Dependencies:")
            for dep, ver in pkg.get("dependencies", {}).items():
                report.append(f"  - {dep}: {ver}")
            for dep, ver in pkg.get("devDependencies", {}).items():
                report.append(f"  - (dev) {dep}: {ver}")
        report.append("Frontend Packages: PASS")
    else:
        report.append("Frontend Packages: FAIL - package.json not found")

    output_path = os.path.join(os.path.dirname(__file__), "environment.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print(f"Environment report written to {output_path}")

if __name__ == "__main__":
    test_environment()
