import boto3
import os
import traceback


def purge_bucket(endpoint_url, access_key, secret_key, bucket_name, region_name='nyc3'):
    """Delete all objects in a DigitalOcean Spaces bucket."""
    try:
        s3 = boto3.client('s3',
                          endpoint_url=endpoint_url,
                          aws_access_key_id=access_key,
                          aws_secret_access_key=secret_key,
                          region_name=region_name
                          )

        print(f"Listing all objects in bucket {bucket_name}...")
        paginator = s3.get_paginator('list_objects_v2')

        object_count = 0
        for page in paginator.paginate(Bucket=bucket_name):
            if 'Contents' in page:
                objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
                if objects_to_delete:
                    print(f"Deleting batch of {len(objects_to_delete)} objects...")
                    s3.delete_objects(
                        Bucket=bucket_name,
                        Delete={'Objects': objects_to_delete}
                    )
                    object_count += len(objects_to_delete)

        print(f"Successfully purged {object_count} objects from bucket {bucket_name}")
        return True
    except Exception as e:
        print(f"Error purging bucket: {e}")
        print(traceback.format_exc())
        return False


def upload_to_spaces(endpoint_url, access_key, secret_key, bucket_name, local_dir, region_name='nyc3'):
    """Upload files to a DigitalOcean Spaces bucket with public-read permissions."""
    try:
        # Create S3 client
        s3 = boto3.client('s3',
                          endpoint_url=endpoint_url,
                          aws_access_key_id=access_key,
                          aws_secret_access_key=secret_key,
                          region_name=region_name
                          )

        # Verify bucket exists
        try:
            s3.head_bucket(Bucket=bucket_name)
            print(f"Verified bucket {bucket_name} exists.")
        except Exception as bucket_error:
            print(f"Error accessing bucket: {bucket_error}")
            return False

        # Upload files with public-read ACL
        file_count = 0
        for root, dirs, files in os.walk(local_dir):
            for file in files:
                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_path, local_dir)
                s3_path = relative_path.replace('\\', '/')

                try:
                    print(f"Uploading: {local_path} to {s3_path}")
                    s3.upload_file(
                        local_path,
                        bucket_name,
                        s3_path,
                        ExtraArgs={'ACL': 'public-read'}
                    )
                    file_count += 1
                    print(f"Successfully uploaded {s3_path} with public-read permissions")
                except Exception as upload_error:
                    print(f"Failed to upload {local_path}: {upload_error}")

        print(f"Upload process completed. Uploaded {file_count} files.")
        return True
    except Exception as e:
        print("An error occurred during upload:")
        print(traceback.format_exc())
        return False


def make_existing_files_public(endpoint_url, access_key, secret_key, bucket_name, region_name='nyc3'):
    """Set all existing files in a bucket to have public-read ACL."""
    try:
        s3 = boto3.client('s3',
                          endpoint_url=endpoint_url,
                          aws_access_key_id=access_key,
                          aws_secret_access_key=secret_key,
                          region_name=region_name
                          )

        # List all objects in the bucket
        print(f"Setting public-read ACL for all existing files in {bucket_name}...")
        paginator = s3.get_paginator('list_objects_v2')

        file_count = 0
        for page in paginator.paginate(Bucket=bucket_name):
            if 'Contents' in page:
                for obj in page['Contents']:
                    try:
                        s3.put_object_acl(
                            Bucket=bucket_name,
                            Key=obj['Key'],
                            ACL='public-read'
                        )
                        file_count += 1
                        print(f"Set public-read ACL for {obj['Key']}")
                    except Exception as e:
                        print(f"Failed to set ACL for {obj['Key']}: {e}")

        print(f"Completed setting public-read ACL for {file_count} existing files")
        return True
    except Exception as e:
        print(f"Error making files public: {e}")
        print(traceback.format_exc())
        return False


