"""
ServiceNow REST API client.

Provides methods for interacting with ServiceNow Table API:
- Get incidents by number
- Update incidents with work notes
- Add customer-visible comments
- Resolve incidents

Usage:
    from servicenow.config import ServiceNowConfig
    from servicenow.client import ServiceNowClient

    config = ServiceNowConfig.from_secrets_manager()
    with ServiceNowClient(config) as client:
        incident = client.get_incident("INC0001234")
        client.add_work_notes("INC0001234", "Analysis in progress", state="2")
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from .config import ServiceNowConfig
except ImportError:
    from config import ServiceNowConfig

logger = logging.getLogger(__name__)

# ServiceNow incident states
INCIDENT_STATES = {
    "NEW": "1",
    "IN_PROGRESS": "2",
    "ON_HOLD": "3",
    "RESOLVED": "6",
    "CLOSED": "7",
    "CANCELED": "8",
}


class ServiceNowError(Exception):
    """Custom exception for ServiceNow API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class ServiceNowClient:
    """Client for ServiceNow Table API operations."""

    def __init__(self, config: ServiceNowConfig, timeout: int = 30):
        """
        Initialize ServiceNow client.

        Args:
            config: ServiceNowConfig instance with credentials.
            timeout: Request timeout in seconds.
        """
        self.config = config
        self.timeout = timeout
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create and configure requests session with retry logic."""
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PATCH", "PUT"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        # Set default headers
        session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

        # Set basic auth
        session.auth = self.config.get_basic_auth()

        return session

    def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to ServiceNow API.

        Args:
            method: HTTP method (GET, POST, PATCH, PUT).
            url: Full API URL.
            params: Query parameters.
            json_data: JSON body data.

        Returns:
            Parsed JSON response.

        Raises:
            ServiceNowError: If request fails.
        """
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                timeout=self.timeout,
            )

            # Log request details
            logger.debug(f"{method} {url} -> {response.status_code}")

            # Handle errors
            if not response.ok:
                error_detail = response.text
                try:
                    error_json = response.json()
                    if "error" in error_json:
                        error_detail = error_json["error"].get("message", error_detail)
                except Exception:
                    pass

                raise ServiceNowError(
                    f"ServiceNow API error: {error_detail}",
                    status_code=response.status_code,
                    response=response.json() if response.text else None,
                )

            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise ServiceNowError(f"Request failed: {str(e)}")

    def get_incident(self, number: str) -> Dict[str, Any]:
        """
        Get incident by number.

        Args:
            number: Incident number (e.g., 'INC0001234').

        Returns:
            Incident record dictionary.

        Raises:
            ServiceNowError: If incident not found or request fails.
        """
        url = self.config.build_table_api_url("incident")
        params = {
            "sysparm_query": f"number={number}",
            "sysparm_limit": 1,
        }

        logger.info(f"Getting incident: {number}")
        response = self._request("GET", url, params=params)

        results = response.get("result", [])
        if not results:
            raise ServiceNowError(f"Incident {number} not found", status_code=404)

        return results[0]

    def get_incident_by_sys_id(self, sys_id: str) -> Dict[str, Any]:
        """
        Get incident by sys_id.

        Args:
            sys_id: ServiceNow sys_id.

        Returns:
            Incident record dictionary.
        """
        url = self.config.build_table_api_url("incident", sys_id)
        logger.info(f"Getting incident by sys_id: {sys_id}")
        response = self._request("GET", url)
        return response.get("result", {})

    def update_incident(self, sys_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update incident by sys_id.

        Args:
            sys_id: ServiceNow sys_id of the incident.
            data: Dictionary of fields to update.

        Returns:
            Updated incident record.
        """
        url = self.config.build_table_api_url("incident", sys_id)
        logger.info(f"Updating incident {sys_id}: {list(data.keys())}")
        response = self._request("PATCH", url, json_data=data)
        return response.get("result", {})

    def add_work_notes(
        self,
        number: str,
        notes: str,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add work notes to an incident and optionally change state.

        Work notes are internal notes visible only to support staff.

        Args:
            number: Incident number (e.g., 'INC0001234').
            notes: Work notes text to add.
            state: Optional new state (use INCIDENT_STATES constants).

        Returns:
            Updated incident record.

        Raises:
            ServiceNowError: If incident not found or update fails.
        """
        # First get the incident to get sys_id
        incident = self.get_incident(number)
        sys_id = incident["sys_id"]

        # Prepare update data
        update_data = {"work_notes": notes}
        if state:
            update_data["state"] = state

        logger.info(f"Adding work notes to {number}, state={state}")
        return self.update_incident(sys_id, update_data)

    def add_comment(self, number: str, comment: str) -> Dict[str, Any]:
        """
        Add customer-visible comment to an incident.

        Comments are visible to the customer/requester.

        Args:
            number: Incident number (e.g., 'INC0001234').
            comment: Comment text to add.

        Returns:
            Updated incident record.
        """
        incident = self.get_incident(number)
        sys_id = incident["sys_id"]

        logger.info(f"Adding comment to {number}")
        return self.update_incident(sys_id, {"comments": comment})

    def resolve_incident(
        self,
        number: str,
        resolution_notes: str,
        resolution_code: str = "Solved (Permanently)",
    ) -> Dict[str, Any]:
        """
        Resolve an incident.

        Args:
            number: Incident number (e.g., 'INC0001234').
            resolution_notes: Notes explaining the resolution.
            resolution_code: Resolution code (default: 'Solved (Permanently)').

        Returns:
            Updated incident record.
        """
        incident = self.get_incident(number)
        sys_id = incident["sys_id"]

        update_data = {
            "state": INCIDENT_STATES["RESOLVED"],
            "close_code": resolution_code,
            "close_notes": resolution_notes,
        }

        logger.info(f"Resolving incident {number}")
        return self.update_incident(sys_id, update_data)

    def search_incidents(
        self,
        query: str,
        limit: int = 10,
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search incidents with a query.

        Args:
            query: ServiceNow encoded query string.
            limit: Maximum number of results.
            fields: List of fields to return (default: all).

        Returns:
            List of matching incident records.
        """
        url = self.config.build_table_api_url("incident")
        params = {
            "sysparm_query": query,
            "sysparm_limit": limit,
        }
        if fields:
            params["sysparm_fields"] = ",".join(fields)

        logger.info(f"Searching incidents: {query[:50]}...")
        response = self._request("GET", url, params=params)
        return response.get("result", [])

    def __enter__(self) -> "ServiceNowClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - close session."""
        self.close()

    def close(self) -> None:
        """Close the HTTP session."""
        if self.session:
            self.session.close()
            logger.debug("ServiceNow client session closed")
