import os
import shutil

base_dir = os.environ.get('GITHUB_WORKSPACE')
dest_dir = f'{base_dir}/deployment_package'
rel_dest_dir = os.path.relpath(dest_dir, base_dir)

os.makedirs(dest_dir, exist_ok=True)
shutil.copy(f'{base_dir}/.env', dest_dir)
shutil.copy(f'{base_dir}/azure.yml', dest_dir)
shutil.copytree(f'{base_dir}/compose/production/traefik', f'{dest_dir}/compose/production/traefik', dirs_exist_ok=True)
shutil.copytree(f'{base_dir}/compose/production/postgres', f'{dest_dir}/compose/production/postgres',
                dirs_exist_ok=True)
