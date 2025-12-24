from loguru import logger
from database import Database
import json
import sys

class VerificationService:
    def __init__(self):
        self.db_instance = Database()

    def run_full_verification(self, exit_on_failure=False):
        """
        Runs a full database structure verification.
        Logs details using loguru.
        """
        logger.info("Starting Database Structure Verification...")
        
        try:
            report = self.db_instance.verify_structure()
            
            if report["status"] == "ok":
                logger.success("Database structure verification passed.")
                
                details = report.get("details", {})
                
                # Log collection info
                col_report = details.get("collections", {})
                existing = col_report.get("existing", [])
                created = col_report.get("created", [])
                
                if created:
                    logger.info(f"Collections created: {', '.join(created)}")
                
                logger.debug(f"Existing collections verified: {', '.join(existing)}")
                
                # Check for critical collections
                expected = ["clients", "bills", "history_action_log", "instance_config"]
                missing = [c for c in expected if c not in (existing + created)]
                if missing:
                    logger.warning(f"Critical collections missing (or not verified): {missing}")
                
                # Log indices info
                indices = details.get("indices", {})
                for col, idx_list in indices.items():
                    if len(idx_list) > 1: # _id_ is always index 0 usually
                        logger.debug(f"Indices for '{col}': {', '.join(idx_list)}")
                    elif col in ["clients", "bills"]:
                        logger.warning(f"Indices for '{col}' might be missing (only {len(idx_list)} found).")

                return True
            else:
                error_msg = report.get("error", "Unknown error during verification")
                logger.error(f"Database verification FAILED: {error_msg}")
                if exit_on_failure:
                    sys.exit(1)
                return False

        except Exception as e:
            logger.critical(f"Critical error during database verification: {e}")
            if exit_on_failure:
                sys.exit(1)
            return False

    def get_detailed_report(self):
        """Returns the raw report from the database instance."""
        return self.db_instance.verify_structure()
