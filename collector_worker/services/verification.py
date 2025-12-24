from loguru import logger
from database import Database
import json
import sys

class VerificationService:
    def __init__(self):
        self.db_instance = Database()

    def run_full_verification(self, exit_on_failure=False):
        """
        Orchestrates full database structure verification.
        Uses Database methods for actions and loguru for reporting.
        """
        logger.info("Starting Database Structure Verification...")
        
        try:
            # 1. Connectivity
            self.db_instance.ping()
            logger.debug("MongoDB connectivity confirmed.")

            # 2. Collections
            col_report = self.db_instance.ensure_collections()
            created = col_report.get("created", [])
            existing = col_report.get("existing", [])
            
            if created:
                logger.info(f"Collections initialized: {', '.join(created)}")
            logger.debug(f"Collections verified: {', '.join(existing)}")

            # 3. Indices
            self.db_instance.ensure_indices()
            logger.debug("Database indices ensured.")

            # 4. Detailed Reporting (optional debug info)
            all_cols = existing + created
            for col in all_cols:
                idxs = self.db_instance.get_indices(col)
                if len(idxs) > 1:
                    logger.debug(f"Indices for '{col}': {', '.join(idxs)}")
                elif col in ["clients", "bills"]:
                    logger.warning(f"Collection '{col}' might be missing performance indices.")

            logger.success("Database structure verification completed successfully.")
            return True

        except Exception as e:
            logger.error(f"Database verification FAILED: {e}")
            if exit_on_failure:
                sys.exit(1)
            return False

    def get_detailed_report(self):
        """Returns a summary of the current database structure."""
        try:
            col_report = self.db_instance.ensure_collections()
            indices = {col: self.db_instance.get_indices(col) for col in (col_report['existing'] + col_report['created'])}
            return {
                "status": "ok",
                "collections": col_report,
                "indices": indices
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
