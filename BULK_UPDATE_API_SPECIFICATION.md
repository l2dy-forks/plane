# Bulk Update Issues API Specification

## Overview

This document provides a comprehensive API specification for implementing the bulk update operations endpoint that the `handleBulkUpdate()` function requires. This endpoint allows updating multiple issues with various properties in a single API call.

## API Endpoint

**Endpoint:** `POST /api/workspaces/{workspaceSlug}/projects/{projectId}/bulk-operation-issues/`

**Authentication:** Required (JWT/Session)

**Permissions:** `ROLE.ADMIN` or `ROLE.MEMBER`

## Request Structure

### URL Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `workspaceSlug` | string | Yes | The workspace slug identifier |
| `projectId` | UUID | Yes | The project UUID |

### Request Body

```json
{
  "issue_ids": ["uuid1", "uuid2", "uuid3"],
  "properties": {
    "state_id": "uuid",
    "priority": "high" | "medium" | "low" | "urgent" | null,
    "label_ids": ["uuid1", "uuid2"],
    "assignee_ids": ["uuid1", "uuid2"],
    "start_date": "YYYY-MM-DD" | null,
    "target_date": "YYYY-MM-DD" | null,
    "module_ids": ["uuid1", "uuid2"] | null,
    "cycle_id": "uuid" | null,
    "estimate_point": "uuid" | null
  }
}
```

### Request Body Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `issue_ids` | array[string] | Yes | Array of issue UUIDs to update |
| `properties` | object | Yes | Object containing properties to update |
| `properties.state_id` | string (UUID) | No | State UUID to assign to issues |
| `properties.priority` | string | No | Priority level: "urgent", "high", "medium", "low", or null |
| `properties.label_ids` | array[string] | No | Array of label UUIDs to assign |
| `properties.assignee_ids` | array[string] | No | Array of user UUIDs to assign |
| `properties.start_date` | string (date) | No | Start date in YYYY-MM-DD format or null |
| `properties.target_date` | string (date) | No | Target date in YYYY-MM-DD format or null |
| `properties.module_ids` | array[string] | No | Array of module UUIDs to assign or null |
| `properties.cycle_id` | string (UUID) | No | Cycle UUID to assign or null |
| `properties.estimate_point` | string (UUID) | No | Estimate point UUID or null |

## Response Structure

### Success Response (200 OK)

```json
{
  "message": "Issues updated successfully",
  "updated_issues": 5,
  "issues": [
    {
      "id": "uuid",
      "updated_properties": ["state_id", "priority"]
    }
  ]
}
```

### Error Responses

#### 400 Bad Request - Missing issue IDs
```json
{
  "error": "Issue IDs are required"
}
```

#### 400 Bad Request - Invalid date range
```json
{
  "error": "Start date cannot exceed target date",
  "details": {
    "issue_id": "uuid",
    "start_date": "2024-06-01",
    "target_date": "2024-05-01"
  }
}
```

#### 400 Bad Request - Invalid property values
```json
{
  "error": "Invalid property values",
  "details": {
    "invalid_state_id": ["uuid1"],
    "invalid_assignee_ids": ["uuid2"],
    "invalid_label_ids": ["uuid3"]
  }
}
```

#### 403 Forbidden
```json
{
  "error": "You do not have permission to update issues in this project"
}
```

#### 404 Not Found - Project or Workspace
```json
{
  "error": "Project not found"
}
```

## Validation Rules

### Input Validation

1. **issue_ids**: Must be a non-empty array of valid UUIDs
2. **properties**: Must contain at least one property to update
3. **Date validation**: `start_date` must be <= `target_date` if both are provided
4. **State validation**: `state_id` must exist and belong to the project
5. **User validation**: All `assignee_ids` must be valid project members
6. **Label validation**: All `label_ids` must exist and belong to the project
7. **Module validation**: All `module_ids` must exist and belong to the project
8. **Cycle validation**: `cycle_id` must exist and belong to the project
9. **Estimate validation**: `estimate_point` must exist and belong to the project's estimate system

### Business Rules

1. **Permission check**: User must have ADMIN or MEMBER role in the project
2. **Issue ownership**: All issues must belong to the specified project
3. **Concurrent updates**: Handle optimistic locking for concurrent modifications
4. **Array properties**: For array properties (labels, assignees, modules), the operation replaces the entire array
5. **Null values**: Explicitly handle null values to clear properties

