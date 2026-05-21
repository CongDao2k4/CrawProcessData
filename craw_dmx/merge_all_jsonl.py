import os
import glob

# Thư mục chứa các file jsonl
input_folder = "cleaned_mapped_metadata_2"
output_file = "dmx_metadatas.jsonl"

# Lấy tất cả file .jsonl trong thư mục
jsonl_files = glob.glob(os.path.join(input_folder, "*.jsonl"))

print(f"Found {len(jsonl_files)} files")

with open(output_file, "w", encoding="utf-8") as outfile:
    for file in jsonl_files:
        print(f"Processing: {file}")
        with open(file, "r", encoding="utf-8") as infile:
            for line in infile:
                outfile.write(line)

print(f"Done! Merged file saved as {output_file}")