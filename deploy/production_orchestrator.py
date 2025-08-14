#!/usr/bin/env python3
"""
Production Orchestrator for Close Apollo Integration
Integrates with file management system for reliable operation
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path

# Add the parent directory to Python path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from file_manager import FileManager
from master_orchestration import main as run_orchestrator


class ProductionOrchestrator:
    def __init__(self):
        self.fm = FileManager()
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def setup_environment(self):
        """Setup production environment"""
        # Ensure directories exist
        self.fm.setup_directories()
        
        # Setup logging
        import logging
        log_file = self.fm.get_log_path("orchestrator")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def run_pipeline(self, mode="production"):
        """Run the enrichment pipeline with file management"""
        try:
            self.logger.info(f"Starting pipeline session: {self.session_id}")
            
            # Create temporary working directory
            temp_files = []
            
            # Run the main orchestrator
            # Note: This will use the existing master_orchestration.py logic
            # but we'll capture and manage the files it creates
            
            self.logger.info("Launching orchestration pipeline...")
            
            # The orchestrator will create apollo_company_results.json and webhook_data.json
            # We need to move these to our managed storage after completion
            
            # For now, we'll call the existing orchestrator and then manage the files
            run_orchestrator()
            
            # After orchestrator completes, move files to managed storage
            self.manage_output_files()
            
            self.logger.info(f"Pipeline session completed: {self.session_id}")
            
        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}")
            raise
            
    def manage_output_files(self):
        """Move orchestrator output files to managed storage"""
        # List of files the orchestrator might create
        output_files = [
            "apollo_company_results.json",
            "webhook_data.json",
            "enrichment_results_production_*.json",
            "raw_apollo_results_*.json", 
            "raw_webhook_data_*.json"
        ]
        
        moved_files = []
        
        for pattern in output_files:
            if '*' in pattern:
                # Handle glob patterns
                import glob
                matches = glob.glob(pattern)
                for file_path in matches:
                    if os.path.exists(file_path):
                        new_path = self.move_to_managed_storage(file_path)
                        moved_files.append(new_path)
            else:
                # Handle exact filenames
                if os.path.exists(pattern):
                    new_path = self.move_to_managed_storage(pattern)
                    moved_files.append(new_path)
        
        self.logger.info(f"Moved {len(moved_files)} files to managed storage")
        return moved_files
        
    def move_to_managed_storage(self, file_path):
        """Move a file to the appropriate managed storage location"""
        import shutil
        
        filename = os.path.basename(file_path)
        
        # Determine destination based on file type
        if filename.startswith('enrichment_results_'):
            dest_dir = self.fm.data_dir / "results"
        elif filename.startswith('apollo_num_response') or filename.startswith('raw_webhook_'):
            dest_dir = self.fm.data_dir / "webhooks"
        elif filename.startswith('raw_apollo_results'):
            dest_dir = self.fm.data_dir / "results"
        else:
            dest_dir = self.fm.data_dir / "temp"
        
        # Create destination with session ID if not already present
        if self.session_id not in filename:
            name_parts = filename.split('.')
            new_filename = f"{name_parts[0]}_{self.session_id}.{'.'.join(name_parts[1:])}"
        else:
            new_filename = filename
            
        dest_path = dest_dir / new_filename
        
        # Move the file
        shutil.move(file_path, dest_path)
        self.logger.info(f"Moved {filename} → {dest_path}")
        
        return dest_path
        
    def cleanup_old_files(self):
        """Run file cleanup"""
        self.logger.info("Running file cleanup...")
        stats = self.fm.cleanup_old_files()
        
        total_deleted = sum(s["deleted"] for s in stats.values())
        total_freed = sum(s["bytes_freed"] for s in stats.values())
        
        self.logger.info(f"Cleanup complete: {total_deleted} files deleted, {total_freed / 1024:.1f} KB freed")
        return stats
        
    def get_status(self):
        """Get system status"""
        usage = self.fm.get_storage_usage()
        
        status = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "storage_usage": usage,
            "total_files": sum(u["files"] for u in usage.values()),
            "total_size_mb": sum(u["mb"] for u in usage.values())
        }
        
        return status


def main():
    """CLI interface for production orchestrator"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Close Apollo Integration - Production Orchestrator')
    parser.add_argument('command', choices=['run', 'cleanup', 'status', 'setup'], 
                       help='Command to execute')
    parser.add_argument('--mode', choices=['testing', 'production'], default='production',
                       help='Pipeline mode')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview cleanup without deleting files')
    
    args = parser.parse_args()
    
    orchestrator = ProductionOrchestrator()
    orchestrator.setup_environment()
    
    if args.command == 'run':
        orchestrator.run_pipeline(mode=args.mode)
        
    elif args.command == 'cleanup':
        if args.dry_run:
            orchestrator.fm.cleanup_old_files(dry_run=True)
        else:
            orchestrator.cleanup_old_files()
            
    elif args.command == 'status':
        status = orchestrator.get_status()
        print(json.dumps(status, indent=2))
        
    elif args.command == 'setup':
        orchestrator.fm.setup_directories()
        print("Production environment setup complete")


if __name__ == "__main__":
    main()