## Implementation Guidelines

### Database Operations

1. **Bulk operations**: Use Django's `bulk_update()` for efficient database updates
2. **Batch size**: Process updates in batches of 100 issues maximum
3. **Transaction handling**: Wrap the entire operation in a database transaction
4. **Related models**: Update related junction tables (IssueAssignee, IssueLabel, ModuleIssue, CycleIssue)

### Activity Tracking

Create activity records for each updated property:

```python
issue_activity.delay(
    type="issue.activity.updated",
    requested_data=json.dumps({"property_name": new_value}),
    current_instance=json.dumps({"property_name": old_value}),
    issue_id=str(issue.id),
    actor_id=str(request.user.id),
    project_id=str(project_id),
    epoch=int(timezone.now().timestamp()),
    notification=True,
    origin=base_host(request=request, is_app=True),
)
```

### Error Handling

1. **Partial failures**: If some issues fail validation, return details about which issues failed
2. **Rollback**: On critical errors, rollback the entire transaction
3. **Logging**: Log all bulk operations for audit purposes

## Implementation Example

Based on existing patterns in the codebase, here's the recommended implementation structure:

```python
class BulkOperationIssuesEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]
    
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id):
        # Validate request data
        issue_ids = request.data.get("issue_ids", [])
        properties = request.data.get("properties", {})
        
        if not issue_ids:
            return Response(
                {"error": "Issue IDs are required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if not properties:
            return Response(
                {"error": "Properties to update are required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate and process bulk update
        try:
            with transaction.atomic():
                result = self.process_bulk_update(
                    slug, project_id, issue_ids, properties, request.user
                )
                return Response(result, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
```

## URL Configuration

Add to `apiserver/plane/app/urls/issue.py`:

```python
path(
    "workspaces/<str:slug>/projects/<uuid:project_id>/bulk-operation-issues/",
    BulkOperationIssuesEndpoint.as_view(),
    name="bulk-operation-issues",
),
```

## Testing Considerations

### Test Cases

1. **Valid bulk update**: Update multiple properties across multiple issues
2. **Invalid issue IDs**: Test with non-existent issue IDs
3. **Permission validation**: Test with users without proper permissions
4. **Date validation**: Test invalid date combinations
5. **Partial updates**: Test updates with some valid and some invalid data
6. **Large batches**: Test performance with large numbers of issues
7. **Concurrent updates**: Test handling of concurrent modifications

### Performance Testing

1. **Batch size limits**: Test with different batch sizes (100, 500, 1000 issues)
2. **Property combinations**: Test updating different combinations of properties
3. **Database load**: Monitor database query count and execution time

## Migration Considerations

### Database Indexes

Ensure proper indexes exist for:
- `issue.project_id`
- `issue.workspace_id`
- `issue.state_id`
- `issue_assignee.issue_id`
- `issue_label.issue_id`
- `module_issue.issue_id`
- `cycle_issue.issue_id`

### Backward Compatibility

This is a new endpoint and doesn't affect existing functionality. No migration of existing data is required.

## Security Considerations

1. **Input sanitization**: Validate all input parameters
2. **SQL injection**: Use parameterized queries only
3. **Rate limiting**: Implement appropriate rate limiting for bulk operations
4. **Audit logging**: Log all bulk update operations with user details
5. **Permission checks**: Verify user permissions for each affected issue

## Related Endpoints

This endpoint complements existing bulk operations:
- `POST /api/workspaces/{slug}/projects/{projectId}/bulk-delete-issues/`
- `POST /api/workspaces/{slug}/projects/{projectId}/bulk-archive-issues/`
- `POST /api/workspaces/{slug}/projects/{projectId}/issues/bulk-update-date/`

## Frontend Integration

The endpoint is called from:
- `web/core/services/issue/issue.service.ts` - `bulkOperations()` method
- `web/core/store/issue/helpers/base-issues.store.ts` - `bulkUpdateProperties()` method
- `web/ce/components/issues/bulk-operations/toolbar.tsx` - `handleBulkUpdate()` function

The frontend expects the API to return successfully updated issues and handle any validation errors appropriately.
