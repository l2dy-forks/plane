import { useState, useCallback } from "react";
import { observer } from "mobx-react";
import { CalendarClock, CalendarCheck2 } from "lucide-react";
// types
import { TBulkOperationsPayload } from "@plane/types";
// ui
import { Checkbox, TOAST_TYPE, setToast } from "@plane/ui";
// components
import { StateDropdown, PriorityDropdown, MemberDropdown, DateDropdown, CycleDropdown, ModuleDropdown } from "@/components/dropdowns";
import { IssuePropertyLabels } from "@/components/issues/issue-layouts/properties/labels";
// helpers
import { cn } from "@/helpers/common.helper";
import { renderFormattedPayloadDate } from "@/helpers/date-time.helper";
// hooks
import { useIssues, useMultipleSelectStore, useRouterParams } from "@/hooks/store";
import { TSelectionHelper } from "@/hooks/use-multiple-select";
import { BulkOperationsActionsRoot } from "./actions";

type Props = {
  className?: string;
  selectionHelpers: TSelectionHelper;
};

// Extract bulk operations type for better type safety
type BulkOperationsState = Partial<TBulkOperationsPayload["properties"]>;

// Constants for better maintainability
const TOAST_MESSAGES = {
  SUCCESS: {
    title: "Success!",
    message: "Issues updated successfully.",
  },
  ERROR: {
    title: "Error!",
    message: "Something went wrong. Please try again.",
  },
} as const;

