import json
import requests
import pymongo
from pymongo import MongoClient
from datetime import datetime

# GitHub configuration
GITHUB_REPO_OWNER = "sdvuk7777"
GITHUB_REPO_NAME = "UMbatchdb"
GITHUB_ACCESS_TOKEN = ""

# MongoDB configuration
MONGO_URI = ""
DB_NAME = "studyuk_batches"
COLLECTION_NAME = "github_json_files"

def get_all_json_files():
    """Fetch all JSON files from GitHub repository"""
    headers = {
        'Authorization': f'token {GITHUB_ACCESS_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    url = f'https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/contents/'
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        contents = response.json()
        
        json_files = []
        
        for item in contents:
            if item['type'] == 'file' and item['name'].endswith('.json'):
                # Remove .json extension for batch_id
                batch_id = item['name'].replace('.json', '')
                json_files.append({
                    'name': item['name'],
                    'batch_id': batch_id,
                    'download_url': item['download_url']
                })
            elif item['type'] == 'dir':
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
                batch_id = item['name'].replace('.json', '')
                json_files.append({
                    'name': item['name'],
                    'batch_id': batch_id,
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
        client.admin.command('ping')
        print("✅ Connected to MongoDB successfully!")
        return client
    except Exception as e:
        print(f"❌ Error connecting to MongoDB: {e}")
        return None

def get_existing_batch_ids(db, collection_name):
    """Get list of existing batch_ids already uploaded"""
    try:
        collection = db[collection_name]
        existing_ids = collection.distinct("batch_id")
        print(f"\n📊 Found {len(existing_ids)} existing batch(s) already in database")
        return set(existing_ids)
    except Exception as e:
        print(f"❌ Error fetching existing batches: {e}")
        return set()

def upload_json_to_mongodb(json_file_info, db, collection_name):
    """Upload JSON data to MongoDB with simple structure"""
    
    try:
        print(f"  📥 Downloading {json_file_info['name']}...")
        response = requests.get(json_file_info['download_url'])
        response.raise_for_status()
        json_data = response.json()
        
        # Prepare simple document structure
        document = {
            "batch_id": json_file_info['batch_id'],
            "uploaded_at": datetime.now(),
            "data": json_data
        }
        
        collection = db[collection_name]
        result = collection.insert_one(document)
        
        # Show data info
        if isinstance(json_data, list):
            print(f"  ✅ Uploaded batch_id: '{json_file_info['batch_id']}' with {len(json_data)} items")
        elif isinstance(json_data, dict):
            print(f"  ✅ Uploaded batch_id: '{json_file_info['batch_id']}' with {len(json_data)} fields")
        else:
            print(f"  ✅ Uploaded batch_id: '{json_file_info['batch_id']}'")
        
        return True
            
    except Exception as e:
        print(f"  ❌ Error uploading {json_file_info['name']}: {e}")
        return False

def create_indexes(db, collection_name):
    """Create indexes for better query performance"""
    try:
        collection = db[collection_name]
        collection.create_index("batch_id", unique=True)
        collection.create_index("uploaded_at")
        print("✅ Indexes created successfully on 'batch_id' and 'uploaded_at'")
    except Exception as e:
        print(f"⚠️ Note: {e}")

def main():
    """Main function to orchestrate the upload process"""
    print("=" * 60)
    print("🚀 JSON Files Uploader to MongoDB")
    print("=" * 60)
    print(f"📦 Target Collection: {COLLECTION_NAME}")
    
    client = connect_to_mongodb()
    if not client:
        return
    
    db = client[DB_NAME]
    create_indexes(db, COLLECTION_NAME)
    
    # Get existing batch_ids from MongoDB
    existing_batches = get_existing_batch_ids(db, COLLECTION_NAME)
    
    # Get all JSON files from GitHub
    print("\n🔍 Scanning GitHub repository...")
    json_files = get_all_json_files()
    
    if not json_files:
        print("❌ No JSON files found in the repository.")
        return
    
    print(f"\n📁 Found {len(json_files)} JSON file(s) in GitHub repository:")
    for file_info in json_files[:5]:
        print(f"  - {file_info['name']} → batch_id: {file_info['batch_id']}")
    if len(json_files) > 5:
        print(f"  ... and {len(json_files) - 5} more")
    
    # Separate files into new and existing
    files_to_upload = []
    files_to_skip = []
    
    for file_info in json_files:
        if file_info['batch_id'] in existing_batches:
            files_to_skip.append(file_info)
        else:
            files_to_upload.append(file_info)
    
    # Display summary
    print("\n" + "=" * 60)
    print("📊 UPLOAD SUMMARY")
    print("=" * 60)
    print(f"📝 Total JSON files found: {len(json_files)}")
    print(f"⏭️  Batches to skip (already exist): {len(files_to_skip)}")
    print(f"🆕 Batches to upload (new): {len(files_to_upload)}")
    
    if files_to_skip:
        print("\n⏭️  SKIPPED BATCHES:")
        for file_info in files_to_skip[:10]:
            print(f"  - {file_info['batch_id']}")
        if len(files_to_skip) > 10:
            print(f"  ... and {len(files_to_skip) - 10} more")
    
    if not files_to_upload:
        print("\n✅ All batches are already uploaded to MongoDB! Nothing to do.")
        client.close()
        return
    
    # Upload new files
    print("\n" + "=" * 60)
    print("🆕 UPLOADING NEW BATCHES")
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
    print(f"✅ Successfully uploaded: {successful_uploads}/{len(files_to_upload)} batches")
    print(f"⏭️  Skipped (already existed): {len(files_to_skip)} batches")
    print(f"📦 All data stored in: {DB_NAME}.{COLLECTION_NAME}")
    print("\n📝 Document Structure:")
    print("  {")
    print("    '_id': ObjectId('...'),")
    print("    'batch_id': 'filename_without_extension',")
    print("    'uploaded_at': ISODate('2024-01-01...'),")
    print("    'data': { ... }  // Your JSON content")
    print("  }")
    print("=" * 60)
    
    # Show example queries
    print("\n💡 Example Queries:")
    print(f"  # Get specific batch:")
    print(f"  db.{COLLECTION_NAME}.findOne({{'batch_id': 'filename'}})")
    print(f"  # Get all batches:")
    print(f"  db.{COLLECTION_NAME}.find()")
    print(f"  # Get only batch_ids:")
    print(f"  db.{COLLECTION_NAME}.find({{}}, {{'batch_id': 1, 'uploaded_at': 1}})")
    
    client.close()

if __name__ == "__main__":
    main()