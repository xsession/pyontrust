import { useShellPresenter } from "../presenters/useShellPresenter";
import { ShellView } from "../views/ShellView";

export function App() {
  const viewModel = useShellPresenter();

  return <ShellView {...viewModel} />;
}