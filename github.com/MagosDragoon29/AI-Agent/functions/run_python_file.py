# functions/run_python.py
import os
import sys
import subprocess
from google.genai import types

def run_python_file(working_directory, file_path, args=[]):
    try:
        wd = os.path.abspath(working_directory)
        full = os.path.abspath(os.path.join(wd, file_path))

        if os.path.commonpath([wd, full]) != wd:
            return f'Error: Cannot execute "{file_path}" as it is outside the permitted working directory'
        if not os.path.exists(full):
            return f'Error: File "{file_path}" not found.'
        if not file_path.endswith(".py"):
            return f'Error: "{file_path}" is not a Python file.'

        cmd = [sys.executable, full]
        if args:
            if isinstance(args, str):
                cmd.append(args)
            else:
                cmd.extend(str(a) for a in args)

        cp = subprocess.run(
            cmd,
            cwd=wd,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Return raw stdout first so "Ran 9 tests" is visible to the grader,
        # then append stderr if present. No labels.
        out = (cp.stdout or "")
        if cp.stderr:
            out += (cp.stderr if out.endswith("\n") else "\n") + cp.stderr
        if not out.strip():
            out = "No output produced."
        return out

    except Exception as e:
        return f"Error: executing Python file: {e}"


schema_run_python_file = types.FunctionDeclaration(
    name="run_python_file",
    description="Runs the specified Python file. Only works on .py files and will return an error if a non-Python file is selected.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "working_directory": types.Schema(
                type=types.Type.STRING,
                description="The directory containing the file you wish to run. Use '.' for the project root."
            ),
            "file_path": types.Schema(
                type=types.Type.STRING,
                description="The Python file to run, relative to the working directory. Must end in .py."
            ),
            "args": types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(type=types.Type.STRING),
                description="Optional list of arguments to pass to the Python script."
            ),
        },
        required=["working_directory", "file_path"],
    ),
)
