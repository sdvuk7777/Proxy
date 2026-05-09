import json
import requests
import pymongo
from pymongo import MongoClient
from urllib.parse import quote_plus
import os

# GitHub configuration
GITHUB_REPO_OWNER = "sdvuk7777"
GITHUB_REPO_NAME = "UMbatchdb"
GITHUB_ACCESS_TOKEN = "xy"

# MongoDB configuration
MONGO_URI = "abc"
DB_NAME = "studyuk_batches"

def get_all_json_files():
    """Fetch all JSON files from GitHub repository"""
    headers = {
        'Authorization': f'token {GITHUB_ACCESS_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    # Get contents of the repository
    url = f'https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/contents/'
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        contents = response.json()
        
        json_files = []
        
        for item in contents:
            if item['type'] == 'file' and item['name'].endswith('.json'):
                json_files.append({
                    'name': item['name'],
                    'download_url': item['download_url']
                })
            elif item['type'] == 'dir':
                # Recursively get files from subdirectories
                subdir_files = get_files_from_subdir(item['path'], headers)
                json_files.extend(subdir_files)
        
        return json_files
    except requests.exceptions.RequestException as e:
        print(f"Error fetching repository contents: {e}")
        return []

def get_files_from_subdir(path, headers):
    """Get files from subdirectory"""
    url = f'https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/contents/{path}'
    
    json_files = []
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        contents = response.json()
        
        for item in contents:
            if item['type'] == 'file' and item['name'].endswith('.json'):
                json_files.append({
                    'name': item['name'],
                    'download_url': item['download_url']
                })
            elif item['type'] == 'dir':
                subdir_files = get_files_from_subdir(item['path'], headers)
                json_files.extend(subdir_files)
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching subdirectory {path}: {e}")
    
    return json_files

def connect_to_mongodb():
    """Connect to MongoDB"""
    try:
        client = MongoClient(MONGO_URI)
        # Test connection
        client.admin.command('ping')
        print("Connected to MongoDB successfully!")
        return client
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return None

def upload_json_to_mongodb(json_file_info, db):
    """Upload JSON data to MongoDB collection"""
    collection_name = json_file_info['name'].replace('.json', '')
    
    try:
        # Download JSON content
        response = requests.get(json_file_info['download_url'])
        response.raise_for_status()
        json_data = response.json()
        
        # Get or create collection
        collection = db[collection_name]
        
        # Determine if JSON is an array or object
        if isinstance(json_data, list):
            if len(json_data) > 0:
                # Insert multiple documents
                result = collection.insert_many(json_data)
                print(f"Uploaded {len(json_data)} documents to collection '{collection_name}'")
            else:
                print(f"Empty array in {json_file_info['name']}, no documents inserted")
        elif isinstance(json_data, dict):
            # Insert single document
            result = collection.insert_one(json_data)
            print(f"Uploaded 1 document to collection '{collection_name}'")
        else:
            print(f"Unexpected data type in {json_file_info['name']}: {type(json_data)}")
            
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {json_file_info['name']}: {e}")
    except json.JSONDecodeError as e:
        print(f"Error parsing {json_file_info['name']} as JSON: {e}")
    except Exception as e:
        print(f"Error uploading {json_file_info['name']} to MongoDB: {e}")

def main():
    """Main function to orchestrate the upload process"""
    print("Starting JSON files upload to MongoDB...")
    print("-" * 50)
    
    # Connect to MongoDB
    client = connect_to_mongodb()
    if not client:
        return
    
    db = client[DB_NAME]
    
    # Get all JSON files from GitHub
    json_files = get_all_json_files()
    
    if not json_files:
        print("No JSON files found in the repository.")
        return
    
    print(f"Found {len(json_files)} JSON file(s):")
    for file_info in json_files:
        print(f"  - {file_info['name']}")
    
    print("\nStarting upload...")
    print("-" * 50)
    
    # Upload each JSON file
    for file_info in json_files:
        print(f"\nProcessing: {file_info['name']}")
        upload_json_to_mongodb(file_info, db)
    
    print("\n" + "=" * 50)
    print("Upload process completed!")
    
    # Close MongoDB connection
    client.close()

if __name__ == "__main__":
    main()