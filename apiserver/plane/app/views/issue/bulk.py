# Python imports
import json
from datetime import datetime

# Django imports
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

# Third Party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from .. import BaseAPIView
from plane.app.permissions import allow_permission, ROLE, ProjectEntityPermission
from plane.bgtasks.issue_activities_task import issue_activity
from plane.db.models import (
    Issue,
    State,
    Label,
    Module,
    Cycle,
    EstimatePoint,
    User,
    IssueAssignee,
    IssueLabel,
)
from plane.utils.host import base_host


class BulkOperationIssuesEndpoint(BaseAPIView):
    """
    Bulk update multiple issues with various properties in a single API call.

    Supports updating:
    - State (state_id)
    - Priority (urgent, high, medium, low, null)
    - Assignees (assignee_ids as array)
    - Labels (label_ids as array, appends to existing labels)
    - Start date and target date
    - Modules (module_ids as array, appends to existing modules)
    - Cycles (cycle_id as single value)
    - Estimate points
    """

    permission_classes = [ProjectEntityPermission]
    VALID_PRIORITIES = ["urgent", "high", "medium", "low", "none"]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id):
        try:
            issue_ids = request.data.get("issue_ids", [])
            properties = request.data.get("properties", {})

            # Validate input
            if not issue_ids:
                return Response(
                    {"error": "Issue IDs are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not properties:
                return Response(
                    {"error": "Properties to update are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate that all issue_ids exist and belong to the project
            issues = (
                Issue.objects.filter(
                    workspace__slug=slug, project_id=project_id, pk__in=issue_ids
                )
                .select_related("state", "project", "estimate_point")
                .prefetch_related(
                    "assignees", "labels", "issue_module__module", "issue_cycle__cycle"
                )
            )

            if len(issues) != len(issue_ids):
                return Response(
                    {"error": "One or more issues not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Validate properties
            validation_error = self._validate_properties(properties, slug, project_id)
            if validation_error:
                return Response(validation_error, status=status.HTTP_400_BAD_REQUEST)

            # Process updates
            updated_issues = []
            updated_issues_details = []
            epoch = int(timezone.now().timestamp())

            for issue in issues:
                issue_updated = False
                updated_properties = []
                requested_data = {}

                # Update state
                if "state_id" in properties:
                    state_id = properties["state_id"]
                    if issue.state_id != state_id:
                        old_state_id = issue.state_id
                        issue.state_id = state_id
                        requested_data["state_id"] = state_id
                        updated_properties.append("state_id")
                        issue_updated = True

                        # Log activity
                        issue_activity.delay(
                            type="issue.activity.updated",
                            requested_data=json.dumps(
                                {"state_id": state_id}, cls=DjangoJSONEncoder
                            ),
                            current_instance=json.dumps(
                                {"state_id": old_state_id}, cls=DjangoJSONEncoder
                            ),
                            issue_id=str(issue.id),
                            actor_id=str(request.user.id),
                            project_id=str(project_id),
                            epoch=epoch,
                            notification=True,
                            origin=base_host(request=request, is_app=True),
                        )

                # Update priority
                if "priority" in properties:
                    priority = properties["priority"]
                    if issue.priority != priority:
                        old_priority = issue.priority
                        issue.priority = priority
                        requested_data["priority"] = priority
                        updated_properties.append("priority")
                        issue_updated = True

                        # Log activity
                        issue_activity.delay(
                            type="issue.activity.updated",
                            requested_data=json.dumps(
                                {"priority": priority}, cls=DjangoJSONEncoder
                            ),
                            current_instance=json.dumps(
                                {"priority": old_priority}, cls=DjangoJSONEncoder
                            ),
                            issue_id=str(issue.id),
                            actor_id=str(request.user.id),
                            project_id=str(project_id),
                            epoch=epoch,
                            notification=True,
                            origin=base_host(request=request, is_app=True),
                        )

                # Update dates
                if "start_date" in properties:
                    start_date = properties["start_date"]
                    if start_date == "":
                        start_date = None

                    if str(issue.start_date) != str(start_date):
                        old_start_date = issue.start_date
                        issue.start_date = start_date
                        requested_data["start_date"] = start_date
                        updated_properties.append("start_date")
                        issue_updated = True

                        # Log activity
                        issue_activity.delay(
                            type="issue.activity.updated",
                            requested_data=json.dumps(
                                {"start_date": str(start_date) if start_date else None},
                                cls=DjangoJSONEncoder,
                            ),
                            current_instance=json.dumps(
                                {
                                    "start_date": str(old_start_date)
                                    if old_start_date
                                    else None
                                },
                                cls=DjangoJSONEncoder,
                            ),
                            issue_id=str(issue.id),
                            actor_id=str(request.user.id),
                            project_id=str(project_id),
                            epoch=epoch,
                            notification=True,
                            origin=base_host(request=request, is_app=True),
                        )

                if "target_date" in properties:
                    target_date = properties["target_date"]
                    if target_date == "":
                        target_date = None

                    if str(issue.target_date) != str(target_date):
                        old_target_date = issue.target_date
                        issue.target_date = target_date
                        requested_data["target_date"] = target_date
                        updated_properties.append("target_date")
                        issue_updated = True

                        # Log activity
                        issue_activity.delay(
                            type="issue.activity.updated",
                            requested_data=json.dumps(
                                {
                                    "target_date": str(target_date)
                                    if target_date
                                    else None
                                },
                                cls=DjangoJSONEncoder,
                            ),
                            current_instance=json.dumps(
                                {
                                    "target_date": str(old_target_date)
                                    if old_target_date
                                    else None
                                },
                                cls=DjangoJSONEncoder,
                            ),
                            issue_id=str(issue.id),
                            actor_id=str(request.user.id),
                            project_id=str(project_id),
                            epoch=epoch,
                            notification=True,
                            origin=base_host(request=request, is_app=True),
                        )

                # Update estimate point
                if "estimate_point" in properties:
                    estimate_point_id = properties["estimate_point"]
                    if estimate_point_id == "":
                        estimate_point_id = None

                    if issue.estimate_point_id != estimate_point_id:
                        old_estimate_point_id = issue.estimate_point_id
                        issue.estimate_point_id = estimate_point_id
                        requested_data["estimate_point"] = estimate_point_id
                        updated_properties.append("estimate_point")
                        issue_updated = True

                        # Log activity
                        issue_activity.delay(
                            type="issue.activity.updated",
                            requested_data=json.dumps(
                                {"estimate_point_id": estimate_point_id},
                                cls=DjangoJSONEncoder,
                            ),
                            current_instance=json.dumps(
                                {"estimate_point_id": old_estimate_point_id},
                                cls=DjangoJSONEncoder,
                            ),
                            issue_id=str(issue.id),
                            actor_id=str(request.user.id),
                            project_id=str(project_id),
                            epoch=epoch,
                            notification=True,
                            origin=base_host(request=request, is_app=True),
                        )

                if issue_updated:
                    updated_issues.append(issue)
                    updated_issues_details.append(
                        {"id": str(issue.id), "updated_properties": updated_properties}
                    )

            # Bulk update simple fields that can be updated directly on the Issue model
            if updated_issues:
                fields_to_update = []

                # Map property names to Issue model field names
                if "state_id" in properties:
                    fields_to_update.append("state")
                if "priority" in properties:
                    fields_to_update.append("priority")
                if "start_date" in properties:
                    fields_to_update.append("start_date")
                if "target_date" in properties:
                    fields_to_update.append("target_date")
                if "estimate_point" in properties:
                    fields_to_update.append("estimate_point")

                if fields_to_update:
                    Issue.objects.bulk_update(updated_issues, fields_to_update)

            # Handle many-to-many and join table relationships separately
            relationship_updates = self._handle_relationship_updates(
                issues, properties, request.user.id, project_id, epoch, request
            )

            # Merge relationship updates with simple field updates
            for issue_id, updated_properties in relationship_updates.items():
                # Find existing detail entry or create new one
                existing_detail = None
                for detail in updated_issues_details:
                    if detail["id"] == issue_id:
                        existing_detail = detail
                        break

                if existing_detail:
                    existing_detail["updated_properties"].extend(updated_properties)
                else:
                    updated_issues_details.append(
                        {"id": issue_id, "updated_properties": updated_properties}
                    )

            return Response(
                {
                    "message": "Issues updated successfully",
                    "updated_issues": len(updated_issues_details),
                    "issues": updated_issues_details,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _validate_properties(self, properties, slug, project_id):
        """Validate the properties to be updated"""

        # Validate state
        if "state_id" in properties:
            state_id = properties["state_id"]
            if (
                state_id
                and not State.objects.filter(
                    id=state_id, project_id=project_id
                ).exists()
            ):
                return {
                    "error": "Invalid property values",
                    "details": {"invalid_state_id": [str(state_id)]},
                }

        # Validate priority
        if "priority" in properties:
            priority = properties["priority"]
            if priority not in self.VALID_PRIORITIES:
                return {
                    "error": "Invalid priority. Must be one of: urgent, high, medium, low, or none"
                }

        # Validate dates
        if "start_date" in properties and "target_date" in properties:
            start_date = properties["start_date"]
            target_date = properties["target_date"]
            if start_date and target_date and start_date != "" and target_date != "":
                try:
                    start = datetime.strptime(start_date, "%Y-%m-%d").date()
                    target = datetime.strptime(target_date, "%Y-%m-%d").date()
                    if start > target:
                        return {"error": "Start date cannot exceed target date"}
                except ValueError:
                    return {"error": "Invalid date format. Use YYYY-MM-DD"}

        # Validate assignees
        if "assignee_ids" in properties:
            assignee_ids = properties["assignee_ids"]
            if assignee_ids and not User.objects.filter(
                id__in=assignee_ids
            ).count() == len(assignee_ids):
                invalid_ids = [
                    str(uid)
                    for uid in assignee_ids
                    if not User.objects.filter(id=uid).exists()
                ]
                return {
                    "error": "Invalid property values",
                    "details": {"invalid_assignee_ids": invalid_ids},
                }

        # Validate labels
        if "label_ids" in properties:
            label_ids = properties["label_ids"]
            if label_ids and not Label.objects.filter(
                id__in=label_ids, project_id=project_id
            ).count() == len(label_ids):
                invalid_ids = [
                    str(lid)
                    for lid in label_ids
                    if not Label.objects.filter(id=lid, project_id=project_id).exists()
                ]
                return {
                    "error": "Invalid property values",
                    "details": {"invalid_label_ids": invalid_ids},
                }

        # Validate modules
        if "module_ids" in properties:
            module_ids = properties["module_ids"]
            if module_ids and not Module.objects.filter(
                id__in=module_ids, project_id=project_id
            ).count() == len(module_ids):
                invalid_ids = [
                    str(mid)
                    for mid in module_ids
                    if not Module.objects.filter(id=mid, project_id=project_id).exists()
                ]
                return {
                    "error": "Invalid property values",
                    "details": {"invalid_module_ids": invalid_ids},
                }

        # Validate cycle - an issue can only belong to one cycle at a time
        if "cycle_id" in properties:
            cycle_id = properties["cycle_id"]
            if (
                cycle_id
                and not Cycle.objects.filter(
                    id=cycle_id, project_id=project_id
                ).exists()
            ):
                return {
                    "error": "Invalid property values",
                    "details": {"invalid_cycle_id": [str(cycle_id)]},
                }

        # Validate estimate point
        if "estimate_point" in properties:
            estimate_point_id = properties["estimate_point"]
            if (
                estimate_point_id
                and estimate_point_id != ""
                and not EstimatePoint.objects.filter(
                    id=estimate_point_id, estimate__project_id=project_id
                ).exists()
            ):
                return {
                    "error": "Invalid property values",
                    "details": {"invalid_estimate_point": [str(estimate_point_id)]},
                }

        return None

    def _track_issue_update(self, updated_issues_map, issue_id, property_name):
        """Helper method to track which properties were updated for each issue"""
        issue_id_str = str(issue_id)
        if issue_id_str not in updated_issues_map:
            updated_issues_map[issue_id_str] = []
        updated_issues_map[issue_id_str].append(property_name)

    def _handle_relationship_updates(
        self, issues, properties, user_id, project_id, epoch, request
    ):
        """
        Handle relationship updates that require separate join tables.

        This includes:
        - Assignees (many-to-many through IssueAssignee)
        - Labels (many-to-many through IssueLabel)
        - Modules (many-to-many through ModuleIssue)
        - Cycles (one-to-many through CycleIssue join table)

        Returns a map of issue_id -> list of updated properties
        """
        updated_issues_map = {}

        # Handle assignees - completely replace existing assignees
        if "assignee_ids" in properties:
            new_assignee_ids = properties["assignee_ids"] or []

            for issue in issues:
                current_assignee_ids = set(issue.assignees.values_list("id", flat=True))
                new_assignee_ids_set = set(new_assignee_ids)

                if new_assignee_ids_set != current_assignee_ids:
                    # Remove all existing assignees
                    IssueAssignee.objects.filter(issue=issue).delete()

                    # Create new assignee relationships
                    if new_assignee_ids_set:
                        new_assignee_objects = [
                            IssueAssignee(
                                issue=issue,
                                assignee_id=assignee_id,
                                project_id=project_id,
                                workspace_id=issue.workspace_id,
                                created_by_id=user_id,
                                updated_by_id=user_id,
                            )
                            for assignee_id in new_assignee_ids_set
                        ]
                        IssueAssignee.objects.bulk_create(
                            new_assignee_objects, batch_size=10
                        )

                    # Track this update
                    self._track_issue_update(
                        updated_issues_map, issue.id, "assignee_ids"
                    )

                    # Log activity for audit trail
                    issue_activity.delay(
                        type="issue.activity.updated",
                        requested_data=json.dumps(
                            {"assignee_ids": list(new_assignee_ids_set)},
                            cls=DjangoJSONEncoder,
                        ),
                        current_instance=json.dumps(
                            {"assignee_ids": list(current_assignee_ids)},
                            cls=DjangoJSONEncoder,
                        ),
                        issue_id=str(issue.id),
                        actor_id=str(user_id),
                        project_id=str(project_id),
                        epoch=epoch,
                        notification=True,
                        origin=base_host(request=request, is_app=True),
                    )

        # Handle labels - append new labels to existing ones (additive)
        if "label_ids" in properties:
            new_label_ids = properties["label_ids"] or []

            for issue in issues:
                current_label_ids = set(issue.labels.values_list("id", flat=True))
                new_label_ids_set = set(new_label_ids)

                # Only add labels that don't already exist (preserve existing labels)
                labels_to_add = new_label_ids_set - current_label_ids
                combined_label_ids = current_label_ids.union(labels_to_add)

                if labels_to_add:
                    # Create new label associations
                    new_label_objects = [
                        IssueLabel(
                            issue=issue,
                            label_id=label_id,
                            project_id=issue.project_id,
                            workspace_id=issue.workspace_id,
                            created_by_id=request.user.id,
                            updated_by_id=request.user.id,
                        )
                        for label_id in labels_to_add
                    ]
                    IssueLabel.objects.bulk_create(new_label_objects)

                    # Track this update
                    self._track_issue_update(updated_issues_map, issue.id, "label_ids")

                    # Log activity for audit trail
                    issue_activity.delay(
                        type="issue.activity.updated",
                        requested_data=json.dumps(
                            {"label_ids": list(combined_label_ids)},
                            cls=DjangoJSONEncoder,
                        ),
                        current_instance=json.dumps(
                            {"label_ids": list(current_label_ids)},
                            cls=DjangoJSONEncoder,
                        ),
                        issue_id=str(issue.id),
                        actor_id=str(user_id),
                        project_id=str(project_id),
                        epoch=epoch,
                        notification=True,
                        origin=base_host(request=request, is_app=True),
                    )

        # Handle modules - append new modules to existing ones (additive)
        if "module_ids" in properties:
            from plane.db.models import ModuleIssue

            new_module_ids = properties["module_ids"] or []

            for issue in issues:
                current_module_ids = set(
                    issue.issue_module.values_list("module_id", flat=True)
                )
                new_module_ids_set = set(new_module_ids)

                # Only add modules that don't already exist (preserve existing modules)
                modules_to_add = new_module_ids_set - current_module_ids
                combined_module_ids = current_module_ids.union(modules_to_add)

                if modules_to_add:
                    # Create new module associations
                    new_module_objects = [
                        ModuleIssue(
                            issue=issue,
                            module_id=module_id,
                            project_id=issue.project_id,
                            workspace_id=issue.workspace_id,
                            created_by_id=user_id,
                            updated_by_id=user_id,
                        )
                        for module_id in modules_to_add
                    ]
                    ModuleIssue.objects.bulk_create(new_module_objects)

                    # Track this update
                    self._track_issue_update(updated_issues_map, issue.id, "module_ids")

                    # Log activity for audit trail
                    issue_activity.delay(
                        type="issue.activity.updated",
                        requested_data=json.dumps(
                            {"module_ids": list(combined_module_ids)},
                            cls=DjangoJSONEncoder,
                        ),
                        current_instance=json.dumps(
                            {"module_ids": list(current_module_ids)},
                            cls=DjangoJSONEncoder,
                        ),
                        issue_id=str(issue.id),
                        actor_id=str(user_id),
                        project_id=str(project_id),
                        epoch=epoch,
                        notification=True,
                        origin=base_host(request=request, is_app=True),
                    )

        # Handle cycles - replace existing cycle (one issue can only be in one cycle)
        # Note: Uses CycleIssue join table instead of direct foreign key for audit/metadata purposes
        if "cycle_id" in properties:
            from plane.db.models import CycleIssue

            new_cycle_id = properties["cycle_id"]

            for issue in issues:
                current_cycle_ids = set(
                    issue.issue_cycle.values_list("cycle_id", flat=True)
                )
                new_cycle_ids = {new_cycle_id} if new_cycle_id else set()

                if new_cycle_ids != current_cycle_ids:
                    # Remove all existing cycle associations (issue can only be in one cycle)
                    CycleIssue.objects.filter(issue=issue).delete()

                    # Create new cycle association if cycle_id provided
                    if new_cycle_id:
                        CycleIssue.objects.create(
                            issue=issue,
                            cycle_id=new_cycle_id,
                            project_id=issue.project_id,
                            workspace_id=issue.workspace_id,
                            created_by_id=user_id,
                            updated_by_id=user_id,
                        )

                    # Track this update
                    self._track_issue_update(updated_issues_map, issue.id, "cycle_id")

                    # Log activity for audit trail
                    current_cycle_id = (
                        list(current_cycle_ids)[0] if current_cycle_ids else None
                    )
                    issue_activity.delay(
                        type="issue.activity.updated",
                        requested_data=json.dumps(
                            {"cycle_id": new_cycle_id}, cls=DjangoJSONEncoder
                        ),
                        current_instance=json.dumps(
                            {"cycle_id": current_cycle_id}, cls=DjangoJSONEncoder
                        ),
                        issue_id=str(issue.id),
                        actor_id=str(user_id),
                        project_id=str(project_id),
                        epoch=epoch,
                        notification=True,
                        origin=base_host(request=request, is_app=True),
                    )

        return updated_issues_map
