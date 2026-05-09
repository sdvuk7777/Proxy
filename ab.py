import json
import requests
import pymongo
from pymongo import MongoClient
from urllib.parse import quote_plus
import os

# GitHub configuration
GITHUB_REPO_OWNER = "sdvuk7777"
GITHUB_REPO_NAME = "UMbatchdb"
GITHUB_ACCESS_TOKEN = "x"

# MongoDB configuration
MONGO_URI = "x"
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
                    'download_url': item['download_url'],
                    'collection_name': item['name'].replace('.json', '')
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
                    'collection_name': item['name'].replace('.json', '')
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

def get_existing_collections(db):
    """Get list of existing collection names in the database"""
    try:
        existing_collections = db.list_collection_names()
        print(f"\n📊 Found {len(existing_collections)} existing collection(s) in database '{DB_NAME}':")
        for collection in existing_collections:
            print(f"  - {collection}")
        return set(existing_collections)  # Return as set for faster lookup
    except Exception as e:
        print(f"❌ Error fetching collections: {e}")
        return set()

def upload_json_to_mongodb(json_file_info, db):
    """Upload JSON data to MongoDB collection"""
    collection_name = json_file_info['collection_name']
    
    try:
        # Download JSON content
        print(f"  📥 Downloading {json_file_info['name']}...")
        response = requests.get(json_file_info['download_url'])
        response.raise_for_status()
        json_data = response.json()
        
        # Get collection
        collection = db[collection_name]
        
        # Determine if JSON is an array or object
        if isinstance(json_data, list):
            if len(json_data) > 0:
                # Insert multiple documents
                result = collection.insert_many(json_data)
                print(f"  ✅ Uploaded {len(json_data)} document(s) to collection '{collection_name}'")
                return len(json_data)
            else:
                print(f"  ⚠️ Empty array in {json_file_info['name']}, no documents inserted")
                return 0
        elif isinstance(json_data, dict):
            # Insert single document
            result = collection.insert_one(json_data)
            print(f"  ✅ Uploaded 1 document to collection '{collection_name}'")
            return 1
        else:
            print(f"  ❌ Unexpected data type in {json_file_info['name']}: {type(json_data)}")
            return 0
            
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Error downloading {json_file_info['name']}: {e}")
        return 0
    except json.JSONDecodeError as e:
        print(f"  ❌ Error parsing {json_file_info['name']} as JSON: {e}")
        return 0
    except Exception as e:
        print(f"  ❌ Error uploading {json_file_info['name']} to MongoDB: {e}")
        return 0

def main():
    """Main function to orchestrate the upload process"""
    print("=" * 60)
    print("🚀 JSON Files Uploader to MongoDB with Skip Logic")
    print("=" * 60)
    
    # Connect to MongoDB
    client = connect_to_mongodb()
    if not client:
        return
    
    db = client[DB_NAME]
    
    # Get existing collections from MongoDB
    existing_collections = get_existing_collections(db)
    
    # Get all JSON files from GitHub
    print("\n🔍 Scanning GitHub repository...")
    json_files = get_all_json_files()
    
    if not json_files:
        print("❌ No JSON files found in the repository.")
        return
    
    print(f"\n📁 Found {len(json_files)} JSON file(s) in GitHub repository:")
    for file_info in json_files:
        print(f"  - {file_info['name']} → will become collection: {file_info['collection_name']}")
    
    # Separate files into new and existing
    files_to_upload = []
    files_to_skip = []
    
    for file_info in json_files:
        if file_info['collection_name'] in existing_collections:
            files_to_skip.append(file_info)
        else:
            files_to_upload.append(file_info)
    
    # Display summary
    print("\n" + "=" * 60)
    print("📊 UPLOAD SUMMARY")
    print("=" * 60)
    print(f"📝 Total JSON files found: {len(json_files)}")
    print(f"⏭️  Files to skip (already in MongoDB): {len(files_to_skip)}")
    print(f"🆕 Files to upload (new): {len(files_to_upload)}")
    
    if files_to_skip:
        print("\n⏭️  SKIPPED FILES (already exist in MongoDB):")
        for file_info in files_to_skip:
            print(f"  - {file_info['name']} (collection: {file_info['collection_name']})")
    
    if not files_to_upload:
        print("\n✅ All files are already uploaded to MongoDB! Nothing to do.")
        client.close()
        return
    
    # Upload new files
    print("\n" + "=" * 60)
    print("🆕 UPLOADING NEW FILES")
    print("=" * 60)
    
    total_uploaded = 0
    successful_uploads = 0
    
    for file_info in files_to_upload:
        print(f"\n📄 Processing: {file_info['name']}")
        docs_count = upload_json_to_mongodb(file_info, db)
        if docs_count > 0:
            successful_uploads += 1
            total_uploaded += docs_count
    
    # Final summary
    print("\n" + "=" * 60)
    print("🎉 UPLOAD PROCESS COMPLETED!")
    print("=" * 60)
    print(f"✅ Successfully uploaded: {successful_uploads}/{len(files_to_upload)} files")
    print(f"📄 Total documents inserted: {total_uploaded}")
    print(f"⏭️  Skipped (already existed): {len(files_to_skip)} files")
    print("=" * 60)
    
    # Close MongoDB connection
    client.close()

# Alternative version with interactive mode (ask before skipping)
def main_interactive():
    """Interactive version - asks user before skipping files"""
    print("=" * 60)
    print("🚀 JSON Files Uploader to MongoDB (Interactive Mode)")
    print("=" * 60)
    
    # Connect to MongoDB
    client = connect_to_mongodb()
    if not client:
        return
    
    db = client[DB_NAME]
    
    # Get existing collections from MongoDB
    existing_collections = get_existing_collections(db)
    
    # Get all JSON files from GitHub
    print("\n🔍 Scanning GitHub repository...")
    json_files = get_all_json_files()
    
    if not json_files:
        print("❌ No JSON files found in the repository.")
        return
    
    print(f"\n📁 Found {len(json_files)} JSON file(s) in GitHub repository")
    
    # Process each file with user input
    files_to_upload = []
    
    for file_info in json_files:
        collection_name = file_info['collection_name']
        
        if collection_name in existing_collections:
            print(f"\n⚠️  File '{file_info['name']}' already exists as collection '{collection_name}'")
            user_input = input("   Do you want to overwrite? (yes/no/skip all): ").lower()
            
            if user_input == 'yes':
                print(f"   🗑️  Dropping existing collection '{collection_name}'...")
                db[collection_name].drop()
                files_to_upload.append(file_info)
            elif user_input == 'skip all':
                print("   ⏭️  Skipping this and all remaining files...")
                break
            else:
                print(f"   ⏭️  Skipping {file_info['name']}")
        else:
            files_to_upload.append(file_info)
    
    # Upload selected files
    if files_to_upload:
        print("\n" + "=" * 60)
        print("📤 UPLOADING FILES")
        print("=" * 60)
        
        for file_info in files_to_upload:
            print(f"\n📄 Processing: {file_info['name']}")
            upload_json_to_mongodb(file_info, db)
    else:
        print("\n✅ No files to upload!")
    
    client.close()

if __name__ == "__main__":
    # Run the automatic version (skips without asking)
    main()
    
    # Uncomment below to run interactive version (asks before skipping/overwriting)
    # main_interactive()