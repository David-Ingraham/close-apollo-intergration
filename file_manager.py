#!/usr/bin/env python3
"""
File Management System for Close Apollo Integration
Handles automatic cleanup of logs, results, and temporary files
"""

import os
import glob
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path


class FileManager:
    def __init__(self, base_dir=None):
        """Initialize file manager with base directory"""
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self.data_dir = self.base_dir / "data"
        self.setup_directories()
    
    def setup_directories(self):
        """Create directory structure if it doesn't exist"""
        directories = [
            self.data_dir / "results",
            self.data_dir / "logs", 
            self.data_dir / "webhooks",
            self.data_dir / "temp",
            self.base_dir / "config"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"✓ Directory ready: {directory}")
    
    def get_results_path(self, session_id):
        """Get path for enrichment results file"""
        return self.data_dir / "results" / f"enrichment_results_{session_id}.json"
    
    def get_webhook_path(self, timestamp=None):
        """Get path for webhook response file"""
        if not timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        return self.data_dir / "webhooks" / f"apollo_webhook_{timestamp}.json"
    
    def get_log_path(self, log_type="general"):
        """Get path for log file"""
        date_str = datetime.now().strftime("%Y%m%d")
        return self.data_dir / "logs" / f"{log_type}_{date_str}.log"
    
    def get_temp_path(self, filename):
        """Get path for temporary file"""
        return self.data_dir / "temp" / filename
    
    def save_enrichment_results(self, results, session_id):
        """Save enrichment results with proper naming"""
        filepath = self.get_results_path(session_id)
        
        # Add metadata
        results_with_meta = {
            "metadata": {
                "session_id": session_id,
                "created_at": datetime.now().isoformat(),
                "file_type": "enrichment_results",
                "retention_days": 7
            },
            "results": results
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results_with_meta, f, indent=2, ensure_ascii=False)
        
        print(f" Results saved: {filepath}")
        return filepath
    
    def save_webhook_response(self, webhook_data):
        """Save webhook response with timestamp"""
        filepath = self.get_webhook_path()
        
        webhook_with_meta = {
            "metadata": {
                "received_at": datetime.now().isoformat(),
                "file_type": "webhook_response", 
                "retention_days": 7
            },
            "webhook_data": webhook_data
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(webhook_with_meta, f, indent=2, ensure_ascii=False)
        
        print(f" Webhook saved: {filepath}")
        return filepath
    
    def cleanup_old_files(self, dry_run=False):
        """Clean up files older than retention period"""
        now = datetime.now()
        cleanup_stats = {
            "results": {"deleted": 0, "kept": 0, "bytes_freed": 0},
            "logs": {"deleted": 0, "kept": 0, "bytes_freed": 0},
            "webhooks": {"deleted": 0, "kept": 0, "bytes_freed": 0},
            "temp": {"deleted": 0, "kept": 0, "bytes_freed": 0}
        }
        
        # Define retention periods
        retention_rules = {
            "results": 7,    # 7 days
            "logs": 7,       # 7 days  
            "webhooks": 7,   # 7 days
            "temp": 1        # 1 day
        }
        
        for folder, days in retention_rules.items():
            folder_path = self.data_dir / folder
            cutoff_date = now - timedelta(days=days)
            
            if not folder_path.exists():
                continue
                
            print(f"\n Cleaning {folder}/ (keeping files newer than {cutoff_date.strftime('%Y-%m-%d %H:%M')})")
            
            for file_path in folder_path.glob("*"):
                if file_path.is_file():
                    file_age = datetime.fromtimestamp(file_path.stat().st_mtime)
                    file_size = file_path.stat().st_size
                    
                    if file_age < cutoff_date:
                        # File is old, delete it
                        if dry_run:
                            print(f"  [DRY RUN] Would delete: {file_path.name} ({file_size} bytes, {file_age.strftime('%Y-%m-%d %H:%M')})")
                        else:
                            file_path.unlink()
                            print(f"  🗑️  Deleted: {file_path.name} ({file_size} bytes)")
                        
                        cleanup_stats[folder]["deleted"] += 1
                        cleanup_stats[folder]["bytes_freed"] += file_size
                    else:
                        # File is recent, keep it
                        cleanup_stats[folder]["kept"] += 1
        
        # Print summary
        print(f"\n CLEANUP SUMMARY:")
        total_deleted = sum(stats["deleted"] for stats in cleanup_stats.values())
        total_bytes_freed = sum(stats["bytes_freed"] for stats in cleanup_stats.values())
        
        for folder, stats in cleanup_stats.items():
            if stats["deleted"] > 0 or stats["kept"] > 0:
                print(f"  {folder}: {stats['deleted']} deleted, {stats['kept']} kept ({stats['bytes_freed']} bytes freed)")
        
        print(f"  TOTAL: {total_deleted} files deleted, {total_bytes_freed / 1024:.1f} KB freed")
        
        return cleanup_stats
    
    def get_storage_usage(self):
        """Get current storage usage by category"""
        usage = {}
        
        for folder in ["results", "logs", "webhooks", "temp"]:
            folder_path = self.data_dir / folder
            if folder_path.exists():
                total_size = sum(f.stat().st_size for f in folder_path.glob("*") if f.is_file())
                file_count = len(list(folder_path.glob("*")))
                usage[folder] = {
                    "files": file_count,
                    "bytes": total_size,
                    "mb": round(total_size / 1024 / 1024, 2)
                }
            else:
                usage[folder] = {"files": 0, "bytes": 0, "mb": 0}
        
        return usage
    
    def create_temp_symlinks(self, enriched_data, webhook_data):
        """Create temporary files for backward compatibility"""
        temp_files = []
        
        if enriched_data:
            apollo_results = self.get_temp_path("apollo_company_results.json")
            with open(apollo_results, 'w', encoding='utf-8') as f:
                json.dump(enriched_data, f, indent=2, ensure_ascii=False)
            temp_files.append(apollo_results)
        
        if webhook_data:
            webhook_file = self.get_temp_path("webhook_data.json")
            with open(webhook_file, 'w', encoding='utf-8') as f:
                json.dump(webhook_data, f, indent=2, ensure_ascii=False)
            temp_files.append(webhook_file)
        
        return temp_files
    
    def cleanup_temp_files(self, temp_files):
        """Clean up specific temporary files"""
        for file_path in temp_files:
            if file_path.exists():
                file_path.unlink()
                print(f" Cleaned temp file: {file_path.name}")


def main():
    """CLI interface for file management"""
    import sys
    
    fm = FileManager()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "cleanup":
            dry_run = "--dry-run" in sys.argv
            fm.cleanup_old_files(dry_run=dry_run)
        
        elif command == "usage":
            usage = fm.get_storage_usage()
            print(" STORAGE USAGE:")
            for folder, stats in usage.items():
                print(f"  {folder}: {stats['files']} files, {stats['mb']} MB")
        
        elif command == "setup":
            fm.setup_directories()
            print(" Directory structure created")
        
        else:
            print("Usage: python file_manager.py [cleanup|usage|setup] [--dry-run]")
    
    else:
        print("File Manager - Close Apollo Integration")
        print("Commands:")
        print("  setup    - Create directory structure")
        print("  cleanup  - Clean up old files (add --dry-run to preview)")
        print("  usage    - Show storage usage")


if __name__ == "__main__":
    main()
