import type { BoardAltFunction } from "../../contracts/api";
import type { ProjectShellController } from "../../project/useProjectShellController";
import { selectPinAssignmentsViewModel } from "../../project/selectors";
import type { PinAssignmentAltFunctionOptionViewModel, PinAssignmentsViewModel } from "../../shared/viewModels/pinAssignments";

export interface PinConfiguratorCommandApi {
  clearPinAssignment: (pinNumber: string) => void;
  assignPinAltFunction: (pinNumber: string, option: PinAssignmentAltFunctionOptionViewModel) => void;
  updatePinBooleanProperty: (pinNumber: string, propertyKey: string, value: boolean) => void;
}

export interface PinConfiguratorPresenter extends PinConfiguratorCommandApi {
  pinAssignments: PinAssignmentsViewModel;
  hydratedPinStates: ProjectShellController["hydratedPinStates"];
}

type PinConfiguratorPresenterInput = Pick<
  ProjectShellController,
  "activeBoardDefinition" | "hydratedPinStates" | "projectDocument" | "clearPinAssignment" | "updatePinAltFunction" | "updatePinBooleanProperty"
>;

export function createPinConfiguratorPresenter({
  activeBoardDefinition,
  hydratedPinStates,
  projectDocument,
  clearPinAssignment,
  updatePinAltFunction,
  updatePinBooleanProperty,
}: PinConfiguratorPresenterInput): PinConfiguratorPresenter {
  return {
    pinAssignments: selectPinAssignmentsViewModel(
      projectDocument.pin_states,
      hydratedPinStates,
      activeBoardDefinition,
      projectDocument.periph_states,
    ),
    hydratedPinStates,
    clearPinAssignment,
    assignPinAltFunction(pinNumber, option) {
      const altFunction: BoardAltFunction = {
        function_id: option.functionId,
        pincm: option.pincm,
        name: option.name,
        peripheral: option.peripheral,
        signal: option.signal,
        direction: option.direction,
        zephyr_pinmux: "",
      };

      updatePinAltFunction(pinNumber, altFunction);
    },
    updatePinBooleanProperty,
  };
}