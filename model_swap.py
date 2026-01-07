#!/usr/bin/env python3
"""
Minimal script to process a single PDP folder with model-swap.

This script performs the basic workflow:
1. Authenticate with the API
2. Create a project
3. Upload PDP images
4. Upload or verify identity
5. Create model-swap job
6. Monitor job progress
7. Download results
"""

import argparse
import base64
import http.client
import json
import time
from pathlib import Path
from urllib.parse import urlparse

import requests


class ModelSwap:
    def __init__(self, base_url, username, password, input_folder, identity_code=None, identity_image=None, output_folder="output", post_process=False):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.input_folder = Path(input_folder)
        self.identity_code = identity_code
        self.identity_image = Path(identity_image) if identity_image else None
        self.output_folder = Path(output_folder)
        self.post_process = post_process
        
        self.access_token = None
        self.project_id = None
        self.project_name = None
        
    def login(self):
        """Authenticate with the API using Basic Auth."""
        print("Authenticating...")
        
        credentials = f"{self.username}:{self.password}"
        basic_auth = base64.b64encode(credentials.encode()).decode()
        headers = {"Authorization": f"Basic {basic_auth}"}
        
        try:
            response = requests.post(f"{self.base_url}/auth/login", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data["token"]
                print("Authentication successful")
                return True
            else:
                print(f"Authentication failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
        except Exception as e:
            print(f"Authentication error: {e}")
            return False
    
    def get_auth_headers(self):
        """Get headers with Bearer token."""
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}
    
    def create_project(self, project_name):
        """Create a project on the API server."""
        print(f"Creating project '{project_name}'...")
        
        try:
            response = requests.post(
                f"{self.base_url}/project",
                headers=self.get_auth_headers(),
                json={"project_name": project_name}
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                self.project_id = data["project_id"]
                self.project_name = data["project_name"]
                print(f"Project created: {self.project_id}")
                return True
            elif response.status_code == 409:
                # Project already exists, get its ID
                print(f"Project '{project_name}' already exists")
                # We'll get project_id from the first upload
                self.project_name = project_name
                return True
            else:
                print(f"Failed to create project: {response.status_code}")
                print(f"Response: {response.text}")
                return False
        except Exception as e:
            print(f"Error creating project: {e}")
            return False
    
    def get_upload_url(self, filename):
        """Get a pre-signed upload URL for an image."""
        try:
            response = requests.post(
                f"{self.base_url}/upload",
                headers=self.get_auth_headers(),
                json={
                    "project_name": self.project_name,
                    "filename": filename
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                # Store project_id from first upload if we don't have it
                if not self.project_id and "project_id" in data:
                    self.project_id = data["project_id"]
                return data
            else:
                print(f"Failed to get upload URL: {response.status_code}")
                print(f"Response: {response.text}")
                return None
        except Exception as e:
            print(f"Error getting upload URL: {e}")
            return None
    
    def upload_image(self, upload_url, file_path, content_type):
        """Upload an image to S3 using the pre-signed URL."""
        try:
            with open(file_path, "rb") as f:
                image_data = f.read()
            
            parsed = urlparse(upload_url)
            
            if parsed.scheme == "https":
                conn = http.client.HTTPSConnection(parsed.netloc, timeout=120)
            else:
                conn = http.client.HTTPConnection(parsed.netloc, timeout=120)
            
            path = parsed.path
            if parsed.query:
                path = f"{path}?{parsed.query}"
            
            headers = {"Content-Type": content_type}
            conn.request("PUT", path, body=image_data, headers=headers)
            response = conn.getresponse()
            response.read()  # Read response to complete request
            conn.close()
            
            return response.status in [200, 201]
        except Exception as e:
            print(f"Error uploading image: {e}")
            return False
    
    def upload_pdp_images(self):
        """Upload all images from the input folder."""
        if not self.input_folder.exists():
            print(f"Input folder not found: {self.input_folder}")
            print(f"Checked path: {self.input_folder.absolute()}")
            return []
        
        # Find all image files
        image_extensions = [".jpg", ".jpeg", ".png"]
        image_files = [
            f for f in sorted(self.input_folder.iterdir())
            if f.is_file() and f.suffix.lower() in image_extensions
            and "_INTERNAL_" not in f.name and "_NONMODEL_" not in f.name
        ]
        
        if not image_files:
            print(f"No processable images found in {self.input_folder}")
            return []
        
        print(f"Found {len(image_files)} images to upload")
        
        # Create project if not already created
        if not self.project_name:
            project_name = self.input_folder.name
            if not self.create_project(project_name):
                return []
        
        file_ids = []
        
        for image_file in image_files:
            print(f"Uploading {image_file.name}...")
            
            upload_info = self.get_upload_url(image_file.name)
            if not upload_info:
                print(f"Failed to get upload URL for {image_file.name}")
                continue
            
            upload_url = upload_info["upload_url"]
            # Fix URL scheme if needed
            if self.base_url.startswith("https://") and upload_url.startswith("http://"):
                upload_url = upload_url.replace("http://", "https://", 1)
            
            success = self.upload_image(
                upload_url,
                image_file,
                upload_info["content_type"]
            )
            
            if success:
                file_ids.append(upload_info["file_id"])
                print(f"Uploaded: {image_file.name} -> {upload_info['file_id']}")
            else:
                print(f"Failed to upload: {image_file.name}")
        
        print(f"Successfully uploaded {len(file_ids)}/{len(image_files)} images")
        return file_ids
    
    def get_or_upload_identity(self):
        """Get identity code from existing identity or upload new one."""
        if self.identity_code:
            # Check if identity exists
            try:
                response = requests.get(
                    f"{self.base_url}/identity/{self.identity_code}",
                    headers=self.get_auth_headers()
                )
                if response.status_code == 200:
                    data = response.json()
                    print(f"Using existing identity: {self.identity_code}")
                    return data["identity_code"]
            except Exception as e:
                print(f"Error checking identity: {e}")
        
        if self.identity_image and self.identity_image.exists():
            # Upload new identity
            print(f"Uploading identity image: {self.identity_image.name}...")
            
            try:
                # Detect content type from file extension
                suffix = self.identity_image.suffix.lower()
                content_type_map = {
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png"
                }
                content_type = content_type_map.get(suffix, "image/jpeg")
                
                with open(self.identity_image, "rb") as f:
                    files = {"image": (self.identity_image.name, f, content_type)}
                    data = {"name": self.identity_image.stem}
                    
                    response = requests.post(
                        f"{self.base_url}/identity/upload",
                        headers=self.get_auth_headers(),
                        files=files,
                        data=data,
                        timeout=30
                    )
                
                if response.status_code in [200, 201]:
                    identity_data = response.json()
                    identity_code = identity_data["identity_code"]
                    print(f"Identity uploaded: {identity_code}")
                    return identity_code
                elif response.status_code == 409:
                    # Identity already exists
                    identity_data = response.json()
                    identity_code = identity_data.get("existing_identity_code", identity_data.get("identity_code"))
                    print(f"Identity already exists: {identity_code}")
                    return identity_code
                else:
                    print(f"Failed to upload identity: {response.status_code}")
                    print(f"Response: {response.text}")
                    return None
            except Exception as e:
                print(f"Error uploading identity: {e}")
                return None
        
        print("No identity code or identity image provided")
        return None
    
    def create_job(self, identity_code, file_ids):
        """Create a model-swap job."""
        print("Creating model-swap job...")
        
        payload = {
            "project_id": self.project_id,
            "images": file_ids,
            "identity_code": identity_code,
            "post_process": self.post_process
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/model-swap",
                headers=self.get_auth_headers(),
                json=payload
            )
            
            if response.status_code == 202:
                data = response.json()
                job_id = data["job_id"]
                print(f"Job created: {job_id}")
                return job_id
            else:
                print(f"Failed to create job: {response.status_code}")
                print(f"Response: {response.text}")
                return None
        except Exception as e:
            print(f"Error creating job: {e}")
            return None
    
    def wait_for_job(self, job_id, max_wait_time=1200, check_interval=5):
        """Wait for job to complete."""
        print("Waiting for job to complete...")
        
        start_time = time.time()
        max_retries_404 = 10
        retry_count = 0
        
        time.sleep(5)  # Initial delay
        
        while True:
            if time.time() - start_time > max_wait_time:
                print(f"Timeout: Job took longer than {max_wait_time} seconds")
                return None
            
            try:
                response = requests.get(
                    f"{self.base_url}/jobs/{job_id}/status",
                    headers=self.get_auth_headers()
                )
                
                if response.status_code == 404:
                    retry_count += 1
                    if retry_count <= max_retries_404:
                        print(f"Job not found yet (attempt {retry_count}/{max_retries_404}), waiting...")
                        time.sleep(3)
                        continue
                    else:
                        print(f"Job {job_id} not found after {max_retries_404} retries")
                        return None
                
                if response.status_code != 200:
                    print(f"Failed to get status: {response.status_code}")
                    print(f"Response: {response.text}")
                    return None
                
                retry_count = 0
                status_data = response.json()
                status = status_data["status"]
                progress = status_data.get("progress", 0)
                
                print(f"Progress: {progress:.1f}% - Status: {status}")
                
                if status in ["completed", "failed", "aborted"]:
                    print(f"Job finished with status: {status}")
                    return status
                
                time.sleep(check_interval)
            except Exception as e:
                print(f"Error checking status: {e}")
                time.sleep(check_interval)
    
    def download_results(self, job_id):
        """Download job results."""
        print("Retrieving results...")
        
        try:
            response = requests.get(
                f"{self.base_url}/jobs/{job_id}/results",
                headers=self.get_auth_headers()
            )
            
            if response.status_code != 200:
                print(f"Failed to get results: {response.status_code}")
                print(f"Response: {response.text}")
                return False
            
            results_data = response.json()
            
            # Create output folder
            self.output_folder.mkdir(parents=True, exist_ok=True)
            
            # Download images
            if "results" in results_data:
                for result in results_data["results"]:
                    if result.get("status") == "completed":
                        output_url = None
                        if result.get("output") and isinstance(result["output"], dict):
                            output_url = result["output"].get("full_size")
                        
                        if output_url:
                            try:
                                img_response = requests.get(output_url, timeout=30)
                                img_response.raise_for_status()
                                
                                original_filename = result.get("original_filename", f"image_{result['image_index']}.jpg")
                                original_filename = Path(original_filename).name
                                
                                version = result.get("version", 0)
                                if "." in original_filename:
                                    basename, ext = original_filename.rsplit(".", 1)
                                    filename = f"{basename}_v{version}.{ext}"
                                else:
                                    filename = f"{original_filename}_v{version}"
                                
                                output_path = self.output_folder / filename
                                with open(output_path, "wb") as f:
                                    f.write(img_response.content)
                                
                                print(f"Downloaded: {filename}")
                            except Exception as e:
                                print(f"Failed to download image {result['image_index']}: {e}")
            
            # Save metadata
            metadata_path = self.output_folder / "metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(results_data, f, indent=2)
            
            print(f"Results saved to {self.output_folder}")
            return True
        except Exception as e:
            print(f"Error downloading results: {e}")
            return False
    
    def run(self):
        """Run the complete workflow."""
        print("=" * 70)
        print("Model Swap")
        print("=" * 70)
        
        # Step 1: Authenticate
        if not self.login():
            return False
        
        # Step 2: Upload PDP images
        file_ids = self.upload_pdp_images()
        if not file_ids:
            print("No images uploaded")
            return False
        
        if not self.project_id:
            print("No project ID available")
            return False
        
        # Step 3: Get or upload identity
        identity_code = self.get_or_upload_identity()
        if not identity_code:
            print("No identity code available")
            return False
        
        # Step 4: Create job
        job_id = self.create_job(identity_code, file_ids)
        if not job_id:
            return False
        
        # Step 5: Wait for completion
        status = self.wait_for_job(job_id)
        if status != "completed":
            print(f"Job did not complete successfully (status: {status})")
            return False
        
        # Step 6: Download results
        if not self.download_results(job_id):
            return False
        
        print("=" * 70)
        print("Processing complete")
        print("=" * 70)
        return True


def main():
    parser = argparse.ArgumentParser(
        description="Script to process a PDP folder with model-swap"
    )
    parser.add_argument(
        "--input-folder",
        type=str,
        required=True,
        help="Path to folder containing PDP images"
    )
    parser.add_argument(
        "--identity-code",
        type=str,
        default=None,
        help="Existing identity code to use"
    )
    parser.add_argument(
        "--identity-image",
        type=str,
        default=None,
        help="Path to identity image file to upload"
    )
    parser.add_argument(
        "--output-folder",
        type=str,
        default="output",
        help="Output folder for results (default: output)"
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="https://v2.api.piktid.com",
        help="API base URL (default: https://v2.api.piktid.com)"
    )
    parser.add_argument(
        "--username",
        type=str,
        required=True,
        help="API username (required)"
    )
    parser.add_argument(
        "--password",
        type=str,
        required=True,
        help="API password (required)"
    )
    parser.add_argument(
        "--post-process",
        action="store_true",
        help="Enable post-processing (default: False)"
    )
    
    args = parser.parse_args()
    
    if not args.username:
        parser.error("--username is required")
    
    if not args.password:
        parser.error("--password is required")
    
    if not args.identity_code and not args.identity_image:
        parser.error("Either --identity-code or --identity-image must be provided")
    
    processor = ModelSwap(
        base_url=args.base_url,
        username=args.username,
        password=args.password,
        input_folder=args.input_folder,
        identity_code=args.identity_code,
        identity_image=args.identity_image,
        output_folder=args.output_folder,
        post_process=args.post_process
    )
    
    success = processor.run()
    
    if not success:
        exit(1)


if __name__ == "__main__":
    main()