export const BulkOperationsToolbar: React.FC<Props> = observer((props) => {
  const { className, selectionHelpers } = props;

  // states
  const [bulkOperations, setBulkOperations] = useState<BulkOperationsState>({});
  const [isUpdating, setIsUpdating] = useState(false);

  // store hooks
  const { selectedEntityIds } = useMultipleSelectStore();
  const { workspaceSlug, projectId } = useRouterParams();
  const { issues } = useIssues();

  // derived values
  const selectedCount = selectedEntityIds.length;
  const hasSelectedItems = selectedCount > 0;
  const hasBulkOperations = Object.keys(bulkOperations).length > 0;

  // handlers
  const handleSelectAllToggle = useCallback(() => {
    selectionHelpers.handleClearSelection();
  }, [selectionHelpers]);

  const handleBulkUpdate = useCallback(async () => {
    if (!workspaceSlug || !projectId || !selectedEntityIds.length || !hasBulkOperations) return;

    setIsUpdating(true);
    try {
      await issues.bulkUpdateProperties(workspaceSlug, projectId, {
        issue_ids: selectedEntityIds,
        properties: bulkOperations,
      });
      setToast({
        type: TOAST_TYPE.SUCCESS,
        ...TOAST_MESSAGES.SUCCESS,
      });
      setBulkOperations({});
    } catch (error) {
      console.error("Failed to update issues:", error);
      setToast({
        type: TOAST_TYPE.ERROR,
        ...TOAST_MESSAGES.ERROR,
      });
    } finally {
      setIsUpdating(false);
    }
  }, [workspaceSlug, projectId, selectedEntityIds, bulkOperations, hasBulkOperations, issues]);

  const updateBulkProperty = useCallback((property: keyof TBulkOperationsPayload["properties"], value: unknown) => {
    setBulkOperations((prev) => ({
      ...prev,
      [property]: value,
    }));
  }, []);

  // Early return for better readability
  if (!hasSelectedItems) return null;

  return (
    <div className={cn("sticky bottom-0 left-0 z-10 h-14", className)}>
      <div className="size-full bg-custom-background-100 border-t border-custom-border-200 py-4 px-3.5 flex items-center divide-x-[0.5px] divide-custom-border-200 text-custom-text-300">
        {/* Selection controls */}
        <div className="h-7 pr-3 text-sm flex items-center gap-2 flex-shrink-0">
          <Checkbox
            checked={hasSelectedItems}
            onChange={handleSelectAllToggle}
            className="size-3.5"
            iconClassName="size-3"
            indeterminate={hasSelectedItems}
          />
          <div className="flex items-center gap-1">
            <span className="flex-shrink-0" style={{ minWidth: "8px" }}>
              {selectedCount}
            </span>
            {selectedCount === 1 ? "selected" : "selected"}
          </div>
        </div>

        <div className="flex w-full overflow-hidden overflow-x-auto" tabIndex={0}>
          <div className="flex grow">
            {/* Bulk operations actions */}
            <BulkOperationsActionsRoot
              handleClearSelection={selectionHelpers.handleClearSelection}
              selectedEntityIds={selectedEntityIds}
            />

            {/* Property selectors */}
            <div className="h-7 pl-3 flex-grow">
              <div className="size-full flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  {/* State */}
                  <div className="h-6">
                    <StateDropdown
                      value={bulkOperations.state_id ?? null}
                      onChange={(val) => updateBulkProperty("state_id", val)}
                      projectId={projectId}
                      buttonVariant="border-with-text"
                      className="h-full"
                      placeholder="State"
                      placement="top-start"
                      disabled={!hasSelectedItems}
                      showDefaultState={false}
                    />
                  </div>

                  {/* Priority */}
                  <div className="h-6">
                    <PriorityDropdown
                      value={bulkOperations.priority ?? null}
                      onChange={(val) => updateBulkProperty("priority", val)}
                      buttonVariant="border-with-text"
                      className="h-full"
                      placeholder="Priority"
                      placement="top-start"
                      disabled={!hasSelectedItems}
                    />
                  </div>

                  {/* Assignees */}
                  <div className="h-6">
                    <MemberDropdown
                      value={bulkOperations.assignee_ids ?? []}
                      onChange={(val) => updateBulkProperty("assignee_ids", val)}
                      projectId={projectId}
                      placeholder="Assignees"
                      multiple
                      buttonVariant="border-with-text"
                      className="h-full"
                      placement="top-start"
                      disabled={!hasSelectedItems}
                    />
                  </div>

                  {/* Start date */}
                  <div className="h-6">
                    <DateDropdown
                      value={bulkOperations.start_date ? new Date(bulkOperations.start_date) : null}
                      onChange={(val) => updateBulkProperty("start_date", val ? renderFormattedPayloadDate(val) : null)}
                      placeholder="Start date"
                      icon={<CalendarClock className="size-3 flex-shrink-0" />}
                      buttonVariant="border-with-text"
                      className="h-full"
                      placement="top-start"
                      disabled={!hasSelectedItems}
                    />
                  </div>

                  {/* Due date */}
                  <div className="h-6">
                    <DateDropdown
                      value={bulkOperations.target_date ? new Date(bulkOperations.target_date) : null}
                      onChange={(val) => updateBulkProperty("target_date", val ? renderFormattedPayloadDate(val) : null)}
                      placeholder="Due date"
                      icon={<CalendarCheck2 className="size-3 flex-shrink-0" />}
                      buttonVariant="border-with-text"
                      className="h-full"
                      placement="top-start"
                      disabled={!hasSelectedItems}
                    />
                  </div>

                  {/* Labels */}
                  <div className="h-6">
                    <IssuePropertyLabels
                      value={bulkOperations.label_ids ?? []}
                      onChange={(val) => updateBulkProperty("label_ids", val)}
                      projectId={projectId || null}
                      className="h-full"
                      disabled={!hasSelectedItems}
                      placement="top-start"
                      maxRender={1}
                      hideDropdownArrow
                      fullHeight
                      placeholderText="Labels"
                    />
                  </div>

                  {/* Cycle */}
                  <div className="h-6">
                    <CycleDropdown
                      value={bulkOperations.cycle_id ?? null}
                      onChange={(val) => updateBulkProperty("cycle_id", val)}
                      projectId={projectId}
                      buttonVariant="border-with-text"
                      className="h-full"
                      placeholder="Cycle"
                      placement="top-start"
                      disabled={!hasSelectedItems}
                    />
                  </div>

                  {/* Module */}
                  <div className="h-6">
                    <ModuleDropdown
                      value={bulkOperations.module_ids ?? []}
                      onChange={(val) => updateBulkProperty("module_ids", val)}
                      projectId={projectId}
                      multiple
                      showCount
                      buttonVariant="border-with-text"
                      className="h-full"
                      placeholder="Module"
                      placement="top-start"
                      disabled={!hasSelectedItems}
                    />
                  </div>
                </div>

                {/* Update button */}
                <button
                  type="button"
                  className="text-white bg-custom-primary-100 hover:bg-custom-primary-200 focus:text-custom-brand-40 focus:bg-custom-primary-200 px-3 font-medium text-xs rounded flex items-center gap-1.5 whitespace-nowrap transition-all justify-center py-1 disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={handleBulkUpdate}
                  disabled={isUpdating || !hasBulkOperations}
                  aria-label={isUpdating ? "Updating issues..." : "Update selected issues"}
                >
                  {isUpdating ? "Updating..." : "Update"}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
});
