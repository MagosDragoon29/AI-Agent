# functions/write_file.py
import os
from google.genai import types

def write_file(working_directory, file_path, contents):
    if file_path is None:
        print("Result for current file:")
    else:
        print(f"Result for '{file_path}'")

    wd = os.path.abspath(working_directory)
    full = os.path.abspath(os.path.join(wd, file_path))

    if os.path.commonpath([wd, full]) != wd:
        return f'Error: Cannot write to "{file_path}" as it is outside the permitted working directory'
    if os.path.isdir(full):
        return f'Error: "{file_path}" is a directory, not a file'

    os.makedirs(os.path.dirname(full) or wd, exist_ok=True)
    try:
        with open(full, "w", encoding="utf-8") as f:
            f.write(contents)
    except Exception as e:
        return f'Error: {e}'

    return f'Successfully wrote to "{file_path}" ({len(contents)} characters written)'

schema_write_file = types.FunctionDeclaration(
    name="write_file",
    description="Write or overwrite a file relative to the working directory.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            # Do NOT require this; the dispatcher injects it.
            # Keeping it out of properties entirely discourages the model from setting it.
            "file_path": types.Schema(
                type=types.Type.STRING,
                description="Relative file path to write, from the working directory."
            ),
            "contents": types.Schema(
                type=types.Type.STRING,
                description="The text content to write."
            ),
        },
        required=["file_path", "contents"],  # no 'working_directory' here
    ),
)
