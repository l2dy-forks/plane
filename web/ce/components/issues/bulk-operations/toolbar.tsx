import { useState } from "react";
import { observer } from "mobx-react";
import { Bell, Archive, Trash2, CalendarClock, CalendarCheck2, Users, Tag } from "lucide-react";
// ui
import { StateGroupIcon, PriorityIcon, Tooltip, Checkbox } from "@plane/ui";
// components
import { StateDropdown, PriorityDropdown, MemberDropdown, DateDropdown, CycleDropdown, ModuleDropdown } from "@/components/dropdowns";
import { LabelDropdown } from "@/components/issues/issue-layouts/properties/label-dropdown";
import { BulkOperationsActionsRoot } from "./actions";
// helpers
import { cn } from "@/helpers/common.helper";
// hooks
import { useIssues, useMultipleSelectStore, useProject, useRouterParams } from "@/hooks/store";
import { TSelectionHelper } from "@/hooks/use-multiple-select";
// types
import { TBulkOperationsPayload } from "@plane/types";

type Props = {
  className?: string;
  selectionHelpers: TSelectionHelper;
};

export const BulkOperationsToolbar: React.FC<Props> = observer((props) => {
  const { className, selectionHelpers } = props;

  // states
  const [bulkOperations, setBulkOperations] = useState<Partial<TBulkOperationsPayload["properties"]>>({});
  const [isUpdating, setIsUpdating] = useState(false);

  // store hooks
  const { selectedEntityIds } = useMultipleSelectStore();
  const { workspaceSlug, projectId } = useRouterParams();
  const { getProjectById } = useProject();
  const { issues } = useIssues();

  // derived values
  const project = projectId ? getProjectById(projectId) : null;
  const selectedCount = selectedEntityIds.length;

  // handlers
  const handleSelectAllToggle = () => {
    selectionHelpers.handleClearSelection();
  };

  const handleBulkUpdate = async () => {
    if (!workspaceSlug || !projectId || !selectedEntityIds.length || !bulkOperations) return;

    setIsUpdating(true);
    try {
      await issues.bulkUpdateProperties(workspaceSlug, projectId, {
        issue_ids: selectedEntityIds,
        properties: bulkOperations,
      });
      selectionHelpers.handleClearSelection();
      setBulkOperations({});
    } catch (error) {
      console.error("Failed to update issues:", error);
    } finally {
      setIsUpdating(false);
    }
  };

  const updateBulkProperty = (property: keyof TBulkOperationsPayload["properties"], value: any) => {
    setBulkOperations((prev) => ({
      ...prev,
      [property]: value,
    }));
  };

  if (!selectedEntityIds.length) return null;

  return (
    <div className={cn("sticky bottom-0 left-0 z-10 h-14", className)}>
      <div className="size-full bg-custom-background-100 border-t border-custom-border-200 py-4 px-3.5 flex items-center divide-x-[0.5px] divide-custom-border-200 text-custom-text-300">
        {/* Selection controls */}
        <div className="h-7 pr-3 text-sm flex items-center gap-2 flex-shrink-0">
          <Checkbox
            checked={selectedCount > 0}
            onChange={handleSelectAllToggle}
            className="size-3.5"
            iconClassName="size-3"
            indeterminate={selectedCount > 0}
          />
          <div className="flex items-center gap-1">
            <span className="flex-shrink-0" style={{ minWidth: "8px" }}>
              {selectedCount}
            </span>
            selected
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
                      disabled={!selectedCount}
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
                      disabled={!selectedCount}
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
                      disabled={!selectedCount}
                    />
                  </div>

                  {/* Start date */}
                  <div className="h-6">
                    <DateDropdown
                      value={bulkOperations.start_date ? new Date(bulkOperations.start_date) : null}
                      onChange={(val) => updateBulkProperty("start_date", val ? val.toISOString().split("T")[0] : null)}
                      placeholder="Start date"
                      icon={<CalendarClock className="size-3 flex-shrink-0" />}
                      buttonVariant="border-with-text"
                      className="h-full"
                      placement="top-start"
                      disabled={!selectedCount}
                    />
                  </div>

                  {/* Due date */}
                  <div className="h-6">
                    <DateDropdown
                      value={bulkOperations.target_date ? new Date(bulkOperations.target_date) : null}
                      onChange={(val) => updateBulkProperty("target_date", val ? val.toISOString().split("T")[0] : null)}
                      placeholder="Due date"
                      icon={<CalendarCheck2 className="size-3 flex-shrink-0" />}
                      buttonVariant="border-with-text"
                      className="h-full"
                      placement="top-start"
                      disabled={!selectedCount}
                    />
                  </div>

                  {/* Labels */}
                  <div className="h-6">
                    <LabelDropdown
                      value={bulkOperations.label_ids ?? []}
                      onChange={(val) => updateBulkProperty("label_ids", val)}
                      projectId={projectId || null}
                      className="h-full"
                      disabled={!selectedCount}
                      placement="top-start"
                      hideDropdownArrow={true}
                      fullHeight={true}
                      buttonClassName="h-full w-full flex items-center gap-1.5 border-[0.5px] border-custom-border-300 hover:bg-custom-background-80 rounded text-xs px-2 py-0.5"
                      label={
                        <div className="flex items-center gap-1.5">
                          <Tag className="h-3 w-3 flex-shrink-0" />
                          <span className="max-w-40 flex-grow truncate">Labels</span>
                        </div>
                      }
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
                      disabled={!selectedCount}
                    />
                  </div>

                  {/* Module */}
                  <div className="h-6">
                    <ModuleDropdown
                      value={bulkOperations.module_ids ?? []}
                      onChange={(val) => updateBulkProperty("module_ids", val)}
                      projectId={projectId}
                      multiple
                      buttonVariant="border-with-text"
                      className="h-full"
                      placeholder="Module"
                      placement="top-start"
                      disabled={!selectedCount}
                    />
                  </div>
                </div>

                {/* Update button */}
                <button
                  type="button"
                  className="text-white bg-custom-primary-100 hover:bg-custom-primary-200 focus:text-custom-brand-40 focus:bg-custom-primary-200 px-3 font-medium text-xs rounded flex items-center gap-1.5 whitespace-nowrap transition-all justify-center py-1 disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={handleBulkUpdate}
                  disabled={isUpdating || Object.keys(bulkOperations).length === 0}
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
