# db/managers/reporting_manager.py
from typing import Dict, List, Any
from datetime import date
from source.db.base_managers.base_manager import BaseManager


class ReportingManager(BaseManager):
    """Manages reporting database operations"""

    async def create_report_record(self, report_name: str, report_type: str,
                                   account_id: str = None, report_date: date = None,
                                   **kwargs) -> str:
        """Create a report record"""
        query = """
            INSERT INTO reporting.report_catalog
            (report_name, report_type, account_id, report_date, file_path,
             file_size_bytes, status, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING report_id
        """

        result = await self.execute_returning(
            query, report_name, report_type, account_id,
            report_date or date.today(), kwargs.get('file_path'),
            kwargs.get('file_size_bytes'), kwargs.get('status', 'PENDING'),
            kwargs.get('created_by', 'SYSTEM')
        )

        return str(result['report_id']) if result else None

    async def get_reports(self, account_id: str = None, report_date: date = None,
                          report_type: str = None) -> List[Dict[str, Any]]:
        """Get reports with optional filters"""
        filters = {}
        if account_id:
            filters['account_id'] = account_id
        if report_date:
            filters['report_date'] = report_date
        if report_type:
            filters['report_type'] = report_type

        where_clause, params = self.build_where_clause(filters)

        query = f"""
            SELECT * FROM reporting.report_catalog
            WHERE {where_clause}
            ORDER BY created_at DESC
        """

        return await self.fetch_all(query, *params)
