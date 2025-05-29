# Bulk Actions Implementation Guide for Issues

This guide provides Python engineers with a comprehensive framework for implementing bulk action endpoints for issues in the Plane project. We'll use existing implementations (`BulkArchiveIssuesEndpoint` and `IssueBulkUpdateDateEndpoint`) as reference examples.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Basic Structure](#basic-structure)
3. [Implementation Examples](#implementation-examples)
4. [Step-by-Step Implementation Guide](#step-by-step-implementation-guide)
5. [Best Practices](#best-practices)
6. [Error Handling](#error-handling)
7. [Testing Considerations](#testing-considerations)

## Architecture Overview

Bulk action endpoints in Plane follow a consistent pattern:

- **Endpoint Type**: `BaseAPIView` (for simple operations) or `BaseViewSet` (for complex CRUD operations)
- **Permission System**: Role-based access control using `@allow_permission` decorator
- **Database Operations**: Django ORM with `bulk_update()` for performance
- **Activity Tracking**: Asynchronous activity logging using Celery tasks
- **Error Handling**: Comprehensive validation and error responses

## Basic Structure

### 1. Class Definition

```python
from plane.app.permissions import allow_permission, ROLE
from plane.utils.error_codes import ERROR_CODES
from rest_framework import status
from rest_framework.response import Response
from .. import BaseAPIView

class BulkActionEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]  # Optional: for additional permissions
    
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])  # Define allowed roles
    def post(self, request, slug, project_id):
        # Implementation here
        pass
```

### 2. URL Configuration

Add to `/apiserver/plane/app/urls/issue.py`:

```python
path(
    "workspaces/<str:slug>/projects/<uuid:project_id>/bulk-action-name/",
    BulkActionEndpoint.as_view(),
    name="bulk-action-name",
),
```

## Implementation Examples

### Example 1: BulkArchiveIssuesEndpoint

**Purpose**: Archive multiple issues that are in completed or cancelled states.

**Key Features**:
- State validation (only completed/cancelled issues can be archived)
- Individual activity logging for each issue
- Bulk database update for performance
- Error handling with specific error codes

```python
class BulkArchiveIssuesEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id):
        # 1. Extract and validate input
        issue_ids = request.data.get("issue_ids", [])
        
        if not len(issue_ids):
            return Response(
                {"error": "Issue IDs are required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Fetch issues with necessary relationships
        issues = Issue.objects.filter(
            workspace__slug=slug, 
            project_id=project_id, 
            pk__in=issue_ids
        ).select_related("state")
        
        # 3. Validate business rules
        bulk_archive_issues = []
        for issue in issues:
            if issue.state.group not in ["completed", "cancelled"]:
                return Response(
                    {
                        "error_code": ERROR_CODES["INVALID_ARCHIVE_STATE_GROUP"],
                        "error_message": "INVALID_ARCHIVE_STATE_GROUP",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            # 4. Log activity for each issue
            issue_activity.delay(
                type="issue.activity.updated",
                requested_data=json.dumps(
                    {"archived_at": str(timezone.now().date()), "automation": False}
                ),
                actor_id=str(request.user.id),
                issue_id=str(issue.id),
                project_id=str(project_id),
                current_instance=json.dumps(
                    IssueSerializer(issue).data, cls=DjangoJSONEncoder
                ),
                epoch=int(timezone.now().timestamp()),
                notification=True,
                origin=base_host(request=request, is_app=True),
            )
            
            # 5. Prepare for bulk update
            issue.archived_at = timezone.now().date()
            bulk_archive_issues.append(issue)
        
        # 6. Perform bulk update
        Issue.objects.bulk_update(bulk_archive_issues, ["archived_at"])

        return Response(
            {"archived_at": str(timezone.now().date())}, 
            status=status.HTTP_200_OK
        )
```

### Example 2: IssueBulkUpdateDateEndpoint

**Purpose**: Update start and target dates for multiple issues with validation.

**Key Features**:
- Custom validation method
- Flexible update structure (array of updates)
- Individual field tracking for activity logs
- Date validation logic

```python
class IssueBulkUpdateDateEndpoint(BaseAPIView):
    def validate_dates(self, current_start, current_target, new_start, new_target):
        """Validate that start date is before target date."""
        from datetime import datetime

        start = new_start or current_start
        target = new_target or current_target

        # Convert string dates to datetime objects if they're strings
        if isinstance(start, str):
            start = datetime.strptime(start, "%Y-%m-%d").date()
        if isinstance(target, str):
            target = datetime.strptime(target, "%Y-%m-%d").date()

        if start and target and start > target:
            return False
        return True

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id):
        # 1. Extract updates array
        updates = request.data.get("updates", [])
        issue_ids = [update["id"] for update in updates]
        epoch = int(timezone.now().timestamp())

        # 2. Fetch all relevant issues in a single query
        issues = list(Issue.objects.filter(id__in=issue_ids))
        issues_dict = {str(issue.id): issue for issue in issues}
        issues_to_update = []

        # 3. Process each update
        for update in updates:
            issue_id = update["id"]
            issue = issues_dict.get(issue_id)

            if not issue:
                continue

            start_date = update.get("start_date")
            target_date = update.get("target_date")
            
            # 4. Validate dates
            validate_dates = self.validate_dates(
                issue.start_date, issue.target_date, start_date, target_date
            )
            if not validate_dates:
                return Response(
                    {"message": "Start date cannot exceed target date"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # 5. Log individual field changes
            if start_date:
                issue_activity.delay(
                    type="issue.activity.updated",
                    requested_data=json.dumps({"start_date": update.get("start_date")}),
                    current_instance=json.dumps({"start_date": str(issue.start_date)}),
                    issue_id=str(issue_id),
                    actor_id=str(request.user.id),
                    project_id=str(project_id),
                    epoch=epoch,
                )
                issue.start_date = start_date

            if target_date:
                issue_activity.delay(
                    type="issue.activity.updated",
                    requested_data=json.dumps({"target_date": update.get("target_date")}),
                    current_instance=json.dumps({"target_date": str(issue.target_date)}),
                    issue_id=str(issue_id),
                    actor_id=str(request.user.id),
                    project_id=str(project_id),
                    epoch=epoch,
                )
                issue.target_date = target_date

            if start_date or target_date:
                issues_to_update.append(issue)

        # 6. Bulk update issues
        Issue.objects.bulk_update(issues_to_update, ["start_date", "target_date"])

        return Response(
            {"message": "Issues updated successfully"}, 
            status=status.HTTP_200_OK
        )
```

## Step-by-Step Implementation Guide

### Step 1: Define Your Endpoint Class

1. **Choose the base class**:
   - `BaseAPIView` for simple bulk operations
   - `BaseViewSet` for complex CRUD operations

2. **Add permission classes** (optional):
   ```python
   permission_classes = [ProjectEntityPermission]
   ```

### Step 2: Implement Input Validation

```python
@allow_permission([ROLE.ADMIN, ROLE.MEMBER])
def post(self, request, slug, project_id):
    # Extract input data
    data = request.data.get("field_name", [])
    
    # Validate required fields
    if not data:
        return Response(
            {"error": "Required field is missing"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
```

### Step 3: Query and Fetch Data

```python
# Use select_related/prefetch_related for performance
items = Model.objects.filter(
    workspace__slug=slug,
    project_id=project_id,
    pk__in=item_ids
).select_related("related_field").prefetch_related("many_to_many_field")
```

### Step 4: Implement Business Logic Validation

```python
items_to_update = []
for item in items:
    # Validate business rules
    if not meets_criteria(item):
        return Response(
            {"error": "Validation failed", "item_id": item.id},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Prepare for update
    item.field = new_value
    items_to_update.append(item)
```

### Step 5: Log Activities

```python
# Log individual activities
for item in items_to_update:
    activity_task.delay(
        type="model.activity.updated",
        requested_data=json.dumps({"field": new_value}),
        current_instance=json.dumps({"field": old_value}),
        actor_id=str(request.user.id),
        item_id=str(item.id),
        project_id=str(project_id),
        epoch=int(timezone.now().timestamp()),
        notification=True,
        origin=base_host(request=request, is_app=True),
    )
```

### Step 6: Perform Bulk Update

```python
# Use bulk_update for performance
Model.objects.bulk_update(items_to_update, ["field1", "field2"], batch_size=100)
```

### Step 7: Return Response

```python
return Response(
    {"message": "Operation completed successfully", "updated_count": len(items_to_update)},
    status=status.HTTP_200_OK
)
```

### Step 8: Add URL Configuration

In `/apiserver/plane/app/urls/issue.py`:

```python
from .views import YourBulkEndpoint

# Add to urlpatterns
path(
    "workspaces/<str:slug>/projects/<uuid:project_id>/bulk-your-action/",
    YourBulkEndpoint.as_view(),
    name="bulk-your-action",
),
```

### Step 9: Import in Views Module

In `/apiserver/plane/app/views/__init__.py`:

```python
from .issue.your_module import YourBulkEndpoint
```

## Best Practices

### 1. Database Performance

- **Use `select_related()`** for foreign key relationships
- **Use `prefetch_related()`** for many-to-many relationships
- **Implement `bulk_update()`** with appropriate `batch_size` (typically 100-500)
- **Filter efficiently** using database indexes

```python
# Good
issues = Issue.objects.filter(
    workspace__slug=slug, 
    project_id=project_id, 
    pk__in=issue_ids
).select_related("state", "project").prefetch_related("assignees", "labels")

# Less efficient
issues = Issue.objects.filter(pk__in=issue_ids)
for issue in issues:
    # This causes N+1 queries
    state_name = issue.state.name
```

### 2. Error Handling

- **Validate input early** and return clear error messages
- **Use appropriate HTTP status codes**
- **Provide specific error codes** for different failure scenarios
- **Handle edge cases** gracefully

```python
# Validate required fields
if not issue_ids:
    return Response(
        {"error": "Issue IDs are required"}, 
        status=status.HTTP_400_BAD_REQUEST
    )

# Validate business rules
if not valid_state:
    return Response(
        {
            "error_code": ERROR_CODES["INVALID_STATE"],
            "error_message": "Invalid state for this operation",
        },
        status=status.HTTP_400_BAD_REQUEST,
    )
```

### 3. Activity Logging

- **Log activities asynchronously** using Celery tasks
- **Include relevant context** in activity logs
- **Use consistent activity types** across the application
- **Include current and requested data** for audit trails

```python
issue_activity.delay(
    type="issue.activity.updated",
    requested_data=json.dumps(requested_changes),
    current_instance=json.dumps(current_state),
    actor_id=str(request.user.id),
    issue_id=str(issue.id),
    project_id=str(project_id),
    epoch=int(timezone.now().timestamp()),
    notification=True,
    origin=base_host(request=request, is_app=True),
)
```

### 4. Permission Management

- **Use role-based permissions** consistently
- **Check permissions early** in the request cycle
- **Use appropriate permission classes** for additional security

```python
@allow_permission([ROLE.ADMIN, ROLE.MEMBER])
def post(self, request, slug, project_id):
    # Your implementation
    pass
```

### 5. Response Format

- **Return consistent response formats**
- **Include relevant metadata** (count, timestamp, etc.)
- **Provide meaningful success messages**

```python
return Response(
    {
        "message": "Issues updated successfully",
        "updated_count": len(items_updated),
        "timestamp": timezone.now().isoformat(),
    },
    status=status.HTTP_200_OK
)
```

## Error Handling

### Common Error Scenarios

1. **Missing Required Data**:
   ```python
   if not required_field:
       return Response(
           {"error": "Required field is missing"},
           status=status.HTTP_400_BAD_REQUEST
       )
   ```

2. **Business Rule Violations**:
   ```python
   if not meets_business_rules(item):
       return Response(
           {
               "error_code": ERROR_CODES["BUSINESS_RULE_VIOLATION"],
               "error_message": "Operation not allowed for current state",
           },
           status=status.HTTP_400_BAD_REQUEST,
       )
   ```

3. **Partial Failures**:
   ```python
   # For operations that can partially succeed
   successful_items = []
   failed_items = []
   
   for item in items:
       try:
           # Process item
           successful_items.append(item)
       except Exception as e:
           failed_items.append({"item_id": item.id, "error": str(e)})
   
   return Response({
       "successful_count": len(successful_items),
       "failed_count": len(failed_items),
       "failures": failed_items
   })
   ```

## Testing Considerations

### 1. Unit Tests

Test each component in isolation:

```python
def test_bulk_action_validation(self):
    # Test input validation
    response = self.client.post(url, {"invalid": "data"})
    self.assertEqual(response.status_code, 400)

def test_bulk_action_success(self):
    # Test successful bulk operation
    response = self.client.post(url, valid_data)
    self.assertEqual(response.status_code, 200)
    # Verify database changes
```

### 2. Integration Tests

Test the complete flow:

```python
def test_bulk_action_with_permissions(self):
    # Test with different user roles
    # Test activity logging
    # Test database consistency
```

### 3. Performance Tests

```python
def test_bulk_action_performance(self):
    # Test with large datasets
    # Verify query count
    # Measure execution time
```

## Example: Implementing a Bulk Label Assignment Endpoint

Here's a complete example implementing a bulk label assignment feature:

```python
# In plane/app/views/issue/bulk_actions.py
import json
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import allow_permission, ROLE
from plane.bgtasks.issue_activities_task import issue_activity
from plane.db.models import Issue, Label
from plane.utils.host import base_host
from .. import BaseAPIView

class BulkAssignLabelsEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id):
        # 1. Extract and validate input
        issue_ids = request.data.get("issue_ids", [])
        label_ids = request.data.get("label_ids", [])
        
        if not issue_ids:
            return Response(
                {"error": "Issue IDs are required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not label_ids:
            return Response(
                {"error": "Label IDs are required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Verify labels exist in the project
        labels = Label.objects.filter(
            project_id=project_id,
            workspace__slug=slug,
            id__in=label_ids
        )
        
        if len(labels) != len(label_ids):
            return Response(
                {"error": "Some labels not found in project"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Fetch issues
        issues = Issue.objects.filter(
            workspace__slug=slug,
            project_id=project_id,
            pk__in=issue_ids
        ).prefetch_related("labels")

        # 4. Process each issue
        epoch = int(timezone.now().timestamp())
        for issue in issues:
            current_labels = list(issue.labels.values_list('id', flat=True))
            
            # Add new labels
            issue.labels.add(*label_ids)
            
            # Log activity
            issue_activity.delay(
                type="issue.activity.updated",
                requested_data=json.dumps({
                    "labels": label_ids,
                    "action": "add"
                }),
                current_instance=json.dumps({
                    "labels": current_labels
                }),
                actor_id=str(request.user.id),
                issue_id=str(issue.id),
                project_id=str(project_id),
                epoch=epoch,
                notification=True,
                origin=base_host(request=request, is_app=True),
            )

        return Response(
            {
                "message": "Labels assigned successfully",
                "issues_updated": len(issues),
                "labels_assigned": len(labels)
            },
            status=status.HTTP_200_OK
        )
```

And add the URL pattern:

```python
# In plane/app/urls/issue.py
path(
    "workspaces/<str:slug>/projects/<uuid:project_id>/bulk-assign-labels/",
    BulkAssignLabelsEndpoint.as_view(),
    name="bulk-assign-labels",
),
```

This guide provides a comprehensive framework for implementing bulk action endpoints. Follow these patterns and best practices to ensure consistency, performance, and maintainability across your bulk operations.
