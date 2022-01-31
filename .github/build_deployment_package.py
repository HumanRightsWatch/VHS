from zipfile import ZipFile
import os

print(os.environ.get('GITHUB_WORKSPACE'))
base_dir = os.environ.get('GITHUB_WORKSPACE')

def rel(abs_path, path):
    return os.path.relpath(path, abs_path)

def add_file(file_path, base_dir, zip_file):
    zip_file.write(file_path, rel(base_dir, file_path))

with ZipFile(f'{base_dir}/deployment_package.zip', 'w') as zip_file:
    add_file(f'{base_dir}/.env', base_dir, zip_file)
    add_file(f'{base_dir}/azure.yml', base_dir, zip_file)
    for folder_name, sub_folders, filenames in os.walk('../compose'):
        for filename in filenames:
            if 'traefik' in folder_name:
                file_path = os.path.join(folder_name, filename)
                add_file(file_path, base_dir, zip_file)
