import os
import config
from google import genai
from google.genai import types

def get_file_content(working_directory, file_path):
    if file_path == None:
        print("Result for current file:")
    else:
        print(f"Result for '{file_path}")
    
    wd = os.path.abspath(working_directory)
    full = os.path.abspath(os.path.join(wd, file_path))

    # error checks
    if os.path.commonpath([wd, full]) != wd:
        return f'Error: Cannot read "{file_path}" as it is outside the permitted working directory'
    
    #if not os.path.exists(full):
        #print(f'Error: Directory "{file_path}" does not exist')
        #return None
    
    if not os.path.isfile(full) or not os.path.exists(full):
        return f'Error: File not found or is not a regular file: "{file_path}"'
    
    try:
        with open(full, "r") as f:
            contents = f.read()
    except Exception as e:
        return f'Error: {e}'
    
    if len(contents) > config.MAX_CHAR_LIMIT:
        contents = contents[:config.MAX_CHAR_LIMIT]
        contents += f'...File "{file_path}" truncated at {config.MAX_CHAR_LIMIT:,} characters'

    return contents

schema_get_file_content = types.FunctionDeclaration(
    name="get_file_content",
    description="Reads the file and returns the content of the file. May not be a directory.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "working_directory": types.Schema(
                type=types.Type.STRING,
                description="The directory that contains the file to read, relative to the working directory. Use '.' for the project root."
            ),
            "file_path": types.Schema(
                type=types.Type.STRING,
                description="The file to read, relative to the working directory. May not be a directory."
            )
        },
        required=["working_directory", "file_path"],
    ),
)