def configure_website_hosting(endpoint_url, access_key, secret_key, bucket_name, region_name='nyc3'):
    """Configure the bucket for static website hosting."""
    try:
        s3 = boto3.client('s3',
                          endpoint_url=endpoint_url,
                          aws_access_key_id=access_key,
                          aws_secret_access_key=secret_key,
                          region_name=region_name
                          )

        print("Setting up website configuration for static site hosting...")
        website_config = {
            'IndexDocument': {'Suffix': 'index.html'},
            'ErrorDocument': {'Key': 'index.html'}  # Fallback to index.html if error page doesn't exist
        }

        s3.put_bucket_website(
            Bucket=bucket_name,
            WebsiteConfiguration=website_config
        )
        print("Website configuration successfully applied")
        print(f"Your website should be accessible at: http://{bucket_name}.{region_name}.digitaloceanspaces.com/")
        print(f"CDN URL (if enabled): http://{bucket_name}.{region_name}.cdn.digitaloceanspaces.com/")
        return True
    except Exception as e:
        print(f"Failed to set website configuration: {e}")
        print(traceback.format_exc())
        return False


def main():
    # Get common inputs
    print("=== DigitalOcean Spaces Static Website Deployment Tool ===")
    endpoint_url = input("Enter DigitalOcean Spaces endpoint URL (e.g., https://nyc3.digitaloceanspaces.com): ")
    access_key = input("Enter your DigitalOcean Spaces Access Key ID: ")
    secret_key = input("Enter your DigitalOcean Spaces Secret Access Key: ")
    bucket_name = input("Enter your Spaces bucket name: ")

    # Determine region from endpoint URL
    try:
        region_name = endpoint_url.split('//')[1].split('.')[0]
    except:
        region_name = 'nyc3'
        print(f"Could not determine region from URL, using default: {region_name}")

    # Ask for purge, upload and ACL operations
    do_purge = input("Do you want to purge the bucket first? (yes/no): ").lower() == 'yes'
    do_upload = input("Do you want to upload files? (yes/no): ").lower() == 'yes'
    make_public = input("Do you want to make all files public? (yes/no): ").lower() == 'yes'
    configure_website = input("Do you want to configure the bucket for website hosting? (yes/no): ").lower() == 'yes'

    # 1. Purge bucket if requested
    if do_purge:
        if purge_bucket(endpoint_url, access_key, secret_key, bucket_name, region_name):
            print("Bucket purged successfully.")
        else:
            if input("Purge failed. Continue with other operations? (yes/no): ").lower() != 'yes':
                print("Operation cancelled.")
                return

    # 2. Upload files if requested
    if do_upload:
        local_dir = input("Enter the local directory to upload (press Enter for current directory): ") or '.'
        if upload_to_spaces(endpoint_url, access_key, secret_key, bucket_name, local_dir, region_name):
            print("Files uploaded successfully.")
        else:
            if input("Upload encountered issues. Continue with other operations? (yes/no): ").lower() != 'yes':
                print("Operation cancelled.")
                return

    # 3. Make files public if requested
    if make_public:
        if make_existing_files_public(endpoint_url, access_key, secret_key, bucket_name, region_name):
            print("Files set to public successfully.")
        else:
            if input(
                    "Making files public encountered issues. Continue with remaining operations? (yes/no): ").lower() != 'yes':
                print("Operation cancelled.")
                return

    # 4. Configure website hosting if requested
    if configure_website:
        if configure_website_hosting(endpoint_url, access_key, secret_key, bucket_name, region_name):
            print("Website hosting configured successfully.")
        else:
            print("Website hosting configuration encountered issues.")

    print("\n=== Operation Summary ===")
    if do_purge:
        print("✓ Bucket purge")
    if do_upload:
        print("✓ File upload")
    if make_public:
        print("✓ Set files to public")
    if configure_website:
        print("✓ Website hosting configuration")

    print("\nYour static website deployment is complete!")
    print(f"Website URL: http://{bucket_name}.{region_name}.digitaloceanspaces.com/")
    print(f"CDN URL (if enabled): http://{bucket_name}.{region_name}.cdn.digitaloceanspaces.com/")


if __name__ == "__main__":
    main()
