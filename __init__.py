import importlib
import subprocess
import os
import folder_paths
import sys
sys.stdout.reconfigure(encoding='utf-8')

def get_python_executable(venv_path):
    if sys.platform.startswith('win'):
        return os.path.join(venv_path, 'Scripts', 'python.exe')
    else:
        return os.path.join(venv_path, 'bin', 'python')

node_path = os.path.join(folder_paths.get_folder_paths("custom_nodes")[0], "comfyui-photoshop")
venv_path = os.path.join(node_path, "venv")

if not os.path.exists(node_path):
    print(f"_PS_ Node path does not exist: {node_path}")

if not os.path.exists(venv_path):

    print("_PS_ Installing venv...")
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'virtualenv'], check=True)
    if sys.platform.startswith('win'):
        subprocess.run([sys.executable, '-m', 'virtualenv', venv_path], shell=True, check=True)
    else:
        subprocess.run([sys.executable, '-m', 'venv', venv_path], check=True)
        
        
    python_executable = get_python_executable(venv_path)
    if not os.path.exists(python_executable):
        print(f"_PS_ python_path path does not exist")
    else: 
        print(f"_PS_ python_path Installed Succedfully")
    
    print("_PS_ Installing requirements...")
    requirements_path = os.path.join(node_path, 'requirements.txt')
    subprocess.run([python_executable, '-m', 'pip', 'install', 'Pillow'], check=True)
    subprocess.run([python_executable, '-m', 'pip', 'install', 'asyncio'], check=True)
    subprocess.run([python_executable, '-m', 'pip', 'install', 'websockets'], check=True)
    print("_PS_ Installed successfully")

backend_path = os.path.join(node_path, 'Backend.py')
python_path = get_python_executable(venv_path)

print("_PS_ python_path", python_path)
print("_PS_ backend_path", backend_path)

if not os.path.exists(python_path):
    print(f"_PS_ python_path path does not exist")

if not os.path.exists(backend_path):
    print(f"_PS_ Backend.py path does not exist")


default_directory = os.getcwd()
node_path = os.path.join(folder_paths.get_folder_paths("custom_nodes")[0], "comfyui-photoshop")

print("_PS_ node_path", node_path)

os.chdir(node_path)
subprocess.Popen([python_path, backend_path])
os.chdir(default_directory)


node_list = ["node-Photoshop", "node-Photoshop-noplugin"]
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

for module_name in node_list:
    imported_module = importlib.import_module(".{}".format(module_name), __name__)
    NODE_CLASS_MAPPINGS = {**NODE_CLASS_MAPPINGS, **imported_module.NODE_CLASS_MAPPINGS}
    NODE_DISPLAY_NAME_MAPPINGS = {
        **NODE_DISPLAY_NAME_MAPPINGS,
        **imported_module.NODE_DISPLAY_NAME_MAPPINGS,
    }

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
WEB_DIRECTORY = "js"
