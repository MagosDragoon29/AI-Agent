import os
from google import genai
from google.genai import types

def get_files_info(working_directory, directory="."):
    wd = os.path.abspath(working_directory)
    full = os.path.abspath(os.path.join(wd, directory))
    if directory == ".":
        print("Result for current directory:")
    else:
        print(f"Result for '{directory}' directory:")

    # error checks
    if os.path.commonpath([wd, full]) != wd:
        print(f'Error: Cannot list "{directory}" as it is outside the permitted working directory')
        return None
    
    if not os.path.exists(full):
        print(f'Error: Directory "{directory}" does not exist')
        return None
    
    if not os.path.isdir(full):
        print(f'Error: "{directory}" is not a directory')
        return None

    # processing
    files = os.listdir(full) 
    for file in files:
        file_dir = os.path.join(full, file)
        size = os.path.getsize(file_dir)
        dir_query = os.path.isdir(file_dir)
        print(f'- {file}: file_size={size} bytes, is_dir={dir_query}')
    pass

schema_get_files_info = types.FunctionDeclaration(
    name="get_files_info",
    description="Lists files in the specified directory along with their sizes, constrained to the working directory.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "directory": types.Schema(
                type=types.Type.STRING,
                description="The directory to list files from, relative to the working directory. Use '.' for the project root."
            ),
        },
        required=["directory"],
    ),
)