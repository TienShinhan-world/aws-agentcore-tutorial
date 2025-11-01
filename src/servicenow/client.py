"""
ServiceNow API Client

This module provides a client for interacting with ServiceNow REST API.
Supports ticket updates, work notes, and state changes.
"""
import json
import logging
from typing import Dict, Any, Optional, List
import requests
from requests.auth import HTTPBasicAuth

from .config import ServiceNowConfig, get_config


logger = logging.getLogger(__name__)


class ServiceNowError(Exception):
    """Base exception for ServiceNow API errors"""
    pass


class ServiceNowClient:
    """
    Client for ServiceNow REST API interactions.

    This client handles authentication, request formatting, and error handling
    for common ServiceNow operations like updating tickets and adding work notes.
    """

    def __init__(self, config: Optional[ServiceNowConfig] = None):
        """
        Initialize ServiceNow client.

        Args:
            config: ServiceNowConfig object. If None, loads from environment.
        """
        self.config = config or get_config()
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """
        Create and configure a requests session with authentication.

        Returns:
            requests.Session: Configured session
        """
        session = requests.Session()

        # Set authentication
        if self.config.oauth_token:
            session.headers["Authorization"] = f"Bearer {self.config.oauth_token}"
        elif self.config.username and self.config.password:
            session.auth = HTTPBasicAuth(self.config.username, self.config.password)
        else:
            raise ServiceNowError("No authentication method configured")

        # Set common headers
        session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

        return session

    def _make_request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to ServiceNow API.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH)
            url: Full API URL
            data: Request body data
            params: Query parameters

        Returns:
            Dict: Response JSON data

        Raises:
            ServiceNowError: If the request fails
        """
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl
            )

            # Log request details
            logger.info(
                f"ServiceNow API request: {method} {url} "
                f"(status: {response.status_code})"
            )

            response.raise_for_status()

            # Parse response
            if response.content:
                return response.json()
            return {}

        except requests.exceptions.HTTPError as e:
            error_msg = f"ServiceNow API HTTP error: {e}"
            if e.response is not None:
                try:
                    error_detail = e.response.json()
                    error_msg += f" - {json.dumps(error_detail)}"
                except:
                    error_msg += f" - {e.response.text}"
            logger.error(error_msg)
            raise ServiceNowError(error_msg) from e

        except requests.exceptions.RequestException as e:
            error_msg = f"ServiceNow API request error: {e}"
            logger.error(error_msg)
            raise ServiceNowError(error_msg) from e

    def get_incident(self, number: str) -> Dict[str, Any]:
        """
        Get incident details by incident number.

        Args:
            number: Incident number (e.g., 'INC0001234')

        Returns:
            Dict: Incident record data

        Raises:
            ServiceNowError: If the incident is not found or request fails
        """
        url = self.config.get_table_api_url("incident")
        params = {
            "sysparm_query": f"number={number}",
            "sysparm_limit": "1"
        }

        result = self._make_request("GET", url, params=params)

        if not result.get("result"):
            raise ServiceNowError(f"Incident {number} not found")

        return result["result"][0]

    def update_incident(
        self,
        number: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an incident by incident number.

        Args:
            number: Incident number (e.g., 'INC0001234')
            updates: Dictionary of fields to update

        Returns:
            Dict: Updated incident record

        Raises:
            ServiceNowError: If the update fails
        """
        # First get the sys_id
        incident = self.get_incident(number)
        sys_id = incident["sys_id"]

        # Update the incident
        url = self.config.get_record_url("incident", sys_id)
        result = self._make_request("PATCH", url, data=updates)

        logger.info(f"Updated incident {number} (sys_id: {sys_id})")

        return result.get("result", {})

    def add_work_notes(
        self,
        number: str,
        work_notes: str,
        state: Optional[str] = None,
        additional_updates: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add work notes to an incident and optionally update state.

        Args:
            number: Incident number (e.g., 'INC0001234')
            work_notes: Work notes text to add
            state: Optional state to set (e.g., '2' for In Progress, '6' for Resolved)
            additional_updates: Optional additional fields to update

        Returns:
            Dict: Updated incident record

        Raises:
            ServiceNowError: If the update fails
        """
        updates = {
            "work_notes": work_notes
        }

        if state is not None:
            updates["state"] = state

        if additional_updates:
            updates.update(additional_updates)

        return self.update_incident(number, updates)

    def resolve_incident(
        self,
        number: str,
        resolution_notes: str,
        resolution_code: str = "Solved (Permanently)"
    ) -> Dict[str, Any]:
        """
        Resolve an incident with resolution notes.

        Args:
            number: Incident number
            resolution_notes: Resolution notes/description
            resolution_code: Resolution code (default: 'Solved (Permanently)')

        Returns:
            Dict: Updated incident record

        Raises:
            ServiceNowError: If the update fails
        """
        updates = {
            "state": "6",  # 6 = Resolved
            "close_notes": resolution_notes,
            "close_code": resolution_code
        }

        logger.info(f"Resolving incident {number}")

        return self.update_incident(number, updates)

    def set_incident_in_progress(
        self,
        number: str,
        work_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Set incident state to 'In Progress'.

        Args:
            number: Incident number
            work_notes: Optional work notes to add

        Returns:
            Dict: Updated incident record

        Raises:
            ServiceNowError: If the update fails
        """
        updates = {"state": "2"}  # 2 = In Progress

        if work_notes:
            updates["work_notes"] = work_notes

        logger.info(f"Setting incident {number} to In Progress")

        return self.update_incident(number, updates)

    def query_incidents(
        self,
        query: str,
        limit: int = 10,
        fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Query incidents with a custom query string.

        Args:
            query: ServiceNow query string (e.g., 'state=1^priority=1')
            limit: Maximum number of results
            fields: Optional list of fields to return

        Returns:
            List[Dict]: List of incident records

        Raises:
            ServiceNowError: If the query fails
        """
        url = self.config.get_table_api_url("incident")
        params = {
            "sysparm_query": query,
            "sysparm_limit": str(limit)
        }

        if fields:
            params["sysparm_fields"] = ",".join(fields)

        result = self._make_request("GET", url, params=params)

        return result.get("result", [])

    def close(self):
        """Close the HTTP session"""
        self.session.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close session"""
        self.close()


# Convenience function for common use case
def update_ticket_with_resolution(
    ticket_number: str,
    resolution_notes: str,
    set_in_progress: bool = True
) -> Dict[str, Any]:
    """
    Convenience function to update a ticket with agent resolution.

    Args:
        ticket_number: Incident number (e.g., 'INC0001234')
        resolution_notes: Resolution notes from agent analysis
        set_in_progress: Whether to set state to In Progress (default: True)

    Returns:
        Dict: Updated incident data

    Raises:
        ServiceNowError: If the update fails
    """
    with ServiceNowClient() as client:
        if set_in_progress:
            return client.add_work_notes(
                number=ticket_number,
                work_notes=resolution_notes,
                state="2"  # In Progress
            )
        else:
            return client.add_work_notes(
                number=ticket_number,
                work_notes=resolution_notes
            )
