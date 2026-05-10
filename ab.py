import json
import requests
import pymongo
from pymongo import MongoClient
from urllib.parse import quote_plus
import os
from datetime import datetime

# GitHub configuration
GITHUB_REPO_OWNER = "sdvuk7777"
GITHUB_REPO_NAME = "UMbatchdb"
GITHUB_ACCESS_TOKEN = ""

# MongoDB configuration
MONGO_URI = ""
DB_NAME = "studyuk_batches"
COLLECTION_NAME = "github_json_files"  # Single collection for all files

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
                    'download_url': item['download_url'],
                    'path': item['path'],
                    'size': item.get('size', 0)
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
                    'download_url': item['download_url'],
                    'path': item['path'],
                    'size': item.get('size', 0)
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
        print("✅ Connected to MongoDB successfully!")
        return client
    except Exception as e:
        print(f"❌ Error connecting to MongoDB: {e}")
        return None

def get_existing_file_names(db, collection_name):
    """Get list of existing file names already uploaded"""
    try:
        collection = db[collection_name]
        existing_files = collection.distinct("file_name")
        print(f"\n📊 Found {len(existing_files)} existing file(s) already in database")
        return set(existing_files)
    except Exception as e:
        print(f"❌ Error fetching existing files: {e}")
        return set()

def upload_json_to_mongodb(json_file_info, db, collection_name):
    """Upload JSON data to MongoDB with file name as a field"""
    
    try:
        # Download JSON content
        print(f"  📥 Downloading {json_file_info['name']}...")
        response = requests.get(json_file_info['download_url'])
        response.raise_for_status()
        json_data = response.json()
        
        # Prepare document structure
        document = {
            "file_name": json_file_info['name'],
            "file_path": json_file_info['path'],
            "file_size": json_file_info['size'],
            "uploaded_at": datetime.now(),
            "data": json_data
        }
        
        # Get collection
        collection = db[collection_name]
        
        # Insert document
        result = collection.insert_one(document)
        
        # Determine data size info
        if isinstance(json_data, list):
            data_items = len(json_data)
            print(f"  ✅ Uploaded '{json_file_info['name']}' with {data_items} items in data array")
        elif isinstance(json_data, dict):
            data_items = len(json_data)
            print(f"  ✅ Uploaded '{json_file_info['name']}' with {data_items} fields in data object")
        else:
            print(f"  ✅ Uploaded '{json_file_info['name']}'")
        
        return True
            
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Error downloading {json_file_info['name']}: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"  ❌ Error parsing {json_file_info['name']} as JSON: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error uploading {json_file_info['name']} to MongoDB: {e}")
        return False

def create_indexes(db, collection_name):
    """Create indexes for better query performance"""
    try:
        collection = db[collection_name]
        
        # Create index on file_name for faster lookups
        collection.create_index("file_name", unique=True)
        
        # Create index on uploaded_at for time-based queries
        collection.create_index("uploaded_at")
        
        print("✅ Indexes created successfully on 'file_name' and 'uploaded_at'")
    except Exception as e:
        print(f"⚠️ Note: {e}")

