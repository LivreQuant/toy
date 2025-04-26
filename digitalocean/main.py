import boto3

s3 = boto3.client('s3',
    endpoint_url='https://nyc3.digitaloceanspaces.com',
    aws_access_key_id='YOUR_ACCESS_KEY',
    aws_secret_access_key='YOUR_SECRET_KEY',
    region_name='nyc3'
)

# Sync directory
import os

bucket_name = 'ff-frontend'
local_dir = '.'

for root, dirs, files in os.walk(local_dir):
    for file in files:
        local_path = os.path.join(root, file)
        relative_path = os.path.relpath(local_path, local_dir)
        s3_path = relative_path.replace('\\', '/')
        
        s3.upload_file(local_path, bucket_name, s3_path)