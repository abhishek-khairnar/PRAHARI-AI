# Project Rules & Constraints

- **External Infrastructure Lock**:
  - NEVER read, modify, or touch any files inside the `mediamtx/` folder (including `mediamtx.yml`).
  - NEVER read, modify, or touch any files inside the `ffmpeg/` folder.
  - NEVER modify or touch `test.mp4`.
  - These are external infrastructure binaries/tools and are NOT part of the application source code.
- **Application Scope**:
  - Only work within the Python application files (e.g., `main.py`, `rtsp_stream.py`, `requirements.txt`, `templates/`, etc.).
