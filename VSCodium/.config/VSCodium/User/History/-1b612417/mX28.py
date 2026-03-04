"""
Pytest tests for share-link affix endpoints.

These tests use FastAPI TestClient to test the share-link affix endpoints.
All test data is configurable via variables at the top of this file.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import json


# =============================================================================
# TEST DATA CONFIGURATION - UPDATE THESE VALUES FOR YOUR ENVIRONMENT
# =============================================================================

# Session token for creating share links
TEST_SESSION_TOKEN = "REKY3yBDKJXU4zhmdFQDZTvT2u1yblER"

# Partition UUID
TEST_PARTITION_UUID = "4f4ea54e-8d71-4bc2-84ee-97c6e6576485"

# Entity UUIDs to test (should exist in your database)
TEST_ENTITY_UUIDS = {
    "issue": "dd20d726-240e-4576-aaf7-68bded526088",
    "qaDocument": "e39a9c3e-7e18-4f63-a93f-a12947955ed9",
    "projectDocument": "983df5bc-a0d2-448e-9109-e21f1c367df9",
    "project": "6d92a576-7cd5-4f77-ab2a-08b155f0673e",
}

# Affix UUIDs to test (should exist in your database and belong to the entities above)
TEST_AFFIX_UUIDS = {
    "issue": [],  # Add affix UUIDs for issue entity
    "qaDocument": [],  # Add affix UUIDs for qaDocument entity
    "projectDocument": [],  # Add affix UUIDs for projectDocument entity
    "project": [],  # Add affix UUIDs for project entity
}

# Share link expiration time (in seconds)
EXPIRES_IN_SECONDS = 86400

# Base URL for share links
SHARE_LINK_BASE_URL = "https://w54.p3.54origins.com/share/"


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from service54 import app
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Create a mock database adapter."""
    db = AsyncMock()
    return db


@pytest.fixture
def mock_share_token_dependency():
    """Mock the share_token_dependency to return a valid share token."""
    async def mock_dependency(request, db):
        # Set the anonymous link entity and partition in request.state
        request.state.anonymous_link_entity = list(TEST_ENTITY_UUIDS.values())[0]
        request.state.anonymous_link_partition = "project_management"
        return "test_share_token_abc123"
    
    return mock_dependency


@pytest.fixture
def mock_token_required():
    """Mock the token_required decorator to bypass authentication."""
    async def mock_decorator(request):
        # Set a mock actor in request.state
        request.state.actor = MagicMock()
        request.state.actor.uuid = uuid4()
        return True
    
    return mock_decorator


@pytest.fixture
def mock_get_db_connection():
    """Mock the get_db_connection_for_submodule dependency."""
    async def mock_get_db():
        db = AsyncMock()
        return db
    
    return mock_get_db


# =============================================================================
# TESTS: POST /share-link/affix/list
# =============================================================================

