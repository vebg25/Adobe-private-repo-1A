import os
import json
import time
from extractor import process_pdf_file

def main():
    """
    Orchestrates the processing of all PDF files in the input directory.
    """
    # These paths are based on the volume mounts specified in the docker run command.
    input_dir = '/app/input'
    output_dir = '/app/output'

    # Ensure the output directory exists.
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Check if the input directory exists.
    if not os.path.exists(input_dir):
        print(f"Error: Input directory '{input_dir}' not found. Please mount your input volume.")
        return

    print(f"Starting document processing from '{input_dir}'...")

    # Process each file in the input directory.
    for filename in os.listdir(input_dir):
        if filename.lower().endswith('.pdf'):
            input_path = os.path.join(input_dir, filename)
            output_filename = os.path.splitext(filename)[0] + '.json'
            output_path = os.path.join(output_dir, output_filename)

            print(f"Processing '{filename}'...")
            start_time = time.time()

            try:
                # Call the core logic from the extractor module.
                result_data = process_pdf_file(input_path)

                # Write the structured data to the output JSON file.
                # We use ensure_ascii=False to correctly handle multilingual characters.
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result_data, f, indent=2, ensure_ascii=False)

                end_time = time.time()
                print(f"Successfully created '{output_filename}' in {end_time - start_time:.2f} seconds.")

            except Exception as e:
                end_time = time.time()
                print(f"Error processing '{filename}': {e}")
                print(f"Failed in {end_time - start_time:.2f} seconds.")

    print("All documents processed.")

if __name__ == "__main__":
    main()