def main():
    """Main function to orchestrate the upload process"""
    print("=" * 60)
    print("🚀 JSON Files Uploader to Single MongoDB Collection")
    print("=" * 60)
    print(f"📦 Target Collection: {COLLECTION_NAME}")
    
    # Connect to MongoDB
    client = connect_to_mongodb()
    if not client:
        return
    
    db = client[DB_NAME]
    
    # Create indexes for better performance
    create_indexes(db, COLLECTION_NAME)
    
    # Get existing file names from MongoDB
    existing_files = get_existing_file_names(db, COLLECTION_NAME)
    
    # Get all JSON files from GitHub
    print("\n🔍 Scanning GitHub repository...")
    json_files = get_all_json_files()
    
    if not json_files:
        print("❌ No JSON files found in the repository.")
        return
    
    print(f"\n📁 Found {len(json_files)} JSON file(s) in GitHub repository:")
    for file_info in json_files[:5]:  # Show first 5 files
        print(f"  - {file_info['name']}")
    if len(json_files) > 5:
        print(f"  ... and {len(json_files) - 5} more")
    
    # Separate files into new and existing
    files_to_upload = []
    files_to_skip = []
    
    for file_info in json_files:
        if file_info['name'] in existing_files:
            files_to_skip.append(file_info)
        else:
            files_to_upload.append(file_info)
    
    # Display summary
    print("\n" + "=" * 60)
    print("📊 UPLOAD SUMMARY")
    print("=" * 60)
    print(f"📝 Total JSON files found: {len(json_files)}")
    print(f"⏭️  Files to skip (already uploaded): {len(files_to_skip)}")
    print(f"🆕 Files to upload (new): {len(files_to_upload)}")
    
    if files_to_skip:
        print("\n⏭️  SKIPPED FILES (already in MongoDB):")
        for file_info in files_to_skip[:10]:  # Show first 10
            print(f"  - {file_info['name']}")
        if len(files_to_skip) > 10:
            print(f"  ... and {len(files_to_skip) - 10} more")
    
    if not files_to_upload:
        print("\n✅ All files are already uploaded to MongoDB! Nothing to do.")
        client.close()
        return
    
    # Upload new files
    print("\n" + "=" * 60)
    print("🆕 UPLOADING NEW FILES")
    print("=" * 60)
    
    successful_uploads = 0
    
    for i, file_info in enumerate(files_to_upload, 1):
        print(f"\n[{i}/{len(files_to_upload)}] Processing: {file_info['name']}")
        if upload_json_to_mongodb(file_info, db, COLLECTION_NAME):
            successful_uploads += 1
    
    # Final summary
    print("\n" + "=" * 60)
    print("🎉 UPLOAD PROCESS COMPLETED!")
    print("=" * 60)
    print(f"✅ Successfully uploaded: {successful_uploads}/{len(files_to_upload)} files")
    print(f"⏭️  Skipped (already existed): {len(files_to_skip)} files")
    print(f"📦 All data stored in collection: {DB_NAME}.{COLLECTION_NAME}")
    print("\n📝 Document Structure:")
    print("  {")
    print("    '_id': ObjectId('...'),")
    print("    'file_name': 'example.json',")
    print("    'file_path': 'path/to/example.json',")
    print("    'file_size': 1234,")
    print("    'uploaded_at': ISODate('2024-01-01...'),")
    print("    'data': { ... }  // Your actual JSON data")
    print("  }")
    print("=" * 60)
    
    # Show sample queries
    print("\n💡 Example Queries:")
    print(f"  # Get specific file:")
    print(f"  db.{COLLECTION_NAME}.findOne({{'file_name': 'example.json'}})")
    print(f"  # Get all files:")
    print(f"  db.{COLLECTION_NAME}.find()")
    print(f"  # Get only file names:")
    print(f"  db.{COLLECTION_NAME}.find({{}}, {{'file_name': 1, 'uploaded_at': 1}})")
    
    # Close MongoDB connection
    client.close()

# Optional: Function to update existing files
def update_existing_files():
    """Update mode - overwrite existing files if they've changed"""
    print("=" * 60)
    print("🔄 UPDATE MODE - Checking for file changes")
    print("=" * 60)
    
    client = connect_to_mongodb()
    if not client:
        return
    
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    
    # Get all JSON files from GitHub
    json_files = get_all_json_files()
    
    updated_count = 0
    for file_info in json_files:
        # Check if file exists
        existing = collection.find_one({"file_name": file_info['name']})
        
        if existing:
            # Check if size changed (indicating file update)
            if existing.get('file_size', 0) != file_info['size']:
                print(f"🔄 Updating {file_info['name']} (size changed)")
                # Download new data
                response = requests.get(file_info['download_url'])
                response.raise_for_status()
                new_data = response.json()
                
                # Update the document
                collection.update_one(
                    {"file_name": file_info['name']},
                    {
                        "$set": {
                            "data": new_data,
                            "file_size": file_info['size'],
                            "updated_at": datetime.now()
                        }
                    }
                )
                updated_count += 1
        else:
            # New file, upload it
            print(f"➕ Adding new file: {file_info['name']}")
            upload_json_to_mongodb(file_info, db, COLLECTION_NAME)
    
    print(f"\n✅ Update complete! Updated {updated_count} files.")
    client.close()

if __name__ == "__main__":
    # Run the main uploader
    main()
    
    # Uncomment below to run update mode (checks for file changes)
    # update_existing_files()