class TestShareLinkAffixList:
    """Tests for POST /share-link/affix/list endpoint."""

    def test_affix_list_empty_body(self, client, mock_share_token_dependency, mock_get_db_connection):
        """Test affix list with empty request body."""
        with patch('service54.core.dependencies.share_token_dependency', mock_share_token_dependency):
            with patch('service54.auth_perms.fast_api.dependencies.get_db_connection_for_submodule', mock_get_db_connection):
                # Mock the AffixListAction.execute() to return empty list
                with patch('service54.actions.get_affix.AffixListAction.execute') as mock_execute:
                    mock_execute.return_value = {
                        "affix_uuids": [],
                        "total": 0
                    }
                    
                    response = client.post(
                        "/share-link/affix/list",
                        headers={"Share-Token": "test_share_token_abc123"},
                        json={}
                    )
                    
                    # Should return 200 with empty list
                    assert response.status_code == 200
                    data = response.json()
                    assert "affix_uuids" in data
                    assert data["affix_uuids"] == []
                    assert data["total"] == 0

    def test_affix_list_with_limit(self, client, mock_share_token_dependency, mock_get_db_connection):
        """Test affix list with limit parameter."""
        with patch('service54.core.dependencies.share_token_dependency', mock_share_token_dependency):
            with patch('service54.auth_perms.fast_api.dependencies.get_db_connection_for_submodule', mock_get_db_connection):
                # Mock the AffixListAction.execute() to return some affixes
                with patch('service54.actions.get_affix.AffixListAction.execute') as mock_execute:
                    mock_execute.return_value = {
                        "affix_uuids": [str(uuid4()), str(uuid4())],
                        "total": 2
                    }
                    
                    response = client.post(
                        "/share-link/affix/list",
                        headers={"Share-Token": "test_share_token_abc123"},
                        json={"limit": 10}
                    )
                    
                    # Should return 200 with affix list
                    assert response.status_code == 200
                    data = response.json()
                    assert "affix_uuids" in data
                    assert len(data["affix_uuids"]) == 2
                    assert data["total"] == 2

    def test_affix_list_with_affix_type_filter(self, client, mock_share_token_dependency, mock_get_db_connection):
        """Test affix list with affix_type filter."""
        with patch('service54.core.dependencies.share_token_dependency', mock_share_token_dependency):
            with patch('service54.auth_perms.fast_api.dependencies.get_db_connection_for_submodule', mock_get_db_connection):
                # Mock the AffixListAction.execute() to return filtered affixes
                with patch('service54.actions.get_affix.AffixListAction.execute') as mock_execute:
                    mock_execute.return_value = {
                        "affix_uuids": [str(uuid4())],
                        "total": 1
                    }
                    
                    response = client.post(
                        "/share-link/affix/list",
                        headers={"Share-Token": "test_share_token_abc123"},
                        json={"affix_type": "comment", "limit": 10}
                    )
                    
                    # Should return 200 with filtered affix list
                    assert response.status_code == 200
                    data = response.json()
                    assert "affix_uuids" in data
                    assert len(data["affix_uuids"]) == 1
                    assert data["total"] == 1

    def test_affix_list_with_offset_and_order(self, client, mock_share_token_dependency, mock_get_db_connection):
        """Test affix list with offset and order parameters."""
        with patch('service54.core.dependencies.share_token_dependency', mock_share_token_dependency):
            with patch('service54.auth_perms.fast_api.dependencies.get_db_connection_for_submodule', mock_get_db_connection):
                # Mock the AffixListAction.execute() to return paginated affixes
                with patch('service54.actions.get_affix.AffixListAction.execute') as mock_execute:
                    mock_execute.return_value = {
                        "affix_uuids": [str(uuid4())],
                        "total": 5
                    }
                    
                    response = client.post(
                        "/share-link/affix/list",
                        headers={"Share-Token": "test_share_token_abc123"},
                        json={"limit": 1, "offset": 0, "order": "desc", "order_by": "created"}
                    )
                    
                    # Should return 200 with paginated affix list
                    assert response.status_code == 200
                    data = response.json()
                    assert "affix_uuids" in data
                    assert len(data["affix_uuids"]) == 1
                    assert data["total"] == 5

    def test_affix_list_missing_share_token(self, client):
        """Test affix list without Share-Token header."""
        response = client.post(
            "/share-link/affix/list",
            json={}
        )
        
        # Should return 403 (missing Share-Token)
        assert response.status_code == 403


# =============================================================================
# TESTS: POST /share-link/affix/read
# =============================================================================

