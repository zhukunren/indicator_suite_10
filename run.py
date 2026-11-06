"""Start the local workbench and open the browser only once it is ready."""
import argparse
import os
from pathlib import Path
import sys
import subprocess
import threading
import time
import urllib.request
import webbrowser


def open_when_ready(url):
    for _ in range(80):
        try:
            with urllib.request.urlopen(url+'/api/health',timeout=1) as response:
                if response.status==200:
                    webbrowser.open(url)
                    return
        except OSError:
            time.sleep(.25)


if __name__=='__main__':
    project_python=Path(__file__).resolve().parent/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if project_python.is_file() and Path(sys.executable).resolve()!=project_python.resolve():
        raise SystemExit(subprocess.call([str(project_python),str(Path(__file__).resolve()),*sys.argv[1:]]))
    import uvicorn
    parser=argparse.ArgumentParser(description='Dongwu strategy research prototype')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    if not args.no_browser:
        threading.Thread(target=open_when_ready,args=(f'http://127.0.0.1:{args.port}',),daemon=True).start()
    uvicorn.run('backend.app:app',host='127.0.0.1',port=args.port)