class TestShareLinkAffixRead:
    """Tests for POST /share-link/affix/read endpoint."""

    def test_affix_read_missing_affix_uuids(self, client, mock_share_token_dependency, mock_get_db_connection):
        """Test affix read without affix_uuid or affix_uuids (should fail validation)."""
        with patch('service54.core.dependencies.share_token_dependency', mock_share_token_dependency):
            with patch('service54.auth_perms.fast_api.dependencies.get_db_connection_for_submodule', mock_get_db_connection):
                response = client.post(
                    "/share-link/affix/read",
                    headers={"Share-Token": "test_share_token_abc123"},
                    json={"limit": 10}
                )
                
                # Should return 422 (validation error - missing affix_uuid/affix_uuids)
                assert response.status_code == 422
                data = response.json()
                assert "detail" in data

    def test_affix_read_empty_affix_uuids(self, client, mock_share_token_dependency, mock_get_db_connection):
        """Test affix read with empty affix_uuids list (should fail validation)."""
        with patch('service54.core.dependencies.share_token_dependency', mock_share_token_dependency):
            with patch('service54.auth_perms.fast_api.dependencies.get_db_connection_for_submodule', mock_get_db_connection):
                response = client.post(
                    "/share-link/affix/read",
                    headers={"Share-Token": "test_share_token_abc123"},
                    json={"affix_uuids": []}
                )
                
                # Should return 422 (validation error - empty affix_uuids)
                assert response.status_code == 422
                data = response.json()
                assert "detail" in data

    def test_affix_read_with_affix_uuids(self, client, mock_share_token_dependency, mock_get_db_connection):
        """Test affix read with valid affix_uuids."""
        affix_uuids = [str(uuid4()), str(uuid4())]
        
        with patch('service54.core.dependencies.share_token_dependency', mock_share_token_dependency):
            with patch('service54.auth_perms.fast_api.dependencies.get_db_connection_for_submodule', mock_get_db_connection):
                # Mock the database check for affix ownership
                mock_db = AsyncMock()
                mock_db.fetchall.return_value = [
                    {"uuid": affix_uuids[0]},
                    {"uuid": affix_uuids[1]}
                ]
                
                # Mock the AffixReadAction.execute() to return affix data
                with patch('service54.actions.get_affix.AffixReadAction.execute') as mock_execute:
                    mock_execute.return_value = [
                        {
                            "uuid": affix_uuids[0],
                            "affix_type": "comment",
                            "entity_uuid": str(uuid4()),
                            "actor_uuid": str(uuid4()),
                            "params": {},
                            "files": []
                        },
                        {
                            "uuid": affix_uuids[1],
                            "affix_type": "comment",
                            "entity_uuid": str(uuid4()),
                            "actor_uuid": str(uuid4()),
                            "params": {},
                            "files": []
                        }
                    ]
                    
                    with patch('service54.views.anonymous_link_views.AsyncDatabaseAdapter', return_value=mock_db):
                        response = client.post(
                            "/share-link/affix/read",
                            headers={"Share-Token": "test_share_token_abc123"},
                            json={"affix_uuids": affix_uuids}
                        )
                        
                        # Should return 200 with affix data
                        assert response.status_code == 200
                        data = response.json()
                        assert isinstance(data, list)
                        assert len(data) == 2

    def test_affix_read_affix_not_belonging_to_entity(self, client, mock_share_token_dependency, mock_get_db_connection):
        """Test affix read with affix_uuids that don't belong to the shared entity."""
        affix_uuids = [str(uuid4())]
        
        with patch('service54.core.dependencies.share_token_dependency', mock_share_token_dependency):
            with patch('service54.auth_perms.fast_api.dependencies.get_db_connection_for_submodule', mock_get_db_connection):
                # Mock the database check to return empty (affix doesn't belong to entity)
                mock_db = AsyncMock()
                mock_db.fetchall.return_value = []
                
                with patch('service54.views.anonymous_link_views.AsyncDatabaseAdapter', return_value=mock_db):
                    response = client.post(
                        "/share-link/affix/read",
                        headers={"Share-Token": "test_share_token_abc123"},
                        json={"affix_uuids": affix_uuids}
                    )
                    
                    # Should return 403 (affix doesn't belong to shared entity)
                    assert response.status_code == 403
                    data = response.json()
                    assert "detail" in data

    def test_affix_read_missing_share_token(self, client):
        """Test affix read without Share-Token header."""
        response = client.post(
            "/share-link/affix/read",
            json={"affix_uuids": [str(uuid4())]}
        )
        
        # Should return 403 (missing Share-Token)
        assert response.status_code == 403


# =============================================================================
# TESTS: Integration - Create Share Link and Test Affix Endpoints
# =============================================================================

class TestShareLinkAffixIntegration:
    """Integration tests for share-link affix endpoints."""

    def test_create_share_link_and_list_affixes(self, client, mock_token_required, mock_get_db_connection):
        """Test creating a share link and then listing affixes."""
        entity_uuid = TEST_ENTITY_UUIDS["issue"]
        
        with patch('service54.auth_perms.fast_api.decorators.token_required', mock_token_required):
            with patch('service54.auth_perms.fast_api.dependencies.get_db_connection_for_submodule', mock_get_db_connection):
                # Mock the database operations
                mock_db = AsyncMock()
                mock_db.fetchone.return_value = {"uuid": str(uuid4()), "created": "2024-01-01T00:00:00"}
                
                # Mock check_exist to return True (entity exists)
                with patch('service54.actions.get_affix.AffixListAction.check_exist', return_value=True):
                    with patch('service54.views.anonymous_link_views.AsyncDatabaseAdapter', return_value=mock_db):
                        # Step 1: Create share link
                        create_response = client.post(
                            "/share-link/create",
                            headers={
                                "Session-Token": TEST_SESSION_TOKEN,
                                "Partition-Uuid": TEST_PARTITION_UUID
                            },
                            json={
                                "url": SHARE_LINK_BASE_URL,
                                "entity_uuid": entity_uuid,
                                "expires_at": "2025-12-31T23:59:59Z"
                            }
                        )
                        
                        # Create share link should return 200
                        assert create_response.status_code == 200
                        create_data = create_response.json()
                        assert "token" in create_data
                        share_token = create_data["token"]
